from PySide6.QtCore import QByteArray, Qt, Signal
from PySide6.QtGui import QActionGroup, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QMessageBox, QPushButton, QStackedWidget, QToolButton, QToolTip,
                               QVBoxLayout, QWidget)

from . import style
from .card_list import CardListView
from .dialogs import EditDialog
from .item_menu import show_item_menu
from .sidebar import GroupSidebar
from .table_view import ItemTableView
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

VIEWS = ("Kacheln", "Tabelle")
HINTS = {
    "Kacheln": "Klicken zum Kopieren · Ziehen zum Sortieren oder in eine Gruppe · Rechtsklick für mehr",
    "Tabelle": "Doppelklick zum Kopieren · ☐ zum Markieren · Spaltenkopf zum Sortieren · Rechtsklick für mehr",
}


class MainWindow(QMainWindow):
    # Hauptfenster: Seitenleiste, Kopfzeile, Suche und die Kachelansicht

    closing = Signal()          # vor dem Schließen, z. B. um Einstellungen zu speichern
    lock_requested = Signal()   # Strg+L
    settings_requested = Signal()   # Zahnrad

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
        self.sidebar.settings_button.clicked.connect(self.settings_requested.emit)
        outer.addWidget(self.sidebar)

        main = QVBoxLayout()
        main.setContentsMargins(16, 14, 16, 8)
        main.setSpacing(8)
        outer.addLayout(main, 1)

        main.addLayout(self._build_header())
        main.addLayout(self._build_toolbar())

        # Ansichten: Kacheln und Tabelle zeigen dieselben Einträge
        self.card_view = CardListView(vm, on_edit=self.open_edit_dialog)
        self.table_view = ItemTableView(vm)
        self.stack = QStackedWidget()
        for view in (self.card_view, self.table_view):
            view.copied.connect(self._on_copied)
            view.menu_requested.connect(self.open_item_menu)
            self.stack.addWidget(view)
        main.addWidget(self.stack, 1)

        self.hint_label = QLabel()
        self.hint_label.setFont(style.font("small"))
        self.hint_label.setStyleSheet(f"color: {style.color('muted').name()};")
        main.addWidget(self.hint_label)

        # oben drüber: Inhalt oder Anmeldeseite
        self.pages = QStackedWidget()
        self.pages.addWidget(central)
        self.login_view = None
        self.setCentralWidget(self.pages)
        self.toast = Toast(central)

        QShortcut(QKeySequence("Ctrl+B"), self, self.on_sidebar_toggle)
        QShortcut(QKeySequence("Ctrl+F"), self, self.search_entry.setFocus)
        # auch in offenen Dialogen: Strg+L sperrt die ganze App
        lock = QShortcut(QKeySequence("Ctrl+L"), self, self.lock_requested.emit)
        lock.setContext(Qt.ShortcutContext.ApplicationShortcut)

        vm.subscribe(self.refresh_header)
        self.set_view("Kacheln")

    # Aufbau

    def _build_header(self):
        header = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setFont(style.font("title", bold=True))
        header.addWidget(self.title_label)
        header.addSpacing(16)

        # Umschalter Kacheln / Tabelle
        self.view_buttons = QButtonGroup(self)
        for index, (name, symbol) in enumerate(zip(VIEWS, ("\uE8A9", "\uE8FD"))):
            button = QToolButton()
            button.setText(symbol)
            button.setFont(style.font("normal", family=style.ICON_FAMILY))   # Windows-Symbolschrift
            button.setCheckable(True)
            button.setToolTip(name)
            button.setFixedSize(32, 26)
            self.view_buttons.addButton(button, index)
            header.addWidget(button)
        self.view_buttons.idClicked.connect(lambda index: self.set_view(VIEWS[index]))

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

        # nur in der Tabelle sichtbar
        self.delete_checked_button = QPushButton()
        self.delete_checked_button.clicked.connect(self.on_delete_checked)
        toolbar.insertWidget(1, self.delete_checked_button)
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

        count = vm.checked_count
        self.delete_checked_button.setText(f"Löschen ({count})" if self.narrow
                                           else f"Markierte löschen ({count})")
        self.delete_checked_button.setEnabled(count > 0)

    # Ansicht wechseln

    def set_view(self, name):
        self.current_view = name
        index = VIEWS.index(name)
        self.view_buttons.button(index).setChecked(True)
        self.stack.setCurrentIndex(index)
        table = name == "Tabelle"
        self.delete_checked_button.setVisible(table)
        self.clear_button.setVisible(not table)
        self.hint_label.setText(HINTS[name])
        self.refresh_header()

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

    def on_delete_checked(self):
        text = self.vm.entries_text(self.vm.checked_count)
        answer = QMessageBox.question(self, "Markierte löschen", f"{text} endgültig löschen?")
        if answer == QMessageBox.StandardButton.Yes and not self.vm.locked:
            self.vm.delete_checked()

    # Kopieren und Benennen

    def _on_copied(self, item):
        self.show_copied("Passwort" if item.is_password else "Eintrag")

    def show_copied(self, label):
        # Rückmeldung nach jedem Kopieren
        self.toast.show_message("In die Zwischenablage kopiert" if label == "Eintrag" else f"{label} kopiert")

    def copy_detail(self, text, label, sensitive=False):
        # Benutzername, Adresse oder Passwort aus dem Dialog
        self.vm.copy_text(text, sensitive=sensitive)
        self.show_copied(label)

    def open_item_menu(self, item, global_pos):
        show_item_menu(self, global_pos, self.vm, item, self.open_edit_dialog, self.show_copied)

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
        self.table_view.set_compact(narrow)
        self.refresh_header()

    # Fensterzustand

    def restore_state(self):
        geometry = self.settings.get("qt_geometry")
        if geometry:
            # Qt prüft selbst, ob die Position noch auf einem Bildschirm liegt
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        if self.settings.get("sidebar_collapsed") and not self.sidebar.collapsed:
            self.sidebar.toggle_collapsed()
        if self.settings.get("view") in VIEWS:
            self.set_view(self.settings["view"])

    def save_state(self):
        self.settings["qt_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings["sidebar_collapsed"] = self.sidebar.collapsed and not self.auto_collapsed
        self.settings["view"] = self.current_view
        self.settings["selected_group"] = self.vm.selected_group_id

    # Anmelden und Sperren

    def show_login(self, login_view):
        # Anmeldeseite ersetzt den ganzen Fensterinhalt
        self.hide_login()
        self.login_view = login_view
        self.pages.addWidget(login_view)
        self.pages.setCurrentWidget(login_view)

    def hide_login(self):
        if self.login_view is not None:
            self.pages.removeWidget(self.login_view)
            self.login_view.hide()
            self.login_view.deleteLater()   # erst nach dem laufenden Klick löschen
            self.login_view = None
        self.pages.setCurrentIndex(0)

    def prepare_lock(self):
        # alles schließen, was Klartext zeigen könnte: Menüs, Dialoge, Tooltip, Suche
        QToolTip.hideText()
        popup = QApplication.activePopupWidget()
        while popup is not None:
            popup.close()
            popup = QApplication.activePopupWidget()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog) and widget.isVisible():
                widget.reject()
        self.search_entry.blockSignals(True)   # Leeren soll keine neue Suche auslösen
        self.search_entry.clear()
        self.search_entry.blockSignals(False)
        self.toast.hide()

    def closeEvent(self, event):
        self.save_state()
        self.closing.emit()
        super().closeEvent(event)
