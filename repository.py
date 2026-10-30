from abc import ABC, abstractmethod


class EntryRepository(ABC):
    # Alles, was das ViewModel vom Speicher braucht.
    # Heute erfüllt ClipboardHistory diese Schnittstelle, später ApiRepository über HTTP.

    # Gruppen

    @abstractmethod
    def get_default_group(self):
        """Die Gruppe "Unsortiert"."""

    @abstractmethod
    def list_groups(self):
        """Alle Gruppen in ihrer Reihenfolge, die Standardgruppe zuerst."""

    @abstractmethod
    def add_group(self, name, color):
        """Legt eine Gruppe an und gibt sie zurück. ValueError bei doppeltem Namen."""

    @abstractmethod
    def remove_group(self, group):
        """Löscht eine Gruppe, ihre Einträge wandern in die Standardgruppe."""

    @abstractmethod
    def move_group(self, group, target, after=False):
        """Verschiebt eine Gruppe vor oder hinter target (None = ans Ende)."""

    # Einträge lesen

    @abstractmethod
    def get_history(self, group=None, sort_by="priority", descending=False,
                    search="", favorites_only=False):
        """Gefilterte und sortierte Einträge."""

    @abstractmethod
    def count(self, group=None):
        """Anzahl der Einträge einer Gruppe, None = alle."""

    @abstractmethod
    def get_content(self, item):
        """Inhalt eines Eintrags; bei Passwörtern wird er erst jetzt geholt."""

    # Einträge ändern

    @abstractmethod
    def add_item(self, text, kind=None, source_app=None, needs_review=False):
        """Neuer Eintrag oben, bei gleichem Inhalt den vorhandenen aktualisieren."""

    @abstractmethod
    def remove_items(self, items):
        """Löscht mehrere Einträge auf einmal."""

    @abstractmethod
    def clear_items(self, items):
        """Löscht die Einträge außer Favoriten, gibt die gelöschten zurück."""

    @abstractmethod
    def move_item(self, item, target, after=False):
        """Verschiebt einen Eintrag vor oder hinter target (None = ans Ende)."""

    @abstractmethod
    def toggle_favorite(self, item):
        """Favorit an oder aus."""

    @abstractmethod
    def rename_item(self, item, title, username=None, url=None):
        """Titel und bei Passwörtern Benutzer und Adresse setzen."""

    @abstractmethod
    def mark_password(self, item, is_password):
        """Als Passwort markieren oder die Markierung entfernen."""

    @abstractmethod
    def assign_items_to_group(self, items, group):
        """Mehrere Einträge in eine Gruppe verschieben, Reihenfolge bleibt erhalten."""