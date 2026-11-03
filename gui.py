import threading
import tkinter as tk
import customtkinter as ctk
import tkinter.font as tkfont

import ctypes
import os
import sys
import time
import traceback


import single_instance

from settings import load_settings, save_settings
from demo_data import load_demo_data
from widgets import GroupIcon, Tooltip, is_inside, place_near
from tkinter import messagebox, ttk, colorchooser
from clipboard_service import ClipboardService
from history import ClipboardHistory
from viewmodel import ClipboardViewModel, MASK
from edit_dialog import EditDialog
from login_view import LoginView
from api_client import ApiClient, ApiError, ServiceUnavailable
from startup import open_api_data, read_header_from_service
from service_runner import ServiceRunner
from service.auth import load_or_create_token
from lock_watcher import LockWatcher

# Dieselbe Datei startet auch den Speicherdienst (wichtig für die .exe)
if "--service" in sys.argv:
    from service.__main__ import run
    run()
    sys.exit(0)

# Erscheinungsbild 

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

CARD = ("#ffffff", "#2b2b2b")
CARD_HOVER = ("#e8f0fb", "#3a3a3a")
TEXT = ("#1a1a1a", "#f2f2f2")
MUTED = ("#6b6b6b", "#a0a0a0")
ACCENT = ("#0067c0", "#4ca0e0")
SIDEBAR = ("#ebebeb", "#212121")
SELECTED = ("#dbe7f6", "#33415c")
DIVIDER = ("#d0d0d0", "#3a3a3a")
DEFAULT_GROUP_COLOR = "#9e9e9e"
SIDEBAR_HOVER = ("#dedede", "#2c2c2c")
SWITCH_BG = ("#e2e2e2", "#333333")    
SWITCH_HOVER = ("#d0d0d0", "#404040")   

ALL_ICON_COLOR = ("#d0d0d0", "#4a4a4a")
ALL_ICON_SYMBOL = "≡"
ALL_ICON_FONT = ("Segoe UI Symbol", 15)

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SMALL = ("Segoe UI", 11)

FONT_BOLD = ("Segoe UI Semibold", 13)
FONT_ITALIC = ("Segoe UI", 13, "italic")
FONT_KIND = ("Segoe MDL2 Assets", 13)

CARD_FONTS = {"title": FONT_BOLD, "placeholder": FONT_ITALIC, "plain": FONT}

SIDEBAR_EXPANDED_WIDTH = 210
SIDEBAR_COLLAPSED_WIDTH = 52

NARROW_BELOW = 740   # unter dieser Fensterbreite schmaler Modus
WIDE_ABOVE = 780     # über dieser Breite wieder breiter Modus

DEFAULT_GEOMETRY = "1000x560"

DRAG_THRESHOLD = 5

TEXT_TOOLTIP_DELAY = 1000   # ms
TEXT_TOOLTIP_WIDTH = 480    # px, danach Zeilenumbruch
TABLE_FONT = ("Segoe UI", 10)

SORT_OPTIONS = {
    "Eigene Reihenfolge": "priority",
    "Zeitstempel": "time",
    "Inhalt": "content",
    "Gruppe": "group",
    "Favoriten": "favorite"
}
SORT_LABELS = {value: label for label, value in SORT_OPTIONS.items()}   # umgekehrte Richtung

LOAD_DEMO_DATA = False   # beim Starten Demo-Daten laden

APP_VERSION = "1.2.0"
APP_TITLE = f"Zwischenablagen Manager  {APP_VERSION}"
APP_ID = "B5A469AA-EA94-4DAE-BFEB-B00931C8C895"

# (Spalten-ID, Überschrift, Breite, Sortierung oder None)
# Verknüpft mit Table Columns in viewmodel.py, die Reihenfolge muss übereinstimmen
COLUMNS = [
    ("check", "☐", 40, None),
    ("position", "Pos.", 50, "priority"),
    ("content", "Inhalt", 380, "content"),
    ("group", "Gruppe", 120, "group"),
    ("time", "Zeitstempel", 140, "time"),
    ("favorite", "★", 40, "favorite"),
]

COMPACT_COLUMNS = ("check", "content", "favorite")   # Spalten im schmalen Modus


def resource_path(filename):
    # In der .exe liegen mitgelieferte Dateien in einem eigenen Ordner von PyInstaller
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, filename)

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def is_on_screen(x, y):
    # 0 bedeutet: an dieser Stelle gibt es keinen Monitor
    return bool(ctypes.windll.user32.MonitorFromPoint(POINT(x, y), 0))

def show_item_menu(widget, event, vm, item, on_edit):
    menu = tk.Menu(widget, tearoff=0)
    edit_label = "Benennen …" if item.needs_review else "Umbenennen …"
    menu.add_command(label=edit_label, command=lambda: on_edit(item))
    if item.title:
        menu.add_command(label="Namen entfernen",
                         command=lambda: vm.rename(item, "", item.username, item.url))
    menu.add_separator()
    if item.is_password:
        menu.add_command(label="Kein Passwort", command=lambda: vm.set_password(item, False))
    else:
        menu.add_command(label="Als Passwort markieren",
                         command=lambda: vm.set_password(item, True))
    menu.add_separator()
    menu.add_command(label="Kopieren", command=lambda: vm.copy(item))
    menu.add_command(label="Löschen", command=lambda: vm.delete(item))
    menu.tk_popup(event.x_root, event.y_root)

