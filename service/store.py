import json
import os
import threading

from service.config import FILE_VERSION

# Felder, die bei Passwörtern in Listen weggelassen werden
PASSWORD_KIND = "password"


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def _empty():
    return {"version": FILE_VERSION, "vault": None, "default_group": None,
            "groups": [], "items": []}


class EntryStore:
    # Verwaltet die Datei des Services. Kennt keinen Schlüssel, nur offene Felder und Geheimtext.

    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()   # Anfragen laufen parallel in mehreren Threads
        self._data = self._load()

    # Datei

    def _load(self):
        if not os.path.exists(self.path):
            return _empty()
        with open(self.path, encoding="utf-8") as file:
            data = json.load(file)
        # eine alte Datei (Version 2) hat nur einen großen Block, noch keine Listen
        data.setdefault("groups", [])
        data.setdefault("items", [])
        return data

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        temp_path = self.path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self._data, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.path)

    # Tresor

    def get_vault(self):
        with self._lock:
            data = self._data
            info = {"header": data.get("vault"), "default_group": data.get("default_group"),
                    "version": data.get("version", 2)}
            if info["version"] < FILE_VERSION:
                info["legacy_payload"] = data.get("payload")
            return info

    def put_vault(self, header, default_group=None):
        with self._lock:
            self._data["vault"] = header
            if default_group is not None:
                self._data["default_group"] = default_group
            self._save()

    def import_all(self, content):
        # ersetzt alles, z. B. bei der Umwandlung von Version 2
        with self._lock:
            self._data = {
                "version": FILE_VERSION,
                "vault": content["header"],
                "default_group": content.get("default_group"),
                "groups": content.get("groups", []),
                "items": content.get("items", []),
            }
            self._save()

    # Gruppen

    def _find(self, collection, object_id):
        for obj in self._data[collection]:
            if obj["id"] == object_id:
                return obj
        raise NotFound(object_id)

    def list_groups(self):
        with self._lock:
            return sorted(self._data["groups"], key=lambda group: group["position"])

    def add_group(self, group):
        with self._lock:
            if any(g["id"] == group["id"] for g in self._data["groups"]):
                raise Conflict(group["id"])
            self._data["groups"].append(group)
            self._save()
            return group

    def patch_group(self, group_id, changes):
        with self._lock:
            group = self._find("groups", group_id)
            group.update(changes)
            self._save()
            return group

    def delete_group(self, group_id):
        with self._lock:
            default = self._data.get("default_group")
            if group_id == default:
                raise Conflict("Die Standardgruppe kann nicht gelöscht werden.")
            group = self._find("groups", group_id)
            self._data["groups"].remove(group)
            # Einträge wandern in die Standardgruppe
            for item in self._data["items"]:
                if item.get("group") == group_id:
                    item["group"] = default
            self._save()

    # Einträge lesen

    def list_entries(self, group_id=None, favorites_only=False, content_hash=None,
                     sort="priority", descending=False, offset=0, limit=None,
                     include_password_content=False):
        with self._lock:
            items = list(self._data["items"])

        if group_id is not None:
            items = [item for item in items if item.get("group") == group_id]
        if favorites_only:
            items = [item for item in items if item.get("is_favorite")]
        if content_hash is not None:
            items = [item for item in items if item.get("content_hash") == content_hash]

        if sort == "time":
            items.sort(key=lambda item: item["created_at"], reverse=descending)
        elif sort == "favorite":
            items.sort(key=lambda item: item["position"])
            items.sort(key=lambda item: item.get("is_favorite", False), reverse=not descending)
        else:
            items.sort(key=lambda item: item["position"], reverse=descending)

        total = len(items)
        page = items[offset:] if limit is None else items[offset:offset + limit]

        if not include_password_content:
            # Passwörter nur auf ausdrückliche Anfrage mit Inhalt
            page = [dict(item, content=None) if item.get("kind") == PASSWORD_KIND else item
                    for item in page]
        return total, page

    def get_content(self, entry_id):
        with self._lock:
            return self._find("items", entry_id).get("content")

    def counts(self):
        with self._lock:
            groups = {}
            for item in self._data["items"]:
                groups[item.get("group")] = groups.get(item.get("group"), 0) + 1
            return len(self._data["items"]), groups

    # Einträge ändern

    def add_entry(self, entry):
        with self._lock:
            if any(item["id"] == entry["id"] for item in self._data["items"]):
                raise Conflict(entry["id"])
            self._data["items"].append(entry)
            self._save()
            return entry

    def patch_entries(self, updates):
        # alle oder keine: erst prüfen, dann ändern
        with self._lock:
            targets = [(self._find("items", update["id"]), update) for update in updates]
            for item, update in targets:
                item.update({key: value for key, value in update.items() if key != "id"})
            self._save()
            return [item for item, _update in targets]

    def delete_entries(self, ids):
        with self._lock:
            wanted = set(ids)
            before = len(self._data["items"])
            self._data["items"] = [item for item in self._data["items"] if item["id"] not in wanted]
            deleted = before - len(self._data["items"])
            if deleted:
                self._save()
            return deleted