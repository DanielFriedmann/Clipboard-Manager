import threading
import tkinter as tk
import customtkinter as ctk


from demo_data import load_demo_data
from widgets import GroupIcon, Tooltip
from tkinter import messagebox, ttk, colorchooser
from clipboard_service import ClipboardService
from history import ClipboardHistory
from viewmodel import ClipboardViewModel

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

ALL_ICON_COLOR = ("#d0d0d0", "#4a4a4a")
ALL_ICON_SYMBOL = "≡"
ALL_ICON_FONT = ("Segoe UI Symbol", 15)

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SMALL = ("Segoe UI", 11)

SIDEBAR_EXPANDED_WIDTH = 210
SIDEBAR_COLLAPSED_WIDTH = 52

DRAG_THRESHOLD = 5

SORT_OPTIONS = {
    "Eigene Reihenfolge": "priority",
    "Zeitstempel": "time",
    "Inhalt": "content",
    "Gruppe": "group",
    "Favoriten": "favorite"
}
SORT_LABELS = {value: label for label, value in SORT_OPTIONS.items()}   # umgekehrte Richtung

LOAD_DEMO_DATA = False   # beim Starten Demo-Daten laden
APP_VERSION = "1.0.0"

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

def place_near(dialog, parent, width=320, height=180):
    # Dialog mit fester Größe über dem Elternfenster platzieren
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
    dialog.geometry(f"{width}x{height}+{x}+{y}")



