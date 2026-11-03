import json
import os
import tempfile

from fastapi.testclient import TestClient

import storage
import pytest
from api_client import ApiClient
from history import ClipboardHistory
from service.main import create_app
from service.store import EntryStore
from startup import (change_vault_password, open_api_data, prepare_new_recovery,
                     read_header_from_service, save_header)
from storage import history_to_dict
from vault import Vault, WrongPassword

TOKEN = "test-token"
PASSWORD = "testpasswort"
VAULT, _ = Vault.create(PASSWORD)


def make_api(file_content=None):
    folder = tempfile.mkdtemp()
    path = os.path.join(folder, "vault.json")
    if file_content is not None:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(file_content, file)
    api = ApiClient(TOKEN, client=TestClient(create_app(EntryStore(path), TOKEN)))
    return api, path


def no_legacy(monkeypatch):
    # keine alte data.json aus Version 1.1 im Test
    monkeypatch.setattr(storage, "DATA_FILE", os.path.join(tempfile.mkdtemp(), "data.json"))


def test_new_vault(monkeypatch):
    no_legacy(monkeypatch)
    api, path = make_api()
    assert read_header_from_service(api) is None

    repo = open_api_data(api, VAULT, is_new=True, header_changed=False, backup_path=path)
    repo.add_item("Hallo")

    assert read_header_from_service(api) == VAULT.header
    assert [g.name for g in repo.list_groups()] == ["Unsortiert"]


def test_old_file_is_converted(monkeypatch):
    no_legacy(monkeypatch)
    history = ClipboardHistory()
    history.add_group("Arbeit")
    history.add_item("alter Eintrag")
    plain = json.dumps(history_to_dict(history), ensure_ascii=False).encode("utf-8")
    api, path = make_api({"version": 2, "vault": VAULT.header, "payload": VAULT.encrypt(plain)})

    vault = Vault.unlock(read_header_from_service(api), PASSWORD)
    repo = open_api_data(api, vault, is_new=False, header_changed=False, backup_path=path)

    assert [i.content for i in repo.get_history()] == ["alter Eintrag"]
    assert api.get("/v1/vault")["version"] == 3
    assert os.path.exists(path + ".v2-backup")


def test_new_password_after_recovery(monkeypatch):
    no_legacy(monkeypatch)
    vault, code = Vault.create(PASSWORD)
    api, path = make_api()
    open_api_data(api, vault, is_new=True, header_changed=False, backup_path=path).add_item("x")

    # wie "Passwort vergessen": mit dem Schlüssel öffnen und neues Passwort setzen
    recovered = Vault.unlock_with_recovery(read_header_from_service(api), code)
    recovered.change_password("neuespasswort")
    open_api_data(api, recovered, is_new=False, header_changed=True, backup_path=path)

    again = Vault.unlock(read_header_from_service(api), "neuespasswort")
    repo = open_api_data(api, again, is_new=False, header_changed=False, backup_path=path)
    assert [i.content for i in repo.get_history()] == ["x"]

def test_change_password(monkeypatch):
    no_legacy(monkeypatch)
    api, path = make_api()
    vault, _ = Vault.create(PASSWORD)
    open_api_data(api, vault, is_new=True, header_changed=False, backup_path=path)
    old_header = vault.header

    with pytest.raises(WrongPassword):
        change_vault_password(api, old_header, "falsch", "neuespasswort")

    new_header = change_vault_password(api, old_header, PASSWORD, "neuespasswort")
    assert read_header_from_service(api) == new_header
    assert old_header["password"] != new_header["password"]   # Original unverändert
    assert new_header["recovery"] == old_header["recovery"]   # Wiederherstellung gilt weiter

    with pytest.raises(WrongPassword):
        Vault.unlock(new_header, PASSWORD)
    Vault.unlock(new_header, "neuespasswort")    

def test_new_recovery_code(monkeypatch):
    no_legacy(monkeypatch)
    api, path = make_api()
    vault, old_code = Vault.create(PASSWORD)
    open_api_data(api, vault, is_new=True, header_changed=False, backup_path=path)
    old_header = vault.header

    with pytest.raises(WrongPassword):
        prepare_new_recovery(old_header, "falsch")

    new_header, new_code = prepare_new_recovery(old_header, PASSWORD)
    assert new_code != old_code
    assert read_header_from_service(api) == old_header   # noch nichts gespeichert

    save_header(api, new_header)
    assert read_header_from_service(api) == new_header

    with pytest.raises(WrongPassword):
        Vault.unlock_with_recovery(new_header, old_code)   # alter Schlüssel ungültig
    Vault.unlock_with_recovery(new_header, new_code.lower())   # Schreibweise egal
    Vault.unlock(new_header, PASSWORD)                         # Passwort gilt weiter