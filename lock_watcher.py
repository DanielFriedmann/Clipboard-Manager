import ctypes
import ctypes.wintypes

CHECK_INTERVAL = 2000            # ms zwischen zwei Prüfungen
DESKTOP_SWITCHDESKTOP = 0x0100   # Recht, das für OpenInputDesktop reicht


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.wintypes.UINT), ("dwTime", ctypes.wintypes.DWORD)]


def idle_seconds():
    # Sekunden seit der letzten Tastatur- oder Mauseingabe am ganzen PC
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount.restype = ctypes.wintypes.DWORD

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    # beide Werte laufen nach 49,7 Tagen über, deshalb auf 32 Bit begrenzt rechnen
    millis = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return millis / 1000.0


def windows_locked():
    # gesperrt, wenn wir den Eingabe-Desktop nicht öffnen dürfen
    user32 = ctypes.windll.user32
    user32.OpenInputDesktop.restype = ctypes.c_void_p   # Handle, auf 64 Bit sonst abgeschnitten
    user32.CloseDesktop.argtypes = [ctypes.c_void_p]

    desktop = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
    if not desktop:
        return True
    user32.CloseDesktop(desktop)
    return False


class LockWatcher:
    # prüft regelmäßig Inaktivität und Windows-Sperre und ruft dann on_lock auf

    def __init__(self, widget, on_lock, settings, get_idle=idle_seconds, is_locked=windows_locked):
        self.widget = widget         # für after(), also kein eigener Thread nötig
        self.on_lock = on_lock
        self.settings = settings     # wird bei jeder Prüfung neu gelesen
        self._get_idle = get_idle
        self._is_locked = is_locked

    def start(self):
        self.widget.after(CHECK_INTERVAL, self._tick)

    def _tick(self):
        try:
            if self.should_lock():
                self.on_lock()
        finally:
            # auch nach einem Fehler weiter prüfen
            self.widget.after(CHECK_INTERVAL, self._tick)

    def should_lock(self):
        minutes = self.settings.get("lock_minutes", 0)
        if minutes and self._get_idle() >= minutes * 60:
            return True
        if self.settings.get("lock_on_windows_lock", False) and self._is_locked():
            return True
        return False