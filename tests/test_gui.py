"""介面測試：在沒有螢幕的環境下用 offscreen 模式建立視窗、操作設定頁並儲存。"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture
def window(tmp_path, monkeypatch):
    import dictate.engine
    import dictate.keystore as keystore
    from dictate import autostart
    from dictate.config import load_config

    store = {}
    monkeypatch.setattr(keystore, "get_secret", lambda name: store.get(name))
    monkeypatch.setattr(keystore, "set_secret", lambda name, value: store.__setitem__(name, value))
    monkeypatch.setattr(dictate.engine.Engine, "bind", lambda self: None)
    monkeypatch.setattr(dictate.engine.Engine, "unbind", lambda self: None)
    monkeypatch.setattr(autostart, "set_enabled", lambda on: None)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path))

    from dictate import gui

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    gui.theme.apply(app)
    path = tmp_path / "dictate" / "config.toml"
    w = gui.MainWindow(path, load_config(path))
    w.store = store
    yield w
    w.quit()


def test_starts_in_setup_state_without_key(window):
    assert window.engine.state == "setup"
    assert window.status_page.state_title.text() == "需要設定"


def test_save_settings_stores_key_and_applies(window):
    from dictate.config import load_config

    page = window.settings_page
    page.stt_service.key.setText("gsk_test")
    page.stt_service.key.setModified(True)
    page.hotkey.setCurrentText("f9")
    page.replacements.setPlainText("拍森 → Python\n錯字=正字")
    page.save()

    assert page.note.text() == "已儲存，設定已生效"
    assert window.store == {"GROQ_API_KEY": "gsk_test"}
    assert window.engine.state == "idle"
    saved = load_config(window.config_path)
    assert saved["hotkey"]["key"] == "f9"
    assert saved["vocabulary"]["replacements"] == {"拍森": "Python", "錯字": "正字"}
    assert "api_key" not in saved["stt"]
    assert "gsk_test" not in window.config_path.read_text(encoding="utf-8")


def test_legacy_key_in_config_moves_to_keystore(window, tmp_path):
    cfg = window.engine.config
    cfg["stt"]["api_key"] = "gsk_old"
    cfg["cleanup"]["api_key"] = "gsk_old"
    window.settings_page.load()
    window.settings_page.save()
    assert window.store["GROQ_API_KEY"] == "gsk_old"
    assert "gsk_old" not in window.config_path.read_text(encoding="utf-8")


def test_custom_provider_settings(window):
    from dictate.config import load_config

    page = window.settings_page
    f = page.cleanup_service
    f.provider.setCurrentIndex(f.provider.findData("openai_compatible"))
    f.base_url.setText("http://127.0.0.1:8080/v1")
    page.effort.setCurrentIndex(page.effort.findData(None))
    page.stt_service.key.setText("gsk_x")
    page.stt_service.key.setModified(True)
    page.save()
    saved = load_config(window.config_path)["cleanup"]
    assert saved["provider"] == "openai_compatible"
    assert saved["base_url"] == "http://127.0.0.1:8080/v1"
    assert "reasoning_effort" not in saved.get("extra", {})
    assert window.engine.pipeline.cleaner.base_url == "http://127.0.0.1:8080/v1"


def test_events_update_activity_and_stats(window):
    window.on_event("result", {"chars": 12, "seconds": 3.0, "latency": 1.2})
    window.on_event("error", {"message": "辨識失敗：測試"})
    assert window.status_page.activity.count() == 2
    window.show_page(2)
    assert window.stats_page.summary is not None


def test_parse_replacements():
    from dictate.gui.settings_page import parse_replacements

    assert parse_replacements("a → b\nc->d\ne = f\n無分隔\n → x") == {"a": "b", "c": "d", "e": "f"}