#  Klassen für Ansichten
class Card(ctk.CTkFrame):  # eine Kachel, wird beim Neuzeichnen wiederverwendet
    def __init__(self, view, item):
        super().__init__(view, fg_color=CARD, corner_radius=8)
        self.view = view
        self.vm = view.vm
        self.item = item
        self._shown = None   # zuletzt angezeigter Stand, um unnötiges Zeichnen zu sparen

        # Spaltenaufteilung: nur die Vorschau wächst, rechts feste Breiten
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=96)
        self.grid_columnconfigure(3, minsize=96)

        # Spalte 0: farbiger Streifen der Gruppe
        self.stripe = ctk.CTkFrame(self, width=4, height=1, corner_radius=2)
        self.stripe.grid(row=0, column=0, sticky="ns", padx=(6, 0), pady=8)

        # Spalte 1: Text in zwei Zeilen; alle Teile einmal anlegen, später nur ein- und ausblenden
        self.text_box = ctk.CTkFrame(self, fg_color="transparent")
        self.text_box.grid(row=0, column=1, sticky="ew", padx=(12, 16), pady=6)
        self.text_box.grid_columnconfigure(1, weight=1)

        self.icon_label = ctk.CTkLabel(self.text_box, text="", font=FONT_KIND,
                                       text_color=MUTED, width=18)

        self.main_label = ctk.CTkLabel(self.text_box, text="", font=FONT, text_color=TEXT,
                                       anchor="w", justify="left", width=1)
        self.main_label.grid(row=0, column=1, sticky="ew")

        self.mask_label = ctk.CTkLabel(self.text_box, text=MASK, font=FONT_SMALL, text_color=MUTED)

        self.review_button = ctk.CTkButton(self.text_box, text="Benennen", width=76, height=22,
                                           font=FONT_SMALL,
                                           command=lambda: self.view.on_edit(self.item))

        self.source_label = ctk.CTkLabel(self.text_box, text="", font=FONT_SMALL,
                                         text_color=MUTED, anchor="w", width=1, height=16)

        # Spalte 2: Uhrzeit über Datum, rechtsbündig
        time_box = ctk.CTkFrame(self, fg_color="transparent")
        time_box.grid(row=0, column=2, sticky="e", padx=(0, 8))

        self.time_label = ctk.CTkLabel(time_box, text="", font=FONT_SMALL, text_color=TEXT,
                                       width=88, height=18, anchor="e")
        self.time_label.pack(anchor="e")
        self.date_label = ctk.CTkLabel(time_box, text="", font=FONT_SMALL, text_color=MUTED,
                                       width=88, height=18, anchor="e")
        self.date_label.pack(anchor="e")

        # Spalte 3: Stern und X über dem Gruppennamen, rechtsbündig
        action_box = ctk.CTkFrame(self, fg_color="transparent")
        action_box.grid(row=0, column=3, sticky="e", padx=(0, 8))

        buttons = ctk.CTkFrame(action_box, fg_color="transparent")
        buttons.pack(anchor="e")

        self.star_button = ctk.CTkButton(
            buttons, text="☆", width=28, height=24,
            fg_color="transparent", hover_color=CARD_HOVER, text_color=MUTED,
            command=lambda: self.vm.toggle_favorite(self.item),
        )
        self.star_button.pack(side="left")

        ctk.CTkButton(
            buttons, text="✕", width=28, height=24,
            fg_color="transparent", hover_color=CARD_HOVER, text_color=MUTED,
            command=lambda: self.vm.delete(self.item),
        ).pack(side="left")

        # in Gruppenansichten leer, aber gleich hoch, damit die Kachel nicht springt
        self.group_label = ctk.CTkLabel(action_box, text="", font=FONT_SMALL,
                                        text_color=MUTED, width=96, height=18, anchor="e")
        self.group_label.pack(anchor="e")

        # Klick, Ziehen und Hover auf allem außer den Buttons; immer mit dem aktuellen self.item
        text_widgets = [self.text_box, self.icon_label, self.main_label,
                        self.mask_label, self.source_label]
        for widget in (self, self.stripe, *text_widgets, time_box, self.time_label,
                       self.date_label, action_box, buttons, self.group_label):
            widget.bind("<ButtonPress-1>", lambda event: self.view._on_press(event, self.item))
            widget.bind("<B1-Motion>", self.view._on_motion)
            widget.bind("<ButtonRelease-1>", self.view._on_release)
            widget.bind("<Enter>", lambda _event: self.configure(fg_color=CARD_HOVER))
            widget.bind("<Leave>", lambda _event: self.view._on_card_leave(self))
            widget.bind("<Button-3>", lambda event: self.view._open_menu(event, self.item))

        # Tooltip erst jetzt, damit seine Bindungen die obigen ergänzen statt ersetzen
        Tooltip([self, *text_widgets], self._tooltip_text, delay=TEXT_TOOLTIP_DELAY,
                position="pointer", wraplength=TEXT_TOOLTIP_WIDTH)

        self.show_item(item)

    # Anzeigen

    @staticmethod
    def _show(widget, visible, **grid_options):
        # grid_forget statt grid_remove: CustomTkinter blendet sonst bei
        # geänderter Bildschirmskalierung versteckte Teile wieder ein
        if visible:
            if widget.winfo_manager() != "grid":
                widget.grid(**grid_options)
        else:
            widget.grid_forget()

    def show_item(self, item):
        # Name nicht "update": das ist schon eine wichtige Tkinter-Methode
        self.item = item
        vm = self.vm
        shown = (
            vm.display_text(item), vm.text_style(item), vm.kind_icon(item),
            item.is_password, item.needs_review, vm.source_text(item),
            vm.time_text(item), vm.date_text(item), item.is_favorite,
            vm.group_name(item, max_length=12) if vm.show_group else "",
            vm.group_color(item),
        )
        if shown == self._shown:
            return   # nichts geändert, nichts zeichnen
        self._shown = shown
        (text, style, icon, is_password, needs_review, source,
         time_text, date_text, is_favorite, group_text, group_color) = shown

        self.stripe.configure(fg_color=group_color)

        self.icon_label.configure(text=icon)
        self._show(self.icon_label, bool(icon), row=0, column=0, padx=(0, 8))

        self.main_label.configure(text=text, font=CARD_FONTS[style],
                                  text_color=MUTED if style == "placeholder" else TEXT)
        self._show(self.mask_label, is_password, row=0, column=2, padx=(12, 0))
        self._show(self.review_button, needs_review, row=0, column=3, padx=(12, 0))

        self.source_label.configure(text=source)
        self._show(self.source_label, bool(source), row=1, column=1, columnspan=2, sticky="ew")

        self.time_label.configure(text=time_text)
        self.date_label.configure(text=date_text)

        self.star_button.configure(text="★" if is_favorite else "☆",
                                   text_color=ACCENT if is_favorite else MUTED)
        self.group_label.configure(text=group_text)

    # Tooltip

    def _tooltip_text(self):
        # wird erst beim Anzeigen aufgerufen, dann ist die Breite bekannt
        if self.vm.always_tooltip(self.item) or self._is_cut():
            return self.vm.tooltip_text(self.item)
        return None

    def _is_cut(self):
        label = self.main_label
        shown = label.cget("text")
        if shown != (self.item.content or "").strip():
            return True   # gekürzt oder Zeilenumbrüche zusammengefasst
        # Achtung: _label ist ein internes Feld von CustomTkinter
        font = tkfont.Font(font=label._label.cget("font"))
        return font.measure(shown) > label.winfo_width()
    
MAX_CARDS = 300   # so viele Kacheln werden höchstens aufbewahrt, auch unsichtbare

