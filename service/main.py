import hmac

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from service.schemas import (Counts, Entry, EntryPage, EntryPatchList, Group, GroupPatch,
                             IdList, ImportData, Sealed, SortKey, VaultInfo, VaultUpdate)
from service.store import Conflict, NotFound

MAX_PAGE = 1000


def create_app(store, token):
    # store und token werden hineingegeben: im Programm die echten, im Test Attrappen
    app = FastAPI(title="Zwischenablagen Entry-Service", version="1")

    # liest "Authorization: Bearer <token>" und zeigt in /docs den Knopf "Authorize"
    bearer = HTTPBearer(auto_error=False)

    def require_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        given = credentials.credentials if credentials else ""
        # compare_digest braucht immer gleich lang, egal wo der erste Unterschied liegt
        if not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiges oder fehlendes Token")

    api = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])

    # Ohne Token: nur zum Prüfen, ob der Service läuft

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Tresor

    @api.get("/vault", response_model=VaultInfo)
    def get_vault():
        return store.get_vault()

    @api.put("/vault", status_code=status.HTTP_204_NO_CONTENT)
    def put_vault(update: VaultUpdate):
        store.put_vault(update.header, update.default_group)

    @api.post("/import", status_code=status.HTTP_204_NO_CONTENT)
    def import_all(content: ImportData):
        store.import_all(content.model_dump())

    # Gruppen

    @api.get("/groups", response_model=list[Group])
    def list_groups():
        return store.list_groups()

    @api.post("/groups", response_model=Group, status_code=status.HTTP_201_CREATED)
    def add_group(group: Group):
        try:
            return store.add_group(group.model_dump())
        except Conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Gruppe existiert bereits")

    @api.patch("/groups/{group_id}", response_model=Group)
    def patch_group(group_id: str, changes: GroupPatch):
        try:
            return store.patch_group(group_id, changes.model_dump(exclude_unset=True))
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Gruppe nicht gefunden")

    @api.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_group(group_id: str):
        try:
            store.delete_group(group_id)
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Gruppe nicht gefunden")
        except Conflict as error:
            raise HTTPException(status.HTTP_409_CONFLICT, str(error))

    # Einträge

    @api.get("/entries", response_model=EntryPage)
    def list_entries(
        group_id: str | None = None,
        favorites_only: bool = False,
        content_hash: str | None = None,
        sort: SortKey = "priority",
        descending: bool = False,
        offset: int = Query(0, ge=0),
        limit: int | None = Query(None, ge=1, le=MAX_PAGE),
    ):
        total, items = store.list_entries(group_id, favorites_only, content_hash,
                                          sort, descending, offset, limit)
        return {"total": total, "items": items}

    @api.get("/entries/{entry_id}/content", response_model=Sealed | None)
    def get_content(entry_id: str):
        try:
            return store.get_content(entry_id)
        except NotFound:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Eintrag nicht gefunden")

    @api.post("/entries", response_model=Entry, status_code=status.HTTP_201_CREATED)
    def add_entry(entry: Entry):
        try:
            return store.add_entry(entry.model_dump())
        except Conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Eintrag existiert bereits")

    @api.patch("/entries", response_model=list[Entry])
    def patch_entries(changes: EntryPatchList):
        updates = [update.model_dump(exclude_unset=True) for update in changes.updates]
        try:
            return store.patch_entries(updates)
        except NotFound as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Eintrag {error} nicht gefunden")

    @api.post("/entries/delete")
    def delete_entries(request: IdList):
        return {"deleted": store.delete_entries(request.ids)}

    @api.get("/counts", response_model=Counts)
    def counts():
        total, groups = store.counts()
        return {"total": total, "groups": {key or "": value for key, value in groups.items()}}

    app.include_router(api)
    return app