"""語音 → 文字的處理流程，與平台無關，方便測試和日後移植。"""

from __future__ import annotations

import logging
import re

from .providers import ProviderError, SpeechToText, TextCleaner, create_cleaner, create_stt

log = logging.getLogger(__name__)

# Whisper 在靜音或雜音時常見的「幻覺」輸出
_HALLUCINATIONS = re.compile(
    r"^(謝謝(大家|您)?(收看|觀看|觀賞)|字幕由.*提供|請不吝點贊.*|"
    r"thank you\.?|thanks for watching\.?|you)[。.！!\s]*$",
    re.IGNORECASE,
)


class Pipeline:
    def __init__(
        self,
        stt: SpeechToText,
        cleaner: TextCleaner | None = None,
        *,
        cleanup_prompt: str = "",
        terms: list[str] | None = None,
        replacements: dict[str, str] | None = None,
        convert_to_traditional: bool = True,
    ):
        self.stt = stt
        self.cleaner = cleaner
        self.terms = terms or []
        self.replacements = replacements or {}
        self.cleanup_prompt = cleanup_prompt
        if self.terms:
            self.cleanup_prompt += "\n以下是使用者常用的專有名詞，請以這些寫法為準：" + "、".join(self.terms)
        self._opencc = None
        if convert_to_traditional:
            import opencc

            self._opencc = opencc.OpenCC("s2twp")

    def stt_prompt(self) -> str:
        prompt = "以下是繁體中文的口述內容，可能夾雜英文。"
        if self.terms:
            prompt += "詞彙：" + "、".join(self.terms) + "。"
        return prompt

    def run(self, wav: bytes) -> str:
        text = self.stt.transcribe(wav, prompt=self.stt_prompt())
        if not text or _HALLUCINATIONS.match(text.strip()):
            return ""
        text = self._to_traditional(text)
        if self.cleaner:
            try:
                cleaned = self.cleaner.clean(text, system_prompt=self.cleanup_prompt)
                text = self._to_traditional(cleaned) or text
            except ProviderError as e:
                # 整理失敗時仍貼出原始辨識結果，不讓使用者白講
                log.warning("文字整理失敗，改用原始辨識結果：%s", e)
        for wrong, right in self.replacements.items():
            text = text.replace(wrong, right)
        return text.strip()

    def _to_traditional(self, text: str) -> str:
        return self._opencc.convert(text) if self._opencc else text


def vocabulary_terms(config: dict) -> list[str]:
    """手動加入的詞在前，自動學到的接在後面（不重複）。"""
    vocab = config["vocabulary"]
    terms = list(vocab["terms"])
    seen = {t.lower() for t in terms}
    for t in vocab.get("learned", []):
        if t.lower() not in seen:
            terms.append(t)
            seen.add(t.lower())
    return terms


def build_pipeline(config: dict) -> Pipeline:
    stt = create_stt(config["stt"])
    cleanup = dict(config["cleanup"])
    cleaner = None
    prompt = cleanup.pop("system_prompt", "")
    if cleanup.pop("enabled", False):
        cleaner = create_cleaner(cleanup)
    return Pipeline(
        stt,
        cleaner,
        cleanup_prompt=prompt,
        terms=vocabulary_terms(config),
        replacements=config["vocabulary"]["replacements"],
        convert_to_traditional=config["output"]["convert_to_traditional"],
    )
