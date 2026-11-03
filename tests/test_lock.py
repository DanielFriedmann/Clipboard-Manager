import os
import tempfile

from fastapi.testclient import TestClient

from api_client import ApiClient
from api_repository import ApiRepository, import_history
from clipboard_service import ClipboardCapture
from history import ClipboardHistory
from models import EntryKind
from service.main import create_app
from service.store import EntryStore
from vault import Vault
from viewmodel import ClipboardViewModel

TOKEN = "test-token"
PASSWORD = "testpasswort"
VAULT, _ = Vault.create(PASSWORD)


def make_api():
    path = os.path.join(tempfile.mkdtemp(), "vault.json")
    api = ApiClient(TOKEN, client=TestClient(create_app(EntryStore(path), TOKEN)))
    import_history(api, VAULT, ClipboardHistory())
    return api


def test_lock_forgets_everything_and_unlock_restores():
    api = make_api()
    # eigenes Tresor-Objekt: close() sperrt es, VAULT brauchen die anderen Tests noch
    repo = ApiRepository(api, Vault.unlock(api.get("/v1/vault")["header"], PASSWORD))
    group = repo.add_group("Arbeit")
    item = repo.add_item("geheim", kind=EntryKind.PASSWORD)
    repo.rename_item(item, "VPN", "daniel")
    repo.assign_items_to_group([item], group)

    vm = ClipboardViewModel(repo)
    vm.select_group(group)
    vm.set_search("vp")
    calls = []
    vm.subscribe(lambda: calls.append(vm.locked))

    vm.lock()
    repo.close()
    assert vm.locked and vm.history is None and vm.search == ""
    assert item.title is None and item.username is None
    assert repo.vault._dek is None
    assert calls[-1] is True
    assert vm.selected_group_id == group.id      # gemerkt für danach

    # entsperren mit neuem Tresor-Objekt aus dem Passwort
    vault = Vault.unlock(api.get("/v1/vault")["header"], PASSWORD)
    vm.unlock(ApiRepository(api, vault))
    assert not vm.locked
    assert vm.selected_group.name == "Arbeit"
    assert [i.title for i in vm.get_visible_items()] == ["VPN"]


def test_repository_close_locks_vault():
    api = make_api()
    vault = Vault.unlock(api.get("/v1/vault")["header"], PASSWORD)
    repo = ApiRepository(api, vault)
    repo.close()
    assert vault._dek is None
    assert repo.list_groups() == []


def test_nothing_collected_while_locked():
    history = ClipboardHistory()
    vm = ClipboardViewModel(history)
    vm.lock()
    vm.receive_capture(ClipboardCapture("während gesperrt"))
    vm.process_incoming()
    vm.unlock(history)
    assert history.count() == 0