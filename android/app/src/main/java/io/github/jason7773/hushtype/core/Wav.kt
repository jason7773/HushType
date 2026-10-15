package io.github.jason7773.hushtype.core

import kotlin.math.sqrt

/** 一段錄音：16 kHz 單聲道 WAV，只存在記憶體。 */
class Recording(val wav: ByteArray, val seconds: Double, val rms: Double)

/** 與平台無關的音訊處理，方便測試。 */
object Wav {
    fun sumSquares(chunk: ShortArray): Double {
        var sum = 0.0
        for (s in chunk) sum += s.toDouble() * s
        return sum
    }

    fun rms(chunk: ShortArray): Double = if (chunk.isEmpty()) 0.0 else sqrt(sumSquares(chunk) / chunk.size)

    /** 去掉開頭和結尾的靜音（各留一點緩衝），上傳的音檔更小、辨識也比較快。 */
    fun trimSilence(
        chunks: List<ShortArray>,
        sampleRate: Int,
        threshold: Double = 200.0,
        padSeconds: Double = 0.5,
    ): List<ShortArray> {
        val loud = chunks.indices.filter { chunks[it].isNotEmpty() && rms(chunks[it]) >= threshold }
        if (loud.isEmpty()) return chunks
        val pad = (padSeconds * sampleRate).toInt()
        var first = loud.first()
        var last = loud.last()
        var kept = 0
        while (first > 0 && kept < pad) {
            first--
            kept += chunks[first].size
        }
        kept = 0
        while (last < chunks.size - 1 && kept < pad) {
            last++
            kept += chunks[last].size
        }
        return chunks.subList(first, last + 1)
    }

    fun encode(chunks: List<ShortArray>, sampleRate: Int): ByteArray {
        val samples = chunks.sumOf { it.size }
        val dataBytes = samples * 2
        val out = ByteArray(44 + dataBytes)
        fun str(at: Int, s: String) = s.forEachIndexed { i, c -> out[at + i] = c.code.toByte() }
        fun int(at: Int, v: Int) {
            for (i in 0 until 4) out[at + i] = (v ushr (8 * i)).toByte()
        }
        fun short(at: Int, v: Int) {
            out[at] = v.toByte()
            out[at + 1] = (v ushr 8).toByte()
        }
        str(0, "RIFF"); int(4, 36 + dataBytes); str(8, "WAVE")
        str(12, "fmt "); int(16, 16); short(20, 1); short(22, 1)
        int(24, sampleRate); int(28, sampleRate * 2); short(32, 2); short(34, 16)
        str(36, "data"); int(40, dataBytes)
        var p = 44
        for (chunk in chunks) for (s in chunk) {
            out[p++] = s.toInt().toByte()
            out[p++] = (s.toInt() shr 8).toByte()
        }
        return out
    }

    /** 把錄到的片段組成 WAV。秒數是實際說話（含前後緩衝）的長度，音量是整段的平均。 */
    fun makeRecording(chunks: List<ShortArray>, sampleRate: Int, trim: Boolean = true): Recording {
        var sq = 0.0
        var n = 0
        for (c in chunks) {
            sq += sumSquares(c)
            n += c.size
        }
        val rms = if (n > 0) sqrt(sq / n) else 0.0
        val kept = if (trim) trimSilence(chunks, sampleRate) else chunks
        val seconds = kept.sumOf { it.size }.toDouble() / sampleRate
        return Recording(encode(kept, sampleRate), seconds, rms)
    }
}
