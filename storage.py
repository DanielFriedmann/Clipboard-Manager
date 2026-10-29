import json
import os
import shutil
from datetime import datetime

from history import ClipboardHistory
from models import ClipboardFormat, ClipboardGroup, ClipboardItem, EntryKind, guess_kind
from vault import DamagedData

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipboardManager")
DATA_FILE = os.path.join(APP_DIR, "data.json")
DATA_VERSION = 2

VAULT_FILE = os.path.join(APP_DIR, "vault.json")
VAULT_VERSION = 3     # 2 = ein Block für alles, 3 = jeder Eintrag einzeln

# Felder, die verschlüsselt im Block "details" stehen
DETAIL_FIELDS = ("title", "username", "url", "source_app")


def _write_json_atomic(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(content, file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def _kind_from_entry(entry, clipboard_format):
    # alte Einträge ohne "kind": Links nachträglich erkennen
    if "kind" not in entry:
        if clipboard_format == ClipboardFormat.TEXT:
            return guess_kind(entry["content"])
        return EntryKind.TEXT
    # unbekannter Wert, z. B. aus einer neueren Version
    try:
        return EntryKind(entry["kind"])
    except ValueError:
        return EntryKind.TEXT


# Umwandeln: Verlauf -> Dictionary (Klartext, nur noch für Version 2 und 1.1)

def history_to_dict(history):
    return {
        "version": DATA_VERSION,
        "default_group": history.default_group.id,
        "groups": [
            {"id": group.id, "name": group.name, "color": group.color,
             "position": group.position}
            for group in history.groups
        ],
        "items": [
            {
                "id": item.id,
                "content": item.content,
                "format": item.clipboard_format.name,
                "group": item.clipboard_group.id if item.clipboard_group else None,
                "created_at": item.created_at.isoformat(),
                "is_favorite": item.is_favorite,
                "position": item.position,
                "kind": item.kind.value,
                "title": item.title,
                "username": item.username,
                "url": item.url,
                "source_app": item.source_app,
                "needs_review": item.needs_review,
            }
            for item in history.history
        ],
    }


# Umwandeln: Dictionary -> Verlauf

def history_from_dict(data):
    history = ClipboardHistory()

    # Gruppen in gespeicherter Reihenfolge anlegen und über ihre ID merken
    groups_by_id = {}
    groups = []
    for index, entry in enumerate(data.get("groups", [])):
        group = ClipboardGroup(
            name=entry["name"],
            color=entry["color"],
            id=entry["id"],
            position=entry.get("position", float(index)),
        )
        groups_by_id[group.id] = group
        groups.append(group)

    # Standardgruppe übernehmen, sonst die frisch angelegte behalten
    default = groups_by_id.get(data.get("default_group"))
    if default is None:
        default = history.default_group
        # vor alle anderen Gruppen setzen
        default.position = min((group.position for group in groups), default=0.0) - 1.0
        groups.insert(0, default)
    history.default_group = default
    history.groups = groups

    # Einträge anhängen, nicht über add_item
    for index, entry in enumerate(data.get("items", [])):
        clipboard_format = ClipboardFormat[entry["format"]]
        item = ClipboardItem(
            clipboard_format=clipboard_format,
            content=entry["content"],
            clipboard_group=groups_by_id.get(entry.get("group"), default),
            created_at=datetime.fromisoformat(entry["created_at"]),
            is_favorite=entry.get("is_favorite", False),
            position=entry.get("position", float(index)),
            kind=_kind_from_entry(entry, clipboard_format),
            title=entry.get("title"),
            username=entry.get("username"),
            url=entry.get("url"),
            source_app=entry.get("source_app"),
            needs_review=entry.get("needs_review", False),
        )
        # alte Einträge ohne ID behalten die neu erzeugte
        if entry.get("id"):
            item.id = entry["id"]
        history.history.append(item)

    # die Position ist maßgeblich, nicht die Reihenfolge in der Datei
    history.history.sort(key=lambda item: item.position)
    history.groups.sort(key=lambda group: group.position)

    return history


# Einzelne Felder verschlüsseln (Version 3)

def _seal(vault, text, label):
    # Text verschlüsseln und über label an seinen Platz binden
    if text is None:
        return None
    return vault.encrypt(text.encode("utf-8"), label.encode("utf-8"))


def _unseal(vault, sealed, label):
    if sealed is None:
        return None
    try:
        return vault.decrypt(sealed, label.encode("utf-8")).decode("utf-8")
    except DamagedData:
        raise ValueError(f"Verschlüsselter Block {label} ist beschädigt oder wurde verändert.") from None


def _group_to_sealed(group, vault):
    return {
        "id": group.id,
        "color": group.color,
        "position": group.position,
        "name": _seal(vault, group.name, f"group:{group.id}:name"),
    }


def _item_to_sealed(item, vault):
    details = {name: getattr(item, name) for name in DETAIL_FIELDS}
    return {
        # offen: der Service darf damit filtern und sortieren
        "id": item.id,
        "group": item.clipboard_group.id if item.clipboard_group else None,
        "format": item.clipboard_format.name,
        "created_at": item.created_at.isoformat(),
        "is_favorite": item.is_favorite,
        "position": item.position,
        "kind": item.kind.value,
        "needs_review": item.needs_review,
        "content_hash": vault.content_hash(item.content),
        # verschlüsselt
        "details": _seal(vault, json.dumps(details, ensure_ascii=False), f"item:{item.id}:details"),
        "content": _seal(vault, item.content, f"item:{item.id}:content"),
    }


def _unseal_data(content, vault):
    # Version 3 in dasselbe Klartext-Dictionary umwandeln, das history_from_dict kennt
    groups = []
    for group in content.get("groups", []):
        plain = dict(group)
        plain["name"] = _unseal(vault, group["name"], f"group:{group['id']}:name")
        groups.append(plain)

    items = []
    for item in content.get("items", []):
        plain = {key: value for key, value in item.items()
                 if key not in ("details", "content", "content_hash")}
        plain["content"] = _unseal(vault, item["content"], f"item:{item['id']}:content")
        details = _unseal(vault, item["details"], f"item:{item['id']}:details")
        plain.update(json.loads(details) if details else {})
        items.append(plain)

    return {"default_group": content.get("default_group"), "groups": groups, "items": items}


def vault_to_dict(history, vault):
    return {
        "version": VAULT_VERSION,
        "vault": vault.header,
        "default_group": history.default_group.id,
        "groups": [_group_to_sealed(group, vault) for group in history.groups],
        "items": [_item_to_sealed(item, vault) for item in history.history],
    }


# Datei schreiben und lesen (Klartext, Version 1.1)

def save_history(history, path=DATA_FILE):
    _write_json_atomic(path, history_to_dict(history))


def load_history(path=DATA_FILE):

    # None bedeutet: keine brauchbare Datei vorhanden
    if not os.path.exists(path):
        return None

    try:
        with open(path, encoding="utf-8") as file:
            return history_from_dict(json.load(file))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError) as error:
        # beschädigte Datei beiseitelegen statt abzustürzen
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.replace(path, f"{path}.defekt-{stamp}")
        print(f"Datendatei beschädigt und umbenannt: {error}")
        return None


# Verschlüsselte Datei

def read_vault_file(path=VAULT_FILE):
    # None, wenn es noch keinen Tresor gibt
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _backup_once(path):
    # vor der ersten Umwandlung eine Kopie behalten (bleibt verschlüsselt)
    backup = path + ".v2-backup"
    if os.path.exists(path) and not os.path.exists(backup):
        shutil.copy2(path, backup)


def load_encrypted(content, vault, path=VAULT_FILE):
    if content.get("version", 2) < 3:
        # Version 2: ein Block für alles, beim nächsten Speichern wird Version 3 daraus
        _backup_once(path)
        try:
            plain = vault.decrypt(content["payload"])
        except DamagedData:
            raise ValueError("Die Datendatei ist beschädigt oder wurde verändert.") from None
        return history_from_dict(json.loads(plain.decode("utf-8")))
    return history_from_dict(_unseal_data(content, vault))


def save_encrypted(history, vault, path=VAULT_FILE):
    _write_json_atomic(path, vault_to_dict(history, vault))


# Übernahme der unverschlüsselten Datei aus Version 1.1

def load_legacy():
    return load_history(DATA_FILE)   # None, wenn es keine alte Datei gibt


def remove_legacy():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)