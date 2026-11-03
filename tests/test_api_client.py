import os
import tempfile

import httpx
from fastapi.testclient import TestClient

from api_client import ApiClient, ApiError, ServiceUnavailable
from service.main import create_app
from service.store import EntryStore

TOKEN = "test-token"


def make_api(token=TOKEN):
    path = os.path.join(tempfile.mkdtemp(), "vault.json")
    app = create_app(EntryStore(path), TOKEN)
    return ApiClient(token, client=TestClient(app))


def test_health():
    assert make_api().health()


def test_request_with_token():
    api = make_api()
    api.put("/v1/vault", json={"header": {"test": True}, "default_group": "g0"})
    assert api.get("/v1/vault")["header"] == {"test": True}


def test_wrong_token_raises_api_error():
    api = make_api(token="falsch")
    try:
        api.get("/v1/groups")
    except ApiError as error:
        assert error.status == 401
        return
    raise AssertionError("falsches Token wurde nicht abgelehnt")


def test_not_found_raises_api_error():
    api = make_api()
    try:
        api.get("/v1/entries/gibtsnicht/content")
    except ApiError as error:
        assert error.status == 404
        return
    raise AssertionError("404 wurde nicht gemeldet")


def test_no_service_raises_unavailable():
    # Port 9 nimmt auf normalen Rechnern keine Verbindung an
    offline = ApiClient(TOKEN, client=httpx.Client(base_url="http://127.0.0.1:9", timeout=1))
    assert not offline.health()
    try:
        offline.get("/v1/groups")
    except ServiceUnavailable:
        return
    raise AssertionError("fehlender Service wurde nicht erkannt")