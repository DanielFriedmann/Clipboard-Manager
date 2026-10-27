from datetime import datetime

from history import ClipboardHistory
from models import ClipboardFormat, ClipboardItem, EntryKind, guess_kind
from storage import history_from_dict, history_to_dict


def test_guess_kind():
    assert guess_kind("https://example.com") == EntryKind.LINK
    assert guess_kind("  www.firma.de  ") == EntryKind.LINK
    assert guess_kind("www.firma.de hat neue Zeiten") == EntryKind.TEXT
    assert guess_kind("Hallo Welt") == EntryKind.TEXT


def test_round_trip_keeps_new_fields():
    history = ClipboardHistory()
    item = ClipboardItem(ClipboardFormat.TEXT, "geheim123",
                         clipboard_group=history.default_group,
                         kind=EntryKind.PASSWORD, title="VPN-Portal",
                         username="daniel", source_app="KeePass",
                         needs_review=True)
    history.history.append(item)

    loaded = history_from_dict(history_to_dict(history)).history[0]

    assert loaded.id == item.id
    assert loaded.is_password
    assert loaded.title == "VPN-Portal"
    assert loaded.username == "daniel"
    assert loaded.source_app == "KeePass"
    assert loaded.needs_review


def test_old_entry_without_new_fields():
    data = {
        "items": [
            {"content": "https://alt.de", "format": "TEXT", "group": None,
             "created_at": datetime.now().isoformat()},
        ],
    }
    loaded = history_from_dict(data).history[0]

    assert loaded.kind == EntryKind.LINK
    assert loaded.title is None
    assert loaded.id


def test_unknown_kind_falls_back_to_text():
    data = {
        "items": [
            {"content": "x", "format": "TEXT", "group": None,
             "created_at": datetime.now().isoformat(), "kind": "zukunft"},
        ],
    }
    assert history_from_dict(data).history[0].kind == EntryKind.TEXT


def test_add_password():
    history = ClipboardHistory()
    item = history.add_item("geheim", kind=EntryKind.PASSWORD,
                            source_app="KeePass", needs_review=True)

    assert item.is_password
    assert item.source_app == "KeePass"
    assert item.needs_review


def test_existing_text_becomes_password():
    history = ClipboardHistory()
    history.add_item("geheim")
    item = history.add_item("geheim", kind=EntryKind.PASSWORD, needs_review=True)

    assert len(history.history) == 1
    assert item.is_password
    assert item.needs_review


def test_password_keeps_its_data():
    history = ClipboardHistory()
    item = history.add_item("geheim", kind=EntryKind.PASSWORD,
                            source_app="KeePass", needs_review=True)
    item.title = "VPN-Portal"
    item.needs_review = False

    # zurückkopiert aus dem eigenen Manager: ohne Quelle, ohne Signal
    history.add_item("geheim")

    assert item.is_password
    assert item.title == "VPN-Portal"
    assert not item.needs_review
    assert item.source_app == "KeePass"


if __name__ == "__main__":
    test_guess_kind()
    test_round_trip_keeps_new_fields()
    test_old_entry_without_new_fields()
    test_unknown_kind_falls_back_to_text()
    test_add_password()
    test_existing_text_becomes_password()
    test_password_keeps_its_data()
    print("alle Tests ok")