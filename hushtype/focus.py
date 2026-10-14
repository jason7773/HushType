"""判斷目前鍵盤焦點是不是在可以輸入文字的地方（Windows）。

回傳 True：有輸入框；False：確定沒有（例如焦點在桌面、網頁本文、按鈕）；
None：判斷不出來。只有 False 時才會跳出「複製文字」的小框，判斷不出來就照常貼上。

先看系統游標（caret），再用 UI Automation 查焦點元件的類型與是否唯讀。
"""

from __future__ import annotations

import logging
import sys
import threading

log = logging.getLogger(__name__)

UIA_EDIT = 50004
UIA_DOCUMENT = 50030
UIA_VALUE_PATTERN = 10002
UIA_TEXT_PATTERN = 10014
UIA_LEGACY_PATTERN = 10018
STATE_SYSTEM_READONLY = 0x40

_local = threading.local()


def has_text_focus() -> bool | None:
    if sys.platform != "win32":
        return None
    try:
        if _caret_in_foreground():
            return True
        return _uia_editable()
    except Exception as e:  # 任何意外都當成判斷不出來
        log.debug("無法判斷焦點：%s", e)
        return None


def _caret_in_foreground() -> bool:
    import ctypes
    from ctypes import wintypes

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    tid = user32.GetWindowThreadProcessId(hwnd, None)
    info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    if not user32.GetGUIThreadInfo(tid, ctypes.byref(info)):
        return False
    return bool(info.hwndCaret)


def _automation():
    """每條執行緒各自初始化 COM 與 UI Automation。"""
    uia = getattr(_local, "uia", None)
    if uia is None:
        import comtypes
        import comtypes.client

        comtypes.CoInitialize()
        mod = comtypes.client.GetModule("UIAutomationCore.dll")
        uia = comtypes.client.CreateObject(mod.CUIAutomation, interface=mod.IUIAutomation)
        _local.uia, _local.mod = uia, mod
    return uia, _local.mod


def _pattern(element, pattern_id: int, interface):
    try:
        unk = element.GetCurrentPattern(pattern_id)
    except Exception:
        return None
    if not unk:
        return None
    try:
        return unk.QueryInterface(interface)
    except Exception:
        return None


def _uia_editable() -> bool | None:
    uia, mod = _automation()
    element = uia.GetFocusedElement()
    if not element:
        return False
    control = element.CurrentControlType

    value = _pattern(element, UIA_VALUE_PATTERN, mod.IUIAutomationValuePattern)
    read_only = bool(value.CurrentIsReadOnly) if value else None
    if control == UIA_EDIT:
        return read_only is not True
    if read_only is False:
        return True

    legacy = _pattern(element, UIA_LEGACY_PATTERN, mod.IUIAutomationLegacyIAccessiblePattern)
    state = legacy.CurrentState if legacy else None
    if control == UIA_DOCUMENT:
        # 網頁本文是唯讀的 Document；Word、記事本的編輯區則不是
        return not (state & STATE_SYSTEM_READONLY) if state is not None else None
    if _pattern(element, UIA_TEXT_PATTERN, mod.IUIAutomationTextPattern) and not (
        state and state & STATE_SYSTEM_READONLY
    ):
        return True  # 例如終端機
    return False


def focused_text(before: int = 3000, after: int = 1000) -> tuple[tuple, str] | None:
    """焦點輸入框的 (識別碼, 游標附近的文字)，給「自動學新詞」在本機比對用。

    密碼欄、取不到文字或不是 Windows 時回傳 None。文字不會被儲存。
    """
    if sys.platform != "win32":
        return None
    try:
        uia, mod = _automation()
        element = uia.GetFocusedElement()
        if not element or element.CurrentIsPassword:
            return None
        key = (element.CurrentProcessId, tuple(element.GetRuntimeId() or ()))
        text = _text_near_caret(element, mod, before, after)
        if text is None:
            value = _pattern(element, UIA_VALUE_PATTERN, mod.IUIAutomationValuePattern)
            if value is None:
                return None
            text = (value.CurrentValue or "")[-(before + after):]
        return key, text
    except Exception as e:
        log.debug("無法讀取輸入框文字：%s", e)
        return None


def _text_near_caret(element, mod, before: int, after: int) -> str | None:
    tp = _pattern(element, UIA_TEXT_PATTERN, mod.IUIAutomationTextPattern)
    if tp is None:
        return None
    selection = tp.GetSelection()
    if not selection or selection.Length == 0:
        return None
    rng = selection.GetElement(0).Clone()
    # TextPatternRangeEndpoint_Start = 0、_End = 1；TextUnit_Character = 0
    rng.MoveEndpointByUnit(0, 0, -before)
    rng.MoveEndpointByUnit(1, 0, after)
    return rng.GetText(before + after)


def foreground_app() -> str:
    """前景視窗所屬程式的檔名（例如 chrome.exe），只用在本機統計；取不到時回傳空字串。"""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32")
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        hwnd = user32.GetForegroundWindow()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return ""
            return buf.value.replace("/", "\\").rsplit("\\", 1)[-1].lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""