class CardView(ctk.CTkScrollableFrame):  #  Kachel-Ansicht
    def __init__(self, master, vm, sidebar):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
        self.sidebar = sidebar
        self.card_items = {}   # Kachel → Eintrag
        self.drag = {"item": None, "start_y": 0, "active": False, "target": None}
        vm.subscribe(self.refresh)   # bei jeder Änderung neu zeichnen

    # Kachel zeichnen

    def refresh(self):
        self.card_items.clear()
        for widget in self.winfo_children():
            widget.destroy()

        items = self.vm.get_visible_items()
        if not items:
            ctk.CTkLabel(self, text=self.vm.empty_text, font=FONT, text_color=MUTED).pack(pady=24)

        for item in items:
            self._create_card(item)

    def _create_card(self, item):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        card.pack(fill="x", padx=4, pady=4)

        # Spaltenaufteilung: nur die Vorschau wächst, rechts feste Breiten
        card.grid_columnconfigure(1, weight=1)
        card.grid_columnconfigure(2, minsize=96)
        card.grid_columnconfigure(3, minsize=96)

        # Spalte 0: farbiger Streifen der Gruppe
        stripe = ctk.CTkFrame(card, width=4, height=1, corner_radius=2,
                              fg_color=self.vm.group_color(item))
        stripe.grid(row=0, column=0, sticky="ns", padx=(6, 0), pady=8)

        # Spalte 1: Vorschau, verlangt keinen eigenen Platz und wird an der Kante abgeschnitten
        preview_label = ctk.CTkLabel(card, text=self.vm.preview(item), font=FONT,
                                     text_color=TEXT, anchor="w", justify="left", width=1)
        preview_label.grid(row=0, column=1, sticky="ew", padx=(12, 16), pady=10)

        # Spalte 2: Uhrzeit über Datum, rechtsbündig
        time_box = ctk.CTkFrame(card, fg_color="transparent")
        time_box.grid(row=0, column=2, sticky="e", padx=(0, 8))

        time_label = ctk.CTkLabel(time_box, text=self.vm.time_text(item), font=FONT_SMALL,
                                  text_color=TEXT, width=88, height=18, anchor="e")
        time_label.pack(anchor="e")
        date_label = ctk.CTkLabel(time_box, text=self.vm.date_text(item), font=FONT_SMALL,
                                  text_color=MUTED, width=88, height=18, anchor="e")
        date_label.pack(anchor="e")

        # Spalte 3: Stern und X über dem Gruppennamen, rechtsbündig
        action_box = ctk.CTkFrame(card, fg_color="transparent")
        action_box.grid(row=0, column=3, sticky="e", padx=(0, 8))

        buttons = ctk.CTkFrame(action_box, fg_color="transparent")
        buttons.pack(anchor="e")

        ctk.CTkButton(
            buttons, text="★" if item.is_favorite else "☆", width=28, height=24,
            fg_color="transparent", hover_color=CARD_HOVER,
            text_color=ACCENT if item.is_favorite else MUTED,
            command=lambda i=item: self.vm.toggle_favorite(i),
        ).pack(side="left")

        ctk.CTkButton(
            buttons, text="✕", width=28, height=24,
            fg_color="transparent", hover_color=CARD_HOVER, text_color=MUTED,
            command=lambda i=item: self.vm.delete(i),
        ).pack(side="left")

        # in Gruppenansichten leer, aber gleich hoch, damit die Kachel nicht springt
        group_text = self.vm.group_name(item, max_length=12) if self.vm.show_group else ""
        group_label = ctk.CTkLabel(action_box, text=group_text, font=FONT_SMALL,
                                   text_color=MUTED, width=96, height=18, anchor="e")
        group_label.pack(anchor="e")

        self.card_items[card] = item

        # Klick, Ziehen und Hover auf allem außer den Buttons
        for widget in (card, stripe, preview_label, time_box, time_label, date_label,
                       action_box, buttons, group_label):
            widget.bind("<ButtonPress-1>", lambda event, i=item: self._on_press(event, i))
            widget.bind("<B1-Motion>", self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>", lambda _event, c=card: c.configure(fg_color=CARD_HOVER))
            widget.bind("<Leave>", lambda _event, c=card: self._on_card_leave(c))

    #  Hover 

    def _on_card_leave(self, card):
        x, y = card.winfo_pointerxy()
        widget = card.winfo_containing(x, y)
        if widget is None or not str(widget).startswith(str(card)):
            card.configure(fg_color=CARD)

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

class TableView(ctk.CTkFrame):  # Tabellen-Ansicht
    def __init__(self, master, vm, sidebar):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
        self.sidebar = sidebar
        self.row_items = {}   # Zeilen-ID → Eintrag
        self.drag = {"item": None, "start_y": 0, "active": False, "target_row": None}

        ttk.Style().theme_use("clam")
        self.tree = ttk.Treeview(
            self, columns=[column[0] for column in COLUMNS],
            show="headings", selectmode="browse",
        )
        for col_id, title, width, _sort_key in COLUMNS:
            self.tree.heading(col_id, text=title,
                              command=lambda c=col_id: self._on_heading_click(c))
            self.tree.column(col_id, width=width, stretch=(col_id == "content"),
                             anchor="w" if col_id == "content" else "center")

        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<ButtonPress-1>", self._on_press)
        self.tree.bind("<B1-Motion>", self._on_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_release)
        self.tree.bind("<Double-1>", self._on_double_click)

        vm.subscribe(self.refresh)

    #  Zeichnen 

    def refresh(self):
        self._apply_style()

        self.tree.configure(displaycolumns=self.vm.visible_columns)

        visible_columns = [column[0] for column in COLUMNS
                           if column[0] != "group" or self.vm.show_group]
        self.tree.configure(displaycolumns=visible_columns)

        self.tree.delete(*self.tree.get_children())
        self.row_items.clear()

        for item in self.vm.get_visible_items():
            values = (
                "☑" if self.vm.is_checked(item) else "☐",
                self.vm.position(item),
                self.vm.preview(item, 80),
                self.vm.group_name(item),
                self.vm.datetime_text(item),
                "★" if item.is_favorite else "☆",
            )
            row_id = self.tree.insert("", "end", values=values)
            self.row_items[row_id] = item

        for col_id, title, _width, sort_key in COLUMNS:
            text = title
            if col_id == "check":
                text = "☑" if self.vm.all_visible_checked else "☐"
            elif sort_key == self.vm.sort_by:
                text += " ▼" if self.vm.descending else " ▲"
            self.tree.heading(col_id, text=text)

    def _apply_style(self):
        dark = ctk.get_appearance_mode() == "Dark"
        bg = "#2b2b2b" if dark else "#ffffff"
        fg = "#f2f2f2" if dark else "#1a1a1a"
        head = "#333333" if dark else "#ebebeb"
        selected = "#33415c" if dark else "#dbe7f6"
        drop = "#4ca0e0" if dark else "#9cc3ec"

        style = ttk.Style()
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg,
                        rowheight=28, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background=head, foreground=fg,
                        relief="flat", font=("Segoe UI Semibold", 10))
        style.map("Treeview", background=[("selected", selected)],
                  foreground=[("selected", fg)])

        self.tree.tag_configure("drop", background=drop)   # Farbe der Ziel-Zeile

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
            self.tree.item(old, tags=())
        if row_id:
            self.tree.item(row_id, tags=("drop",))
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
            self._set_drop_row(self.tree.identify_row(event.y) or None)
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
        if row_id:
            _x, y, _width, height = self.tree.bbox(row_id)
            self.vm.move(item, self.row_items[row_id], after=event.y > y + height / 2)
        elif self.tree.identify_region(event.x, event.y) == "nothing":
            self.vm.move(item, None)

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        if row_id and self._column_id_at(event.x) not in ("check", "favorite"):
            self.vm.copy(self.row_items[row_id])   

