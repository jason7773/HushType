"""開機自動啟動（Windows：目前使用者的「執行」登錄機碼，不需要系統管理員權限）。"""

from __future__ import annotations

import sys
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NAME = "Hushtype"
_LEGACY_NAME = "dictate"  # 改名前的版本


def supported() -> bool:
    return sys.platform == "win32"


def command() -> str:
    if getattr(sys, "frozen", False):  # 打包後的 Hushtype.exe
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launcher = Path(__file__).resolve().parent.parent / "hushtype.pyw"
    return f'"{pythonw}" "{launcher}" --minimized'


def is_enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _NAME)
            return True
    except FileNotFoundError:
        return False


def set_enabled(enabled: bool) -> None:
    if not supported():
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, _NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, _NAME)
            except FileNotFoundError:
                pass


def migrate_legacy() -> None:
    """舊版的開機啟動項目指向已刪除的 dictate.exe：刪掉它，若原本有開就改成新的。"""
    if not supported():
        return
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                winreg.QueryValueEx(key, _LEGACY_NAME)
            except FileNotFoundError:
                return
            winreg.DeleteValue(key, _LEGACY_NAME)
            winreg.SetValueEx(key, _NAME, 0, winreg.REG_SZ, command())
    except OSError:
        pass
