import ctypes
import threading
import time

import pywintypes
import win32clipboard
import win32con
import win32gui

WM_CLIPBOARDUPDATE = 0x031D

OPEN_RETRIES = 10          # so oft wird das Öffnen versucht
OPEN_RETRY_DELAY = 0.02    # Pause zwischen den Versuchen in Sekunden


class ClipboardService:
    def __init__(self, on_text_changed):
        self.on_text_changed = on_text_changed
        self.hwnd = None
        self._lock = threading.Lock()   # immer nur ein Thread an der Zwischenablage

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

    def get_text(self):
        with self._lock:
            self._open()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()

    def set_text(self, text):
        with self._lock:
            self._open()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            finally:
                win32clipboard.CloseClipboard()

    # Nachrichten von Windows

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLIPBOARDUPDATE:
            try:
                text = self.get_text()
            except pywintypes.error as error:
                # diese eine Änderung überspringen statt abzustürzen
                print(f"Zwischenablage konnte nicht gelesen werden: {error}")
                return 0

            if text is not None:
                self.on_text_changed(text)
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