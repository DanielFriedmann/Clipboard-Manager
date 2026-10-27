import getpass

import customtkinter as ctk

from history import ClipboardHistory
from storage import load_encrypted, load_legacy, remove_legacy, save_encrypted
from vault import MIN_PASSWORD_LENGTH, Vault, WrongPassword, check_password

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 20)
FONT_SMALL = ("Segoe UI", 11)
FONT_CODE = ("Consolas", 14)
MUTED = ("#6b6b6b", "#a0a0a0")
ERROR = ("#c62828", "#ef9a9a")
NAME_DISPLAY = 3   # Windows: Anzeigename des Benutzers, etwa "Daniel Friedmann"


def windows_user_name():
    # Anzeigename, sonst der Anmeldename
    try:
        import win32api
        name = win32api.GetUserNameEx(NAME_DISPLAY)
        if name:
            return name
    except Exception:
        pass
    return getpass.getuser()


class LoginView(ctk.CTkFrame):
    # Anmeldung, Anlegen des Benutzers und Wiederherstellung; liegt über dem ganzen Fenster

    def __init__(self, master, vault_content, on_success):
        super().__init__(master, corner_radius=0)
        self.vault_content = vault_content
        self.on_success = on_success
        self.user_name = windows_user_name()

        self.box = ctk.CTkFrame(self, fg_color="transparent")
        self.box.place(relx=0.5, rely=0.45, anchor="center")

        if vault_content is None:
            self.show_setup()
        else:
            self.show_login()

    # Bausteine

    def _clear(self):
        for widget in self.box.winfo_children():
            widget.destroy()

    def _title(self, text, subtitle):
        ctk.CTkLabel(self.box, text=text, font=FONT_TITLE).pack(pady=(0, 4))
        ctk.CTkLabel(self.box, text=subtitle, font=FONT_SMALL, text_color=MUTED,
                     wraplength=320, justify="center").pack(pady=(0, 16))

    def _password_field(self, placeholder):
        entry = ctk.CTkEntry(self.box, placeholder_text=placeholder, show="•", width=300, font=FONT)
        entry.pack(pady=4)
        return entry

    def _message(self):
        label = ctk.CTkLabel(self.box, text="", font=FONT_SMALL, text_color=ERROR, wraplength=300)
        label.pack(pady=(4, 0))
        return label

    def _button(self, text, command, secondary=False):
        button = ctk.CTkButton(self.box, text=text, width=300, command=command)
        if secondary:
            button.configure(fg_color="transparent", text_color=MUTED, hover=False)
        button.pack(pady=(8, 0))
        return button

    def _busy(self, busy):
        # Scrypt braucht einen Moment, Sanduhr zeigen
        self.configure(cursor="watch" if busy else "")
        self.update_idletasks()

    def _check_new_password(self, first, second):
        if first != second:
            return "Die Passwörter stimmen nicht überein."
        try:
            check_password(first)
        except ValueError as error:
            return str(error)
        return None

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
        self.pw2.bind("<Return>", lambda _event: self._on_setup())
        self.pw1.focus_set()

    def _on_setup(self):
        problem = self._check_new_password(self.pw1.get(), self.pw2.get())
        if problem:
            self.msg.configure(text=problem)
            return

        self._busy(True)
        vault, code = Vault.create(self.pw1.get())
        history = load_legacy() or ClipboardHistory()   # Daten aus Version 1.1 übernehmen
        save_encrypted(history, vault)
        remove_legacy()                                  # erst nach erfolgreichem Speichern
        self._busy(False)
        self.show_code(code, vault, history)

    def show_code(self, code, vault, history):
        self._clear()
        self._title("Wiederherstellungsschlüssel",
                    "Damit kannst du ein neues Passwort setzen, falls du deines vergisst. "
                    "Er wird nur jetzt angezeigt. Schreib ihn auf und bewahre ihn sicher auf.")

        entry = ctk.CTkEntry(self.box, width=360, font=FONT_CODE, justify="center")
        entry.insert(0, code)
        entry.configure(state="readonly")
        entry.pack(pady=4)

        confirmed = ctk.CTkCheckBox(self.box, text="Ich habe den Schlüssel sicher notiert",
                                    font=FONT_SMALL)
        confirmed.pack(pady=(12, 0))

        button = self._button("Weiter", lambda: self.on_success(vault, history, True))
        button.configure(state="disabled")
        confirmed.configure(command=lambda: button.configure(
            state="normal" if confirmed.get() else "disabled"))

    # Anmelden

    def show_login(self):
        self._clear()
        self._title("Anmelden", f"Windows-Benutzer: {self.user_name}")
        self.pw = self._password_field("Passwort")
        self.msg = self._message()
        self._button("Anmelden", self._on_login)
        self._button("Passwort vergessen?", self.show_recovery, secondary=True)
        self.pw.bind("<Return>", lambda _event: self._on_login())
        self.pw.focus_set()

    def _on_login(self):
        self._busy(True)
        try:
            vault = Vault.unlock(self.vault_content["vault"], self.pw.get())
        except WrongPassword:
            self._busy(False)
            self.pw.delete(0, "end")
            self.msg.configure(text="Falsches Passwort.")
            return
        self._finish(vault)

    # Passwort vergessen

    def show_recovery(self):
        self._clear()
        self._title("Passwort zurücksetzen",
                    "Gib deinen Wiederherstellungsschlüssel und ein neues Passwort ein.")
        self.code = ctk.CTkEntry(self.box, placeholder_text="Wiederherstellungsschlüssel",
                                 width=300, font=FONT)
        self.code.pack(pady=4)
        self.pw1 = self._password_field("Neues Passwort")
        self.pw2 = self._password_field("Neues Passwort wiederholen")
        self.msg = self._message()
        self._button("Passwort setzen", self._on_recovery)
        self._button("Zurück zur Anmeldung", self.show_login, secondary=True)
        self.code.focus_set()

    def _on_recovery(self):
        problem = self._check_new_password(self.pw1.get(), self.pw2.get())
        if problem:
            self.msg.configure(text=problem)
            return

        self._busy(True)
        try:
            vault = Vault.unlock_with_recovery(self.vault_content["vault"], self.code.get())
        except WrongPassword:
            self._busy(False)
            self.msg.configure(text="Der Wiederherstellungsschlüssel ist falsch.")
            return
        vault.change_password(self.pw1.get())
        self._finish(vault, save=True)

    # Abschluss

    def _finish(self, vault, save=False):
        try:
            history = load_encrypted(self.vault_content, vault)
        except Exception as error:
            self._busy(False)
            self.msg.configure(text=f"Die Daten konnten nicht gelesen werden: {error}")
            return
        if save:
            save_encrypted(history, vault)   # neues Passwort sofort festschreiben
        remove_legacy()                      # falls noch eine alte Klartext-Datei übrig ist
        self._busy(False)
        self.on_success(vault, history, False)