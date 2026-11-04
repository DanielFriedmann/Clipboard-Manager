from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication

# Farben wie in der CTk-Version: (hell, dunkel)
COLORS = {
    "window": ("#f2f2f2", "#1e1e1e"),
    "card": ("#ffffff", "#2b2b2b"),
    "card_hover": ("#e8f0fb", "#3a3a3a"),
    "card_border": ("#e3e3e3", "#333333"),
    "text": ("#1a1a1a", "#f2f2f2"),
    "muted": ("#6b6b6b", "#a0a0a0"),
    "accent": ("#0067c0", "#4ca0e0"),
    "button_hover": ("#d9e6f5", "#46505e"),
    "sidebar": ("#ebebeb", "#212121"),
    "sidebar_hover": ("#dedede", "#2c2c2c"),
    "selected": ("#dbe7f6", "#33415c"),
    "divider": ("#d0d0d0", "#3a3a3a"),
    "all_icon": ("#d0d0d0", "#4a4a4a"),
}

ICON_FAMILY = "Segoe MDL2 Assets"   # Windows-Symbolschrift für Schloss und Link

# Größen relativ zur Systemschrift, die Windows vorgibt (auch "Textgröße" in den Einstellungen)
FONT_SCALES = {
    "normal": 1.0,
    "small": 0.88,
    "section": 1.15,
    "title": 1.6,
}


def is_dark():
    # folgt der Windows-Einstellung "Hell" / "Dunkel"
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def color(name):
    light, dark = COLORS[name]
    return QColor(dark if is_dark() else light)


def font(role="normal", bold=False, italic=False, family=None):
    # Systemschrift als Grundlage, nur die Größe wird je nach Rolle angepasst
    result = QFont(QGuiApplication.font())
    result.setPointSizeF(result.pointSizeF() * FONT_SCALES[role])
    result.setBold(bold)
    result.setItalic(italic)
    if family:
        result.setFamily(family)
    return result
