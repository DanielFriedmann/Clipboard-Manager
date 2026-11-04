import html

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QListView, QStyle, QStyledItemDelegate, QToolTip

from viewmodel import MASK

from . import style

ITEM_ROLE = Qt.ItemDataRole.UserRole   # liefert den ClipboardItem einer Zeile

ROW_HEIGHT = 72        # Kachel 64 px plus 8 px Abstand
CARD_MARGIN = 4
TIME_WIDTH = 96
ACTION_WIDTH = 96
BUTTON_SIZE = QSize(28, 24)
REVIEW_SIZE = QSize(76, 22)


class CardListModel(QAbstractListModel):
    # Brücke zwischen ViewModel und Qt: kennt nur die gerade geladenen Einträge

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm
        self._items = []
        vm.subscribe(self._on_vm_changed)
        self._on_vm_changed()

    # Pflichtmethoden für Qt

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None
        item = self._items[index.row()]
        if role == ITEM_ROLE:
            return item
        if role == Qt.ItemDataRole.DisplayRole:
            return self.vm.display_text(item)   # z. B. für Screenreader
        return None

    # Nachladen beim Scrollen: ersetzt den Knopf "Weitere laden"

    def canFetchMore(self, parent=QModelIndex()):
        return not parent.isValid() and not self.vm.locked and self.vm.has_more

    def fetchMore(self, parent=QModelIndex()):
        self.vm.load_more()   # ViewModel meldet sich danach über _on_vm_changed

    # Änderungen aus dem ViewModel

    def _on_vm_changed(self):
        new = [] if self.vm.locked else list(self.vm.get_visible_items())
        old = self._items

        if len(new) > len(old) and new[:len(old)] == old:
            # nur hinten angehängt, z. B. nachgeladen: Scrollposition bleibt
            self.beginInsertRows(QModelIndex(), len(old), len(new) - 1)
            self._items = new
            self.endInsertRows()
            self._changed_all(len(old))
        elif new == old:
            # dieselben Einträge, aber vielleicht Favorit, Name oder Gruppe geändert
            self._changed_all(len(new))
        else:
            self.beginResetModel()
            self._items = new
            self.endResetModel()

    def _changed_all(self, count):
        if count:
            self.dataChanged.emit(self.index(0), self.index(count - 1))


