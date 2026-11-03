import copy

from api_repository import ApiRepository, import_history
from history import ClipboardHistory
from storage import VAULT_FILE, VAULT_VERSION, load_encrypted, load_legacy, remove_legacy
from vault import Vault

# Nach der Anmeldung: Daten über den Speicherdienst öffnen.
# Liefert ein ApiRepository für das ViewModel.


def read_header_from_service(api):
    # None, wenn es noch keinen Tresor gibt
    return api.get("/v1/vault")["header"]

def save_header(api, header):
    # nur die eingepackten Schlüssel ersetzen, die Standardgruppe bleibt
    info = api.get("/v1/vault")
    api.put("/v1/vault", json={"header": header, "default_group": info["default_group"]})


def change_vault_password(api, header, current, new):
    # liefert den neuen Header; WrongPassword, wenn das aktuelle Passwort falsch ist
    # auf einer Kopie arbeiten: schlägt das Speichern fehl, bleibt der alte Header gültig
    vault = Vault.unlock(copy.deepcopy(header), current)
    try:
        vault.change_password(new)
        save_header(api, vault.header)
        return vault.header
    finally:
        vault.lock()   # Datenschlüssel dieser Kopie sofort vergessen

def prepare_new_recovery(header, password):
    # liefert (neuer Header, Code); gespeichert wird erst, wenn der Code notiert ist
    vault = Vault.unlock(copy.deepcopy(header), password)
    try:
        code = vault.new_recovery_code()
        return vault.header, code
    finally:
        vault.lock()
        
def open_api_data(api, vault, is_new, header_changed, backup_path=VAULT_FILE):
    info = api.get("/v1/vault")

    if is_new:
        # neuer Tresor, ggf. mit den Daten aus Version 1.1
        import_history(api, vault, load_legacy() or ClipboardHistory())
    elif info["version"] < VAULT_VERSION:
        # alte Datei (ein großer Block): hier entschlüsseln, einzeln verschlüsselt zurückgeben
        old = {"version": info["version"], "payload": info["legacy_payload"]}
        import_history(api, vault, load_encrypted(old, vault, backup_path))
    elif header_changed:
        # nach "Passwort vergessen": neuen Header speichern, Daten bleiben gleich
        save_header(api, vault.header)

    remove_legacy()   # erst wenn alles beim Dienst angekommen ist
    return ApiRepository(api, vault)