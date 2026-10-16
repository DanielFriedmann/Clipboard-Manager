import queue
import threading
import tkinter as tk

from clipboard_service import ClipboardService
from history import ClipboardHistory

# --- Daten und Service ---
history = ClipboardHistory()
text_queue = queue.Queue()   # threadsichere Übergabe Service → GUI


def on_new_text(text):
    # ACHTUNG: läuft im Service-Thread, deshalb nur in die Queue legen
    text_queue.put(text)


service = ClipboardService(on_new_text)


# --- GUI-Funktionen (laufen alle im GUI-Thread) ---
def refresh_listbox():
    listbox.delete(0, tk.END)
    for item in history.history:
        listbox.insert(tk.END, item.content)


def check_queue():
    changed = False
    while not text_queue.empty():
        history.add_item(text_queue.get())
        changed = True

    if changed:
        refresh_listbox()

    root.after(100, check_queue)   # sich selbst in 100 ms erneut einplanen


def on_select(event):
    selection = listbox.curselection()
    if not selection:
        return
    item = history.history[selection[0]]
    service.set_text(item.content)


# --- Fenster ---
root = tk.Tk()
root.title("Zwischenablagen Manager")
root.geometry("400x300")

listbox = tk.Listbox(root)
listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
listbox.bind("<<ListboxSelect>>", on_select)

# --- Start ---
threading.Thread(target=service.start, daemon=True).start()
root.after(100, check_queue)
root.mainloop()