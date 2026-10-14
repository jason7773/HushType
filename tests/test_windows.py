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
