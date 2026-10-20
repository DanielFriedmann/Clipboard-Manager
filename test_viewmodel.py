from history import ClipboardHistory
from viewmodel import ClipboardViewModel

vm = ClipboardViewModel(ClipboardHistory())

calls = []
vm.subscribe(lambda: calls.append("geändert"))

for text in ["Rechnung März", "Hallo Welt", "Rechnung April"]:
    vm.receive_text(text)
vm.process_incoming()

print(vm.count_text, "   (erwartet: 3 Einträge)")
print(len(calls), "Benachrichtigung   (erwartet: 1)")

vm.set_search("rechnung")
print(vm.count_text, "   (erwartet: 2 Einträge)")
print(vm.clear_button_text, "   (erwartet: Angezeigte löschen)")

vm.set_sort("time")
print(vm.can_drag, "   (erwartet: False)")

vm.set_favorites_only(True)
print(vm.empty_text, "/", vm.count_text, "   (erwartet: Keine Treffer / 0 Einträge)")

vm.set_search("")
vm.set_sort("priority")
vm.set_favorites_only(False)

arbeit = vm.add_group("Arbeit", "#e57373")
vm.assign_to_group(vm.get_visible_items()[0], arbeit)

vm.select_group(arbeit)
print(vm.title_text, vm.count_text, "   (erwartet: Arbeit 1 Eintrag)")
print(vm.clear_button_text, "   (erwartet: Angezeigte löschen)")

print(vm.group_count(None), vm.group_count(vm.default_group), vm.group_count(arbeit),
      "   (erwartet: 3 2 1)")

try:
    vm.add_group("  ", "#000000")
except ValueError as e:
    print("Korrekt abgelehnt:", e)

vm.remove_group(arbeit)
print(vm.title_text, "   (erwartet: Alle Einträge)")