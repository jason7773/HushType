"""配色、樣式表與圖示。跟隨 Windows 的淺色 / 深色模式。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

# 玻璃風格：底層是緩慢流動的極光漸層，上面疊半透明的玻璃卡片。
# glass_* 是 (r, g, b, alpha) ，其餘是一般色碼。
LIGHT = {
    "bg": "#eef0f9",
    "surface": "#ffffff",
    "surface_alt": "#e6e8f4",
    "border": "#d9dcec",
    "text": "#15152b",
    "text_secondary": "#4a4a66",
    "text_muted": "#7d7d99",
    "grid": "#dfe1ef",
    "accent": "#5b54f0",
    "accent_hover": "#463fd8",
    "accent_soft": "#e7e6ff",
    "accent_text": "#ffffff",
    "good": "#0f8a4a",
    "bad": "#d23c4f",
    "warn": "#a35f00",
    "glass_top": (255, 255, 255, 0.74),
    "glass_bottom": (255, 255, 255, 0.52),
    "glass_edge": (255, 255, 255, 0.95),
    "glass_shade": (40, 40, 110, 0.10),
    "glass_hover": (255, 255, 255, 0.86),
    "field": (255, 255, 255, 0.70),
    "save_bar": (246, 244, 255, 0.94),
    "aurora_base": "#eef0f9",
    "aurora": ("#8f7dff", "#4fa8ff", "#ff9bd2", "#5fe3d2"),
    "aurora_alpha": 0.55,
}

DARK = {
    "bg": "#0b0b16",
    "surface": "#17172a",
    "surface_alt": "#222238",
    "border": "#2c2c46",
    "text": "#f3f3fb",
    "text_secondary": "#babad2",
    "text_muted": "#85859f",
    "grid": "#25253a",
    "accent": "#8b84ff",
    "accent_hover": "#a9a4ff",
    "accent_soft": "#25234a",
    "accent_text": "#ffffff",
    "good": "#4fd68a",
    "bad": "#ff7d8c",
    "warn": "#f0b85a",
    "glass_top": (255, 255, 255, 0.085),
    "glass_bottom": (255, 255, 255, 0.035),
    "glass_edge": (255, 255, 255, 0.16),
    "glass_shade": (0, 0, 0, 0.35),
    "glass_hover": (255, 255, 255, 0.12),
    "field": (255, 255, 255, 0.06),
    "save_bar": (22, 20, 40, 0.94),
    "aurora_base": "#0b0b16",
    "aurora": ("#6d5dfc", "#2f80ed", "#c04dff", "#14b8a6"),
    "aurora_alpha": 0.42,
}


def rgba(value) -> str:
    """給樣式表用：(r, g, b, a) → rgba(...)；一般色碼原樣回傳。"""
    if isinstance(value, tuple):
        r, g, b, a = value
        return f"rgba({r}, {g}, {b}, {int(a * 255)})"
    return value


def qcolor(value) -> QColor:
    if isinstance(value, tuple):
        r, g, b, a = value
        col = QColor(r, g, b)
        col.setAlphaF(a)
        return col
    return QColor(value)


# 引擎狀態 → (顯示名稱, 顏色)
STATES = {
    "idle": ("待命中", "#5b54f0"),
    "recording": ("錄音中", "#f0476a"),
    "processing": ("處理中", "#f2a516"),
    "paused": ("已暫停", "#8a8aa3"),
    "setup": ("需要設定", "#8a8aa3"),
}

# 極光背景隨狀態換色：錄音時偏暖紅、處理時偏琥珀
STATE_AURORA = {
    "recording": ("#ff5f87", "#ff8a5c", "#c04dff", "#ffb36b"),
    "processing": ("#ffb020", "#ff7a59", "#8f7dff", "#5fe3d2"),
}

THEMES = [("跟隨系統", "system"), ("淺色", "light"), ("深色", "dark")]

current = dict(LIGHT)
mode = "system"


def is_dark() -> bool:
    if mode == "dark":
        return True
    if mode == "light":
        return False
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def _asset_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "hushtype-ui"
    d.mkdir(exist_ok=True)
    return d


def _draw_asset(name: str, color: str, size: int, draw) -> str:
    """把小圖示畫成 PNG，給樣式表的 url() 使用。"""
    path = _asset_dir() / f"{name}-{color.lstrip('#')}.png"
    if not path.exists():
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        draw(p, QColor(color), size)
        p.end()
        pm.save(str(path))
    return path.as_posix()


def _chevron(p: QPainter, color: QColor, size: int) -> None:
    p.setPen(QPen(color, size * 0.11, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    path.moveTo(size * 0.28, size * 0.40)
    path.lineTo(size * 0.50, size * 0.62)
    path.lineTo(size * 0.72, size * 0.40)
    p.drawPath(path)


def _check(p: QPainter, color: QColor, size: int) -> None:
    p.setPen(QPen(color, size * 0.13, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    path = QPainterPath()
    path.moveTo(size * 0.25, size * 0.52)
    path.lineTo(size * 0.43, size * 0.70)
    path.lineTo(size * 0.76, size * 0.33)
    p.drawPath(path)


def _stylesheet(c: dict) -> str:
    chevron = _draw_asset("chevron", c["text_secondary"], 32, _chevron)
    check = _draw_asset("check", "#ffffff", 32, _check)
    g0, g1 = BRAND
    glass = f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {rgba(c['glass_top'])}, stop:1 {rgba(c['glass_bottom'])})"
    glass_hover = rgba(c["glass_hover"])
    edge, shade, field = rgba(c["glass_edge"]), rgba(c["glass_shade"]), rgba(c["field"])
    brand = f"qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {g0}, stop:1 {g1})"
    brand_soft = (
        f"qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(109, 93, 252, 70), stop:1 rgba(47, 128, 237, 30))"
    )
    return f"""
    QWidget {{ color: {c['text']}; font-size: 14px; }}
    QMainWindow, #page, #side, #card, #keyCard, #updateCard, #entry, #chip {{ background: transparent; border: none; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QStackedWidget {{ background: transparent; }}

    #sidebar {{ background: transparent; border: none; outline: 0; padding: 6px 10px; }}
    #sidebar::item {{ padding: 10px 12px; border-radius: 12px; margin: 2px 0; color: {c['text_secondary']}; border: 1px solid transparent; }}
    #sidebar::item:selected {{ background: {brand_soft}; color: {c['text']}; font-weight: 600; border: 1px solid {edge}; }}
    #sidebar::item:hover:!selected {{ background: {glass_hover}; color: {c['text']}; }}
    #brand {{ font-size: 18px; font-weight: 800; letter-spacing: 0.3px; }}
    #brandSub {{ color: {c['text_muted']}; font-size: 11px; letter-spacing: 1px; }}

    #h1 {{ font-size: 24px; font-weight: 700; }}
    #h2 {{ font-size: 15px; font-weight: 700; }}
    #muted {{ color: {c['text_muted']}; font-size: 12px; }}
    #secondary {{ color: {c['text_secondary']}; }}
    #eyebrow {{ color: {c['accent']}; font-size: 11px; font-weight: 700; letter-spacing: 2px; }}
    #big {{ font-size: 26px; font-weight: 700; }}
    #stateTitle {{ font-size: 20px; font-weight: 800; }}
    #h1small {{ font-size: 13px; font-weight: 700; color: {c['text_muted']}; letter-spacing: 2px; margin-top: 8px; }}
    #bigger {{ font-size: 30px; font-weight: 800; }}
    #keyChip {{
        background: {glass}; border: 1px solid {edge}; border-bottom: 3px solid {shade};
        border-radius: 9px; padding: 4px 12px; font-weight: 800; font-size: 15px;
    }}
    #entryText {{ line-height: 150%; }}
    #divider {{ background: {edge}; border: none; }}
    #chipMark {{ color: {c['accent']}; font-size: 11px; font-weight: 700; }}
    #badge {{ background: {brand_soft}; color: {c['accent']}; border-radius: 7px; padding: 1px 7px; font-size: 11px; font-weight: 700; }}
    QPushButton#chipRemove {{ background: transparent; border: none; padding: 2px; border-radius: 8px; }}
    QPushButton#chipRemove:hover {{ background: {glass_hover}; }}
    QPushButton#ghost {{ background: transparent; border: none; padding: 5px 10px; color: {c['text_secondary']}; border-radius: 8px; }}
    QPushButton#ghost:hover {{ background: {glass_hover}; color: {c['text']}; }}
    #good {{ color: {c['good']}; }}
    #bad {{ color: {c['bad']}; }}
    #warn {{ color: {c['warn']}; font-size: 12px; }}

    QPushButton {{
        background: {glass}; border: 1px solid {edge}; border-bottom-color: {shade};
        border-radius: 11px; padding: 8px 16px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {glass_hover}; }}
    QPushButton:pressed {{ background: {field}; }}
    QPushButton:disabled {{ color: {c['text_muted']}; }}
    QPushButton#primary {{
        background: {brand}; color: white; border: 1px solid rgba(255, 255, 255, 90);
        border-bottom-color: rgba(0, 0, 0, 40); font-weight: 700; padding: 9px 22px;
    }}
    QPushButton#primary:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7f71ff, stop:1 #4893f5); }}
    QPushButton#primary:disabled {{ background: {field}; color: {c['text_muted']}; border-color: {edge}; }}
    QPushButton#seg {{
        background: transparent; border: 1px solid transparent; border-radius: 10px;
        padding: 6px 14px; font-size: 13px; color: {c['text_secondary']};
    }}
    QPushButton#seg:hover {{ color: {c['text']}; background: {glass_hover}; }}
    QPushButton#seg:checked {{ background: {glass}; border: 1px solid {edge}; border-bottom-color: {shade}; color: {c['text']}; font-weight: 700; }}

    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
        background: {field}; border: 1px solid {edge}; border-top-color: {shade}; border-radius: 10px; padding: 7px 11px;
        selection-background-color: {c['accent']}; selection-color: {c['accent_text']};
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover {{ background: {glass_hover}; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border: 1px solid {c['accent']}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {c['text_muted']}; }}
    QComboBox {{ padding-right: 30px; }}
    QComboBox::drop-down {{ border: none; width: 28px; subcontrol-origin: padding; subcontrol-position: center right; }}
    QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 4px; outline: 0;
        selection-background-color: {c['accent_soft']}; selection-color: {c['text']};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QCheckBox {{ spacing: 10px; background: transparent; }}
    QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 7px; border: 1px solid {edge}; border-top-color: {shade}; background: {field}; }}
    QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
    QCheckBox::indicator:checked {{ background: {brand}; border: 1px solid rgba(255, 255, 255, 90); image: url({check}); }}
    QCheckBox::indicator:disabled {{ background: {field}; border-color: {edge}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px; }}
    QScrollBar::handle:vertical {{ background: {shade}; border-radius: 3px; min-height: 40px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}

    QProgressBar {{ background: {field}; border: none; border-radius: 3px; max-height: 6px; }}
    QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff5f87, stop:1 #ffb36b); border-radius: 3px; }}
    QListWidget#activity {{ background: transparent; border: none; outline: 0; }}
    QListWidget#activity::item {{ padding: 8px 4px; border-bottom: 1px solid {edge}; color: {c['text_secondary']}; }}
    QTableWidget {{ background: transparent; border: none; gridline-color: {edge}; }}
    QTableWidget::item {{ border-bottom: 1px solid {edge}; padding: 4px; }}
    QHeaderView::section {{ background: transparent; border: none; border-bottom: 1px solid {edge}; padding: 6px; color: {c['text_secondary']}; font-weight: 600; }}
    QToolTip {{ background: #1c1c30; color: #f3f3fb; border: 1px solid rgba(255, 255, 255, 40); padding: 6px 9px; border-radius: 8px; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; padding: 5px; }}
    QMenu::item {{ padding: 7px 20px; border-radius: 7px; }}
    QMenu::item:selected {{ background: {c['accent_soft']}; }}
    QMenu::item:disabled {{ color: {c['text_muted']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
    #saveBar {{ background: {rgba(c['save_bar'])}; border: 1px solid {edge}; border-bottom-color: {shade}; border-radius: 18px; }}
    """


def apply(app: QApplication, theme_mode: str | None = None) -> None:
    global mode
    if theme_mode:
        mode = theme_mode
    current.clear()
    current.update(DARK if is_dark() else LIGHT)
    c = current
    pal = QPalette()
    for role, key in [
        (QPalette.Window, "bg"),
        (QPalette.Base, "surface"),
        (QPalette.AlternateBase, "surface_alt"),
        (QPalette.Button, "surface"),
        (QPalette.Text, "text"),
        (QPalette.WindowText, "text"),
        (QPalette.ButtonText, "text"),
        (QPalette.PlaceholderText, "text_muted"),
        (QPalette.Highlight, "accent"),
        (QPalette.HighlightedText, "accent_text"),
        (QPalette.ToolTipBase, "text"),
        (QPalette.ToolTipText, "surface"),
    ]:
        pal.setColor(role, QColor(c[key]))
    app.setPalette(pal)
    app.setStyleSheet(_stylesheet(c))
    for w in app.topLevelWidgets():
        w.update()


def nav_icon(kind: str, color: str, size: int = 40) -> QIcon:
    """側邊欄圖示：狀態（麥克風）、設定（滑桿）、統計（長條）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 20
    pen = QPen(QColor(color), 1.7 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    if kind == "status":
        p.drawRoundedRect(QRectF(7 * s, 2.5 * s, 6 * s, 10 * s), 3 * s, 3 * s)
        arc = QPainterPath()
        arc.moveTo(4.5 * s, 9.5 * s)
        arc.cubicTo(4.5 * s, 16 * s, 15.5 * s, 16 * s, 15.5 * s, 9.5 * s)
        p.drawPath(arc)
        p.drawLine(QPointF(10 * s, 15 * s), QPointF(10 * s, 17.5 * s))
    elif kind == "settings":
        for y, knob in ((5, 13), (10, 7), (15, 11)):
            p.drawLine(QPointF(3 * s, y * s), QPointF(17 * s, y * s))
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(knob * s, y * s), 1.8 * s, 1.8 * s)
            p.setBrush(Qt.NoBrush)
    elif kind == "home":
        path = QPainterPath()
        path.moveTo(3.5 * s, 9 * s)
        path.lineTo(10 * s, 3.5 * s)
        path.lineTo(16.5 * s, 9 * s)
        path.lineTo(16.5 * s, 16.5 * s)
        path.lineTo(3.5 * s, 16.5 * s)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(8 * s, 16.5 * s), QPointF(8 * s, 12 * s))
        p.drawLine(QPointF(8 * s, 12 * s), QPointF(12 * s, 12 * s))
        p.drawLine(QPointF(12 * s, 12 * s), QPointF(12 * s, 16.5 * s))
    elif kind == "history":
        p.drawEllipse(QPointF(10 * s, 10 * s), 7 * s, 7 * s)
        p.drawLine(QPointF(10 * s, 10 * s), QPointF(10 * s, 6 * s))
        p.drawLine(QPointF(10 * s, 10 * s), QPointF(13 * s, 11.5 * s))
    elif kind == "dictionary":
        p.drawRoundedRect(QRectF(4 * s, 3 * s, 12 * s, 14 * s), 2 * s, 2 * s)
        p.drawLine(QPointF(4 * s, 13.5 * s), QPointF(16 * s, 13.5 * s))
        p.drawLine(QPointF(7.5 * s, 6.5 * s), QPointF(12.5 * s, 6.5 * s))
    elif kind == "stats":
        for x, top in ((4.5, 10), (10, 4), (15.5, 7.5)):
            p.drawLine(QPointF(x * s, 16.5 * s), QPointF(x * s, top * s))
    p.end()
    return QIcon(pm)


BRAND = ("#6d5dfc", "#2f80ed")  # Logo 漸層：紫 → 藍


def _draw_glyph(p: QPainter, s: float, color: QColor, small: bool = False) -> None:
    """Hushtype 標誌：聲波 + 文字游標，表示「說話變成文字」。小尺寸時減少線條，避免糊在一起。"""
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    if small:
        bars, bar_w, cursor_x, cursor_w, serif = ((13, 16), (22.5, 32), (32, 20)), 7.0, 47, 5.5, 6
    else:
        bars, bar_w, cursor_x, cursor_w, serif = ((12, 12), (20, 22), (28, 30), (36, 17)), 5.2, 47.5, 3.6, 4.5
    for x, h in bars:
        p.drawRoundedRect(QRectF(x * s, (32 - h / 2) * s, bar_w * s, h * s), bar_w * s / 2, bar_w * s / 2)
    pen = QPen(color, cursor_w * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(cursor_x * s, 16 * s), QPointF(cursor_x * s, 48 * s))
    p.drawLine(QPointF((cursor_x - serif) * s, 16 * s), QPointF((cursor_x + serif) * s, 16 * s))
    p.drawLine(QPointF((cursor_x - serif) * s, 48 * s), QPointF((cursor_x + serif) * s, 48 * s))


def make_icon_pixmap(color: str | None = None, size: int = 64) -> QPixmap:
    """圓角方塊底色 + 白色標誌。color 為 None 時用品牌漸層（Logo），否則用狀態顏色（系統匣）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64
    p.setPen(Qt.NoPen)
    if color is None:
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0, QColor(BRAND[0]))
        grad.setColorAt(1, QColor(BRAND[1]))
        p.setBrush(grad)
    else:
        p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 15 * s, 15 * s)
    _draw_glyph(p, s, QColor("#ffffff"), small=size <= 24)
    p.end()
    return pm


def make_icon(color: str | None = None) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_icon_pixmap(color, size))
    return icon


def state_icon(state: str) -> QIcon:
    """系統匣圖示：待命時用品牌漸層，其他狀態用狀態顏色。"""
    return make_icon(None if state == "idle" else STATES[state][1])


def state_pixmap(state: str, size: int) -> QPixmap:
    return make_icon_pixmap(None if state == "idle" else STATES[state][1], size)


# ---- 自繪小圖示（取代 emoji，跟著主題換色）----


def glyph_pixmap(kind: str, color: str | None = None, size: int = 16, ratio: float = 2.0) -> QPixmap:
    """畫線條風格的小圖示。color 為 None 時用目前主題的次要文字色。"""
    px = int(size * ratio)
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    col = QColor(color or current["text_secondary"])
    s = px / 20
    pen = QPen(col, 1.8 * s, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def path(*pts, close=False):
        pp = QPainterPath()
        pp.moveTo(pts[0][0] * s, pts[0][1] * s)
        for x, y in pts[1:]:
            pp.lineTo(x * s, y * s)
        if close:
            pp.closeSubpath()
        p.drawPath(pp)

    if kind == "lock":
        p.drawRoundedRect(QRectF(4.5 * s, 9 * s, 11 * s, 8.5 * s), 2.2 * s, 2.2 * s)
        arc = QPainterPath()
        arc.moveTo(7 * s, 9 * s)
        arc.lineTo(7 * s, 6.5 * s)
        arc.cubicTo(7 * s, 2.5 * s, 13 * s, 2.5 * s, 13 * s, 6.5 * s)
        arc.lineTo(13 * s, 9 * s)
        p.drawPath(arc)
        p.drawLine(QPointF(10 * s, 12.3 * s), QPointF(10 * s, 14.3 * s))
    elif kind == "check":
        path((4.5, 10.5), (8.3, 14.2), (15.5, 6))
    elif kind == "cross":
        path((5.5, 5.5), (14.5, 14.5))
        path((14.5, 5.5), (5.5, 14.5))
    elif kind == "close":
        p.setPen(QPen(col, 1.6 * s, Qt.SolidLine, Qt.RoundCap))
        path((6.5, 6.5), (13.5, 13.5))
        path((13.5, 6.5), (6.5, 13.5))
    elif kind == "warn":
        path((10, 3.2), (17.6, 16.4), (2.4, 16.4), close=True)
        p.drawLine(QPointF(10 * s, 8 * s), QPointF(10 * s, 11.6 * s))
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(10 * s, 14 * s), 1.05 * s, 1.05 * s)
    elif kind == "sparkle":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        star = QPainterPath()
        star.moveTo(10 * s, 2 * s)
        star.cubicTo(10.8 * s, 7.5 * s, 12.5 * s, 9.2 * s, 18 * s, 10 * s)
        star.cubicTo(12.5 * s, 10.8 * s, 10.8 * s, 12.5 * s, 10 * s, 18 * s)
        star.cubicTo(9.2 * s, 12.5 * s, 7.5 * s, 10.8 * s, 2 * s, 10 * s)
        star.cubicTo(7.5 * s, 9.2 * s, 9.2 * s, 7.5 * s, 10 * s, 2 * s)
        p.drawPath(star)
    elif kind == "arrow":
        path((3.5, 10), (16, 10))
        path((11.5, 5.5), (16, 10), (11.5, 14.5))
    elif kind == "shield":
        sh = QPainterPath()
        sh.moveTo(10 * s, 2.5 * s)
        sh.lineTo(16.5 * s, 5 * s)
        sh.cubicTo(16.5 * s, 12 * s, 14 * s, 15.5 * s, 10 * s, 17.5 * s)
        sh.cubicTo(6 * s, 15.5 * s, 3.5 * s, 12 * s, 3.5 * s, 5 * s)
        sh.closeSubpath()
        p.drawPath(sh)
        path((7.2, 10), (9.3, 12), (13, 8))
    elif kind == "copy":
        p.drawRoundedRect(QRectF(7 * s, 7 * s, 9.5 * s, 10 * s), 2 * s, 2 * s)
        path((13, 4.5), (13, 3.8), (4.5, 3.8), (4.5, 13), (5, 13))
    elif kind == "dot":
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawEllipse(QPointF(10 * s, 10 * s), 4 * s, 4 * s)
    p.end()
    pm.setDevicePixelRatio(ratio)
    return pm


def glyph_icon(kind: str, color: str | None = None, size: int = 16) -> QIcon:
    return QIcon(glyph_pixmap(kind, color, size))
