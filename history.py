from models import ClipboardGroup, ClipboardItem, ClipboardFormat
from datetime import datetime


class ClipboardHistory:
    def __init__(self):
        self.history = []
        self.default_group = ClipboardGroup(name="Allgemein")
        self.groups = [self.default_group]

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
            clipboard_item = ClipboardItem(
                clipboard_format=ClipboardFormat.TEXT,
                content=text, 
                clipboard_group=self.default_group,
                )
        
        
        self.history.insert(0, clipboard_item)         

    def remove_item(self, item):
        if item in self.history:
            self.history.remove(item) 

    def move_item(self, item, target):
        
        if item is target:
            return

       
        self.history.remove(item)

        
        if target is None:
            self.history.append(item)               # ans Ende
        else:
            index = self.history.index(target)      # erst NACH dem Entfernen bestimmen
            self.history.insert(index, item)        # direkt vor target

    def toggle_favorite(self, item):
        item.is_favorite = not item.is_favorite

    def get_history(self, group=None):
        if group is None:
            return list(self.history)
        return [item for item in self.history if item.clipboard_group is group]

    def clear_history(self, group=None):
        if group is None:
        
            self.history = [
            item for item in self.history
            if item.is_favorite or item.clipboard_group is not self.default_group
            ]

        else:
        
            self.history = [
            item for item in self.history
            if item.clipboard_group is not group or item.is_favorite
            ]

    # Gruppenverwaltung

    def add_group(self, name, color="#9e9e9e"):
        if any(group.name.lower() == name.lower() for group in self.groups):
            raise ValueError(f"Gruppe mit dem Namen '{name}' existiert bereits.")
        new_group = ClipboardGroup(name=name, color=color)
        self.groups.append(new_group)
        return new_group

    def remove_group(self, group):
        if group == self.default_group:
            raise ValueError("Die Standardgruppe kann nicht gelöscht werden.")
        if group in self.groups:
            self.groups.remove(group)
            for item in self.history:
                if item.clipboard_group == group:
                    item.clipboard_group = self.default_group

    def assign_item_to_group(self, item, group):
        if group not in self.groups:
            raise ValueError("Die angegebene Gruppe existiert nicht.")
        item.clipboard_group = group

        self.history.remove(item)
        self.history.insert(0, item)

        
    def print_history(self):
        print("--------------------------------")
        print("Clipboard History:")
        for item in self.history:
            print(f"Format: {item.clipboard_format}, Content: {item.content}, Created At: {item.created_at}, Favorite: {item.is_favorite}")
    