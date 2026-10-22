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
vm.assign_items_to_group([vm.get_visible_items()[0]], arbeit)

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

from datetime import datetime, timedelta

vm.set_search("")
vm.set_favorites_only(False)
vm.select_group(None)

item = vm.get_visible_items()[0]
print(vm.date_text(item), "   (erwartet: Heute)")

item.created_at = datetime.now() - timedelta(days=1)
print(vm.date_text(item), "   (erwartet: Gestern)")

item.created_at = datetime(2026, 1, 15, 9, 30)
print(vm.date_text(item), "   (erwartet: 15.01.2026)")

print(vm.group_name(item), "/", vm.group_color(item), "   (erwartet: Unsortiert / #9e9e9e)")
print(vm.show_group, "   (erwartet: True)")

vm.select_group(vm.default_group)
print(vm.show_group, "   (erwartet: False)")

long_group = vm.add_group("Kundenprojekte Süd", "#e57373")
vm.assign_items_to_group([item], long_group)
print(vm.group_name(item, max_length=12), "   (erwartet: Kundenproje…)")

vm.select_group(None)
privat = vm.add_group("Privat", "#81c784")
first = vm.get_visible_items()[0]
vm.assign_items_to_group([first], privat)

vm.set_sort("group")
print([vm.group_name(item) for item in vm.get_visible_items()])
print("   (erwartet: alphabetisch, z. B. Kundenprojekte Süd, Privat, Unsortiert …)")

vm.toggle_direction()
print([vm.group_name(item) for item in vm.get_visible_items()])
print("   (erwartet: dieselbe Liste umgekehrt)")