package io.github.jason7773.hushtype.ui

import android.view.View
import android.widget.LinearLayout
import io.github.jason7773.hushtype.data.History
import io.github.jason7773.hushtype.data.HistoryEntry
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

class HistoryPage(activity: MainActivity) : Page(activity) {
    private val listener: () -> Unit = { activity.runOnUiThread { activity.refresh() } }

    init {
        History.addListener(listener)
    }

    override fun onHidden() {
        History.removeListener(listener)
    }

    override fun build(): LinearLayout = column {
        val entries = History.all(activity)
        val retention = when (settings.historyRetention) {
            "1d" -> "保留 1 天"
            "7d" -> "保留 1 週"
            "30d" -> "保留 1 個月"
            "forever" -> "永久保留"
            else -> "只保留到 App 關閉"
        }
        addView(activity.pageTitle("歷史紀錄", "$retention，可以在設定裡更改"))
        if (entries.isEmpty()) {
            addView(ui.card {
                addView(ui.heading("還沒有紀錄"))
                addView(ui.muted("用 Hushtype 鍵盤說話後，結果會出現在這裡，方便你再複製一次。"))
            })
            return@column
        }
        for (e in entries) addView(entryCard(e))
        addView(ui.secondaryButton("全部清除", Icon.TRASH) { History.clear(activity) }, lp(WRAP, WRAP))
    }

    private fun entryCard(e: HistoryEntry): View = ui.card {
        addView(ui.horizontal(spacing = 4) {
            addView(ui.text(formatTime(e.time), 13f, pal.textMuted, MEDIUM), lp(0, WRAP, 1f))
            addView(ui.iconButton(Icon.COPY, pal.textSecondary, "複製") { activity.copy(e.text) })
            addView(ui.iconButton(Icon.TRASH, pal.textMuted, "刪除") { History.delete(activity, e.id) })
        })
        addView(ui.text(e.text, 15.5f, pal.text).apply { setTextIsSelectable(true) })
        val parts = mutableListOf("說了 %.1f 秒".format(e.seconds))
        if (e.sttMs > 0) parts.add("辨識 %.1f 秒".format(e.sttMs / 1000.0))
        if (e.cleanupMs > 0) parts.add("整理 %.1f 秒".format(e.cleanupMs / 1000.0))
        addView(ui.text(parts.joinToString(" · "), 12f, pal.textMuted))
    }

    private fun formatTime(ms: Long): String {
        val cal = Calendar.getInstance().apply { timeInMillis = ms }
        val today = Calendar.getInstance()
        val sameDay = cal.get(Calendar.YEAR) == today.get(Calendar.YEAR) && cal.get(Calendar.DAY_OF_YEAR) == today.get(Calendar.DAY_OF_YEAR)
        val pattern = if (sameDay) "今天 HH:mm" else "M月d日 HH:mm"
        return SimpleDateFormat(pattern, Locale.TAIWAN).format(Date(ms))
    }
}