class CardView(ctk.CTkScrollableFrame):  # Kachel-Ansicht
    def __init__(self, master, vm, sidebar, on_edit):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
        self.sidebar = sidebar
        self.on_edit = on_edit
        self.cards = {}        # Eintrags-ID → Kachel, wird wiederverwendet
        self.card_items = {}   # Kachel → Eintrag, für Drag & Drop
        self._packed = []      # zuletzt angezeigte Reihenfolge
        self.drag = {"item": None, "start_y": 0, "active": False, "target": None}

        # feste Elemente, werden nur ein- und ausgeblendet
        self.empty_label = ctk.CTkLabel(self, text="", font=FONT, text_color=MUTED)
        self.more_button = ctk.CTkButton(self, text="", height=32, font=FONT_SMALL,
                                         fg_color="transparent", border_width=1, text_color=TEXT,
                                         hover_color=CARD_HOVER, command=vm.load_more)

        self._dirty = False                # veraltet, weil unsichtbar nicht gezeichnet
        self.bind("<Map>", self._on_map)   # beim Einblenden nachholen

        vm.subscribe(self.refresh)   # bei jeder Änderung neu zeichnen

    # Zeichnen

    def _clear(self):
        # beim Sperren: alle Kacheln mit ihrem Klartext zerstören
        for card in self.cards.values():
            card.destroy()
        self.cards.clear()
        self.card_items = {}
        self.empty_label.pack_forget()
        self.more_button.pack_forget()
        self._packed = []
        self._dirty = True   # nach dem Entsperren neu zeichnen
    
    def _on_map(self, _event):
        if self._dirty:
            self.refresh()

    def refresh(self):

        # gesperrt: aufräumen, auch wenn die Ansicht gerade nicht sichtbar ist
        if self.vm.locked:
            self._clear()
            return
        
        # unsichtbare Ansicht nicht zeichnen, nur vormerken
        if not self.winfo_ismapped():
            self._dirty = True
            return
        self._dirty = False

        # Scrollposition: bei neuer Ansicht nach oben, sonst an derselben Stelle bleiben
        # Achtung: _parent_canvas ist ein internes Feld von CustomTkinter
        canvas = self._parent_canvas
        top = 0.0 if self.vm.scroll_to_top else canvas.yview()[0]
        old_height = self.winfo_reqheight()

        items = self.vm.get_visible_items()
        wanted = {item.id for item in items}

        # nicht angezeigte Kacheln behalten (schnelles Zurückwechseln), aber nicht unbegrenzt
        hidden = [item_id for item_id in self.cards if item_id not in wanted]
        for item_id in hidden[:max(0, len(self.cards) - MAX_CARDS)]:
            self.cards.pop(item_id).destroy()

        # vorhandene Kacheln aktualisieren, nur fehlende neu bauen
        order = []
        for item in items:
            card = self.cards.get(item.id)
            if card is None:
                card = Card(self, item)
                self.cards[item.id] = card
            else:
                card.show_item(item)
            order.append(card)
        self.card_items = {card: card.item for card in order}

        if not items:
            self.empty_label.configure(text=self.vm.empty_text)
            order.append(self.empty_label)
        if self.vm.has_more:
            self.more_button.configure(text=self.vm.more_text)
            order.append(self.more_button)

        # nur neu anordnen, wenn sich die Reihenfolge geändert hat
        if order != self._packed:
            for widget in self._packed:
                if widget.winfo_exists():
                    widget.pack_forget()
            for widget in order:
                if widget is self.empty_label:
                    widget.pack(pady=24)
                elif widget is self.more_button:
                    widget.pack(fill="x", padx=4, pady=(4, 8))
                else:
                    widget.pack(fill="x", padx=4, pady=4)
            self._packed = order

        # dieselbe Stelle wie vorher, auch wenn die Liste jetzt länger ist
        self.update_idletasks()
        new_height = self.winfo_reqheight()
        if new_height > 0:
            canvas.yview_moveto(top * old_height / new_height)

    # Drag & Drop

    def _find_card(self, widget):
        while widget is not None:
            if widget in self.card_items:
                return widget
            widget = widget.master
        return None

    def _set_drop_target(self, card):
        old = self.drag["target"]
        if old is card:
            return
        if old is not None and old.winfo_exists():
            old.configure(border_width=0)
        if card is not None:
            card.configure(border_width=2, border_color=ACCENT)
        self.drag["target"] = card

    def _sidebar_target(self, event):
        row = self.sidebar.find_row(event.x_root, event.y_root)
        if row is not None and self.sidebar.group_of(row) is None:
            return None   # "Alle Einträge" ist keine Gruppe
        return row

    def _on_press(self, event, item):
        self.drag.update(item=item, start_y=event.y_root, active=False)

    def _on_motion(self, event):
        if self.drag["item"] is None:
            return

        window = self.winfo_toplevel()
        if not self.drag["active"] and abs(event.y_root - self.drag["start_y"]) > DRAG_THRESHOLD:
            self.drag["active"] = True
            window.configure(cursor="fleur")

        if not self.drag["active"]:
            return

        sidebar_row = self._sidebar_target(event)
        self.sidebar.set_highlight(sidebar_row)

        if sidebar_row is None and self.vm.can_drag:
            self._set_drop_target(self._find_card(window.winfo_containing(event.x_root, event.y_root)))
        else:
            self._set_drop_target(None)

    def _on_release(self, event):
        item = self.drag["item"]
        if item is None:
            return

        if not self.drag["active"]:
            self.drag.update(item=None, active=False, target=None)
            self.vm.copy(item)   # kein Ziehen → Klick
            return

        window = self.winfo_toplevel()
        window.configure(cursor="")
        sidebar_row = self._sidebar_target(event)
        card = self._find_card(window.winfo_containing(event.x_root, event.y_root))
        self.sidebar.set_highlight(None)
        self._set_drop_target(None)
        self.drag.update(item=None, active=False, target=None)

        if sidebar_row is not None:
            self.vm.assign_items_to_group([item], self.sidebar.group_of(sidebar_row))
        elif card is not None:
            middle = card.winfo_rooty() + card.winfo_height() / 2
            self.vm.move(item, self.card_items[card], after=event.y_root > middle)

    # Hover und Menü

    def _on_card_leave(self, card):
        x, y = card.winfo_pointerxy()
        widget = card.winfo_containing(x, y)
        if widget is None or not is_inside(widget, card):
            card.configure(fg_color=CARD)

    def _open_menu(self, event, item):
        show_item_menu(self, event, self.vm, item, self.on_edit)

