import queue
import threading
import customtkinter as ctk

from clipboard_service import ClipboardService
from history import ClipboardHistory
from tkinter import messagebox


ctk.set_appearance_mode("system")      # folgt der Windows Darstellung
ctk.set_default_color_theme("blue")


CARD = ("#ffffff", "#2b2b2b")
CARD_HOVER = ("#e8f0fb", "#3a3a3a")
TEXT = ("#1a1a1a", "#f2f2f2")
MUTED = ("#6b6b6b", "#a0a0a0")
ACCENT = ("#0067c0", "#4ca0e0")

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 18)
FONT_SMALL = ("Segoe UI", 11)

PREVIEW_LENGTH = 60
DRAG_THRESHOLD = 5 

SORT_OPTIONS = {
    "Eigene Reihenfolge": "priority",
    "Zeitstempel": "time",
    "Inhalt": "content"
}


history = ClipboardHistory()
text_queue = queue.Queue()   # threadsichere Übergabe Service → GUI
card_items = {} 
drag = {"item": None, "start_y": 0, "active": False, "target": None} # Wichtiges Dicitonary
view = {"sort_by": "priority", "descending": False, "search": "", "favorites_only": False} # Wichtiges Dicitonary


def on_new_text(text):
    
    text_queue.put(text)


service = ClipboardService(on_new_text)



def make_preview(text, max_length=PREVIEW_LENGTH):
    preview = " ".join(text.split())
    if len(preview) > max_length:
        preview = preview[:max_length - 1] + "…"
    return preview

def on_card_click(item):
    service.set_text(item.content)

def on_delete_click(item):
    history.remove_item(item)
    refresh_cards()

def on_pin_click(item):
    history.toggle_favorite(item)
    refresh_cards()

def on_clear_click():
    items = get_visible_items()
    count = len([item for item in items if not item.is_favorite])

    if count == 0:
        messagebox.showinfo("Löschen", "Keine Einträge zum Löschen. Favoriten werden nicht gelöscht.")
        return

    text = "1 Eintrag" if count == 1 else f"{count} Einträge"
    if not messagebox.askyesno("Löschen", f"{text} löschen?\nFavoriten bleiben erhalten."):
        return

    history.clear_items(items)
    refresh_cards()

def get_visible_items():
    return history.get_history(
        sort_by=view["sort_by"],
        descending=view["descending"],
        search=view["search"],
        favorites_only=view["favorites_only"],
    )

def on_card_leave(card):
  
    x, y = card.winfo_pointerxy()
    widget = card.winfo_containing(x, y)
    if widget is None or not str(widget).startswith(str(card)):
        card.configure(fg_color=CARD)

def find_card(widget):
    
    while widget is not None:
        if widget in card_items:
            return widget
        widget = widget.master
    return None

def set_drop_target(card):
    
    old = drag["target"]
    if old is card:
        return
    if old is not None and old.winfo_exists():
        old.configure(border_width=0)
    if card is not None:
        card.configure(border_width=2, border_color=ACCENT)
    drag["target"] = card

def on_press(event, item):
    drag["item"] = item
    drag["start_y"] = event.y_root
    drag["active"] = False

def on_release(event):
    item = drag["item"]
    if item is None:
        return

    if drag["active"]:
        root.configure(cursor="")
        card = find_card(root.winfo_containing(event.x_root, event.y_root))
        if card is not None and drag_allowed():
            target = card_items[card]            
            middle = card.winfo_rooty() + card.winfo_height() / 2
            history.move_item(item, target, after=event.y_root > middle)
        drag.update(item=None, active=False, target=None)
        refresh_cards()
    else:
        drag.update(item=None, active=False, target=None)
        on_card_click(item)

def drag_allowed():
    return view["sort_by"] == "priority" and not view["descending"]

def on_search_change(event):
    view["search"] = search_entry.get()
    refresh_cards()

def on_sort_change(choice):
    view["sort_by"] = SORT_OPTIONS[choice]
    refresh_cards()

def on_direction_click():
    view["descending"] = not view["descending"]
    direction_button.configure(text="↓" if view["descending"] else "↑")
    refresh_cards()

def on_favorites_toggle():
    view["favorites_only"] = favorites_switch.get() == 1
    refresh_cards()

def on_motion(event):
    if drag["item"] is None:
        return

    if not drag["active"] and abs(event.y_root - drag["start_y"]) > DRAG_THRESHOLD:
        drag["active"] = True
        root.configure(cursor="fleur")   # Verschiebe-Mauszeiger

    if drag["active"] and drag_allowed():
        widget = root.winfo_containing(event.x_root, event.y_root)
        set_drop_target(find_card(widget))

    if drag_allowed():
        root.configure(cursor="fleur")

