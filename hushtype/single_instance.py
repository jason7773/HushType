"""只允許一個 Hushtype 在執行；再開一次時叫出已經在跑的那個視窗。

用 Windows 的具名事件（不需要網路元件），其他平台不做限制。
"""

from __future__ import annotations

import sys
import threading
from typing import Callable

_NAME = "Local\\Hushtype-activate"
_ERROR_ALREADY_EXISTS = 183
_INFINITE = 0xFFFFFFFF


class Instance:
    def __init__(self, handle: int | None):
        self.handle = handle

    def listen(self, on_activate: Callable[[], None]) -> None:
        """在背景等其他啟動的程式通知；收到時呼叫 on_activate（在背景執行緒）。"""
        if not self.handle:
            return
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]

        def wait():
            while kernel32.WaitForSingleObject(self.handle, _INFINITE) == 0:
                on_activate()

        threading.Thread(target=wait, daemon=True, name="single-instance").start()


def acquire() -> Instance | None:
    """取得執行權；已經有一個在執行時通知它並回傳 None。"""
    if sys.platform != "win32":
        return Instance(None)
    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.SetEvent.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    # 自動重設的事件：每次 SetEvent 喚醒等待的那一方一次
    handle = kernel32.CreateEventW(None, 0, 0, _NAME)
    if not handle:
        return Instance(None)  # 建不起來就不限制，至少能開
    if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
        kernel32.SetEvent(handle)
        kernel32.CloseHandle(handle)
        return None
    return Instance(handle)
