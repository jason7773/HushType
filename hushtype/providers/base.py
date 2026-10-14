"""服務介面與註冊表。

新增一個服務（例如 Azure、OpenAI、本機 whisper.cpp）只要：
1. 寫一個類別，實作 SpeechToText.transcribe 或 TextCleaner.clean
2. 用 @register_stt("名稱") 或 @register_cleaner("名稱") 註冊
3. 在 hushtype/providers/__init__.py 匯入該模組
4. config.toml 裡把 provider 改成那個名稱
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Callable


class ProviderError(RuntimeError):
    """呼叫服務失敗（網路、金鑰、額度等）。"""


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, wav: bytes, *, prompt: str | None = None) -> str:
        """把 16 kHz 單聲道 WAV 轉成文字。"""

    def check(self) -> None:
        """確認服務可以連線、金鑰有效；失敗時丟出 ProviderError。"""


class TextCleaner(ABC):
    @abstractmethod
    def clean(self, text: str, *, system_prompt: str) -> str:
        """依 system_prompt 整理逐字稿，只回傳整理後的文字。"""

    def check(self) -> None:
        """確認服務可以連線、金鑰有效；失敗時丟出 ProviderError。"""


_STT: dict[str, type[SpeechToText]] = {}
_CLEANERS: dict[str, type[TextCleaner]] = {}


def register_stt(name: str) -> Callable[[type[SpeechToText]], type[SpeechToText]]:
    def deco(cls: type[SpeechToText]) -> type[SpeechToText]:
        _STT[name] = cls
        return cls

    return deco


def register_cleaner(name: str) -> Callable[[type[TextCleaner]], type[TextCleaner]]:
    def deco(cls: type[TextCleaner]) -> type[TextCleaner]:
        _CLEANERS[name] = cls
        return cls

    return deco


def _build(registry: dict, kind: str, options: dict):
    options = dict(options)
    name = options.pop("provider", None)
    if name not in registry:
        known = ", ".join(sorted(registry)) or "（無）"
        raise ValueError(f"未知的{kind}服務：{name!r}，可用的有：{known}")
    return registry[name](**options)


def create_stt(options: dict) -> SpeechToText:
    return _build(_STT, "語音辨識", options)


def create_cleaner(options: dict) -> TextCleaner:
    return _build(_CLEANERS, "文字整理", options)


def resolve_api_key(api_key: str | None, api_key_env: str | None, *, required: bool = True) -> str:
    """依序找：設定檔的 api_key → Windows 認證管理員 → 環境變數。"""
    from ..keystore import get_secret

    if api_key:
        return api_key
    if api_key_env:
        stored = get_secret(api_key_env)
        if stored:
            return stored
        if os.environ.get(api_key_env):
            return os.environ[api_key_env]
    if not required:
        return ""
    raise ProviderError("尚未設定 API 金鑰，請到「設定」頁面填入")
