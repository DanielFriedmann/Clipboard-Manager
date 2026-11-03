import customtkinter as ctk

from widgets import place_near

FONT = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
MUTED = ("#6b6b6b", "#a0a0a0")
MASK_CHAR = "•"


class EditDialog(ctk.CTkToplevel):
    # Name und bei Passwörtern Benutzername bearbeiten

    def __init__(self, parent, item, on_save, icon_path=None, content=None):
        super().__init__(parent)
        self.on_save = on_save
        self.password_entry = None
        self.username_entry = None
        self.url_entry = None

        self.title("Passwort benennen" if item.is_password else "Umbenennen")
        self.resizable(False, False)
        self.transient(parent)   # bleibt über dem Hauptfenster
        if icon_path:
            # CustomTkinter setzt kurz nach dem Öffnen ein eigenes Symbol
            self.after(250, lambda: self.iconbitmap(icon_path))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 0))

        self.title_entry = self._add_field(body, "Name", item.title or "",
                                           "z. B. VPN-Portal" if item.is_password else "")
        if item.is_password:
            self.url_entry = self._add_field(body, "Adresse (optional)",
                                             item.url or "", "z. B. https://vpn.firma.de")
            self.username_entry = self._add_field(body, "Benutzername (optional)",
                                                  item.username or "")
            self._add_password(body, content if content is not None else item.content)

        # Knöpfe
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=16)
        ctk.CTkButton(buttons, text="Speichern", width=100, command=self._save).pack(side="right")
        ctk.CTkButton(buttons, text="Abbrechen", width=100, fg_color="transparent",
                      border_width=1, text_color=("#1a1a1a", "#f2f2f2"),
                      command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _event: self._save())
        self.bind("<Escape>", lambda _event: self.destroy())

        place_near(self, parent, width=380, height=374 if item.is_password else 170)

        # erst nach dem Anzeigen: Eingaben abfangen und Cursor ins Feld setzen
        self.after(100, self._activate)

    # Aufbau

    def _add_field(self, parent, label, value, placeholder=""):
        ctk.CTkLabel(parent, text=label, font=FONT_SMALL, text_color=MUTED,
                     anchor="w", height=18).pack(fill="x")
        entry = ctk.CTkEntry(parent, font=FONT, placeholder_text=placeholder)
        entry.pack(fill="x", pady=(2, 10))
        if value:
            entry.insert(0, value)
        return entry

    def _add_password(self, parent, content):
        ctk.CTkLabel(parent, text="Passwort", font=FONT_SMALL, text_color=MUTED,
                     anchor="w", height=18).pack(fill="x")

        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(2, 0))

        self.password_entry = ctk.CTkEntry(row, font=FONT, show=MASK_CHAR)
        self.password_entry.insert(0, content)
        self.password_entry.configure(state="readonly")   # nur ansehen, nicht ändern
        self.password_entry.pack(side="left", fill="x", expand=True)

        self.reveal_button = ctk.CTkButton(row, text="Anzeigen", width=90,
                                           fg_color="transparent", border_width=1,
                                           text_color=("#1a1a1a", "#f2f2f2"),
                                           command=self._toggle_reveal)
        self.reveal_button.pack(side="left", padx=(8, 0))

    # Ereignisse

    def _activate(self):
        self.grab_set()   # Hauptfenster sperren, solange der Dialog offen ist
        self.title_entry.focus_set()

    def _toggle_reveal(self):
        hidden = self.password_entry.cget("show") == MASK_CHAR
        self.password_entry.configure(show="" if hidden else MASK_CHAR)
        self.reveal_button.configure(text="Verbergen" if hidden else "Anzeigen")

    def _save(self):
        username = self.username_entry.get() if self.username_entry else None
        url = self.url_entry.get() if self.url_entry else None
        self.on_save(self.title_entry.get(), username, url)
        self.destroy()