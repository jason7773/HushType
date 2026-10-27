"""語音 → 文字的處理流程，與平台無關，方便測試和日後移植。"""

from __future__ import annotations

import logging
import re
import threading
import time

from .providers import ProviderError, SpeechToText, TextCleaner, create_cleaner, create_stt

log = logging.getLogger(__name__)

# Whisper 在靜音或雜音時常見的「幻覺」輸出
_HALLUCINATIONS = re.compile(
    r"^(謝謝(大家|您)?(收看|觀看|觀賞)|字幕由.*提供|請不吝點贊.*|"
    r"thank you\.?|thanks for watching\.?|you)[。.！!\s]*$",
    re.IGNORECASE,
)

_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")

KEEP_LANGUAGE_RULE = "保持逐字稿原本的語言，不要翻譯：英文就輸出英文，中英夾雜就維持中英夾雜。"


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
        language: str = "",
    ):
        self.stt = stt
        self.language = language
        self.cleaner = cleaner
        self.timings: dict[str, float] = {}  # 上一次各步驟花的秒數
        self.terms = terms or []
        self.replacements = replacements or {}
        # 自訂的整理規則也一樣：不管規則怎麼寫，都不能把英文翻成中文
        self.cleanup_prompt = cleanup_prompt + "\n" + KEEP_LANGUAGE_RULE
        if self.terms:
            self.cleanup_prompt += "\n以下是使用者常用的專有名詞，請以這些寫法為準：" + "、".join(self.terms)
        self._opencc = None
        if convert_to_traditional:
            import opencc

            self._opencc = opencc.OpenCC("s2twp")

    def stt_prompt(self) -> str:
        if self.language == "en":
            prompt = "The following is dictated English."
            if self.terms:
                prompt += " Vocabulary: " + ", ".join(self.terms) + "."
            return prompt
        if self.language == "zh":
            prompt = "以下是繁體中文的口述內容，可能夾雜英文。"
        else:
            # 中英都有的範例，辨識模型才不會偏向只寫中文
            prompt = "以下是口述內容，可能是中文、英文或中英夾雜，例如：明天的 meeting 改到三點。This may also be entirely in English."
        if self.terms:
            prompt += "詞彙：" + "、".join(self.terms) + "。"
        return prompt

    def warm_up(self) -> None:
        """在背景先連上辨識和整理服務（不送任何內容）。"""

        def run():
            for service in (self.stt, self.cleaner):
                if service is not None:
                    try:
                        service.warm_up()
                    except Exception:
                        pass

        threading.Thread(target=run, daemon=True).start()

    def run(self, wav: bytes) -> str:
        self.timings = {}
        t = time.monotonic()
        text = self.stt.transcribe(wav, prompt=self.stt_prompt())
        self.timings["stt"] = time.monotonic() - t
        if not text or _HALLUCINATIONS.match(text.strip()):
            return ""
        text = self._to_traditional(text)
        if self.cleaner:
            t = time.monotonic()
            try:
                cleaned = self._to_traditional(self.cleaner.clean(text, system_prompt=self.cleanup_prompt))
                if cleaned and not _CJK.search(text) and _CJK.search(cleaned):
                    # 說的是英文，整理後卻冒出中文：模型擅自翻譯了，改用原本的辨識結果
                    log.warning("文字整理把英文翻成中文，改用原始辨識結果")
                    cleaned = ""
                text = cleaned or text
            except ProviderError as e:
                # 整理失敗時仍貼出原始辨識結果，不讓使用者白講
                log.warning("文字整理失敗，改用原始辨識結果：%s", e)
            self.timings["cleanup"] = time.monotonic() - t
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
        language=config["stt"].get("language") or "",
    )
