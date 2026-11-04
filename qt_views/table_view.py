import html

from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QApplication, QHeaderView, QTableView, QToolTip

from . import style
from .drag import ITEM_MIME, dragged_items, items_mime, set_preview

# (Spalten-ID, Überschrift, Sortierung oder None); Reihenfolge wie TABLE_COLUMNS im ViewModel
COLUMNS = {
    "check": ("☐", None),
    "position": ("Pos.", "priority"),
    "content": ("Inhalt", "content"),
    "group": ("Gruppe", "group"),
    "time": ("Zeitstempel", "time"),
    "favorite": ("★", "favorite"),
}
COMPACT_COLUMNS = ("check", "content", "favorite")   # Spalten im schmalen Modus
FIXED_WIDTHS = {"check": 36, "position": 52, "group": 130, "time": 130, "favorite": 36}
CENTERED = ("check", "position", "favorite")


class TableModel(QAbstractTableModel):
    # dieselben Einträge wie die Kacheln, nur als Zeilen und Spalten

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.compact = False
        self._items = []
        self._columns = []
        vm.subscribe(self._on_vm_changed)
        self._on_vm_changed()

    @property
    def columns(self):
        return self._columns

    def item_at(self, row):
        return self._items[row] if 0 <= row < len(self._items) else None

    def set_compact(self, compact):
        self.compact = compact
        self._on_vm_changed()

    def _wanted_columns(self):
        columns = list(self.vm.visible_columns)
        if self.compact:
            columns = [column for column in columns if column in COMPACT_COLUMNS]
        return columns

    def _on_vm_changed(self):
        new = [] if self.vm.locked else list(self.vm.get_visible_items())
        columns = self._wanted_columns()
        old = self._items

        if columns != self._columns:
            self.beginResetModel()
            self._items, self._columns = new, columns
            self.endResetModel()
        elif len(new) > len(old) and new[:len(old)] == old:
            # nachgeladen: nur anhängen, Scrollposition bleibt
            self.beginInsertRows(QModelIndex(), len(old), len(new) - 1)
            self._items = new
            self.endInsertRows()
            self._changed_all(len(old))
        elif new == old:
            self._changed_all(len(new))
        else:
            self.beginResetModel()
            self._items = new
            self.endResetModel()
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, max(0, len(self._columns) - 1))

    def _changed_all(self, count):
        if count and self._columns:
            self.dataChanged.emit(self.index(0, 0), self.index(count - 1, len(self._columns) - 1))

    # Pflichtmethoden für Qt

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._columns)

    def canFetchMore(self, parent=QModelIndex()):
        return not parent.isValid() and not self.vm.locked and self.vm.has_more

    def fetchMore(self, parent=QModelIndex()):
        self.vm.load_more()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        item = self.item_at(index.row())
        if item is None:
            return None
        column = self._columns[index.column()]
        vm = self.vm

        if role == Qt.ItemDataRole.DisplayRole:
            if column == "check":
                return "☑" if vm.is_checked(item) else "☐"
            if column == "position":
                return vm.position(item)
            if column == "content":
                return vm.display_text(item, 200)
            if column == "group":
                return vm.group_name(item)
            if column == "time":
                return vm.datetime_text(item)
            if column == "favorite":
                return "★" if item.is_favorite else "☆"
        if role == Qt.ItemDataRole.FontRole and column == "content":
            text_style = vm.text_style(item)
            return style.font("normal", bold=text_style == "title", italic=text_style == "placeholder")
        if role == Qt.ItemDataRole.ForegroundRole:
            if column == "content" and vm.text_style(item) == "placeholder":
                return style.color("muted")
            if column == "favorite" and item.is_favorite:
                return style.color("accent")
        if role == Qt.ItemDataRole.TextAlignmentRole and column in CENTERED:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or section >= len(self._columns):
            return None
        column = self._columns[section]
        title, sort_key = COLUMNS[column]
        if role == Qt.ItemDataRole.DisplayRole:
            if column == "check":
                return "☑" if self.vm.all_visible_checked else "☐"
            if sort_key is not None and sort_key == self.vm.sort_by:
                return f"{title} {'▼' if self.vm.descending else '▲'}"
            return title
        if role == Qt.ItemDataRole.ToolTipRole and column == "check":
            return "Alle markieren"
        return None


