import queue

PREVIEW_LENGTH = 60


class ClipboardViewModel:
    def __init__(self, history):
        self.history = history
        self.service = None   
        self.checked = set()          # markierte Einträge

        # Zustand der Ansicht
        self.sort_by = "priority"
        self.descending = False
        self.search = ""
        self.favorites_only = False

        self._incoming = queue.Queue()   # Übergabe Service-Thread → GUI-Thread
        self._listeners = []

    # Benachrichtigung / Abonnement

    def subscribe(self, callback):
        self._listeners.append(callback)

    def _notify(self):
        for callback in self._listeners:
            callback()

    # Service-Thread → GUI-Thread

    def receive_text(self, text):
        # läuft im SERVICE-Thread: nur in die Queue legen
        self._incoming.put(text)

    def process_incoming(self):
        # läuft im GUI-Thread, wird regelmäßig von der Oberfläche aufgerufen
        changed = False
        while not self._incoming.empty():
            self.history.add_item(self._incoming.get())
            changed = True
        if changed:
            self._notify()

    # Daten für die Ansichten

    def get_visible_items(self):
        return self.history.get_history(
            sort_by=self.sort_by,
            descending=self.descending,
            search=self.search,
            favorites_only=self.favorites_only,
        )

    def is_checked(self, item):
        return item in self.checked

    def checked_visible(self):
        # nur Markierungen, die gerade auch angezeigt werden
        return [item for item in self.get_visible_items() if item in self.checked]

    @property
    def checked_count(self):
        return len(self.checked_visible())

    @property
    def all_visible_checked(self):
        visible = self.get_visible_items()
        return bool(visible) and all(item in self.checked for item in visible)

    def position(self, item):
        # Platz in der eigenen Reihenfolge, ab 1 gezählt
        return self.history.history.index(item) + 1

    @staticmethod
    def datetime_text(item):
        return item.created_at.strftime("%d.%m.%Y %H:%M")

    def _prune_checked(self):
        # Markierungen gelöschter Einträge entfernen
        self.checked &= set(self.history.history)

    @property
    def is_filtering(self):
        return bool(self.search) or self.favorites_only

    @property
    def can_drag(self):
        return self.sort_by == "priority" and not self.descending

    @property
    def count_text(self):
        count = len(self.get_visible_items())
        return "1 Eintrag" if count == 1 else f"{count} Einträge"

    @property
    def empty_text(self):
        return "Keine Treffer" if self.is_filtering else "Noch nichts kopiert"

    @property
    def clear_button_text(self):
        return "Angezeigte löschen" if self.is_filtering else "Alle löschen"

    def deletable_count(self):
        return len([item for item in self.get_visible_items() if not item.is_favorite])

    @staticmethod
    def preview(item, max_length=PREVIEW_LENGTH):
        text = " ".join(item.content.split())
        if len(text) > max_length:
            text = text[:max_length - 1] + "…"
        return text

    @staticmethod
    def time_text(item):
        return item.created_at.strftime("%H:%M")

    # Ansicht

    def set_search(self, text):
        self.search = text
        self._notify()

    def set_sort(self, sort_by):
        self.sort_by = sort_by
        self._notify()

    def toggle_direction(self):
        self.descending = not self.descending
        self._notify()

    def set_favorites_only(self, value):
        self.favorites_only = value
        self._notify()

    def sort_by_column(self, sort_by):

        if self.sort_by == sort_by:
            self.descending = not self.descending
        else:
            self.sort_by = sort_by
            self.descending = False
        self._notify()

    # Befehle

    def copy(self, item):
        # kein _notify: die Änderung kommt über den Service ohnehin zurück
        self.service.set_text(item.content)

    def delete(self, item):
        self.history.remove_item(item)
        self._prune_checked()
        self._notify()

    def toggle_favorite(self, item):
        self.history.toggle_favorite(item)
        self._notify()

    def move(self, item, target, after=False):
        if not self.can_drag:
            return
        self.history.move_item(item, target, after=after)
        self._notify()

    def delete_visible(self):
        self.history.clear_items(self.get_visible_items())
        self._prune_checked()
        self._notify()

    def toggle_checked(self, item):
        if item in self.checked:
            self.checked.remove(item)
        else:
            self.checked.add(item)
        self._notify()

    def set_all_checked(self, value):
        visible = set(self.get_visible_items())
        if value:
            self.checked |= visible   # alle sichtbaren hinzufügen
        else:
            self.checked -= visible   # alle sichtbaren entfernen
        self._notify()

    def delete_checked(self):
        for item in self.checked_visible():
            self.history.remove_item(item)
        self._prune_checked()
        self._notify()