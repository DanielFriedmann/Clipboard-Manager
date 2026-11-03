from history import ClipboardHistory
from repository import EntryRepository
from viewmodel import ClipboardViewModel


def test_history_fulfils_interface():
    # schlägt mit TypeError fehl, wenn eine Methode fehlt
    history = ClipboardHistory()
    assert isinstance(history, EntryRepository)


def test_visible_items_are_cached_until_change():
    vm = ClipboardViewModel(ClipboardHistory())
    first = vm.get_visible_items()
    assert vm.get_visible_items() is first      # dieselbe Liste, nicht neu berechnet

    vm.set_search("x")
    assert vm.get_visible_items() is not first  # nach einer Änderung neu


def test_delete_checked_removes_marks():
    history = ClipboardHistory()
    a = history.add_item("a")
    b = history.add_item("b")
    vm = ClipboardViewModel(history)
    vm.toggle_checked(a)
    vm.toggle_checked(b)

    vm.delete_checked()

    assert history.count() == 0
    assert vm.checked == set()


def test_position_counts_in_visible_list():
    history = ClipboardHistory()
    group = history.add_group("Arbeit")
    a = history.add_item("a")
    history.add_item("b")
    history.assign_items_to_group([a], group)
    vm = ClipboardViewModel(history)

    vm.select_group(group)
    assert vm.position(a) == 1


def test_count_per_group():
    history = ClipboardHistory()
    group = history.add_group("Arbeit")
    a = history.add_item("a")
    history.add_item("b")
    history.assign_items_to_group([a], group)

    assert history.count() == 2
    assert history.count(group) == 1


if __name__ == "__main__":
    test_history_fulfils_interface()
    test_visible_items_are_cached_until_change()
    test_delete_checked_removes_marks()
    test_position_counts_in_visible_list()
    test_count_per_group()
    print("alle Tests ok")