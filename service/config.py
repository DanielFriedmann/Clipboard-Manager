import os

# derselbe Ordner wie die App, aber ohne storage.py zu importieren:
# der Service soll nichts von Verlauf, Modellen oder Schlüsseln wissen
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "ClipboardManager")
VAULT_FILE = os.path.join(APP_DIR, "vault.json")
TOKEN_FILE = os.path.join(APP_DIR, "service-token")

HOST = "127.0.0.1"   # nur dieser Rechner, nie das Netzwerk
PORT = 8765

FILE_VERSION = 3