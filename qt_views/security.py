import getpass

from vault import check_password

NAME_DISPLAY = 3   # Windows: Anzeigename des Benutzers, etwa "Daniel Friedmann"


def windows_user_name():
    # Anzeigename, sonst der Anmeldename
    try:
        import win32api
        name = win32api.GetUserNameEx(NAME_DISPLAY)
        if name:
            return name
    except Exception:
        pass
    return getpass.getuser()


def check_new_password(first, second):
    # gemeinsam für Anlegen, Zurücksetzen und Ändern; None = alles in Ordnung
    if first != second:
        return "Die Passwörter stimmen nicht überein."
    try:
        check_password(first)
    except ValueError as error:
        return str(error)
    return None
