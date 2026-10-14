"""桌面應用程式：主視窗 + 系統匣圖示。"""

from __future__ import annotations

import copy
import logging
import sys
import time
import tomllib
from pathlib import Path

from PySide6.QtCore import QObject, QSize, Qt, Signal
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart, keystore
from ..config import DEFAULTS, load_config, save_config
from ..engine import Engine
from . import theme
from .overlay import Overlay
from .settings_page import SettingsPage
from .stats_page import StatsPage
from .status_page import StatusPage, key_label
from .widgets import label

log = logging.getLogger(__name__)

INSTANCE_NAME = "dictate-single-instance"


class Bridge(QObject):
    """把引擎（背景執行緒）的事件轉到介面執行緒。"""

    event = Signal(str, dict)


class MainWindow(QMainWindow):
    def __init__(self, config_path: Path, config: dict):
        super().__init__()
        self.config_path = config_path
        self._ready = False  # 介面建好前忽略引擎事件
        self.bridge = Bridge()
        self.bridge.event.connect(self.on_event)
        self.engine = Engine(config, self.bridge.event.emit)
        self._quitting = False
        self._hide_notice_shown = False
        self._last_error_notice = 0.0

        self.setWindowTitle("dictate")
        self.setWindowIcon(theme.make_icon(theme.STATES["idle"][1]))
        self.resize(940, 700)
        self.setMinimumSize(720, 520)

        central = QWidget()
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        side = QWidget()
        side.setObjectName("side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side.setFixedWidth(190)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(0)
        brand = QHBoxLayout()
        brand.setContentsMargins(20, 20, 20, 10)
        brand.setSpacing(10)
        logo = QLabel()
        pm = theme.make_icon_pixmap(theme.STATES["idle"][1], 56)
        pm.setDevicePixelRatio(2)
        logo.setPixmap(pm)
        brand.addWidget(logo)
        brand.addWidget(label("dictate", "brand"), 1)
        side_lay.addLayout(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("sidebar")
        self.nav.setIconSize(QSize(20, 20))
        for text in ("狀態", "設定", "統計"):
            self.nav.addItem(QListWidgetItem(text))
        self.nav.setFocusPolicy(Qt.NoFocus)
        self.refresh_nav_icons()
        side_lay.addWidget(self.nav, 1)
        version = label(f"版本 {__version__}", "muted")
        version.setContentsMargins(22, 0, 0, 14)
        version.setAutoFillBackground(False)
        side_lay.addWidget(version)
        row.addWidget(side)

        self.pages = QStackedWidget()
        self.status_page = StatusPage(self)
        self.settings_page = SettingsPage(self)
        self.stats_page = StatsPage(self)
        for page in (self.status_page, self.settings_page, self.stats_page):
            self.pages.addWidget(page)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self._show_page)
        self.nav.setCurrentRow(0)

        self.overlay = Overlay(lambda: self.engine.recorder.level)
        self._build_tray()
        self._ready = True
        self.on_event("state", {"state": self.engine.state})
        try:
            self.engine.bind()
        except Exception as e:  # 例如沒有權限監聽鍵盤
            self.status_page.add_activity(f"無法註冊快捷鍵：{e}", ok=False)

    # ---- 頁面 ----

    def refresh_nav_icons(self) -> None:
        for i, kind in enumerate(("status", "settings", "stats")):
            self.nav.item(i).setIcon(theme.nav_icon(kind, theme.current["text_secondary"]))

    def apply_theme(self) -> None:
        theme.apply(QApplication.instance(), self.engine.config["ui"]["theme"])
        self.refresh_nav_icons()
        self.status_page.set_state(self.engine.state)

    def _show_page(self, i: int) -> None:
        self.pages.setCurrentIndex(i)
        if i == 0:
            self.status_page.refresh()
        elif i == 2:
            self.stats_page.refresh()

    def show_page(self, i: int) -> None:
        self.nav.setCurrentRow(i)
        self.bring_to_front()

    def bring_to_front(self) -> None:
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()

    # ---- 系統匣 ----

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        menu = QMenu()
        self.tray_state = QAction("", menu)
        self.tray_state.setEnabled(False)
        menu.addAction(self.tray_state)
        menu.addSeparator()
        menu.addAction("開啟 dictate", lambda: self.show_page(0))
        self.pause_action = menu.addAction("暫停", lambda: self.set_paused(not self.engine.paused))
        menu.addAction("設定", lambda: self.show_page(1))
        menu.addAction("使用統計", lambda: self.show_page(2))
        menu.addSeparator()
        menu.addAction("結束", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.bring_to_front()

    # ---- 引擎事件 ----

    def on_event(self, kind: str, data: dict) -> None:
        if not self._ready:
            return
        if kind == "state":
            state = data["state"]
            name, color = theme.STATES[state]
            self.tray.setIcon(theme.make_icon(color))
            self.tray.setToolTip(f"dictate：{name}")
            self.tray_state.setText(f"{name}・{key_label(self.engine.config['hotkey']['key'])}")
            self.pause_action.setText("恢復" if self.engine.paused else "暫停")
            self.status_page.set_state(state)
            self._update_overlay(state)
        elif kind == "result":
            text = data.get("text")
            what = f"「{text}」" if text else f"{data['chars']} 字"
            self.status_page.add_activity(f"已輸入 {what}（說 {data['seconds']:.0f} 秒，等 {data['latency']:.1f} 秒）")
            if self.pages.currentIndex() == 0:
                self.status_page.refresh()
            elif self.pages.currentIndex() == 2:
                self.stats_page.refresh()
        elif kind == "skipped":
            self.status_page.add_activity(f"略過：{data['reason']}")
        elif kind == "error":
            self.status_page.add_activity(data["message"], ok=False)
            if self.engine.config["ui"]["overlay"]:
                self.overlay.show_error(data["message"].split("：")[0][:8])
            if not self.isVisible() and time.monotonic() - self._last_error_notice > 15:
                self._last_error_notice = time.monotonic()
                self.tray.showMessage("dictate", data["message"], QSystemTrayIcon.Warning, 5000)

    def _update_overlay(self, state: str) -> None:
        if not self.engine.config["ui"]["overlay"]:
            self.overlay.dismiss()
        elif state == "recording":
            self.overlay.show_recording()
        elif state == "processing":
            self.overlay.show_processing()
        elif self.overlay.mode in ("recording", "processing"):
            self.overlay.dismiss()

    def set_paused(self, paused: bool) -> None:
        self.engine.set_paused(paused)

    # ---- 設定 ----

    def save_settings(self, config: dict, keys: dict[str, str], autostart_on: bool) -> str | None:
        """儲存並套用設定；失敗時回傳錯誤訊息。"""
        for name, value in keys.items():
            try:
                keystore.set_secret(name, value)
            except Exception as e:
                return f"無法把金鑰存進 Windows 認證管理員：{e}"
        try:
            save_config(config, self.config_path)
        except OSError as e:
            return f"無法寫入設定檔：{e}"
        try:
            autostart.set_enabled(autostart_on)
        except OSError as e:
            return f"無法設定開機自動啟動：{e}"
        try:
            self.engine.apply_config(config)
        except Exception as e:
            return f"套用設定失敗：{e}"
        self.apply_theme()
        self.status_page.refresh()
        return self.engine.setup_error or None

    # ---- 關閉 ----

    def closeEvent(self, event) -> None:
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        if not self._hide_notice_shown:
            self._hide_notice_shown = True
            self.tray.showMessage("dictate 仍在執行", "視窗已縮到系統匣，快捷鍵照常可用。", QSystemTrayIcon.Information, 4000)

    def quit(self) -> None:
        self._quitting = True
        try:
            self.engine.unbind()
        except Exception:
            pass
        self.tray.hide()
        self.overlay.hide()
        QApplication.quit()


def _notify_running_instance() -> bool:
    """已經有 dictate 在執行時，請它把視窗叫出來，並回傳 True。"""
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_NAME)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False


def run(config_path: Path, *, minimized: bool = False) -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("dictate")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(["Segoe UI", "Microsoft JhengHei UI", "Microsoft JhengHei", "Noto Sans CJK TC"])
    font.setPointSizeF(10)
    app.setFont(font)

    if _notify_running_instance():
        return 0
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_NAME)
    server.listen(INSTANCE_NAME)

    try:
        config = load_config(config_path)
    except (tomllib.TOMLDecodeError, OSError) as e:
        QMessageBox.warning(
            None,
            "dictate",
            f"設定檔有錯誤，已改用預設值啟動。\n\n{config_path}\n{e}\n\n在「設定」頁按儲存會覆寫這個檔案。",
        )
        config = copy.deepcopy(DEFAULTS)

    theme.apply(app, config["ui"]["theme"])
    window = MainWindow(config_path, config)

    def on_connection():
        conn = server.nextPendingConnection()
        conn.readyRead.connect(lambda: (conn.readAll(), window.bring_to_front()))

    server.newConnection.connect(on_connection)
    QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: window.apply_theme())

    if minimized:
        window.tray.showMessage("dictate 已啟動", f"按住「{key_label(config['hotkey']['key'])}」說話。", QSystemTrayIcon.Information, 3000)
    else:
        window.show()
    return app.exec()
