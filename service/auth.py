import os
import secrets

from service.config import TOKEN_FILE


def load_or_create_token(path=TOKEN_FILE):
    # gemeinsames Geheimnis von App und Service, liegt im Benutzerprofil
    if os.path.exists(path):
        with open(path, encoding="utf-8") as file:
            token = file.read().strip()
        if token:
            return token

    token = secrets.token_urlsafe(32)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write(token)
    return token