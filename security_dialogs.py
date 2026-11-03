import tkinter as tk

import customtkinter as ctk

from vault import MIN_PASSWORD_LENGTH, check_password

FONT = ("Segoe UI", 13)
FONT_TITLE = ("Segoe UI Semibold", 16)
FONT_SMALL = ("Segoe UI", 11)
MUTED = ("#6b6b6b", "#a0a0a0")
ERROR = ("#c62828", "#ef9a9a")
SUCCESS = ("#2e7d32", "#a5d6a7")
DIALOG_WIDTH = 360

FONT_CODE = ("Consolas", 14)


def check_new_password(first, second):
    # gemeinsam für Anlegen, Zurücksetzen und Ändern; None = alles in Ordnung
    if first != second:
        return "Die Passwörter stimmen nicht überein."
    try:
        check_password(first)
    except ValueError as error:
        return str(error)
    return None


class SecurityDialog(ctk.CTkToplevel):
    # Grundgerüst für kleine modale Dialoge über dem Einstellungsfenster

    def __init__(self, parent, title, icon_path=None):
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        if icon_path:
            # CustomTkinter setzt kurz nach dem Öffnen ein eigenes Symbol
            self.after(250, lambda: self.iconbitmap(icon_path))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=20, pady=16)
        self.bind("<Escape>", lambda _event: self.destroy())

    def destroy(self):
        # Tk gibt die Sperre nicht von selbst an das Fenster darunter zurück
        parent = self.parent
        super().destroy()
        try:
            if parent.winfo_exists():
                parent.grab_set()
        except tk.TclError:
            pass   # Elternfenster wird gerade selbst geschlossen

    # Bausteine

    def _show(self):
        # mittig über dem Elternfenster, danach modal
        self.update_idletasks()
        width = max(DIALOG_WIDTH, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - width) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        self.after(10, self._make_modal)

    def _make_modal(self):
        if self.winfo_exists():
            self.grab_set()
            self.focus_first()

    def focus_first(self):
        pass

    def _clear(self):
        for widget in self.body.winfo_children():
            widget.destroy()

    def _text(self, text, font=FONT_SMALL, color=MUTED):
        label = ctk.CTkLabel(self.body, text=text, font=font, text_color=color,
                             wraplength=DIALOG_WIDTH - 40, justify="left", anchor="w")
        label.pack(fill="x", pady=(0, 8))
        return label

    def _password_field(self, label):
        ctk.CTkLabel(self.body, text=label, font=FONT_SMALL, text_color=MUTED,
                     anchor="w", height=18).pack(fill="x")
        entry = ctk.CTkEntry(self.body, show="•", font=FONT)
        entry.pack(fill="x", pady=(2, 10))
        return entry

    def _message(self):
        label = ctk.CTkLabel(self.body, text="", font=FONT_SMALL, text_color=ERROR,
                             wraplength=DIALOG_WIDTH - 40, justify="left", anchor="w")
        label.pack(fill="x")
        return label

    def _buttons(self, primary_text, primary_command, with_cancel=True):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill="x", pady=(12, 0))
        primary = ctk.CTkButton(row, text=primary_text, width=110, command=primary_command)
        primary.pack(side="right")
        if with_cancel:
            ctk.CTkButton(row, text="Abbrechen", width=100, fg_color="transparent",
                          border_width=1, text_color=("#1a1a1a", "#f2f2f2"),
                          command=self.destroy).pack(side="right", padx=(0, 8))
        return primary

    def _busy(self, busy):
        # Scrypt braucht einen Moment, Sanduhr zeigen
        self.configure(cursor="watch" if busy else "")
        self.update_idletasks()


