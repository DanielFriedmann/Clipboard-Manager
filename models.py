from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class ClipboardFormat(Enum):
    TEXT = 1
    IMAGE = 2
    FILES = 3

@dataclass(eq=False)
class ClipboardGroup:
    name: str
    color: str = "#9e9e9e"  # Defaultfarbe Grau

@dataclass(eq=False)
class ClipboardItem:
    clipboard_format: ClipboardFormat
    content: str
    clipboard_group: ClipboardGroup | None = None
    created_at: datetime = field(default_factory = datetime.now)
    is_pinned: bool = False


