import ctypes
import win32gui
import win32con
import win32clipboard

WM_CLIPBOARDUPDATE = 797 


class ClipboardService:
    def __init__(self, on_text_changed):
        self.on_text_changed = on_text_changed
        

    def get_text(self):
        win32clipboard.OpenClipboard()
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()        

    def set_text(self, text):
        win32clipboard.OpenClipboard()
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        
        if msg == WM_CLIPBOARDUPDATE:
            text = self.get_text()
        
            if text is not None:      
                self.on_text_changed(text)
        
            return 0
        
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        

    def start(self):
        
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
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