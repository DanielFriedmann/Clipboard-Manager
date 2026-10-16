from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class ClipboardFormat(Enum):
    TEXT = 1
    IMAGE = 2
    FILES = 3

@dataclass
class ClipboardItem:
    clipboard_format: ClipboardFormat
    content: str
    created_at: datetime = field(default_factory = datetime.now)
    is_pinned: bool = False


