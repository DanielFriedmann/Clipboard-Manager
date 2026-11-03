from api_repository import ApiRepository, import_history
from history import ClipboardHistory
from storage import VAULT_FILE, VAULT_VERSION, load_encrypted, load_legacy, remove_legacy

# Nach der Anmeldung: Daten über den Speicherdienst öffnen.
# Liefert ein ApiRepository für das ViewModel.


def read_header_from_service(api):
    # None, wenn es noch keinen Tresor gibt
    return api.get("/v1/vault")["header"]


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
        api.put("/v1/vault", json={"header": vault.header, "default_group": info["default_group"]})

    remove_legacy()   # erst wenn alles beim Dienst angekommen ist
    return ApiRepository(api, vault)