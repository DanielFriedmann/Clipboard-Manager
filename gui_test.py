import tkinter as tk
from history import ClipboardHistory

# Testadaten
history = ClipboardHistory()
history.add_item("Erster Testtext")
history.add_item("Zweiter Testtext")
history.add_item("Dritter Testtext")


# --- Handler: wird aufgerufen, wenn eine Zeile ausgewählt wird ---
def on_select(event):
    selection = listbox.curselection()   # z. B. (1,) oder () wenn nichts ausgewählt
    if not selection:
        return

    index = selection[0]                 # erste (und einzige) ausgewählte Position
    item = history.history[index]        # passender Eintrag aus dem Verlauf
    print(f"Ausgewählt: {item.content}")



root = tk.Tk()
root.title("Zwischenablagen Manager")
root.geometry("400x300")


listbox = tk.Listbox(root)
listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
listbox.bind("<<ListboxSelect>>", on_select)


for item in history.history:
    listbox.insert(tk.END, item.content)

root.mainloop()