"""「設定」頁：所有設定都在這裡改，按「儲存」後立即生效。"""

from __future__ import annotations

import copy
import threading

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, autostart, hotkeys, keystore
from ..config import DEFAULT_CLEANUP_PROMPT
from . import theme
from .widgets import Card, HeroTitle, label

HOTKEYS = [
    "right ctrl", "right alt", "right shift", "caps lock", "f8", "f9", "f10", "f12", "scroll lock", "pause",
    "mouse:x1", "mouse:x2", "mouse:middle",
]
# 每個服務的建議模型，第一個是預設；欄位也可以自己輸入其他型號
STT_MODELS = {
    "groq": ["whisper-large-v3-turbo", "whisper-large-v3"],
    "openai": ["gpt-4o-mini-transcribe", "gpt-4o-transcribe", "gpt-transcribe", "whisper-1"],
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.8-flash"],
    "openai_compatible": [],
}
CLEANUP_MODELS = {
    "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"],
    "openai": ["gpt-5.4-mini", "gpt-6-luna", "gpt-5-mini"],
    "gemini": ["gemini-3.5-flash-lite", "gemini-3.8-flash"],
    "openai_compatible": [],
}
# 選服務時顯示的資料去向說明
PROVIDER_NOTES = {
    "groq": "Groq：API 資料不會拿去訓練模型。",
    "openai": "OpenAI：API 資料預設不會拿去訓練模型，但會保留最多 30 天供濫用審查。",
    "gemini": "注意：Gemini 免費方案的內容可能被 Google 拿去改善產品。機密內容請先在 Google AI Studio 開啟付費方案。",
    "openai_compatible": "資料會送到你填的網址。填本機網址（127.0.0.1）時完全不出你的電腦。",
}
LANGUAGES = [("中英自動偵測（建議）", ""), ("只說中文", "zh"), ("只說英文", "en")]
EFFORTS = [("低（較快）", "low"), ("中", "medium"), ("高", "high"), ("不設定", None)]
PROVIDERS = [
    ("Groq", "groq"),
    ("OpenAI", "openai"),
    ("Google Gemini", "gemini"),
    ("其他 OpenAI 相容服務（含本機）", "openai_compatible"),
]
NAMED_KEYS = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}


def _combo(items, current) -> QComboBox:
    box = QComboBox()
    for text, data in items:
        box.addItem(text, data)
    i = box.findData(current)
    box.setCurrentIndex(i if i >= 0 else 0)
    box.setMinimumWidth(280)
    return box


def _editable_combo(values: list[str], current: str) -> QComboBox:
    box = QComboBox()
    box.setEditable(True)
    box.addItems(values)
    box.setCurrentText(current)
    box.setMinimumWidth(280)
    return box


class _WheelGuard(QObject):
    """滑鼠停在下拉選單或數字欄上滾動時不改值，改成捲動整頁。"""

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Wheel:
            event.ignore()  # 交給上層的捲動區域
            return True
        return False


def _form() -> QFormLayout:
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(10)
    form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
    return form


def key_env(section: str, provider: str) -> str:
    """金鑰在認證管理員裡的名稱。同一家服務的語音辨識和文字整理共用同一把。"""
    return NAMED_KEYS.get(provider) or f"DICTATE_{section.upper()}_API_KEY"


class ServiceForm:
    """一組「服務／網址／金鑰」欄位，語音辨識和文字整理各一組。"""

    def __init__(self, form: QFormLayout, section_name: str, section: dict, models: dict[str, list[str]]):
        self.section_name = section_name
        self.models = models
        self.provider = _combo(PROVIDERS, section["provider"])
        self.base_url = QLineEdit(section.get("base_url", ""))
        self.base_url.setPlaceholderText("例如 http://127.0.0.1:8080/v1")
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("貼上 API 金鑰")
        self.show_key = QPushButton("顯示")
        self.show_key.setCheckable(True)
        self.show_key.toggled.connect(self._toggle_key)
        key_row = QHBoxLayout()
        key_row.addWidget(self.key, 1)
        key_row.addWidget(self.show_key)
        self._key_widget = QWidget()
        self._key_widget.setLayout(key_row)
        key_row.setContentsMargins(0, 0, 0, 0)
        self.note = label("", "muted", wrap=True)
        form.addRow("服務", self.provider)
        form.addRow("", self.note)
        form.addRow("網址", self.base_url)
        form.addRow("API 金鑰", self._key_widget)
        self.model = _editable_combo(models.get(section["provider"], []), section["model"])
        form.addRow("模型", self.model)
        self._form = form
        self.provider.currentIndexChanged.connect(self._provider_changed)
        self.legacy_key = section.get("api_key", "")
        self.load_key()
        self._sync()

    def _toggle_key(self, on: bool) -> None:
        self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)
        self.show_key.setText("隱藏" if on else "顯示")

    def _sync(self) -> None:
        provider = self.provider.currentData()
        self._form.setRowVisible(self.base_url, provider == "openai_compatible")
        self.note.setText(PROVIDER_NOTES.get(provider, ""))
        self.note.setObjectName("warn" if provider == "gemini" else "muted")
        self.note.style().unpolish(self.note)
        self.note.style().polish(self.note)
        self.load_key()

    def _provider_changed(self) -> None:
        """換服務時，模型清單換成該服務的建議型號。"""
        choices = self.models.get(self.provider.currentData(), [])
        current = self.model.currentText()
        self.model.clear()
        self.model.addItems(choices)
        self.model.setCurrentText(current if current in choices or not choices else choices[0])
        self._sync()

    @property
    def env(self) -> str:
        return key_env(self.section_name, self.provider.currentData())

    def load_key(self) -> None:
        self.key.setText(keystore.get_secret(self.env) or self.legacy_key)
        self.key.setModified(False)

    def write(self, section: dict) -> None:
        for k in ("provider", "base_url", "api_key", "api_key_env"):
            section.pop(k, None)
        section["provider"] = self.provider.currentData()
        section["model"] = self.model.currentText().strip()
        if section["provider"] == "openai_compatible":
            section["base_url"] = self.base_url.text().strip()
            section["api_key_env"] = self.env