class GroupSidebar(ctk.CTkFrame):  # Gruppen-Seitenleiste
    def __init__(self, master, vm):
        super().__init__(master, width=SIDEBAR_EXPANDED_WIDTH, corner_radius=0, fg_color=SIDEBAR)
        self.pack_propagate(False)
        self.vm = vm
        self.collapsed = False
        self.row_groups = {}   # Zeile → Gruppe (None = "Alle Einträge")
        self.highlighted_row = None
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
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

        Tooltip(self.settings_button, "Einstellungen (folgt)")

        # Mitte: scrollbare Liste füllt den Platz dazwischen
        self.list = ctk.CTkScrollableFrame(self, fg_color="transparent")
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
        if widget is None or not str(widget).startswith(str(row)):
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
        ):
            self.vm.remove_group(group)

#  Verknüpfung: Daten, ViewModel, Service


history = ClipboardHistory()   
if LOAD_DEMO_DATA:
    load_demo_data(history)
vm = ClipboardViewModel(history)
service = ClipboardService(vm.receive_text)
vm.service = service

#  Hauptfenster


def refresh_header():
    count_label.configure(text=vm.count_text)
    clear_button.configure(text=vm.clear_button_text)
    direction_button.configure(text="↓" if vm.descending else "↑")
    sort_menu.set(SORT_LABELS[vm.sort_by])
    title_lable.configure(text=vm.title_text)

    count = vm.checked_count
    delete_checked_button.configure(text=f"Markierte löschen ({count})",
                                    state="normal" if count else "disabled")


def on_clear_click():
    count = vm.deletable_count()
    if count == 0:
        messagebox.showinfo("Löschen", "Keine Einträge zum Löschen. Favoriten werden nicht gelöscht.", parent=root)
        return

    text = "1 Eintrag" if count == 1 else f"{count} Einträge"
    if not messagebox.askyesno("Löschen", f"{text} löschen?\nFavoriten bleiben erhalten.", parent=root):
        return

    vm.delete_visible()


def on_search_change(_event):
    vm.set_search(search_entry.get())


def on_sort_change(choice):
    vm.set_sort(SORT_OPTIONS[choice])


def on_favorites_toggle():
    vm.set_favorites_only(favorites_switch.get() == 1)

def on_delete_checked():
        count = vm.checked_count
        text = "1 Eintrag" if count == 1 else f"{count} Einträge"
        if messagebox.askyesno("Markierte löschen", f"{text} endgültig löschen?", parent=root):
            vm.delete_checked()

def on_view_change(choice):
    if choice == "Tabelle":
        card_view.pack_forget()
        card_controls.pack_forget()
        clear_button.pack_forget()

        # versteckten Filter nicht weiterwirken lassen
        if vm.favorites_only:
            favorites_switch.deselect()
            vm.set_favorites_only(False)

        table_controls.pack(side="right")
        table_view.pack(fill="both", expand=True, padx=12, before=hint_label)
        hint_label.configure(text="Doppelklick zum Kopieren · Ziehen zum Sortieren · Spaltenkopf zum Sortieren · ☐ zum Markieren")
    else:
        table_view.pack_forget()
        table_controls.pack_forget()

        card_controls.pack(side="right")
        clear_button.pack(side="right", before=count_label)
        card_view.pack(fill="both", expand=True, padx=12, before=hint_label)
        hint_label.configure(text="Klicken zum Kopieren · Ziehen zum Sortieren (nur in eigener Reihenfolge)")



