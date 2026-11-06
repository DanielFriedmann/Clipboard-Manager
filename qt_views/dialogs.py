from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QGridLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout)

from . import style
from .links import link_target, open_link

MAX_BUTTONS = 2   # höchstens so viele Knöpfe neben einem Feld
EYE_SYMBOL = "\uE890"   # "View" aus Segoe MDL2 Assets


class EditDialog(QDialog):
    # Name und bei Passwörtern Adresse, Benutzername und Passwort ansehen und bearbeiten
    # on_save(title, username, url) speichert, on_copy(text, label) kopiert z. B. den Benutzernamen

    def __init__(self, parent, item, on_save, on_copy, content=None):
        super().__init__(parent)
        self.on_save = on_save
        self.on_copy = on_copy
        self.url_entry = None
        self.username_entry = None
        self.password_entry = None

        self.setWindowTitle("Eigenschaften" if item.is_password else "Umbenennen")
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        self.fields = QGridLayout()
        self.fields.setHorizontalSpacing(8)
        self.fields.setVerticalSpacing(4)
        self._row = 0
        layout.addLayout(self.fields)

        self.title_entry, _ = self._add_field("Name", item.title,
                                              "z. B. VPN-Portal" if item.is_password else "")
        if item.is_password:
            self.url_entry, (self.open_button, _) = self._add_field(
                "Adresse (optional)", item.url, "z. B. https://vpn.firma.de",
                buttons=[("Öffnen", self._open_url),
                         ("Kopieren", lambda: self._copy(self.url_entry, "Adresse"))])
            self.url_entry.textChanged.connect(self._update_open_button)
            self._update_open_button()

            self.username_entry, _ = self._add_field(
                "Benutzername (optional)", item.username,
                buttons=[("Kopieren", lambda: self._copy(self.username_entry, "Benutzername"))])

            # Auge in der Spalte von "Öffnen", Kopieren unter den anderen Kopieren-Knöpfen
            self.password_entry, (self.reveal_button, _) = self._add_field(
                "Passwort", content,
                buttons=[(EYE_SYMBOL, self._toggle_reveal),
                         ("Kopieren", lambda: self._copy(self.password_entry, "Passwort", sensitive=True))])
            self.password_entry.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_entry.setReadOnly(True)   # nur ansehen, nicht ändern
            self.reveal_button.setFont(style.font("normal", family=style.ICON_FAMILY))
            self.reveal_button.setCheckable(True)   # gedrückt dargestellt, solange es sichtbar ist
            self.reveal_button.setToolTip("Passwort anzeigen")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Speichern")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addSpacing(12)
        layout.addWidget(buttons)

        self.title_entry.setFocus()

    # Aufbau: Beschriftung über dem Feld, Knöpfe rechts daneben

    def _add_field(self, label, value, placeholder="", buttons=()):
        caption = QLabel(label)
        caption.setFont(style.font("small"))
        caption.setStyleSheet(f"color: {style.color('muted').name()};")
        self.fields.addWidget(caption, self._row, 0, 1, MAX_BUTTONS + 1)

        entry = QLineEdit(value or "")
        entry.setPlaceholderText(placeholder)
        # Feld ohne Knöpfe nutzt die ganze Breite
        self.fields.addWidget(entry, self._row + 1, 0, 1, MAX_BUTTONS + 1 - len(buttons))

        created = []
        for offset, (text, command) in enumerate(buttons):
            button = QPushButton(text)
            button.setAutoDefault(False)   # Enter soll speichern, nicht diesen Knopf drücken
            button.clicked.connect(command)
            self.fields.addWidget(button, self._row + 1, MAX_BUTTONS + 1 - len(buttons) + offset)
            created.append(button)
        self._row += 2
        return entry, tuple(created)

    # Ereignisse

    def _copy(self, entry, label, sensitive=False):
        # Passwörter unverändert, sonst Leerzeichen am Rand entfernen
        text = entry.text() if sensitive else entry.text().strip()
        if text:
            self.on_copy(text, label, sensitive)

    def _update_open_button(self):
        self.open_button.setEnabled(link_target(self.url_entry.text()) is not None)

    def _open_url(self):
        url = link_target(self.url_entry.text())
        if url is not None:
            open_link(url)

    def _toggle_reveal(self):
        visible = self.reveal_button.isChecked()
        self.password_entry.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.reveal_button.setToolTip("Passwort verbergen" if visible else "Passwort anzeigen")

    def _save(self):
        username = self.username_entry.text() if self.username_entry else None
        url = self.url_entry.text() if self.url_entry else None
        self.on_save(self.title_entry.text(), username, url)
        self.accept()

    def done(self, result):
        # sichtbares Passwort sofort aus dem Feld nehmen
        if self.password_entry is not None:
            self.password_entry.clear()
        super().done(result)
