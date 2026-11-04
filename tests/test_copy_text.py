from history import ClipboardHistory
from models import EntryKind
from viewmodel import ClipboardViewModel


class FakeService:
    def __init__(self):
        self.copied = []

    def set_text(self, text, sensitive=False):
        self.copied.append((text, sensitive))


def make_vm():
    vm = ClipboardViewModel(ClipboardHistory())
    vm.service = FakeService()
    return vm


def test_copy_text_sends_to_service():
    vm = make_vm()
    vm.copy_text("daniel")
    assert vm.service.copied == [("daniel", False)]


def test_copy_text_ignores_empty():
    vm = make_vm()
    vm.copy_text("")
    assert vm.service.copied == []


def test_copy_password_is_sensitive_and_order_stays():
    vm = make_vm()
    first = vm.history.add_item("Hallo")
    secret = vm.history.add_item("Geheim", kind=EntryKind.PASSWORD)
    order = list(vm.get_visible_items())

    vm.copy(first)
    vm.copy(secret)

    assert vm.service.copied == [("Hallo", False), ("Geheim", True)]
    assert vm.get_visible_items() == order   # eigene Kopien verändern die Reihenfolge nicht