class CardDelegate(QStyledItemDelegate):
    # zeichnet eine Kachel; es gibt keine Widgets pro Eintrag, nur diese eine Zeichenfunktion

    edit_requested = Signal(object)   # "Benennen" geklickt

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm

    def sizeHint(self, option, index):
        # Breite egal: die Liste gibt jeder Zeile die volle Breite
        return QSize(1, ROW_HEIGHT)

    # Aufteilung einer Kachel, gemeinsam für Zeichnen, Klicken und Tooltip

    def _layout(self, rect, item):
        card = rect.adjusted(CARD_MARGIN, CARD_MARGIN, -CARD_MARGIN, -CARD_MARGIN)
        parts = {"card": card}

        right = card.right() - 8
        parts["delete"] = QRect(right - BUTTON_SIZE.width(), card.top() + 8,
                                BUTTON_SIZE.width(), BUTTON_SIZE.height())
        parts["star"] = parts["delete"].translated(-BUTTON_SIZE.width(), 0)
        parts["group"] = QRect(right - ACTION_WIDTH, card.top() + 34, ACTION_WIDTH, 18)

        time_right = right - ACTION_WIDTH - 8
        parts["time"] = QRect(time_right - TIME_WIDTH, card.top() + 12, TIME_WIDTH, 18)
        parts["date"] = QRect(time_right - TIME_WIDTH, card.top() + 32, TIME_WIDTH, 18)

        text_left = card.left() + 22
        text_right = time_right - TIME_WIDTH - 16
        has_source = bool(self.vm.source_text(item))
        line_top = card.top() + (10 if has_source else 21)

        # rechts in der ersten Zeile: Benennen-Knopf und Maske
        end = text_right
        if item.needs_review:
            parts["review"] = QRect(end - REVIEW_SIZE.width(), line_top, REVIEW_SIZE.width(),
                                    REVIEW_SIZE.height())
            end = parts["review"].left() - 12
        if item.is_password:
            parts["mask"] = QRect(end - 64, line_top, 64, 22)
            end = parts["mask"].left() - 12

        if self.vm.kind_icon(item):
            parts["icon"] = QRect(text_left, line_top, 18, 22)
            text_left += 26
        parts["main"] = QRect(text_left, line_top, max(0, end - text_left), 22)
        parts["source"] = QRect(card.left() + 22, card.top() + 34, max(0, text_right - card.left() - 22), 16)
        return parts

    def _main_font(self, item):
        text_style = self.vm.text_style(item)
        return style.font(13, bold=text_style == "title", italic=text_style == "placeholder")

    def _hovered_part(self, view, rect, item):
        # welcher Knopf liegt gerade unter dem Mauszeiger?
        pos = view.viewport().mapFromGlobal(QCursor.pos())
        if not rect.contains(pos):
            return None
        parts = self._layout(rect, item)
        for name in ("star", "delete", "review"):
            if name in parts and parts[name].contains(pos):
                return name
        return None

    # Zeichnen

    def paint(self, painter, option, index):
        item = index.data(ITEM_ROLE)
        if item is None:
            return
        vm = self.vm
        parts = self._layout(option.rect, item)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        hovered_part = self._hovered_part(option.widget, option.rect, item) if hovered else None

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Hintergrund der Kachel
        card = parts["card"]
        painter.setPen(QPen(style.color("card_border"), 1))
        painter.setBrush(style.color("card_hover" if hovered else "card"))
        painter.drawRoundedRect(card.adjusted(0, 0, -1, -1), 8, 8)

        # farbiger Streifen der Gruppe
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(vm.group_color(item)))
        painter.drawRoundedRect(QRect(card.left() + 6, card.top() + 8, 4, card.height() - 16), 2, 2)

        text = style.color("text")
        muted = style.color("muted")

        # Symbol für Passwort oder Link
        if "icon" in parts:
            painter.setFont(style.font(13, family=style.ICON_FAMILY))
            painter.setPen(muted)
            painter.drawText(parts["icon"], Qt.AlignmentFlag.AlignVCenter, vm.kind_icon(item))

        # Haupttext, bei Platzmangel mit "…" gekürzt
        main_font = self._main_font(item)
        painter.setFont(main_font)
        painter.setPen(muted if vm.text_style(item) == "placeholder" else text)
        main_text = QFontMetrics(main_font).elidedText(vm.display_text(item), Qt.TextElideMode.ElideRight,
                                                       parts["main"].width())
        painter.drawText(parts["main"], Qt.AlignmentFlag.AlignVCenter, main_text)

        small = style.font(11)
        painter.setFont(small)
        if "mask" in parts:
            painter.setPen(muted)
            painter.drawText(parts["mask"], Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, MASK)
        if "review" in parts:
            self._draw_button(painter, parts["review"], "Benennen", small,
                              filled=True, hovered=hovered_part == "review")

        source = vm.source_text(item)
        if source:
            painter.setPen(muted)
            painter.drawText(parts["source"], Qt.AlignmentFlag.AlignVCenter,
                             QFontMetrics(small).elidedText(source, Qt.TextElideMode.ElideRight,
                                                            parts["source"].width()))

        # Uhrzeit über Datum
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        painter.setPen(text)
        painter.drawText(parts["time"], right, vm.time_text(item))
        painter.setPen(muted)
        painter.drawText(parts["date"], right, vm.date_text(item))

        # Stern und X, darunter die Gruppe
        star_font = style.font(15)
        self._draw_button(painter, parts["star"], "★" if item.is_favorite else "☆", star_font,
                          color=style.color("accent") if item.is_favorite else muted,
                          hovered=hovered_part == "star")
        self._draw_button(painter, parts["delete"], "✕", style.font(13), color=muted,
                          hovered=hovered_part == "delete")
        if vm.show_group:
            painter.setFont(small)
            painter.setPen(muted)
            painter.drawText(parts["group"], right, vm.group_name(item, max_length=12))

        painter.restore()

    def _draw_button(self, painter, rect, label, font, color=None, filled=False, hovered=False):
        painter.setPen(Qt.PenStyle.NoPen)
        if filled:
            accent = style.color("accent")
            painter.setBrush(accent.darker(115) if hovered else accent)
            painter.drawRoundedRect(rect, 6, 6)
            color = QColor("white")
        elif hovered:
            painter.setBrush(style.color("button_hover"))
            painter.drawRoundedRect(rect, 6, 6)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    # Klicks

    def editorEvent(self, event, model, option, index):
        if event.type() != QEvent.Type.MouseButtonRelease or event.button() != Qt.MouseButton.LeftButton:
            return False
        item = index.data(ITEM_ROLE)
        if item is None:
            return False
        parts = self._layout(option.rect, item)
        pos = event.position().toPoint()

        if parts["star"].contains(pos):
            self.vm.toggle_favorite(item)
        elif parts["delete"].contains(pos):
            self.vm.delete(item)
        elif "review" in parts and parts["review"].contains(pos):
            self.edit_requested.emit(item)
        elif parts["card"].contains(pos):
            self.vm.copy(item)
        return True

    # Tooltip

    def helpEvent(self, event, view, option, index):
        item = index.data(ITEM_ROLE)
        if item is None or event.type() != QEvent.Type.ToolTip:
            return super().helpEvent(event, view, option, index)
        parts = self._layout(option.rect, item)
        if not parts["main"].contains(event.pos()):
            QToolTip.hideText()
            return True

        metrics = QFontMetrics(self._main_font(item))
        cut = metrics.horizontalAdvance(self.vm.display_text(item)) > parts["main"].width()
        shortened = self.vm.display_text(item) != " ".join((item.content or "").split())
        if not (self.vm.always_tooltip(item) or cut or shortened):
            QToolTip.hideText()
            return True

        # als HTML, damit Qt lange Zeilen umbricht; Inhalt vorher maskieren
        text = html.escape(self.vm.tooltip_text(item)).replace("\n", "<br>")
        QToolTip.showText(event.globalPos(), f"<p style='white-space: pre-wrap'>{text}</p>", view)
        return True


