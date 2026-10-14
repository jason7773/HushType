"""API 金鑰存在作業系統的安全儲存區（Windows 為「認證管理員」），不寫進設定檔。"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SERVICE = "dictate"


def get_secret(name: str) -> str | None:
    try:
        import keyring

        return keyring.get_password(SERVICE, name)
    except Exception as e:  # 沒有安裝 keyring 或系統沒有可用的儲存區
        log.debug("無法讀取金鑰 %s：%s", name, e)
        return None


def set_secret(name: str, value: str) -> None:
    import keyring

    if value:
        keyring.set_password(SERVICE, name, value)
    else:
        try:
            keyring.delete_password(SERVICE, name)
        except keyring.errors.PasswordDeleteError:
            pass
