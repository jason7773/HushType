"""「首頁」：目前狀態、快捷鍵、使用洞察、活躍日曆、系統檢查。"""

from __future__ import annotations

import threading
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import autostart
from ..hotkeys import key_label
from ..stats import load_summary
from . import theme
from .widgets import Card, Heatmap, StatTile, label

HINTS = {
    "idle": "{how}「{key}」說話，文字會出現在游標位置",
    "recording": "{stop}就會送出",
    "processing": "正在辨識與整理文字…",
    "paused": "快捷鍵暫時停用，按「恢復」繼續",
    "setup": "{error}",
}


def _duration(minutes: float) -> tuple[str, str]:
    """把分鐘數變成「12 小時 51 分鐘」這種寫法，回傳 (數字 HTML, 說明)。"""
    total = int(round(minutes))
    h, m = divmod(total, 60)
    small = '<span style="font-size:14px;font-weight:400">&nbsp;{}&nbsp;</span>'
    if h:
        return f"{h}{small.format('小時')}{m}{small.format('分鐘')}", ""
    return f"{m}{small.format('分鐘')}", ""


def _compact(n: int) -> tuple[str, str]:
    if n >= 10000:
        return f"{n / 1000:.1f}K", "字"
    return f"{n:,}", "字"


class _CheckSignals(QObject):
    done = Signal(list)


