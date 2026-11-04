import html

from PySide6.QtCore import QAbstractListModel, QEvent, QModelIndex, QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QDrag, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QApplication, QListView, QStyle, QStyledItemDelegate, QToolTip

from viewmodel import MASK

from . import style
from .drag import ITEM_MIME, dragged_items, items_mime, set_preview
from .links import item_link, open_link

ITEM_ROLE = Qt.ItemDataRole.UserRole   # liefert den ClipboardItem einer Zeile

CARD_MARGIN = 4        # Abstand um jede Kachel
PADDING = 10           # Innenabstand oben und unten
BUTTON_WIDTH = 28
GROUP_WIDTH = 96       # Breite für den Gruppennamen unter den Knöpfen
NARROW_CARD = 560      # schmaler als das: ohne Uhrzeit und Datum

BUTTON_TIPS = {
    "open": "Im Browser öffnen",
    "star": "Favorit",
    "delete": "Löschen",
    "review": "Namen und Benutzer eintragen",
}


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
    copied = Signal(object)           # Eintrag wurde in die Zwischenablage kopiert

    def __init__(self, vm, parent=None):
        super().__init__(parent)
        self.vm = vm
        self._font_cache = None

    # Schriften und Maße, alles aus der Systemschrift abgeleitet

    def _fonts(self):
        # einmal anlegen statt bei jeder Kachel neu
        if self._font_cache is None:
            self._font_cache = self._make_fonts()
        return self._font_cache

    def _make_fonts(self):
        return {
            "plain": style.font("normal"),
            "title": style.font("normal", bold=True),
            "placeholder": style.font("normal", italic=True),
            "small": style.font("small"),
            "icon": style.font("normal", family=style.ICON_FAMILY),
            "star": style.font("section"),
        }

    def _line_heights(self):
        fonts = self._fonts()
        first = QFontMetrics(fonts["title"]).height() + 6
        second = QFontMetrics(fonts["small"]).height() + 2
        return first, second

    def sizeHint(self, option, index):
        first, second = self._line_heights()
        # Breite egal: die Liste gibt jeder Zeile die volle Breite
        return QSize(1, 2 * CARD_MARGIN + 2 * PADDING + first + 2 + second)

    # Aufteilung einer Kachel, gemeinsam für Zeichnen, Klicks und Tooltip

    def _layout(self, rect, item):
        first, second = self._line_heights()
        small = QFontMetrics(self._fonts()["small"])
        card = rect.adjusted(CARD_MARGIN, CARD_MARGIN, -CARD_MARGIN, -CARD_MARGIN)
        top1 = card.top() + PADDING
        top2 = top1 + first + 2
        parts = {"card": card, "narrow": card.width() < NARROW_CARD}

        # rechts: Knöpfe in Zeile 1, Gruppe in Zeile 2
        right = card.right() - 8
        buttons = ["delete", "star"] + (["open"] if item_link(item) else [])
        for name in buttons:
            parts[name] = QRect(right - BUTTON_WIDTH, top1, BUTTON_WIDTH, first)
            right -= BUTTON_WIDTH
        action_left = min(right, card.right() - 8 - GROUP_WIDTH)
        parts["group"] = QRect(action_left, top2, card.right() - 8 - action_left, second)

        # davor Uhrzeit über Datum, im schmalen Modus weggelassen
        time_right = action_left - 12
        if not parts["narrow"]:
            time_width = small.horizontalAdvance("00.00.0000") + 8
            parts["time"] = QRect(time_right - time_width, top1, time_width, first)
            parts["date"] = QRect(time_right - time_width, top2, time_width, second)
            time_right -= time_width + 16

        text_left = card.left() + 22
        has_source = bool(self.vm.source_text(item))
        line_top = top1 if has_source else card.top() + (card.height() - first) // 2

        # rechts in der ersten Zeile: Benennen-Knopf und Maske
        end = time_right
        if item.needs_review:
            width = small.horizontalAdvance("Benennen") + 20
            parts["review"] = QRect(end - width, line_top + 2, width, first - 4)
            end = parts["review"].left() - 12
        if item.is_password:
            width = small.horizontalAdvance(MASK) + 4
            parts["mask"] = QRect(end - width, line_top, width, first)
            end = parts["mask"].left() - 12

        if self.vm.kind_icon(item):
            parts["icon"] = QRect(text_left, line_top, 18, first)
            text_left += 26
        parts["main"] = QRect(text_left, line_top, max(0, end - text_left), first)
        parts["source"] = QRect(card.left() + 22, top2, max(0, time_right - card.left() - 22), second)
        return parts

    def _hovered_part(self, view, rect, item):
        # welcher Knopf liegt gerade unter dem Mauszeiger?
        pos = view.viewport().mapFromGlobal(QCursor.pos())
        if not rect.contains(pos):
            return None
        parts = self._layout(rect, item)
        for name in BUTTON_TIPS:
            if name in parts and parts[name].contains(pos):
                return name
        return None

    # Zeichnen

    def paint(self, painter, option, index):
        item = index.data(ITEM_ROLE)
        if item is None:
            return
        vm = self.vm
        fonts = self._fonts()
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
        left_middle = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        right_middle = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        # Symbol für Passwort oder Link
        if "icon" in parts:
            painter.setFont(fonts["icon"])
            painter.setPen(muted)
            painter.drawText(parts["icon"], left_middle, vm.kind_icon(item))

        # Haupttext, bei Platzmangel mit "…" gekürzt
        text_style = vm.text_style(item)
        painter.setFont(fonts[text_style])
        painter.setPen(muted if text_style == "placeholder" else text)
        main_text = QFontMetrics(fonts[text_style]).elidedText(
            vm.display_text(item), Qt.TextElideMode.ElideRight, parts["main"].width())
        painter.drawText(parts["main"], left_middle, main_text)

        painter.setFont(fonts["small"])
        if "mask" in parts:
            painter.setPen(muted)
            painter.drawText(parts["mask"], right_middle, MASK)
        if "review" in parts:
            self._draw_button(painter, parts["review"], "Benennen", fonts["small"],
                              filled=True, hovered=hovered_part == "review")

        source = vm.source_text(item)
        if source:
            painter.setFont(fonts["small"])
            painter.setPen(muted)
            painter.drawText(parts["source"], left_middle, QFontMetrics(fonts["small"]).elidedText(
                source, Qt.TextElideMode.ElideRight, parts["source"].width()))

        # Uhrzeit über Datum
        if "time" in parts:
            painter.setFont(fonts["small"])
            painter.setPen(text)
            painter.drawText(parts["time"], right_middle, vm.time_text(item))
            painter.setPen(muted)
            painter.drawText(parts["date"], right_middle, vm.date_text(item))

        # Öffnen, Stern und X, darunter die Gruppe
        if "open" in parts:
            self._draw_button(painter, parts["open"], "↗", fonts["star"], color=style.color("accent"),
                              hovered=hovered_part == "open")
        self._draw_button(painter, parts["star"], "★" if item.is_favorite else "☆", fonts["star"],
                          color=style.color("accent") if item.is_favorite else muted,
                          hovered=hovered_part == "star")
        self._draw_button(painter, parts["delete"], "✕", fonts["plain"], color=muted,
                          hovered=hovered_part == "delete")
        if vm.show_group:
            painter.setFont(fonts["small"])
            painter.setPen(muted)
            painter.drawText(parts["group"], right_middle, QFontMetrics(fonts["small"]).elidedText(
                vm.group_name(item), Qt.TextElideMode.ElideRight, parts["group"].width()))

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
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
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

        if "open" in parts and parts["open"].contains(pos):
            open_link(item_link(item))
        elif parts["star"].contains(pos):
            self.vm.toggle_favorite(item)
        elif parts["delete"].contains(pos):
            self.vm.delete(item)
        elif "review" in parts and parts["review"].contains(pos):
            self.edit_requested.emit(item)
        elif parts["card"].contains(pos):
            self.vm.copy(item)
            self.copied.emit(item)
        return True

    # Tooltip

    def helpEvent(self, event, view, option, index):
        item = index.data(ITEM_ROLE)
        if item is None or event.type() != QEvent.Type.ToolTip:
            return super().helpEvent(event, view, option, index)
        parts = self._layout(option.rect, item)
        pos = event.pos()

        for name, tip in BUTTON_TIPS.items():
            if name in parts and parts[name].contains(pos):
                QToolTip.showText(event.globalPos(), tip, view)
                return True

        text = self._tooltip(item, parts)
        if text is None or not parts["main"].contains(pos):
            QToolTip.hideText()
            return True
        # als HTML, damit Qt lange Zeilen umbricht; Inhalt vorher maskieren
        body = html.escape(text).replace("\n", "<br>")
        QToolTip.showText(event.globalPos(), f"<p style='white-space: pre-wrap'>{body}</p>", view)
        return True

    def _tooltip(self, item, parts):
        vm = self.vm
        display = vm.display_text(item)
        font = self._fonts()[vm.text_style(item)]
        cut = QFontMetrics(font).horizontalAdvance(display) > parts["main"].width()
        shortened = not item.is_password and display != " ".join((item.content or "").split())
        if not (vm.always_tooltip(item) or cut or shortened or parts["narrow"]):
            return None
        text = vm.tooltip_text(item)
        if parts["narrow"] and not item.is_password:
            text += f"\n\n{vm.datetime_text(item)}"   # Datum fehlt in der schmalen Kachel
        return text


