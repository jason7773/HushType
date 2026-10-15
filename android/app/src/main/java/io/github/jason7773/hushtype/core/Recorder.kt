package io.github.jason7773.hushtype.core

import android.annotation.SuppressLint
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlin.math.min

/** 麥克風錄音。音訊只留在記憶體，不寫入儲存空間。 */
class Recorder(private val sampleRate: Int = 16_000, maxSeconds: Int = 300) {
    private val maxSamples = sampleRate * maxSeconds
    private val chunks = ArrayList<ShortArray>()
    private var record: AudioRecord? = null
    private var thread: Thread? = null

    @Volatile private var running = false
    @Volatile private var samples = 0

    /** 最近一段音訊的音量（0–1），給介面顯示。 */
    @Volatile var level = 0f
        private set

    val recording: Boolean get() = running
    val elapsedSeconds: Double get() = samples.toDouble() / sampleRate
    val full: Boolean get() = samples >= maxSamples

    /** 呼叫前要先確認有麥克風權限。失敗（例如麥克風被其他程式占用）時回傳 false。 */
    @SuppressLint("MissingPermission")
    fun start(): Boolean {
        if (running) return true
        val minBuf = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuf, sampleRate / 5 * 2),
            )
        } catch (e: Exception) {
            return false
        }
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release()
            return false
        }
        try {
            rec.startRecording()
        } catch (e: Exception) {
            rec.release()
            return false
        }
        synchronized(chunks) { chunks.clear() }
        samples = 0
        level = 0f
        record = rec
        running = true
        thread = Thread({ loop(rec) }, "hushtype-mic").apply { start() }
        return true
    }

    private fun loop(rec: AudioRecord) {
        val frame = sampleRate / 20 // 50 ms
        while (running) {
            val buf = ShortArray(frame)
            val n = rec.read(buf, 0, frame)
            if (n <= 0) {
                if (n < 0) break
                continue
            }
            val chunk = if (n == frame) buf else buf.copyOf(n)
            if (samples < maxSamples) {
                synchronized(chunks) { chunks.add(chunk) }
                samples += n
            }
            level = min((Wav.rms(chunk) / 6000).toFloat(), 1f)
        }
    }

    private fun halt(): List<ShortArray> {
        running = false
        thread?.join(500)
        thread = null
        record?.let {
            try {
                it.stop()
            } catch (_: Exception) {
            }
            it.release()
        }
        record = null
        level = 0f
        return synchronized(chunks) { ArrayList(chunks).also { chunks.clear() } }
    }

    fun stop(): Recording = Wav.makeRecording(halt(), sampleRate)

    /** 丟掉這次錄音。 */
    fun cancel() {
        halt()
    }
}