class TableView(ctk.CTkFrame):  # Tabellen-Ansicht
    def __init__(self, master, vm, sidebar, on_edit):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
        self.compact = False
        self.sidebar = sidebar
        self.on_edit = on_edit
        self.row_items = {}   # Zeilen-ID → Eintrag
        self.row_tags = {}    # Zeilen-ID → Stil-Tags, damit "drop" sie nicht überschreibt
        self.more_row = None   # Zeile "Weitere laden" am Ende
        self.drag = {"item": None, "start_y": 0, "active": False, "target_row": None}

        ttk.Style().theme_use("clam")
        self.tree = ttk.Treeview(
            self, columns=[column[0] for column in COLUMNS],
            show="headings", selectmode="browse",
        )
        for col_id, title, width, _sort_key in COLUMNS:
            self.tree.heading(col_id, text=title,
                              command=lambda c=col_id: self._on_heading_click(c))
            self.tree.column(col_id, width=width, minwidth=100 if col_id == "content" else width,
                             stretch=(col_id == "content"),
                             anchor="w" if col_id == "content" else "center")

        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<ButtonPress-1>", self._on_press)
        self.tree.bind("<B1-Motion>", self._on_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_release)
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self._hover_row = None
        self.tooltip = Tooltip(self.tree, self._tooltip_text, delay=TEXT_TOOLTIP_DELAY,
                               position="pointer", wraplength=TEXT_TOOLTIP_WIDTH)
        self.tree.bind("<Motion>", self._on_hover, add="+")

        self._dirty = False                # veraltet, weil unsichtbar nicht gezeichnet
        self.bind("<Map>", self._on_map)   # beim Einblenden nachholen
        vm.subscribe(self.refresh)

    #  Zeichnen 
    def _on_map(self, _event):
        if self._dirty:
            self.refresh()

    def refresh(self):
        # gesperrt: alle Zeilen entfernen, auch wenn die Ansicht gerade nicht sichtbar ist
        if self.vm.locked:
            self.tooltip.hide()
            self.tree.delete(*self.tree.get_children())
            self.row_items.clear()
            self.row_tags.clear()
            self.more_row = None
            self._hover_row = None
            self._dirty = True
            return
        # unsichtbare Ansicht nicht zeichnen, nur vormerken
        if not self.winfo_ismapped():
            self._dirty = True
            return
        self._dirty = False
        self._apply_style()

        visible = self.vm.visible_columns
        if self.compact:
            visible = [column for column in visible if column in COMPACT_COLUMNS]
        self.tree.configure(displaycolumns=visible)

        # Scrollposition: bei neuer Ansicht nach oben, sonst dieselbe Zeile oben behalten
        top = 0.0 if self.vm.scroll_to_top else self.tree.yview()[0]
        old_rows = len(self.tree.get_children())

        self.tree.delete(*self.tree.get_children())
        self.row_items.clear()
        self.row_tags.clear()
        self.more_row = None

        self._hover_row = None   # alte Zeilen-IDs gibt es nicht mehr

        for item in self.vm.get_visible_items():
            values = (
                "☑" if self.vm.is_checked(item) else "☐",
                self.vm.position(item),
                self.vm.display_text(item, 80),
                self.vm.group_name(item),
                self.vm.datetime_text(item),
                "★" if item.is_favorite else "☆",
            )
            tags = (self.vm.text_style(item),)
            row_id = self.tree.insert("", "end", values=values, tags=tags)
            self.row_items[row_id] = item
            self.row_tags[row_id] = tags

        # letzte Zeile: weitere Einträge nachladen
        if self.vm.has_more:
            values = ("", "", f"▼  {self.vm.more_text}", "", "", "")
            self.more_row = self.tree.insert("", "end", values=values, tags=("more",))

        new_rows = len(self.tree.get_children())
        if new_rows and old_rows:
            self.tree.yview_moveto(top * old_rows / new_rows)

        for col_id, title, _width, sort_key in COLUMNS:
            text = title
            if col_id == "check":
                text = "☑" if self.vm.all_visible_checked else "☐"
            elif sort_key == self.vm.sort_by:
                text += " ▼" if self.vm.descending else " ▲"
            self.tree.heading(col_id, text=text)

    def set_compact(self, compact):
        self.compact = compact
        self.refresh()

    def _apply_style(self):
        dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if dark else "#ffffff"
        fg = "#f2f2f2" if dark else "#1a1a1a"
        head = "#333333" if dark else "#ebebeb"
        selected = "#33415c" if dark else "#dbe7f6"
        drop = "#4ca0e0" if dark else "#9cc3ec"

        style = ttk.Style()
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg,
                        rowheight=28, borderwidth=0, font=TABLE_FONT)
        style.configure("Treeview.Heading", background=head, foreground=fg,
                        relief="flat", font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", selected)],
                  foreground=[("selected", fg)])

        self.tree.tag_configure("drop", background=drop)   # Farbe der Ziel-Zeile
        self.tree.tag_configure("title", font=("Segoe UI Semibold", 10))
        self.tree.tag_configure("placeholder", font=("Segoe UI", 10, "italic"),
                                foreground="#a0a0a0" if dark else "#6b6b6b")
        self.tree.tag_configure("more", foreground="#4ca0e0" if dark else "#0067c0")

    # Hilfsfunktionen 

    def _column_id_at(self, x):
        index = int(self.tree.identify_column(x)[1:]) - 1
        displayed = self.tree["displaycolumns"]
        if displayed in ("#all", ("#all",)):
            displayed = [column[0] for column in COLUMNS]
        return displayed[index]

    def _set_drop_row(self, row_id):
        old = self.drag["target_row"]
        if old == row_id:
            return
        if old and self.tree.exists(old):
            self.tree.item(old, tags=self.row_tags.get(old, ()))
        if row_id:
            self.tree.item(row_id, tags=self.row_tags.get(row_id, ()) + ("drop",))
        self.drag["target_row"] = row_id

    def _reset_drag(self):
        self.drag.update(item=None, active=False, target_row=None)

    def _sidebar_target(self, event):
        row = self.sidebar.find_row(event.x_root, event.y_root)
        if row is not None and self.sidebar.group_of(row) is None:
            return None
        return row

    def _drag_items(self):
        item = self.drag["item"]
        if self.vm.is_checked(item):
            return self.vm.checked_visible()   # markierte Zeile → alle markierten
        return [item]                          # sonst nur diese eine

    # Eingaben 
    def _on_heading_click(self, col_id):
        if col_id == "check":
            self.vm.set_all_checked(not self.vm.all_visible_checked)
            return
        sort_key = next(column[3] for column in COLUMNS if column[0] == col_id)
        if sort_key is not None:
            self.vm.sort_by_column(sort_key)

    def _on_press(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        if row_id == self.more_row:
            self.vm.load_more()
            return "break"

        item = self.row_items[row_id]
        col_id = self._column_id_at(event.x)

        if col_id == "check":
            self.vm.toggle_checked(item)
            return "break"
        if col_id == "favorite":
            self.vm.toggle_favorite(item)
            return "break"

        # mögliches Ziehen vormerken
        self.drag.update(item=item, start_y=event.y, active=False, target_row=None)

    def _on_motion(self, event):
        if self.drag["item"] is None:
            return

        if not self.drag["active"] and abs(event.y - self.drag["start_y"]) > DRAG_THRESHOLD:
            self.drag["active"] = True
            self.tree.configure(cursor="fleur")

        if not self.drag["active"]:
            return

        sidebar_row = self._sidebar_target(event)
        self.sidebar.set_highlight(sidebar_row)

        is_single = len(self._drag_items()) == 1
        if sidebar_row is None and is_single and self.vm.can_drag:
            target = self.tree.identify_row(event.y)
            self._set_drop_row(target if target in self.row_items else None)
        else:
            self._set_drop_row(None)
        return "break"

    def _on_release(self, event):
        item = self.drag["item"]
        if item is None:
            return

        was_dragging = self.drag["active"]
        items = self._drag_items()   # VOR dem Zurücksetzen bestimmen
        self.tree.configure(cursor="")
        sidebar_row = self._sidebar_target(event)
        self.sidebar.set_highlight(None)
        self._set_drop_row(None)
        self._reset_drag()

        if not was_dragging:
            return

        # in eine Gruppe: einer oder mehrere
        if sidebar_row is not None:
            self.vm.assign_items_to_group(items, self.sidebar.group_of(sidebar_row))
            return

        # innerhalb der Liste: nur einzeln und nur in eigener Reihenfolge
        if len(items) > 1 or not self.vm.can_drag:
            return

        row_id = self.tree.identify_row(event.y)
        if row_id in self.row_items:
            _x, y, _width, height = self.tree.bbox(row_id)
            self.vm.move(item, self.row_items[row_id], after=event.y > y + height / 2)
        elif self.tree.identify_region(event.x, event.y) == "nothing":
            self.vm.move(item, None)

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        if row_id in self.row_items and self._column_id_at(event.x) not in ("check", "favorite"):
            self.vm.copy(self.row_items[row_id])

    def _on_right_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if row_id not in self.row_items:
            return
        self.tree.selection_set(row_id)   # zeigt, welche Zeile gemeint ist
        show_item_menu(self, event, self.vm, self.row_items[row_id], self.on_edit)

    # Tooltip

    def _on_hover(self, event):
        row_id = None
        if self.tree.identify_region(event.x, event.y) == "cell":
            row_id = self.tree.identify_row(event.y) or None
        if row_id != self._hover_row:
            # neue Zeile: alten Tooltip schließen und Verzögerung neu starten
            self._hover_row = row_id
            self.tooltip.hide()
            if row_id:
                self.tooltip.schedule()

    def _tooltip_text(self):
        row_id = self._hover_row
        if row_id is None or row_id not in self.row_items:
            return None
        item = self.row_items[row_id]
        if self.vm.always_tooltip(item) or self._is_cut(item, row_id):
            return self.vm.tooltip_text(item)
        return None

    def _is_cut(self, item, row_id):
        shown = str(self.tree.set(row_id, "content"))
        if shown != item.content.strip():
            return True
        width = self.tree.column("content", "width")
        return tkfont.Font(font=TABLE_FONT).measure(shown) > width - 12

class GroupSidebar(ctk.CTkFrame):  # Gruppen-Seitenleiste
    def __init__(self, master, vm):
        super().__init__(master, width=SIDEBAR_EXPANDED_WIDTH, corner_radius=0, fg_color=SIDEBAR)
        self.pack_propagate(False)
        self.vm = vm
        self.collapsed = False
        self.row_groups = {}   # Zeile → Gruppe (None = "Alle Einträge")
        self.highlighted_row = None
        self.drag = {"group": None, "start_y": 0, "active": False}

        # Kopf: Umschalter und Titel
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(side="top", fill="x", padx=6, pady=(10, 6))

        self.toggle_button = ctk.CTkButton(
            self.header, text="☰", width=36, height=32, font=FONT,
            fg_color="transparent", hover_color=SIDEBAR_HOVER, text_color=TEXT,
            command=self.toggle_collapsed,
        )
        self.toggle_button.pack(side="left")

        self.toggle_tip = Tooltip(self.toggle_button, "Menü einklappen (Strg+B)")

        self.title_label = ctk.CTkLabel(self.header, text="Gruppen", font=FONT_TITLE,
                                        text_color=TEXT)
        self.title_label.pack(side="left", padx=(6, 0))

        # Fuß: vor der Liste packen, damit er unten fest bleibt
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.footer.pack(side="bottom", fill="x", padx=6, pady=(6, 10))

        self.settings_button = ctk.CTkButton(
            self.footer, text="⚙  Einstellungen", anchor="w", height=32, font=FONT,
            fg_color="transparent", hover_color=SIDEBAR_HOVER, text_color=TEXT,
        )
        self.settings_button.pack(fill="x")

        Tooltip(self.settings_button, "Einstellungen")

        # Mitte: scrollbare Liste füllt den Platz dazwischen
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius = 0)
        self.list.pack(side="top", fill="both", expand=True, padx=6)

        vm.subscribe(self.refresh)

    # Zeichnen

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.toggle_tip.text = "Menü aufklappen (Strg+B)" if self.collapsed else "Menü einklappen (Strg+B)"

        if self.collapsed:
            self.configure(width=SIDEBAR_COLLAPSED_WIDTH)
            self.title_label.pack_forget()
            self.settings_button.configure(text="⚙", anchor="center")
            self.list.pack_configure(padx=3)
            # Achtung: _scrollbar ist ein internes Feld von CustomTkinter
            self.list._scrollbar.grid_remove()
        else:
            self.configure(width=SIDEBAR_EXPANDED_WIDTH)
            self.title_label.pack(side="left", padx=(6, 0))
            self.settings_button.configure(text="⚙  Einstellungen", anchor="w")
            self.list.pack_configure(padx=6)
            self.list._scrollbar.grid()

        self.refresh()

    def refresh(self):
        self.row_groups.clear()
        self.highlighted_row = None
        for widget in self.list.winfo_children():
            widget.destroy()

        if self.vm.locked:
            return   # gesperrt: keine Gruppennamen zeigen

        self._create_row(None, "Alle Einträge", None)
        default = self.vm.default_group
        self._create_row(default, default.name, default.color)
        self._create_add_row()

        divider_padx = 4 if self.collapsed else 8
        ctk.CTkFrame(self.list, height=2, corner_radius=0, fg_color=DIVIDER).pack(
            fill="x", padx=divider_padx, pady=8)

        for group in self.vm.custom_groups:
            self._create_row(group, group.name, group.color)

    def _create_row(self, group, name, color):
        is_selected = group is self.vm.selected_group
        normal_color = SELECTED if is_selected else "transparent"

        row = ctk.CTkFrame(self.list, corner_radius=6, border_width=0, fg_color=normal_color)
        row.pack(fill="x", pady=1)

        # Auswahlbalken links, nur bei der ausgewählten Zeile sichtbar
        bar = ctk.CTkFrame(row, width=3, height=1, corner_radius=2,
                           fg_color=ACCENT if is_selected else "transparent")

        # Quadrat: "Alle Einträge" mit Symbol, Gruppen mit Anfangsbuchstaben
        if group is None:
            icon = GroupIcon(row, ALL_ICON_COLOR, ALL_ICON_SYMBOL, text_color=TEXT,
                             font=ALL_ICON_FONT)
        else:
            icon = GroupIcon(row, color, self.vm.group_initial(group))

        if self.collapsed:
            # Balken frei an den linken Rand, nimmt keinen Platz weg
            bar.place(x=2, rely=0.5, anchor="w", relheight=0.6)
            # ohne side: pack setzt das Quadrat automatisch in die Mitte
            icon.pack(pady=6)
            widgets = (row, bar, icon, icon.label)
            Tooltip(list(widgets), self.vm.group_tooltip(group, name))
        else:
            bar.pack(side="left", fill="y", padx=(2, 0), pady=6)
            icon.pack(side="left", padx=(6, 8), pady=6)

            # Anzahl zuerst packen, damit sie sich ihren Platz rechts reserviert
            count_label = ctk.CTkLabel(row, text=str(self.vm.group_count(group)),
                                       font=FONT_SMALL, text_color=MUTED, width=24, anchor="e")
            count_label.pack(side="right", padx=(4, 10))

            # Name füllt nur den übrigen Platz und wird notfalls gekürzt
            name_label = ctk.CTkLabel(row, text=self.vm.sidebar_name(name), font=FONT,
                                      text_color=TEXT, anchor="w", width=1)
            name_label.pack(side="left", fill="x", expand=True)

            widgets = (row, bar, icon, icon.label, name_label, count_label)

        self.row_groups[row] = group

        for widget in widgets:
            widget.bind("<ButtonPress-1>", lambda event, g=group: self._on_press(event, g))
            widget.bind("<B1-Motion>", self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>", lambda _event, r=row, s=is_selected: self._on_row_enter(r, s))
            widget.bind("<Leave>", lambda _event, r=row, c=normal_color: self._on_row_leave(r, c))
            if self._is_custom(group):
                widget.bind("<Button-3>", lambda event, g=group: self._on_group_menu(event, g))

    def _create_add_row(self):
        row = ctk.CTkFrame(self.list, corner_radius=6, fg_color="transparent")
        row.pack(fill="x", pady=(4, 1))

        icon = GroupIcon(row, "transparent", "＋", text_color=MUTED)

        if self.collapsed:
            icon.pack(pady=6)
            widgets = (row, icon, icon.label)
        else:
            # Platzhalter in Breite des Auswahlbalkens, damit die Quadrate untereinander stehen
            spacer = ctk.CTkFrame(row, width=3, height=1, fg_color="transparent")
            spacer.pack(side="left", padx=(2, 0))
            icon.pack(side="left", padx=(6, 8), pady=6)

            label = ctk.CTkLabel(row, text="Neue Gruppe", font=FONT, text_color=MUTED, anchor="w")
            label.pack(side="left", fill="x", expand=True)
            widgets = (row, spacer, icon, icon.label, label)
            Tooltip(list(widgets), "Neue Gruppe")

        for widget in widgets:
            widget.bind("<Button-1>", lambda _event: self._on_add_group())
            widget.bind("<Enter>", lambda _event, r=row: self._on_row_enter(r, False))
            widget.bind("<Leave>", lambda _event, r=row: self._on_row_leave(r, "transparent"))

    # Hover

    def _on_row_enter(self, row, is_selected):
        if not is_selected:
            row.configure(fg_color=SIDEBAR_HOVER)

    def _on_row_leave(self, row, normal_color):
        x, y = row.winfo_pointerxy()
        widget = row.winfo_containing(x, y)
        if widget is None or not is_inside(widget, row):
            row.configure(fg_color=normal_color)

    # Für Drag & Drop, auch von den anderen Ansichten benutzt

    def find_row(self, x_root, y_root):
        widget = self.winfo_containing(x_root, y_root)
        while widget is not None:
            if widget in self.row_groups:
                return widget
            widget = widget.master
        return None

    def group_of(self, row):
        return self.row_groups[row]

    def set_highlight(self, row):
        old = self.highlighted_row
        if old is row:
            return
        if old is not None and old.winfo_exists():
            old.configure(border_width=0)
        if row is not None:
            row.configure(border_width=2, border_color=ACCENT)
        self.highlighted_row = row

    def _is_custom(self, group):
        return group is not None and group is not self.vm.default_group

    # Eigene Gruppen verschieben

    def _on_press(self, event, group):
        self.drag.update(group=group, start_y=event.y_root, active=False)

    def _on_motion(self, event):
        group = self.drag["group"]
        if not self._is_custom(group):
            return   # "Alle Einträge" und "Unsortiert" lassen sich nicht ziehen

        if not self.drag["active"] and abs(event.y_root - self.drag["start_y"]) > DRAG_THRESHOLD:
            self.drag["active"] = True
            self.winfo_toplevel().configure(cursor="fleur")

        if self.drag["active"]:
            row = self.find_row(event.x_root, event.y_root)
            if row is not None and not self._is_custom(self.row_groups[row]):
                row = None   # nur eigene Gruppen sind Ziele
            self.set_highlight(row)

    def _on_release(self, event):
        group = self.drag["group"]
        was_dragging = self.drag["active"]
        self.drag.update(group=None, active=False)

        if not was_dragging:
            self.vm.select_group(group)   # kein Ziehen → Klick
            return

        self.winfo_toplevel().configure(cursor="")
        row = self.find_row(event.x_root, event.y_root)
        self.set_highlight(None)

        if row is None or not self._is_custom(self.row_groups[row]):
            return

        middle = row.winfo_rooty() + row.winfo_height() / 2
        self.vm.move_group(group, self.row_groups[row], after=event.y_root > middle)

    # Gruppen anlegen und löschen

    def _on_add_group(self):
        window = self.winfo_toplevel()

        dialog = ctk.CTkInputDialog(title="Neue Gruppe", text="Name der neuen Gruppe:")
        place_near(dialog, window)
        name = dialog.get_input()
        if name is None:
            return

        color = colorchooser.askcolor(title="Farbe der Gruppe wählen",
                                      parent=window)[1] or DEFAULT_GROUP_COLOR

        try:
            group = self.vm.add_group(name, color)
        except ValueError as error:
            messagebox.showwarning("Neue Gruppe", str(error), parent=window)
            return

        self.vm.select_group(group)

    def _on_group_menu(self, event, group):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f"„{group.name}“ löschen",
                         command=lambda: self._delete_group(group))
        menu.tk_popup(event.x_root, event.y_root)

    def _delete_group(self, group):
        if messagebox.askyesno(
            "Gruppe löschen",
            f"Gruppe „{group.name}“ löschen?\nIhre Einträge wandern nach „{self.vm.default_group.name}“.",
            parent=self.winfo_toplevel(),
        ) and not self.vm.locked:
            self.vm.remove_group(group)

