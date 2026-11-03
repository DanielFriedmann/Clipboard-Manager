import json
from datetime import datetime

from history import _clean, _content_key, _matches, _place, _position_between
from models import ClipboardFormat, ClipboardGroup, ClipboardItem, EntryKind, guess_kind
from repository import EntryRepository
from storage import (DETAIL_FIELDS, _group_to_sealed, _item_to_sealed, _seal,
                     _unseal, vault_to_dict)

# diese Sortierungen kann der Service selbst, die anderen braucht Klartext
SERVER_SORTS = ("priority", "time", "favorite")
MAX_PAGE = 1000   # mehr liefert der Service pro Anfrage nicht, darüber wird alles geladen


def _kind(value):
    try:
        return EntryKind(value)
    except ValueError:
        return EntryKind.TEXT


def import_history(api, vault, history):
    # ganzen Verlauf einzeln verschlüsselt an den Dienst übergeben (neu oder alte Datei)
    data = vault_to_dict(history, vault)
    api.post("/v1/import", json={
        "header": data["vault"],
        "default_group": data["default_group"],
        "groups": data["groups"],
        "items": data["items"],
    })


class ApiRepository(EntryRepository):
    # Dieselbe Schnittstelle wie ClipboardHistory, aber die Daten liegen beim Entry-Service.
    # Ver- und entschlüsselt wird nur hier in der App.

    def __init__(self, api, vault):
        self.api = api
        self.vault = vault
        self._items = {}          # ID → ClipboardItem, damit jeder Eintrag nur ein Objekt hat
        self._groups = {}         # ID → ClipboardGroup
        self._group_list = []     # Gruppen in ihrer Reihenfolge
        self._default_group = None
        self._order = []          # zuletzt geladene Liste in eigener Reihenfolge (für move_item)
        self._counts = None       # zwischengespeicherte Anzahl pro Gruppe
        self._load_groups()

    # Umwandeln: Service ↔ Objekte

    def _load_groups(self):
        info = self.api.get("/v1/vault")
        for raw in self.api.get("/v1/groups"):
            group = self._groups.get(raw["id"])
            if group is None:
                group = ClipboardGroup(name="", id=raw["id"])
                self._groups[group.id] = group
            group.name = _unseal(self.vault, raw["name"], f"group:{raw['id']}:name")
            group.color = raw["color"]
            group.position = raw["position"]
        self._group_list = sorted(self._groups.values(), key=lambda group: group.position)
        self._default_group = self._groups.get(info["default_group"]) or self._group_list[0]

    def _to_item(self, raw):
        item_id = raw["id"]
        details = {}
        if raw.get("details"):
            details = json.loads(_unseal(self.vault, raw["details"], f"item:{item_id}:details"))
        content = None
        if raw.get("content"):
            content = _unseal(self.vault, raw["content"], f"item:{item_id}:content")

        item = self._items.get(item_id)
        if item is None:
            item = ClipboardItem(clipboard_format=ClipboardFormat[raw.get("format", "TEXT")],
                                 content=content)
            item.id = item_id
            self._items[item_id] = item

        item.content = content    # bei Passwörtern None: Inhalt nur auf Anfrage
        item.clipboard_group = self._groups.get(raw.get("group"), self._default_group)
        item.created_at = datetime.fromisoformat(raw["created_at"])
        item.is_favorite = raw.get("is_favorite", False)
        item.position = raw.get("position", 0.0)
        item.kind = _kind(raw.get("kind", "text"))
        item.needs_review = raw.get("needs_review", False)
        for name in DETAIL_FIELDS:
            setattr(item, name, details.get(name))
        return item

    def _fields(self, item, *names):
        # Änderung für PATCH: nur die genannten Felder, verschlüsselte neu versiegelt
        update = {"id": item.id}
        for name in names:
            if name == "details":
                details = {field: getattr(item, field) for field in DETAIL_FIELDS}
                update["details"] = _seal(self.vault, json.dumps(details, ensure_ascii=False),
                                          f"item:{item.id}:details")
            elif name == "group":
                update["group"] = item.clipboard_group.id if item.clipboard_group else None
            elif name == "created_at":
                update["created_at"] = item.created_at.isoformat()
            elif name == "kind":
                update["kind"] = item.kind.value
            else:
                update[name] = getattr(item, name)
        return update

    def _send(self, updates):
        if updates:
            self.api.patch("/v1/entries", json={"updates": updates})
        self._counts = None

    def _top_position(self):
        # Position für einen neuen Eintrag ganz oben
        first = self.api.get("/v1/entries", params={"limit": 1})["items"]
        return first[0]["position"] - 1.0 if first else 0.0

    # Einträge lesen

    def _params(self, group, sort_by, descending, favorites_only):
        server_sort = sort_by in SERVER_SORTS
        params = {"sort": sort_by if server_sort else "priority",
                  "descending": descending if server_sort else False}
        if group is not None:
            params["group_id"] = group.id
        if favorites_only:
            params["favorites_only"] = True
        return params

    def _remember_order(self, items, sort_by, descending):
        if sort_by == "priority" and not descending:
            self._order = items

    def get_history(self, group=None, sort_by="priority", descending=False,
                    search="", favorites_only=False):
        page = self.api.get("/v1/entries", params=self._params(group, sort_by, descending,
                                                                favorites_only))
        items = [self._to_item(raw) for raw in page["items"]]

        # Suche und diese Sortierungen brauchen Klartext, also hier in der App
        if search:
            term = search.lower()
            items = [item for item in items if _matches(item, term)]
        if sort_by == "content":
            items = sorted(items, key=_content_key, reverse=descending)
        elif sort_by == "group":
            items = sorted(items, key=lambda item: item.clipboard_group.name.lower()
                           if item.clipboard_group else "", reverse=descending)

        self._remember_order(items, sort_by, descending)
        return items

    def get_page(self, group=None, sort_by="priority", descending=False,
                 search="", favorites_only=False, limit=None):
        needs_all = search or sort_by not in SERVER_SORTS or limit is None or limit > MAX_PAGE
        if needs_all:
            # alles laden und hier filtern, nur die ersten "limit" anzeigen
            items = self.get_history(group, sort_by, descending, search, favorites_only)
            return (items if limit is None else items[:limit]), len(items)

        params = self._params(group, sort_by, descending, favorites_only)
        params["limit"] = limit
        page = self.api.get("/v1/entries", params=params)
        items = [self._to_item(raw) for raw in page["items"]]
        self._remember_order(items, sort_by, descending)
        return items, page["total"]

    def count(self, group=None):
        if self._counts is None:
            self._counts = self.api.get("/v1/counts")
        if group is None:
            return self._counts["total"]
        return self._counts["groups"].get(group.id, 0)

    def get_content(self, item):
        if item.content is not None:
            return item.content
        sealed = self.api.get(f"/v1/entries/{item.id}/content")
        if sealed is None:
            return ""
        # bewusst nicht in item.content merken: Passwörter nur so kurz wie nötig im Speicher
        return _unseal(self.vault, sealed, f"item:{item.id}:content")

    # Einträge ändern

    def add_item(self, text, kind=None, source_app=None, needs_review=False):
        kind = kind or EntryKind.TEXT
        content_hash = self.vault.content_hash(text)
        found = self.api.get("/v1/entries", params={"content_hash": content_hash, "limit": 1})["items"]

        if found:
            item = self._to_item(found[0])
            item.created_at = datetime.now()
            # zum Passwort hochstufen, aber nie zurückstufen
            if kind == EntryKind.PASSWORD and not item.is_password:
                item.kind = EntryKind.PASSWORD
                item.needs_review = needs_review
            if item.source_app is None:
                item.source_app = source_app
            self._send([self._fields(item, "created_at", "kind", "needs_review", "details")])
            if item.is_password:
                item.content = None
            return item

        item = ClipboardItem(
            clipboard_format=ClipboardFormat.TEXT,
            content=text,
            clipboard_group=self._default_group,
            kind=kind,
            source_app=source_app,
            needs_review=needs_review,
        )
        item.position = self._top_position()
        self.api.post("/v1/entries", json=_item_to_sealed(item, self.vault))
        self._items[item.id] = item
        self._counts = None
        if item.is_password:
            item.content = None   # Klartext nicht länger als nötig behalten
        return item

    def remove_items(self, items):
        ids = [item.id for item in items]
        if not ids:
            return
        self.api.post("/v1/entries/delete", json={"ids": ids})
        for item_id in ids:
            self._items.pop(item_id, None)
        self._counts = None

    def clear_items(self, items):
        removed = [item for item in items if not item.is_favorite]
        self.remove_items(removed)
        return removed

    def move_item(self, item, target, after=False):
        if item is target:
            return
        order = [entry for entry in self._order if entry is not item]
        if target is None:
            index = len(order)
        else:
            index = order.index(target) + (1 if after else 0)

        before = order[index - 1] if index > 0 else None
        following = order[index] if index < len(order) else None
        position = _position_between(before, following)
        if (before is not None and position <= before.position) or \
           (following is not None and position >= following.position):
            # Lücke aufgebraucht: alle neu durchnummerieren und nochmal rechnen
            self._renumber_all()
            position = _position_between(before, following)

        item.position = position
        self._send([self._fields(item, "position")])

    def _renumber_all(self):
        raws = self.api.get("/v1/entries")["items"]
        updates = []
        for index, raw in enumerate(raws):
            raw["position"] = float(index)
            if raw["id"] in self._items:
                self._items[raw["id"]].position = float(index)
            updates.append({"id": raw["id"], "position": float(index)})
        self._send(updates)

    def toggle_favorite(self, item):
        item.is_favorite = not item.is_favorite
        self._send([self._fields(item, "is_favorite")])

    def rename_item(self, item, title, username=None, url=None):
        item.title = _clean(title)
        if item.is_password:
            item.username = _clean(username)
            item.url = _clean(url)
        item.needs_review = False
        self._send([self._fields(item, "details", "needs_review")])

    def mark_password(self, item, is_password):
        if is_password:
            if item.is_password:
                return
            item.kind = EntryKind.PASSWORD
            item.needs_review = item.title is None
            item.content = None
        else:
            item.content = self.get_content(item)
            item.kind = guess_kind(item.content)
            item.needs_review = False
        self._send([self._fields(item, "kind", "needs_review")])

    def assign_items_to_group(self, items, group):
        if group.id not in self._groups:
            raise ValueError("Die angegebene Gruppe existiert nicht.")
        top = self._top_position()
        updates = []
        # rückwärts, damit die Reihenfolge der Einträge erhalten bleibt
        for item in reversed(items):
            item.clipboard_group = group
            item.position = top
            top -= 1.0
            updates.append(self._fields(item, "group", "position"))
        self._send(updates)

    # Gruppen

    def get_default_group(self):
        return self._default_group

    def list_groups(self):
        return list(self._group_list)

    def add_group(self, name, color="#9e9e9e"):
        if any(group.name.lower() == name.lower() for group in self._group_list):
            raise ValueError(f"Gruppe mit dem Namen '{name}' existiert bereits.")
        group = ClipboardGroup(name=name, color=color)
        _place(self._group_list, group, len(self._group_list))   # ans Ende
        self.api.post("/v1/groups", json=_group_to_sealed(group, self.vault))
        self._groups[group.id] = group
        return group

    def remove_group(self, group):
        if group is self._default_group:
            raise ValueError("Die Standardgruppe kann nicht gelöscht werden.")
        self.api.delete(f"/v1/groups/{group.id}")
        self._groups.pop(group.id, None)
        self._group_list.remove(group)
        for item in self._items.values():
            if item.clipboard_group is group:
                item.clipboard_group = self._default_group
        self._counts = None

    def move_group(self, group, target, after=False):
        if group is target or group is self._default_group or target is self._default_group:
            return
        before = {g.id: g.position for g in self._group_list}
        self._group_list.remove(group)
        if target is None:
            index = len(self._group_list)
        else:
            index = self._group_list.index(target) + (1 if after else 0)
        _place(self._group_list, group, index)
        # nur Gruppen senden, deren Position sich wirklich geändert hat
        for g in self._group_list:
            if before.get(g.id) != g.position:
                self.api.patch(f"/v1/groups/{g.id}", json={"position": g.position})