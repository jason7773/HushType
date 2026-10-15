package io.github.jason7773.hushtype.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import android.provider.Settings as SystemSettings
import android.view.Gravity
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import io.github.jason7773.hushtype.data.DayStats
import io.github.jason7773.hushtype.data.Stats
import io.github.jason7773.hushtype.ime.HushtypeIme
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.temporal.TemporalAdjusters
import kotlin.math.roundToInt

class HomePage(activity: MainActivity) : Page(activity) {
    private val imm get() = activity.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager
    private var lastSetup: List<Boolean>? = null

    private fun imeEnabled(): Boolean =
        imm.enabledInputMethodList.any { it.packageName == activity.packageName }

    private fun imeSelected(): Boolean {
        val id = SystemSettings.Secure.getString(activity.contentResolver, SystemSettings.Secure.DEFAULT_INPUT_METHOD) ?: return false
        return id.startsWith(activity.packageName + "/") && id.endsWith(HushtypeIme::class.java.simpleName)
    }

    private fun micAllowed() = activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

    private fun setupState() = listOf(imeEnabled(), micAllowed(), settings.hasApiKey())

    override fun onResume() {
        if (setupState() != lastSetup) activity.refresh()
    }

    override fun build(): LinearLayout = column {
        lastSetup = setupState()
        addView(hero())
        val (enabled, mic, key) = lastSetup!!
        if (!(enabled && mic && key)) addView(setupCard(enabled, mic, key))
        addView(tryCard())
        addView(insights())
        addView(privacyCard())
    }

    private fun hero(): View = ui.card {
        addView(ui.horizontal(spacing = 14) {
            addView(LogoView(context), LinearLayout.LayoutParams(dp(56), dp(56)))
            addView(ui.vertical(spacing = 2) {
                addView(ui.text("說話，就是打字", 21f, pal.text, BOLD))
                addView(ui.muted("重視隱私的語音輸入鍵盤"))
            }, lp(0, WRAP, 1f))
        })
        addView(ui.body("在任何 App 切換到 Hushtype 鍵盤，按一下麥克風開始說話，再按一下就會輸入去掉贅字、加好標點的文字。"))
    }

    private fun setupCard(enabled: Boolean, mic: Boolean, key: Boolean): View = ui.card {
        addView(ui.heading("開始使用"))
        addView(step(1, "啟用 Hushtype 鍵盤", "在系統的鍵盤清單裡打開 Hushtype。系統會提醒鍵盤可以讀取輸入的文字，這是所有鍵盤都會出現的標準警告。", enabled, "前往啟用") {
            activity.startActivity(Intent(SystemSettings.ACTION_INPUT_METHOD_SETTINGS))
        })
        addView(ui.divider())
        addView(step(2, "允許使用麥克風", "只有在你按下麥克風時才會錄音，錄音只放在記憶體。", mic, "允許") { activity.requestMic() })
        addView(ui.divider())
        addView(step(3, "填入 API 金鑰", "選擇語音服務並貼上你自己申請的金鑰，金鑰會加密存在手機裡。", key, "前往設定") {
            activity.showTab(MainActivity.Tab.SETTINGS)
        })
    }

    private fun step(n: Int, title: String, desc: String, done: Boolean, action: String, onClick: () -> Unit): View =
        ui.horizontal(spacing = 12) {
            gravity = Gravity.TOP
            val badge = FrameLayout(context).apply {
                background = if (done) GradientPillDrawable(intArrayOf(pal.good, pal.good), dpf(14)) else GradientPillDrawable(Palette.BRAND, dpf(14))
                if (done) {
                    addView(IconView(context, Icon.CHECK, Color.WHITE, 2.4f).apply { setPadding(dp(6), dp(6), dp(6), dp(6)) }, FrameLayout.LayoutParams(MATCH, MATCH))
                } else {
                    addView(ui.text(n.toString(), 13f, Color.WHITE, BOLD).apply { gravity = Gravity.CENTER }, FrameLayout.LayoutParams(MATCH, MATCH))
                }
            }
            addView(badge, LinearLayout.LayoutParams(dp(28), dp(28)))
            addView(ui.vertical(spacing = 6) {
                addView(ui.text(title, 15.5f, pal.text, MEDIUM))
                addView(ui.muted(desc))
                if (!done) addView(ui.secondaryButton(action, Icon.ARROW) { onClick() }, lp(WRAP, WRAP, top = ui.dp(2)))
            }, lp(0, WRAP, 1f))
        }

