import uvicorn

from service.auth import load_or_create_token
from service.config import HOST, PORT, VAULT_FILE
from service.main import create_app
from service.store import EntryStore


def run():
    app = create_app(EntryStore(VAULT_FILE), load_or_create_token())
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    run()