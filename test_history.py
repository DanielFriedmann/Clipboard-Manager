from history import ClipboardHistory


def show(title, items):
    print(f"\n{title}")
    for item in items:
        pin = "📌" if item.is_pinned else "  "
        print(f"  {pin} {item.content:<3} {item.clipboard_group.name}")


h = ClipboardHistory()
arbeit = h.add_group("Arbeit", "#e57373")

# Vier Einträge A–D anlegen
for text in ["D", "C", "B", "A"]:
    h.add_item(text)

# Hilfsfunktion: Eintrag über seinen Text finden
def find(text):
    return next(item for item in h.history if item.content == text)

# A: Arbeit + angeheftet | B: Arbeit | C: angeheftet | D: nichts
h.assign_item_to_group(find("A"), arbeit)
h.assign_item_to_group(find("B"), arbeit)
h.toggle_pinned(find("A"))
h.toggle_pinned(find("C"))

show("Alle:", h.get_history())
show("Nur Arbeit:", h.get_history(arbeit))

# Erwartet: A, C, D bleiben (B war Arbeit und nicht angeheftet)
h.clear_history(arbeit)
show("Nach clear_history(arbeit):", h.get_history())

# Erwartet: A, C bleiben (D war in Allgemein und nicht angeheftet)
h.clear_history()
show("Nach clear_history():", h.get_history())

# Doppelte Gruppe muss einen Fehler werfen
try:
    h.add_group("arbeit")
    print("\nFEHLER: doppelte Gruppe wurde angelegt")
except ValueError as e:
    print(f"\nKorrekt abgelehnt: {e}")