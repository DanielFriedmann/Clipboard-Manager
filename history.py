from models import ClipboardItem, ClipboardFormat
from datetime import datetime


class ClipboardHistory:
    def __init__(self):
        self.history = []

    def add_item(self, text):                    
        # 1. Gibt es diesen Text schon im Verlauf?
        existing = None
        for item in self.history:
            if item.content == text:
                existing = item
                break
        
        # 2. Alten Eintrag wiederverwenden oder neuen erzeugen
        if existing is not None:
            self.history.remove(existing)
            existing.created_at = datetime.now()  
            clipboard_item = existing             
        else:
            clipboard_item = ClipboardItem(clipboard_format=ClipboardFormat.TEXT, content=text)
        
        
        self.history.insert(0, clipboard_item)         

    def remove_item(self, item):
        if item in self.history:
            self.history.remove(item) 

    def toggle_pinned(self, item):
        item.is_pinned = not item.is_pinned

    def get_history(self):
        pinned_items = [item for item in self.history if item.is_pinned]
        unpinned_items = [item for item in self.history if not item.is_pinned]
        return pinned_items + unpinned_items

        
    def print_history(self):
        print("--------------------------------")
        print("Clipboard History:")
        for item in self.history:
            print(f"Format: {item.clipboard_format}, Content: {item.content}, Created At: {item.created_at}, Pinned: {item.is_pinned}")
    