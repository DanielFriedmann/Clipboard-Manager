import threading
from tkinter import messagebox, ttk
import customtkinter as ctk

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

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SMALL = ("Segoe UI", 11)

DRAG_THRESHOLD = 5

SORT_OPTIONS = {
    "Eigene Reihenfolge": "priority",
    "Zeitstempel": "time",
    "Inhalt": "content",
}
SORT_LABELS = {value: label for label, value in SORT_OPTIONS.items()}   # umgekehrte Richtung

# (Spalten-ID, Überschrift, Breite, Sortierung oder None)
COLUMNS = [
    ("check", "☐", 40, None),
    ("position", "Pos.", 50, "priority"),
    ("content", "Inhalt", 380, "content"),
    ("time", "Zeitstempel", 140, "time"),
    ("favorite", "★", 40, None),
]


#  Kachel-Ansicht


class CardView(ctk.CTkScrollableFrame):
    def __init__(self, master, vm):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
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

        ctk.CTkButton(
            card, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=CARD_HOVER, text_color=MUTED,
            command=lambda i=item: self.vm.delete(i),
        ).pack(side="right", padx=(0, 8))

        ctk.CTkButton(
            card, text="★" if item.is_favorite else "☆", width=28, height=28,
            fg_color="transparent", hover_color=CARD_HOVER,
            text_color=ACCENT if item.is_favorite else MUTED,
            command=lambda i=item: self.vm.toggle_favorite(i),
        ).pack(side="right")

        preview_label = ctk.CTkLabel(
            card, text=self.vm.preview(item), font=FONT,
            text_color=TEXT, anchor="w", justify="left",
        )
        preview_label.pack(fill="x", padx=12, pady=(8, 0))

        time_label = ctk.CTkLabel(
            card, text=self.vm.time_text(item), font=FONT_SMALL,
            text_color=MUTED, anchor="w",
        )
        time_label.pack(fill="x", padx=12, pady=(0, 8))

        self.card_items[card] = item

        for widget in (card, preview_label, time_label):
            widget.bind("<ButtonPress-1>", lambda event, i=item: self._on_press(event, i))
            widget.bind("<B1-Motion>", self._on_motion)
            widget.bind("<ButtonRelease-1>", self._on_release)
            widget.bind("<Enter>", lambda event, c=card: c.configure(fg_color=CARD_HOVER))
            widget.bind("<Leave>", lambda event, c=card: self._on_card_leave(c))

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

    def _on_press(self, event, item):
        self.drag.update(item=item, start_y=event.y_root, active=False)

    def _on_motion(self, event):
        if self.drag["item"] is None:
            return

        window = self.winfo_toplevel()
        if not self.drag["active"] and abs(event.y_root - self.drag["start_y"]) > DRAG_THRESHOLD:
            self.drag["active"] = True
            if self.vm.can_drag:
                window.configure(cursor="fleur")

        if self.drag["active"] and self.vm.can_drag:
            self._set_drop_target(self._find_card(window.winfo_containing(event.x_root, event.y_root)))

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
        card = self._find_card(window.winfo_containing(event.x_root, event.y_root))
        self._set_drop_target(None)
        self.drag.update(item=None, active=False, target=None)

        if card is not None:
            middle = card.winfo_rooty() + card.winfo_height() / 2
            self.vm.move(item, self.card_items[card], after=event.y_root > middle)

class TableView(ctk.CTkFrame):
    def __init__(self, master, vm):
        super().__init__(master, fg_color="transparent")
        self.vm = vm
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

        self.tree.delete(*self.tree.get_children())
        self.row_items.clear()

        for item in self.vm.get_visible_items():
            values = (
                "☑" if self.vm.is_checked(item) else "☐",
                self.vm.position(item),
                self.vm.preview(item, 80),
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
        return COLUMNS[index][0]

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
            if self.vm.can_drag:
                self.tree.configure(cursor="fleur")

        if self.drag["active"]:
            if self.vm.can_drag:
                self._set_drop_row(self.tree.identify_row(event.y) or None)
            return "break"   # verhindert, dass die Auswahl beim Ziehen mitwandert

    def _on_release(self, event):
        item = self.drag["item"]
        if item is None:
            return

        was_dragging = self.drag["active"]
        self.tree.configure(cursor="")
        self._set_drop_row(None)
        self._reset_drag()

        if not was_dragging or not self.vm.can_drag:
            return   # einfacher Klick: Kopieren läuft über den Doppelklick

        row_id = self.tree.identify_row(event.y)
        if row_id:
            _x, y, _width, height = self.tree.bbox(row_id)
            self.vm.move(item, self.row_items[row_id], after=event.y > y + height / 2)
        elif self.tree.identify_region(event.x, event.y) == "nothing":
            self.vm.move(item, None)   # unter der letzten Zeile → ans Ende

    def _on_double_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        row_id = self.tree.identify_row(event.y)
        if row_id and self._column_id_at(event.x) not in ("check", "favorite"):
            self.vm.copy(self.row_items[row_id])   

#  Verknüpfung: Daten, ViewModel, Service


history = ClipboardHistory()
vm = ClipboardViewModel(history)
service = ClipboardService(vm.receive_text)
vm.service = service


#  Hauptfenster


def refresh_header():
    count_label.configure(text=vm.count_text)
    clear_button.configure(text=vm.clear_button_text)
    direction_button.configure(text="↓" if vm.descending else "↑")
    sort_menu.set(SORT_LABELS[vm.sort_by])

    count = vm.checked_count
    delete_checked_button.configure(text=f"Markierte löschen ({count})",
                                    state="normal" if count else "disabled")


def on_clear_click():
    count = vm.deletable_count()
    if count == 0:
        messagebox.showinfo("Löschen", "Keine Einträge zum Löschen. Favoriten werden nicht gelöscht.")
        return

    text = "1 Eintrag" if count == 1 else f"{count} Einträge"
    if not messagebox.askyesno("Löschen", f"{text} löschen?\nFavoriten bleiben erhalten."):
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
        if messagebox.askyesno("Markierte löschen", f"{text} endgültig löschen?"):
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
root.title("Zwischenablagen Manager")
root.geometry("820x520")
root.minsize(560, 420)

# Kopfzeile
header = ctk.CTkFrame(root, fg_color="transparent")
header.pack(fill="x", padx=16, pady=(14, 8))

ctk.CTkLabel(header, text="Zwischenablage", font=FONT_TITLE).pack(side="left")

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
toolbar = ctk.CTkFrame(root, fg_color="transparent")
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
card_view = CardView(root, vm)
card_view.pack(fill="both", expand=True, padx=12)

table_view = TableView(root, vm)   # wird erst beim Umschalten angezeigt

hint_label = ctk.CTkLabel(
    root, text="Klicken zum Kopieren · Ziehen zum Sortieren (nur in eigener Reihenfolge)",
    font=FONT_SMALL, text_color=MUTED,
    )   
hint_label.pack(fill="x", padx=16, pady=(8, 12))


# Start
vm.subscribe(refresh_header)
card_view.refresh()
table_view.refresh()
refresh_header()

threading.Thread(target=service.start, daemon=True).start()
root.after(100, poll_incoming)
root.mainloop()