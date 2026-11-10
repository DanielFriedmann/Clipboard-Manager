import ctypes
import ctypes.wintypes
import os
import threading
import time
from dataclasses import dataclass

import pywintypes
import win32clipboard
import win32con
import win32gui
import win32process

WM_CLIPBOARDUPDATE = 0x031D

OPEN_RETRIES = 10          # so oft wird das Öffnen versucht
OPEN_RETRY_DELAY = 0.02    # Pause zwischen den Versuchen in Sekunden

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Signale, die Passwort-Manager beim Kopieren mitschicken
FORMAT_EXCLUDE = "ExcludeClipboardContentFromMonitorProcessing"
FORMAT_HISTORY = "CanIncludeInClipboardHistory"
FORMAT_CLOUD = "CanUploadToCloudClipboard"
FORMAT_VIEWER_IGNORE = "Clipboard Viewer Ignore"

# eigene Markierung: diese Änderung kommt von uns und wird nicht als neuer Eintrag erfasst
FORMAT_OWN_COPY = "AbkooClipboardManagerOwnCopy"

DWORD_ZERO = (0).to_bytes(4, "little")


@dataclass
class ClipboardCapture:
    text: str
    is_sensitive: bool = False
    source_app: str | None = None


def _process_name(pid):
    # nur Leserechte anfordern, das klappt auch bei den meisten fremden Prozessen
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = ctypes.wintypes.DWORD(260)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            # "C:\...\KeePass.exe" -> "KeePass"
            return os.path.splitext(os.path.basename(buffer.value))[0]
        return None
    finally:
        kernel32.CloseHandle(handle)


class ClipboardService:
    def __init__(self, on_clipboard_changed):
        self.on_clipboard_changed = on_clipboard_changed
        self.hwnd = None
        # pausiert: Änderungen werden gar nicht erst gelesen
        # Windows meldet nur neue Änderungen, nach dem Fortsetzen kommt also nichts nachträglich
        self.paused = False
        self._lock = threading.Lock()   # immer nur ein Thread an der Zwischenablage

        # eigene Formate anmelden, Windows liefert dafür eine feste Nummer
        self._fmt_exclude = win32clipboard.RegisterClipboardFormat(FORMAT_EXCLUDE)
        self._fmt_history = win32clipboard.RegisterClipboardFormat(FORMAT_HISTORY)
        self._fmt_cloud = win32clipboard.RegisterClipboardFormat(FORMAT_CLOUD)
        self._fmt_viewer_ignore = win32clipboard.RegisterClipboardFormat(FORMAT_VIEWER_IGNORE)
        self._fmt_own_copy = win32clipboard.RegisterClipboardFormat(FORMAT_OWN_COPY)

    # Zugriff auf die Zwischenablage

    def _open(self):
        # andere Programme halten die Zwischenablage manchmal kurz offen
        for attempt in range(OPEN_RETRIES):
            try:
                win32clipboard.OpenClipboard()
                return
            except pywintypes.error:
                if attempt == OPEN_RETRIES - 1:
                    raise
                time.sleep(OPEN_RETRY_DELAY)

    def _is_sensitive(self):
        # nur aufrufen, solange die Zwischenablage geöffnet ist
        if win32clipboard.IsClipboardFormatAvailable(self._fmt_exclude):
            return True
        if win32clipboard.IsClipboardFormatAvailable(self._fmt_viewer_ignore):
            return True
        if win32clipboard.IsClipboardFormatAvailable(self._fmt_history):
            data = win32clipboard.GetClipboardData(self._fmt_history)
            if data[:4] == DWORD_ZERO:
                return True
        return False

    def _source_app(self):
        hwnd = win32clipboard.GetClipboardOwner()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return _process_name(pid)

    def get_text(self):
        with self._lock:
            self._open()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()

    def read_capture(self):
        with self._lock:
            self._open()
            try:
                if win32clipboard.IsClipboardFormatAvailable(self._fmt_own_copy):
                    return None   # von uns selbst kopiert
                if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return None
                text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                is_sensitive = self._is_sensitive()
            finally:
                win32clipboard.CloseClipboard()

        # braucht die geöffnete Zwischenablage nicht
        try:
            source_app = self._source_app()
        except pywintypes.error:
            source_app = None

        return ClipboardCapture(text, is_sensitive, source_app)

    def set_text(self, text, sensitive=False):
        with self._lock:
            self._open()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
                win32clipboard.SetClipboardData(self._fmt_own_copy, b"\x01")
                if sensitive:
                    # Windows soll Passwörter nicht in Win+V oder die Cloud übernehmen
                    win32clipboard.SetClipboardData(self._fmt_exclude, b"\x00")
                    win32clipboard.SetClipboardData(self._fmt_history, DWORD_ZERO)
                    win32clipboard.SetClipboardData(self._fmt_cloud, DWORD_ZERO)
            finally:
                win32clipboard.CloseClipboard()

    def clear(self):
        # Windows-Zwischenablage leeren, z. B. beim Sperren
        with self._lock:
            self._open()
            try:
                win32clipboard.EmptyClipboard()
            finally:
                win32clipboard.CloseClipboard()

    # Nachrichten von Windows

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            if self.paused:
                return 0
            try:
                capture = self.read_capture()
            except pywintypes.error as error:
                # diese eine Änderung überspringen statt abzustürzen
                print(f"Zwischenablage konnte nicht gelesen werden: {error}")
                return 0

            if capture is not None:
                self.on_clipboard_changed(capture)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def start(self):
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "ClipboardListener"
        win32gui.RegisterClass(wc)

        self.hwnd = win32gui.CreateWindow(
            "ClipboardListener", "Clipboard Listener", 0,
            0, 0, 0, 0,
            win32con.HWND_MESSAGE, 0, 0, None,
        )

        ctypes.windll.user32.AddClipboardFormatListener(self.hwnd)
        print("Lausche auf die Zwischenablage ...")
        win32gui.PumpMessages()