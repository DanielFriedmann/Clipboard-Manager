from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from vault import MIN_PASSWORD_LENGTH, Vault, WrongPassword

from . import style
from .security import check_new_password, windows_user_name

BOX_WIDTH = 320


class LoginView(QWidget):
    # Anmeldung, Anlegen des Benutzers und Wiederherstellung; ersetzt den Fensterinhalt.
    # Kennt nur den Header mit den eingepackten Schlüsseln, die Daten öffnet on_unlocked.
    # on_unlocked(vault, is_new, header_changed) liefert None oder einen Fehlertext.

    def __init__(self, header, on_unlocked, locked=False, parent=None):
        super().__init__(parent)
        self.header = header             # None, wenn es noch keinen Tresor gibt
        self.on_unlocked = on_unlocked
        self.locked = locked             # True: Entsperren nach einer Sperre
        self.user_name = windows_user_name()

        self.setObjectName("login")
        self.setStyleSheet(f"#login {{ background: {style.color('window').name()}; }}")

        # Kasten in der Mitte, Inhalt wird je nach Seite neu aufgebaut
        outer = QVBoxLayout(self)
        outer.addStretch(2)
        self.box = QWidget()
        self.box.setFixedWidth(BOX_WIDTH + 60)
        self.layout_box = QVBoxLayout(self.box)
        self.layout_box.setSpacing(6)
        outer.addWidget(self.box, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(3)

        if header is None:
            self.show_setup()
        else:
            self.show_login()

    # Bausteine

    def _clear(self):
        while self.layout_box.count():
            widget = self.layout_box.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _title(self, text, subtitle):
        title = QLabel(text)
        title.setFont(style.font("title", bold=True))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout_box.addWidget(title)
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color: {style.color('muted').name()};")
        # umbrochener Text: Höhe selbst festlegen, sonst schneidet das zentrierte Layout ab
        sub.setFixedWidth(BOX_WIDTH)
        sub.setMinimumHeight(sub.heightForWidth(BOX_WIDTH))
        self.layout_box.addWidget(sub, 0, Qt.AlignmentFlag.AlignHCenter)
        self.layout_box.addSpacing(12)

    def _password_field(self, placeholder):
        entry = QLineEdit()
        entry.setPlaceholderText(placeholder)
        entry.setEchoMode(QLineEdit.EchoMode.Password)
        entry.setMinimumHeight(30)
        self.layout_box.addWidget(entry)
        return entry

    def _message(self):
        label = QLabel("")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #c62828;" if not style.is_dark() else "color: #ef9a9a;")
        label.setMinimumHeight(2 * label.fontMetrics().height())   # Platz für zwei Zeilen Fehlertext
        self.layout_box.addWidget(label)
        return label

    def _button(self, text, command, secondary=False):
        button = QPushButton(text)
        button.setMinimumHeight(32)
        if secondary:
            button.setFlat(True)
            button.setStyleSheet(f"color: {style.color('muted').name()};")
        else:
            button.setDefault(True)
        button.clicked.connect(command)
        self.layout_box.addWidget(button)
        return button

    def _busy(self, busy):
        # Scrypt braucht einen Moment, Sanduhr zeigen
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
        else:
            QApplication.restoreOverrideCursor()

    # Benutzer anlegen

    def show_setup(self):
        self._clear()
        self._title("Willkommen",
                    f"{self.user_name}, lege ein Passwort für deine Zwischenablage fest. "
                    f"Mindestens {MIN_PASSWORD_LENGTH} Zeichen.")
        self.pw1 = self._password_field("Passwort")
        self.pw2 = self._password_field("Passwort wiederholen")
        self.msg = self._message()
        self._button("Anlegen", self._on_setup)
        self.pw2.returnPressed.connect(self._on_setup)
        self.pw1.setFocus()

    def _on_setup(self):
        problem = check_new_password(self.pw1.text(), self.pw2.text())
        if problem:
            self.msg.setText(problem)
            return
        self._busy(True)
        try:
            vault, code = Vault.create(self.pw1.text())
        finally:
            self._busy(False)
        self.show_code(code, vault)

    def show_code(self, code, vault):
        self._clear()
        self._title("Wiederherstellungsschlüssel",
                    "Damit kannst du ein neues Passwort setzen, falls du deines vergisst. "
                    "Er wird nur jetzt angezeigt. Schreib ihn auf und bewahre ihn sicher auf.")

        entry = QLineEdit(code)
        entry.setReadOnly(True)   # markieren und kopieren geht, ändern nicht
        entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
        entry.setFont(style.font("section", family="Consolas"))
        entry.setMinimumHeight(34)
        self.layout_box.addWidget(entry)

        confirmed = QCheckBox("Ich habe den Schlüssel sicher notiert")
        self.layout_box.addWidget(confirmed)
        self.msg = self._message()

        # erst jetzt speichern: wer hier abbricht, hat noch keinen Tresor ohne notierten Schlüssel
        button = self._button("Weiter", lambda: self._finish(vault, is_new=True))
        button.setEnabled(False)
        confirmed.toggled.connect(button.setEnabled)

    # Anmelden

    def show_login(self):
        self._clear()
        self._title("Gesperrt" if self.locked else "Anmelden", f"Windows-Benutzer: {self.user_name}")
        self.pw = self._password_field("Passwort")
        self.msg = self._message()
        self._button("Anmelden", self._on_login)
        self._button("Passwort vergessen?", self.show_recovery, secondary=True)
        self.pw.returnPressed.connect(self._on_login)
        self.pw.setFocus()

    def _on_login(self):
        self._busy(True)
        try:
            vault = Vault.unlock(self.header, self.pw.text())
        except WrongPassword:
            self._busy(False)
            self.pw.clear()
            self.msg.setText("Falsches Passwort.")
            return
        self._busy(False)
        self._finish(vault)

    # Passwort vergessen

    def show_recovery(self):
        self._clear()
        self._title("Passwort zurücksetzen", "Gib deinen Wiederherstellungsschlüssel und ein neues Passwort ein.")
        self.code = QLineEdit()
        self.code.setPlaceholderText("Wiederherstellungsschlüssel")
        self.code.setMinimumHeight(30)
        self.layout_box.addWidget(self.code)
        self.pw1 = self._password_field("Neues Passwort")
        self.pw2 = self._password_field("Neues Passwort wiederholen")
        self.msg = self._message()
        self._button("Passwort setzen", self._on_recovery)
        self._button("Zurück zur Anmeldung", self.show_login, secondary=True)
        self.pw2.returnPressed.connect(self._on_recovery)
        self.code.setFocus()

    def _on_recovery(self):
        problem = check_new_password(self.pw1.text(), self.pw2.text())
        if problem:
            self.msg.setText(problem)
            return
        self._busy(True)
        try:
            vault = Vault.unlock_with_recovery(self.header, self.code.text())
            vault.change_password(self.pw1.text())
        except WrongPassword:
            self._busy(False)
            self.msg.setText("Der Wiederherstellungsschlüssel ist falsch.")
            return
        self._busy(False)
        self._finish(vault, header_changed=True)

    # Abschluss

    def _finish(self, vault, is_new=False, header_changed=False):
        self._busy(True)
        try:
            error = self.on_unlocked(vault, is_new, header_changed)
        finally:
            self._busy(False)
        if error:
            self.msg.setText(error)
