import ctypes
from ctypes import wintypes

MUTEX_NAME = "Local\\Abkoo.Zwischenablagen.Manager"
ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

# Rückgabe- und Parametertypen festlegen, damit ctypes Handles richtig behandelt
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)

_mutex = None   # Handle festhalten, solange das Programm läuft


def acquire():
    # True, wenn dies die erste Instanz ist
    global _mutex
    _mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def bring_to_front(window_title):
    # Fenster der laufenden Instanz suchen und nach vorne holen
    hwnd = user32.FindWindowW(None, window_title)
    if not hwnd:
        return
    if user32.IsIconic(hwnd):          # minimiert?
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)