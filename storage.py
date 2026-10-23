import json
import os
from datetime import datetime

from history import ClipboardHistory
from models import ClipboardFormat, ClipboardGroup, ClipboardItem

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipboardManager")
DATA_FILE = os.path.join(APP_DIR, "data.json")
DATA_VERSION = 1


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
                "content": item.content,
                "format": item.clipboard_format.name,
                "group": item.clipboard_group.id if item.clipboard_group else None,
                "created_at": item.created_at.isoformat(),
                "is_favorite": item.is_favorite,
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
        history.history.append(ClipboardItem(
            clipboard_format=ClipboardFormat[entry["format"]],
            content=entry["content"],
            clipboard_group=groups_by_id.get(entry.get("group"), default),
            created_at=datetime.fromisoformat(entry["created_at"]),
            is_favorite=entry.get("is_favorite", False),
        ))

    return history


# Datei schreiben und lesen

def save_history(history, path=DATA_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"

    # erst vollständig in eine Hilfsdatei schreiben, dann austauschen
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(history_to_dict(history), file, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


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