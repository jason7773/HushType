package io.github.jason7773.hushtype.core

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URI
import java.util.Base64
import java.util.UUID

/** 可選的服務。都走 OpenAI 相容 API；金鑰由使用者自己申請。 */
enum class Provider(
    val id: String,
    val label: String,
    val baseUrl: String,
    val sttModels: List<String>,
    val cleanupModels: List<String>,
    val keyUrl: String,
) {
    GROQ(
        "groq", "Groq", "https://api.groq.com/openai/v1",
        listOf("whisper-large-v3-turbo", "whisper-large-v3"),
        listOf("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"),
        "https://console.groq.com/keys",
    ),
    OPENAI(
        "openai", "OpenAI", "https://api.openai.com/v1",
        listOf("gpt-4o-mini-transcribe", "gpt-4o-transcribe", "gpt-transcribe", "whisper-1"),
        listOf("gpt-5.4-mini", "gpt-6-luna", "gpt-5-mini"),
        "https://platform.openai.com/api-keys",
    ),
    GEMINI(
        "gemini", "Gemini", "https://generativelanguage.googleapis.com/v1beta/openai",
        listOf("gemini-3.5-flash-lite", "gemini-3.8-flash"),
        listOf("gemini-3.5-flash-lite", "gemini-3.8-flash"),
        "https://aistudio.google.com/apikey",
    );

    /** Gemini 沒有 /audio/transcriptions，改用多模態對話送出錄音。 */
    val sttViaChat: Boolean get() = this == GEMINI

    /** OpenAI 的推理型模型不接受自訂 temperature。 */
    val cleanupTemperature: Double? get() = if (this == OPENAI) null else 0.2

    companion object {
        fun of(id: String?): Provider = entries.firstOrNull { it.id == id } ?: GROQ
    }
}

class ApiException(message: String) : Exception(message)

/** 呼叫 OpenAI 相容 API。只用系統內建的 HttpURLConnection，連線會被重複使用。 */
class ApiClient(private val provider: Provider, private val apiKey: String) {
    private val base = provider.baseUrl.trimEnd('/')

    /** 先跟服務建好連線（不送任何內容），放開按鈕時就能直接上傳。 */
    fun warmUp() {
        try {
            val conn = open("$base/models", "HEAD", 5_000)
            conn.responseCode
            conn.inputStream.close()
        } catch (_: Exception) {
        }
    }

    /** 列出模型，確認金鑰有效且型號存在。 */
    fun check(models: List<String>) {
        val conn = open("$base/models", "GET", 10_000)
        val body = read(conn)
        val ids = try {
            val data = JSONObject(body).optJSONArray("data") ?: JSONArray()
            (0 until data.length()).map { data.getJSONObject(it).optString("id") }.toSet()
        } catch (_: Exception) {
            return
        }
        if (ids.isEmpty()) return
        for (m in models) {
            if (m !in ids && "models/$m" !in ids) throw ApiException("服務上沒有模型 $m，或你的帳號無權使用")
        }
    }

    fun transcribe(wav: ByteArray, model: String, language: String?, prompt: String?): String =
        if (provider.sttViaChat) transcribeViaChat(wav, model, language, prompt) else transcribeWhisper(wav, model, language, prompt)

    private fun transcribeWhisper(wav: ByteArray, model: String, language: String?, prompt: String?): String {
        // gpt-transcribe 改用 languages 參數，也不回傳偵測到的語言，交給 prompt 提示即可
        if (model.startsWith("gpt-transcribe")) return whisperRequest(wav, model, null, prompt, "json").optString("text").trim()
        if (!language.isNullOrEmpty()) return whisperRequest(wav, model, language, prompt, "json").optString("text").trim()
        // 自動偵測：英文就照英文寫，不會被硬轉成中文。
        // 偶爾口音較重的中文會被判成其他語言（例如日文、粵語），這時固定成中文再辨識一次。
        var json = whisperRequest(wav, model, null, prompt, "verbose_json")
        if (TextRules.shouldRetryAsChinese(json.optString("language"))) json = whisperRequest(wav, model, "zh", prompt, "json")
        return json.optString("text").trim()
    }

    private fun whisperRequest(wav: ByteArray, model: String, language: String?, prompt: String?, format: String): JSONObject {
        val boundary = "----hushtype" + UUID.randomUUID().toString().replace("-", "")
        val body = ByteArrayOutputStream(wav.size + 1024)
        fun field(name: String, value: String) {
            body.write("--$boundary\r\nContent-Disposition: form-data; name=\"$name\"\r\n\r\n$value\r\n".toByteArray())
        }
        field("model", model)
        field("response_format", format)
        field("temperature", "0")
        if (!language.isNullOrEmpty()) field("language", language)
        if (!prompt.isNullOrEmpty()) field("prompt", prompt)
        body.write(
            ("--$boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.wav\"\r\n" +
                "Content-Type: audio/wav\r\n\r\n").toByteArray(),
        )
        body.write(wav)
        body.write("\r\n--$boundary--\r\n".toByteArray())

        val conn = open("$base/audio/transcriptions", "POST", 45_000)
        conn.setRequestProperty("Content-Type", "multipart/form-data; boundary=$boundary")
        send(conn, body.toByteArray())
        return parse(read(conn))
    }

