package io.github.jason7773.hushtype.data

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import io.github.jason7773.hushtype.core.DictationConfig
import io.github.jason7773.hushtype.core.Provider
import io.github.jason7773.hushtype.core.TextRules
import org.json.JSONArray
import org.json.JSONObject

/** 所有設定。一般設定存在 App 私有空間；API 金鑰用 Keystore 加密後才存。 */
class Settings private constructor(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val secrets: SharedPreferences = context.getSharedPreferences("secrets", Context.MODE_PRIVATE)

    var provider: Provider
        get() = Provider.of(prefs.getString("provider", null))
        set(value) {
            val e = prefs.edit().putString("provider", value.id)
            // 換服務時，原本的型號在新服務上多半不存在，改用新服務的預設值
            if (sttModel !in value.sttModels) e.remove("stt_model")
            if (cleanupModel !in value.cleanupModels) e.remove("cleanup_model")
            e.apply()
        }

    var sttModel: String
        get() = prefs.getString("stt_model", null) ?: provider.sttModels.first()
        set(value) = prefs.edit().putString("stt_model", value.trim()).apply()

    var cleanupModel: String
        get() = prefs.getString("cleanup_model", null) ?: provider.cleanupModels.first()
        set(value) = prefs.edit().putString("cleanup_model", value.trim()).apply()

    var cleanupEnabled by bool("cleanup_enabled", true)
    var toTraditional by bool("to_traditional", true)
    var haptics by bool("haptics", true)
    var switchBack by bool("switch_back", false) // 輸入後自動切回原本的鍵盤
    var animations by bool("animations", true)
    var language: String
        get() = prefs.getString("language", "") ?: "" // 留空：中英自動偵測
        set(value) = prefs.edit().putString("language", value).apply()

    /** system、light、dark */
    var theme: String
        get() = prefs.getString("theme", "system") ?: "system"
        set(value) = prefs.edit().putString("theme", value).apply()

    /** 歷史紀錄保留多久：session（只在記憶體）、1d、7d、30d、forever */
    var historyRetention: String
        get() = prefs.getString("history_retention", "session") ?: "session"
        set(value) = prefs.edit().putString("history_retention", value).apply()

    var typingCpm: Int
        get() = prefs.getInt("typing_cpm", 40)
        set(value) = prefs.edit().putInt("typing_cpm", value).apply()

    var terms: List<String>
        get() {
            val arr = JSONArray(prefs.getString("terms", "[]"))
            return (0 until arr.length()).map { arr.getString(it) }
        }
        set(value) = prefs.edit().putString("terms", JSONArray(value).toString()).apply()

    /** 固定替換，保留加入的順序。 */
    var replacements: Map<String, String>
        get() {
            val obj = JSONObject(prefs.getString("replacements", "{}") ?: "{}")
            val out = LinkedHashMap<String, String>()
            obj.keys().forEach { out[it] = obj.getString(it) }
            return out
        }
        set(value) = prefs.edit().putString("replacements", JSONObject(value as Map<*, *>).toString()).apply()

    fun apiKey(p: Provider = provider): String {
        val stored = secrets.getString("key_${p.id}", null) ?: return ""
        val plain = Crypto.decrypt(KEY_ALIAS, Base64.decode(stored, Base64.NO_WRAP)) ?: return ""
        return String(plain, Charsets.UTF_8)
    }

    fun setApiKey(p: Provider, key: String) {
        val e = secrets.edit()
        if (key.isBlank()) {
            e.remove("key_${p.id}")
        } else {
            val enc = Crypto.encrypt(KEY_ALIAS, key.trim().toByteArray(Charsets.UTF_8))
            e.putString("key_${p.id}", Base64.encodeToString(enc, Base64.NO_WRAP))
        }
        e.apply()
    }

    fun hasApiKey(p: Provider = provider): Boolean = secrets.contains("key_${p.id}")

    fun dictationConfig(): DictationConfig = DictationConfig(
        provider = provider,
        apiKey = apiKey(),
        sttModel = sttModel,
        language = language,
        cleanupEnabled = cleanupEnabled,
        cleanupModel = cleanupModel,
        cleanupPrompt = TextRules.DEFAULT_CLEANUP_PROMPT,
        terms = terms,
        replacements = replacements,
        toTraditional = toTraditional,
    )

    private fun bool(key: String, default: Boolean) = object : kotlin.properties.ReadWriteProperty<Any?, Boolean> {
        override fun getValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>) = prefs.getBoolean(key, default)
        override fun setValue(thisRef: Any?, property: kotlin.reflect.KProperty<*>, value: Boolean) {
            prefs.edit().putBoolean(key, value).apply()
        }
    }

    companion object {
        private const val KEY_ALIAS = "hushtype_api_keys"

        @Volatile private var instance: Settings? = null

        fun get(context: Context): Settings =
            instance ?: synchronized(this) {
                instance ?: Settings(context.applicationContext).also { instance = it }
            }
    }
}
