"""把文字送進目前游標所在的應用程式。"""

from __future__ import annotations

import threading
import time

# 貼上後還原剪貼簿是在背景做的；下一次貼上要等上一次還原完
_clipboard = threading.Lock()

VK_CONTROL, VK_V = 0x11, 0x56


def _send_inputs(events: list[tuple[int, int, int]]) -> None:
    """用一次 SendInput 送出 [(vk, scan, flags)]：整串一起進系統佇列，不會被使用者的按鍵插隊。"""
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    INPUT_KEYBOARD = 1
    inputs = (INPUT * len(events))()
    for i, (vk, scan, flags) in enumerate(events):
        inputs[i].type = INPUT_KEYBOARD
        inputs[i].ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    sent = ctypes.windll.user32.SendInput(len(events), inputs, ctypes.sizeof(INPUT))
    if sent != len(events):
        raise OSError(f"無法送出按鍵（{sent}/{len(events)}），可能被其他程式擋下")


def send_keys(keys: list[tuple[int, bool]]) -> None:
    """送出 [(虛擬鍵碼, 是否按下)]。"""
    KEYEVENTF_KEYUP = 0x0002
    _send_inputs([(vk, 0, 0 if down else KEYEVENTF_KEYUP) for vk, down in keys])


def paste() -> None:
    # Ctrl 的按下和放開放在同一次 SendInput，放開一定會跟著送出，不會留下按著的 Ctrl
    send_keys([(VK_CONTROL, True), (VK_V, True), (VK_V, False), (VK_CONTROL, False)])


def type_text(text: str, delay: float = 0.002) -> None:
    """逐字模擬打字（Unicode 輸入，不經過輸入法、不受鍵盤配置影響）。"""
    KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x0002, 0x0004
    data = text.replace("\r\n", "\n").encode("utf-16-le")
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        if unit == 0x0A:  # 換行用 Enter 鍵，多數程式不吃 Unicode 的換行字元
            send_keys([(0x0D, True), (0x0D, False)])
        else:
            _send_inputs([(0, unit, KEYEVENTF_UNICODE), (0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)])
        if delay:
            time.sleep(delay)


def insert_text(text: str, *, method: str = "paste", restore_clipboard: bool = True) -> None:
    if method == "type":
        type_text(text)
        return

    import pyperclip

    _clipboard.acquire()
    previous = None
    try:
        if restore_clipboard:
            try:
                previous = pyperclip.paste()
            except pyperclip.PyperclipException:
                previous = None
        pyperclip.copy(text)
        time.sleep(0.03)
        paste()
    except BaseException:
        _clipboard.release()
        raise
    if previous is None:
        _clipboard.release()
        return

    def restore():
        try:
            time.sleep(0.4)  # 等目標程式讀完剪貼簿
            pyperclip.copy(previous)
        except Exception:
            pass
        finally:
            _clipboard.release()

    threading.Thread(target=restore, daemon=True).start()
