from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout)

from vault import MIN_PASSWORD_LENGTH

from . import style
from .security import check_new_password

LOCK_CHOICES = [
    (5, "5 Minuten"),
    (15, "15 Minuten"),
    (30, "30 Minuten"),
    (60, "60 Minuten"),
    (0, "Nie"),
]
CONTROL_WIDTH = 160   # gleiche Breite für alle Bedienelemente rechts
TEXT_WIDTH = 340      # Textbreite in den kleinen Dialogen
ERROR_COLOR = ("#c62828", "#ef9a9a")
SUCCESS_COLOR = ("#2e7d32", "#a5d6a7")


def _busy(busy):
    # Scrypt braucht einen Moment, Sanduhr zeigen
    if busy:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
    else:
        QApplication.restoreOverrideCursor()


def _colored(label, colors):
    label.setStyleSheet(f"color: {colors[1] if style.is_dark() else colors[0]};")


class SettingsDialog(QDialog):
    # Einstellungen; jede Änderung gilt sofort, ohne Speichern-Knopf

    def __init__(self, parent, settings, on_change, on_lock_now, version,
                 on_change_password=None, on_new_recovery=None):
        super().__init__(parent)
        self.settings = settings
        self.on_change = on_change              # on_change(key, value) speichert sofort
        self.on_lock_now = on_lock_now
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        self.grid = QGridLayout()
        self.grid.setColumnStretch(0, 1)
        self.grid.setVerticalSpacing(8)
        self._row = 0
        layout.addLayout(self.grid)

        # Sperren
        self._section("Sperren")
        self.lock_box = QComboBox()
        for minutes, label in LOCK_CHOICES:
            self.lock_box.addItem(label, minutes)
        current = settings.get("lock_minutes", 15)
        index = self.lock_box.findData(current)
        if index < 0:
            # Wert von Hand in settings.json gesetzt: trotzdem anzeigen
            self.lock_box.addItem(f"{current} Minuten", current)
            index = self.lock_box.count() - 1
        self.lock_box.setCurrentIndex(index)
        self.lock_box.currentIndexChanged.connect(
            lambda _i: self.on_change("lock_minutes", self.lock_box.currentData()))
        self._setting_row("Automatisch sperren nach", self.lock_box)

        self.windows_box = QCheckBox()
        self.windows_box.setChecked(settings.get("lock_on_windows_lock", True))
        self.windows_box.toggled.connect(lambda value: self.on_change("lock_on_windows_lock", value))
        self._setting_row("Mit Windows sperren (Win+L)", self.windows_box)

        # Sicherheit
        self._section("Sicherheit")
        self._setting_row("Passwort", self._action_button("Ändern …", on_change_password))
        self._setting_row("Wiederherstellungsschlüssel",
                          self._action_button("Neu erzeugen …", on_new_recovery))

        # Fußzeile
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addSpacing(16)
        layout.addWidget(line)
        footer = QHBoxLayout()
        version_label = QLabel(f"Version {version}")
        version_label.setFont(style.font("small"))
        _colored(version_label, style.COLORS["muted"])
        footer.addWidget(version_label)
        footer.addStretch(1)
        lock_button = QPushButton("Jetzt sperren")
        lock_button.setAutoDefault(False)
        lock_button.setFixedWidth(CONTROL_WIDTH)
        lock_button.clicked.connect(self._lock_now)
        footer.addWidget(lock_button)
        layout.addLayout(footer)

    # Bausteine

    def _section(self, text):
        label = QLabel(text)
        label.setFont(style.font("section", bold=True))
        if self._row:
            self.grid.setRowMinimumHeight(self._row, 16)   # Abstand vor der neuen Gruppe
            self._row += 1
        self.grid.addWidget(label, self._row, 0, 1, 2)
        self._row += 1

    def _setting_row(self, text, widget):
        self.grid.addWidget(QLabel(text), self._row, 0)
        if not isinstance(widget, QCheckBox):
            widget.setFixedWidth(CONTROL_WIDTH)
        self.grid.addWidget(widget, self._row, 1, Qt.AlignmentFlag.AlignRight)
        self._row += 1

    def _action_button(self, text, callback):
        button = QPushButton(text)
        button.setAutoDefault(False)
        if callback is None:
            button.setEnabled(False)
        else:
            button.clicked.connect(lambda: callback(self))   # Dialog als Elternteil für Unterdialoge
        return button

    def _lock_now(self):
        self.accept()
        self.on_lock_now()


