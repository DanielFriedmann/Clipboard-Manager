import hashlib
import json
import os
import tempfile

from history import ClipboardHistory
from models import EntryKind
from storage import (history_to_dict, load_encrypted, read_vault_file,
                     save_encrypted)
from vault import Vault

PASSWORD = "testpasswort"

# Scrypt ist absichtlich langsam, deshalb nur einmal für alle Tests
VAULT, _ = Vault.create(PASSWORD)


def make_history():
    history = ClipboardHistory()
    group = history.add_group("Kunde Müller", "#ff0000")
    text = history.add_item("Hallo Welt")
    secret = history.add_item("geheim123", kind=EntryKind.PASSWORD)
    history.rename_item(secret, "VPN-Portal", "daniel", "https://vpn.firma.de")
    history.assign_items_to_group([text], group)
    return history


def save_and_read(history):
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "vault.json")
    save_encrypted(history, VAULT, path)
    return path, read_vault_file(path)


def test_round_trip():
    history = make_history()
    path, content = save_and_read(history)

    # neu anmelden wie beim Programmstart
    vault = Vault.unlock(content["vault"], PASSWORD)
    loaded = load_encrypted(content, vault, path)

    assert [i.content for i in loaded.history] == [i.content for i in history.history]
    assert [g.name for g in loaded.groups] == [g.name for g in history.groups]
    secret = next(i for i in loaded.history if i.is_password)
    assert secret.title == "VPN-Portal"
    assert secret.username == "daniel"
    assert secret.url == "https://vpn.firma.de"
    assert loaded.history[0].clipboard_group.name == "Kunde Müller"


def test_file_contains_no_plaintext():
    path, _content = save_and_read(make_history())
    with open(path, encoding="utf-8") as file:
        text = file.read()
    for secret in ("geheim123", "Hallo Welt", "VPN-Portal", "daniel", "Kunde Müller"):
        assert secret not in text


def test_swapped_blocks_are_detected():
    _path, content = save_and_read(make_history())
    first, second = content["items"][0], content["items"][1]
    first["content"], second["content"] = second["content"], first["content"]
    try:
        load_encrypted(content, VAULT, os.devnull)
    except ValueError:
        return
    raise AssertionError("vertauschte Blöcke wurden nicht erkannt")


def test_content_hash():
    assert VAULT.content_hash("abc") == VAULT.content_hash("abc")
    assert VAULT.content_hash("abc") != VAULT.content_hash("abd")
    # nicht einfach SHA-256, sonst könnte man häufige Passwörter nachrechnen
    assert VAULT.content_hash("abc") != hashlib.sha256(b"abc").hexdigest()


def test_version_2_is_converted():
    history = make_history()
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "vault.json")
    plain = json.dumps(history_to_dict(history), ensure_ascii=False).encode("utf-8")
    old = {"version": 2, "vault": VAULT.header, "payload": VAULT.encrypt(plain)}
    with open(path, "w", encoding="utf-8") as file:
        json.dump(old, file)

    loaded = load_encrypted(read_vault_file(path), VAULT, path)
    assert os.path.exists(path + ".v2-backup")
    assert [i.content for i in loaded.history] == [i.content for i in history.history]

    save_encrypted(loaded, VAULT, path)
    assert read_vault_file(path)["version"] == 3


if __name__ == "__main__":
    test_round_trip()
    test_file_contains_no_plaintext()
    test_swapped_blocks_are_detected()
    test_content_hash()
    test_version_2_is_converted()
    print("alle Tests ok")