"""共用元件：卡片、數字方塊、長條圖。"""

from __future__ import annotations

import math
from typing import Callable

from datetime import date, timedelta

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from . import theme


def label(text: str = "", name: str | None = None, *, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


class Card(QFrame):
    def __init__(self, title: str | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)
        if title:
            self.body.addWidget(label(title, "h2"))


class StatTile(Card):
    def __init__(self, title: str):
        super().__init__()
        self.body.setSpacing(2)
        self.title = label(title, "secondary")
        self.value = label("—", "big")
        self.sub = label("", "muted")
        for w in (self.title, self.value, self.sub):
            self.body.addWidget(w)

    def set(self, value: str, unit: str = "", sub: str = "") -> None:
        unit_html = f'<span style="font-size:14px;font-weight:400">&nbsp;{unit}</span>' if unit else ""
        self.value.setText(f"{value}{unit_html}")
        self.sub.setText(sub)


class StateDot(QWidget):
    def __init__(self, size: int = 18):
        super().__init__()
        self._color = QColor("#8f8e86")
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))


def nice_max(v: float) -> float:
    """可被 4 整除的漂亮上限，讓格線刻度是整齊的數字。"""
    if v <= 0:
        return 4
    raw = v / 4
    p = 10 ** math.floor(math.log10(raw))
    for s in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if s * p >= raw:
            return s * p * 4
    return 40 * p


def _fmt(v: float) -> str:
    return f"{v:,.1f}".rstrip("0").rstrip(".") if v % 1 else f"{v:,.0f}"


