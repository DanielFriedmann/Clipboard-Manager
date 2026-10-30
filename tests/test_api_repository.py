import os
import tempfile

from fastapi.testclient import TestClient

from api_client import ApiClient
from api_repository import ApiRepository, push_to_service
from clipboard_service import ClipboardCapture
from history import ClipboardHistory
from models import EntryKind
from service.main import create_app
from service.store import EntryStore
from vault import Vault
from viewmodel import ClipboardViewModel

TOKEN = "test-token"
VAULT, _ = Vault.create("testpasswort")   # Scrypt ist langsam, nur einmal


def make_repository(history=None):
    path = os.path.join(tempfile.mkdtemp(), "vault.json")
    app = create_app(EntryStore(path), TOKEN)
    api = ApiClient(TOKEN, client=TestClient(app))
    push_to_service(api, VAULT, history or ClipboardHistory())
    return ApiRepository(api, VAULT), api, path


def contents(items):
    return [item.content for item in items]


def test_existing_data_is_taken_over():
    history = ClipboardHistory()
    group = history.add_group("Arbeit")
    a = history.add_item("a")
    history.add_item("b")
    history.assign_items_to_group([a], group)

    repo, _api, _path = make_repository(history)

    assert [g.name for g in repo.list_groups()] == ["Unsortiert", "Arbeit"]
    assert contents(repo.get_history()) == ["a", "b"]
    arbeit = repo.list_groups()[1]
    assert contents(repo.get_history(group=arbeit)) == ["a"]
    assert repo.count() == 2
    assert repo.count(arbeit) == 1


def test_add_new_on_top_and_duplicates():
    repo, _api, _path = make_repository()
    repo.add_item("erster")
    repo.add_item("zweiter")
    again = repo.add_item("erster")

    assert contents(repo.get_history()) == ["zweiter", "erster"]
    assert again is repo.get_history()[1]        # dasselbe Objekt wiederverwendet
    assert repo.count() == 2


def test_password_content_only_on_request():
    repo, api, _path = make_repository()
    secret = repo.add_item("geheim123", kind=EntryKind.PASSWORD, needs_review=True)

    assert secret.content is None
    listed = repo.get_history()[0]
    assert listed.is_password and listed.content is None
    assert repo.get_content(listed) == "geheim123"
    assert listed.content is None               # nicht im Objekt behalten

    raw = api.get("/v1/entries")["items"][0]
    assert raw["content"] is None               # auch über die API nicht in der Liste


def test_changes_survive_new_session():
    repo, api, _path = make_repository()
    group = repo.add_group("Kunde Müller", "#ff0000")
    item = repo.add_item("geheim", kind=EntryKind.PASSWORD)
    repo.rename_item(item, "VPN", "daniel", "https://vpn.firma.de")
    repo.toggle_favorite(item)
    repo.assign_items_to_group([item], group)

    fresh = ApiRepository(api, VAULT)   # wie ein Neustart der App
    loaded = fresh.get_history()[0]
    assert loaded.title == "VPN"
    assert loaded.username == "daniel"
    assert loaded.url == "https://vpn.firma.de"
    assert loaded.is_favorite
    assert loaded.clipboard_group.name == "Kunde Müller"
    assert not loaded.needs_review


def test_move_and_search():
    repo, _api, _path = make_repository()
    for text in ("c", "b", "a"):
        repo.add_item(text)
    a, b, c = repo.get_history()
    repo.move_item(c, a)                         # c vor a

    assert contents(repo.get_history()) == ["c", "a", "b"]
    assert contents(repo.get_history(search="b")) == ["b"]


def test_mark_password_and_back():
    repo, _api, _path = make_repository()
    item = repo.add_item("https://firma.de", kind=EntryKind.LINK)
    repo.mark_password(item, True)
    assert repo.get_history()[0].content is None

    repo.mark_password(item, False)
    assert item.kind == EntryKind.LINK
    assert repo.get_history()[0].content == "https://firma.de"


def test_remove_and_groups():
    repo, _api, _path = make_repository()
    group = repo.add_group("Arbeit")
    item = repo.add_item("x")
    repo.assign_items_to_group([item], group)
    repo.remove_group(group)

    assert repo.get_history()[0].clipboard_group is repo.get_default_group()
    repo.remove_items(repo.get_history())
    assert repo.count() == 0


def test_file_has_no_plaintext():
    repo, _api, path = make_repository()
    repo.add_group("Kunde Müller")
    repo.rename_item(repo.add_item("Hallo Welt"), "Begrüßung")
    with open(path, encoding="utf-8") as file:
        text = file.read()
    for secret in ("Kunde Müller", "Hallo Welt", "Begrüßung"):
        assert secret not in text


class FakeClipboard:
    def __init__(self):
        self.calls = []

    def set_text(self, text, sensitive=False):
        self.calls.append((text, sensitive))


def test_viewmodel_works_with_api_repository():
    repo, _api, _path = make_repository()
    vm = ClipboardViewModel(repo)
    vm.service = FakeClipboard()
    vm.receive_capture(ClipboardCapture("geheim", is_sensitive=True, source_app="KeePass"))
    vm.receive_capture(ClipboardCapture("Hallo"))
    vm.process_incoming()

    secret = next(item for item in vm.get_visible_items() if item.is_password)
    vm.copy(secret)
    assert vm.service.calls == [("geheim", True)]
    assert vm.group_count(None) == 2

    vm.toggle_checked(secret)
    vm.delete_checked()
    assert vm.count_text == "1 Eintrag"