class ItemTableView(QTableView):
    # Tabellenansicht: Markieren, Sortieren per Spaltenkopf, Ziehen, Doppelklick zum Kopieren

    copied = Signal(object)
    menu_requested = Signal(object, QPoint)

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.table_model = TableModel(vm, self)
        self.setModel(self.table_model)

        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(QFontMetrics(style.font()).height() + 12)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)

        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_click)

        self._press = None   # (Position, Zeile, Spalte) beim Drücken
        self._drop = None    # (Zeile, danach) für die Einfügelinie
        self.table_model.modelReset.connect(self._apply_widths)
        self.table_model.modelAboutToBeReset.connect(self._remember_scroll)
        self.table_model.modelReset.connect(self._restore_scroll)
        self._scroll = 0
        self._apply_widths()

    def set_compact(self, compact):
        self.table_model.set_compact(compact)

    def _apply_widths(self):
        # Inhalt bekommt den Rest, die anderen Spalten feste Breiten
        header = self.horizontalHeader()
        for section, column in enumerate(self.table_model.columns):
            if column == "content":
                header.setSectionResizeMode(section, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(section, QHeaderView.ResizeMode.Fixed)
                self.setColumnWidth(section, FIXED_WIDTHS[column])

    def _remember_scroll(self):
        self._scroll = self.verticalScrollBar().value()

    def _restore_scroll(self):
        if self.vm.scroll_to_top:
            self.scrollToTop()
        else:
            self.verticalScrollBar().setValue(self._scroll)

    def _column(self, index):
        return self.table_model.columns[index.column()] if index.isValid() else None

    # Spaltenkopf

    def _on_header_click(self, section):
        column = self.table_model.columns[section]
        if column == "check":
            self.vm.set_all_checked(not self.vm.all_visible_checked)
            return
        sort_key = COLUMNS[column][1]
        if sort_key is not None:
            self.vm.sort_by_column(sort_key)

    # Maus

    def mousePressEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        self._press = None
        if event.button() == Qt.MouseButton.LeftButton and index.isValid():
            self._press = (event.position().toPoint(), index.row(), self._column(index))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._press is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        start, row, _column = self._press
        if (event.position().toPoint() - start).manhattanLength() >= QApplication.startDragDistance():
            self._press = None
            self._start_drag(row)

    def mouseReleaseEvent(self, event):
        press, self._press = self._press, None
        super().mouseReleaseEvent(event)
        if press is None or event.button() != Qt.MouseButton.LeftButton:
            return
        # kurzer Klick ohne Ziehen: Markierung oder Favorit umschalten
        _start, row, column = press
        item = self.table_model.item_at(row)
        if item is None:
            return
        if column == "check":
            self.vm.toggle_checked(item)
        elif column == "favorite":
            self.vm.toggle_favorite(item)

    def mouseDoubleClickEvent(self, event):
        index = self.indexAt(event.position().toPoint())
        item = self.table_model.item_at(index.row()) if index.isValid() else None
        if item is not None and self._column(index) not in ("check", "favorite"):
            self.vm.copy(item)
            self.copied.emit(item)

    def contextMenuEvent(self, event):
        index = self.indexAt(event.pos())
        item = self.table_model.item_at(index.row()) if index.isValid() else None
        if item is not None:
            self.menu_requested.emit(item, event.globalPos())

    # Ziehen: markierte Zeile nimmt alle markierten mit

    def _drag_items(self, item):
        if self.vm.is_checked(item):
            return self.vm.checked_visible()
        return [item]

    def _start_drag(self, row):
        item = self.table_model.item_at(row)
        if item is None:
            return
        items = self._drag_items(item)
        drag = QDrag(self)
        drag.setMimeData(items_mime(items))
        set_preview(drag, self, items, self.vm)   # bei mehreren mit der Anzahl
        drag.exec(Qt.DropAction.MoveAction)
        self._set_drop(None)

    def _drop_target(self, pos):
        row = self.rowAt(pos.y())
        if row < 0:
            count = self.table_model.rowCount()
            return (count - 1, True) if count else None
        top = self.rowViewportPosition(row)
        return row, pos.y() > top + self.rowHeight(row) / 2

    def _set_drop(self, drop):
        if drop != self._drop:
            self._drop = drop
            self.viewport().update()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(ITEM_MIME) and self.vm.can_drag:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        # innerhalb der Liste nur einzeln und nur in eigener Reihenfolge
        items = dragged_items(self.vm, event.mimeData())
        if len(items) != 1 or not self.vm.can_drag:
            self._set_drop(None)
            event.ignore()
            return
        self._set_drop(self._drop_target(event.position().toPoint()))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_drop(None)

    def dropEvent(self, event):
        items = dragged_items(self.vm, event.mimeData())
        drop = self._drop_target(event.position().toPoint())
        self._set_drop(None)
        if len(items) != 1 or drop is None or not self.vm.can_drag:
            event.ignore()
            return
        row, after = drop
        event.acceptProposedAction()
        self.vm.move(items[0], self.table_model.item_at(row), after=after)

    # Tooltip und Zeichnen

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            self._show_tooltip(event)
            return True
        return super().viewportEvent(event)

    def _show_tooltip(self, event):
        index = self.indexAt(event.pos())
        item = self.table_model.item_at(index.row()) if index.isValid() else None
        if item is None or self._column(index) != "content":
            QToolTip.hideText()
            return
        shown = self.vm.display_text(item, 200)
        metrics = QFontMetrics(index.data(Qt.ItemDataRole.FontRole))
        cut = metrics.horizontalAdvance(shown) > self.columnWidth(index.column()) - 12
        shortened = not item.is_password and shown != " ".join((item.content or "").split())
        if not (self.vm.always_tooltip(item) or cut or shortened):
            QToolTip.hideText()
            return
        body = html.escape(self.vm.tooltip_text(item)).replace("\n", "<br>")
        QToolTip.showText(event.globalPos(), f"<p style='white-space: pre-wrap'>{body}</p>", self)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self.table_model.rowCount() == 0 and not self.vm.locked:
            painter.setFont(style.font())
            painter.setPen(style.color("muted"))
            painter.drawText(self.viewport().rect().adjusted(0, 24, 0, 0),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.vm.empty_text)
        if self._drop is not None:
            row, after = self._drop
            y = self.rowViewportPosition(row) + (self.rowHeight(row) if after else 0)
            painter.setPen(QPen(style.color("accent"), 3))
            painter.drawLine(4, y, self.viewport().width() - 4, y)
