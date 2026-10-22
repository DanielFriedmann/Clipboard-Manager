import customtkinter as ctk
import tkinter as tk

ICON_FONT = ("Segoe UI Semibold", 12)
TOOLTIP_DELAY = 500   # ms


def text_color_for(background):
    # Hex-Farbe wie "#fff176" in ihre drei Anteile zerlegen
    red = int(background[1:3], 16)
    green = int(background[3:5], 16)
    blue = int(background[5:7], 16)

    # Wahrgenommene Helligkeit: Grün wirkt am hellsten, Blau am dunkelsten
    brightness = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#1a1a1a" if brightness > 150 else "#ffffff"


class GroupIcon(ctk.CTkFrame):
    # Farbiges Quadrat mit einem Zeichen in der Mitte

    def __init__(self, master, color, text, size=24, text_color=None, font=ICON_FONT):
        super().__init__(master, width=size, height=size, corner_radius=5, fg_color=color)
        self.pack_propagate(False)

        if text_color is None:
            text_color = text_color_for(color)

        self.label = ctk.CTkLabel(self, text=text, font=font, text_color=text_color,
                                  width=size, height=size)
        self.label.place(relx=0.5, rely=0.5, anchor="center")

class Tooltip:
    # Kleines Hinweisfenster, das nach kurzer Verzögerung neben einem Element erscheint.
    # Das erste Element in widgets bestimmt Position und Bereich des Tooltips.

    def __init__(self, widgets, text, delay=TOOLTIP_DELAY):
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        self.widgets = widgets
        self.text = text          # darf später geändert werden
        self.delay = delay
        self._after_id = None
        self._window = None

        for widget in self.widgets:
            # add="+" hängt die Bindungen an, statt bestehende zu ersetzen
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<ButtonPress>", lambda _event: self.hide(), add="+")
            widget.bind("<Destroy>", lambda _event: self.hide(), add="+")

    # Ereignisse

    def _on_enter(self, _event):
        if self._window is not None or self._after_id is not None:
            return
        self._after_id = self.widgets[0].after(self.delay, self.show)

    def _on_leave(self, _event):
        # nur schließen, wenn die Maus den ganzen Bereich verlassen hat
        area = self.widgets[0]
        x, y = area.winfo_pointerxy()
        widget = area.winfo_containing(x, y)
        if widget is None or not str(widget).startswith(str(area)):
            self.hide()

    # Anzeigen und Verbergen

    def show(self):
        self._after_id = None
        area = self.widgets[0]
        if self._window is not None or not area.winfo_exists():
            return

        dark = ctk.get_appearance_mode() == "Dark"
        background = "#2b2b2b" if dark else "#ffffff"
        foreground = "#f2f2f2" if dark else "#1a1a1a"
        border = "#555555" if dark else "#c8c8c8"

        self._window = tk.Toplevel(area)
        self._window.overrideredirect(True)        # ohne Titelleiste und Rahmen
        self._window.attributes("-topmost", True)  # immer im Vordergrund

        tk.Label(
            self._window, text=self.text, font=("Segoe UI", 9),
            bg=background, fg=foreground, padx=8, pady=4,
            highlightthickness=1, highlightbackground=border,
        ).pack()

        # rechts neben dem Bereich, senkrecht mittig
        self._window.update_idletasks()
        x = area.winfo_rootx() + area.winfo_width() + 8
        y = area.winfo_rooty() + (area.winfo_height() - self._window.winfo_height()) // 2
        self._window.geometry(f"+{x}+{y}")

    def hide(self):
        if self._after_id is not None:
            self.widgets[0].after_cancel(self._after_id)
            self._after_id = None
        if self._window is not None:
            self._window.destroy()
            self._window = None