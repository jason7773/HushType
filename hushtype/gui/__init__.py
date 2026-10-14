"""桌面應用程式：主視窗 + 系統匣圖示。"""

from __future__ import annotations

import copy
import logging
import sys
import time
import tomllib
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
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

from .. import __version__, autostart, keystore, single_instance
from ..config import DEFAULTS, load_config, save_config
from ..engine import Engine
from . import theme
from .overlay import Overlay
from .result_card import ResultCard
from .settings_page import SettingsPage
from .stats_page import StatsPage
from .dictionary_page import DictionaryPage
from .history_page import HistoryPage
from .home_page import HomePage
from ..hotkeys import key_label
from ..history import History
from ..config import data_dir
from .update import UpdateController
from .widgets import AuroraBackground, GlassFrame, Spotlight, label

log = logging.getLogger(__name__)


PAGE_HOME, PAGE_HISTORY, PAGE_DICTIONARY, PAGE_STATS, PAGE_SETTINGS = range(5)
NAV_TOP = [("首頁", "home"), ("歷史紀錄", "history"), ("字典", "dictionary"), ("統計", "stats")]
NAV_BOTTOM = [("設定", "settings")]


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

        self.setWindowTitle("Hushtype")
        self.setWindowIcon(theme.make_icon())
        self.resize(940, 700)
        self.setMinimumSize(720, 520)

        self.aurora = AuroraBackground()
        self.aurora.animated = config["ui"].get("animations", True)
        central = self.aurora
        row = QHBoxLayout(central)
        row.setContentsMargins(12, 12, 0, 12)
        row.setSpacing(0)
        side = GlassFrame(radius=22, spotlight=False)
        side.setObjectName("side")
        side.setFixedWidth(206)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(0, 0, 0, 0)
        side_lay.setSpacing(0)
        brand = QHBoxLayout()
        brand.setContentsMargins(18, 20, 16, 14)
        brand.setSpacing(11)
        logo = QLabel()
        pm = theme.make_icon_pixmap(None, 72)
        pm.setDevicePixelRatio(2)
        logo.setPixmap(pm)
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        names.addWidget(label("Hushtype", "brand"))
        names.addWidget(label("悄聲・語音輸入", "brandSub"))
        brand.addLayout(names, 1)
        side_lay.addLayout(brand)
        self.nav = self._nav_list(NAV_TOP)
        side_lay.addWidget(self.nav, 1)
        self.nav_bottom = self._nav_list(NAV_BOTTOM)
        self.nav_bottom.setFixedHeight(56)
        side_lay.addWidget(self.nav_bottom)
        self.refresh_nav_icons()
        version = label(f"版本 {__version__}", "muted")
        version.setContentsMargins(24, 0, 0, 16)
        version.setAutoFillBackground(False)
        side_lay.addWidget(version)
        row.addWidget(side)

        self.history = History(data_dir() / "history.db", config["history"]["retention"])
        self.pages = QStackedWidget()
        self._page_fade = None
        self.home_page = HomePage(self)
        self.history_page = HistoryPage(self)
        self.dictionary_page = DictionaryPage(self)
        self.stats_page = StatsPage(self)
        self.settings_page = SettingsPage(self)
        for page in (self.home_page, self.history_page, self.dictionary_page, self.stats_page, self.settings_page):
            self.pages.addWidget(page)
        row.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.spotlight = Spotlight(self)
        QApplication.instance().installEventFilter(self.spotlight)
        self.nav.currentRowChanged.connect(lambda i: i >= 0 and self._select(i))
        self.nav_bottom.currentRowChanged.connect(lambda i: i >= 0 and self._select(len(NAV_TOP) + i))
        self._select(PAGE_HOME)
        purge = QTimer(self)
        purge.setInterval(3600 * 1000)
        purge.timeout.connect(self.history.purge)
        purge.start()

        self.overlay = Overlay(lambda: self.engine.recorder.level)
        self.card = ResultCard(self.retry_failed)
        self.updates = UpdateController(self)
        self.updates.checked.connect(self._update_checked)
        self.updates.progress.connect(lambda pct: self.home_page.show_update(f"正在下載新版… {pct}%", busy=True))
        self.updates.failed.connect(self._update_failed)
        self.updates.installing.connect(self._update_installing)
        self._update_notified = False
        self._build_tray()
        self._ready = True
        self.on_event("state", {"state": self.engine.state})
        try:
            self.engine.bind()
        except Exception as e:  # 例如沒有權限監聽鍵盤
            self.add_event(f"無法註冊快捷鍵：{e}", ok=False)
        if config["ui"].get("check_updates", True):
            QTimer.singleShot(4000, self.updates.check)

    # ---- 頁面 ----

    def _nav_list(self, items) -> QListWidget:
        nav = QListWidget()
        nav.setObjectName("sidebar")
        nav.setIconSize(QSize(20, 20))
        nav.setFocusPolicy(Qt.NoFocus)
        nav.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for text, _ in items:
            nav.addItem(QListWidgetItem(text))
        return nav

    def refresh_nav_icons(self) -> None:
        current = self.pages.currentIndex() if hasattr(self, "pages") else 0
        for offset, nav, items in ((0, self.nav, NAV_TOP), (len(NAV_TOP), self.nav_bottom, NAV_BOTTOM)):
            for i, (_, kind) in enumerate(items):
                selected = offset + i == current
                color = theme.current["accent"] if selected else theme.current["text_secondary"]
                nav.item(i).setIcon(theme.nav_icon(kind, color))

    def apply_theme(self) -> None:
        theme.apply(QApplication.instance(), self.engine.config["ui"]["theme"])
        self.aurora.animated = self.engine.config["ui"].get("animations", True)
        self.aurora.set_colors(theme.STATE_AURORA.get(self.engine.state, theme.current["aurora"]))
        self.aurora.set_running(self.isActiveWindow())
        self._style_title_bar()
        self.refresh_nav_icons()
        self.home_page.set_state(self.engine.state)
        self.home_page.heatmap.update()

    def _select(self, i: int) -> None:
        """切換頁面並同步側邊欄上下兩組選單的選取狀態。"""
        top = i < len(NAV_TOP)
        for nav, row in ((self.nav, i if top else -1), (self.nav_bottom, -1 if top else i - len(NAV_TOP))):
            nav.blockSignals(True)
            nav.setCurrentRow(row)
            nav.blockSignals(False)
        changed = self.pages.currentIndex() != i
        self.pages.setCurrentIndex(i)
        page = self.pages.widget(i)
        self.refresh_nav_icons()
        if changed and self.engine.config["ui"].get("animations", True):
            self._fade_in(page)
        if hasattr(page, "refresh") and page is not self.settings_page:
            page.refresh()

    def _fade_in(self, page: QWidget) -> None:
        """換頁時新頁面淡入。"""
        if self._page_fade is not None:
            self._page_fade.stop()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start()
        self._page_fade = anim

    def _style_title_bar(self) -> None:
        """Windows 10/11：標題列跟著深色模式，Windows 11 用圓角。"""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            dark = ctypes.c_int(1 if theme.is_dark() else 0)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
            round_corners = ctypes.c_int(2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(round_corners), ctypes.sizeof(round_corners))
        except Exception as e:
            log.debug("無法設定標題列樣式：%s", e)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._style_title_bar()
        self.aurora.set_running(True)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self.aurora.set_running(False)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and hasattr(self, "aurora"):
            self.aurora.set_running(self.isActiveWindow() and self.isVisible())

    def show_page(self, i: int) -> None:
        self._select(i)
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
        menu.addAction("開啟 Hushtype", lambda: self.show_page(PAGE_HOME))
        self.pause_action = menu.addAction("暫停", lambda: self.set_paused(not self.engine.paused))
        self.copy_action = menu.addAction("複製上一段文字", self.copy_last)
        self.retry_action = menu.addAction("重試失敗的錄音", self.retry_failed)
        self.update_action = menu.addAction("更新並重新啟動", self.start_update)
        self.update_action.setVisible(False)
        menu.addAction("設定", lambda: self.show_page(PAGE_SETTINGS))
        menu.addAction("歷史紀錄", lambda: self.show_page(PAGE_HISTORY))
        menu.addAction("使用統計", lambda: self.show_page(PAGE_STATS))
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
        if kind == "activate":
            self.bring_to_front()
        elif kind == "state":
            state = data["state"]
            name, color = theme.STATES[state]
            self.tray.setIcon(theme.state_icon(state))
            self.tray.setToolTip(f"Hushtype：{name}")
            self.tray_state.setText(f"{name}・{key_label(self.engine.config['hotkey']['key'])}")
            self.pause_action.setText("恢復" if self.engine.paused else "暫停")
            self.copy_action.setEnabled(bool(self.engine.last_text))
            self.retry_action.setEnabled(self.engine.failed is not None)
            if state == "recording":
                self.card.dismiss()
            self.home_page.set_state(state)
            self.aurora.set_colors(theme.STATE_AURORA.get(state, theme.current["aurora"]))
            self._update_overlay(state)
        elif kind == "result":
            text = data.get("text")
            what = f"「{text}」" if text else f"{data['chars']} 字"
            steps = data.get("timings") or {}
            names = (("stt", "辨識"), ("cleanup", "整理"), ("paste", "貼上"))
            detail = "、".join(f"{name} {steps[k]:.1f}" for k, name in names if k in steps)
            detail = f"：{detail}" if detail else ""
            self.add_event(f"已輸入 {what}（說 {data['seconds']:.0f} 秒，等 {data['latency']:.1f} 秒{detail}）")
            if data.get("output"):
                self.history.add(data["output"], app=data.get("app", ""), seconds=data["seconds"])
            current = self.pages.currentWidget()
            if current in (self.home_page, self.history_page, self.stats_page):
                current.refresh()
        elif kind == "unplaced":
            self.card.show_text(data["text"])
        elif kind == "corrections":
            self.engine.learn(data["words"])
        elif kind == "learned":
            words = "、".join(data["words"])
            self.add_event(f"學到新詞：{words}")
            try:
                save_config(self.engine.config, self.config_path)
            except OSError as e:
                log.warning("無法儲存學到的詞：%s", e)
            self.dictionary_page.refresh()
            self.tray.showMessage("Hushtype 學到新詞", f"{words}\n之後會照這個寫法輸出，可在「字典」頁刪除。", QSystemTrayIcon.Information, 4000)
        elif kind == "skipped":
            self.add_event(f"略過：{data['reason']}")
        elif kind == "error":
            self.add_event(data["message"], ok=False)
            if data.get("retry"):
                self.overlay.dismiss()
                self.card.show_failure(data["message"].split("：", 1)[-1][:120])
            elif self.engine.config["ui"]["overlay"]:
                self.overlay.show_error(data["message"].split("：")[0][:8])
            if not self.isVisible() and time.monotonic() - self._last_error_notice > 15:
                self._last_error_notice = time.monotonic()
                self.tray.showMessage("Hushtype", data["message"], QSystemTrayIcon.Warning, 5000)

    def _update_overlay(self, state: str) -> None:
        if not self.engine.config["ui"]["overlay"]:
            self.overlay.dismiss()
        elif state == "recording":
            self.overlay.show_recording()
        elif state == "processing":
            self.overlay.show_processing()
        elif self.overlay.mode in ("recording", "processing"):
            self.overlay.dismiss()

    def add_event(self, text: str, ok: bool = True) -> None:
        self.history_page.add_event(text, ok)

    def set_history_retention(self, retention: str) -> None:
        self.history.set_retention(retention)
        cfg = copy.deepcopy(self.engine.config)
        cfg["history"]["retention"] = self.history.retention
        self.save_settings(cfg, {}, None)

    def copy_last(self) -> None:
        if self.engine.last_text:
            QApplication.clipboard().setText(self.engine.last_text)

    def retry_failed(self) -> None:
        if not self.engine.retry():
            self.add_event("沒有可以重試的錄音", ok=False)

    # ---- 更新 ----

    def check_updates(self) -> None:
        self.updates.check()

    def _update_checked(self, release, message: str) -> None:
        self.settings_page.set_update_note(message)
        if release is None:
            return
        self.home_page.show_update(f"有新版 {release.version} 可以更新（目前 {__version__}）。")
        self.update_action.setText(f"更新到 {release.version} 並重新啟動")
        self.update_action.setVisible(True)
        if not self.isVisible() and not self._update_notified:
            self._update_notified = True
            self.tray.showMessage("Hushtype 有新版", f"版本 {release.version}，打開 Hushtype 按「更新並重新啟動」。", QSystemTrayIcon.Information, 5000)

    def start_update(self) -> None:
        if self.engine.recorder.recording or self.engine.busy:
            self.home_page.show_update("正在錄音或處理中，完成後再按一次更新。")
            return
        self.home_page.show_update("正在下載新版…", busy=True)
        self.updates.install()

    def _update_failed(self, message: str) -> None:
        self.home_page.show_update(f"更新失敗：{message}")
        self.settings_page.set_update_note(f"更新失敗：{message}")

    def _update_installing(self) -> None:
        # 安裝程式會在背景安裝，裝完自動重新開啟
        self.quit()

    def set_paused(self, paused: bool) -> None:
        self.engine.set_paused(paused)

    # ---- 設定 ----

    def save_settings(self, config: dict, keys: dict[str, str], autostart_on: bool | None) -> str | None:
        """儲存並套用設定；失敗時回傳錯誤訊息。autostart_on 為 None 時不動開機啟動。"""
        for name, value in keys.items():
            try:
                keystore.set_secret(name, value)
            except Exception as e:
                return f"無法把金鑰存進 Windows 認證管理員：{e}"
        try:
            save_config(config, self.config_path)
        except OSError as e:
            return f"無法寫入設定檔：{e}"
        if autostart_on is not None:
            try:
                autostart.set_enabled(autostart_on)
            except OSError as e:
                return f"無法設定開機自動啟動：{e}"
        try:
            self.engine.apply_config(config)
        except Exception as e:
            return f"套用設定失敗：{e}"
        self.apply_theme()
        self.home_page.refresh()
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
            self.tray.showMessage("Hushtype 仍在執行", "視窗已縮到系統匣，快捷鍵照常可用。", QSystemTrayIcon.Information, 4000)

    def quit(self) -> None:
        self._quitting = True
        QApplication.instance().removeEventFilter(self.spotlight)
        try:
            self.engine.unbind()
        except Exception:
            pass
        self.tray.hide()
        self.overlay.hide()
        self.card.hide()
        QApplication.quit()


def run(config_path: Path, *, minimized: bool = False) -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Hushtype")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Microsoft JhengHei UI", "Microsoft JhengHei", "Noto Sans CJK TC"])
    font.setPointSizeF(10)
    app.setFont(font)

    instance = single_instance.acquire()
    if instance is None:
        return 0  # 已經在執行，已經叫它出來了

    try:
        config = load_config(config_path)
    except (tomllib.TOMLDecodeError, OSError) as e:
        QMessageBox.warning(
            None,
            "Hushtype",
            f"設定檔有錯誤，已改用預設值啟動。\n\n{config_path}\n{e}\n\n在「設定」頁按儲存會覆寫這個檔案。",
        )
        config = copy.deepcopy(DEFAULTS)

    theme.apply(app, config["ui"]["theme"])
    window = MainWindow(config_path, config)

    instance.listen(lambda: window.bridge.event.emit("activate", {}))
    QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: window.apply_theme())

    if minimized:
        window.tray.showMessage("Hushtype 已啟動", f"按住「{key_label(config['hotkey']['key'])}」說話。", QSystemTrayIcon.Information, 3000)
    else:
        window.show()
    return app.exec()
