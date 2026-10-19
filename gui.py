import queue
import threading
import customtkinter as ctk

from clipboard_service import ClipboardService
from history import ClipboardHistory


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


history = ClipboardHistory()
text_queue = queue.Queue()   # threadsichere Übergabe Service → GUI


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
    history.clear_history()
    refresh_cards()

def on_card_leave(card):
  
    x, y = card.winfo_pointerxy()
    widget = card.winfo_containing(x, y)
    if widget is None or not str(widget).startswith(str(card)):
        card.configure(fg_color=CARD)


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

    
    for widget in (card, preview_label, time_label):
        widget.bind("<Button-1>", lambda event, i=item: on_card_click(i))
        widget.bind("<Enter>", lambda event, c=card: c.configure(fg_color=CARD_HOVER))
        widget.bind("<Leave>", lambda event, c=card: on_card_leave(c))


def refresh_cards():
    
    for widget in list_frame.winfo_children():
        widget.destroy()

    if not history.history:
        ctk.CTkLabel(list_frame, text="Noch nichts kopiert", font=FONT, text_color=MUTED).pack(pady=24)

    for item in history.get_history():
        create_card(item)

    count = len(history.history)
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