import os
import tempfile

from demo_data import load_demo_data
from history import ClipboardHistory
from storage import load_history, save_history

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "data.json")

    # Fall 1: keine Datei vorhanden
    print(load_history(path), "   (erwartet: None)")

    # Fall 2: speichern und wieder laden
    original = ClipboardHistory()
    load_demo_data(original)
    original.move_item(original.history[-1], original.history[0])   # eigene Reihenfolge ändern
    save_history(original, path)
    loaded = load_history(path)

    print(len(loaded.history), len(original.history), "   (erwartet: zweimal 14)")
    print([g.name for g in loaded.groups] == [g.name for g in original.groups],
          "   (erwartet: True, Gruppen in gleicher Reihenfolge)")
    print([i.content for i in loaded.history] == [i.content for i in original.history],
          "   (erwartet: True, eigene Reihenfolge erhalten)")
    print([i.is_favorite for i in loaded.history] == [i.is_favorite for i in original.history],
          "   (erwartet: True, Favoriten erhalten)")
    print([i.created_at for i in loaded.history] == [i.created_at for i in original.history],
          "   (erwartet: True, Zeitstempel erhalten)")
    print(all(i.clipboard_group in loaded.groups for i in loaded.history),
          "   (erwartet: True, alle Einträge zeigen auf geladene Gruppen)")
    print(loaded.default_group.name, loaded.default_group is loaded.groups[0],
          "   (erwartet: Unsortiert True)")

    # Fall 3: Umlaute lesbar in der Datei
    with open(path, encoding="utf-8") as file:
        print("äöü" in file.read(), "   (erwartet: True)")

    # Fall 4: beschädigte Datei
    with open(path, "w", encoding="utf-8") as file:
        file.write("{ kaputt")
    print(load_history(path), "   (erwartet: Meldung und None)")
    print([name for name in os.listdir(folder) if "defekt" in name],
          "   (erwartet: eine umbenannte Datei)")

    
    # Fall 5: verschlüsselt speichern und laden
    from vault import Vault, WrongPassword
    from storage import load_encrypted, read_vault_file, save_encrypted

    vault_path = os.path.join(folder, "vault.json")
    vault, _code = Vault.create("geheim123")
    save_encrypted(original, vault, vault_path)

    with open(vault_path, encoding="utf-8") as file:
        raw = file.read()
    print("Einkaufsliste" in raw, "Arbeit" in raw, "   (erwartet: False False, kein Klartext)")

    content = read_vault_file(vault_path)
    unlocked = Vault.unlock(content["vault"], "geheim123")
    loaded = load_encrypted(content, unlocked)
    print([i.content for i in loaded.history] == [i.content for i in original.history],
          "   (erwartet: True)")
    print([g.name for g in loaded.groups] == [g.name for g in original.groups],
          "   (erwartet: True)")

    try:
        Vault.unlock(content["vault"], "falsch123")
        print("FEHLER: falsches Passwort angenommen")
    except WrongPassword:
        print("Falsches Passwort korrekt abgelehnt")

    print(read_vault_file(os.path.join(folder, "gibtesnicht.json")), "   (erwartet: None)")