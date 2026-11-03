# Erzeugt einen Tresor mit Testdaten, z. B. für testumgebung.ps1
# Aufruf aus dem Projektordner: python -m manual.make_test_data <Datenordner> [Anzahl] [Passwort]

import os
import sys
from datetime import datetime, timedelta

from history import ClipboardHistory
from models import EntryKind
from storage import save_encrypted
from vault import Vault

DEFAULT_COUNT = 120
DEFAULT_PASSWORD = "testtest"


def build_history(count):
    history = ClipboardHistory()
    work = history.add_group("Arbeit", "#1e88e5")
    private = history.add_group("Privat", "#43a047")
    history.add_group("Ideen", "#fdd835")   # bleibt leer

    # viele einfache Einträge, über mehrere Tage verteilt
    now = datetime.now()
    for i in range(count):
        item = history.add_item(f"Testeintrag {i}", source_app="Testdaten")
        item.created_at = now - timedelta(hours=(count - i) * 3)

    # Favoriten und Gruppen (vor den besonderen Fällen, damit die oben stehen)
    for item in history.history[::9]:
        item.is_favorite = True
    history.assign_items_to_group(history.history[10:25], work)
    history.assign_items_to_group(history.history[30:36], private)

    # besondere Fälle
    history.add_item("https://example.com/projekte/clipboard", kind=EntryKind.LINK,
                     source_app="chrome")
    history.add_item("Zeile 1\nZeile 2\nZeile 3\n" + "Ein langer Text, der abgeschnitten wird. " * 12,
                     source_app="Word")
    signature = history.add_item("Mit freundlichen Grüßen\nDaniel Friedmann", source_app="Outlook")
    history.rename_item(signature, "Signatur")
    history.add_item("Geheim-123!", kind=EntryKind.PASSWORD, source_app="KeePass",
                     needs_review=True)
    vpn = history.add_item("VPN-Passwort-456", kind=EntryKind.PASSWORD, source_app="KeePass")
    history.rename_item(vpn, "VPN-Portal", "daniel", "https://vpn.firma.de")

    return history


def main():
    folder = sys.argv[1]
    count = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_COUNT
    password = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PASSWORD

    vault, code = Vault.create(password)
    history = build_history(count)
    save_encrypted(history, vault, os.path.join(folder, "vault.json"))

    print(f"Testdaten: {len(history.history)} Einträge, {len(history.groups)} Gruppen")
    print(f"Passwort: {password}")
    print(f"Wiederherstellungsschlüssel: {code}")


if __name__ == "__main__":
    main()