class CardListView(QListView):
    # Kachelansicht: zeigt das Model mit dem Delegate, Qt zeichnet nur die sichtbaren Zeilen

    copied = Signal(object)
    menu_requested = Signal(object, QPoint)   # Eintrag und Bildschirmposition für das Kontextmenü

    def __init__(self, vm, on_edit=None, parent=None):
        super().__init__(parent)
        self.vm = vm
        self.list_model = CardListModel(vm, self)
        self.delegate = CardDelegate(vm, self)
        if on_edit is not None:
            self.delegate.edit_requested.connect(on_edit)
        self.delegate.copied.connect(self.copied)

        self.setModel(self.list_model)
        self.setItemDelegate(self.delegate)
        self.setUniformItemSizes(True)   # alle Zeilen gleich hoch: Qt muss nicht jede messen
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(24)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setFrameShape(QListView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setResizeMode(QListView.ResizeMode.Adjust)   # Kacheln wachsen mit der Fensterbreite
        self.setMouseTracking(True)      # für Hover auf Kacheln und Knöpfen
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAcceptDrops(True)
        self.apply_colors()

        self._scroll = 0
        self._press_pos = None   # Startpunkt für ein mögliches Ziehen
        self._drop = None        # (Zeile, danach) für die Einfügelinie
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

    # Maus

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        pos = event.position().toPoint()
        if (event.buttons() & Qt.MouseButton.LeftButton and self._press_pos is not None
                and (pos - self._press_pos).manhattanLength() >= QApplication.startDragDistance()):
            self._start_drag(self.indexAt(self._press_pos))
            return
        # nur die Kachel unter dem Zeiger neu zeichnen, wegen Hover auf den Knöpfen
        self.viewport().update(self.visualRect(self.indexAt(pos)))

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.viewport().update()

    def contextMenuEvent(self, event):
        item = self.indexAt(event.pos()).data(ITEM_ROLE)
        if item is not None:
            self.menu_requested.emit(item, event.globalPos())

    # Ziehen: in eine Gruppe der Seitenleiste oder an eine andere Stelle

    def _start_drag(self, index):
        self._press_pos = None
        item = index.data(ITEM_ROLE)
        if item is None:
            return
        drag = QDrag(self)
        drag.setMimeData(items_mime([item]))
        set_preview(drag, self, [item], self.vm)   # kleine Vorschau statt der ganzen Kachel
        drag.exec(Qt.DropAction.MoveAction)
        self._set_drop(None)

    def _drop_target(self, pos):
        # Zeile und ob davor oder danach eingefügt wird
        index = self.indexAt(pos)
        if not index.isValid():
            return (self.list_model.rowCount() - 1, True) if self.list_model.rowCount() else None
        rect = self.visualRect(index)
        return index.row(), pos.y() > rect.center().y()

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
        target = self.list_model.index(row).data(ITEM_ROLE)
        event.acceptProposedAction()
        self.vm.move(items[0], target, after=after)

    # Zeichnen

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self.list_model.rowCount() == 0 and not self.vm.locked:
            painter.setFont(style.font("normal"))
            painter.setPen(style.color("muted"))
            painter.drawText(self.viewport().rect().adjusted(0, 24, 0, 0),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.vm.empty_text)
        if self._drop is not None:
            # Einfügelinie zwischen zwei Kacheln
            row, after = self._drop
            rect = self.visualRect(self.list_model.index(row))
            y = rect.bottom() if after else rect.top()
            painter.setPen(QPen(style.color("accent"), 3))
            painter.drawLine(rect.left() + 8, y, rect.right() - 8, y)
