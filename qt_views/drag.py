from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap

from . import style

# eigene Datentypen, damit nur unsere Ansichten diese Drops annehmen
ITEM_MIME = "application/x-abkoo-clipboard-items"
GROUP_MIME = "application/x-abkoo-clipboard-group"

PREVIEW_TEXT_WIDTH = 180   # Vorschau beim Ziehen bleibt klein, damit die Gruppen sichtbar bleiben
PREVIEW_OFFSET = QPoint(-16, -12)   # Vorschau rechts unterhalb des Mauszeigers


def items_mime(items):
    # beim Ziehen wird nur die ID mitgegeben, nie der Inhalt
    data = QMimeData()
    data.setData(ITEM_MIME, QByteArray(",".join(item.id for item in items).encode("ascii")))
    return data


def dragged_items(vm, mime):
    # IDs zurück in Einträge; gezogen wird immer aus der sichtbaren Liste
    if not mime.hasFormat(ITEM_MIME):
        return []
    ids = bytes(mime.data(ITEM_MIME)).decode("ascii").split(",")
    by_id = {item.id: item for item in vm.get_visible_items()}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def group_mime(group):
    data = QMimeData()
    data.setData(GROUP_MIME, QByteArray(group.id.encode("ascii")))
    return data


def dragged_group(vm, mime):
    if not mime.hasFormat(GROUP_MIME):
        return None
    group_id = bytes(mime.data(GROUP_MIME)).decode("ascii")
    return next((group for group in vm.custom_groups if group.id == group_id), None)


def drag_preview(widget, text, color, count=1):
    # kleine Kachel als Vorschau: Farbstreifen, gekürzter Text, bei mehreren die Anzahl
    font = style.font("small", bold=True)
    metrics = QFontMetrics(font)
    text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, PREVIEW_TEXT_WIDTH)
    badge = str(count) if count > 1 else ""
    badge_width = metrics.horizontalAdvance(badge) + 14 if badge else 0
    width = 20 + metrics.horizontalAdvance(text) + (badge_width + 8 if badge else 0) + 12
    height = metrics.height() + 14

    # in voller Bildschirmauflösung zeichnen, sonst ist die Vorschau bei 150 % unscharf
    ratio = widget.devicePixelRatioF()
    pixmap = QPixmap(int(width * ratio), int(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(style.color("accent"), 1))
    painter.setBrush(style.color("card"))
    painter.drawRoundedRect(QRect(0, 0, width - 1, height - 1), 6, 6)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRect(6, 5, 4, height - 10), 2, 2)

    painter.setFont(font)
    painter.setPen(style.color("text"))
    painter.drawText(QRect(18, 0, metrics.horizontalAdvance(text) + 2, height),
                     Qt.AlignmentFlag.AlignVCenter, text)
    if badge:
        circle = QRect(width - 12 - badge_width, (height - metrics.height() - 2) // 2,
                       badge_width, metrics.height() + 2)
        painter.setBrush(style.color("accent"))
        painter.drawRoundedRect(circle, circle.height() / 2, circle.height() / 2)
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, badge)
    painter.end()
    return pixmap


def set_preview(drag, widget, items, vm):
    # Vorschau für einen oder mehrere Einträge setzen
    first = items[0]
    text = vm.display_text(first)   # bei Passwörtern Name oder Platzhalter, nie der Inhalt
    drag.setPixmap(drag_preview(widget, text, vm.group_color(first), count=len(items)))
    drag.setHotSpot(PREVIEW_OFFSET)
