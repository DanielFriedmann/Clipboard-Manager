import unittest
from unittest import mock

from history import ClipboardHistory
from models import EntryKind
from viewmodel import ClipboardViewModel


class HistoryEditTest(unittest.TestCase):
    def setUp(self):
        self.history = ClipboardHistory()
        self.vm = ClipboardViewModel(self.history)
        self.second = self.history.add_item("zweiter")
        self.item = self.history.add_item("alter Text")

    def test_changes_title_and_content(self):
        self.vm.edit(self.item, "Notiz", content="neuer Text")
        self.assertEqual(self.item.title, "Notiz")
        self.assertEqual(self.item.content, "neuer Text")

    def test_keeps_position_time_and_group(self):
        position, created, group = self.item.position, self.item.created_at, self.item.clipboard_group
        self.vm.edit(self.item, "", content="neuer Text")
        self.assertEqual((self.item.position, self.item.created_at, self.item.clipboard_group),
                         (position, created, group))
        self.assertEqual(self.history.get_history()[0], self.item)

    def test_content_none_keeps_content(self):
        self.vm.edit(self.item, "Nur Name")
        self.assertEqual(self.item.content, "alter Text")

    def test_empty_content_is_not_saved(self):
        self.vm.edit(self.item, "Name", content="   ")
        self.assertEqual(self.item.content, "alter Text")
        self.assertEqual(self.item.title, "Name")

    def test_text_becomes_link_and_back(self):
        self.vm.edit(self.item, "", content="https://abkoo.de")
        self.assertEqual(self.item.kind, EntryKind.LINK)
        self.vm.edit(self.item, "", content="kein Link mehr")
        self.assertEqual(self.item.kind, EntryKind.TEXT)

    def test_password_stays_password(self):
        password = self.history.add_item("geheim", kind=EntryKind.PASSWORD, needs_review=True)
        self.vm.edit(password, "VPN", "max", "vpn.firma.de", content="https://neu")
        self.assertTrue(password.is_password)
        self.assertEqual(password.content, "https://neu")
        self.assertFalse(password.needs_review)

    def test_duplicate_content_is_allowed(self):
        self.vm.edit(self.item, "", content="zweiter")
        self.assertEqual(self.history.count(), 2)


class FakeVault:
    def content_hash(self, text):
        return f"hash:{text}"


class FakeApi:
    def __init__(self):
        self.patches = []

    def get(self, path, **kwargs):
        if path == "/v1/vault":
            return {"default_group": "g1"}
        if path == "/v1/groups":
            return [{"id": "g1", "name": "x", "color": "#9e9e9e", "position": 0.0}]
        raise AssertionError(path)

    def patch(self, path, json):
        self.patches.append(json["updates"])


def fake_seal(vault, text, label):
    return {"nonce": label, "data": text}


def fake_unseal(vault, sealed, label):
    return sealed if isinstance(sealed, str) else sealed["data"]


@mock.patch("api_repository._seal", fake_seal)
@mock.patch("api_repository._unseal", fake_unseal)
class ApiRepositoryEditTest(unittest.TestCase):
    def make(self, kind=EntryKind.TEXT, content="alt"):
        from api_repository import ApiRepository
        from models import ClipboardFormat, ClipboardItem
        api = FakeApi()
        repository = ApiRepository(api, FakeVault())
        item = ClipboardItem(clipboard_format=ClipboardFormat.TEXT, content=content, kind=kind)
        return api, repository, item

    def test_sends_one_patch_with_new_content_and_hash(self):
        api, repository, item = self.make()
        repository.edit_item(item, "Titel", content="https://neu.de")
        self.assertEqual(len(api.patches), 1)
        update = api.patches[0][0]
        self.assertEqual(update["content"]["data"], "https://neu.de")
        self.assertEqual(update["content"]["nonce"], f"item:{item.id}:content")
        self.assertEqual(update["content_hash"], "hash:https://neu.de")
        self.assertEqual(update["kind"], "link")
        self.assertNotIn("position", update)
        self.assertNotIn("created_at", update)

    def test_only_name_sends_no_content(self):
        api, repository, item = self.make()
        repository.edit_item(item, "Titel")
        update = api.patches[0][0]
        self.assertNotIn("content", update)
        self.assertNotIn("content_hash", update)

    def test_password_plaintext_is_not_kept(self):
        api, repository, item = self.make(EntryKind.PASSWORD, content=None)
        repository.edit_item(item, "VPN", "max", "", content="neues-geheimnis")
        update = api.patches[0][0]
        self.assertEqual(update["content"]["data"], "neues-geheimnis")
        self.assertNotIn("kind", update)
        self.assertIsNone(item.content)


if __name__ == "__main__":
    unittest.main()
