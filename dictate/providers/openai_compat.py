"""OpenAI 相容 API（Groq、OpenAI、本機 llama.cpp / whisper.cpp server 等都適用）。"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from .base import (
    ProviderError,
    SpeechToText,
    TextCleaner,
    register_cleaner,
    register_stt,
    resolve_api_key,
)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _is_local(base_url: str) -> bool:
    return urlparse(base_url).hostname in {"localhost", "127.0.0.1", "::1"}


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _check(base_url: str, api_key: str, model: str) -> None:
    """列出模型，確認金鑰有效且型號存在。"""
    try:
        resp = requests.get(base_url.rstrip("/") + "/models", headers=_headers(api_key), timeout=10)
    except requests.RequestException as e:
        raise ProviderError(f"連線失敗：{e}") from e
    if resp.status_code == 401:
        raise ProviderError("API 金鑰無效")
    if resp.status_code != 200:
        raise ProviderError(f"服務回應 {resp.status_code}")
    try:
        ids = {m["id"] for m in resp.json().get("data", [])}
    except (ValueError, KeyError, TypeError):
        return
    if ids and model not in ids:
        raise ProviderError(f"服務上沒有模型 {model}，或你的帳號無權使用")


def _post(url: str, api_key: str, timeout: float, **kwargs) -> dict:
    try:
        resp = requests.post(url, headers=_headers(api_key), timeout=timeout, **kwargs)
    except requests.RequestException as e:
        raise ProviderError(f"連線失敗：{e}") from e
    if resp.status_code != 200:
        raise ProviderError(f"服務回應 {resp.status_code}：{resp.text[:300]}")
    return resp.json()


@register_stt("openai_compatible")
class OpenAICompatibleSTT(SpeechToText):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        language: str | None = None,
        timeout: float = 30,
    ):
        self.base_url = base_url
        self.url = base_url.rstrip("/") + "/audio/transcriptions"
        self.model = model
        self.api_key = resolve_api_key(api_key, api_key_env, required=not _is_local(base_url))
        self.language = language
        self.timeout = timeout

    def check(self) -> None:
        _check(self.base_url, self.api_key, self.model)

    def transcribe(self, wav: bytes, *, prompt: str | None = None) -> str:
        data = {"model": self.model, "response_format": "json", "temperature": "0"}
        if self.language:
            data["language"] = self.language
        if prompt:
            data["prompt"] = prompt
        body = _post(
            self.url,
            self.api_key,
            self.timeout,
            files={"file": ("audio.wav", wav, "audio/wav")},
            data=data,
        )
        return body.get("text", "").strip()


@register_cleaner("openai_compatible")
class OpenAICompatibleCleaner(TextCleaner):
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        temperature: float = 0.2,
        timeout: float = 30,
        extra: dict | None = None,
    ):
        self.base_url = base_url
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.extra = extra or {}  # 額外參數，例如 reasoning_effort
        self.model = model
        self.api_key = resolve_api_key(api_key, api_key_env, required=not _is_local(base_url))
        self.temperature = temperature
        self.timeout = timeout

    def check(self) -> None:
        _check(self.base_url, self.api_key, self.model)

    def clean(self, text: str, *, system_prompt: str) -> str:
        body = _post(
            self.url,
            self.api_key,
            self.timeout,
            json={
                "model": self.model,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"<transcript>\n{text}\n</transcript>"},
                ],
                **self.extra,
            },
        )
        try:
            content = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise ProviderError(f"回應格式不正確：{body}") from e
        # 推理型模型（如 Qwen3）可能把思考過程放在 <think> 裡
        content = _THINK_BLOCK.sub("", content)
        content = content.replace("<transcript>", "").replace("</transcript>", "")
        return content.strip()


@register_stt("groq")
class GroqSTT(OpenAICompatibleSTT):
    def __init__(self, base_url: str = GROQ_BASE_URL, api_key_env: str = "GROQ_API_KEY", **kw):
        super().__init__(base_url=base_url, api_key_env=api_key_env, **kw)


@register_cleaner("groq")
class GroqCleaner(OpenAICompatibleCleaner):
    def __init__(self, base_url: str = GROQ_BASE_URL, api_key_env: str = "GROQ_API_KEY", **kw):
        super().__init__(base_url=base_url, api_key_env=api_key_env, **kw)
