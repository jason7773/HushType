import copy
import io
import time
import wave
from datetime import datetime

import numpy as np
import pytest

from hushtype.audio import make_recording
from hushtype.config import DEFAULTS, load_config
from hushtype.pipeline import Pipeline, build_pipeline
from hushtype.providers import (
    ProviderError,
    SpeechToText,
    TextCleaner,
    create_cleaner,
    create_stt,
    register_stt,
)
from hushtype.providers import openai_compat


class FakeSTT(SpeechToText):
    def __init__(self, text):
        self.text = text
        self.prompts = []

    def transcribe(self, wav, *, prompt=None):
        self.prompts.append(prompt)
        return self.text


class FakeCleaner(TextCleaner):
    def __init__(self, result=None, error=None):
        self.result, self.error = result, error
        self.calls = []

    def clean(self, text, *, system_prompt):
        self.calls.append((text, system_prompt))
        if self.error:
            raise self.error
        return self.result


class FakeResponse:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.text = str(body)

    def json(self):
        return self._body


def test_pipeline_converts_to_traditional_and_cleans():
    cleaner = FakeCleaner(result="明天四点开会。")
    p = Pipeline(FakeSTT("嗯明天三点不对四点开会"), cleaner, cleanup_prompt="P")
    assert p.run(b"") == "明天四點開會。"
    # 送進整理模型前已先轉成繁體
    assert cleaner.calls[0][0] == "嗯明天三點不對四點開會"


def test_pipeline_falls_back_when_cleanup_fails():
    p = Pipeline(FakeSTT("测试"), FakeCleaner(error=ProviderError("429")))
    assert p.run(b"") == "測試"


def test_pipeline_drops_whisper_hallucination():
    cleaner = FakeCleaner(result="x")
    p = Pipeline(FakeSTT("謝謝觀看！"), cleaner)
    assert p.run(b"") == ""
    assert cleaner.calls == []


def test_pipeline_vocabulary_and_replacements():
    stt = FakeSTT("我在寫拍森")
    cleaner = FakeCleaner(result="我在寫拍森。")
    p = Pipeline(stt, cleaner, cleanup_prompt="P", terms=["Groq"], replacements={"拍森": "Python"})
    assert p.run(b"") == "我在寫Python。"
    assert "Groq" in stt.prompts[0]
    assert "Groq" in cleaner.calls[0][1]


