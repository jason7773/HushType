"""配色、樣式表與圖示。跟隨 Windows 的淺色 / 深色模式。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

LIGHT = {
    "bg": "#f4f4f2",
    "surface": "#fcfcfb",
    "surface_alt": "#efeeeb",
    "border": "#e3e2de",
    "text": "#0b0b0b",
    "text_secondary": "#52514e",
    "text_muted": "#7a7974",
    "grid": "#ebeae6",
    "accent": "#2a78d6",
    "accent_hover": "#1d5fae",
    "accent_text": "#ffffff",
    "good": "#008300",
    "bad": "#d03b3b",
}

DARK = {
    "bg": "#111110",
    "surface": "#1a1a19",
    "surface_alt": "#242422",
    "border": "#2e2e2c",
    "text": "#f0efec",
    "text_secondary": "#c3c2b7",
    "text_muted": "#8f8e86",
    "grid": "#2a2a28",
    "accent": "#3987e5",
    "accent_hover": "#6aa6ee",
    "accent_text": "#ffffff",
    "good": "#3fae5a",
    "bad": "#e66767",
}

# 引擎狀態 → (顯示名稱, 顏色)
STATES = {
    "idle": ("待命中", "#2a78d6"),
    "recording": ("錄音中", "#e34948"),
    "processing": ("處理中", "#eda100"),
    "paused": ("已暫停", "#8f8e86"),
    "setup": ("需要設定", "#8f8e86"),
}

current = dict(LIGHT)


def is_dark() -> bool:
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def _stylesheet(c: dict) -> str:
    return f"""
    QWidget {{ color: {c['text']}; font-size: 14px; }}
    QMainWindow, #page {{ background: {c['bg']}; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    #side {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}
    #sidebar {{ background: transparent; border: none; outline: 0; padding: 12px 8px; }}
    #sidebar::item {{ padding: 10px 14px; border-radius: 8px; margin: 2px 0; color: {c['text_secondary']}; }}
    #sidebar::item:selected {{ background: {c['surface_alt']}; color: {c['text']}; font-weight: 600; }}
    #sidebar::item:hover:!selected {{ background: {c['surface_alt']}; }}
    #brand {{ font-size: 18px; font-weight: 700; padding: 18px 22px 6px 22px; }}
    #card {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 12px; }}
    #h1 {{ font-size: 22px; font-weight: 700; }}
    #h2 {{ font-size: 15px; font-weight: 600; }}
    #muted {{ color: {c['text_muted']}; font-size: 12px; }}
    #secondary {{ color: {c['text_secondary']}; }}
    #big {{ font-size: 26px; font-weight: 600; }}
    #stateTitle {{ font-size: 24px; font-weight: 700; }}
    #good {{ color: {c['good']}; }}
    #bad {{ color: {c['bad']}; }}
    QPushButton {{
        background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px;
        padding: 7px 14px;
    }}
    QPushButton:hover {{ background: {c['surface_alt']}; }}
    QPushButton:disabled {{ color: {c['text_muted']}; }}
    QPushButton#primary {{ background: {c['accent']}; color: {c['accent_text']}; border: none; font-weight: 600; }}
    QPushButton#primary:hover {{ background: {c['accent_hover']}; }}
    QPushButton#seg {{ border-radius: 0; padding: 4px 12px; font-size: 13px; }}
    QPushButton#seg:checked {{ background: {c['text']}; color: {c['surface']}; border-color: {c['text']}; }}
    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
        background: {c['bg']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 6px 8px;
        selection-background-color: {c['accent']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
    QLineEdit:disabled, QComboBox:disabled {{ color: {c['text_muted']}; }}
    QComboBox QAbstractItemView {{ background: {c['surface']}; border: 1px solid {c['border']}; selection-background-color: {c['surface_alt']}; selection-color: {c['text']}; }}
    QCheckBox {{ spacing: 8px; }}
    QProgressBar {{ background: {c['surface_alt']}; border: none; border-radius: 3px; max-height: 6px; }}
    QProgressBar::chunk {{ background: {STATES['recording'][1]}; border-radius: 3px; }}
    QListWidget#activity {{ background: transparent; border: none; }}
    QListWidget#activity::item {{ padding: 6px 2px; border-bottom: 1px solid {c['border']}; }}
    QTableWidget {{ background: transparent; border: none; gridline-color: {c['border']}; }}
    QHeaderView::section {{ background: transparent; border: none; border-bottom: 1px solid {c['border']}; padding: 6px; color: {c['text_secondary']}; font-weight: 500; }}
    QToolTip {{ background: {c['text']}; color: {c['surface']}; border: none; padding: 6px 8px; border-radius: 6px; }}
    #saveBar {{ background: {c['surface']}; border-top: 1px solid {c['border']}; }}
    """


def apply(app: QApplication) -> None:
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