class ChangePasswordDialog(SecurityDialog):
    # on_submit(current, new) liefert None bei Erfolg oder einen Fehlertext

    def __init__(self, parent, on_submit, icon_path=None):
        super().__init__(parent, "Passwort ändern", icon_path)
        self.on_submit = on_submit

        self._text(f"Das neue Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen. "
                   "Dein Wiederherstellungsschlüssel bleibt gültig.")
        self.current = self._password_field("Aktuelles Passwort")
        self.new1 = self._password_field("Neues Passwort")
        self.new2 = self._password_field("Neues Passwort wiederholen")
        self.msg = self._message()
        self.save_button = self._buttons("Ändern", self._save)

        self.bind("<Return>", lambda _event: self._save())
        self._show()

    def focus_first(self):
        self.current.focus_set()

    def _save(self):
        if not self.current.get():
            self.msg.configure(text="Bitte das aktuelle Passwort eingeben.")
            return
        problem = check_new_password(self.new1.get(), self.new2.get())
        if problem is None and self.new1.get() == self.current.get():
            problem = "Das neue Passwort ist dasselbe wie das aktuelle."
        if problem:
            self.msg.configure(text=problem)
            return

        self._busy(True)
        error = self.on_submit(self.current.get(), self.new1.get())
        if not self.winfo_exists():
            return   # inzwischen gesperrt und geschlossen
        self._busy(False)
        if error:
            self.current.delete(0, "end")
            self.current.focus_set()
            self.msg.configure(text=error)
            return
        self._show_done()

    def _show_done(self):
        self.unbind("<Return>")
        self._clear()
        self._text("Das Passwort wurde geändert.", font=FONT_TITLE, color=SUCCESS)
        self._text("Ab jetzt meldest du dich mit dem neuen Passwort an.")
        done = self._buttons("Schließen", self.destroy, with_cancel=False)
        self.bind("<Return>", lambda _event: self.destroy())
        done.focus_set()

class NewRecoveryDialog(SecurityDialog):
    # on_prepare(password) liefert (Code, None) oder (None, Fehlertext)
    # on_confirm() speichert und liefert None oder einen Fehlertext

    def __init__(self, parent, on_prepare, on_confirm, icon_path=None):
        super().__init__(parent, "Neuer Wiederherstellungsschlüssel", icon_path)
        self.on_prepare = on_prepare
        self.on_confirm = on_confirm
        self.show_password_step()
        self._show()

    def focus_first(self):
        if getattr(self, "password", None) is not None and self.password.winfo_exists():
            self.password.focus_set()

    # Schritt 1: Passwort

    def show_password_step(self):
        self._text("Dein bisheriger Wiederherstellungsschlüssel wird dabei ungültig. "
                   "Bestätige mit deinem Passwort.")
        self.password = self._password_field("Aktuelles Passwort")
        self.msg = self._message()
        self._buttons("Weiter", self._prepare)
        self.bind("<Return>", lambda _event: self._prepare())

    def _prepare(self):
        if not self.password.get():
            self.msg.configure(text="Bitte das aktuelle Passwort eingeben.")
            return
        self._busy(True)
        code, error = self.on_prepare(self.password.get())
        if not self.winfo_exists():
            return   # inzwischen gesperrt und geschlossen
        self._busy(False)
        if error:
            self.password.delete(0, "end")
            self.msg.configure(text=error)
            return
        self.show_code_step(code)

    # Schritt 2: Code anzeigen, erst nach Bestätigung speichern

    def show_code_step(self, code):
        self.unbind("<Return>")
        self._clear()
        self.password = None
        self._text("Schreib den neuen Schlüssel auf und bewahre ihn sicher auf. "
                   "Er wird nur jetzt angezeigt.")

        entry = ctk.CTkEntry(self.body, font=FONT_CODE, justify="center")
        entry.insert(0, code)
        entry.configure(state="readonly")   # markieren und kopieren geht, ändern nicht
        entry.pack(fill="x", pady=(0, 12))

        confirmed = ctk.CTkCheckBox(self.body, text="Ich habe den Schlüssel sicher notiert",
                                    font=FONT_SMALL)
        confirmed.pack(anchor="w")
        self.msg = self._message()

        # Abbrechen verwirft den neuen Schlüssel, der alte bleibt gültig
        button = self._buttons("Speichern", self._confirm)
        button.configure(state="disabled")
        confirmed.configure(command=lambda: button.configure(
            state="normal" if confirmed.get() else "disabled"))
        self._fit()

    def _confirm(self):
        self._busy(True)
        error = self.on_confirm()
        if not self.winfo_exists():
            return
        self._busy(False)
        if error:
            self.msg.configure(text=error)
            return
        self._clear()
        self._text("Der neue Schlüssel ist gespeichert.", font=FONT_TITLE, color=SUCCESS)
        self._text("Der bisherige Wiederherstellungsschlüssel funktioniert nicht mehr.")
        done = self._buttons("Schließen", self.destroy, with_cancel=False)
        self.bind("<Return>", lambda _event: self.destroy())
        done.focus_set()
        self._fit()

    def _fit(self):
        # Höhe an den neuen Inhalt anpassen, Position und Breite bleiben
        self.update_idletasks()
        self.geometry(f"{self.winfo_width()}x{self.winfo_reqheight()}")