package io.github.jason7773.hushtype.core

import android.icu.text.Transliterator

/** 一次口述需要的設定（從 Settings 取一份快照，背景執行時不受畫面改動影響）。 */
data class DictationConfig(
    val provider: Provider,
    val apiKey: String,
    val sttModel: String,
    val language: String,
    val cleanupEnabled: Boolean,
    val cleanupModel: String,
    val cleanupPrompt: String,
    val terms: List<String>,
    val replacements: Map<String, String>,
    val toTraditional: Boolean,
)

class DictationResult(val text: String, val sttMs: Long, val cleanupMs: Long, val cleanupFailed: Boolean)

/** 語音 → 文字：辨識、過濾幻覺、簡轉繁、AI 整理、固定替換。 */
class Dictation(private val config: DictationConfig) {
    private val client = ApiClient(config.provider, config.apiKey)

    fun warmUp() = client.warmUp()

    fun run(recording: Recording): DictationResult {
        var t = System.nanoTime()
        var text = client.transcribe(
            recording.wav,
            config.sttModel,
            config.language.ifEmpty { null },
            TextRules.sttPrompt(config.terms, config.language),
        )
        val sttMs = (System.nanoTime() - t) / 1_000_000
        if (text.isBlank() || TextRules.isHallucination(text)) return DictationResult("", sttMs, 0, false)
        if (config.toTraditional) text = Chinese.toTraditional(text)

        var cleanupMs = 0L
        var cleanupFailed = false
        if (config.cleanupEnabled && config.cleanupModel.isNotBlank()) {
            t = System.nanoTime()
            try {
                val prompt = TextRules.cleanupPrompt(config.cleanupPrompt, config.terms)
                val cleaned = client.clean(text, config.cleanupModel, prompt)
                // 說的是英文，整理後卻冒出中文：模型擅自翻譯了，改用原本的辨識結果
                val translated = !TextRules.containsCjk(text) && TextRules.containsCjk(cleaned)
                if (cleaned.isNotBlank() && !translated) text = cleaned
            } catch (e: ApiException) {
                // 整理失敗時仍輸出原始辨識結果，不讓使用者白講
                cleanupFailed = true
            }
            cleanupMs = (System.nanoTime() - t) / 1_000_000
        }
        text = TextRules.applyReplacements(text, config.replacements)
        return DictationResult(text.trim(), sttMs, cleanupMs, cleanupFailed)
    }
}

/** 用系統內建的 ICU 做簡轉繁，不必另外打包字典。只在明顯是簡體時才轉，避免把繁體字轉錯。 */
object Chinese {
    private val transliterator: Transliterator? by lazy {
        runCatching { Transliterator.getInstance("Simplified-Traditional") }.getOrNull()
    }

    fun toTraditional(text: String): String {
        if (!TextRules.looksSimplified(text)) return text
        return transliterator?.transliterate(text) ?: text
    }
}
