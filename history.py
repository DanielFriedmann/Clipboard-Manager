from models import ClipboardGroup, ClipboardItem, ClipboardFormat
from datetime import datetime


class ClipboardHistory:
    def __init__(self):
        self.history = []
        self.default_group = ClipboardGroup(name="Unsortiert")
        self.groups = [self.default_group]

    def add_item(self, text):                    
        
        existing = None
        for item in self.history:
            if item.content == text:
                existing = item
                break
        
        
        if existing is not None:            
            existing.created_at = datetime.now()                          
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

    def move_item(self, item, target, after=False):
        
        if item is target:
            return

       
        self.history.remove(item)

        
        if target is None:
            self.history.append(item)               # ans Ende
        else:
            index = self.history.index(target)      # erst NACH dem Entfernen bestimmen
            if after:
                index += 1
            self.history.insert(index, item)        # direkt vor target

    def toggle_favorite(self, item):
        item.is_favorite = not item.is_favorite

    def get_history(self, group=None, sort_by="priority", descending=False,
                search="", favorites_only=False):
        items = list(self.history)

        # 1. Filter, jeder baut auf dem vorherigen auf
        if group is not None:
            items = [item for item in items if item.clipboard_group is group]
        if favorites_only:
            items = [item for item in items if item.is_favorite]
        if search:
            term = search.lower()
            items = [item for item in items if term in item.content.lower()]

        # 2. Sortierung und Richtung
        if sort_by == "time":
            items = sorted(items, key=lambda item: item.created_at, reverse=descending)
        elif sort_by == "content":
            items = sorted(items, key=lambda item: item.content.lower(), reverse=descending)
        elif sort_by == "favorite":
            items = sorted(items, key=lambda item: item.is_favorite, reverse=not descending)
        elif sort_by == "group":
            items = sorted(
                items,
                key=lambda item: item.clipboard_group.name.lower() if item.clipboard_group else "",
                reverse=descending,
            )
        elif descending:
            items.reverse()   # eigene Reihenfolge, umgedreht

        return items

    def clear_items(self, items):
        for item in items:
            if not item.is_favorite:
                self.remove_item(item)

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

    def move_group(self, group, target, after=False):
        if group is target or group is self.default_group or target is self.default_group:
            return

        self.groups.remove(group)

        if target is None:
            self.groups.append(group)
        else:
            index = self.groups.index(target)
            if after:
                index += 1
            self.groups.insert(index, group)

        
    def print_history(self):
        print("--------------------------------")
        print("Clipboard History:")
        for item in self.history:
            print(f"Format: {item.clipboard_format}, Content: {item.content}, Created At: {item.created_at}, Favorite: {item.is_favorite}")
    