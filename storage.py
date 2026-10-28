import json
import os
from datetime import datetime

from history import ClipboardHistory
from models import ClipboardFormat, ClipboardGroup, ClipboardItem, EntryKind, guess_kind

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipboardManager")
DATA_FILE = os.path.join(APP_DIR, "data.json")
DATA_VERSION = 2

VAULT_FILE = os.path.join(APP_DIR, "vault.json")
VAULT_VERSION = 2

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


# Umwandeln: Verlauf -> Dictionary

def history_to_dict(history):
    return {
        "version": DATA_VERSION,
        "default_group": history.default_group.id,
        "groups": [
            {"id": group.id, "name": group.name, "color": group.color}
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
    for entry in data.get("groups", []):
        group = ClipboardGroup(name=entry["name"], color=entry["color"], id=entry["id"])
        groups_by_id[group.id] = group
        groups.append(group)

    # Standardgruppe übernehmen, sonst die frisch angelegte behalten
    default = groups_by_id.get(data.get("default_group"))
    if default is None:
        default = history.default_group
        groups.insert(0, default)
    history.default_group = default
    history.groups = groups

    # Einträge in gespeicherter Reihenfolge anhängen, nicht über add_item
    for entry in data.get("items", []):
        clipboard_format = ClipboardFormat[entry["format"]]
        item = ClipboardItem(
            clipboard_format=clipboard_format,
            content=entry["content"],
            clipboard_group=groups_by_id.get(entry.get("group"), default),
            created_at=datetime.fromisoformat(entry["created_at"]),
            is_favorite=entry.get("is_favorite", False),
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

    return history


# Datei schreiben und lesen

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


def load_encrypted(content, vault):
    plain = vault.decrypt(content["payload"])
    return history_from_dict(json.loads(plain.decode("utf-8")))


def save_encrypted(history, vault, path=VAULT_FILE):
    plain = json.dumps(history_to_dict(history), ensure_ascii=False).encode("utf-8")
    _write_json_atomic(path, {
        "version": VAULT_VERSION,
        "vault": vault.header,
        "payload": vault.encrypt(plain),
    })


# Übernahme der unverschlüsselten Datei aus Version 1.1

def load_legacy():
    return load_history(DATA_FILE)   # None, wenn es keine alte Datei gibt


def remove_legacy():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)