#  Verknüpfung: Daten, ViewModel, Service

# nur eine Instanz: sonst laufendes Fenster nach vorne holen und beenden
if not single_instance.acquire():
    single_instance.bring_to_front(APP_TITLE)
    sys.exit(0)
settings = load_settings()

#  Eigene Programmkennung, damit Windows in der Taskleiste unser Symbol zeigt statt das von Python
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Abkoo.Zwischenablagen.Manager")

root = ctk.CTk()
root.title(APP_TITLE)
# CustomTkinter setzt kurz nach dem Start ein eigenes Symbol, deshalb mit Verzögerung
root.after(300, lambda: root.iconbitmap(resource_path("icon.ico")))
root.minsize(420, 420)
root.geometry(settings["window_geometry"] or DEFAULT_GEOMETRY)
root.bind("<Control-b>", lambda _event: on_sidebar_toggle())

# Speicherdienst starten
api = ApiClient(load_or_create_token())
service_runner = ServiceRunner(api)
try:
    service_runner.ensure_running()
except ServiceUnavailable as error:
    messagebox.showerror("Zwischenablagen Manager",
                         f"Der Speicherdienst konnte nicht gestartet werden.\n\n{error}",
                         parent=root)
    root.destroy()
    sys.exit(1)


def stop_service():
    service_runner.stop()

