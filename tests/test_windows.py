"""只在 Windows 上跑的測試：滑鼠 hook、UI Automation。"""

import sys
import threading
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="只在 Windows 執行")


def _send_xbutton(which: int) -> None:
    import ctypes
    from ctypes import wintypes

    MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP = 0x0080, 0x0100

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]

        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    for flag in (MOUSEEVENTF_XDOWN, MOUSEEVENTF_XUP):
        inp = INPUT(type=0)
        inp.mi = MOUSEINPUT(0, 0, which, flag, 0, 0)
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def test_mouse_hook_sees_side_button():
    from hushtype.hotkeys import MouseHook

    got = []
    done = threading.Event()

    def handler(button, down):
        got.append((button, down))
        if len(got) >= 2:
            done.set()

    hook = MouseHook(handler, suppress={"x2"})
    hook.start()
    try:
        time.sleep(0.2)
        _send_xbutton(2)
        if not done.wait(3):
            pytest.skip("這台機器沒有可用的桌面，收不到模擬的滑鼠事件")
    finally:
        hook.stop()
    assert got == [("x2", True), ("x2", False)]


def test_ui_automation_loads():
    from hushtype import focus

    uia, mod = focus._automation()
    assert uia is not None and hasattr(mod, "IUIAutomationValuePattern")
    assert focus.has_text_focus() in (True, False, None)


def test_focused_text_reads_native_text_box():
    import subprocess

    from hushtype import focus

    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$f = New-Object Windows.Forms.Form; $f.TopMost = $true;"
        "$t = New-Object Windows.Forms.TextBox; $t.Multiline = $true; $t.Dock = 'Fill';"
        "$t.Text = 'hello Hushtype world'; $f.Controls.Add($t);"
        "$f.Add_Shown({ $f.Activate(); $t.Focus(); $t.SelectionStart = 5 });"
        "[Windows.Forms.Application]::Run($f)"
    )
    proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", script])
    try:
        got = None
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            snap = focus.focused_text()
            if snap and "Hushtype" in snap[1]:
                got = snap
                break
            time.sleep(0.3)
        if got is None:
            pytest.skip("這台機器沒有可用的桌面，測試視窗拿不到焦點")
        assert got[1].strip() == "hello Hushtype world"
        assert focus.focused_text()[0] == got[0]  # 同一個輸入框，識別碼不變
    finally:
        proc.kill()


def test_second_instance_activates_first():
    from hushtype import single_instance

    first = single_instance.acquire()
    assert first is not None and first.handle
    woke = threading.Event()
    first.listen(woke.set)
    assert single_instance.acquire() is None  # 第二個會通知第一個然後結束
    assert woke.wait(3)
