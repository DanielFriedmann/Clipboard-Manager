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
    "drop_line": ("#0067c0", "#4ca0e0"),
}

FONT_FAMILY = "Segoe UI"
ICON_FAMILY = "Segoe MDL2 Assets"   # Windows-Symbolschrift für Schloss und Link


def is_dark():
    # folgt der Windows-Einstellung "Hell" / "Dunkel"
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def color(name):
    light, dark = COLORS[name]
    return QColor(dark if is_dark() else light)


def font(pixel_size=13, bold=False, italic=False, family=FONT_FAMILY):
    # Pixelgrößen wie in der CTk-Version; Qt rechnet sie selbst auf den Bildschirm um
    result = QFont(family)
    result.setPixelSize(pixel_size)
    result.setBold(bold)
    result.setItalic(italic)
    return result