def create_card(item):
    card = ctk.CTkFrame(list_frame, fg_color=CARD, corner_radius=8)
    card.pack(fill="x", padx=4, pady=4)

    # Delete button

    delete_button = ctk.CTkButton(
        card,
        text="✕",
        width=28,
        height=28,
        fg_color="transparent",
        hover_color=CARD_HOVER,
        text_color=MUTED,
        command=lambda i=item: on_delete_click(i),
        )
    delete_button.pack(side="right", padx=(0, 8))

    # Pin button

    pin_button = ctk.CTkButton(
        card,
        text="★" if item.is_favorite else "☆",
        width=28,
        height=28,
        fg_color="transparent",
        hover_color=CARD_HOVER,
        text_color=ACCENT if item.is_favorite else MUTED,
        command=lambda i=item: on_pin_click(i),
        )
    pin_button.pack(side="right")

    #Entry Preview

    preview_label = ctk.CTkLabel(
        card, text=make_preview(item.content), font=FONT,
        text_color=TEXT, anchor="w", justify="left",
    )
    preview_label.pack(fill="x", padx=12, pady=(8, 0))

    # Entry Timestamp

    time_label = ctk.CTkLabel(
        card, text=item.created_at.strftime("%H:%M"), font=FONT_SMALL,
        text_color=MUTED, anchor="w",
    )
    time_label.pack(fill="x", padx=12, pady=(0, 8))

    
    card_items[card] = item

    for widget in (card, preview_label, time_label):
        widget.bind("<ButtonPress-1>", lambda event, i=item: on_press(event, i))
        widget.bind("<B1-Motion>", on_motion)
        widget.bind("<ButtonRelease-1>", on_release)
        widget.bind("<Enter>", lambda event, c=card: c.configure(fg_color=CARD_HOVER))
        widget.bind("<Leave>", lambda event, c=card: on_card_leave(c))

def refresh_cards():
    card_items.clear()
    for widget in list_frame.winfo_children():
        widget.destroy()

    items = history.get_history(
        sort_by=view["sort_by"],
        descending=view["descending"],
        search=view["search"],
        favorites_only=view["favorites_only"],
    )

    if not items:
        filtering = view["search"] or view["favorites_only"]
        text = "Keine Treffer" if filtering else "Noch nichts kopiert"
        ctk.CTkLabel(list_frame, text=text, font=FONT, text_color=MUTED).pack(pady=24)

    for item in items:
        create_card(item)

    count = len(items)
    count_label.configure(text=f"{count} Eintrag" if count == 1 else f"{count} Einträge")

def check_queue():
    changed = False
    while not text_queue.empty():
        history.add_item(text_queue.get())
        changed = True

    if changed:
        refresh_cards()

    root.after(100, check_queue)


root = ctk.CTk()
root.title("Zwischenablagen Manager")
root.geometry("820x520")
root.minsize(420, 420)


header = ctk.CTkFrame(root, fg_color="transparent")
header.pack(fill="x", padx=16, pady=(14, 8))

ctk.CTkLabel(header, text="Zwischenablage", font=FONT_TITLE).pack(side="left")

clear_button = ctk.CTkButton(
    header,
    text="Alle löschen",
    width=90,
    height=28,
    font=FONT_SMALL,
    command=on_clear_click,
)
clear_button.pack(side="right")

count_label = ctk.CTkLabel(header, text="0 Einträge", font=FONT_SMALL, text_color=MUTED)
count_label.pack(side="right", padx=(0, 10))

toolbar = ctk.CTkFrame(root, fg_color="transparent")
toolbar.pack(fill="x", padx=16, pady=(0, 8))

search_entry = ctk.CTkEntry(toolbar, placeholder_text="Suchen …", font=FONT_SMALL)
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
search_entry.bind("<KeyRelease>", on_search_change)

favorites_switch = ctk.CTkSwitch(toolbar, text="Nur Favoriten", font=FONT_SMALL,
                                 command=on_favorites_toggle)
favorites_switch.pack(side="right")

direction_button = ctk.CTkButton(toolbar, text="↑", width=32, height=28,
                                 font=FONT_SMALL, command=on_direction_click)
direction_button.pack(side="right", padx=(0, 12))

sort_menu = ctk.CTkOptionMenu(toolbar, values=list(SORT_OPTIONS), width=160, height=28,
                              font=FONT_SMALL, command=on_sort_change)
sort_menu.pack(side="right", padx=(0, 4))



list_frame = ctk.CTkScrollableFrame(root, fg_color="transparent")
list_frame.pack(fill="both", expand=True, padx=12)


ctk.CTkLabel(
    root, text="Eintrag anklicken, um ihn erneut in die Zwischenablage zu legen",
    font=FONT_SMALL, text_color=MUTED,
).pack(fill="x", padx=16, pady=(8, 12))


refresh_cards()
threading.Thread(target=service.start, daemon=True).start()
root.after(100, check_queue)
root.mainloop()