# Fehler des Speicherdienstes während der Benutzung im Fenster melden

SERVICE_MESSAGE_PAUSE = 30   # Sekunden zwischen zwei Meldungen
last_service_message = {"time": None}


def show_service_problem(error):
    if isinstance(error, ServiceUnavailable):
        try:
            if service_runner is not None:
                service_runner.ensure_running()
            text = ("Der Speicherdienst war kurz nicht erreichbar und wurde neu gestartet.\n"
                    "Bitte die letzte Aktion wiederholen.")
        except ServiceUnavailable as again:
            text = f"Der Speicherdienst ist nicht erreichbar.\n\n{again}"
    else:
        text = f"Der Speicherdienst hat einen Fehler gemeldet ({error.status}):\n{error.detail}"

    # nicht bei jedem Fehler erneut melden, z. B. wenn er alle 100 ms auftritt
    now = time.monotonic()
    if last_service_message["time"] is not None and \
       now - last_service_message["time"] < SERVICE_MESSAGE_PAUSE:
        return
    last_service_message["time"] = now
    messagebox.showwarning("Zwischenablagen Manager", text, parent=root)


def report_callback_error(exc_type, error, tb):
    # Fehler aus Klicks und after-Aufrufen: Dienst-Probleme im Fenster, alles andere wie bisher
    if isinstance(error, (ServiceUnavailable, ApiError)):
        show_service_problem(error)
    else:
        traceback.print_exception(exc_type, error, tb)


root.report_callback_exception = report_callback_error

# Tresor-Header über den Speicherdienst lesen
try:
    header = read_header_from_service(api)
except (ApiError, ServiceUnavailable) as error:
    messagebox.showerror("Zwischenablagen Manager",
                         f"Die Daten konnten nicht gelesen werden.\n\n{error}", parent=root)
    stop_service()
    root.destroy()
    sys.exit(1)

# Anmeldung: wartet, bis der Benutzer angemeldet ist und die Daten offen sind
login_result = {}
login_done = tk.BooleanVar(value=False)


def on_unlocked(vault, is_new, header_changed):
    # liefert None bei Erfolg, sonst einen Fehlertext für die Anmeldeseite
    try:
        repository = open_api_data(api, vault, is_new, header_changed)
    except (OSError, ValueError, ApiError, ServiceUnavailable) as error:
        return f"Die Daten konnten nicht geöffnet werden: {error}"
    login_result.update(vault=vault, repository=repository, is_new=is_new)
    login_done.set(True)
    return None

def cancel_login():
    # nur melden: das Beenden passiert nach wait_variable, nicht in diesem Callback
    login_result["cancelled"] = True
    login_done.set(True)


root.protocol("WM_DELETE_WINDOW", cancel_login)
login_view = LoginView(root, header, on_unlocked)
login_view.place(relx=0, rely=0, relwidth=1, relheight=1)
root.update()
root.wait_variable(login_done)

if login_result.get("cancelled"):
    stop_service()
    root.destroy()
    sys.exit(0)

login_view.destroy()

vault = login_result["vault"]
repository = login_result["repository"]
# für die Sperre: aktueller Header (ändert sich z. B. nach "Passwort vergessen")
session = {"header": vault.header, "lock_view": None}
if login_result["is_new"] and LOAD_DEMO_DATA and repository.count() == 0:
    load_demo_data(repository)

vm = ClipboardViewModel(repository)
service = ClipboardService(vm.receive_capture)
vm.service = service

#  Hauptfenster

