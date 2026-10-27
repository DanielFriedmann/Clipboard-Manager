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


if __name__ == "__main__":
    test_guess_kind()
    test_round_trip_keeps_new_fields()
    test_old_entry_without_new_fields()
    test_unknown_kind_falls_back_to_text()
    print("alle Tests ok")