    private fun tryCard(): View = ui.card {
        addView(ui.heading("試試看"))
        addView(ui.muted(if (imeSelected()) "點下面的輸入框，按麥克風說一句話。" else "點下面的輸入框，再點右下角的鍵盤圖示切換到 Hushtype，按麥克風說一句話。"))
        val field = ui.input("在這裡說說看…", multiline = true).apply { minLines = 3; gravity = Gravity.TOP }
        addView(field)
        addView(ui.horizontal(spacing = 10) {
            addView(ui.secondaryButton("切換鍵盤", Icon.KEYBOARD) {
                field.requestFocus()
                imm.showInputMethodPicker()
            })
            addView(ui.secondaryButton("清除", Icon.TRASH) { field.setText("") })
        })
    }

    private fun insights(): View = ui.card {
        val s = Stats.summary(activity)
        addView(ui.heading("使用洞察"))
        val tiles = listOf(
            Triple("口述字數", formatCount(s.chars), "共 ${s.count} 次"),
            Triple("節省時間", formatMinutes(s.savedMinutes), "以每分鐘打 ${settings.typingCpm} 字估算"),
            Triple("口述速度", if (s.charsPerMinute > 0) "${s.charsPerMinute.roundToInt()}" else "–", "字／分鐘"),
            Triple("連續天數", "${s.streak}", if (s.streak > 0) "天，繼續保持" else "天"),
        )
        for (row in tiles.chunked(2)) {
            addView(ui.horizontal(spacing = 10) {
                for ((label, value, sub) in row) addView(tile(label, value, sub), lp(0, WRAP, 1f))
            })
        }
        addView(ui.text("最近 18 週", 13f, pal.textMuted, MEDIUM), lp(top = ui.dp(4)))
        addView(ActivityCalendar(context, pal, s.days), lp(MATCH, ui.dp(7 * 15)))
    }

    private fun tile(label: String, value: String, sub: String): View = ui.vertical(spacing = 2) {
        setPadding(dp(14), dp(12), dp(14), dp(12))
        background = android.graphics.drawable.GradientDrawable().apply {
            cornerRadius = dpf(16)
            setColor(pal.field)
            setStroke(dp(1), pal.fieldBorder)
        }
        addView(ui.muted(label))
        addView(ui.text(value, 24f, pal.text, BOLD))
        addView(ui.text(sub, 12f, pal.textMuted))
    }

    private fun privacyCard(): View = ui.card {
        addView(ui.horizontal(spacing = 10) {
            addView(ui.icon(Icon.SHIELD, pal.accent, 22))
            addView(ui.heading("你的聲音只去你選的地方"))
        })
        addView(ui.body("錄音只放在記憶體，辨識完就丟掉；文字只送到你在設定裡選的服務。Hushtype 沒有自己的伺服器，不收集任何資料，使用統計只記數字、不記內容。"))
    }

    private fun formatCount(n: Int): String = if (n >= 10_000) "%.1f 萬".format(n / 10_000.0) else "%,d".format(n)

    private fun formatMinutes(m: Double): String = when {
        m < 1 -> "${(m * 60).roundToInt()} 秒"
        m < 60 -> "${m.roundToInt()} 分"
        else -> "%.1f 時".format(m / 60)
    }
}

/** 像 GitHub 一樣的活躍日曆：每格一天，顏色越深說得越多。 */
class ActivityCalendar(context: Context, private val pal: Palette, private val days: Map<LocalDate, DayStats>) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val weeks = 18

    override fun onDraw(canvas: Canvas) {
        val gap = resources.displayMetrics.density * 3
        val cell = minOf((width - gap * (weeks - 1)) / weeks, (height - gap * 6) / 7)
        val totalW = cell * weeks + gap * (weeks - 1)
        val left = (width - totalW) / 2
        val today = LocalDate.now()
        val start = today.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)).minusWeeks((weeks - 1).toLong())
        val max = days.values.maxOfOrNull { it.chars }?.coerceAtLeast(1) ?: 1
        val empty = if (pal.dark) Color.argb(26, 255, 255, 255) else Color.argb(22, 21, 21, 43)
        for (w in 0 until weeks) for (d in 0 until 7) {
            val date = start.plusDays((w * 7 + d).toLong())
            if (date.isAfter(today)) continue
            val chars = days[date]?.chars ?: 0
            paint.color = if (chars == 0) empty else {
                val t = 0.3f + 0.7f * (chars.toFloat() / max)
                Color.argb((t * 255).toInt(), Color.red(pal.accent), Color.green(pal.accent), Color.blue(pal.accent))
            }
            val x = left + w * (cell + gap)
            val y = d * (cell + gap)
            canvas.drawRoundRect(RectF(x, y, x + cell, y + cell), cell * 0.28f, cell * 0.28f, paint)
        }
    }
}
