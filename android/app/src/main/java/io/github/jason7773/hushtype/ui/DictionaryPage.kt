package io.github.jason7773.hushtype.ui

import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.LinearLayout

class DictionaryPage(activity: MainActivity) : Page(activity) {
    override fun build(): LinearLayout = column {
        addView(activity.pageTitle("字典", "讓辨識寫對你常用的人名、術語和英文"))
        addView(termsCard())
        addView(replacementsCard())
    }

    private fun termsCard(): View = ui.card {
        addView(ui.heading("專有名詞"))
        addView(ui.muted("會提示給辨識和整理模型，例如人名、公司名、產品名。"))
        val field = ui.input("新增詞彙，例如 Hushtype")
        fun add() {
            val words = field.text.toString().split(',', '，', '、').map { it.trim() }.filter { it.isNotEmpty() }
            if (words.isEmpty()) return
            val terms = settings.terms.toMutableList()
            for (w in words) if (terms.none { it.equals(w, ignoreCase = true) }) terms.add(w)
            settings.terms = terms
            activity.refresh()
        }
        field.imeOptions = EditorInfo.IME_ACTION_DONE
        field.setOnEditorActionListener { _, _, _ ->
            add()
            true
        }
        addView(ui.horizontal(spacing = 8) {
            addView(field, lp(0, WRAP, 1f))
            addView(ui.primaryButton("加入", Icon.PLUS) { add() })
        })
        val terms = settings.terms
        if (terms.isEmpty()) {
            addView(ui.muted("還沒有詞彙。"))
        } else {
            val flow = FlowLayout(context, dp(8), dp(8))
            for (t in terms) flow.addView(removableChip(t) {
                settings.terms = settings.terms.filter { it != t }
                activity.refresh()
            })
            addView(flow)
        }
    }

    private fun removableChip(label: String, onRemove: () -> Unit): View = ui.horizontal(spacing = 4) {
        setPadding(dp(14), dp(7), dp(8), dp(7))
        background = android.graphics.drawable.GradientDrawable().apply {
            cornerRadius = dpf(16)
            setColor(pal.accentSoft)
        }
        addView(ui.text(label, 14f, pal.accent, MEDIUM))
        addView(IconView(context, Icon.CLOSE, pal.accent), LinearLayout.LayoutParams(dp(18), dp(18)))
        contentDescription = "刪除 $label"
        isClickable = true
        setOnClickListener { onRemove() }
    }

    private fun replacementsCard(): View = ui.card {
        addView(ui.heading("固定替換"))
        addView(ui.muted("辨識老是聽錯的詞，直接換成正確寫法，例如「拍森」換成「Python」。"))
        val from = ui.input("聽成")
        val to = ui.input("改成")
        addView(ui.horizontal(spacing = 8) {
            addView(from, lp(0, WRAP, 1f))
            addView(ui.icon(Icon.ARROW, pal.textMuted, 20))
            addView(to, lp(0, WRAP, 1f))
        })
        addView(ui.primaryButton("加入替換", Icon.PLUS) {
            val a = from.text.toString().trim()
            val b = to.text.toString().trim()
            if (a.isEmpty()) {
                activity.toast("請填入「聽成」的詞")
                return@primaryButton
            }
            settings.replacements = LinkedHashMap(settings.replacements).apply { put(a, b) }
            activity.refresh()
        }, lp(WRAP, WRAP))
        val map = settings.replacements
        if (map.isEmpty()) {
            addView(ui.muted("還沒有替換規則。"))
        } else {
            for ((a, b) in map) {
                addView(ui.divider())
                addView(ui.horizontal(spacing = 10) {
                    addView(ui.text(a, 15f, pal.textSecondary))
                    addView(ui.icon(Icon.ARROW, pal.textMuted, 16))
                    addView(ui.text(b.ifEmpty { "（刪除）" }, 15f, pal.text, MEDIUM), lp(0, WRAP, 1f))
                    addView(ui.iconButton(Icon.TRASH, pal.textMuted, "刪除") {
                        settings.replacements = LinkedHashMap(settings.replacements).apply { remove(a) }
                        activity.refresh()
                    })
                })
            }
        }
    }
}
