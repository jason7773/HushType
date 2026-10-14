"""「狀態」頁：目前狀態、系統檢查、今天的用量、最近活動。"""

from __future__ import annotations

import threading
from datetime import datetime

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import autostart
from ..stats import load_summary
from . import theme
from .widgets import Card, StatTile, label

HINTS = {
    "idle": "按住「{key}」說話，放開後文字會出現在游標位置",
    "recording": "放開「{key}」就會送出",
    "processing": "正在辨識與整理文字…",
    "paused": "快捷鍵暫時停用，按「恢復」繼續",
    "setup": "{error}",
}

KEY_NAMES = {"right ctrl": "右 Ctrl", "right alt": "右 Alt", "right shift": "右 Shift", "caps lock": "Caps Lock"}


def key_label(key: str) -> str:
    return KEY_NAMES.get(key, key.upper() if len(key) <= 3 else key.title())


class _CheckSignals(QObject):
    done = Signal(list)


class StatusPage(QScrollArea):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setWidgetResizable(True)
        root = QWidget()
        root.setObjectName("page")
        self.setWidget(root)
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(16)
        lay.addWidget(label("狀態", "h1"))

        # 目前狀態
        hero = Card()
        row = QHBoxLayout()
        row.setSpacing(14)
        self.state_icon = QLabel()
        self.state_icon.setFixedSize(48, 48)
        row.addWidget(self.state_icon, 0, Qt.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        self.state_title = label("", "stateTitle")
        self.state_hint = label("", "secondary", wrap=True)
        texts.addWidget(self.state_title)
        texts.addWidget(self.state_hint)
        row.addLayout(texts, 1)
        self.pause_btn = QPushButton("暫停")
        self.pause_btn.clicked.connect(lambda: window.set_paused(not window.engine.paused))
        row.addWidget(self.pause_btn, 0, Qt.AlignTop)
        hero.body.addLayout(row)
        self.level = QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.hide()
        hero.body.addWidget(self.level)
        lay.addWidget(hero)

        # 今天
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.t_count, self.t_time, self.t_chars = StatTile("今天使用"), StatTile("今天說話"), StatTile("今天輸出")
        for t in (self.t_count, self.t_time, self.t_chars):
            tiles.addWidget(t)
        lay.addLayout(tiles)

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

        # 最近活動
        act = Card("最近活動")
        self.activity = QListWidget()
        self.activity.setObjectName("activity")
        self.activity.setMinimumHeight(160)
        self.activity.setFocusPolicy(Qt.NoFocus)
        act.body.addWidget(self.activity)
        self.empty_note = label("還沒有活動。按住快捷鍵說話試試看。", "muted")
        act.body.addWidget(self.empty_note)
        lay.addWidget(act)
        lay.addStretch(1)

        self._signals = _CheckSignals()
        self._signals.done.connect(self._checks_done)
        self._level_timer = QTimer(self)
        self._level_timer.setInterval(50)
        self._level_timer.timeout.connect(lambda: self.level.setValue(int(window.engine.recorder.level * 100)))

    # ---- 更新 ----

    def set_state(self, state: str) -> None:
        engine = self.window.engine
        name, color = theme.STATES[state]
        pm = theme.make_icon_pixmap(color, 96)
        pm.setDevicePixelRatio(2)
        self.state_icon.setPixmap(pm)
        self.state_title.setText(name)
        self.state_hint.setText(
            HINTS[state].format(key=key_label(engine.config["hotkey"]["key"]), error=engine.setup_error)
        )
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
        s = load_summary(cfg)["today"]
        self.t_count.set(f"{s['count']:,}", "次", f"失敗 {s['errors']} 次" if s["errors"] else "")
        self.t_time.set(f"{s['minutes']:.1f}", "分鐘", "")
        self.t_chars.set(f"{s['chars']:,}", "字", f"估計省下 {s['saved_minutes']:.0f} 分鐘")

        rows = [
            ("快捷鍵", f"{key_label(cfg['hotkey']['key'])}（{'按住說話' if cfg['hotkey']['mode'] == 'hold' else '按一下開始／結束'}）", None),
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
        where = "Groq" if section["provider"] == "groq" else section.get("base_url", "自訂服務")
        return f"{section['model']}（{where}）"

    def _fill_grid(self, rows) -> None:
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, (name, text, ok) in enumerate(rows):
            self.grid.addWidget(label(name, "secondary"), i, 0)
            value = label(text, wrap=True)
            if ok is not None:
                value.setObjectName("good" if ok else "bad")
                value.setText(("✓ " if ok else "✗ ") + text)
            self.grid.addWidget(value, i, 1)

    def add_activity(self, text: str, ok: bool = True) -> None:
        mark = "" if ok else "⚠ "
        self.activity.insertItem(0, QListWidgetItem(f"{datetime.now():%H:%M:%S}　{mark}{text}"))
        while self.activity.count() > 50:
            self.activity.takeItem(self.activity.count() - 1)
        self.empty_note.hide()

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
