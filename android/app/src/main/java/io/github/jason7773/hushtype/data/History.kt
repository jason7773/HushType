package io.github.jason7773.hushtype.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class HistoryEntry(
    val id: Long,
    val time: Long,
    val text: String,
    val seconds: Double,
    val sttMs: Long,
    val cleanupMs: Long,
)

/**
 * 辨識結果的歷史紀錄。預設只放在記憶體（App 被系統關掉就清除）；
 * 選擇保留更久時，整份紀錄用 Keystore 加密後存在 App 私有空間。
 */
object History {
    private const val KEY_ALIAS = "hushtype_history"
    private val entries = ArrayList<HistoryEntry>()
    private var loaded = false
    private val listeners = LinkedHashSet<() -> Unit>()

    private fun file(context: Context) = File(context.filesDir, "history.bin")

    private fun retentionMs(retention: String): Long? = when (retention) {
        "1d" -> 86_400_000L
        "7d" -> 7 * 86_400_000L
        "30d" -> 30 * 86_400_000L
        "forever" -> Long.MAX_VALUE
        else -> null // session
    }

    @Synchronized
    fun all(context: Context): List<HistoryEntry> {
        ensureLoaded(context)
        prune(context)
        return entries.sortedByDescending { it.time }
    }

    @Synchronized
    fun latest(context: Context): HistoryEntry? = all(context).firstOrNull()

    @Synchronized
    fun add(context: Context, entry: HistoryEntry) {
        ensureLoaded(context)
        entries.add(entry)
        save(context)
        notifyChanged()
    }

    @Synchronized
    fun delete(context: Context, id: Long) {
        entries.removeAll { it.id == id }
        save(context)
        notifyChanged()
    }

    @Synchronized
    fun clear(context: Context) {
        entries.clear()
        save(context)
        notifyChanged()
    }

    /** 保留期限改變時呼叫：改成只在記憶體時刪掉檔案；改成保留時把目前的紀錄寫入。 */
    @Synchronized
    fun retentionChanged(context: Context) {
        prune(context)
        save(context)
        notifyChanged()
    }

    fun addListener(l: () -> Unit) = synchronized(listeners) { listeners.add(l) }
    fun removeListener(l: () -> Unit) = synchronized(listeners) { listeners.remove(l) }

    private fun notifyChanged() {
        val copy = synchronized(listeners) { listeners.toList() }
        copy.forEach { it() }
    }

    private fun ensureLoaded(context: Context) {
        if (loaded) return
        loaded = true
        val f = file(context)
        if (retentionMs(Settings.get(context).historyRetention) == null) {
            f.delete()
            return
        }
        if (!f.exists()) return
        val plain = Crypto.decrypt(KEY_ALIAS, f.readBytes()) ?: return
        val arr = JSONArray(String(plain, Charsets.UTF_8))
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            entries.add(
                HistoryEntry(
                    o.getLong("id"), o.getLong("time"), o.getString("text"),
                    o.optDouble("seconds", 0.0), o.optLong("stt_ms"), o.optLong("cleanup_ms"),
                ),
            )
        }
    }

    private fun prune(context: Context) {
        val keep = retentionMs(Settings.get(context).historyRetention) ?: return
        if (keep == Long.MAX_VALUE) return
        val cutoff = System.currentTimeMillis() - keep
        entries.removeAll { it.time < cutoff }
    }

    private fun save(context: Context) {
        val f = file(context)
        if (retentionMs(Settings.get(context).historyRetention) == null || entries.isEmpty()) {
            f.delete()
            return
        }
        val arr = JSONArray()
        for (e in entries) {
            arr.put(
                JSONObject().put("id", e.id).put("time", e.time).put("text", e.text)
                    .put("seconds", e.seconds).put("stt_ms", e.sttMs).put("cleanup_ms", e.cleanupMs),
            )
        }
        val tmp = File(f.path + ".tmp")
        tmp.writeBytes(Crypto.encrypt(KEY_ALIAS, arr.toString().toByteArray(Charsets.UTF_8)))
        tmp.renameTo(f)
    }
}