def poll_incoming():
    vm.process_incoming()
    root.after(100, poll_incoming)



root = ctk.CTk()
root.title(f"Zwischenablagen Manager  {APP_VERSION}")
root.minsize(900, 420)
root.bind("<Control-b>", lambda event: sidebar.toggle_collapsed())

root.geometry("1000x560")

sidebar = GroupSidebar(root, vm)
sidebar.pack(side="left", fill="y")

main_area = ctk.CTkFrame(root, fg_color="transparent")
main_area.pack(side="left", fill="both", expand=True)

# Kopfzeile
header = ctk.CTkFrame(main_area, fg_color="transparent")
header.pack(fill="x", padx=16, pady=(14, 8))

title_lable = ctk.CTkLabel(header, text="", font=FONT_TITLE)
title_lable.pack(side="left")

view_switch = ctk.CTkSegmentedButton(header, values=["Kacheln", "Tabelle"],
                                     font=FONT_SMALL, command=on_view_change)
view_switch.set("Kacheln")
view_switch.pack(side="left", padx=(16, 0))

clear_button = ctk.CTkButton(header, text="Alle löschen", width=130, height=28,
                             font=FONT_SMALL, command=on_clear_click)
clear_button.pack(side="right")

count_label = ctk.CTkLabel(header, text="", font=FONT_SMALL, text_color=MUTED)
count_label.pack(side="right", padx=(0, 10))

# Werkzeugleiste
toolbar = ctk.CTkFrame(main_area, fg_color="transparent")
toolbar.pack(fill="x", padx=16, pady=(0, 8))

search_entry = ctk.CTkEntry(toolbar, placeholder_text="Suchen …", font=FONT_SMALL)
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
search_entry.bind("<KeyRelease>", on_search_change)

# --- nur in der Kachel-Ansicht ---
card_controls = ctk.CTkFrame(toolbar, fg_color="transparent")
card_controls.pack(side="right")

favorites_switch = ctk.CTkSwitch(card_controls, text="Nur Favoriten", font=FONT_SMALL,
                                 command=on_favorites_toggle)
favorites_switch.pack(side="right")

direction_button = ctk.CTkButton(card_controls, text="↑", width=32, height=28,
                                 font=FONT_SMALL, command=vm.toggle_direction)
direction_button.pack(side="right", padx=(0, 12))

sort_menu = ctk.CTkOptionMenu(card_controls, values=list(SORT_OPTIONS), width=160, height=28,
                              font=FONT_SMALL, command=on_sort_change)
sort_menu.pack(side="right", padx=(0, 4))

# --- nur in der Tabellen-Ansicht (noch nicht gepackt) ---
table_controls = ctk.CTkFrame(toolbar, fg_color="transparent")

delete_checked_button = ctk.CTkButton(table_controls, text="Markierte löschen", width=170,
                                      height=28, font=FONT_SMALL, command=on_delete_checked)
delete_checked_button.pack()

# Ansicht
card_view = CardView(main_area, vm, sidebar)
card_view.pack(fill="both", expand=True, padx=12)

table_view = TableView(main_area, vm, sidebar)   # wird erst beim Umschalten angezeigt

hint_label = ctk.CTkLabel(
    main_area, text="Klicken zum Kopieren · Ziehen zum Sortieren (nur in eigener Reihenfolge)",
    font=FONT_SMALL, text_color=MUTED,
    )   
hint_label.pack(fill="x", padx=16, pady=(8, 12))


# Start
vm.subscribe(refresh_header)
card_view.refresh()
table_view.refresh()
refresh_header()
sidebar.refresh()

threading.Thread(target=service.start, daemon=True).start()
root.after(100, poll_incoming)
root.mainloop()