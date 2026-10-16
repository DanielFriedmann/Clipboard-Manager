import win32clipboard  # Windows Clipboard Modul
import win32con        # Windows Konstanten
import pywintypes      # Fehlertyp von pywin32


def list_clipboard_formats():
    win32clipboard.OpenClipboard()

    try:
        print("Clipboard opened successfully.")

        
        format_id = win32clipboard.EnumClipboardFormats(0)
 
        while format_id != 0:
            try:
                name = win32clipboard.GetClipboardFormatName(format_id)
            except pywintypes.error:
                name = "Standard Format"

            print(f"Format ID: {format_id}, Name: {name}") 

            format_id = win32clipboard.EnumClipboardFormats(format_id)

        
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            clipboard_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            print(f"Clipboard Text: {clipboard_text}") 
        else:
            print("No text in clipboard.") 

    finally:
        win32clipboard.CloseClipboard()
        print("Clipboard closed successfully.")

def get_clipboard_text():
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            clipboard_text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return clipboard_text
        else:
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

from history import ClipboardHistory

h = ClipboardHistory()
h.add_item("A")
h.add_item("B")
h.add_item("A")
h.print_history()