class BarChart(QWidget):
    """單一數列長條圖，滑鼠移上去顯示數值。"""

    L, R, T, B = 44, 8, 10, 26

    def __init__(self, height: int = 200):
        super().__init__()
        self.setMinimumHeight(height)
        self.setMouseTracking(True)
        self.items: list = []
        self.value: Callable = lambda d: 0
        self.label_of: Callable = lambda d: ""
        self.tip: Callable = lambda d: ""
        self.label_width = 44
        self.hover = -1

    def sizeHint(self) -> QSize:
        return QSize(600, self.minimumHeight())

    def set_data(self, items, *, value, label, tip, label_width: int = 44) -> None:
        self.items, self.value, self.label_of, self.tip = list(items), value, label, tip
        self.label_width = label_width
        self.hover = -1
        self.update()

    def _geometry(self):
        pw = self.width() - self.L - self.R
        ph = self.height() - self.T - self.B
        step = pw / max(len(self.items), 1)
        return pw, ph, step

    def paintEvent(self, _event) -> None:
        c = theme.current
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pw, ph, step = self._geometry()
        values = [self.value(d) for d in self.items]
        top = nice_max(max(values, default=0))
        fm = QFontMetrics(p.font())
        font = p.font()
        font.setPixelSize(11)
        p.setFont(font)

        for i in range(5):
            y = self.T + ph - ph * i / 4
            p.setPen(QPen(QColor(c["grid"]), 1))
            p.drawLine(QPointF(self.L, y), QPointF(self.width() - self.R, y))
            p.setPen(QColor(c["text_muted"]))
            p.drawText(QRectF(0, y - 8, self.L - 6, 16), Qt.AlignRight | Qt.AlignVCenter, _fmt(top * i / 4))

        bw = max(min(step - 2, 28), 2)
        every = math.ceil(len(self.items) / max(int(pw / self.label_width), 1)) if self.items else 1
        for i, (d, v) in enumerate(zip(self.items, values)):
            h = v / top * ph
            x = self.L + i * step + (step - bw) / 2
            y = self.T + ph - h
            if h > 0:
                r = min(4, bw / 2, h)
                path = QPainterPath()
                path.moveTo(x, self.T + ph)
                path.lineTo(x, y + r)
                path.quadTo(x, y, x + r, y)
                path.lineTo(x + bw - r, y)
                path.quadTo(x + bw, y, x + bw, y + r)
                path.lineTo(x + bw, self.T + ph)
                path.closeSubpath()
                p.fillPath(path, QColor(c["accent_hover"] if i == self.hover else c["accent"]))
            if i % every == 0:
                p.setPen(QColor(c["text_muted"]))
                cx = self.L + i * step + step / 2
                p.drawText(QRectF(cx - 30, self.height() - self.B + 6, 60, 16), Qt.AlignCenter, self.label_of(d))
        p.setPen(QPen(QColor(c["text_muted"]), 1))
        p.drawLine(QPointF(self.L, self.T + ph), QPointF(self.width() - self.R, self.T + ph))
        del fm
        p.end()

    def mouseMoveEvent(self, event) -> None:
        pw, ph, step = self._geometry()
        i = int((event.position().x() - self.L) // step) if step else -1
        if not 0 <= i < len(self.items) or event.position().y() > self.T + ph:
            i = -1
        if i != self.hover:
            self.hover = i
            self.update()
        if i >= 0:
            QToolTip.showText(event.globalPosition().toPoint(), self.tip(self.items[i]), self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, _event) -> None:
        self.hover = -1
        self.update()


class Heatmap(QWidget):
    """像 GitHub 那樣的每日活躍方格：一欄一週，一列一個星期幾，顏色越深用得越多。"""

    CELL, GAP, LEFT, BOTTOM = 13, 4, 22, 20
    DAYS = ["日", "一", "二", "三", "四", "五", "六"]

    def __init__(self):
        super().__init__()
        self.counts: dict[str, int] = {}
        self.today = date.today()
        self.setMouseTracking(True)
        self.setMinimumHeight(self.GAP + 7 * (self.CELL + self.GAP) + self.BOTTOM)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(600, self.minimumHeight())

    def set_counts(self, counts: dict[str, int], today: date | None = None) -> None:
        self.counts, self.today = counts, today or date.today()
        self.update()

    def _weeks(self) -> int:
        return max(4, (self.width() - self.LEFT) // (self.CELL + self.GAP))

    def _start(self) -> date:
        # 最後一欄是本週（週日開始）
        last_sunday = self.today - timedelta(days=(self.today.weekday() + 1) % 7)
        return last_sunday - timedelta(weeks=self._weeks() - 1)

    def _cell(self, week: int, dow: int) -> QRectF:
        step = self.CELL + self.GAP
        return QRectF(self.LEFT + week * step, dow * step, self.CELL, self.CELL)

    def _level(self, n: int, top: int) -> int:
        if n <= 0:
            return 0
        return min(4, 1 + int(3 * n / max(top, 1)))

    def paintEvent(self, _event) -> None:
        c = theme.current
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)
        start, weeks = self._start(), self._weeks()
        top = max(self.counts.values(), default=1)
        accent = QColor(c["accent"])
        empty = QColor(c["surface_alt"])
        p.setPen(QColor(c["text_muted"]))
        for dow in (1, 3, 5):
            p.drawText(QRectF(0, self._cell(0, dow).top(), self.LEFT - 6, self.CELL), Qt.AlignRight | Qt.AlignVCenter, self.DAYS[dow])
        last_month = None
        for w in range(weeks):
            for dow in range(7):
                d = start + timedelta(days=w * 7 + dow)
                if d > self.today:
                    continue
                level = self._level(self.counts.get(d.isoformat(), 0), top)
                if level:
                    col = QColor(accent)
                    col.setAlphaF((0.25, 0.45, 0.7, 1.0)[level - 1])
                else:
                    col = empty
                p.setPen(Qt.NoPen)
                p.setBrush(col)
                p.drawRoundedRect(self._cell(w, dow), 3, 3)
            first = start + timedelta(days=w * 7)
            if first.month != last_month and first.day <= 7:
                p.setPen(QColor(c["text_muted"]))
                p.drawText(QRectF(self._cell(w, 0).left(), self.height() - self.BOTTOM + 4, 50, 14), Qt.AlignLeft, f"{first.month} 月")
                last_month = first.month
        p.end()

    def mouseMoveEvent(self, event) -> None:
        step = self.CELL + self.GAP
        w = int((event.position().x() - self.LEFT) // step)
        dow = int(event.position().y() // step)
        if 0 <= w < self._weeks() and 0 <= dow < 7:
            d = self._start() + timedelta(days=w * 7 + dow)
            if d <= self.today:
                n = self.counts.get(d.isoformat(), 0)
                QToolTip.showText(event.globalPosition().toPoint(), f"{d:%Y/%m/%d}：{n} 次" if n else f"{d:%Y/%m/%d}：沒有使用", self)
                return
        QToolTip.hideText()


class FlowLayout(QLayout):
    """自動換行的排列，用在字典的詞彙標籤。"""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect, *, apply: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() and line > 0:
                x, y, line = rect.x(), y + line + self._spacing, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line = max(line, hint.height())
        return y + line - rect.y()
