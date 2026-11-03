import base64
import hashlib
import hmac
import os
import secrets

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MIN_PASSWORD_LENGTH = 8

# Kosten der Schlüsselableitung: absichtlich langsam gegen Durchprobieren von Passwörtern
KDF_PARAMS = {"n": 2 ** 17, "r": 8, "p": 1}

# Verwendungszweck, damit verschlüsselte Teile nicht vertauscht werden können
PURPOSE_PASSWORD = b"dek-password"
PURPOSE_RECOVERY = b"dek-recovery"
PURPOSE_DATA = b"data"
PURPOSE_HASH = b"content-hash"


class WrongPassword(Exception):
    pass


class DamagedData(Exception):
    # Prüfwert passt nicht: Datei beschädigt oder verändert
    pass


# Hilfsfunktionen

def _b64(data):
    return base64.b64encode(data).decode("ascii")


def _unb64(text):
    return base64.b64decode(text)


def _derive_key(secret, salt, params):
    kdf = Scrypt(salt=salt, length=32, n=params["n"], r=params["r"], p=params["p"])
    return kdf.derive(secret.encode("utf-8"))


def _wrap(dek, secret, purpose):
    # Datenschlüssel mit einem aus dem Geheimnis abgeleiteten Schlüssel einpacken
    salt = os.urandom(16)
    nonce = os.urandom(12)
    wrapping_key = _derive_key(secret, salt, KDF_PARAMS)
    wrapped = AESGCM(wrapping_key).encrypt(nonce, dek, purpose)
    return {"salt": _b64(salt), "nonce": _b64(nonce), "key": _b64(wrapped)}


def _unwrap(entry, secret, purpose, params):
    wrapping_key = _derive_key(secret, _unb64(entry["salt"]), params)
    try:
        return AESGCM(wrapping_key).decrypt(_unb64(entry["nonce"]), _unb64(entry["key"]), purpose)
    except InvalidTag:
        raise WrongPassword() from None


def _new_recovery_code():
    # 20 Zufallsbytes als 32 gut lesbare Zeichen in Achtergruppen
    raw = base64.b32encode(secrets.token_bytes(20)).decode("ascii")
    return "-".join(raw[i:i + 8] for i in range(0, len(raw), 8))


def _normalize_code(code):
    return code.upper().replace("-", "").replace(" ", "")


def check_password(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.")


# Der Tresor

class Vault:
    def __init__(self, dek, header):
        self._dek = dek          # Datenschlüssel, nur im Arbeitsspeicher
        self._hash_key = None    # Schlüssel für content_hash, wird bei Bedarf abgeleitet
        self.header = header     # wird unverschlüsselt in der Datei gespeichert

    @classmethod
    def create(cls, password):
        # neuen Tresor anlegen, liefert Tresor und Wiederherstellungsschlüssel
        check_password(password)
        dek = AESGCM.generate_key(bit_length=256)
        recovery_code = _new_recovery_code()
        header = {
            "kdf": dict(KDF_PARAMS),
            "password": _wrap(dek, password, PURPOSE_PASSWORD),
            "recovery": _wrap(dek, _normalize_code(recovery_code), PURPOSE_RECOVERY),
        }
        return cls(dek, header), recovery_code

    @classmethod
    def unlock(cls, header, password):
        dek = _unwrap(header["password"], password, PURPOSE_PASSWORD, header["kdf"])
        return cls(dek, header)

    @classmethod
    def unlock_with_recovery(cls, header, recovery_code):
        dek = _unwrap(header["recovery"], _normalize_code(recovery_code),
                      PURPOSE_RECOVERY, header["kdf"])
        return cls(dek, header)

    def change_password(self, new_password):
        # nur der eingepackte Datenschlüssel ändert sich, die Daten bleiben gleich
        check_password(new_password)
        self.header["password"] = _wrap(self._dek, new_password, PURPOSE_PASSWORD)
        self.header["kdf"] = dict(KDF_PARAMS)

    # Ver- und Entschlüsseln

    def encrypt(self, plain_bytes, associated=PURPOSE_DATA):
        # associated: wird mitgeprüft, aber nicht verschlüsselt (bindet den Block an seinen Platz)
        nonce = os.urandom(12)
        data = AESGCM(self._dek).encrypt(nonce, plain_bytes, associated)
        return {"nonce": _b64(nonce), "data": _b64(data)}

    def decrypt(self, entry, associated=PURPOSE_DATA):
        try:
            nonce = _unb64(entry["nonce"])
            data = _unb64(entry["data"])
            return AESGCM(self._dek).decrypt(nonce, data, associated)
        except (InvalidTag, ValueError, KeyError, TypeError):
            # falscher Prüfwert, ungültiges Base64 oder fehlende Felder: alles heißt "beschädigt"
            raise DamagedData() from None

    def content_hash(self, text):
        # gleicher Text ergibt denselben Wert, ohne Schlüssel lässt er sich nicht nachrechnen
        if self._hash_key is None:
            hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=PURPOSE_HASH)
            self._hash_key = hkdf.derive(self._dek)
        return hmac.new(self._hash_key, text.encode("utf-8"), hashlib.sha256).hexdigest()

    def lock(self):
        self._dek = None
        self._hash_key = None