class _HotkeySignal(QObject):
    captured = Signal(str)
    failed = Signal(str)


class SettingsPage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("page")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        outer.addWidget(self.scroll, 1)

        bar = QWidget()
        bar.setObjectName("saveBar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(20, 10, 12, 10)
        self.note = label("", "muted")
        bar_lay.addWidget(self.note, 1)
        self.revert_btn = QPushButton("取消變更")
        self.revert_btn.clicked.connect(self.load)
        self.save_btn = QPushButton("儲存")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.save)
        bar_lay.addWidget(self.revert_btn)
        bar_lay.addWidget(self.save_btn)
        holder = QHBoxLayout()
        holder.setContentsMargins(28, 8, 38, 0)
        holder.addWidget(bar)
        outer.addLayout(holder)

        self._wheel_guard = _WheelGuard(self)
        self._hotkey = _HotkeySignal()
        self._hotkey.captured.connect(self._hotkey_captured)
        self._hotkey.failed.connect(lambda msg: self.note.setText(f"無法錄製按鍵：{msg}"))
        self.load()

    # ---- 建立表單 ----

    def load(self) -> None:
        cfg = self.window.engine.config
        root = QWidget()
        root.setObjectName("page")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(28, 26, 28, 32)
        lay.setSpacing(16)
        lay.addWidget(HeroTitle("設定", 32))

        # 一般
        card, form = self._card(lay, "一般")
        self.autostart = QCheckBox("開機時自動啟動（只顯示系統匣圖示）")
        self.autostart.setChecked(autostart.is_enabled())
        self.autostart.setEnabled(autostart.supported())
        form.addRow(self.autostart)
        self.beep = QCheckBox("開始與結束錄音時發出提示音")
        self.beep.setChecked(cfg["feedback"]["beep"])
        form.addRow(self.beep)
        self.overlay = QCheckBox("錄音與轉譯時，在螢幕下方顯示小視窗")
        self.overlay.setChecked(cfg["ui"]["overlay"])
        form.addRow(self.overlay)
        self.animations = QCheckBox("流動的極光背景與換頁動畫（關掉可以省一點電）")
        self.animations.setChecked(cfg["ui"].get("animations", True))
        form.addRow(self.animations)
        self.theme = _combo(theme.THEMES, cfg["ui"]["theme"])
        form.addRow("外觀", self.theme)
        self.check_updates = QCheckBox("啟動時自動檢查新版")
        self.check_updates.setChecked(cfg["ui"].get("check_updates", True))
        form.addRow(self.check_updates)
        urow = QHBoxLayout()
        self.update_note = label(f"目前版本 {__version__}", "muted")
        urow.addWidget(self.update_note, 1)
        check_btn = QPushButton("立即檢查更新")
        check_btn.clicked.connect(self._check_now)
        urow.addWidget(check_btn)
        form.addRow("版本", urow)

        # 快捷鍵與麥克風
        card, form = self._card(lay, "快捷鍵與麥克風")
        self.hotkey = QComboBox()
        self.hotkey.setMinimumWidth(280)
        for key in HOTKEYS:
            self.hotkey.addItem(hotkeys.key_label(key), key)
        self.set_hotkey(cfg["hotkey"]["key"])
        self.capture_btn = QPushButton("錄製按鍵")
        self.capture_btn.setToolTip("按下後，再按一下鍵盤按鍵或滑鼠中鍵／側鍵；按 Esc 取消")
        self.capture_btn.clicked.connect(self._capture_hotkey)
        row = QHBoxLayout()
        row.addWidget(self.hotkey, 1)
        row.addWidget(self.capture_btn)
        form.addRow("快捷鍵", row)
        self.mode = _combo([("按住說話，放開送出", "hold"), ("按一下開始，再按一下結束", "toggle")], cfg["hotkey"]["mode"])
        form.addRow("操作方式", self.mode)
        self.suppress = QCheckBox("攔下快捷鍵，不讓其他程式收到（例如 F12 不會再打開開發者工具）")
        self.suppress.setChecked(cfg["hotkey"].get("suppress", True))
        form.addRow(self.suppress)
        self.mic = QComboBox()
        self.mic.setMinimumWidth(280)
        self.mic.addItem("系統預設", "")
        try:
            from ..audio import input_devices

            for name in input_devices():
                self.mic.addItem(name, name)
        except Exception:
            pass
        i = self.mic.findData(cfg["audio"]["device"])
        if i < 0 and cfg["audio"]["device"]:
            self.mic.addItem(f"{cfg['audio']['device']}（目前找不到）", cfg["audio"]["device"])
            i = self.mic.count() - 1
        self.mic.setCurrentIndex(max(i, 0))
        form.addRow("麥克風", self.mic)

        # 語音辨識
        card, form = self._card(lay, "語音辨識")
        self.stt_service = ServiceForm(form, "stt", cfg["stt"], STT_MODELS)
        self.language = _combo(LANGUAGES, cfg["stt"].get("language") or "")
        form.addRow("語言", self.language)

        # 文字整理
        card, form = self._card(lay, "文字整理")
        self.cleanup_on = QCheckBox("用 AI 去除贅字、加標點、自動分段與條列")
        self.cleanup_on.setChecked(cfg["cleanup"]["enabled"])
        form.addRow(self.cleanup_on)
        self.cleanup_service = ServiceForm(form, "cleanup", cfg["cleanup"], CLEANUP_MODELS)
        self.effort = _combo(EFFORTS, cfg["cleanup"].get("extra", {}).get("reasoning_effort"))
        form.addRow("推理強度", self.effort)
        self.prompt = QPlainTextEdit(cfg["cleanup"]["system_prompt"])
        self.prompt.setMinimumHeight(180)
        form.addRow("整理規則", self.prompt)
        reset = QPushButton("還原預設規則")
        reset.clicked.connect(lambda: self.prompt.setPlainText(DEFAULT_CLEANUP_PROMPT))
        form.addRow("", reset)
        card.body.addWidget(label("推理強度只對 gpt-oss 等推理型模型有效；其他模型請選「不設定」。", "muted", wrap=True))

        # 輸出
        card, form = self._card(lay, "輸出")
        self.method = _combo([("貼上（快，建議）", "paste"), ("模擬逐字打字", "type")], cfg["output"]["method"])
        form.addRow("輸入方式", self.method)
        self.restore_clip = QCheckBox("貼上後還原原本的剪貼簿內容")
        self.restore_clip.setChecked(cfg["output"]["restore_clipboard"])
        form.addRow(self.restore_clip)
        self.traditional = QCheckBox("轉成繁體中文（台灣用語）")
        self.traditional.setChecked(cfg["output"]["convert_to_traditional"])
        form.addRow(self.traditional)
        self.show_unplaced = QCheckBox("找不到輸入框時，在螢幕下方顯示文字和「複製」按鈕")
        self.show_unplaced.setChecked(cfg["output"].get("show_unplaced", True))
        form.addRow(self.show_unplaced)

        # 隱私與統計
        card, form = self._card(lay, "隱私與統計")
        self.log_text = QCheckBox("在「歷史紀錄 → 事件」顯示辨識出的文字")
        self.log_text.setChecked(cfg["privacy"]["log_text"])
        form.addRow(self.log_text)
        self.stats_on = QCheckBox("記錄使用統計（只有時間與字數，不含內容）")
        self.stats_on.setChecked(cfg["stats"]["enabled"])
        form.addRow(self.stats_on)
        self.cpm = QSpinBox()
        self.cpm.setRange(5, 300)
        self.cpm.setSuffix(" 字／分鐘")
        self.cpm.setValue(int(cfg["stats"]["typing_cpm"]))
        form.addRow("你的打字速度", self.cpm)
        card.body.addWidget(label("打字速度用來估算「省下的時間」。", "muted"))
        card.body.addWidget(
            label("API 金鑰存在 Windows 認證管理員，不會寫進設定檔。", "muted", wrap=True)
        )

        for w in root.findChildren(QComboBox) + root.findChildren(QAbstractSpinBox):
            w.setFocusPolicy(Qt.StrongFocus)
            w.installEventFilter(self._wheel_guard)

        lay.addStretch(1)
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(root)
        self.note.setText("")

    def _check_now(self) -> None:
        self.update_note.setText("檢查中…")
        self.window.check_updates()

    def set_update_note(self, text: str) -> None:
        self.update_note.setText(text)

    def _card(self, lay, title: str):
        card = Card(title)
        form = _form()
        card.body.addLayout(form)
        lay.addWidget(card)
        return card, form

    # ---- 錄製快捷鍵 ----

    def set_hotkey(self, key: str) -> None:
        i = self.hotkey.findData(key)
        if i < 0:
            self.hotkey.addItem(hotkeys.key_label(key), key)
            i = self.hotkey.count() - 1
        self.hotkey.setCurrentIndex(i)

    def _capture_hotkey(self) -> None:
        engine = self.window.engine
        self.capture_btn.setText("請按鍵盤或滑鼠按鍵…")
        self.capture_btn.setEnabled(False)
        was_paused = engine.paused
        engine.set_paused(True)
        engine.unbind()  # 暫時放開目前的快捷鍵，錄製時才收得到

        def wait():
            name = ""
            try:
                name = hotkeys.capture()
            except Exception as e:
                self._hotkey.failed.emit(str(e))
            finally:
                try:
                    engine.bind()
                except Exception as e:
                    self._hotkey.failed.emit(str(e))
                engine.set_paused(was_paused)
                self._hotkey.captured.emit(name)

        threading.Thread(target=wait, daemon=True).start()

    def _hotkey_captured(self, name: str) -> None:
        if name:
            self.set_hotkey(name)
            self.note.setText(f"快捷鍵改成「{hotkeys.key_label(name)}」，按「儲存」後生效")
        self.capture_btn.setText("錄製按鍵")
        self.capture_btn.setEnabled(True)

    # ---- 儲存 ----

    def collect(self) -> dict:
        cfg = copy.deepcopy(self.window.engine.config)
        cfg["feedback"]["beep"] = self.beep.isChecked()
        cfg["ui"]["overlay"] = self.overlay.isChecked()
        cfg["ui"]["animations"] = self.animations.isChecked()
        cfg["ui"]["theme"] = self.theme.currentData()
        cfg["ui"]["check_updates"] = self.check_updates.isChecked()
        cfg["hotkey"]["key"] = self.hotkey.currentData() or "right ctrl"
        cfg["hotkey"]["mode"] = self.mode.currentData()
        cfg["hotkey"]["suppress"] = self.suppress.isChecked()
        cfg["audio"]["device"] = self.mic.currentData()

        self.stt_service.write(cfg["stt"])
        cfg["stt"]["language"] = self.language.currentData()

        cfg["cleanup"]["enabled"] = self.cleanup_on.isChecked()
        self.cleanup_service.write(cfg["cleanup"])
        extra = dict(cfg["cleanup"].get("extra", {}))
        extra.pop("reasoning_effort", None)
        if self.effort.currentData():
            extra["reasoning_effort"] = self.effort.currentData()
        cfg["cleanup"]["extra"] = extra
        cfg["cleanup"]["system_prompt"] = self.prompt.toPlainText().strip() + "\n"

        cfg["output"]["method"] = self.method.currentData()
        cfg["output"]["restore_clipboard"] = self.restore_clip.isChecked()
        cfg["output"]["convert_to_traditional"] = self.traditional.isChecked()
        cfg["output"]["show_unplaced"] = self.show_unplaced.isChecked()


        cfg["privacy"]["log_text"] = self.log_text.isChecked()
        cfg["stats"]["enabled"] = self.stats_on.isChecked()
        cfg["stats"]["typing_cpm"] = self.cpm.value()
        return cfg

    def keys_to_store(self) -> dict[str, str]:
        """要寫入認證管理員的金鑰。兩組欄位共用同一個名稱時，以有修改過的為準。"""
        forms = [self.stt_service]
        if self.cleanup_on.isChecked():
            forms.append(self.cleanup_service)
        out: dict[str, str] = {}
        for f in sorted(forms, key=lambda f: f.key.isModified()):
            if f.key.isModified() or f.env not in out:
                out[f.env] = f.key.text().strip()
        return out

    def save(self) -> None:
        cfg = self.collect()
        error = self.window.save_settings(cfg, self.keys_to_store(), self.autostart.isChecked())
        if error:
            self.note.setText(error)
        else:
            self.note.setText("已儲存，設定已生效")
            for f in (self.stt_service, self.cleanup_service):
                f.legacy_key = ""
                f.key.setModified(False)


def parse_replacements(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        for sep in ("→", "->", "=", "＝"):
            if sep in line:
                wrong, right = line.split(sep, 1)
                if wrong.strip():
                    out[wrong.strip()] = right.strip()
                break
    return out