def refresh_header():

    if vm.locked:
        title_label.configure(text="")
        count_label.configure(text="")
        delete_checked_button.configure(state="disabled")
        return
    
    narrow = layout["narrow"]

    title = vm.title_text
    title_label.configure(text=vm.sidebar_name(title, 14) if narrow else title)
    count_label.configure(text=vm.count_text)
    clear_button.configure(text="Löschen" if narrow else vm.clear_button_text,
                           width=80 if narrow else 130)

    # aktiver Favoriten-Filter soll auch bei geschlossenem Menü sichtbar sein
    filter_button.configure(fg_color=ACCENT if vm.favorites_only else ("#d0d0d0", "#3a3a3a"),
                            text_color="white" if vm.favorites_only else TEXT)

    count = vm.checked_count
    delete_checked_button.configure(
        text=f"Löschen ({count})" if narrow else f"Markierte löschen ({count})",
        width=100 if narrow else 170,
        state="normal" if count else "disabled",
    )

def on_clear_click():
    count = vm.deletable_count()
    if count == 0:
        messagebox.showinfo("Löschen", "Keine Einträge zum Löschen. Favoriten werden nicht gelöscht.", parent=root)
        return

    text = "1 Eintrag" if count == 1 else f"{count} Einträge"
    if not messagebox.askyesno("Löschen", f"{text} löschen?\nFavoriten bleiben erhalten.", parent=root):
        return
    if vm.locked:
        return   # während der Rückfrage gesperrt

    vm.delete_visible()

    vm.delete_visible()

def on_search_change(_event):
    vm.set_search(search_entry.get())

def open_filter_menu():
    menu = tk.Menu(root, tearoff=0)

    # Variablen am Menü festhalten, sonst räumt Python sie zu früh weg
    menu.sort_var = tk.StringVar(value=vm.sort_by)
    menu.descending_var = tk.BooleanVar(value=vm.descending)
    menu.favorites_var = tk.BooleanVar(value=vm.favorites_only)

    for label, key in SORT_OPTIONS.items():
        menu.add_radiobutton(label=label, value=key, variable=menu.sort_var,
                             command=lambda k=key: vm.set_sort(k))
    menu.add_separator()
    menu.add_checkbutton(label="Absteigend", variable=menu.descending_var,
                         command=vm.toggle_direction)
    menu.add_checkbutton(label="Nur Favoriten", variable=menu.favorites_var,
                         command=lambda: vm.set_favorites_only(menu.favorites_var.get()))

    # direkt unter dem Button öffnen
    x = filter_button.winfo_rootx()
    y = filter_button.winfo_rooty() + filter_button.winfo_height()
    menu.tk_popup(x, y)

def on_delete_checked():
    count = vm.checked_count
    text = "1 Eintrag" if count == 1 else f"{count} Einträge"
    if messagebox.askyesno("Markierte löschen", f"{text} endgültig löschen?", parent=root):
        if not vm.locked:   # während der Rückfrage gesperrt?
            vm.delete_checked()

def on_view_change(choice):
    current_view["name"] = choice

    # aktives Feld hervorheben
    for name, button in view_buttons.items():
        active = name == choice
        button.configure(fg_color=ACCENT if active else "transparent",
                         hover_color=ACCENT if active else SWITCH_HOVER,
                         text_color="white" if active else TEXT)

    if choice == "Tabelle":
        card_view.pack_forget()
        clear_button.grid_remove()

        table_controls.pack(side="right", padx=(8, 0), before=filter_button)
        table_view.pack(fill="both", expand=True, padx=12)
        hint_label.configure(text="Doppelklick zum Kopieren · Ziehen zum Sortieren · Spaltenkopf zum Sortieren · ☐ zum Markieren · Rechtsklick für mehr")
    else:
        table_view.pack_forget()
        table_controls.pack_forget()

        clear_button.grid()
        card_view.pack(fill="both", expand=True, padx=12)
        hint_label.configure(text="Klicken zum Kopieren · Ziehen zum Sortieren (nur in eigener Reihenfolge) · Rechtsklick für mehr")

def restore_window():
    # CustomTkinter setzt die Größe beim ersten Anzeigen zurück, deshalb erneut setzen
    if settings["window_geometry"]:
        root.geometry(settings["window_geometry"])
    # liegt die linke obere Ecke auf keinem Bildschirm, Fenster neu platzieren
    if not is_on_screen(root.winfo_rootx() + 40, root.winfo_rooty() + 10):
        root.geometry(f"{DEFAULT_GEOMETRY}+100+100")
    if settings["window_maximized"]:
        root.state("zoomed")
    # erst nach dem ersten Anzeigen einklappen, sonst blendet CustomTkinter die Scrollbar wieder ein
    if settings["sidebar_collapsed"]:
        layout["auto_collapsed"] = False
        if not sidebar.collapsed:
            sidebar.toggle_collapsed()

    # ab jetzt auf Größenänderungen reagieren
    root.bind("<Configure>", check_layout, add="+")
    check_layout()

def poll_incoming():
    vm.process_incoming()
    root.after(100, poll_incoming)

def window_width():
    # CustomTkinter liefert die Größe bereits ohne Bildschirmskalierung
    return int(root.geometry().split("x")[0])

def check_layout(_event=None):
    # root.title(f"Breite {window_width()}") # Zum messen
    width = window_width()
    if not layout["narrow"] and width < NARROW_BELOW:
        apply_layout(True)
    elif layout["narrow"] and width > WIDE_ABOVE:
        apply_layout(False)

def apply_layout(narrow):
    layout["narrow"] = narrow

    # Seitenleiste automatisch ein- bzw. wieder ausklappen
    if narrow and not sidebar.collapsed:
        sidebar.toggle_collapsed()
        layout["auto_collapsed"] = True
    elif not narrow and layout["auto_collapsed"]:
        if sidebar.collapsed:
            sidebar.toggle_collapsed()
        layout["auto_collapsed"] = False

    # Anzahl nur im breiten Modus
    if narrow:
        count_label.grid_remove()
    else:
        count_label.grid()

    # Tabelle kompakter, Hinweistext nur im breiten Modus
    table_view.set_compact(narrow)
    if narrow:
        hint_label.pack_forget()
    else:
        hint_label.pack(side="bottom", fill="x", padx=16, pady=(8, 12))

    refresh_header()

def on_sidebar_toggle():
    # von Hand umgeschaltet: der automatische Zustand gilt nicht mehr
    layout["auto_collapsed"] = False
    sidebar.toggle_collapsed()

def open_edit_dialog(item):
    content = vm.item_content(item) if item.is_password else None
    EditDialog(root, item, lambda title, username, url: vm.rename(item, title, username, url),
               icon_path=resource_path("icon.ico"), content=content)

# Sperren

def close_dialogs():
    # offene Dialoge schließen, z. B. Benennen mit sichtbarem Passwort
    for widget in root.winfo_children():
        if isinstance(widget, tk.Toplevel):
            widget.destroy()


def lock_app():
    if vm.locked:
        return
    close_dialogs()
    try:
        service.clear()
    except Exception as error:
        print(f"Zwischenablage konnte nicht geleert werden: {error}")
    search_entry.delete(0, "end")

    repository = vm.history
    vm.lock()            # Views räumen auf
    repository.close()   # Klartext und Schlüssel entfernen

    lock_view = LoginView(root, session["header"], on_unlocked_again, locked=True)
    lock_view.place(relx=0, rely=0, relwidth=1, relheight=1)
    lock_view.lift()
    session["lock_view"] = lock_view


