from typing import Literal

from pydantic import BaseModel, Field

# Beschreibung der Daten, die über die API gehen.
# FastAPI prüft jede Anfrage dagegen und antwortet bei Fehlern mit 422.


class Sealed(BaseModel):
    # ein verschlüsselter Block, für den Service nur Zeichenketten
    nonce: str
    data: str


class VaultInfo(BaseModel):
    header: dict | None = None          # eingepackte Schlüssel, Inhalt kennt nur die App
    default_group: str | None = None
    version: int = 3
    legacy_payload: Sealed | None = None   # nur bei einer alten Datei (Version 2)


class VaultUpdate(BaseModel):
    header: dict
    default_group: str | None = None


class Group(BaseModel):
    id: str
    color: str
    position: float
    name: Sealed


class GroupPatch(BaseModel):
    color: str | None = None
    position: float | None = None
    name: Sealed | None = None


class Entry(BaseModel):
    # offen: damit filtert und sortiert der Service
    id: str
    group: str | None = None
    format: str = "TEXT"
    created_at: str
    is_favorite: bool = False
    position: float = 0.0
    kind: str = "text"
    needs_review: bool = False
    content_hash: str
    # verschlüsselt
    details: Sealed | None = None
    content: Sealed | None = None


class EntryPatch(BaseModel):
    id: str
    group: str | None = None
    created_at: str | None = None
    is_favorite: bool | None = None
    position: float | None = None
    kind: str | None = None
    needs_review: bool | None = None
    content_hash: str | None = None
    details: Sealed | None = None
    content: Sealed | None = None


class EntryPatchList(BaseModel):
    updates: list[EntryPatch]


class IdList(BaseModel):
    ids: list[str]


class EntryPage(BaseModel):
    total: int            # Treffer insgesamt, nicht nur auf dieser Seite
    items: list[Entry]


class Counts(BaseModel):
    total: int
    groups: dict[str, int]


class ImportData(BaseModel):
    # ganzer Bestand auf einmal, z. B. bei der Umwandlung einer alten Datei
    header: dict
    default_group: str | None = None
    groups: list[Group] = Field(default_factory=list)
    items: list[Entry] = Field(default_factory=list)


SortKey = Literal["priority", "time", "favorite"]