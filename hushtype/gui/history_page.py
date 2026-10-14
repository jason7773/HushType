"""「歷史紀錄」頁：每次辨識出的文字（可複製、刪除）與事件紀錄。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..history import RETENTIONS, Entry, disk_supported
from ..stats import app_label
from .settings_page import _combo
from .widgets import Card, label

MAX_ROWS = 300  # 一次顯示的筆數上限，避免頁面太長


def _day_title(d: date) -> str:
    today = date.today()
    if d == today:
        return "今天"
    if d == today - timedelta(days=1):
        return "昨天"
    return f"{d:%Y/%m/%d}"


class EntryRow(QFrame):
    def __init__(self, page: "HistoryPage", entry: Entry):
        super().__init__()
        self.setObjectName("entry")
        self.entry = entry
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 12, 10, 12)
        row.setSpacing(14)
        meta = QVBoxLayout()
        meta.setSpacing(2)
        meta.addWidget(label(f"{entry.created_at:%H:%M}", "secondary"))
        if entry.app:
            meta.addWidget(label(app_label(entry.app), "muted"))
        meta.addStretch(1)
        row.addLayout(meta)
        text = label(entry.text, "entryText", wrap=True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(text, 1)
        copy = QPushButton("複製")
        copy.setObjectName("ghost")
        copy.clicked.connect(lambda: page.copy(entry, copy))
        delete = QPushButton("刪除")
        delete.setObjectName("ghost")
        delete.clicked.connect(lambda: page.delete(entry))
        buttons = QVBoxLayout()
        buttons.setSpacing(4)
        buttons.addWidget(copy)
        buttons.addWidget(delete)
        buttons.addStretch(1)
        row.addLayout(buttons)


class HistoryPage(QScrollArea):
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

        head = QHBoxLayout()
        head.addWidget(label("歷史紀錄", "hero"), 1)
        self.copy_last_btn = QPushButton("複製上一次結果")
        self.copy_last_btn.clicked.connect(self.copy_last)
        head.addWidget(self.copy_last_btn, 0, Qt.AlignVCenter)
        lay.addLayout(head)

        # 保留設定與隱私說明
        keep = Card()
        row = QHBoxLayout()
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(label("保留歷史紀錄", "h2"))
        texts.addWidget(label("選擇在這台電腦上保留辨識文字多久。", "secondary"))
        row.addLayout(texts, 1)
        self.retention = _combo(RETENTIONS, window.engine.config["history"]["retention"])
        self.retention.setMinimumWidth(180)
        self.retention.setEnabled(disk_supported())
        self.retention.currentIndexChanged.connect(self._retention_changed)
        row.addWidget(self.retention, 0, Qt.AlignVCenter)
        keep.body.addLayout(row)
        line = QFrame()
        line.setObjectName("divider")
        line.setFixedHeight(1)
        keep.body.addWidget(line)
        keep.body.addWidget(label("🔒 你的口述內容是私密的", "h2"))
        self.privacy = label("", "secondary", wrap=True)
        keep.body.addWidget(self.privacy)
        lay.addWidget(keep)

        # 分頁：口述／事件
        tabs = QHBoxLayout()
        tabs.setSpacing(0)
        self.tab_group = QButtonGroup(self)
        for i, name in enumerate(("口述", "事件")):
            b = QPushButton(name)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(i == 0)
            self.tab_group.addButton(b, i)
            tabs.addWidget(b)
        tabs.addStretch(1)
        self.clear_btn = QPushButton("清除全部")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.clicked.connect(self.clear)
        tabs.addWidget(self.clear_btn)
        lay.addLayout(tabs)

        self.stack = QStackedWidget()
        self.entries_box = QWidget()
        self.entries_lay = QVBoxLayout(self.entries_box)
        self.entries_lay.setContentsMargins(0, 0, 0, 0)
        self.entries_lay.setSpacing(8)
        self.stack.addWidget(self.entries_box)
        events = Card()
        self.events = QListWidget()
        self.events.setObjectName("activity")
        self.events.setFocusPolicy(Qt.NoFocus)
        self.events.setMinimumHeight(240)
        events.body.addWidget(self.events)
        self.stack.addWidget(events)
        self.tab_group.idClicked.connect(self.stack.setCurrentIndex)
        lay.addWidget(self.stack)
        lay.addStretch(1)
        self._update_privacy()

    # ---- 顯示 ----

    def _update_privacy(self) -> None:
        r = self.window.history.retention
        if r == "session":
            text = "辨識出的文字只放在記憶體，關閉程式就清除，不會寫進硬碟。"
        else:
            text = (
                "辨識出的文字只存在這台電腦，而且用你的 Windows 帳號加密（DPAPI），"
                "其他帳號或拿走硬碟的人都讀不到。改回「只保留到關閉程式」會立刻刪除硬碟上的紀錄。"
            )
        if not disk_supported():
            text += "（目前的系統不支援加密保存，只能保留到關閉程式。）"
        self.privacy.setText(text)

    def refresh(self) -> None:
        while self.entries_lay.count():
            w = self.entries_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        entries = self.window.history.entries[:MAX_ROWS]
        self.copy_last_btn.setEnabled(bool(self.window.engine.last_text or entries))
        if not entries:
            self.entries_lay.addWidget(label("還沒有紀錄。按住快捷鍵說話，辨識出的文字會出現在這裡。", "muted"))
            return
        current = None
        for e in entries:
            d = e.created_at.date()
            if d != current:
                title = label(_day_title(d), "secondary")
                title.setContentsMargins(2, 8 if current else 0, 0, 0)
                self.entries_lay.addWidget(title)
                current = d
            self.entries_lay.addWidget(EntryRow(self, e))
        if len(self.window.history.entries) > MAX_ROWS:
            self.entries_lay.addWidget(label(f"只顯示最近 {MAX_ROWS} 筆。", "muted"))

    def add_event(self, text: str, ok: bool = True) -> None:
        mark = "" if ok else "⚠ "
        self.events.insertItem(0, QListWidgetItem(f"{datetime.now():%H:%M:%S}　{mark}{text}"))
        while self.events.count() > 200:
            self.events.takeItem(self.events.count() - 1)

    # ---- 動作 ----

    def _flash(self, button: QPushButton, text: str) -> None:
        old = button.text()
        button.setText(text)
        QTimer.singleShot(1500, lambda: button.setText(old) if button else None)

    def copy(self, entry: Entry, button: QPushButton | None = None) -> None:
        QApplication.clipboard().setText(entry.text)
        if button:
            self._flash(button, "已複製 ✓")

    def copy_last(self) -> None:
        text = self.window.engine.last_text or (self.window.history.entries[0].text if self.window.history.entries else "")
        if text:
            QApplication.clipboard().setText(text)
            self._flash(self.copy_last_btn, "已複製 ✓")

    def delete(self, entry: Entry) -> None:
        self.window.history.delete(entry)
        self.refresh()

    def clear(self) -> None:
        if self.stack.currentIndex() == 1:
            self.events.clear()
            return
        if not self.window.history.entries:
            return
        ask = QMessageBox.question(self, "清除歷史紀錄", "要刪除全部的口述紀錄嗎？這個動作無法復原。")
        if ask == QMessageBox.Yes:
            self.window.history.clear()
            self.refresh()

    def _retention_changed(self) -> None:
        value = self.retention.currentData()
        self.window.set_history_retention(value)
        self._update_privacy()
        self.refresh()