class HomePage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        root = QWidget()
        root.setObjectName("page")
        self.setWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.setSpacing(16)

        # 標題 + 快捷鍵
        head = QHBoxLayout()
        head.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(label("開口，就寫好了", "hero"))
        titles.addWidget(label("錄音和文字只送到你自己選的服務，其他地方一律不送。", "secondary"))
        head.addLayout(titles, 1)
        key_card = Card()
        key_card.setObjectName("keyCard")
        key_card.body.setSpacing(6)
        key_card.body.addWidget(label("快捷鍵", "muted"))
        self.key_chip = label("", "keyChip")
        key_card.body.addWidget(self.key_chip, 0, Qt.AlignLeft)
        self.key_mode = label("", "muted")
        key_card.body.addWidget(self.key_mode)
        head.addWidget(key_card, 0, Qt.AlignTop)
        lay.addLayout(head)

        # 有新版時才出現
        self.update_card = Card()
        self.update_card.setObjectName("updateCard")
        urow = QHBoxLayout()
        self.update_text = label("", wrap=True)
        urow.addWidget(self.update_text, 1)
        self.update_btn = QPushButton("更新並重新啟動")
        self.update_btn.setObjectName("primary")
        self.update_btn.clicked.connect(lambda: window.start_update())
        urow.addWidget(self.update_btn, 0, Qt.AlignVCenter)
        self.update_card.body.addLayout(urow)
        self.update_card.hide()
        lay.addWidget(self.update_card)

        # 目前狀態
        state = Card()
        row = QHBoxLayout()
        row.setSpacing(14)
        self.state_icon = QLabel()
        self.state_icon.setFixedSize(44, 44)
        row.addWidget(self.state_icon, 0, Qt.AlignVCenter)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.state_title = label("", "stateTitle")
        self.state_hint = label("", "secondary", wrap=True)
        texts.addWidget(self.state_title)
        texts.addWidget(self.state_hint)
        row.addLayout(texts, 1)
        self.pause_btn = QPushButton("暫停")
        self.pause_btn.clicked.connect(lambda: window.set_paused(not window.engine.paused))
        row.addWidget(self.pause_btn, 0, Qt.AlignVCenter)
        state.body.addLayout(row)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.hide()
        state.body.addWidget(self.level)
        lay.addWidget(state)

        # 洞察
        lay.addWidget(label("洞察", "h1small"))
        grid = QGridLayout()
        grid.setSpacing(12)
        self.tiles = {
            key: StatTile(title)
            for key, title in [
                ("chars", "口述字數"),
                ("saved", "節省時間"),
                ("speed", "平均口述速度"),
                ("time", "總口述時間"),
            ]
        }
        for i, tile in enumerate(self.tiles.values()):
            tile.value.setObjectName("bigger")
            grid.addWidget(tile, i // 2, i % 2)
        lay.addLayout(grid)

        # 活躍日曆
        cal = Card()
        nums = QHBoxLayout()
        nums.setSpacing(28)
        self.days = {}
        for key, title in [("active", "活躍天數"), ("streak", "目前連續天數"), ("longest", "最長連續天數")]:
            box = QVBoxLayout()
            box.setSpacing(0)
            value = label("0", "bigger")
            box.addWidget(value)
            box.addWidget(label(title, "muted"))
            nums.addLayout(box)
            self.days[key] = value
        nums.addStretch(1)
        cal.body.addLayout(nums)
        self.heatmap = Heatmap()
        cal.body.addWidget(self.heatmap)
        legend = QHBoxLayout()
        legend.addStretch(1)
        legend.addWidget(label("較少 ▢ ▣ ■ 較多", "muted"))
        cal.body.addLayout(legend)
        lay.addWidget(cal)

        # 系統檢查
        checks = Card("系統檢查")
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(8)
        self.grid.setColumnStretch(1, 1)
        checks.body.addLayout(self.grid)
        btns = QHBoxLayout()
        self.test_btn = QPushButton("測試連線")
        self.test_btn.clicked.connect(self.run_checks)
        btns.addWidget(self.test_btn)
        self.test_note = label("", "muted")
        btns.addWidget(self.test_note, 1)
        checks.body.addLayout(btns)
        lay.addWidget(checks)
        self._service_rows: dict[str, tuple[str, bool | None]] = {}
        lay.addStretch(1)

        self._signals = _CheckSignals()
        self._signals.done.connect(self._checks_done)
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(50)
        self._level_timer.timeout.connect(lambda: self.level.setValue(int(window.engine.recorder.level * 100)))

    # ---- 更新 ----

    def set_state(self, state: str) -> None:
        engine = self.window.engine
        hotkey = engine.config["hotkey"]
        key = key_label(hotkey["key"])
        hold = hotkey["mode"] == "hold"
        name, color = theme.STATES[state]
        pm = theme.state_pixmap(state, 88)
        pm.setDevicePixelRatio(2)
        self.state_icon.setPixmap(pm)
        self.state_title.setText(name)
        self.state_hint.setText(
            HINTS[state].format(
                how="按住" if hold else "按一下",
                stop=f"放開「{key}」" if hold else f"再按一下「{key}」",
                key=key,
                error=engine.setup_error,
            )
        )
        self.key_chip.setText(key)
        self.key_mode.setText("按住說話" if hold else "按一下開始／結束")
        self.pause_btn.setText("恢復" if engine.paused else "暫停")
        self.pause_btn.setEnabled(state != "setup")
        recording = state == "recording"
        self.level.setVisible(recording)
        if recording:
            self._level_timer.start()
        else:
            self._level_timer.stop()

    def refresh(self) -> None:
        engine = self.window.engine
        cfg = engine.config
        s = load_summary(cfg)
        total = s["total"]
        self.tiles["chars"].set(*_compact(total["chars"]), f"今天 {s['today']['chars']:,} 字")
        self.tiles["saved"].set(_duration(total["saved_minutes"])[0], "", f"以每分鐘打 {cfg['stats']['typing_cpm']} 字估算")
        self.tiles["speed"].set(f"{s['chars_per_minute']:,}", "字／分鐘", "打字約 40 字／分鐘")
        self.tiles["time"].set(_duration(total["minutes"])[0], "", f"共 {total['count']:,} 次")
        self.days["active"].setText(f"{s['active_days']}<span style='font-size:14px;font-weight:400'>&nbsp;天</span>")
        self.days["streak"].setText(f"{s['streak_days']}<span style='font-size:14px;font-weight:400'>&nbsp;天</span>")
        self.days["longest"].setText(f"{s['longest_streak']}<span style='font-size:14px;font-weight:400'>&nbsp;天</span>")
        self.heatmap.set_counts(s["heatmap"])

        hotkey = cfg["hotkey"]
        rows = [
            ("快捷鍵", f"{key_label(hotkey['key'])}（{'按住說話' if hotkey['mode'] == 'hold' else '按一下開始／結束'}）", None),
            ("麥克風", cfg["audio"]["device"] or self._default_mic(), None),
            ("語音辨識", self._service_text(cfg["stt"]), None),
            ("文字整理", self._service_text(cfg["cleanup"]) if cfg["cleanup"]["enabled"] else "已關閉", None),
            ("API 金鑰", "已設定" if engine.pipeline else "未設定或有誤", bool(engine.pipeline)),
            ("開機自動啟動", "開啟" if autostart.is_enabled() else "關閉", None),
            ("使用統計", "記錄中（不含內容）" if cfg["stats"]["enabled"] else "關閉", None),
        ]
        for name, (text, ok) in self._service_rows.items():
            rows.append((f"{name}連線", text, ok))
        self._fill_grid(rows)

    @staticmethod
    def _default_mic() -> str:
        try:
            from ..audio import default_input_device

            return f"系統預設（{default_input_device() or '找不到麥克風'}）"
        except Exception:
            return "系統預設"

    @staticmethod
    def _service_text(section: dict) -> str:
        names = {"groq": "Groq", "openai": "OpenAI", "gemini": "Gemini"}
        where = names.get(section["provider"]) or section.get("base_url", "自訂服務")
        return f"{section['model']}（{where}）"

    def _fill_grid(self, rows) -> None:
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        for i, (name, text, ok) in enumerate(rows):
            self.grid.addWidget(label(name, "secondary"), i, 0)
            value = label(text, wrap=True)
            if ok is not None:
                value.setObjectName("good" if ok else "bad")
                value.setText(("✓ " if ok else "✗ ") + text)
            self.grid.addWidget(value, i, 1)

    def show_update(self, text: str | None, busy: bool = False) -> None:
        self.update_card.setVisible(text is not None)
        if text is not None:
            self.update_text.setText(text)
            self.update_btn.setEnabled(not busy)

    # ---- 測試連線 ----

    def run_checks(self) -> None:
        self.test_btn.setEnabled(False)
        self.test_note.setText("測試中…")
        engine = self.window.engine
        threading.Thread(target=lambda: self._signals.done.emit(engine.check_services()), daemon=True).start()

    def _checks_done(self, results: list) -> None:
        self.test_btn.setEnabled(True)
        self.test_note.setText(f"上次測試：{datetime.now():%H:%M}")
        self._service_rows = {name: (text, ok) for name, ok, text in results}
        self.refresh()
