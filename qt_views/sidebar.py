from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QColorDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QMenu,
                               QMessageBox, QScrollArea, QSizePolicy, QToolButton, QVBoxLayout,
                               QWidget)

from . import style
from .drag import ITEM_MIME, dragged_group, dragged_items, group_mime

EXPANDED_WIDTH = 210
COLLAPSED_WIDTH = 52
ICON_SIZE = 24
DEFAULT_GROUP_COLOR = "#9e9e9e"
ALL_SYMBOL = "≡"


class GroupRow(QWidget):
    # eine Zeile der Seitenleiste; zeichnet sich selbst wie die Kacheln

    clicked = Signal()
    menu_requested = Signal(object)   # globale Position für das Kontextmenü

    def __init__(self, name, symbol, color, count=None, selected=False, collapsed=False,
                 muted=False, tooltip=None, group=None, sidebar=None, parent=None):
        super().__init__(parent)
        self.group = group              # None bei "Alle Einträge" und "Neue Gruppe"
        self.sidebar = sidebar          # entscheidet, was hier abgelegt werden darf
        self._press_pos = None
        self._drop = None               # "into", "before" oder "after" während eines Drops
        self.name = name
        self.symbol = symbol
        self.color = color              # None: neutrales Quadrat, z. B. "Alle Einträge"
        self.count = count
        self.selected = selected
        self.collapsed = collapsed
        self.muted = muted              # "Neue Gruppe" in grauer Schrift
        self._hovered = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setAcceptDrops(group is not None)

    def sizeHint(self):
        return QSize(COLLAPSED_WIDTH if self.collapsed else EXPANDED_WIDTH,
                     max(36, QFontMetrics(style.font()).height() + 16))

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()

    def mouseMoveEvent(self, event):
        # eigene Gruppen lassen sich ziehen, um die Reihenfolge zu ändern
        if self._press_pos is None or self.sidebar is None or not self.sidebar.is_custom(self.group):
            return
        if (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance():
            self._press_pos = None
            drag = QDrag(self)
            drag.setMimeData(group_mime(self.group))
            drag.setPixmap(self.grab())
            drag.exec(Qt.DropAction.MoveAction)

    def mouseReleaseEvent(self, event):
        pressed, self._press_pos = self._press_pos, None
        if (pressed is not None and event.button() == Qt.MouseButton.LeftButton
                and self.rect().contains(event.position().toPoint())):
            self.clicked.emit()

    # Ablegen: Einträge in die Gruppe, Gruppen davor oder dahinter

    def _drop_kind(self, event):
        if self.sidebar is None:
            return None
        return self.sidebar.drop_kind(self, event.mimeData(), event.position().toPoint())

    def dragEnterEvent(self, event):
        self.dragMoveEvent(event)

    def dragMoveEvent(self, event):
        kind = self._drop_kind(event)
        if kind != self._drop:
            self._drop = kind
            self.update()
        if kind is None:
            event.ignore()
        else:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop = None
        self.update()

    def dropEvent(self, event):
        kind = self._drop_kind(event)
        self._drop = None
        self.update()
        if kind is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.sidebar.drop(self, event.mimeData(), kind)

    def contextMenuEvent(self, event):
        self.menu_requested.emit(event.globalPos())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 1, 0, -1)

        # Hintergrund: ausgewählt oder unter der Maus
        if self.selected or self._hovered:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(style.color("selected" if self.selected else "sidebar_hover"))
            painter.drawRoundedRect(rect, 6, 6)
        if self.selected:
            painter.setBrush(style.color("accent"))
            painter.drawRoundedRect(QRect(rect.left() + 2, rect.top() + 6, 3, rect.height() - 12), 2, 2)

        # Ziel beim Ablegen: Rahmen um die Gruppe oder Linie davor bzw. dahinter
        accent = style.color("accent")
        if self._drop == "into":
            painter.setPen(QPen(accent, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
        elif self._drop in ("before", "after"):
            y = rect.top() if self._drop == "before" else rect.bottom()
            painter.setPen(QPen(accent, 3))
            painter.drawLine(rect.left() + 4, y, rect.right() - 4, y)

        # Quadrat mit Symbol oder Anfangsbuchstaben
        if self.collapsed:
            icon = QRect((rect.width() - ICON_SIZE) // 2, rect.center().y() - ICON_SIZE // 2 + 1,
                         ICON_SIZE, ICON_SIZE)
        else:
            icon = QRect(rect.left() + 11, rect.center().y() - ICON_SIZE // 2 + 1, ICON_SIZE, ICON_SIZE)
        if self.color is None:
            background, foreground = style.color("all_icon"), style.color("text")
        elif self.color == "transparent":
            background, foreground = None, style.color("muted")
        else:
            background, foreground = QColor(self.color), QColor(style.text_color_for(self.color))
        if background is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(icon, 5, 5)
        painter.setFont(style.font("normal", bold=True))
        painter.setPen(foreground)
        painter.drawText(icon, Qt.AlignmentFlag.AlignCenter, self.symbol)

        if self.collapsed:
            return

        # Name und Anzahl
        middle = Qt.AlignmentFlag.AlignVCenter
        text_left = icon.right() + 10
        count_width = 0
        if self.count is not None:
            painter.setFont(style.font("small"))
            painter.setPen(style.color("muted"))
            count_rect = QRect(rect.right() - 44, rect.top(), 34, rect.height())
            painter.drawText(count_rect, middle | Qt.AlignmentFlag.AlignRight, str(self.count))
            count_width = 48
        name_font = style.font("normal")
        painter.setFont(name_font)
        painter.setPen(style.color("muted" if self.muted else "text"))
        name_rect = QRect(text_left, rect.top(), rect.right() - text_left - count_width, rect.height())
        painter.drawText(name_rect, middle, QFontMetrics(name_font).elidedText(
            self.name, Qt.TextElideMode.ElideRight, name_rect.width()))


class GroupSidebar(QFrame):
    # Gruppenleiste links: Auswahl, neue Gruppe, Gruppe löschen, einklappen

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.collapsed = False
        self.setObjectName("sidebar")
        self.setStyleSheet(f"#sidebar {{ background: {style.color('sidebar').name()}; }}")
        self.setFixedWidth(EXPANDED_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 10, 6, 10)
        layout.setSpacing(6)

        # Kopf: Umschalter und Titel
        header = QHBoxLayout()
        self.toggle_button = QToolButton()
        self.toggle_button.setText("☰")
        self.toggle_button.setAutoRaise(True)
        self.toggle_button.setFixedSize(36, 32)
        self.toggle_button.clicked.connect(self.toggle_collapsed)
        self.title_label = QLabel("Gruppen")
        self.title_label.setFont(style.font("section", bold=True))
        header.addWidget(self.toggle_button)
        header.addWidget(self.title_label, 1)
        layout.addLayout(header)

        # Mitte: scrollbare Liste
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        self.list_widget = QWidget()
        self.rows = QVBoxLayout(self.list_widget)
        self.rows.setContentsMargins(0, 0, 0, 0)
        self.rows.setSpacing(2)
        self.scroll.setWidget(self.list_widget)
        self.scroll.viewport().setAutoFillBackground(False)   # Farbe der Seitenleiste durchscheinen lassen
        layout.addWidget(self.scroll, 1)

        # Fuß: Einstellungen
        self.settings_button = QToolButton()
        self.settings_button.setText("⚙  Einstellungen")
        self.settings_button.setAutoRaise(True)
        self.settings_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.settings_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.settings_button.setMinimumHeight(32)
        layout.addWidget(self.settings_button)

        self._update_tooltips()
        vm.subscribe(self.refresh)
        self.refresh()

    # Einklappen

    def toggle_collapsed(self):
        self.collapsed = not self.collapsed
        self.setFixedWidth(COLLAPSED_WIDTH if self.collapsed else EXPANDED_WIDTH)
        self.title_label.setVisible(not self.collapsed)
        self.settings_button.setText("⚙" if self.collapsed else "⚙  Einstellungen")
        self._update_tooltips()
        self.refresh()

    def _update_tooltips(self):
        self.toggle_button.setToolTip("Menü aufklappen (Strg+B)" if self.collapsed
                                      else "Menü einklappen (Strg+B)")
        self.settings_button.setToolTip("Einstellungen")

    # Zeilen aufbauen

    def refresh(self):
        # wenige Zeilen: einfach neu aufbauen
        while self.rows.count():
            child = self.rows.takeAt(0).widget()
            if child is not None:
                child.hide()              # sofort weg, gelöscht wird erst später
                child.setParent(None)
                child.deleteLater()
        if self.vm.locked:
            return   # gesperrt: keine Gruppennamen zeigen

        self._add_row(None, "Alle Einträge", ALL_SYMBOL, None)
        default = self.vm.default_group
        self._add_row(default, default.name, self.vm.group_initial(default), default.color)

        new_row = GroupRow("Neue Gruppe", "＋", "transparent", collapsed=self.collapsed, muted=True,
                           tooltip="Neue Gruppe")
        new_row.clicked.connect(self._on_add_group)
        self.rows.addWidget(new_row)

        divider = QFrame()
        divider.setFixedHeight(2)
        divider.setStyleSheet(f"background: {style.color('divider').name()};")
        self.rows.addSpacing(6)
        self.rows.addWidget(divider)
        self.rows.addSpacing(6)

        for group in self.vm.custom_groups:
            self._add_row(group, group.name, self.vm.group_initial(group), group.color)
        self.rows.addStretch(1)

    def _add_row(self, group, name, symbol, color):
        tooltip = self.vm.group_tooltip(group, name) if self.collapsed else None
        row = GroupRow(name, symbol, color, count=self.vm.group_count(group),
                       selected=group is self.vm.selected_group, collapsed=self.collapsed,
                       tooltip=tooltip, group=group, sidebar=self)
        row.clicked.connect(lambda g=group: self.vm.select_group(g))
        if self.is_custom(group):
            row.menu_requested.connect(lambda pos, g=group: self._on_group_menu(pos, g))
        self.rows.addWidget(row)

    def is_custom(self, group):
        return group is not None and group is not self.vm.default_group

    # Ziehen und Ablegen, von den Zeilen aufgerufen

    def drop_kind(self, row, mime, pos):
        # None: hier nicht ablegbar, sonst "into", "before" oder "after"
        if self.vm.locked or row.group is None:
            return None
        if mime.hasFormat(ITEM_MIME):
            return "into"
        dragged = dragged_group(self.vm, mime)
        if dragged is not None and self.is_custom(row.group) and dragged is not row.group:
            return "after" if pos.y() > row.height() / 2 else "before"
        return None

    def drop(self, row, mime, kind):
        if kind == "into":
            items = dragged_items(self.vm, mime)
            if items:
                self.vm.assign_items_to_group(items, row.group)
        else:
            dragged = dragged_group(self.vm, mime)
            if dragged is not None:
                self.vm.move_group(dragged, row.group, after=kind == "after")

    # Gruppen anlegen und löschen

    def _on_add_group(self):
        name, ok = QInputDialog.getText(self.window(), "Neue Gruppe", "Name der neuen Gruppe:")
        if not ok or self.vm.locked:
            return
        color = QColorDialog.getColor(QColor(DEFAULT_GROUP_COLOR), self.window(), "Farbe der Gruppe wählen")
        if self.vm.locked:
            return   # während der Farbauswahl gesperrt
        color_name = color.name() if color.isValid() else DEFAULT_GROUP_COLOR
        try:
            group = self.vm.add_group(name, color_name)
        except ValueError as error:
            QMessageBox.warning(self.window(), "Neue Gruppe", str(error))
            return
        self.vm.select_group(group)

    def _on_group_menu(self, pos, group):
        menu = QMenu(self)
        menu.addAction(f"„{group.name}“ löschen", lambda: self._delete_group(group))
        menu.exec(pos)

    def _delete_group(self, group):
        answer = QMessageBox.question(
            self.window(), "Gruppe löschen",
            f"Gruppe „{group.name}“ löschen?\nIhre Einträge wandern nach „{self.vm.default_group.name}“.")
        if answer == QMessageBox.StandardButton.Yes and not self.vm.locked:
            self.vm.remove_group(group)
