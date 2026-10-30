from models import ClipboardGroup, ClipboardItem, ClipboardFormat, EntryKind, guess_kind
from repository import EntryRepository
from datetime import datetime


def _matches(item, term):
    # Passwörter nie über ihren Inhalt finden
    fields = [item.title, item.username, item.url, item.source_app]
    if not item.is_password:
        fields.append(item.content)
    return any(term in field.lower() for field in fields if field)


def _clean(text):
    # leere Eingabe heißt: kein Wert
    text = (text or "").strip()
    return text or None


def _content_key(item):
    # sortiert nach dem, was man sieht
    if item.title:
        return item.title.lower()
    if item.is_password:
        return ""
    return item.content.lower()


def _position_between(before, after):
    # Position zwischen zwei Nachbarn; None heißt: kein Nachbar auf dieser Seite
    if before is None and after is None:
        return 0.0
    if before is None:
        return after.position - 1.0
    if after is None:
        return before.position + 1.0
    return (before.position + after.position) / 2


def _renumber(objects):
    # Lücken neu verteilen, wenn Kommazahlen zu eng beieinander liegen
    for index, obj in enumerate(objects):
        obj.position = float(index)


def _place(objects, obj, index):
    # obj an Stelle index in die sortierte Liste setzen und seine Position berechnen
    before = objects[index - 1] if index > 0 else None
    after = objects[index] if index < len(objects) else None
    position = _position_between(before, after)
    objects.insert(index, obj)
    # Zahl liegt nicht mehr echt dazwischen: alles neu durchnummerieren
    if (before is not None and position <= before.position) or \
       (after is not None and position >= after.position):
        _renumber(objects)
    else:
        obj.position = position


class ClipboardHistory(EntryRepository):
    def __init__(self):
        self.history = []
        self.default_group = ClipboardGroup(name="Unsortiert")
        self.groups = [self.default_group]

    # Einträge ändern

    def add_item(self, text, kind=None, source_app=None, needs_review=False):
        kind = kind or EntryKind.TEXT
        existing = next((item for item in self.history if item.content == text), None)

        if existing is not None:
            existing.created_at = datetime.now()
            # zum Passwort hochstufen, aber nie zurückstufen
            if kind == EntryKind.PASSWORD and not existing.is_password:
                existing.kind = EntryKind.PASSWORD
                existing.needs_review = needs_review
            if existing.source_app is None:
                existing.source_app = source_app
            return existing

        clipboard_item = ClipboardItem(
            clipboard_format=ClipboardFormat.TEXT,
            content=text,
            clipboard_group=self.default_group,
            kind=kind,
            source_app=source_app,
            needs_review=needs_review,
        )
        _place(self.history, clipboard_item, 0)   # ganz nach oben
        return clipboard_item

    def remove_item(self, item):
        if item in self.history:
            self.history.remove(item)

    def remove_items(self, items):
        for item in items:
            self.remove_item(item)

    def move_item(self, item, target, after=False):
        if item is target:
            return

        self.history.remove(item)

        if target is None:
            index = len(self.history)               # ans Ende
        else:
            index = self.history.index(target)      # erst NACH dem Entfernen bestimmen
            if after:
                index += 1
        _place(self.history, item, index)

    def toggle_favorite(self, item):
        item.is_favorite = not item.is_favorite

    def rename_item(self, item, title, username=None, url=None):
        item.title = _clean(title)
        if item.is_password:
            item.username = _clean(username)
            item.url = _clean(url)
        item.needs_review = False

    def mark_password(self, item, is_password):
        if is_password:
            if not item.is_password:
                item.kind = EntryKind.PASSWORD
                item.needs_review = item.title is None
        else:
            item.kind = guess_kind(item.content)
            item.needs_review = False

    def clear_items(self, items):
        removed = [item for item in items if not item.is_favorite]
        self.remove_items(removed)
        return removed

    def clear_history(self, group=None):
        if group is None:
            self.history = [
                item for item in self.history
                if item.is_favorite or item.clipboard_group is not self.default_group
            ]
        else:
            self.history = [
                item for item in self.history
                if item.clipboard_group is not group or item.is_favorite
            ]

    # Einträge lesen

    def get_history(self, group=None, sort_by="priority", descending=False,
                    search="", favorites_only=False):
        items = list(self.history)

        # 1. Filter, jeder baut auf dem vorherigen auf
        if group is not None:
            items = [item for item in items if item.clipboard_group is group]
        if favorites_only:
            items = [item for item in items if item.is_favorite]
        if search:
            term = search.lower()
            items = [item for item in items if _matches(item, term)]

        # 2. Sortierung und Richtung
        if sort_by == "time":
            items = sorted(items, key=lambda item: item.created_at, reverse=descending)
        elif sort_by == "content":
            items = sorted(items, key=_content_key, reverse=descending)
        elif sort_by == "favorite":
            items = sorted(items, key=lambda item: item.is_favorite, reverse=not descending)
        elif sort_by == "group":
            items = sorted(
                items,
                key=lambda item: item.clipboard_group.name.lower() if item.clipboard_group else "",
                reverse=descending,
            )
        elif descending:
            items.reverse()   # eigene Reihenfolge, umgedreht

        return items

    def count(self, group=None):
        if group is None:
            return len(self.history)
        return sum(1 for item in self.history if item.clipboard_group is group)

    def get_content(self, item):
        return item.content

    # Gruppenverwaltung

    def get_default_group(self):
        return self.default_group

    def list_groups(self):
        return list(self.groups)   # Kopie, damit niemand die Liste von außen verändert

    def add_group(self, name, color="#9e9e9e"):
        if any(group.name.lower() == name.lower() for group in self.groups):
            raise ValueError(f"Gruppe mit dem Namen '{name}' existiert bereits.")
        new_group = ClipboardGroup(name=name, color=color)
        _place(self.groups, new_group, len(self.groups))   # ans Ende
        return new_group

    def remove_group(self, group):
        if group == self.default_group:
            raise ValueError("Die Standardgruppe kann nicht gelöscht werden.")
        if group in self.groups:
            self.groups.remove(group)
            for item in self.history:
                if item.clipboard_group == group:
                    item.clipboard_group = self.default_group

    def assign_item_to_group(self, item, group):
        if group not in self.groups:
            raise ValueError("Die angegebene Gruppe existiert nicht.")
        item.clipboard_group = group

        self.history.remove(item)
        _place(self.history, item, 0)

    def assign_items_to_group(self, items, group):
        # rückwärts, damit die Reihenfolge der Einträge erhalten bleibt
        for item in reversed(items):
            self.assign_item_to_group(item, group)

    def move_group(self, group, target, after=False):
        if group is target or group is self.default_group or target is self.default_group:
            return

        self.groups.remove(group)

        if target is None:
            index = len(self.groups)
        else:
            index = self.groups.index(target)
            if after:
                index += 1
        _place(self.groups, group, index)

    # Ausgabe zum Testen

    def print_history(self):
        print("Clipboard History:")
        for item in self.history:
            print(f"Format: {item.clipboard_format}, Content: {item.content}, "
                  f"Created At: {item.created_at}, Favorite: {item.is_favorite}")