from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from models import EntryKind

ALLOWED_SCHEMES = ("http", "https")   # nichts anderes öffnen, z. B. kein file: oder javascript:


def link_target(text):
    # Adresse aus einem Text, oder None, wenn es kein sicherer Weblink ist
    text = (text or "").strip()
    if not text or any(char.isspace() for char in text):
        return None
    if text.lower().startswith("www."):
        text = "https://" + text
    url = QUrl(text, QUrl.ParsingMode.StrictMode)
    if not url.isValid() or url.scheme().lower() not in ALLOWED_SCHEMES or not url.host():
        return None
    return url


def item_link(item):
    # Links öffnen ihren Inhalt, Passwörter ihre eingetragene Adresse
    if item.is_password:
        return link_target(item.url)
    if item.kind == EntryKind.LINK:
        return link_target(item.content)
    return None


def open_link(url):
    # im Standardbrowser von Windows
    QDesktopServices.openUrl(url)