def test_groq_stt_request(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    seen = {}

    def fake_post(url, headers, timeout, **kw):
        seen.update(url=url, headers=headers, **kw)
        return FakeResponse(200, {"text": " 你好 "})

    monkeypatch.setattr(openai_compat.requests, "post", fake_post)
    stt = create_stt({"provider": "groq", "model": "whisper-large-v3-turbo", "language": "zh"})
    assert stt.transcribe(b"RIFF", prompt="詞彙") == "你好"
    assert seen["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert seen["headers"]["Authorization"] == "Bearer k"
    assert seen["data"]["language"] == "zh"
    assert seen["data"]["prompt"] == "詞彙"


def test_cleaner_strips_think_block(monkeypatch):
    def fake_post(url, headers, timeout, **kw):
        assert url.endswith("/chat/completions")
        content = "<think>想一下</think>\n整理好的文字。"
        return FakeResponse(200, {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(openai_compat.requests, "post", fake_post)
    c = openai_compat.OpenAICompatibleCleaner(base_url="http://x/v1", model="m", api_key="k")
    assert c.clean("原文", system_prompt="S") == "整理好的文字。"


def test_http_error_becomes_provider_error(monkeypatch):
    monkeypatch.setattr(
        openai_compat.requests, "post", lambda *a, **k: FakeResponse(401, {"error": "bad key"})
    )
    stt = openai_compat.OpenAICompatibleSTT(base_url="http://x/v1", model="m", api_key="k")
    with pytest.raises(ProviderError, match="401"):
        stt.transcribe(b"")


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr("hushtype.keystore.get_secret", lambda name: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="API 金鑰"):
        create_stt({"provider": "groq", "model": "m"})


def test_unknown_provider():
    with pytest.raises(ValueError, match="未知"):
        create_stt({"provider": "nope"})


def test_custom_provider_can_be_registered():
    @register_stt("echo")
    class Echo(SpeechToText):
        def __init__(self, reply):
            self.reply = reply

        def transcribe(self, wav, *, prompt=None):
            return self.reply

    assert create_stt({"provider": "echo", "reply": "hi"}).transcribe(b"") == "hi"


def test_config_merges_defaults(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('[cleanup]\nenabled = false\n[hotkey]\nkey = "f9"\n', encoding="utf-8")
    cfg = load_config(f)
    assert cfg["hotkey"] == {"key": "f9", "mode": "hold", "suppress": True}
    assert cfg["cleanup"]["enabled"] is False
    assert cfg["cleanup"]["model"] == DEFAULTS["cleanup"]["model"]


def test_example_config_builds(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    p = build_pipeline(load_config("config.example.toml"))
    assert p.cleaner is not None
    assert p.replacements == {"拍森": "Python"}


def test_recording_encodes_wav():
    chunk = (np.sin(np.linspace(0, 100, 16000)) * 3000).astype(np.int16).reshape(-1, 1)
    rec = make_recording([chunk, chunk], 16000)
    assert rec.seconds == pytest.approx(2.0)
    assert rec.rms > 1000
    with wave.open(io.BytesIO(rec.wav)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getnframes()) == (16000, 1, 32000)


def test_usage_log_and_summary(tmp_path):
    from datetime import date, datetime

    from hushtype.stats import UsageLog, summarize

    log = UsageLog(tmp_path / "u.db")
    log.record(started_at=datetime(2026, 10, 13, 9, 5), audio_seconds=60, chars=200, latency_seconds=1, status="ok")
    log.record(started_at=datetime(2026, 10, 14, 9, 30), audio_seconds=30, chars=100, latency_seconds=2, status="ok")
    log.record(started_at=datetime(2026, 10, 14, 22, 0), audio_seconds=5, chars=0, latency_seconds=1, status="error")
    log.record(started_at=datetime(2026, 9, 1, 12, 0), audio_seconds=120, chars=300, latency_seconds=1, status="ok")

    s = summarize(log.rows(), today=date(2026, 10, 14), days=7, typing_cpm=40)
    assert s["today"]["count"] == 1 and s["today"]["errors"] == 1
    assert s["month"] == {
        "count": 2, "minutes": 1.5, "chars": 300, "avg_latency": 1.5,
        # 300 字 / 40 = 7.5 分鐘打字，減 1.5 分鐘說話、0.05 分鐘等待
        "saved_minutes": 6.0, "errors": 1,
    }
    assert s["total"]["count"] == 3
    assert s["streak_days"] == 2
    assert len(s["daily"]) == 7 and s["daily"][-1]["date"] == "2026-10-14"
    assert [m["month"] for m in s["monthly"]] == ["2026-10", "2026-09"]
    assert s["hourly"][9] == 2 and s["hourly"][22] == 0


def test_dashboard_renders(tmp_path):
    from hushtype.dashboard import write_dashboard
    from hushtype.stats import summarize

    out = write_dashboard(summarize([]), tmp_path / "d.html")
    html = out.read_text(encoding="utf-8")
    assert "使用統計" in html and "__DATA__" not in html


def test_cleaner_sends_extra_params(monkeypatch):
    seen = {}

    def fake_post(url, headers, timeout, **kw):
        seen.update(kw["json"])
        return FakeResponse(200, {"choices": [{"message": {"content": "好"}}]})

    monkeypatch.setattr(openai_compat.requests, "post", fake_post)
    c = openai_compat.OpenAICompatibleCleaner(
        base_url="http://x/v1", model="m", api_key="k", extra={"reasoning_effort": "low"}
    )
    c.clean("原文", system_prompt="S")
    assert seen["reasoning_effort"] == "low" and seen["model"] == "m"


def test_save_config_only_writes_changes_and_round_trips(tmp_path):
    import copy

    from hushtype.config import DEFAULTS, save_config

    cfg = copy.deepcopy(DEFAULTS)
    cfg["hotkey"]["key"] = "f9"
    cfg["cleanup"]["system_prompt"] = 'a "q" \\ b\n第二行 """'
    cfg["vocabulary"]["replacements"] = {'拍"森': "Py\\thon"}
    path = tmp_path / "c.toml"
    save_config(cfg, path)
    text = path.read_text(encoding="utf-8")
    assert "[stt]" not in text and 'key = "f9"' in text
    assert load_config(path) == cfg


def test_hotkey_names():
    from hushtype.hotkeys import key_label, mouse_button

    assert mouse_button("mouse:x2") == "x2"
    assert mouse_button("mouse:left") is None
    assert mouse_button("right ctrl") is None
    assert key_label("mouse:middle") == "滑鼠中鍵"
    assert key_label("right ctrl") == "右 Ctrl"
    assert key_label("f9") == "F9"


def test_engine_routes_mouse_button_events():
    from hushtype.engine import Engine

    calls = []
    engine = Engine.__new__(Engine)
    engine._mouse_button = "x2"
    engine.on_press = lambda: calls.append("down")
    engine.on_release = lambda: calls.append("up")
    engine._on_mouse("x1", True)
    engine._on_mouse("x2", True)
    engine._on_mouse("x2", False)
    assert calls == ["down", "up"]


def test_openai_and_gemini_providers(monkeypatch):
    import base64

    import hushtype.providers.openai_compat as oc

    sent = {}

    def fake_post(url, api_key, timeout, **kw):
        sent["url"], sent["key"], sent["kw"] = url, api_key, kw
        return {"choices": [{"message": {"content": "你好"}}], "text": "你好"}

    monkeypatch.setattr(oc, "_post", fake_post)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    monkeypatch.setattr("hushtype.keystore.get_secret", lambda name: None)

    cleaner = create_cleaner({"provider": "openai", "model": "gpt-5.4-mini"})
    assert cleaner.clean("嗯你好", system_prompt="p") == "你好"
    assert sent["url"] == "https://api.openai.com/v1/chat/completions" and sent["key"] == "sk-test"
    assert "temperature" not in sent["kw"]["json"]  # GPT-5 系列不接受自訂 temperature

    stt = create_stt({"provider": "openai", "model": "gpt-transcribe", "language": "zh"})
    stt.transcribe(b"RIFF")
    assert "language" not in sent["kw"]["data"]

    stt = create_stt({"provider": "gemini", "model": "gemini-3.5-flash-lite", "language": "zh"})
    assert stt.transcribe(b"RIFFdata", prompt="詞彙：Groq") == "你好"
    assert sent["url"].startswith("https://generativelanguage.googleapis.com/") and sent["key"] == "gm-test"
    parts = sent["kw"]["json"]["messages"][0]["content"]
    assert "Groq" in parts[0]["text"]
    assert base64.b64decode(parts[1]["input_audio"]["data"]) == b"RIFFdata"


def test_failed_recording_can_be_retried(monkeypatch):
    from hushtype import engine as engine_mod
    from hushtype.audio import Recording

    events = []
    cfg = copy.deepcopy(DEFAULTS)
    cfg["stats"]["enabled"] = False
    cfg["cleanup"]["enabled"] = False
    monkeypatch.setenv("GROQ_API_KEY", "gsk")
    monkeypatch.setattr("hushtype.keystore.get_secret", lambda name: None)
    eng = engine_mod.Engine(cfg, lambda kind, data: events.append((kind, data)))

    answers = iter([ProviderError("429"), "你好"])

    def run(wav):
        a = next(answers)
        if isinstance(a, Exception):
            raise a
        return a

    monkeypatch.setattr(eng.pipeline, "run", run)
    pasted = []
    monkeypatch.setattr(engine_mod, "insert_text", lambda text, **kw: pasted.append(text))
    monkeypatch.setattr(engine_mod.focus, "has_text_focus", lambda: False)

    rec = Recording(wav=b"", seconds=2.0, rms=1000)
    eng._process(rec, datetime.now(), time.monotonic())
    assert events[-1][0] == "error" and events[-1][1]["retry"] is True
    assert eng.failed is not None

    assert eng.retry() is True  # 背景 worker 會重新處理
    deadline = time.monotonic() + 3
    while not pasted and time.monotonic() < deadline:
        time.sleep(0.02)
    assert pasted == ["你好"]
    assert ("unplaced", {"text": "你好"}) in events
    assert eng.failed is None and eng.last_text == "你好"


def test_updater_versions_and_release(monkeypatch, tmp_path):
    import hashlib

    from hushtype import updater

    assert updater.is_newer("0.10.0", "0.9.9")
    assert not updater.is_newer("v0.4.0", "0.4.0")
    assert updater.parse_version("0.4.1-dev.7") == (0, 4, 1)

    payload = b"installer-bytes"

    class Resp:
        def __init__(self, status=200, data=None, body=b""):
            self.status_code, self._data, self._body = status, data, body
            self.headers = {"Content-Length": str(len(body))}

        def json(self):
            return self._data

        def raise_for_status(self):
            pass

        def iter_content(self, n):
            yield self._body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    release_json = {
        "tag_name": "v0.5.0",
        "html_url": "https://github.com/jason7773/dictate/releases/tag/v0.5.0",
        "assets": [
            {"name": "notes.txt", "browser_download_url": "x"},
            {
                "name": "Hushtype-setup-0.5.0.exe",
                "browser_download_url": "https://github.com/dl/Hushtype-setup-0.5.0.exe",
                "size": len(payload),
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
            },
        ],
    }

    def fake_get(url, stream=False, **kw):
        return Resp(body=payload) if stream else Resp(data=release_json)

    monkeypatch.setattr(updater.requests, "get", fake_get)
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    rel = updater.latest_release()
    assert rel.version == "0.5.0" and rel.url.endswith("0.5.0.exe")
    path = updater.download(rel)
    assert path.read_bytes() == payload

    rel.sha256 = "0" * 64
    with pytest.raises(updater.UpdateError):
        updater.download(rel)
    assert not path.exists()


def test_history_retention_and_encryption(tmp_path):
    from hushtype.history import History

    fake = (lambda t: b"enc:" + t.encode()[::-1], lambda b: bytes(b)[4:][::-1].decode())
    path = tmp_path / "history.db"
    h = History(path, "session", crypt=fake)
    h.add("只在記憶體")
    assert not path.exists()

    h.set_retention("7d")  # 改成保留：記憶體裡的也寫進去
    h.add("第二段", app="line.exe")
    assert path.exists() and "只在記憶體".encode() not in path.read_bytes()
    again = History(path, "7d", crypt=fake)
    assert [e.text for e in again.entries] == ["第二段", "只在記憶體"]

    import sqlite3
    with sqlite3.connect(path) as db:
        db.execute("UPDATE history SET created_at = '2000-01-01T00:00:00' WHERE app = 'line.exe'")
    again = History(path, "7d", crypt=fake)
    assert [e.text for e in again.entries] == ["只在記憶體"]

    again.set_retention("session")  # 改回不保存：刪掉硬碟上的紀錄
    assert not path.exists()


def test_summary_streaks_and_apps():
    from datetime import date, datetime

    from hushtype.stats import summarize

    rows = [
        (datetime(2026, 10, d, 10), 60.0, 120, 1.0, "ok", app)
        for d, app in [(1, "chrome.exe"), (2, "chrome.exe"), (3, "line.exe"), (10, "winword.exe"), (11, "")]
    ]
    s = summarize(rows, today=date(2026, 10, 11))
    assert s["active_days"] == 5 and s["longest_streak"] == 3 and s["streak_days"] == 2
    assert s["chars_per_minute"] == 120
    assert s["apps"][0]["app"] == "Chrome" and s["apps"][0]["count"] == 2
    assert s["heatmap"]["2026-10-03"] == 1


def test_legacy_data_folder_is_migrated(tmp_path, monkeypatch):
    from hushtype import config

    monkeypatch.setenv("APPDATA", str(tmp_path))
    old = tmp_path / "dictate"
    old.mkdir()
    (old / "config.toml").write_text('[hotkey]\nkey = "f9"\n', encoding="utf-8")
    (old / "usage.db").write_bytes(b"x")
    config.migrate_legacy_data()
    assert config.default_config_path() == tmp_path / "Hushtype" / "config.toml"
    assert config.load_config(config.default_config_path())["hotkey"]["key"] == "f9"
    assert (tmp_path / "Hushtype" / "usage.db").exists()