def on_unlocked_again(new_vault, _is_new, header_changed):
    # wie bei der ersten Anmeldung: None bei Erfolg, sonst Fehlertext
    try:
        repository = open_api_data(api, new_vault, False, header_changed)
    except (OSError, ValueError, ApiError, ServiceUnavailable) as error:
        return f"Die Daten konnten nicht geöffnet werden: {error}"
    session["header"] = new_vault.header
    vm.unlock(repository)
    # erst nach diesem Callback entfernen, die Anmeldeseite räumt noch auf
    root.after_idle(session["lock_view"].destroy)
    session["lock_view"] = None
    return None

# Einstellungen

LOCK_CHOICES = [
    (5, "5 Minuten"),
    (15, "15 Minuten"),
    (30, "30 Minuten"),
    (60, "60 Minuten"),
    (1, "1 Minute"),
    (0, "Nie"),
]


def set_setting(key, value):
    # sofort speichern, damit nichts verloren geht, falls die App abstürzt
    settings[key] = value
    try:
        save_settings(settings)
    except OSError as error:
        print(f"Einstellungen konnten nicht gespeichert werden: {error}")


def open_settings_menu():
    menu = tk.Menu(root, tearoff=0)

    # Variablen am Menü festhalten, sonst räumt Python sie zu früh weg
    menu.lock_var = tk.IntVar(value=settings["lock_minutes"])
    menu.windows_var = tk.BooleanVar(value=settings["lock_on_windows_lock"])

    # folgen in H3
    menu.add_command(label="Passwort ändern …", state="disabled")
    menu.add_command(label="Neuen Wiederherstellungsschlüssel erzeugen …", state="disabled")
    menu.add_separator()

    lock_menu = tk.Menu(menu, tearoff=0)
    for minutes, label in LOCK_CHOICES:
        lock_menu.add_radiobutton(label=label, value=minutes, variable=menu.lock_var,
                                  command=lambda m=minutes: set_setting("lock_minutes", m))
    menu.add_cascade(label="Automatisch sperren nach", menu=lock_menu)
    menu.add_checkbutton(label="Beim Sperren von Windows mitsperren", variable=menu.windows_var,
                         command=lambda: set_setting("lock_on_windows_lock",
                                                     menu.windows_var.get()))
    menu.add_separator()
    menu.add_command(label="Jetzt sperren", accelerator="Strg+L", command=lock_app)

    button = sidebar.settings_button
    menu.tk_popup(button.winfo_rootx(), button.winfo_rooty())

#  Daten

current_view = {"name": "Kacheln"}
layout = {"narrow": False, "auto_collapsed": False}


def on_close():

    # Einstellungen festhalten    
    settings["window_maximized"] = root.state() == "zoomed"
    if not settings["window_maximized"]:
        # bei maximiertem Fenster die letzte normale Größe behalten
        settings["window_geometry"] = root.geometry()
    settings["sidebar_collapsed"] = sidebar.collapsed and not layout["auto_collapsed"]
    settings["view"] = current_view["name"]
    settings["selected_group"] = vm.selected_group_id
    try:
        save_settings(settings)
    except OSError as error:
        print(f"Einstellungen konnten nicht gespeichert werden: {error}")

    stop_service()
    root.destroy()


sidebar = GroupSidebar(root, vm)
sidebar.pack(side="left", fill="y")
sidebar.toggle_button.configure(command=on_sidebar_toggle)
sidebar.settings_button.configure(command=open_settings_menu)

main_area = ctk.CTkFrame(root, fg_color="transparent")
main_area.pack(side="left", fill="both", expand=True)

# Kopfzeile: Titel, Ansicht, (freie Spalte), Anzahl, Löschen
header = ctk.CTkFrame(main_area, fg_color="transparent")
header.pack(fill="x", padx=16, pady=(14, 8))
header.grid_columnconfigure(2, weight=1)   # leere Spalte schiebt Anzahl und Button nach rechts

title_label = ctk.CTkLabel(header, text="", font=FONT_TITLE, anchor="w")
title_label.grid(row=0, column=0, sticky="w")

# Segment-Schalter: gemeinsamer Hintergrund, aktives Feld farbig
view_box = ctk.CTkFrame(header, fg_color=SWITCH_BG, corner_radius=8)
view_box.grid(row=0, column=1, padx=(16, 0))

view_buttons = {}
views = (("Kacheln", "▤"), ("Tabelle", "▦"))
for index, (name, icon) in enumerate(views):
    button = ctk.CTkButton(view_box, text=icon, width=30, height=22, corner_radius=6,
                           font=("Segoe UI Symbol", 13), fg_color="transparent",
                           hover_color=SWITCH_HOVER, text_color=TEXT,
                           command=lambda n=name: on_view_change(n))
    last = index == len(views) - 1
    button.pack(side="left", padx=(3, 3 if last else 0), pady=3)
    Tooltip(button, name)
    view_buttons[name] = button

count_label = ctk.CTkLabel(header, text="", font=FONT_SMALL, text_color=MUTED)
count_label.grid(row=0, column=3, padx=(0, 10))

clear_button = ctk.CTkButton(header, text="Alle löschen", width=130, height=28,
                             font=FONT_SMALL, command=on_clear_click)
clear_button.grid(row=0, column=4)

# Werkzeugleiste
toolbar = ctk.CTkFrame(main_area, fg_color="transparent")
toolbar.pack(fill="x", padx=16, pady=(0, 8))

search_entry = ctk.CTkEntry(toolbar, placeholder_text="Suchen …", font=FONT_SMALL)
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
search_entry.bind("<KeyRelease>", on_search_change)

filter_button = ctk.CTkButton(toolbar, text="⇅", width=32, height=28,
                              font=("Segoe UI Symbol", 14), command=open_filter_menu)
filter_button.pack(side="right")
Tooltip(filter_button, "Sortieren und filtern")

# nur in der Tabellen-Ansicht (noch nicht gepackt)
table_controls = ctk.CTkFrame(toolbar, fg_color="transparent")

delete_checked_button = ctk.CTkButton(table_controls, text="Markierte löschen", width=170,
                                      height=28, font=FONT_SMALL, command=on_delete_checked)
delete_checked_button.pack()

# Ansicht
card_view = CardView(main_area, vm, sidebar, open_edit_dialog)
card_view.pack(fill="both", expand=True, padx=12)

table_view = TableView(main_area, vm, sidebar, open_edit_dialog)   # wird erst beim Umschalten angezeigt

hint_label = ctk.CTkLabel(
    main_area, text="Klicken zum Kopieren · Ziehen zum Sortieren (nur in eigener Reihenfolge)",
    font=FONT_SMALL, text_color=MUTED,
    )   
hint_label.pack(side="bottom", fill="x", padx=16, pady=(8, 12))


# Start
root.protocol("WM_DELETE_WINDOW", on_close)
root.bind_all("<Control-l>", lambda _event: lock_app())
root.bind_all("<Control-L>", lambda _event: lock_app())   # auch mit Feststelltaste
vm.subscribe(refresh_header)
card_view.refresh()
table_view.refresh()
refresh_header()
sidebar.refresh()

# gespeicherte Einstellungen anwenden
if settings["view"] in ("Kacheln", "Tabelle"):
    vm.select_group_by_id(settings["selected_group"])
    view = settings["view"] if settings["view"] in view_buttons else "Kacheln"
    on_view_change(view)
root.after(300, restore_window)

threading.Thread(target=service.start, daemon=True).start()
root.after(100, poll_incoming)
lock_watcher = LockWatcher(root, lock_app, settings)
lock_watcher.start()
root.mainloop()