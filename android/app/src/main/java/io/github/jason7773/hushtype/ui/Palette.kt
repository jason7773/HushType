package io.github.jason7773.hushtype.ui

import android.content.Context
import android.content.res.Configuration
import android.graphics.Color
import io.github.jason7773.hushtype.data.Settings

/** 配色，與桌面版的淺色／深色主題一致。 */
class Palette(
    val dark: Boolean,
    val bg: Int,
    val text: Int,
    val textSecondary: Int,
    val textMuted: Int,
    val accent: Int,
    val accentSoft: Int,
    val good: Int,
    val bad: Int,
    val warn: Int,
    val glassTop: Int,
    val glassBottom: Int,
    val glassBorderStart: Int,
    val glassBorderEnd: Int,
    val field: Int,
    val fieldBorder: Int,
    val aurora: IntArray,
) {
    companion object {
        val BRAND = intArrayOf(Color.parseColor("#6d5dfc"), Color.parseColor("#2f80ed"))
        val RECORDING = Color.parseColor("#f0476a")
        val PROCESSING = Color.parseColor("#f2a516")
        val AURORA_RECORDING = colors("#ff5f87", "#ff8a5c", "#c04dff", "#ffb36b")
        val AURORA_PROCESSING = colors("#ffb020", "#ff7a59", "#8f7dff", "#5fe3d2")

        private fun colors(vararg hex: String) = IntArray(hex.size) { Color.parseColor(hex[it]) }
        private fun c(hex: String) = Color.parseColor(hex)

        val LIGHT = Palette(
            dark = false,
            bg = c("#eef0f9"),
            text = c("#15152b"),
            textSecondary = c("#4a4a66"),
            textMuted = c("#7d7d99"),
            accent = c("#5b54f0"),
            accentSoft = c("#e7e6ff"),
            good = c("#0f8a4a"),
            bad = c("#d23c4f"),
            warn = c("#a35f00"),
            glassTop = c("#b8ffffff"),
            glassBottom = c("#8cffffff"),
            glassBorderStart = c("#f2ffffff"),
            glassBorderEnd = c("#405b54f0"),
            field = c("#99ffffff"),
            fieldBorder = c("#d9dcec"),
            aurora = colors("#8f7dff", "#4fa8ff", "#ff9bd2", "#5fe3d2"),
        )

        val DARK = Palette(
            dark = true,
            bg = c("#0b0b16"),
            text = c("#f3f3fb"),
            textSecondary = c("#babad2"),
            textMuted = c("#85859f"),
            accent = c("#8b84ff"),
            accentSoft = c("#25234a"),
            good = c("#4fd68a"),
            bad = c("#ff7d8c"),
            warn = c("#f0b85a"),
            glassTop = c("#a6222238"),
            glassBottom = c("#8c17172a"),
            glassBorderStart = c("#40ffffff"),
            glassBorderEnd = c("#148b84ff"),
            field = c("#660b0b16"),
            fieldBorder = c("#2c2c46"),
            aurora = colors("#6d5dfc", "#2f80ed", "#c04dff", "#14b8a6"),
        )

        fun of(context: Context): Palette {
            val dark = when (Settings.get(context).theme) {
                "light" -> false
                "dark" -> true
                else -> (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK) ==
                    Configuration.UI_MODE_NIGHT_YES
            }
            return if (dark) DARK else LIGHT
        }
    }
}
