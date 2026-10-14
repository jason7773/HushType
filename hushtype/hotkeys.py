"""快捷鍵：鍵盤按鍵或滑鼠按鍵（中鍵、側鍵）。

設定檔裡鍵盤按鍵用 keyboard 套件的名稱（例如 "right ctrl"），
滑鼠按鍵寫成 "mouse:middle"、"mouse:x1"（側鍵・後）、"mouse:x2"（側鍵・前）。

滑鼠用 Windows 的低階滑鼠 hook 監聽，並攔下選定的按鍵，
避免瀏覽器把側鍵當成「上一頁／下一頁」。
"""

from __future__ import annotations

import logging
import queue
import sys
import threading
from typing import Callable

log = logging.getLogger(__name__)

MOUSE_PREFIX = "mouse:"
MOUSE_BUTTONS = ("middle", "x1", "x2")

KEY_NAMES = {
    "right ctrl": "右 Ctrl",
    "right alt": "右 Alt",
    "right shift": "右 Shift",
    "caps lock": "Caps Lock",
    "scroll lock": "Scroll Lock",
    "mouse:x1": "滑鼠側鍵（後）",
    "mouse:x2": "滑鼠側鍵（前）",
    "mouse:middle": "滑鼠中鍵",
}


def key_label(key: str) -> str:
    return KEY_NAMES.get(key, key.upper() if len(key) <= 3 else key.title())


def mouse_button(key: str) -> str | None:
    """"mouse:x2" → "x2"；不是滑鼠按鍵就回傳 None。"""
    if key.startswith(MOUSE_PREFIX):
        button = key[len(MOUSE_PREFIX):]
        if button in MOUSE_BUTTONS:
            return button
    return None


def mouse_supported() -> bool:
    return sys.platform == "win32"


class MouseHook:
    """監聽滑鼠中鍵與側鍵。handler(button, down) 在另一條執行緒呼叫，不會拖慢滑鼠。

    suppress 裡的按鍵會被攔下，其他程式收不到。
    """

    def __init__(self, handler: Callable[[str, bool], None], suppress: set[str] | frozenset[str] = frozenset()):
        self.handler = handler
        self.suppress = frozenset(suppress)
        self._events: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._proc = None  # 保留 callback 參照，避免被回收

    def start(self) -> None:
        if not mouse_supported():
            raise RuntimeError("滑鼠快捷鍵只支援 Windows")
        ready = threading.Event()
        error: list[str] = []
        self._thread = threading.Thread(target=self._run, args=(ready, error), daemon=True)
        self._thread.start()
        threading.Thread(target=self._dispatch, daemon=True).start()
        ready.wait(5)
        if error:
            self._events.put(None)
            raise RuntimeError(error[0])

    def stop(self) -> None:
        if self._thread is None:
            return
        import ctypes

        WM_QUIT = 0x0012
        ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self._thread.join(2)
        self._thread = None
        self._events.put(None)

    def _dispatch(self) -> None:
        while True:
            item = self._events.get()
            if item is None:
                return
            try:
                self.handler(*item)
            except Exception:
                log.exception("滑鼠快捷鍵處理失敗")

    def _run(self, ready: threading.Event, error: list[str]) -> None:
        import ctypes
        from ctypes import wintypes

        WH_MOUSE_LL = 14
        WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
        WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
        DOWN = {WM_MBUTTONDOWN, WM_XBUTTONDOWN}
        WATCHED = DOWN | {WM_MBUTTONUP, WM_XBUTTONUP}

        class MSLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("pt", wintypes.POINT),
                ("mouseData", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = LRESULT
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        def proc(n_code, w_param, l_param):
            if n_code == 0 and w_param in WATCHED:
                if w_param in (WM_MBUTTONDOWN, WM_MBUTTONUP):
                    button = "middle"
                else:
                    data = ctypes.cast(l_param, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                    button = "x1" if (data.mouseData >> 16) & 0xFFFF == 1 else "x2"
                self._events.put((button, w_param in DOWN))
                if button in self.suppress:
                    return 1
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(proc)
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            error.append(f"無法監聽滑鼠（錯誤碼 {ctypes.get_last_error()}）")
            ready.set()
            return
        ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(hook)


def capture(timeout: float = 10.0) -> str:
    """等使用者按下一個鍵盤按鍵或滑鼠中鍵／側鍵，回傳設定檔用的名稱。

    按 Esc 或逾時回傳空字串。滑鼠左右鍵不算，才不會抓到按「錄製」按鈕的那一下。
    """
    import keyboard

    got: queue.Queue[str] = queue.Queue()

    def on_key(event) -> None:
        if event.event_type == keyboard.KEY_DOWN:
            got.put((event.name or "").lower())

    kb = keyboard.hook(on_key)
    mouse = None
    if mouse_supported():
        mouse = MouseHook(lambda button, down: down and got.put(MOUSE_PREFIX + button), suppress=set(MOUSE_BUTTONS))
        try:
            mouse.start()
        except RuntimeError as e:
            log.warning("%s", e)
            mouse = None
    try:
        name = got.get(timeout=timeout)
    except queue.Empty:
        name = ""
    finally:
        keyboard.unhook(kb)
        if mouse:
            mouse.stop()
    return "" if name in ("esc", "escape") else name
