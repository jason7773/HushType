"""配色、樣式表與圖示。跟隨 Windows 的淺色 / 深色模式。"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#f5f5f4",
    "surface": "#ffffff",
    "surface_alt": "#efeeeb",
    "border": "#e6e5e1",
    "text": "#111111",
    "text_secondary": "#52514e",
    "text_muted": "#7a7974",
    "grid": "#ecebe7",
    "accent": "#2a78d6",
    "accent_hover": "#1d5fae",
    "accent_soft": "#e6f0fb",
    "accent_text": "#ffffff",
    "good": "#127a1f",
    "bad": "#c93434",
    "warn": "#9a6200",
}

DARK = {
    "bg": "#0f0f10",
    "surface": "#18181a",
    "surface_alt": "#242427",
    "border": "#2c2c30",
    "text": "#f0efec",
    "text_secondary": "#c3c2b7",
    "text_muted": "#8f8e86",
    "grid": "#26262a",
    "accent": "#3987e5",
    "accent_hover": "#6aa6ee",
    "accent_soft": "#1b2a3d",
    "accent_text": "#ffffff",
    "good": "#4cc26a",
    "bad": "#ef7474",
    "warn": "#e8b04a",
}

# 引擎狀態 → (顯示名稱, 顏色)
STATES = {
    "idle": ("待命中", "#2a78d6"),
    "recording": ("錄音中", "#e34948"),
    "processing": ("處理中", "#eda100"),
    "paused": ("已暫停", "#8f8e86"),
    "setup": ("需要設定", "#8f8e86"),
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
    d = Path(tempfile.gettempdir()) / "dictate-ui"
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
    return f"""
    QWidget {{ color: {c['text']}; font-size: 14px; }}
    QMainWindow, #page {{ background: {c['bg']}; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

    #side {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
    #sidebar {{ background: transparent; border: none; outline: 0; padding: 8px 10px; }}
    #sidebar::item {{ padding: 9px 12px; border-radius: 8px; margin: 2px 0; color: {c['text_secondary']}; }}
    #sidebar::item:selected {{ background: {c['accent_soft']}; color: {c['accent']}; font-weight: 600; }}
    #sidebar::item:hover:!selected {{ background: {c['surface_alt']}; }}
    #brand {{ font-size: 17px; font-weight: 700; }}

    #card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
    #h1 {{ font-size: 24px; font-weight: 700; }}
    #h2 {{ font-size: 15px; font-weight: 600; }}
    #muted {{ color: {c['text_muted']}; font-size: 12px; }}
    #secondary {{ color: {c['text_secondary']}; }}
    #big {{ font-size: 26px; font-weight: 600; }}
    #stateTitle {{ font-size: 24px; font-weight: 700; }}
    #good {{ color: {c['good']}; }}
    #bad {{ color: {c['bad']}; }}
    #warn {{ color: {c['warn']}; font-size: 12px; }}

    QPushButton {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
        padding: 7px 14px; font-weight: 500;
    }}
    QPushButton:hover {{ background: {c['surface_alt']}; }}
    QPushButton:pressed {{ background: {c['border']}; }}
    QPushButton:disabled {{ color: {c['text_muted']}; }}
    QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; padding: 8px 22px; }}
    QPushButton#primary:hover {{ background: {c['accent_hover']}; }}
    QPushButton#seg {{ border-radius: 0; padding: 4px 12px; font-size: 13px; margin-left: -1px; }}
    QPushButton#seg:checked {{ background: {c['text']}; color: {c['surface']}; border-color: {c['text']}; }}

    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
        background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 10px;
        selection-background-color: {c['accent']}; selection-color: {c['accent_text']};
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover {{ border-color: {c['text_muted']}; }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {c['text_muted']}; }}
    QComboBox {{ padding-right: 30px; }}
    QComboBox::drop-down {{ border: none; width: 28px; subcontrol-origin: padding; subcontrol-position: center right; }}
    QComboBox::down-arrow {{ image: url({chevron}); width: 14px; height: 14px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; outline: 0;
        selection-background-color: {c['accent_soft']}; selection-color: {c['text']};
    }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QCheckBox {{ spacing: 10px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid {c['text_muted']}; background: {c['bg']}; }}
    QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; image: url({check}); }}
    QCheckBox::indicator:disabled {{ background: {c['surface_alt']}; border-color: {c['border']}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 40px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}

    QProgressBar {{ background: {c['surface_alt']}; border: none; border-radius: 3px; max-height: 6px; }}
    QProgressBar::chunk {{ background: {STATES['recording'][1]}; border-radius: 3px; }}
    QListWidget#activity {{ background: transparent; border: none; outline: 0; }}
    QListWidget#activity::item {{ padding: 7px 2px; border-bottom: 1px solid {c['border']}; color: {c['text_secondary']}; }}
    QTableWidget {{ background: transparent; border: none; gridline-color: {c['border']}; }}
    QTableWidget::item {{ border-bottom: 1px solid {c['border']}; padding: 4px; }}
    QHeaderView::section {{ background: transparent; border: none; border-bottom: 1px solid {c['border']}; padding: 6px; color: {c['text_secondary']}; font-weight: 500; }}
    QToolTip {{ background: {c['text']}; color: {c['surface']}; border: none; padding: 6px 8px; border-radius: 6px; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 4px; }}
    QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
    QMenu::item:selected {{ background: {c['surface_alt']}; }}
    QMenu::item:disabled {{ color: {c['text_muted']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
    #saveBar {{ background: {c['surface']}; border-top: 1px solid {c['border']}; }}
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
        (QPalette.Base, "bg"),
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
    elif kind == "stats":
        for x, top in ((4.5, 10), (10, 4), (15.5, 7.5)):
            p.drawLine(QPointF(x * s, 16.5 * s), QPointF(x * s, top * s))
    p.end()
    return QIcon(pm)


def make_icon_pixmap(color: str, size: int = 64) -> QPixmap:
    """圓角方塊底色 + 白色麥克風。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    s = size / 64
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 14 * s, 14 * s)
    p.setBrush(QColor("#ffffff"))
    p.drawRoundedRect(QRectF(24 * s, 12 * s, 16 * s, 26 * s), 8 * s, 8 * s)
    pen = QPen(QColor("#ffffff"), 4 * s, Qt.SolidLine, Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    arc = QPainterPath()
    arc.moveTo(QPointF(17 * s, 30 * s))
    arc.cubicTo(QPointF(17 * s, 48 * s), QPointF(47 * s, 48 * s), QPointF(47 * s, 30 * s))
    p.drawPath(arc)
    p.drawLine(QPointF(32 * s, 44 * s), QPointF(32 * s, 52 * s))
    p.end()
    return pm


def make_icon(color: str) -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_icon_pixmap(color, size))
    return icon
