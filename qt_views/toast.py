from PySide6.QtCore import QEvent, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

SHOW_MS = 1800    # so lange bleibt die Meldung stehen
FADE_MS = 200
BOTTOM_MARGIN = 28


class Toast(QLabel):
    # kurze Meldung unten im Fenster, verschwindet von selbst und blockiert nichts

    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)   # Klicks gehen durch
        self.setStyleSheet("QLabel { background: rgba(32, 32, 32, 235); color: white;"
                           " border-radius: 8px; padding: 8px 16px; }")
        self.hide()

        self._effect = QGraphicsOpacityEffect(self)
        self._effect.setOpacity(0.0)
        self.setGraphicsEffect(self._effect)
        self._fade = QPropertyAnimation(self._effect, b"opacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.finished.connect(self._on_fade_finished)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)

        parent.installEventFilter(self)   # bei Größenänderung des Fensters mitwandern

    def show_message(self, text):
        self.setText(text)
        self.adjustSize()
        self._place()
        self.raise_()
        self.show()
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())   # läuft schon eine: dort weitermachen
        self._fade.setEndValue(1.0)
        self._fade.start()
        self._timer.start(SHOW_MS)   # bei schneller Folge neu starten statt stapeln

    def _place(self):
        parent = self.parentWidget()
        x = (parent.width() - self.width()) // 2
        y = parent.height() - self.height() - BOTTOM_MARGIN
        self.move(x, y)

    def _fade_out(self):
        self._fade.stop()
        self._fade.setStartValue(self._effect.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _on_fade_finished(self):
        if self._effect.opacity() == 0.0:
            self.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False
