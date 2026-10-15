package io.github.jason7773.hushtype.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.time.LocalDate

/** 每天的使用量：次數、說話秒數、輸出字數。只存數字，從不存語音或文字內容。 */
class DayStats(var count: Int = 0, var seconds: Double = 0.0, var chars: Int = 0)

class StatsSummary(
    val chars: Int,
    val seconds: Double,
    val count: Int,
    val savedMinutes: Double,
    val charsPerMinute: Double,
    val streak: Int,
    val days: Map<LocalDate, DayStats>,
)

object Stats {
    private fun prefs(context: Context) = context.getSharedPreferences("stats", Context.MODE_PRIVATE)

    @Synchronized
    fun load(context: Context): MutableMap<LocalDate, DayStats> {
        val obj = JSONObject(prefs(context).getString("days", "{}") ?: "{}")
        val out = HashMap<LocalDate, DayStats>()
        obj.keys().forEach { k ->
            val a = obj.getJSONArray(k)
            out[LocalDate.parse(k)] = DayStats(a.getInt(0), a.getDouble(1), a.getInt(2))
        }
        return out
    }

    @Synchronized
    fun record(context: Context, seconds: Double, chars: Int) {
        val days = load(context)
        val d = days.getOrPut(LocalDate.now()) { DayStats() }
        d.count += 1
        d.seconds += seconds
        d.chars += chars
        val obj = JSONObject()
        for ((k, v) in days) obj.put(k.toString(), JSONArray().put(v.count).put(v.seconds).put(v.chars))
        prefs(context).edit().putString("days", obj.toString()).apply()
    }

    fun clear(context: Context) = prefs(context).edit().clear().apply()

    fun summary(context: Context): StatsSummary {
        val days = load(context)
        val chars = days.values.sumOf { it.chars }
        val seconds = days.values.sumOf { it.seconds }
        val count = days.values.sumOf { it.count }
        val cpm = Settings.get(context).typingCpm.coerceAtLeast(1)
        val saved = (chars.toDouble() / cpm - seconds / 60).coerceAtLeast(0.0)
        val speed = if (seconds > 0) chars / (seconds / 60) else 0.0
        // 連續天數：今天還沒用也不算中斷，從昨天往回數
        var day = LocalDate.now()
        if ((days[day]?.count ?: 0) == 0) day = day.minusDays(1)
        var streak = 0
        while ((days[day]?.count ?: 0) > 0) {
            streak++
            day = day.minusDays(1)
        }
        return StatsSummary(chars, seconds, count, saved, speed, streak, days)
    }
}
