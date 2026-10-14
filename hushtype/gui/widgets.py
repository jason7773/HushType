"""共用元件：極光背景、玻璃卡片、漸層標題、數字方塊、圖表。"""

from __future__ import annotations

import math
from typing import Callable

from datetime import date, timedelta

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QLayout, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from . import theme


def label(text: str = "", name: str | None = None, *, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def icon_label(kind: str, color: str | None = None, size: int = 16) -> QLabel:
    lab = QLabel()
    lab.setPixmap(theme.glyph_pixmap(kind, color, size))
    lab.setFixedSize(size, size)
    lab.setStyleSheet("background: transparent;")
    return lab


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


def _mix(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(
        round(a.red() + (b.red() - a.red()) * t),
        round(a.green() + (b.green() - a.green()) * t),
        round(a.blue() + (b.blue() - a.blue()) * t),
    )


class AuroraBackground(QWidget):
    """整個視窗的底：幾團柔和的彩色光暈緩慢飄動，狀態改變時換色。

    先畫在很小的圖上再放大，光暈自然模糊，也省效能。視窗不在前景時停止動畫。
    """

    SCALE = 6
    BLOBS = ((0.18, 0.12, 0.62), (0.86, 0.18, 0.55), (0.70, 0.92, 0.60), (0.12, 0.85, 0.48))

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self._t = 0.0
        self._colors = [QColor(x) for x in theme.current["aurora"]]
        self._from = list(self._colors)
        self._to = list(self._colors)
        self._mix = 1.0
        self.animated = True
        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._tick)

    def set_running(self, on: bool) -> None:
        if on and self.animated:
            self._timer.start()
        elif self._mix >= 1.0:
            self._timer.stop()

    def set_colors(self, colors) -> None:
        target = [QColor(x) for x in colors]
        if [c.name() for c in target] == [c.name() for c in self._to]:
            return
        self._from, self._to, self._mix = list(self._colors), target, 0.0
        self._timer.start()

    def _tick(self) -> None:
        if self.animated:
            self._t += 0.08
        if self._mix < 1.0:
            self._mix = min(1.0, self._mix + 0.07)
            k = 1 - (1 - self._mix) ** 3
            self._colors = [_mix(a, b, k) for a, b in zip(self._from, self._to)]
            if self._mix >= 1.0 and not (self.animated and self.window().isActiveWindow()):
                self._timer.stop()
        self.update()

    def paintEvent(self, _event) -> None:
        c = theme.current
        w, h = max(self.width() // self.SCALE, 8), max(self.height() // self.SCALE, 8)
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(c["aurora_base"]))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        alpha = c["aurora_alpha"]
        for i, ((bx, by, br), col) in enumerate(zip(self.BLOBS, self._colors)):
            t = self._t * (0.11 + 0.03 * i) + i * 1.7
            cx = (bx + 0.08 * math.sin(t) + 0.04 * math.sin(t * 2.3)) * w
            cy = (by + 0.07 * math.cos(t * 0.9) + 0.03 * math.sin(t * 1.7)) * h
            radius = br * max(w, h) * (1 + 0.06 * math.sin(t * 1.3))
            grad = QRadialGradient(QPointF(cx, cy), radius)
            inner = QColor(col)
            inner.setAlphaF(alpha)
            outer = QColor(col)
            outer.setAlphaF(0)
            grad.setColorAt(0, inner)
            grad.setColorAt(1, outer)
            p.fillRect(QRectF(0, 0, w, h), grad)
        p.end()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawImage(QRectF(self.rect()), img)
        painter.end()


class GlassFrame(QFrame):
    """半透明玻璃面板：上亮下暗的填色、漸層邊框，滑鼠移過時有一圈跟著游標的光暈。"""

    def __init__(self, parent: QWidget | None = None, *, radius: float = 20, tone: str = "card", spotlight: bool = True):
        super().__init__(parent)
        self.radius = radius
        self.tone = tone
        self.spotlight = spotlight
        self.spot: QPointF | None = None

    def set_spot(self, pos: QPointF | None) -> None:
        if pos != self.spot:
            self.spot = pos
            self.update()

    def paintEvent(self, _event) -> None:
        c = theme.current
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)

        fill = QLinearGradient(0, 0, 0, r.height())
        fill.setColorAt(0, theme.qcolor(c["glass_top"]))
        fill.setColorAt(1, theme.qcolor(c["glass_bottom"]))
        p.fillPath(path, fill)
        if self.tone == "accent":
            tint = QLinearGradient(0, 0, r.width(), r.height())
            a, b = QColor(theme.BRAND[0]), QColor(theme.BRAND[1])
            a.setAlphaF(0.22)
            b.setAlphaF(0.12)
            tint.setColorAt(0, a)
            tint.setColorAt(1, b)
            p.fillPath(path, tint)
        if self.spot is not None:
            glow = QRadialGradient(self.spot, 240)
            col = QColor(255, 255, 255)
            col.setAlphaF(0.10 if theme.is_dark() else 0.45)
            glow.setColorAt(0, col)
            col = QColor(col)
            col.setAlphaF(0)
            glow.setColorAt(1, col)
            p.fillPath(path, glow)

        edge = QLinearGradient(0, 0, 0, r.height())
        edge.setColorAt(0, theme.qcolor(c["glass_edge"]))
        shade = theme.qcolor(c["glass_shade"])
        edge.setColorAt(1, shade)
        p.setPen(QPen(QBrush(edge), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()


class Spotlight(QObject):
    """把滑鼠位置告訴底下的玻璃卡片，讓光暈跟著游標走。"""

    def __init__(self, root: QWidget):
        super().__init__(root)
        self.root = root
        self.current: GlassFrame | None = None

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.MouseMove:
            w = QApplication.widgetAt(event.globalPosition().toPoint())
            target = None
            while w is not None:
                if isinstance(w, GlassFrame) and w.spotlight:
                    target = w
                    break
                if w is self.root:
                    break
                w = w.parentWidget()
            if self.current is not None and self.current is not target:
                try:
                    self.current.set_spot(None)
                except RuntimeError:
                    pass
            self.current = target
            if target is not None:
                target.set_spot(QPointF(target.mapFromGlobal(event.globalPosition().toPoint())))
        elif event.type() == QEvent.Leave and obj is self.root and self.current is not None:
            self.current.set_spot(None)
            self.current = None
        return False


class HeroTitle(QWidget):
    """大標題：文字用深色到品牌紫藍的漸層填色。"""

    def __init__(self, text: str, size: int = 34):
        super().__init__()
        self.text = text
        self._font = QFont(self.font())
        self._font.setPixelSize(size)
        self._font.setWeight(QFont.ExtraBold)
        fm = QFontMetrics(self._font)
        self.setMinimumHeight(fm.height() + 6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self._font)
        return QSize(fm.horizontalAdvance(self.text) + 8, fm.height() + 6)

    def setText(self, text: str) -> None:
        self.text = text
        self.updateGeometry()
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        fm = QFontMetrics(self._font)
        width = fm.horizontalAdvance(self.text)
        grad = QLinearGradient(0, 0, max(width, 1), 0)
        grad.setColorAt(0, QColor(theme.current["text"]))
        grad.setColorAt(0.45, QColor(theme.current["text"]))
        grad.setColorAt(0.8, QColor(theme.BRAND[0]))
        grad.setColorAt(1, QColor(theme.BRAND[1]))
        path = QPainterPath()
        path.addText(QPointF(1, fm.ascent() + 2), self._font, self.text)
        p.fillPath(path, grad)
        p.end()


class Card(GlassFrame):
    def __init__(self, title: str | None = None, parent: QWidget | None = None, **kw):
        super().__init__(parent, **kw)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
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

        grid = theme.qcolor(c["glass_shade"])
        for i in range(5):
            y = self.T + ph - ph * i / 4
            p.setPen(QPen(grid, 1, Qt.DashLine if i else Qt.SolidLine))
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
                r = min(6, bw / 2, h)
                path = QPainterPath()
                path.moveTo(x, self.T + ph)
                path.lineTo(x, y + r)
                path.quadTo(x, y, x + r, y)
                path.lineTo(x + bw - r, y)
                path.quadTo(x + bw, y, x + bw, y + r)
                path.lineTo(x + bw, self.T + ph)
                path.closeSubpath()
                grad = QLinearGradient(0, y, 0, self.T + ph)
                top_col, bottom_col = QColor(theme.BRAND[1]), QColor(theme.BRAND[0])
                bottom_col.setAlphaF(0.95 if i == self.hover else 0.55)
                if i == self.hover:
                    top_col = top_col.lighter(120)
                grad.setColorAt(0, top_col)
                grad.setColorAt(1, bottom_col)
                p.fillPath(path, grad)
            if i % every == 0:
                p.setPen(QColor(c["text_muted"]))
                cx = self.L + i * step + step / 2
                p.drawText(QRectF(cx - 30, self.height() - self.B + 6, 60, 16), Qt.AlignCenter, self.label_of(d))
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
        levels = heat_colors()
        empty = QColor(c["text_muted"])
        empty.setAlphaF(0.13)
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
                col = levels[level - 1] if level else empty
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


def heat_colors() -> list[QColor]:
    """活躍日曆的四個深淺：淡藍 → 品牌紫。"""
    a, b = QColor(theme.BRAND[1]), QColor(theme.BRAND[0])
    out = []
    for i, alpha in enumerate((0.30, 0.55, 0.80, 1.0)):
        col = _mix(a, b, i / 3)
        col.setAlphaF(alpha)
        out.append(col)
    return out


class HeatLegend(QWidget):
    """「較少 ■■■■ 較多」圖例，色塊用畫的。"""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(16)
        self.setMinimumWidth(150)

    def paintEvent(self, _event) -> None:
        c = theme.current
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = p.font()
        font.setPixelSize(11)
        p.setFont(font)
        fm = QFontMetrics(font)
        right = self.width()
        more, less = "較多", "較少"
        p.setPen(QColor(c["text_muted"]))
        x = right - fm.horizontalAdvance(more)
        p.drawText(QPointF(x, 12), more)
        x -= 8
        empty = QColor(c["text_muted"])
        empty.setAlphaF(0.13)
        for col in reversed([empty, *heat_colors()]):
            x -= 12
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x, 2, 11, 11), 3, 3)
            x -= 3
        p.setPen(QColor(c["text_muted"]))
        p.drawText(QPointF(x - 5 - fm.horizontalAdvance(less), 12), less)
        p.end()


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
