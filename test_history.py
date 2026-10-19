from history import ClipboardHistory

def build():
    h = ClipboardHistory()
    for text in ["D", "C", "B", "A"]:   # ergibt A B C D
        h.add_item(text)
    return h

def order(h):
    return " ".join(item.content for item in h.history)

def find(h, text):
    return next(item for item in h.history if item.content == text)


h = build(); h.move_item(find(h, "A"), find(h, "D"))
print(f"A vor D:     {order(h)}   (erwartet: B C A D)")

h = build(); h.move_item(find(h, "D"), find(h, "A"))
print(f"D vor A:     {order(h)}   (erwartet: D A B C)")

h = build(); h.move_item(find(h, "B"), None)
print(f"B ans Ende:  {order(h)}   (erwartet: A C D B)")

h = build(); h.move_item(find(h, "A"), find(h, "A"))
print(f"A vor A:     {order(h)}   (erwartet: A B C D)")

h = build(); arbeit = h.add_group("Arbeit")
h.assign_item_to_group(find(h, "C"), arbeit)
print(f"C → Arbeit:  {order(h)}   (erwartet: C A B D)")