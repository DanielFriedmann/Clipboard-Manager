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