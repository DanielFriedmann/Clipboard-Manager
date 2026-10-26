from cryptography.exceptions import InvalidTag

from vault import Vault, WrongPassword

# Anlegen
vault, code = Vault.create("geheim123")
print(code, "   (erwartet: vier Achtergruppen mit Bindestrichen)")

# Verschlüsseln und entschlüsseln
entry = vault.encrypt("Hallo äöü".encode("utf-8"))
print(vault.decrypt(entry).decode("utf-8"), "   (erwartet: Hallo äöü)")
print(entry["data"] != vault.encrypt("Hallo äöü".encode("utf-8"))["data"],
      "   (erwartet: True, jedes Mal anders)")

header = vault.header

# Anmelden mit richtigem Passwort
unlocked = Vault.unlock(header, "geheim123")
print(unlocked.decrypt(entry).decode("utf-8"), "   (erwartet: Hallo äöü)")

# Falsches Passwort
try:
    Vault.unlock(header, "falsch123")
    print("FEHLER: falsches Passwort angenommen")
except WrongPassword:
    print("Falsches Passwort korrekt abgelehnt")

# Wiederherstellung, auch klein geschrieben und ohne Bindestriche
recovered = Vault.unlock_with_recovery(header, code.lower().replace("-", ""))
print(recovered.decrypt(entry).decode("utf-8"), "   (erwartet: Hallo äöü)")

# Passwort ändern: altes geht nicht mehr, neues schon, Daten bleiben lesbar
recovered.change_password("neuesPasswort")
try:
    Vault.unlock(header, "geheim123")
    print("FEHLER: altes Passwort geht noch")
except WrongPassword:
    print("Altes Passwort korrekt abgelehnt")
print(Vault.unlock(header, "neuesPasswort").decrypt(entry).decode("utf-8"),
      "   (erwartet: Hallo äöü)")

# Zu kurzes Passwort
try:
    Vault.create("kurz")
    print("FEHLER: kurzes Passwort angenommen")
except ValueError as error:
    print("Korrekt abgelehnt:", error)

# Manipulierte Daten
manipulated = dict(entry, data=entry["data"][:-4] + "AAAA")
try:
    vault.decrypt(manipulated)
    print("FEHLER: Manipulation nicht erkannt")
except InvalidTag:
    print("Manipulation korrekt erkannt")