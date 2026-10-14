"""螢幕下方正中間的小浮動視窗：錄音時顯示跟著聲音跳動的五條音波，處理時顯示「轉譯中」。

視窗不會搶走焦點、滑鼠也點不到它，所以不會影響文字貼到原本的程式。
"""

from __future__ import annotations

import math
import time
from typing import Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFont, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

BG_TOP = QColor(34, 32, 58, 236)
BG_BOTTOM = QColor(16, 16, 30, 242)
EDGE_TOP = QColor(255, 255, 255, 80)
EDGE_BOTTOM = QColor(255, 255, 255, 14)
BAR = QColor(255, 255, 255)
BAR_TOP = QColor("#c3b8ff")
BAR_BOTTOM = QColor("#5fb0ff")
RECORD_DOT = QColor("#ff4f79")
TEXT = QColor(255, 255, 255, 230)
ERROR = QColor("#ff7b7b")

BAR_WEIGHTS = (0.55, 0.8, 1.0, 0.8, 0.55)
BAR_PHASES = (0.0, 1.7, 3.1, 4.4, 5.6)


class Overlay(QWidget):
    W, H = 148, 44
    PAD = 10  # 留給陰影的邊
    MARGIN_BOTTOM = 72

    def __init__(self, level: Callable[[], float]):
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.W + 2 * self.PAD, self.H + 2 * self.PAD)
        self._level_source = level
        self.mode = "hidden"  # hidden / recording / processing / error
        self.message = ""
        self.level = 0.0
        self._t0 = time.monotonic()

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(160)
        self._fade.setEasingCurve(QEasingCurve.OutCubic)
        self._fade.finished.connect(self._fade_done)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.dismiss)

    # ---- 對外 ----

    def show_recording(self) -> None:
        self._enter("recording")

    def show_processing(self) -> None:
        self._enter("processing")

    def show_error(self, message: str) -> None:
        self.message = message
        self._enter("error")
        self._hide_timer.start(2200)

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

    def _enter(self, mode: str) -> None:
        self._hide_timer.stop()
        was_hidden = not self.isVisible() or self.mode == "hidden"
        self.mode = mode
        if mode == "recording":
            self.level = 0.0
        if was_hidden:
            self._place()
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.stop()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        self._timer.start()
        self.update()

    def _fade_done(self) -> None:
        if self.mode == "hidden":
            self._timer.stop()
            self.hide()

    def _place(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(area.center().x() - self.width() // 2, area.bottom() - self.H - self.PAD - self.MARGIN_BOTTOM)

    def _tick(self) -> None:
        if self.mode == "recording":
            raw = max(0.0, min(1.0, self._level_source() * 2.2)) ** 0.7
            # 上升快、下降慢，看起來比較自然
            self.level += (raw - self.level) * (0.55 if raw > self.level else 0.18)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 柔和的陰影
        p.setPen(Qt.NoPen)
        for i in range(self.PAD, 0, -2):
            shadow = QColor(0, 0, 0, int(22 * (1 - i / self.PAD) + 4))
            p.setBrush(shadow)
            r = QRectF(self.PAD - i, self.PAD - i + 3, self.W + 2 * i, self.H + 2 * i - 3)
            p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.translate(self.PAD, self.PAD)
        rect = QRectF(0.5, 0.5, self.W - 1, self.H - 1)
        path = QPainterPath()
        path.addRoundedRect(rect, self.H / 2, self.H / 2)
        fill = QLinearGradient(0, 0, 0, self.H)
        fill.setColorAt(0, BG_TOP)
        fill.setColorAt(1, BG_BOTTOM)
        p.fillPath(path, fill)
        edge = QLinearGradient(0, 0, 0, self.H)
        edge.setColorAt(0, EDGE_TOP)
        edge.setColorAt(1, EDGE_BOTTOM)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        t = time.monotonic() - self._t0

        if self.mode == "recording":
            self._paint_bars(p, t)
        elif self.mode == "processing":
            self._paint_processing(p, t)
        elif self.mode == "error":
            self._paint_text(p, self.message or "失敗", ERROR, left=18)
        p.end()

    def _paint_bars(self, p: QPainter, t: float) -> None:
        # 左邊一個紅點表示錄音中（緩慢呼吸）
        pulse = 0.65 + 0.35 * (0.5 + 0.5 * math.sin(t * 4))
        dot = QColor(RECORD_DOT)
        dot.setAlphaF(pulse)
        p.setPen(Qt.NoPen)
        halo = QColor(RECORD_DOT)
        halo.setAlphaF(0.25 * pulse)
        p.setBrush(halo)
        p.drawEllipse(QRectF(17, self.H / 2 - 7, 14, 14))
        p.setBrush(dot)
        p.drawEllipse(QRectF(20, self.H / 2 - 4, 8, 8))

        bar_w, gap, min_h, max_h = 6.0, 6.0, 6.0, 26.0
        total = len(BAR_WEIGHTS) * bar_w + (len(BAR_WEIGHTS) - 1) * gap
        x = 40 + (self.W - 40 - 16 - total) / 2
        grad = QLinearGradient(0, (self.H - max_h) / 2, 0, (self.H + max_h) / 2)
        grad.setColorAt(0, BAR_TOP)
        grad.setColorAt(1, BAR_BOTTOM)
        p.setBrush(grad)
        for weight, phase in zip(BAR_WEIGHTS, BAR_PHASES):
            wobble = 0.6 + 0.4 * math.sin(t * 9 + phase)
            idle = 0.08 * (0.5 + 0.5 * math.sin(t * 3 + phase))  # 沒聲音時也微微起伏
            amount = min(1.0, self.level * weight * wobble + idle)
            h = min_h + (max_h - min_h) * amount
            p.drawRoundedRect(QRectF(x, (self.H - h) / 2, bar_w, h), bar_w / 2, bar_w / 2)
            x += bar_w + gap

    def _paint_processing(self, p: QPainter, t: float) -> None:
        # 三個依序亮起的點 + 「轉譯中」
        p.setPen(Qt.NoPen)
        for i in range(3):
            a = 0.3 + 0.7 * max(0.0, math.sin(t * 5 - i * 0.9))
            c = QColor(BAR)
            c.setAlphaF(a)
            p.setBrush(c)
            p.drawEllipse(QRectF(22 + i * 10, self.H / 2 - 3, 6, 6))
        self._paint_text(p, "轉譯中", TEXT, left=60)

    def _paint_text(self, p: QPainter, text: str, color: QColor, left: float) -> None:
        font = QFont(self.font())
        font.setPixelSize(14)
        font.setWeight(QFont.DemiBold)
        p.setFont(font)
        p.setPen(color)
        p.drawText(QRectF(left, 0, self.W - left - 16, self.H), Qt.AlignVCenter | Qt.AlignLeft, text)
