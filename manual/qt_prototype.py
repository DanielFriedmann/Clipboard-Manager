# Qt-Oberfläche mit Testdaten, ohne Speicherdienst und ohne Anmeldung
# Aufruf aus dem Projektordner: python -m manual.qt_prototype [Anzahl]

import sys

from PySide6.QtWidgets import QApplication

from manual.make_test_data import build_history
from qt_views.main_window import MainWindow
from settings import DEFAULTS
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

    # eigene Einstellungen, damit die echte settings.json unberührt bleibt
    window = MainWindow(vm, dict(DEFAULTS), f"Qt-Prototyp · {count} Testeinträge")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
