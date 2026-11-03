import customtkinter as ctk

FONT = ("Segoe UI", 13)
FONT_SECTION = ("Segoe UI Semibold", 15)
FONT_SMALL = ("Segoe UI", 11)
MUTED = ("#6b6b6b", "#a0a0a0")
WINDOW_WIDTH = 460
CONTROL_WIDTH = 150   # gleiche Breite für alle Bedienelemente rechts, wirkt ruhiger

LOCK_CHOICES = [
    (5, "5 Minuten"),
    (15, "15 Minuten"),
    (30, "30 Minuten"),
    (60, "60 Minuten"),
    (0, "Nie"),
]


class SettingsWindow(ctk.CTkToplevel):
    # Einstellungen als eigenes Fenster; jede Änderung gilt sofort, ohne Speichern-Button

    def __init__(self, master, settings, on_change, on_lock_now, version,
                 on_change_password=None, on_new_recovery=None, icon_path=None):
        super().__init__(master)
        self.settings = settings
        self.on_change = on_change            # on_change(key, value) speichert sofort
        self.on_lock_now = on_lock_now
        self.on_change_password = on_change_password   # None = noch nicht verfügbar
        self.on_new_recovery = on_new_recovery

        self.title("Einstellungen")
        self.resizable(False, False)
        self.transient(master)   # bleibt über dem Hauptfenster, eigener Taskleisten-Eintrag entfällt

        if icon_path:
            # CustomTkinter setzt das Symbol nach ca. 200 ms selbst, deshalb danach überschreiben
            self.after(250, lambda: self.iconbitmap(icon_path))

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=20)
        self.body.grid_columnconfigure(0, weight=1)
        self._row = 0

        self._build_lock_section()
        self._build_security_section()
        self._build_footer(version)

        self.bind("<Escape>", lambda _event: self.destroy())
        self._place_over(master)
        # modal erst, wenn das Fenster sichtbar ist, sonst schlägt grab_set unter Windows fehl
        self.after(10, self._make_modal)

    # Bausteine

    def _next_row(self):
        row = self._row
        self._row += 1
        return row

    def _section(self, text):
        top = 0 if self._row == 0 else 20
        ctk.CTkLabel(self.body, text=text, font=FONT_SECTION, anchor="w").grid(
            row=self._next_row(), column=0, columnspan=2, sticky="w", pady=(top, 6))

    def _setting_row(self, text, widget_factory):
        row = self._next_row()
        ctk.CTkLabel(self.body, text=text, font=FONT, anchor="w").grid(
            row=row, column=0, sticky="w", pady=4)
        widget = widget_factory(self.body)
        widget.grid(row=row, column=1, sticky="e", pady=4)
        return widget

    def _place_over(self, master):
        # mittig über dem Hauptfenster
        self.update_idletasks()
        width = max(WINDOW_WIDTH, self.winfo_reqwidth())
        height = self.winfo_reqheight()
        x = master.winfo_rootx() + (master.winfo_width() - width) // 2
        y = master.winfo_rooty() + (master.winfo_height() - height) // 3
        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _make_modal(self):
        if self.winfo_exists():
            self.grab_set()
            self.focus_set()

    # Sperren

    def _build_lock_section(self):
        self._section("Sperren")

        labels = [label for _minutes, label in LOCK_CHOICES]
        current = self.settings.get("lock_minutes", 15)
        current_label = next((label for minutes, label in LOCK_CHOICES if minutes == current),
                             f"{current} Minuten")   # Wert von Hand in settings.json gesetzt

        self.lock_menu = self._setting_row(
            "Automatisch sperren nach",
            lambda parent: ctk.CTkOptionMenu(parent, values=labels, width=CONTROL_WIDTH,
                                             font=FONT, command=self._on_lock_minutes))
        self.lock_menu.set(current_label)

        self.windows_switch = self._setting_row(
            "Mit Windows sperren (Win+L)",
            lambda parent: ctk.CTkSwitch(parent, text="", width=CONTROL_WIDTH,
                                         command=self._on_windows_lock))
        if self.settings.get("lock_on_windows_lock", True):
            self.windows_switch.select()
        else:
            self.windows_switch.deselect()

    def _on_lock_minutes(self, label):
        minutes = dict((text, value) for value, text in LOCK_CHOICES)[label]
        self.on_change("lock_minutes", minutes)

    def _on_windows_lock(self):
        self.on_change("lock_on_windows_lock", bool(self.windows_switch.get()))

    # Sicherheit

    def _build_security_section(self):
        self._section("Sicherheit")
        self._setting_row("Passwort", lambda parent: self._action_button(
            parent, "Ändern …", self.on_change_password))
        self._setting_row("Wiederherstellungsschlüssel", lambda parent: self._action_button(
            parent, "Neu erzeugen …", self.on_new_recovery))

    def _action_button(self, parent, text, callback):
        button = ctk.CTkButton(parent, text=text, width=CONTROL_WIDTH, font=FONT,
                               command=lambda: callback(self))   # Fenster als Elternteil für Unterdialoge
        if callback is None:
            button.configure(state="disabled")
        return button

    # Fußzeile

    def _build_footer(self, version):
        ctk.CTkFrame(self.body, height=2, corner_radius=0, border_width=0, fg_color=MUTED).grid(
            row=self._next_row(), column=0, columnspan=2, sticky="ew", pady=(20, 12))

        row = self._next_row()
        ctk.CTkLabel(self.body, text=f"Version {version}", font=FONT_SMALL,
                     text_color=MUTED).grid(row=row, column=0, sticky="w")
        ctk.CTkButton(self.body, text="Jetzt sperren", width=CONTROL_WIDTH, font=FONT,
                      fg_color="transparent", border_width=1, text_color=("gray10", "gray90"),
                      command=self._lock_now).grid(row=row, column=1, sticky="e")

    def _lock_now(self):
        self.destroy()
        self.on_lock_now()