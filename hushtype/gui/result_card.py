"""螢幕下方的小框：找不到輸入框時顯示辨識出的文字與「複製」，辨識失敗時提供「重試」。

視窗不搶焦點，按按鈕後游標仍留在原本的程式裡。
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QCursor, QFontMetrics, QGuiApplication
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import glyph_icon

STYLE = """
#cardFrame {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(36, 34, 62, 242), stop:1 rgba(16, 16, 30, 246));
    border: 1px solid rgba(255, 255, 255, 22); border-top-color: rgba(255, 255, 255, 70); border-radius: 18px;
}
QLabel { color: rgba(255, 255, 255, 230); background: transparent; }
#cardTitle { color: rgba(255, 255, 255, 150); font-size: 12px; }
#cardTitle[error="true"] { color: #ff9b9b; }
QPushButton { color: white; background: rgba(255, 255, 255, 30); border: none; border-radius: 10px; padding: 6px 16px; font-weight: 600; }
QPushButton:hover { background: rgba(255, 255, 255, 50); }
QPushButton#cardPrimary { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6d5dfc, stop:1 #2f80ed); border: 1px solid rgba(255, 255, 255, 60); }
QPushButton#cardPrimary:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7f71ff, stop:1 #4893f5); }
QPushButton#cardClose { background: transparent; padding: 3px; border-radius: 8px; }
QPushButton#cardClose:hover { background: rgba(255, 255, 255, 30); }
"""


class ResultCard(QWidget):
    W = 380
    MARGIN_BOTTOM = 72
    VISIBLE_MS = 15000

    def __init__(self, on_retry: Callable[[], None]):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(self.W)
        self.on_retry = on_retry
        self.text = ""
        self.mode = "hidden"  # hidden / text / error

        frame = QFrame(self)
        frame.setObjectName("cardFrame")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(16, 10, 10, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        top.addWidget(self.title, 1)
        close = QPushButton()
        close.setIcon(glyph_icon("close", "#c9c9de"))
        close.setIconSize(QSize(16, 16))
        close.setObjectName("cardClose")
        close.setFocusPolicy(Qt.NoFocus)
        close.clicked.connect(self.dismiss)
        top.addWidget(close)
        lay.addLayout(top)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setFixedWidth(self.W - 26)  # 固定寬度，高度才算得準
        lay.addWidget(self.preview)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.action = QPushButton()
        self.action.setObjectName("cardPrimary")
        self.action.setFocusPolicy(Qt.NoFocus)
        self.action.clicked.connect(self._act)
        buttons.addWidget(self.action)
        lay.addLayout(buttons)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(lambda: self.mode == "hidden" and self.hide())
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._maybe_hide)

    # ---- 對外 ----

    def show_text(self, text: str) -> None:
        self.text = text
        self._set_title("沒有找到輸入框，文字保留在這裡", error=False)
        self.preview.setText(self._elide(text))
        self.preview.show()
        self.action.setText("複製")
        self._enter("text")

    def show_failure(self, message: str) -> None:
        self._set_title("辨識失敗，錄音還在", error=True)
        self.preview.setText(self._elide(message))
        self.preview.show()
        self.action.setText("重試")
        self._enter("error")

    def dismiss(self) -> None:
        if self.mode == "hidden":
            return
        self.mode = "hidden"
        self._hide_timer.stop()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(0.0)
        self._fade.start()

    # ---- 內部 ----

    def _act(self) -> None:
        if self.mode == "text":
            QApplication.clipboard().setText(self.text)
            self.action.setText("已複製")
            self._hide_timer.start(1200)
        elif self.mode == "error":
            self.dismiss()
            self.on_retry()

    def _set_title(self, text: str, *, error: bool) -> None:
        self.title.setText(text)
        self.title.setProperty("error", "true" if error else "false")
        self.title.style().unpolish(self.title)
        self.title.style().polish(self.title)

    def _elide(self, text: str) -> str:
        """最多顯示兩行，太長就用「…」結尾。"""
        flat = " ".join(text.split())
        metrics = QFontMetrics(self.preview.font())
        return metrics.elidedText(flat, Qt.ElideRight, (self.W - 26) * 2 - 60)

    def _enter(self, mode: str) -> None:
        was_hidden = self.mode == "hidden" or not self.isVisible()
        self.mode = mode
        self.layout().activate()
        self.adjustSize()
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.center().x() - self.W // 2, area.bottom() - self.height() - self.MARGIN_BOTTOM)
        if was_hidden:
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.stop()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        self._hide_timer.start(self.VISIBLE_MS)

    def _maybe_hide(self) -> None:
        if self.underMouse():  # 滑鼠停在上面時先不要消失
            self._hide_timer.start(2000)
        else:
            self.dismiss()
