# Prototyp der Qt-Kachelliste mit Testdaten, ohne Speicherdienst und ohne Anmeldung
# Aufruf aus dem Projektordner: python -m manual.qt_prototype [Anzahl]

import sys

from PySide6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QLineEdit,
                               QMainWindow, QVBoxLayout, QWidget)

from manual.make_test_data import build_history
from qt_views.card_list import CardListView
from viewmodel import ClipboardViewModel


class FakeService:
    # ersetzt den ClipboardService: zeigt nur, was kopiert würde
    def set_text(self, text, sensitive=False):
        print(f"Kopiert: {'••••••••' if sensitive else text[:40]!r}")


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    app = QApplication(sys.argv)

    vm = ClipboardViewModel(build_history(count))
    vm.service = FakeService()

    window = QMainWindow()
    window.setWindowTitle(f"Qt-Prototyp · {count} Testeinträge")
    window.resize(1000, 600)

    central = QWidget()
    layout = QVBoxLayout(central)
    layout.setContentsMargins(12, 12, 12, 12)

    # Kopfzeile zum Ausprobieren: Gruppe wechseln, suchen, Anzahl
    top = QHBoxLayout()
    groups = QComboBox()
    groups.addItem("Alle Einträge", None)
    for group in vm.history.list_groups():
        groups.addItem(group.name, group)
    groups.currentIndexChanged.connect(lambda _i: vm.select_group(groups.currentData()))
    search = QLineEdit()
    search.setPlaceholderText("Suchen …")
    search.textChanged.connect(vm.set_search)
    counter = QLabel()
    vm.subscribe(lambda: counter.setText(f"{len(vm.get_visible_items())} von {vm.count_text}"))
    top.addWidget(groups)
    top.addWidget(search, 1)
    top.addWidget(counter)
    layout.addLayout(top)

    cards = CardListView(vm, on_edit=lambda item: print(f"Benennen: {vm.display_text(item)}"))
    layout.addWidget(cards, 1)

    window.setCentralWidget(central)
    vm._notify()   # Zähler einmal füllen
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
