import unittest
from types import SimpleNamespace

from history import ClipboardHistory
from viewmodel import ClipboardViewModel


def capture(text):
    # wie ClipboardCapture, aber ohne die Windows-Module zu laden
    return SimpleNamespace(text=text, is_sensitive=False, source_app=None)


class FakeService:
    paused = False


class CaptureToggleTest(unittest.TestCase):
    def setUp(self):
        self.history = ClipboardHistory()
        self.vm = ClipboardViewModel(self.history)
        self.service = FakeService()
        self.vm.service = self.service

    def test_enabled_by_default(self):
        self.assertTrue(self.vm.capture_enabled)
        self.assertFalse(self.service.paused)

    def test_paused_ignores_new_copies(self):
        self.vm.set_capture_enabled(False)
        self.vm.receive_capture(capture("geheim"))
        self.vm.process_incoming()
        self.assertEqual(self.history.count(), 0)
        self.assertTrue(self.service.paused)

    def test_pausing_discards_copies_still_in_queue(self):
        self.vm.receive_capture(capture("kam kurz vor der Pause"))
        self.vm.set_capture_enabled(False)
        self.vm.set_capture_enabled(True)
        self.vm.process_incoming()
        self.assertEqual(self.history.count(), 0)

    def test_resume_records_again(self):
        self.vm.set_capture_enabled(False)
        self.vm.toggle_capture()
        self.vm.receive_capture(capture("wieder da"))
        self.vm.process_incoming()
        self.assertEqual(self.history.count(), 1)
        self.assertFalse(self.service.paused)

    def test_service_set_later_takes_current_state(self):
        # Einstellungen werden geladen, bevor der Service zugewiesen ist
        vm = ClipboardViewModel(ClipboardHistory())
        vm.set_capture_enabled(False)
        service = FakeService()
        vm.service = service
        self.assertTrue(service.paused)

    def test_toggle_notifies_listeners(self):
        calls = []
        self.vm.subscribe(lambda: calls.append(True))
        self.vm.toggle_capture()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
