from datetime import datetime

from history import ClipboardHistory
from storage import history_from_dict, history_to_dict


def make_history(*texts):
    history = ClipboardHistory()
    for text in reversed(texts):      # add_item setzt nach oben
        history.add_item(text)
    return history


def contents(history):
    return [item.content for item in history.history]


def test_new_item_goes_to_top():
    history = make_history("b", "c")
    history.add_item("a")
    assert contents(history) == ["a", "b", "c"]
    positions = [item.position for item in history.history]
    assert positions == sorted(positions)


def test_move_between_changes_only_one_position():
    history = make_history("a", "b", "c")
    a, b, c = history.history
    before = (a.position, b.position)

    history.move_item(c, b)             # c vor b

    assert contents(history) == ["a", "c", "b"]
    assert (a.position, b.position) == before
    assert a.position < c.position < b.position


def test_renumber_when_gap_is_used_up():
    history = make_history("a", "b", "c")
    a, b, c = history.history
    # 100-mal in dieselbe Lücke direkt hinter a schieben
    for _ in range(100):
        history.move_item(c, a, after=True)
        history.move_item(b, a, after=True)

    positions = [item.position for item in history.history]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(positions)   # keine doppelten


def test_old_file_keeps_order():
    data = {
        "items": [
            {"content": text, "format": "TEXT", "group": None,
             "created_at": datetime.now().isoformat()}
            for text in ("erster", "zweiter", "dritter")
        ],
    }
    assert contents(history_from_dict(data)) == ["erster", "zweiter", "dritter"]


def test_round_trip_keeps_order_after_move():
    history = make_history("a", "b", "c")
    history.move_item(history.history[2], None)   # c ans Ende (bleibt)
    history.move_item(history.history[0], None)   # a ans Ende
    loaded = history_from_dict(history_to_dict(history))
    assert contents(loaded) == ["b", "c", "a"]


if __name__ == "__main__":
    test_new_item_goes_to_top()
    test_move_between_changes_only_one_position()
    test_renumber_when_gap_is_used_up()
    test_old_file_keeps_order()
    test_round_trip_keeps_order_after_move()
    print("alle Tests ok")