"""語音輸入引擎：監聽快捷鍵、錄音、處理、貼上。介面與主控台模式共用。

引擎透過 listener(kind, data) 回報事件，不直接印出或顯示任何東西：
- "state"    {"state": idle / recording / processing / paused / setup}
- "result"   {"chars", "seconds", "latency", "text"（只有開啟 log_text 才有）}
- "skipped"  {"reason"}
- "error"    {"message"}
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime
from typing import Callable

from . import hotkeys
from .audio import Recorder, Recording
from .output import insert_text
from .pipeline import Pipeline, build_pipeline
from .providers import ProviderError
from .stats import UsageLog, usage_db_path

log = logging.getLogger(__name__)

Listener = Callable[[str, dict], None]


def _beep(freq: int) -> None:
    try:
        import winsound
    except ImportError:
        return
    threading.Thread(target=winsound.Beep, args=(freq, 80), daemon=True).start()


class Engine:
    def __init__(self, config: dict, listener: Listener | None = None):
        self.listener = listener or (lambda kind, data: None)
        self.jobs: queue.Queue[tuple[Recording, datetime, float]] = queue.Queue()
        self.paused = False
        self.busy = 0  # 排隊或處理中的錄音數
        self._hooks: list = []
        self._mouse: hotkeys.MouseHook | None = None
        self._bound = False
        self._started_at = datetime.now()
        self.apply_config(config, rebind=False)
        threading.Thread(target=self._worker, daemon=True).start()

    # ---- 設定 ----

    def apply_config(self, config: dict, *, rebind: bool = True) -> None:
        self.config = config
        audio = config["audio"]
        self.recorder = Recorder(audio["sample_rate"], audio["max_seconds"], audio["device"])
        self.usage = UsageLog(usage_db_path(config)) if config["stats"]["enabled"] else None
        self.pipeline: Pipeline | None = None
        self.setup_error = ""
        try:
            self.pipeline = build_pipeline(config)
        except (ProviderError, ValueError) as e:
            self.setup_error = str(e)
        if rebind and self._bound:
            self.unbind()
            self.bind()
        self._emit_state()

    def check_services(self) -> list[tuple[str, bool, str]]:
        """逐一測試服務連線，回傳 [(名稱, 是否成功, 說明)]。會花幾秒，請在背景執行。"""
        if self.pipeline is None:
            return [("服務設定", False, self.setup_error)]
        results = []
        targets = [("語音辨識", self.pipeline.stt)]
        if self.pipeline.cleaner:
            targets.append(("文字整理", self.pipeline.cleaner))
        for name, provider in targets:
            t0 = time.monotonic()
            try:
                provider.check()
                results.append((name, True, f"正常（{(time.monotonic() - t0) * 1000:.0f} ms）"))
            except ProviderError as e:
                results.append((name, False, str(e)))
        return results

    # ---- 狀態 ----

    @property
    def state(self) -> str:
        if self.paused:
            return "paused"
        if self.pipeline is None:
            return "setup"
        if self.recorder.recording:
            return "recording"
        if self.busy:
            return "processing"
        return "idle"

    def _emit(self, kind: str, **data) -> None:
        try:
            self.listener(kind, data)
        except Exception:
            log.exception("事件處理失敗")

    def _emit_state(self) -> None:
        self._emit("state", state=self.state)

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if paused and self.recorder.recording:
            self.recorder.stop()
        self._emit_state()

    def _feedback(self, freq: int) -> None:
        if self.config["feedback"]["beep"]:
            _beep(freq)

    # ---- 快捷鍵 ----

    def bind(self) -> None:
        key = self.config["hotkey"]["key"]
        button = hotkeys.mouse_button(key)
        if button:
            hook = hotkeys.MouseHook(self._on_mouse, suppress={button})
            hook.start()
            self._mouse, self._mouse_button = hook, button
        else:
            import keyboard

            self._hooks = [
                keyboard.on_press_key(key, self.on_press),
                keyboard.on_release_key(key, self.on_release),
            ]
        self._bound = True

    def unbind(self) -> None:
        if self._mouse:
            self._mouse.stop()
            self._mouse = None
        if self._hooks:
            import keyboard

            for hook in self._hooks:
                try:
                    keyboard.unhook(hook)
                except (KeyError, ValueError):
                    pass
            self._hooks = []
        self._bound = False

    def _on_mouse(self, button: str, down: bool) -> None:
        if button == self._mouse_button:
            self.on_press() if down else self.on_release()

    # 以下在快捷鍵 hook 的執行緒中執行，必須快速返回
    def on_press(self, _event=None) -> None:
        if self.paused:
            return
        if self.config["hotkey"]["mode"] == "toggle":
            self._stop() if self.recorder.recording else self._start()
        elif not self.recorder.recording:  # 按住時會重複觸發，只在第一次開始
            self._start()

    def on_release(self, _event=None) -> None:
        if self.config["hotkey"]["mode"] == "hold" and self.recorder.recording:
            self._stop()

    def _start(self) -> None:
        if self.pipeline is None:
            self._emit("error", message=self.setup_error)
            self._feedback(300)
            return
        try:
            self.recorder.start()
        except Exception as e:  # 沒有麥克風、權限被拒等
            self._emit("error", message=f"無法開始錄音：{e}")
            self._feedback(300)
            return
        self._started_at = datetime.now()
        self._feedback(880)
        self._emit_state()

    def _stop(self) -> None:
        rec = self.recorder.stop()
        self._feedback(660)
        audio = self.config["audio"]
        if rec.seconds < audio["min_seconds"]:
            self._emit("skipped", reason="太短")
        elif rec.rms < audio["silence_rms"]:
            self._emit("skipped", reason="沒有偵測到聲音")
        else:
            self.busy += 1
            self.jobs.put((rec, self._started_at, time.monotonic()))
        self._emit_state()

    # ---- 背景處理 ----

    def _worker(self) -> None:
        while True:
            rec, started_at, t0 = self.jobs.get()  # t0：放開按鍵的時間
            try:
                self._process(rec, started_at, t0)
            except Exception as e:
                log.exception("處理失敗")
                self._emit("error", message=f"處理失敗：{e}")
            finally:
                self.busy -= 1
                self._emit_state()

    def _process(self, rec: Recording, started_at: datetime, t0: float) -> None:
        pipeline = self.pipeline
        if pipeline is None:
            return
        try:
            text = pipeline.run(rec.wav)
        except ProviderError as e:
            self._feedback(300)
            self._record(started_at, rec, "", t0, "error")
            self._emit("error", message=f"辨識失敗：{e}")
            return
        if not text:
            self._record(started_at, rec, "", t0, "empty")
            self._emit("skipped", reason="沒有辨識到內容")
            return
        out = self.config["output"]
        insert_text(text, method=out["method"], restore_clipboard=out["restore_clipboard"])
        latency = time.monotonic() - t0
        self._record(started_at, rec, text, t0, "ok")
        data = {"chars": len(text), "seconds": rec.seconds, "latency": latency}
        if self.config["privacy"]["log_text"]:
            data["text"] = text
        self._emit("result", **data)

    def _record(self, started_at: datetime, rec: Recording, text: str, t0: float, status: str) -> None:
        if self.usage is None:
            return
        try:
            self.usage.record(
                started_at=started_at,
                audio_seconds=rec.seconds,
                chars=len(text),
                latency_seconds=time.monotonic() - t0,
                status=status,
            )
        except Exception as e:  # 統計失敗不影響輸入
            log.warning("無法寫入使用紀錄：%s", e)
