import customtkinter as ctk
import tkinter as tk
import ctypes
import ctypes.wintypes

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

def place_near(dialog, parent, width=320, height=180):
    # Dialog mit fester Größe über dem Elternfenster platzieren
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
    dialog.geometry(f"{width}x{height}+{x}+{y}")


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

MONITOR_DEFAULTTONEAREST = 2

TOOLTIP_WATCH_INTERVAL = 200   # ms


def is_inside(widget, area):
    # ".!frame20" liegt NICHT in ".!frame2", deshalb mit Punkt vergleichen
    path, area_path = str(widget), str(area)
    return path == area_path or path.startswith(area_path + ".")


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


def work_area(x, y):
    # Arbeitsbereich (ohne Taskleiste) des Monitors an dieser Stelle
    user32 = ctypes.windll.user32
    monitor = user32.MonitorFromPoint(ctypes.wintypes.POINT(x, y), MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    area = info.rcWork
    return area.left, area.top, area.right, area.bottom

class Tooltip:
    # Kleines Hinweisfenster, das nach kurzer Verzögerung erscheint.
    # Das erste Element in widgets bestimmt Position und Bereich des Tooltips.
    # text darf ein String sein oder eine Funktion, die beim Anzeigen
    # einen String liefert oder None (dann kein Tooltip).

    def __init__(self, widgets, text, delay=TOOLTIP_DELAY, position="right", wraplength=0):
        if not isinstance(widgets, (list, tuple)):
            widgets = [widgets]
        self.widgets = widgets
        self.text = text          # darf später geändert werden
        self.delay = delay
        self.position = position  # "right" neben dem Element, "pointer" am Mauszeiger
        self.wraplength = wraplength
        self._after_id = None
        self._window = None
        self._watch_id = None

        for widget in self.widgets:
            # add="+" hängt die Bindungen an, statt bestehende zu ersetzen
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<ButtonPress>", lambda _event: self.hide(), add="+")
            widget.bind("<Destroy>", lambda _event: self.hide(), add="+")

    # Ereignisse

    def _on_enter(self, _event):
        self.schedule()

    def _on_leave(self, _event):
        if not self._pointer_inside():
            self.hide()

    def _pointer_inside(self):
        area = self.widgets[0]
        if not area.winfo_exists():
            return False
        x, y = area.winfo_pointerxy()
        widget = area.winfo_containing(x, y)
        if widget is None:
            return False
        if self._window is not None and is_inside(widget, self._window):
            return False   # über dem Tooltip selbst zählt als draußen
        return is_inside(widget, area)

    # Anzeigen und Verbergen

    def schedule(self):
        if self._window is not None or self._after_id is not None:
            return
        self._after_id = self.widgets[0].after(self.delay, self.show)

    def _current_text(self):
        return self.text() if callable(self.text) else self.text

    def show(self):
        self._after_id = None
        area = self.widgets[0]
        if self._window is not None or not area.winfo_exists():
            return

        # Maus hat den Bereich verlassen, ohne dass <Leave> ankam
        if not self._pointer_inside():
            return

        text = self._current_text()
        if not text:
            return

        dark = ctk.get_appearance_mode() == "Dark"
        background = "#2b2b2b" if dark else "#ffffff"
        foreground = "#f2f2f2" if dark else "#1a1a1a"
        border = "#555555" if dark else "#c8c8c8"

        self._window = tk.Toplevel(area)
        self._window.overrideredirect(True)        # ohne Titelleiste und Rahmen
        self._window.attributes("-topmost", True)  # immer im Vordergrund

        tk.Label(
            self._window, text=text, font=("Segoe UI", 9),
            bg=background, fg=foreground, padx=8, pady=4,
            justify="left", wraplength=self.wraplength,
            highlightthickness=1, highlightbackground=border,
        ).pack()

        self._window.update_idletasks()
        width = self._window.winfo_width()
        height = self._window.winfo_height()

        if self.position == "pointer":
            pointer_x, pointer_y = area.winfo_pointerxy()
            bounds = work_area(pointer_x, pointer_y)
            if bounds is None:
                bounds = (0, 0, area.winfo_screenwidth(), area.winfo_screenheight())
            left, top, right, bottom = bounds

            # rechts unter dem Zeiger, sonst links bzw. darüber
            x = pointer_x + 12
            if x + width > right - 8:
                x = pointer_x - width - 12
            y = pointer_y + 20
            if y + height > bottom - 8:
                y = pointer_y - height - 8

            # nie über den linken oder oberen Rand hinaus
            x = max(x, left + 8)
            y = max(y, top + 8)
        else:
            # rechts neben dem Bereich, senkrecht mittig
            x = area.winfo_rootx() + area.winfo_width() + 8
            y = area.winfo_rooty() + (area.winfo_height() - height) // 2

        self._window.geometry(f"+{x}+{y}")
        self._watch_id = area.after(TOOLTIP_WATCH_INTERVAL, self._watch)

    def hide(self):
        area = self.widgets[0]
        for job in (self._after_id, self._watch_id):
            if job is not None:
                try:
                    area.after_cancel(job)
                except tk.TclError:
                    pass   # Element wurde schon zerstört
        self._after_id = None
        self._watch_id = None
        if self._window is not None:
            self._window.destroy()
            self._window = None


    def _watch(self):
        self._watch_id = None
        if self._window is None:
            return
        if self._pointer_inside():
            self._watch_id = self.widgets[0].after(TOOLTIP_WATCH_INTERVAL, self._watch)
        else:
            self.hide()