    private fun transcribeViaChat(wav: ByteArray, model: String, language: String?, prompt: String?): String {
        var instruction = TextRules.GEMINI_STT_INSTRUCTION
        instruction += TextRules.geminiLanguageHint(language)
        if (!prompt.isNullOrEmpty()) instruction += "\n" + prompt
        val content = JSONArray()
            .put(JSONObject().put("type", "text").put("text", instruction))
            .put(
                JSONObject().put("type", "input_audio").put(
                    "input_audio",
                    JSONObject().put("data", Base64.getEncoder().encodeToString(wav)).put("format", "wav"),
                ),
            )
        val payload = JSONObject()
            .put("model", model)
            .put("temperature", 0)
            .put("messages", JSONArray().put(JSONObject().put("role", "user").put("content", content)))
            .put("reasoning_effort", "low")
        return TextRules.stripModelArtifacts(chat(payload, 60_000))
    }

    /** 依 systemPrompt 整理逐字稿。推理型模型會要求少想一點，回應較快。 */
    fun clean(text: String, model: String, systemPrompt: String): String {
        val messages = JSONArray()
            .put(JSONObject().put("role", "system").put("content", systemPrompt))
            .put(JSONObject().put("role", "user").put("content", "<transcript>\n$text\n</transcript>"))
        val payload = JSONObject().put("model", model).put("messages", messages)
        provider.cleanupTemperature?.let { payload.put("temperature", it) }
        payload.put("reasoning_effort", "low")
        val content = try {
            chat(payload, 30_000)
        } catch (e: ApiException) {
            // 不支援推理強度的模型會回 400，拿掉再試一次
            if (e.message?.contains("reasoning") != true) throw e
            payload.remove("reasoning_effort")
            chat(payload, 30_000)
        }
        return TextRules.stripModelArtifacts(content)
    }

    private fun chat(payload: JSONObject, timeoutMs: Int): String {
        val conn = open("$base/chat/completions", "POST", timeoutMs)
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        send(conn, payload.toString().toByteArray())
        val json = parse(read(conn))
        return try {
            json.getJSONArray("choices").getJSONObject(0).getJSONObject("message").optString("content")
        } catch (e: Exception) {
            throw ApiException("回應格式不正確")
        }
    }

    private fun open(url: String, method: String, readTimeoutMs: Int): HttpURLConnection {
        val conn = URI(url).toURL().openConnection() as HttpURLConnection
        conn.requestMethod = method
        conn.connectTimeout = 10_000
        conn.readTimeout = readTimeoutMs
        conn.useCaches = false
        if (apiKey.isNotEmpty()) conn.setRequestProperty("Authorization", "Bearer $apiKey")
        return conn
    }

    private fun send(conn: HttpURLConnection, body: ByteArray) {
        conn.doOutput = true
        conn.setFixedLengthStreamingMode(body.size)
        try {
            conn.outputStream.use { it.write(body) }
        } catch (e: IOException) {
            throw ApiException("連線失敗，請檢查網路")
        }
    }

    private fun read(conn: HttpURLConnection): String {
        val code = try {
            conn.responseCode
        } catch (e: IOException) {
            throw ApiException("連線失敗，請檢查網路")
        }
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = try {
            stream?.use { it.readBytes().toString(Charsets.UTF_8) } ?: ""
        } catch (e: IOException) {
            throw ApiException("連線中斷，請再試一次")
        }
        if (code in 200..299) return text
        throw ApiException(
            when (code) {
                401, 403 -> "API 金鑰無效或沒有權限"
                404 -> "找不到模型或服務位址（${errorDetail(text)}）"
                413 -> "錄音太長，請分段說"
                429 -> "已達服務的用量上限，請稍後再試"
                in 500..599 -> "服務暫時無法使用（$code），請稍後再試"
                else -> "服務回應 $code：${errorDetail(text)}"
            },
        )
    }

    private fun errorDetail(body: String): String = try {
        JSONObject(body).getJSONObject("error").optString("message").take(160)
    } catch (_: Exception) {
        body.take(160)
    }

    private fun parse(body: String): JSONObject = try {
        JSONObject(body)
    } catch (e: Exception) {
        throw ApiException("回應格式不正確")
    }
}