class _SecurityDialog(QDialog):
    # Grundgerüst für die kleinen Dialoge über den Einstellungen

    def __init__(self, parent, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(TEXT_WIDTH + 40)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 16, 20, 16)
        self.body.setSpacing(6)

    def _clear(self):
        while self.body.count():
            item = self.body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
            elif item.layout() is not None:
                while item.layout().count():
                    child = item.layout().takeAt(0).widget()
                    if child is not None:
                        child.hide()
                        child.deleteLater()

    def _text(self, text, font=None, colors=None):
        label = QLabel(text)
        label.setWordWrap(True)
        if font is not None:
            label.setFont(font)
        _colored(label, colors or style.COLORS["muted"])
        # umbrochener Text: Höhe selbst festlegen, sonst wird er nach dem Seitenwechsel abgeschnitten
        label.setMinimumHeight(label.heightForWidth(TEXT_WIDTH))
        self.body.addWidget(label)
        return label

    def _password_field(self, label):
        caption = QLabel(label)
        caption.setFont(style.font("small"))
        self.body.addWidget(caption)
        entry = QLineEdit()
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        self.body.addWidget(entry)
        return entry

    def _message(self):
        label = QLabel("")
        label.setWordWrap(True)
        _colored(label, ERROR_COLOR)
        self.body.addWidget(label)
        return label

    def _buttons(self, primary_text, primary_command, with_cancel=True):
        buttons = QDialogButtonBox()
        primary = buttons.addButton(primary_text, QDialogButtonBox.ButtonRole.AcceptRole)
        primary.setDefault(True)
        primary.clicked.connect(primary_command)
        if with_cancel:
            cancel = buttons.addButton("Abbrechen", QDialogButtonBox.ButtonRole.RejectRole)
            cancel.clicked.connect(self.reject)
        self.body.addSpacing(10)
        self.body.addWidget(buttons)
        return primary

    def _show_done(self, title, text):
        self._clear()
        self._text(title, font=style.font("section", bold=True), colors=SUCCESS_COLOR)
        self._text(text)
        self._buttons("Schließen", self.accept, with_cancel=False).setFocus()
        self.adjustSize()


class ChangePasswordDialog(_SecurityDialog):
    # on_submit(current, new) liefert None bei Erfolg oder einen Fehlertext

    def __init__(self, parent, on_submit):
        super().__init__(parent, "Passwort ändern")
        self.on_submit = on_submit
        self._text(f"Das neue Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen. "
                   "Dein Wiederherstellungsschlüssel bleibt gültig.")
        self.current = self._password_field("Aktuelles Passwort")
        self.new1 = self._password_field("Neues Passwort")
        self.new2 = self._password_field("Neues Passwort wiederholen")
        self.msg = self._message()
        self._buttons("Ändern", self._save)
        self.current.setFocus()

    def _save(self):
        if not self.current.text():
            self.msg.setText("Bitte das aktuelle Passwort eingeben.")
            return
        problem = check_new_password(self.new1.text(), self.new2.text())
        if problem is None and self.new1.text() == self.current.text():
            problem = "Das neue Passwort ist dasselbe wie das aktuelle."
        if problem:
            self.msg.setText(problem)
            return
        _busy(True)
        try:
            error = self.on_submit(self.current.text(), self.new1.text())
        finally:
            _busy(False)
        if error:
            self.current.clear()
            self.current.setFocus()
            self.msg.setText(error)
            return
        self._show_done("Das Passwort wurde geändert.", "Ab jetzt meldest du dich mit dem neuen Passwort an.")


class NewRecoveryDialog(_SecurityDialog):
    # on_prepare(password) liefert (Code, None) oder (None, Fehlertext)
    # on_confirm() speichert und liefert None oder einen Fehlertext

    def __init__(self, parent, on_prepare, on_confirm):
        super().__init__(parent, "Neuer Wiederherstellungsschlüssel")
        self.on_prepare = on_prepare
        self.on_confirm = on_confirm
        self._text("Dein bisheriger Wiederherstellungsschlüssel wird dabei ungültig. "
                   "Bestätige mit deinem Passwort.")
        self.password = self._password_field("Aktuelles Passwort")
        self.msg = self._message()
        self._buttons("Weiter", self._prepare)
        self.password.setFocus()

    # Schritt 1: Passwort

    def _prepare(self):
        if not self.password.text():
            self.msg.setText("Bitte das aktuelle Passwort eingeben.")
            return
        _busy(True)
        try:
            code, error = self.on_prepare(self.password.text())
        finally:
            _busy(False)
        if error:
            self.password.clear()
            self.msg.setText(error)
            return
        self._show_code(code)

    # Schritt 2: Code anzeigen, erst nach Bestätigung speichern

    def _show_code(self, code):
        self._clear()
        self._text("Schreib den neuen Schlüssel auf und bewahre ihn sicher auf. Er wird nur jetzt angezeigt.")
        entry = QLineEdit(code)
        entry.setReadOnly(True)   # markieren und kopieren geht, ändern nicht
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setFont(style.font("section", family="Consolas"))
        self.body.addWidget(entry)
        confirmed = QCheckBox("Ich habe den Schlüssel sicher notiert")
        self.body.addWidget(confirmed)
        self.msg = self._message()
        # Abbrechen verwirft den neuen Schlüssel, der alte bleibt gültig
        button = self._buttons("Speichern", self._confirm)
        button.setEnabled(False)
        confirmed.toggled.connect(button.setEnabled)
        self.adjustSize()

    def _confirm(self):
        _busy(True)
        try:
            error = self.on_confirm()
        finally:
            _busy(False)
        if error:
            self.msg.setText(error)
            return
        self._show_done("Der neue Schlüssel ist gespeichert.",
                        "Der bisherige Wiederherstellungsschlüssel funktioniert nicht mehr.")
