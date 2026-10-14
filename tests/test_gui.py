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
    import dictate.updater as updater

    def no_network(*a, **kw):
        raise updater.UpdateError("測試中不連網")

    monkeypatch.setattr(updater, "latest_release", no_network)
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
    page.set_hotkey("f9")
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


def test_overlay_follows_engine_state(window):
    ov = window.overlay
    window.on_event("state", {"state": "recording"})
    assert ov.mode == "recording" and ov.isVisible()
    window.on_event("state", {"state": "processing"})
    assert ov.mode == "processing"
    window.on_event("state", {"state": "idle"})
    assert ov.mode == "hidden"


def test_overlay_shows_error_and_can_be_disabled(window):
    window.on_event("error", {"message": "辨識失敗：服務回應 401"})
    assert window.overlay.mode == "error" and window.overlay.message == "辨識失敗"
    window.on_event("state", {"state": "idle"})  # 錯誤訊息留著，等計時器自己消失
    assert window.overlay.mode == "error"

    window.engine.config["ui"]["overlay"] = False
    window.overlay.dismiss()
    window.on_event("state", {"state": "recording"})
    assert window.overlay.mode == "hidden"


def test_theme_setting_saved_and_applied(window):
    from dictate.config import load_config
    from dictate.gui import theme

    page = window.settings_page
    page.theme.setCurrentIndex(page.theme.findData("dark"))
    page.stt_service.key.setText("gsk_x")
    page.stt_service.key.setModified(True)
    page.save()
    assert load_config(window.config_path)["ui"]["theme"] == "dark"
    assert theme.current["bg"] == theme.DARK["bg"]


def test_mouse_button_hotkey_saved_with_label(window):
    from dictate.config import load_config

    page = window.settings_page
    page.set_hotkey("mouse:x2")
    assert page.hotkey.currentText() == "滑鼠側鍵（前）"
    page._hotkey_captured("mouse:x1")
    assert page.hotkey.currentData() == "mouse:x1"
    page.save()
    assert load_config(window.config_path)["hotkey"]["key"] == "mouse:x1"
    assert "滑鼠側鍵（後）" in window.status_page.state_hint.text() or window.engine.state == "setup"


def test_wheel_over_dropdown_does_not_change_value(window):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    page = window.settings_page
    window.show()
    window.show_page(1)
    for box in (page.mode, page.cpm):
        before = box.currentIndex() if hasattr(box, "currentIndex") else box.value()
        event = QWheelEvent(
            QPointF(5, 5), QPointF(box.mapToGlobal(QPoint(5, 5))), QPoint(0, 0), QPoint(0, -120),
            Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False,
        )
        QtWidgets.QApplication.sendEvent(box, event)
        after = box.currentIndex() if hasattr(box, "currentIndex") else box.value()
        assert after == before


def test_unplaced_text_and_failure_card(window):
    window.on_event("unplaced", {"text": "這是一段沒有地方貼的文字"})
    assert window.card.mode == "text" and window.card.isVisible()
    window.card._act()
    assert QtWidgets.QApplication.clipboard().text() == "這是一段沒有地方貼的文字"

    retried = []
    window.engine.retry = lambda: retried.append(True) or True
    window.on_event("error", {"message": "辨識失敗：服務回應 429", "retry": True})
    assert window.card.mode == "error" and window.card.action.text() == "重試"
    window.card._act()
    assert retried == [True]


def test_switching_provider_suggests_its_models_and_key(window):
    from dictate.config import load_config

    form = window.settings_page.stt_service
    form.provider.setCurrentIndex(form.provider.findData("gemini"))
    assert form.model.currentText() == "gemini-3.5-flash-lite"
    assert form.env == "GEMINI_API_KEY"
    assert "Gemini" in form.note.text()
    form.key.setText("gm-key")
    form.key.setModified(True)
    window.settings_page.save()
    saved = load_config(window.config_path)
    assert saved["stt"]["provider"] == "gemini" and saved["stt"]["model"] == "gemini-3.5-flash-lite"
    assert "base_url" not in saved["stt"]
    assert window.store["GEMINI_API_KEY"] == "gm-key"


def test_copy_last_result_from_activity(window):
    window.on_event("result", {"chars": 4, "seconds": 2.0, "latency": 0.8, "output": "第一段話"})
    window.engine.last_text = "第二段話"
    window.on_event("result", {"chars": 4, "seconds": 2.0, "latency": 0.8, "output": "第二段話"})
    page = window.status_page
    assert "第二段話" not in page.activity.item(0).text()  # 沒開 log_text 時不顯示內容
    page.copy_last()
    assert QtWidgets.QApplication.clipboard().text() == "第二段話"
    page._copy_item(page.activity.item(1))
    assert QtWidgets.QApplication.clipboard().text() == "第一段話"


def test_update_banner_and_install(window, monkeypatch):
    from dictate import updater

    rel = updater.Release(version="9.9.9", url="https://example/x.exe", size=1, sha256="", page="")
    window.updates.release = rel
    window._update_checked(rel, "有新版 9.9.9")
    assert not window.status_page.update_card.isHidden()
    assert window.update_action.isVisible()

    monkeypatch.setattr(updater, "can_self_update", lambda: False)
    window.start_update()
    assert "開發版" in window.status_page.update_text.text()
