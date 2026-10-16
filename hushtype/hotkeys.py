"""快捷鍵：鍵盤按鍵或滑鼠按鍵（中鍵、側鍵）。

設定檔裡鍵盤按鍵寫名稱（例如 "right ctrl"、"f9"），
滑鼠按鍵寫成 "mouse:middle"、"mouse:x1"（側鍵・後）、"mouse:x2"（側鍵・前）。

鍵盤與滑鼠都用 Windows 的低階 hook 監聽，並攔下選定的按鍵
（避免 F12 打開開發者工具、瀏覽器把側鍵當成「上一頁」）。

鍵盤 hook 的幾個原則，避免讓系統以為某個鍵一直按著（Ctrl 卡住）：
- 用虛擬鍵碼比對，左右 Ctrl／Shift／Alt 分得清楚，不會連另一邊一起攔。
- 程式自己送出的按鍵（Ctrl+V 貼上等，帶 INJECTED 旗標）一律放行。
- 只攔「按下」，「放開」永遠放行：就算哪一次按下沒攔到，系統也一定收得到放開。
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
    if key.startswith(VK_PREFIX):
        return f"按鍵 {key[len(VK_PREFIX):]}"
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


# 鍵盤按鍵名稱 → Windows 虛擬鍵碼（低階 hook 收到的是分左右的鍵碼）
_NAMED_VKS: dict[str, tuple[int, ...]] = {
    "ctrl": (0xA2, 0xA3), "left ctrl": (0xA2,), "right ctrl": (0xA3,),
    "shift": (0xA0, 0xA1), "left shift": (0xA0,), "right shift": (0xA1,),
    "alt": (0xA4, 0xA5), "left alt": (0xA4,), "right alt": (0xA5,), "alt gr": (0xA5,),
    "left windows": (0x5B,), "right windows": (0x5C,), "menu": (0x5D,), "apps": (0x5D,),
    "caps lock": (0x14,), "scroll lock": (0x91,), "num lock": (0x90,), "pause": (0x13,),
    "print screen": (0x2C,), "insert": (0x2D,), "delete": (0x2E,), "home": (0x24,), "end": (0x23,),
    "page up": (0x21,), "page down": (0x22,), "up": (0x26,), "down": (0x28,), "left": (0x25,), "right": (0x27,),
    "space": (0x20,), "tab": (0x09,), "enter": (0x0D,), "backspace": (0x08,), "esc": (0x1B,), "escape": (0x1B,),
    **{f"f{i}": (0x6F + i,) for i in range(1, 25)},
    **{chr(c): (c - 32,) for c in range(ord("a"), ord("z") + 1)},
    **{str(d): (0x30 + d,) for d in range(10)},
}
_VK_NAMES = {vks[0]: name for name, vks in _NAMED_VKS.items() if len(vks) == 1 and name not in ("alt gr", "apps", "escape")}
VK_PREFIX = "vk:"  # 表裡沒有的鍵存成 "vk:數字"


def key_vks(key: str) -> tuple[int, ...]:
    """鍵盤按鍵名稱 → 虛擬鍵碼。認不得就丟 ValueError。"""
    key = key.strip().lower()
    if key in _NAMED_VKS:
        return _NAMED_VKS[key]
    if key.startswith(VK_PREFIX) and key[len(VK_PREFIX):].isdigit():
        return (int(key[len(VK_PREFIX):]),)
    if len(key) == 1 and sys.platform == "win32":  # 標點符號等，依目前鍵盤配置查
        import ctypes

        code = ctypes.windll.user32.VkKeyScanW(ord(key))
        if code != -1 and code & 0xFF != 0xFF:
            return (code & 0xFF,)
    raise ValueError(f"不認得的快捷鍵「{key}」，請到設定重新選擇")


def vk_name(vk: int) -> str:
    return _VK_NAMES.get(vk, f"{VK_PREFIX}{vk}")


class _LowLevelHook:
    """Windows 低階 hook 的共用部分：專用執行緒跑訊息迴圈，事件交給另一條執行緒處理。

    hook 的 callback 必須很快返回（太慢 Windows 會略過甚至移除 hook），
    所以 callback 只做判斷和排進佇列，handler 在 _dispatch 執行緒呼叫。
    """

    HOOK_ID = 0
    WHAT = ""

    def __init__(self, handler: Callable):
        self.handler = handler
        self._events: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._proc = None  # 保留 callback 參照，避免被回收

    def start(self) -> None:
        if not mouse_supported():
            raise RuntimeError(f"{self.WHAT}快捷鍵只支援 Windows")
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
                log.exception("%s快捷鍵處理失敗", self.WHAT)

    def _filter(self, w_param: int, l_param: int) -> bool:
        """在 hook 執行緒呼叫：把事件排進 self._events，回傳 True 表示攔下這個事件。"""
        raise NotImplementedError

    def _run(self, ready: threading.Event, error: list[str]) -> None:
        import ctypes
        from ctypes import wintypes

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
            if n_code == 0:
                try:
                    if self._filter(w_param, l_param):
                        return 1
                except Exception:
                    pass  # 出錯時寧可放行，不能吃掉按鍵
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(proc)
        self._thread_id = kernel32.GetCurrentThreadId()
        hook = user32.SetWindowsHookExW(self.HOOK_ID, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not hook:
            error.append(f"無法監聽{self.WHAT}（錯誤碼 {ctypes.get_last_error()}）")
            ready.set()
            return
        ready.set()
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            user32.UnhookWindowsHookEx(hook)


class KeyHook(_LowLevelHook):
    """監聽鍵盤按鍵。handler(vk, down) 只在按下與放開時各呼叫一次（按住的自動重複不算）。

    vks 是要監聽的虛擬鍵碼，None 表示全部（錄製快捷鍵用）。
    suppress=True 時攔下這些鍵的「按下」，其他程式收不到；「放開」一律放行。
    """

    HOOK_ID = 13  # WH_KEYBOARD_LL
    WHAT = "鍵盤"
    LLKHF_INJECTED = 0x10

    def __init__(self, handler: Callable[[int, bool], None], vks=None, *, suppress: bool = False):
        super().__init__(handler)
        self.vks = frozenset(vks) if vks is not None else None
        self.suppress = suppress
        self._down: set[int] = set()

    def _filter(self, w_param: int, l_param: int) -> bool:
        import ctypes

        WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
        data = ctypes.cast(l_param, ctypes.POINTER(ctypes.c_uint32))  # KBDLLHOOKSTRUCT：vkCode, scanCode, flags…
        vk, flags = data[0], data[2]
        if flags & self.LLKHF_INJECTED or (self.vks is not None and vk not in self.vks):
            return False
        down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
        if down != (vk in self._down):
            (self._down.add if down else self._down.discard)(vk)
            self._events.put((vk, down))
        return down and self.suppress


class MouseHook(_LowLevelHook):
    """監聽滑鼠中鍵與側鍵。handler(button, down) 在另一條執行緒呼叫，不會拖慢滑鼠。

    suppress 裡的按鍵會被攔下，其他程式收不到。
    """

    HOOK_ID = 14  # WH_MOUSE_LL
    WHAT = "滑鼠"

    def __init__(self, handler: Callable[[str, bool], None], suppress: set[str] | frozenset[str] = frozenset()):
        super().__init__(handler)
        self.suppress = frozenset(suppress)

    def _filter(self, w_param: int, l_param: int) -> bool:
        import ctypes

        WM_MBUTTONDOWN, WM_MBUTTONUP = 0x0207, 0x0208
        WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
        if w_param in (WM_MBUTTONDOWN, WM_MBUTTONUP):
            button = "middle"
        elif w_param in (WM_XBUTTONDOWN, WM_XBUTTONUP):
            mouse_data = ctypes.cast(l_param, ctypes.POINTER(ctypes.c_uint32))[2]  # MSLLHOOKSTRUCT：pt(2), mouseData…
            button = "x1" if (mouse_data >> 16) & 0xFFFF == 1 else "x2"
        else:
            return False
        self._events.put((button, w_param in (WM_MBUTTONDOWN, WM_XBUTTONDOWN)))
        return button in self.suppress


def release_stuck_keys(vks=(0xA2, 0xA3)) -> list[int]:
    """系統以為按著、但其實沒人按的鍵（例如舊版留下的 Ctrl），送出「放開」讓它恢復。

    只在程式啟動時呼叫（這時使用者通常沒有按著這些鍵）。回傳處理了哪些鍵。
    """
    if sys.platform != "win32":
        return []
    import ctypes

    stuck = [vk for vk in vks if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000]
    if stuck:
        from .output import send_keys

        send_keys([(vk, False) for vk in stuck])
    return stuck


def capture(timeout: float = 10.0) -> str:
    """等使用者按下一個鍵盤按鍵或滑鼠中鍵／側鍵，回傳設定檔用的名稱。

    按 Esc 或逾時回傳空字串。滑鼠左右鍵不算，才不會抓到按「錄製」按鈕的那一下。
    """
    got: queue.Queue[str] = queue.Queue()
    kb = KeyHook(lambda vk, down: down and got.put(vk_name(vk)))
    kb.start()
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
        kb.stop()
        if mouse:
            mouse.stop()
    return "" if name == "esc" else name
