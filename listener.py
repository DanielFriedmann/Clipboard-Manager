import ctypes          
import win32gui
import win32con
import win32clipboard 
from history import ClipboardHistory


WM_CLIPBOARDUPDATE = 797

history = ClipboardHistory()

def get_clipboard_text():
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()

def set_clipboard_text(text):
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_CLIPBOARDUPDATE:
        text = get_clipboard_text()

        if text is not None:      
            history.add_item(text)
            history.print_history()

        return 0

    return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


wc = win32gui.WNDCLASS()
wc.lpfnWndProc = wnd_proc
wc.lpszClassName = "ClipboardListener"
win32gui.RegisterClass(wc)     # Bauplan für das Fenster registrieren

hwnd = win32gui.CreateWindow(
    "ClipboardListener", "Clipboard Listener", 0,
    0, 0, 0, 0,
    win32con.HWND_MESSAGE, 0, 0, None   # Message-Only Fenster nach Bauplan erzeugen
)


ctypes.windll.user32.AddClipboardFormatListener(hwnd) # bei Windows als Zuhörer anmelden
print("Lausche auf die Zwischenablage ... (kopiere etwas)")


win32gui.PumpMessages() # Nachrichtenschleife