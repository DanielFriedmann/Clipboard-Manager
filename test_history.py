from history import ClipboardHistory

# Testdaten
h = ClipboardHistory()
h.add_item("A")
h.add_item("B")
h.add_item("C")
h.add_item("A") 

print("Nach dem Hinzufügen:")
h.print_history()

# Löschen testen
item_to_remove = h.history[1]     # zweiter Eintrag von oben
print(f"\nEntferne: {item_to_remove.content}")
h.remove_item(item_to_remove)

print("\nNach dem Löschen:")
h.print_history()