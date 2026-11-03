import os
import sys

import uvicorn

from service.auth import load_or_create_token
from service.config import HOST, PORT, VAULT_FILE
from service.main import create_app
from service.store import EntryStore


def run():
    # in der .exe ohne Konsole gibt es kein stdout/stderr, uvicorn braucht aber welche
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    app = create_app(EntryStore(VAULT_FILE), load_or_create_token())
    # log_config=None: uvicorn richtet kein eigenes Logging ein (das scheitert ohne Konsole)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning", log_config=None)


if __name__ == "__main__":
    run()