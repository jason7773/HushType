package io.github.jason7773.hushtype.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WavTest {
    private fun tone(n: Int, amp: Int) = ShortArray(n) { if (it % 2 == 0) amp.toShort() else (-amp).toShort() }

    @Test
    fun encodeWritesValidHeader() {
        val wav = Wav.encode(listOf(ShortArray(10) { 1000 }), 16_000)
        assertEquals(44 + 20, wav.size)
        assertEquals("RIFF", String(wav, 0, 4))
        assertEquals("WAVE", String(wav, 8, 4))
        assertEquals("data", String(wav, 36, 4))
        // 取樣率 16000，小端序
        assertEquals(16_000, (wav[24].toInt() and 0xff) or ((wav[25].toInt() and 0xff) shl 8))
        // 第一個樣本 1000 = 0x03E8
        assertEquals(0xE8.toByte(), wav[44])
        assertEquals(0x03.toByte(), wav[45])
    }

    @Test
    fun trimSilenceKeepsPaddingAroundSpeech() {
        val quiet = ShortArray(1600)
        val chunks = List(20) { quiet } + List(5) { tone(1600, 3000) } + List(20) { quiet }
        val trimmed = Wav.trimSilence(chunks, 16_000)
        // 說話 5 段，前後各留 0.5 秒（5 段 × 0.1 秒）
        assertEquals(15, trimmed.size)
    }

    @Test
    fun trimSilenceLeavesAllQuietAudioAlone() {
        val chunks = List(10) { ShortArray(1600) }
        assertEquals(10, Wav.trimSilence(chunks, 16_000).size)
    }

    @Test
    fun recordingReportsSpeechLengthAndVolume() {
        val rec = Wav.makeRecording(listOf(tone(16_000, 2000)), 16_000)
        assertEquals(1.0, rec.seconds, 0.001)
        assertEquals(2000.0, rec.rms, 0.5)
    }
}

class TextRulesTest {
    @Test
    fun detectsWhisperHallucinations() {
        assertTrue(TextRules.isHallucination("謝謝大家收看。"))
        assertTrue(TextRules.isHallucination("Thank you."))
        assertFalse(TextRules.isHallucination("謝謝你幫我改報告"))
    }

    @Test
    fun stripsThinkingAndTags() {
        assertEquals("你好。", TextRules.stripModelArtifacts("<think>\n想一下\n</think><transcript>\n你好。\n</transcript>"))
    }

    @Test
    fun appliesReplacementsInOrder() {
        assertEquals("我在學 Python", TextRules.applyReplacements("我在學 拍森", linkedMapOf("拍森" to "Python")))
    }

    @Test
    fun promptsIncludeTerms() {
        assertTrue(TextRules.sttPrompt(listOf("Groq", "Hushtype")).contains("Groq、Hushtype"))
        assertEquals("base", TextRules.cleanupPrompt("base", emptyList()))
    }

    @Test
    fun countsCharactersWithoutSpaces() {
        assertEquals(7, TextRules.countChars("你好 hello"))
    }

    @Test
    fun onlyConvertsTextThatLooksSimplified() {
        assertTrue(TextRules.looksSimplified("我们明天见"))
        assertFalse(TextRules.looksSimplified("皇后明天到"))
    }
}