class CardListView(QListView):
    # Kachelansicht: zeigt das Model mit dem Delegate, Qt zeichnet nur die sichtbaren Zeilen

    def __init__(self, vm, on_edit=None, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.list_model = CardListModel(vm, self)
        self.delegate = CardDelegate(vm, self)
        if on_edit is not None:
            self.delegate.edit_requested.connect(on_edit)

        self.setModel(self.list_model)
        self.setItemDelegate(self.delegate)
        self.setUniformItemSizes(True)   # alle Zeilen gleich hoch: Qt muss nicht jede messen
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListView.ResizeMode.Adjust)   # Kacheln wachsen mit der Fensterbreite
        self.apply_colors()
        self.setMouseTracking(True)      # für Hover auf Kacheln und Knöpfen
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._scroll = 0
        self.list_model.modelAboutToBeReset.connect(self._remember_scroll)
        self.list_model.modelReset.connect(self._restore_scroll)

    def apply_colors(self):
        # Hintergrund hinter den Kacheln, passend zu Hell oder Dunkel
        self.setStyleSheet(f"QListView {{ background: {style.color('window').name()}; border: none; }}")

    def _remember_scroll(self):
        self._scroll = self.verticalScrollBar().value()

    def _restore_scroll(self):
        # neue Ansicht nach oben, sonst an derselben Stelle bleiben
        if self.vm.scroll_to_top:
            self.scrollToTop()
        else:
            self.verticalScrollBar().setValue(self._scroll)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        # nur die Kachel unter dem Zeiger neu zeichnen, wegen Hover auf Stern, X und Benennen
        index = self.indexAt(event.position().toPoint())
        self.viewport().update(self.visualRect(index))

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.list_model.rowCount() == 0 and not self.vm.locked:
            painter = QPainter(self.viewport())
            painter.setFont(style.font(13))
            painter.setPen(style.color("muted"))
            painter.drawText(self.viewport().rect().adjusted(0, 24, 0, 0),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.vm.empty_text)
