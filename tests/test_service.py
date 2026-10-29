import json
import os
import tempfile

from fastapi.testclient import TestClient

from service.main import create_app
from service.store import EntryStore

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
SEALED = {"nonce": "bm9uY2U=", "data": "ZGF0YQ=="}   # Attrappe, der Service prüft nicht


def make_client():
    path = os.path.join(tempfile.mkdtemp(), "vault.json")
    client = TestClient(create_app(EntryStore(path), TOKEN))
    client.put("/v1/vault", json={"header": {"kdf": {}}, "default_group": "g0"}, headers=AUTH)
    client.post("/v1/groups", json={"id": "g0", "color": "#9e9e9e", "position": 0, "name": SEALED},
                headers=AUTH)
    return client, path


def entry(entry_id, position, group="g0", kind="text", favorite=False):
    return {"id": entry_id, "group": group, "created_at": f"2026-10-29T10:00:0{int(position) % 10}",
            "is_favorite": favorite, "position": position, "kind": kind,
            "content_hash": f"h-{entry_id}", "details": SEALED, "content": SEALED}


def test_health_without_token():
    client, _path = make_client()
    assert client.get("/health").json() == {"status": "ok"}


def test_token_required():
    client, _path = make_client()
    assert client.get("/v1/groups").status_code == 401
    assert client.get("/v1/groups", headers={"Authorization": "Bearer falsch"}).status_code == 401
    assert client.get("/v1/groups", headers=AUTH).status_code == 200


def test_pagination_and_order():
    client, _path = make_client()
    for i in range(5):
        client.post("/v1/entries", json=entry(f"e{i}", float(i)), headers=AUTH)

    page = client.get("/v1/entries", params={"offset": 1, "limit": 2}, headers=AUTH).json()
    assert page["total"] == 5
    assert [item["id"] for item in page["items"]] == ["e1", "e2"]


def test_password_content_only_on_request():
    client, _path = make_client()
    client.post("/v1/entries", json=entry("pw", 0.0, kind="password"), headers=AUTH)

    listed = client.get("/v1/entries", headers=AUTH).json()["items"][0]
    assert listed["content"] is None
    assert listed["details"] is not None

    content = client.get("/v1/entries/pw/content", headers=AUTH).json()
    assert content == SEALED


def test_batch_patch_and_delete():
    client, _path = make_client()
    for i in range(3):
        client.post("/v1/entries", json=entry(f"e{i}", float(i)), headers=AUTH)

    result = client.patch("/v1/entries", json={"updates": [
        {"id": "e0", "is_favorite": True}, {"id": "e1", "group": "g1"}]}, headers=AUTH)
    assert result.status_code == 200

    favorites = client.get("/v1/entries", params={"favorites_only": True}, headers=AUTH).json()
    assert [item["id"] for item in favorites["items"]] == ["e0"]

    deleted = client.post("/v1/entries/delete", json={"ids": ["e0", "e2", "gibtsnicht"]},
                          headers=AUTH).json()
    assert deleted == {"deleted": 2}


def test_patch_unknown_changes_nothing():
    client, _path = make_client()
    client.post("/v1/entries", json=entry("e0", 0.0), headers=AUTH)
    result = client.patch("/v1/entries", json={"updates": [
        {"id": "e0", "is_favorite": True}, {"id": "fehlt", "is_favorite": True}]}, headers=AUTH)
    assert result.status_code == 404
    item = client.get("/v1/entries", headers=AUTH).json()["items"][0]
    assert item["is_favorite"] is False


def test_find_duplicate_by_hash():
    client, _path = make_client()
    client.post("/v1/entries", json=entry("e0", 0.0), headers=AUTH)
    found = client.get("/v1/entries", params={"content_hash": "h-e0"}, headers=AUTH).json()
    assert [item["id"] for item in found["items"]] == ["e0"]


def test_delete_group_moves_entries_to_default():
    client, _path = make_client()
    client.post("/v1/groups", json={"id": "g1", "color": "#ff0000", "position": 1, "name": SEALED},
                headers=AUTH)
    client.post("/v1/entries", json=entry("e0", 0.0, group="g1"), headers=AUTH)

    assert client.delete("/v1/groups/g0", headers=AUTH).status_code == 409
    assert client.delete("/v1/groups/g1", headers=AUTH).status_code == 204
    assert client.get("/v1/counts", headers=AUTH).json() == {"total": 1, "groups": {"g0": 1}}


def test_data_survives_restart():
    client, path = make_client()
    client.post("/v1/entries", json=entry("e0", 0.0), headers=AUTH)

    restarted = TestClient(create_app(EntryStore(path), TOKEN))
    assert restarted.get("/v1/entries", headers=AUTH).json()["total"] == 1


def test_invalid_request_is_rejected():
    client, _path = make_client()
    broken = entry("e0", 0.0)
    del broken["content_hash"]
    assert client.post("/v1/entries", json=broken, headers=AUTH).status_code == 422


def test_old_file_is_reported():
    path = os.path.join(tempfile.mkdtemp(), "vault.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"version": 2, "vault": {"kdf": {}}, "payload": SEALED}, file)
    client = TestClient(create_app(EntryStore(path), TOKEN))

    info = client.get("/v1/vault", headers=AUTH).json()
    assert info["version"] == 2
    assert info["legacy_payload"] == SEALED
    assert client.get("/v1/groups", headers=AUTH).json() == []


if __name__ == "__main__":
    test_health_without_token()
    test_token_required()
    test_pagination_and_order()
    test_password_content_only_on_request()
    test_batch_patch_and_delete()
    test_patch_unknown_changes_nothing()
    test_find_duplicate_by_hash()
    test_delete_group_moves_entries_to_default()
    test_data_survives_restart()
    test_invalid_request_is_rejected()
    test_old_file_is_reported()
    print("alle Tests ok")