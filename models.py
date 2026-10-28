from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

import uuid

class ClipboardFormat(Enum):
    TEXT = 1
    IMAGE = 2
    FILES = 3

class EntryKind(Enum):
    TEXT = "text"
    LINK = "link"
    PASSWORD = "password"


LINK_PREFIXES = ("http://", "https://", "www.")


def guess_kind(text: str) -> EntryKind:
    # Passwörter erkennt der Clipboard-Service am Signal, hier nur Text oder Link
    stripped = text.strip()
    if any(c.isspace() for c in stripped):
        return EntryKind.TEXT
    if stripped.lower().startswith(LINK_PREFIXES):
        return EntryKind.LINK
    return EntryKind.TEXT

@dataclass(eq=False)
class ClipboardGroup:
    name: str
    color: str = "#9e9e9e"  # Defaultfarbe Grau
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

@dataclass(eq=False)
class ClipboardItem:
    clipboard_format: ClipboardFormat
    content: str
    clipboard_group: ClipboardGroup | None = None
    created_at: datetime = field(default_factory = datetime.now)
    is_favorite: bool = False
    kind: EntryKind = EntryKind.TEXT
    title: str | None = None
    username: str | None = None
    url: str | None = None
    source_app: str | None = None
    needs_review: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def is_password(self) -> bool:
        return self.kind == EntryKind.PASSWORD


