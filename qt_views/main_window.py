from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget)

from . import style
from .card_list import CardListView
from .dialogs import EditDialog
from .sidebar import GroupSidebar
from .toast import Toast

NARROW_BELOW = 740   # unter dieser Fensterbreite schmaler Modus
WIDE_ABOVE = 780     # über dieser Breite wieder breiter Modus
DEFAULT_SIZE = (1000, 600)

SORT_OPTIONS = {
    "Eigene Reihenfolge": "priority",
    "Zeitstempel": "time",
    "Inhalt": "content",
    "Gruppe": "group",
    "Favoriten": "favorite",
}

CARD_HINT = "Klicken zum Kopieren · ↗ öffnet Links"


class MainWindow(QMainWindow):
    # Hauptfenster: Seitenleiste, Kopfzeile, Suche und die Kachelansicht

    closing = Signal()   # vor dem Schließen, z. B. um Einstellungen zu speichern

    def __init__(self, vm, settings, title):
        super().__init__()
        self.vm = vm
        self.settings = settings
        self.narrow = False
        self.auto_collapsed = False   # Seitenleiste wegen schmalem Fenster eingeklappt

        self.setWindowTitle(title)
        self.setMinimumSize(420, 420)
        self.resize(*DEFAULT_SIZE)

        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(f"#central {{ background: {style.color('window').name()}; }}")
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = GroupSidebar(vm)
        self.sidebar.toggle_button.clicked.disconnect()
        self.sidebar.toggle_button.clicked.connect(self.on_sidebar_toggle)
        self.sidebar.settings_button.setEnabled(False)   # Einstellungen folgen in Schritt 5
        outer.addWidget(self.sidebar)

        main = QVBoxLayout()
        main.setContentsMargins(16, 14, 16, 8)
        main.setSpacing(8)
        outer.addLayout(main, 1)

        main.addLayout(self._build_header())
        main.addLayout(self._build_toolbar())

        self.card_view = CardListView(vm, on_edit=self.open_edit_dialog)
        self.card_view.copied.connect(self._on_copied)
        main.addWidget(self.card_view, 1)

        self.hint_label = QLabel(CARD_HINT)
        self.hint_label.setFont(style.font("small"))
        self.hint_label.setStyleSheet(f"color: {style.color('muted').name()};")
        main.addWidget(self.hint_label)

        self.setCentralWidget(central)
        self.toast = Toast(central)

        QShortcut(QKeySequence("Ctrl+B"), self, self.on_sidebar_toggle)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_entry.setFocus)

        vm.subscribe(self.refresh_header)
        self.refresh_header()

    # Aufbau

    def _build_header(self):
        header = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setFont(style.font("title", bold=True))
        header.addWidget(self.title_label)
        header.addSpacing(16)

        # Umschalter Kacheln / Tabelle; die Tabelle kommt in Schritt 3
        self.view_buttons = QButtonGroup(self)
        for index, (name, symbol) in enumerate((("Kacheln", "▤"), ("Tabelle", "▦"))):
            button = QToolButton()
            button.setText(symbol)
            button.setCheckable(True)
            button.setToolTip(name)
            button.setFixedSize(32, 26)
            self.view_buttons.addButton(button, index)
            header.addWidget(button)
        self.view_buttons.button(0).setChecked(True)
        self.view_buttons.button(1).setEnabled(False)
        self.view_buttons.button(1).setToolTip("Tabelle (folgt)")

        header.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setFont(style.font("small"))
        self.count_label.setStyleSheet(f"color: {style.color('muted').name()};")
        header.addWidget(self.count_label)
        header.addSpacing(10)

        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self.on_clear_click)
        header.addWidget(self.clear_button)
        return header

    def _build_toolbar(self):
        toolbar = QHBoxLayout()
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Suchen …  (Strg+F)")
        self.search_entry.setClearButtonEnabled(True)   # kleines X zum Leeren
        self.search_entry.textChanged.connect(self.vm.set_search)
        toolbar.addWidget(self.search_entry, 1)

        self.filter_button = QToolButton()
        self.filter_button.setText("⇅")
        self.filter_button.setToolTip("Sortieren und filtern")
        self.filter_button.setFixedSize(32, 28)
        self.filter_button.setCheckable(True)   # gedrückt dargestellt, solange "Nur Favoriten" aktiv ist
        self.filter_button.clicked.connect(self.open_filter_menu)
        toolbar.addWidget(self.filter_button)
        return toolbar

    # Kopfzeile aktualisieren

    def refresh_header(self):
        vm = self.vm
        if vm.locked:
            self.title_label.setText("")
            self.count_label.setText("")
            return
        title = vm.title_text
        self.title_label.setText(vm.sidebar_name(title, 14) if self.narrow else title)
        self.count_label.setText(vm.count_text)
        self.clear_button.setText("Löschen" if self.narrow else vm.clear_button_text)
        self.filter_button.setChecked(vm.favorites_only)

    # Sortieren und filtern

    def open_filter_menu(self):
        vm = self.vm
        menu = QMenu(self)
        sorts = QActionGroup(menu)   # nur eine Sortierung gleichzeitig
        for label, key in SORT_OPTIONS.items():
            action = menu.addAction(label, lambda k=key: vm.set_sort(k))
            action.setCheckable(True)
            action.setChecked(vm.sort_by == key)
            sorts.addAction(action)
        menu.addSeparator()
        descending = menu.addAction("Absteigend", vm.toggle_direction)
        descending.setCheckable(True)
        descending.setChecked(vm.descending)
        favorites = menu.addAction("Nur Favoriten", lambda: vm.set_favorites_only(not vm.favorites_only))
        favorites.setCheckable(True)
        favorites.setChecked(vm.favorites_only)

        # direkt unter dem Knopf öffnen
        menu.exec(self.filter_button.mapToGlobal(self.filter_button.rect().bottomLeft()))
        self.filter_button.setChecked(vm.favorites_only)

    # Löschen

    def on_clear_click(self):
        count = self.vm.deletable_count()
        if count == 0:
            QMessageBox.information(self, "Löschen", "Keine Einträge zum Löschen. Favoriten werden nicht gelöscht.")
            return
        text = self.vm.entries_text(count)
        answer = QMessageBox.question(self, "Löschen", f"{text} löschen?\nFavoriten bleiben erhalten.")
        if answer == QMessageBox.StandardButton.Yes and not self.vm.locked:
            self.vm.delete_visible()

    # Kopieren und Benennen

    def _on_copied(self, item):
        self.toast.show_message("Passwort kopiert" if item.is_password else "In die Zwischenablage kopiert")

    def copy_detail(self, text, label):
        # Benutzername oder Adresse aus dem Dialog
        self.vm.copy_text(text)
        self.toast.show_message(f"{label} kopiert")

    def open_edit_dialog(self, item):
        content = self.vm.item_content(item) if item.is_password else None
        dialog = EditDialog(self, item,
                            on_save=lambda title, username, url: self.vm.rename(item, title, username, url),
                            on_copy=self.copy_detail, content=content)
        dialog.open()   # modal, aber ohne die Ereignisschleife anzuhalten

    # Schmaler und breiter Modus

    def on_sidebar_toggle(self):
        # von Hand umgeschaltet: der automatische Zustand gilt nicht mehr
        self.auto_collapsed = False
        self.sidebar.toggle_collapsed()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.width()
        if not self.narrow and width < NARROW_BELOW:
            self._apply_layout(True)
        elif self.narrow and width > WIDE_ABOVE:
            self._apply_layout(False)

    def _apply_layout(self, narrow):
        self.narrow = narrow
        if narrow and not self.sidebar.collapsed:
            self.sidebar.toggle_collapsed()
            self.auto_collapsed = True
        elif not narrow and self.auto_collapsed:
            if self.sidebar.collapsed:
                self.sidebar.toggle_collapsed()
            self.auto_collapsed = False
        self.count_label.setVisible(not narrow)
        self.hint_label.setVisible(not narrow)
        self.refresh_header()

    # Fensterzustand

    def restore_state(self):
        geometry = self.settings.get("qt_geometry")
        if geometry:
            # Qt prüft selbst, ob die Position noch auf einem Bildschirm liegt
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        if self.settings.get("sidebar_collapsed") and not self.sidebar.collapsed:
            self.sidebar.toggle_collapsed()

    def save_state(self):
        self.settings["qt_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings["sidebar_collapsed"] = self.sidebar.collapsed and not self.auto_collapsed
        self.settings["view"] = "Kacheln"
        self.settings["selected_group"] = self.vm.selected_group_id

    def closeEvent(self, event):
        self.save_state()
        self.closing.emit()
        super().closeEvent(event)
