import queue
from datetime import date, timedelta

from models import EntryKind, guess_kind

PREVIEW_LENGTH = 80
# Spalten der Tabelle in ihrer Reihenfolge; Überschriften und Breiten stehen in gui.py
TABLE_COLUMNS = ("check", "position", "content", "group", "time", "favorite")

MASK = "••••••••"

# Symbole aus der Windows-Schrift "Segoe MDL2 Assets"
KIND_ICONS = {
    EntryKind.PASSWORD: "\uE72E",   # Schloss
    EntryKind.LINK: "\uE71B",       # Kettenglied
}

TOOLTIP_MAX_LINES = 15
TOOLTIP_MAX_CHARS = 1000

PAGE_SIZE = 50   # so viele Einträge werden auf einmal geladen


class ClipboardViewModel:
    def __init__(self, history):
        self.history = history
        self.service = None
        self.checked = set()            # markierte Einträge
        self.selected_group = None

        # Zustand der Ansicht
        self.sort_by = "priority"
        self.descending = False
        self.search = ""
        self.favorites_only = False

        self._incoming = queue.Queue()   # Übergabe Service-Thread → GUI-Thread
        self._listeners = []
        self._visible = None             # zwischengespeicherte sichtbare Liste
        self._positions = None           # Eintrag → Platz in dieser Liste

        self._total = 0                  # Treffer insgesamt, auch nicht geladene
        self._limit = PAGE_SIZE          # so viele werden gerade angezeigt
        self.scroll_to_top = False       # neue Ansicht: Views springen nach oben

        self.locked = False              # gesperrt: keine Daten, Views zeigen nichts
        self._locked_group_id = None     # Gruppe, die nach dem Entsperren wieder gewählt wird

    # Benachrichtigung / Abonnement

    def subscribe(self, callback):
        self._listeners.append(callback)

    def _notify(self):
        # Zustand hat sich geändert: sichtbare Liste beim nächsten Abruf neu bestimmen
        self._visible = None
        self._positions = None
        for callback in self._listeners:
            callback()
        self.scroll_to_top = False

    # Service-Thread → GUI-Thread

    def receive_capture(self, capture):
        # läuft im SERVICE-Thread: nur in die Queue legen
        self._incoming.put(capture)

    def process_incoming(self):
        # läuft im GUI-Thread, wird regelmäßig von der Oberfläche aufgerufen

        if self.locked:
            self._discard_incoming()   # gesperrt: nichts sammeln
            return
        
        changed = False
        while not self._incoming.empty():
            capture = self._incoming.get()
            kind = EntryKind.PASSWORD if capture.is_sensitive else guess_kind(capture.text)
            self.history.add_item(
                capture.text,
                kind=kind,
                source_app=capture.source_app,
                needs_review=kind == EntryKind.PASSWORD,
            )
            changed = True
        if changed:
            self._notify()

    def _discard_incoming(self):
        while not self._incoming.empty():
            self._incoming.get()

    # Sperren

    def lock(self):
        # alles vergessen, was Klartext enthält; die Views räumen bei _notify auf
        self._locked_group_id = self.selected_group_id
        self.locked = True
        self.history = None
        self.checked.clear()
        self.selected_group = None
        self.search = ""
        self._discard_incoming()
        self._notify()

    def unlock(self, repository):
        self.history = repository
        self.locked = False
        self._reset_paging()
        self.select_group_by_id(self._locked_group_id)   # zeichnet alles neu

    # Daten für die Ansichten

    @staticmethod
    def sidebar_name(name, max_length=16):
        return ClipboardViewModel._shorten(name, max_length)

    def _page(self, limit):
        return self.history.get_page(
            group=self.selected_group,
            sort_by=self.sort_by,
            descending=self.descending,
            search=self.search,
            favorites_only=self.favorites_only,
            limit=limit,
        )

    def get_visible_items(self):
        if self._visible is None:
            self._visible, self._total = self._page(self._limit)
        return self._visible

    def _all_matching(self):
        # alle Treffer der Ansicht, auch die noch nicht geladenen
        items, _total = self._page(None)
        return items

    @property
    def total_count(self):
        self.get_visible_items()
        return self._total

    @property
    def has_more(self):
        return self.total_count > len(self.get_visible_items())

    @property
    def more_count(self):
        return min(PAGE_SIZE, self.total_count - len(self.get_visible_items()))

    @property
    def more_text(self):
        shown = len(self.get_visible_items())
        return f"Weitere {self.more_count} laden  ·  {shown} von {self.total_count}"

    def load_more(self):
        self._limit += PAGE_SIZE
        self._notify()

    def _reset_paging(self):
        # neue Ansicht: wieder mit der ersten Seite anfangen
        self._limit = PAGE_SIZE
        self.scroll_to_top = True

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
        # Platz in der angezeigten Liste, ab 1 gezählt
        if self._positions is None:
            self._positions = {entry: index + 1
                               for index, entry in enumerate(self.get_visible_items())}
        return self._positions.get(item, 0)

    @staticmethod
    def datetime_text(item):
        return item.created_at.strftime("%d.%m.%Y %H:%M")

    @property
    def is_filtering(self):
        return bool(self.search) or self.favorites_only or self.selected_group is not None

    @property
    def can_drag(self):
        return self.sort_by == "priority" and not self.descending

    @property
    def count_text(self):
        return self.entries_text(self.total_count)

    @property
    def empty_text(self):
        if self.search or self.favorites_only:
            return "Keine Treffer"
        if self.selected_group is not None:
            return "Keine Einträge in dieser Gruppe"
        return "Noch nichts kopiert"

    @property
    def clear_button_text(self):
        return "Angezeigte löschen" if self.is_filtering else "Alle löschen"

    def deletable_count(self):
        return len([item for item in self._all_matching() if not item.is_favorite])

    @staticmethod
    def _shorten(text, max_length):
        text = " ".join(text.split())
        if len(text) > max_length:
            text = text[:max_length - 1] + "…"
        return text

    @staticmethod
    def preview(item, max_length=PREVIEW_LENGTH):
        if item.is_password:
            return MASK
        return ClipboardViewModel._shorten(item.content, max_length)

    @staticmethod
    def item_title(item):
        if item.title:
            return item.title
        if item.is_password:
            return "Unbenanntes Passwort"
        return None

    @staticmethod
    def display_text(item, max_length=PREVIEW_LENGTH):
        # Titel ersetzt den Inhalt
        title = ClipboardViewModel.item_title(item)
        if title:
            return ClipboardViewModel._shorten(title, max_length)
        return ClipboardViewModel.preview(item, max_length)

    @staticmethod
    def text_style(item):
        # "title" = umbenannt, "placeholder" = Passwort ohne Namen, "plain" = Inhalt
        if item.title:
            return "title"
        if item.is_password:
            return "placeholder"
        return "plain"

    @staticmethod
    def kind_icon(item):
        return KIND_ICONS.get(item.kind, "")

    @staticmethod
    def source_text(item):
        return f"aus {item.source_app}" if item.source_app else ""

    def tooltip_text(self, item):
        if item.is_password:
            # niemals den Inhalt eines Passworts zeigen
            lines = [self.item_title(item)]
            if item.username:
                lines.append(f"Benutzer: {item.username}")
            if item.url:
                lines.append(f"Adresse: {item.url}")
            info = [part for part in (self.source_text(item), self.datetime_text(item)) if part]
            lines.append(" · ".join(info))
            return "\n".join(lines)
        return self._limit_text(item.content)

    @staticmethod
    def _limit_text(text):
        text = text.strip()
        cut = len(text) > TOOLTIP_MAX_CHARS
        lines = text[:TOOLTIP_MAX_CHARS].splitlines()
        if len(lines) > TOOLTIP_MAX_LINES:
            lines = lines[:TOOLTIP_MAX_LINES]
            cut = True
        result = "\n".join(lines)
        return result + "\n…" if cut else result

    @staticmethod
    def always_tooltip(item):
        # Inhalt ist nicht zu sehen, also immer einen Tooltip zeigen
        return bool(item.title) or item.is_password

    @staticmethod
    def group_initial(group):
        name = group.name.strip() if group else ""
        return name[:1].upper() or "?"

    @staticmethod
    def group_name(item, max_length=None):
        name = item.clipboard_group.name if item.clipboard_group else ""
        if max_length:
            return ClipboardViewModel._shorten(name, max_length)
        return name

    @staticmethod
    def group_color(item):
        return item.clipboard_group.color if item.clipboard_group else "#9e9e9e"

    @staticmethod
    def date_text(item):
        day = item.created_at.date()
        today = date.today()
        if day == today:
            return "Heute"
        if day == today - timedelta(days=1):
            return "Gestern"
        return day.strftime("%d.%m.%Y")

    @property
    def show_group(self):
        # Gruppenname nur in "Alle Einträge" anzeigen
        return self.selected_group is None

    @property
    def visible_columns(self):
        # vorerst nur die automatische Regel, später auch Benutzereinstellungen
        return [column for column in TABLE_COLUMNS if column != "group" or self.show_group]

    @staticmethod
    def time_text(item):
        return item.created_at.strftime("%H:%M")

    @property
    def default_group(self):
        return self.history.get_default_group()

    @property
    def custom_groups(self):
        default = self.history.get_default_group()
        return [group for group in self.history.list_groups() if group is not default]

    def group_count(self, group):
        # None zählt alle Einträge
        return self.history.count(group)

    @property
    def title_text(self):
        return self.selected_group.name if self.selected_group else "Alle Einträge"

    @staticmethod
    def entries_text(count):
        return "1 Eintrag" if count == 1 else f"{count} Einträge"

    def group_tooltip(self, group, name):
        return f"{name} · {self.entries_text(self.group_count(group))}"

    # Ansicht

    def set_search(self, text):
        self.search = text
        self._reset_paging()
        self._notify()

    def set_sort(self, sort_by):
        self.sort_by = sort_by
        self._reset_paging()
        self._notify()

    def toggle_direction(self):
        self.descending = not self.descending
        self._reset_paging()
        self._notify()

    def set_favorites_only(self, value):
        self.favorites_only = value
        self._reset_paging()
        self._notify()

    def sort_by_column(self, sort_by):
        if self.sort_by == sort_by:
            self.descending = not self.descending
        else:
            self.sort_by = sort_by
            self.descending = False
        self._reset_paging()
        self._notify()

    # Befehle

    def copy(self, item):
        # kein _notify: eigene Kopien erfasst der Service nicht als neuen Eintrag
        self.service.set_text(self.history.get_content(item), sensitive=item.is_password)

    def copy_text(self, text, sensitive=False):
        # einzelne Angabe kopieren, z. B. Benutzername oder Adresse aus dem Dialog
        if text:
            self.service.set_text(text, sensitive=sensitive)

    def item_content(self, item):
        # bei Passwörtern wird der Inhalt erst jetzt geholt
        return self.history.get_content(item)

    def delete(self, item):
        self.history.remove_items([item])
        self.checked.discard(item)
        self._notify()

    def toggle_favorite(self, item):
        self.history.toggle_favorite(item)
        self._notify()

    def rename(self, item, title, username=None, url=None):
        self.history.rename_item(item, title, username, url)
        self._notify()

    def set_password(self, item, is_password):
        self.history.mark_password(item, is_password)
        self._notify()

    def move(self, item, target, after=False):
        if not self.can_drag:
            return
        self.history.move_item(item, target, after=after)
        self._notify()

    def delete_visible(self):
        removed = self.history.clear_items(self._all_matching())
        self.checked -= set(removed)
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
        items = self.checked_visible()
        self.history.remove_items(items)
        self.checked -= set(items)
        self._notify()

    def select_group(self, group):
        self.selected_group = group
        self._reset_paging()
        # Nach Gruppe sortieren ergibt innerhalb einer Gruppe keinen Sinn
        if group is not None and self.sort_by == "group":
            self.sort_by = "priority"
            self.descending = False
        self._notify()

    def select_group_by_id(self, group_id):
        # unbekannte oder fehlende ID → "Alle Einträge"
        group = next((g for g in self.history.list_groups() if g.id == group_id), None)
        self.select_group(group)

    @property
    def selected_group_id(self):
        if self.locked:
            return self._locked_group_id   # z. B. beim Schließen im gesperrten Zustand
        return self.selected_group.id if self.selected_group else None

    def add_group(self, name, color):
        name = name.strip()
        if not name:
            raise ValueError("Bitte einen Namen eingeben.")
        group = self.history.add_group(name, color)
        self._notify()
        return group

    def remove_group(self, group):
        self.history.remove_group(group)
        if self.selected_group is group:
            self.selected_group = None   # gelöschte Gruppe kann nicht ausgewählt bleiben
        self._notify()

    def assign_items_to_group(self, items, group):
        self.history.assign_items_to_group(items, group)
        self.checked -= set(items)
        self._notify()

    def move_group(self, group, target, after=False):
        self.history.move_group(group, target, after=after)
        self._notify()