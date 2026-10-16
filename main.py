from clipboard_service import ClipboardService
from history import ClipboardHistory

history = ClipboardHistory()


def on_new_text(text):
    history.add_item(text)
    history.print_history()


service = ClipboardService(on_new_text)
service.start()