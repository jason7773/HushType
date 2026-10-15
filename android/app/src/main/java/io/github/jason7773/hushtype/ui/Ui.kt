package io.github.jason7773.hushtype.ui

import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.text.InputType
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Switch
import android.widget.TextView

fun Context.dp(v: Number): Int = (v.toFloat() * resources.displayMetrics.density + 0.5f).toInt()
fun Context.dpf(v: Number): Float = v.toFloat() * resources.displayMetrics.density

val MATCH = ViewGroup.LayoutParams.MATCH_PARENT
val WRAP = ViewGroup.LayoutParams.WRAP_CONTENT

fun lp(w: Int = MATCH, h: Int = WRAP, weight: Float = 0f, top: Int = 0, bottom: Int = 0, start: Int = 0, end: Int = 0) =
    LinearLayout.LayoutParams(w, h, weight).apply {
        topMargin = top
        bottomMargin = bottom
        marginStart = start
        marginEnd = end
    }

val MEDIUM: Typeface = Typeface.create(Typeface.DEFAULT, 600, false)
val BOLD: Typeface = Typeface.create(Typeface.DEFAULT, 700, false)

/** 建立玻璃風格元件的小工具。 */
class Ui(val ctx: Context, val pal: Palette) {
    fun dp(v: Number) = ctx.dp(v)

    fun vertical(padding: Int = 0, spacing: Int = 0, block: LinearLayout.() -> Unit = {}): LinearLayout =
        SpacedLinearLayout(ctx, dp(spacing)).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(padding), dp(padding), dp(padding), dp(padding))
            block()
        }

    fun horizontal(spacing: Int = 0, block: LinearLayout.() -> Unit = {}): LinearLayout =
        SpacedLinearLayout(ctx, dp(spacing)).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            block()
        }

    fun card(block: LinearLayout.() -> Unit = {}): LinearLayout = vertical(padding = 18, spacing = 12) {
        background = GlassDrawable(pal, dpf(22), dpf(1))
        block()
    }

    fun dpf(v: Number) = ctx.dpf(v)

    fun text(s: CharSequence, size: Float = 15f, color: Int = pal.text, face: Typeface? = null): TextView =
        TextView(ctx).apply {
            text = s
            setTextSize(TypedValue.COMPLEX_UNIT_SP, size)
            setTextColor(color)
            if (face != null) typeface = face
            setLineSpacing(0f, 1.15f)
        }

    fun heading(s: String) = text(s, 17f, pal.text, MEDIUM)
    fun body(s: CharSequence) = text(s, 14.5f, pal.textSecondary)
    fun muted(s: CharSequence) = text(s, 13f, pal.textMuted)

    fun icon(icon: Icon, color: Int = pal.textSecondary, size: Int = 22): IconView =
        IconView(ctx, icon, color).apply { layoutParams = LinearLayout.LayoutParams(dp(size), dp(size)) }

    private fun ripple(content: android.graphics.drawable.Drawable?, radius: Float): RippleDrawable {
        val mask = GradientDrawable().apply {
            cornerRadius = radius
            setColor(Color.WHITE)
        }
        val rippleColor = if (pal.dark) Color.argb(50, 255, 255, 255) else Color.argb(40, 91, 84, 240)
        return RippleDrawable(ColorStateList.valueOf(rippleColor), content, mask)
    }

    /** 品牌漸層的主要按鈕。 */
    fun primaryButton(label: String, icon: Icon? = null, onClick: (View) -> Unit): View =
        button(label, icon, Color.WHITE, GradientPillDrawable(Palette.BRAND, dpf(14)), onClick)

    fun secondaryButton(label: String, icon: Icon? = null, onClick: (View) -> Unit): View {
        val bg = GradientDrawable().apply {
            cornerRadius = dpf(14)
            setColor(pal.accentSoft)
        }
        return button(label, icon, pal.accent, bg, onClick)
    }

    private fun button(label: String, icon: Icon?, color: Int, bg: android.graphics.drawable.Drawable, onClick: (View) -> Unit): View =
        horizontal(spacing = 8) {
            gravity = Gravity.CENTER
            setPadding(dp(18), dp(11), dp(18), dp(11))
            background = ripple(bg, dpf(14))
            if (icon != null) addView(icon(icon, color, 18))
            addView(text(label, 14.5f, color, MEDIUM))
            isClickable = true
            isFocusable = true
            setOnClickListener(onClick)
        }

    /** 圓形的小圖示按鈕。 */
    fun iconButton(icon: Icon, color: Int = pal.textSecondary, description: String, onClick: (View) -> Unit): View =
        FrameLayout(ctx).apply {
            layoutParams = LinearLayout.LayoutParams(dp(40), dp(40))
            background = ripple(null, dpf(20))
            contentDescription = description
            addView(IconView(ctx, icon, color).apply { setPadding(dp(9), dp(9), dp(9), dp(9)) }, FrameLayout.LayoutParams(MATCH, MATCH))
            isClickable = true
            setOnClickListener(onClick)
        }

    fun chip(label: String, selected: Boolean, onClick: (View) -> Unit): TextView = text(label, 13.5f, if (selected) Color.WHITE else pal.textSecondary, if (selected) MEDIUM else null).apply {
        setPadding(dp(14), dp(8), dp(14), dp(8))
        val bg = if (selected) GradientPillDrawable(Palette.BRAND, dpf(16)) else GradientDrawable().apply {
            cornerRadius = dpf(16)
            setColor(pal.field)
            setStroke(dp(1), pal.fieldBorder)
        }
        background = ripple(bg, dpf(16))
        isClickable = true
        setOnClickListener(onClick)
    }

    /** 分段選擇（例如服務、主題），選中的那段用品牌漸層。 */
    fun segmented(options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit): View {
        val flow = FlowLayout(ctx, dp(8), dp(8))
        for ((id, label) in options) flow.addView(chip(label, id == selected) { onSelect(id) })
        return flow
    }

    fun input(hint: String, value: String = "", password: Boolean = false, multiline: Boolean = false): EditText =
        EditText(ctx).apply {
            this.hint = hint
            setText(value)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 15f)
            setTextColor(pal.text)
            setHintTextColor(pal.textMuted)
            setPadding(dp(14), dp(11), dp(14), dp(11))
            background = GradientDrawable().apply {
                cornerRadius = dpf(12)
                setColor(pal.field)
                setStroke(dp(1), pal.fieldBorder)
            }
            inputType = when {
                password -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
                multiline -> InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_MULTI_LINE
                else -> InputType.TYPE_CLASS_TEXT
            }
            if (!multiline) isSingleLine = true
            if (password) importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO
        }

    fun switchRow(title: String, description: String?, checked: Boolean, onChange: (Boolean) -> Unit): View =
        horizontal(spacing = 12) {
            addView(vertical(spacing = 2) {
                addView(text(title, 15f, pal.text))
                if (description != null) addView(muted(description))
            }, lp(0, WRAP, 1f))
            val sw = Switch(ctx).apply {
                isChecked = checked
                val on = Palette.BRAND[0]
                thumbTintList = ColorStateList(arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()), intArrayOf(on, if (pal.dark) Color.parseColor("#9a9ab3") else Color.WHITE))
                trackTintList = ColorStateList(arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf()), intArrayOf(Color.argb(110, Color.red(on), Color.green(on), Color.blue(on)), if (pal.dark) Color.parseColor("#3a3a55") else Color.parseColor("#c9cbe0")))
                setOnCheckedChangeListener { _, v -> onChange(v) }
            }
            addView(sw)
            setOnClickListener { sw.toggle() }
        }

    fun divider(): View = View(ctx).apply {
        setBackgroundColor(if (pal.dark) Color.argb(28, 255, 255, 255) else Color.argb(30, 21, 21, 43))
        layoutParams = lp(MATCH, maxOf(1, dp(0.7f)))
    }
}

/** 子元件之間自動留間距的 LinearLayout。 */
class SpacedLinearLayout(context: Context, private val spacing: Int) : LinearLayout(context) {
    override fun addView(child: View, index: Int, params: ViewGroup.LayoutParams) {
        val p = if (params is LayoutParams) params else generateLayoutParams(params)
        if (childCount > 0 && spacing > 0) {
            if (orientation == VERTICAL) p.topMargin += spacing else p.marginStart += spacing
        }
        super.addView(child, index, p)
    }

    override fun generateDefaultLayoutParams(): LayoutParams =
        if (orientation == VERTICAL) LayoutParams(MATCH, WRAP) else LayoutParams(WRAP, WRAP)
}

/** 會自動換行的排列（標籤、選項）。 */
class FlowLayout(context: Context, private val hGap: Int, private val vGap: Int) : ViewGroup(context) {
    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val maxW = MeasureSpec.getSize(widthMeasureSpec) - paddingLeft - paddingRight
        var x = 0
        var y = 0
        var rowH = 0
        for (i in 0 until childCount) {
            val c = getChildAt(i)
            if (c.visibility == GONE) continue
            measureChild(c, MeasureSpec.makeMeasureSpec(maxW, MeasureSpec.AT_MOST), MeasureSpec.makeMeasureSpec(0, MeasureSpec.UNSPECIFIED))
            if (x > 0 && x + c.measuredWidth > maxW) {
                x = 0
                y += rowH + vGap
                rowH = 0
            }
            x += c.measuredWidth + hGap
            rowH = maxOf(rowH, c.measuredHeight)
        }
        setMeasuredDimension(MeasureSpec.getSize(widthMeasureSpec), y + rowH + paddingTop + paddingBottom)
    }

    override fun onLayout(changed: Boolean, l: Int, t: Int, r: Int, b: Int) {
        val maxW = r - l - paddingLeft - paddingRight
        var x = 0
        var y = 0
        var rowH = 0
        for (i in 0 until childCount) {
            val c = getChildAt(i)
            if (c.visibility == GONE) continue
            if (x > 0 && x + c.measuredWidth > maxW) {
                x = 0
                y += rowH + vGap
                rowH = 0
            }
            c.layout(paddingLeft + x, paddingTop + y, paddingLeft + x + c.measuredWidth, paddingTop + y + c.measuredHeight)
            x += c.measuredWidth + hGap
            rowH = maxOf(rowH, c.measuredHeight)
        }
    }

    override fun generateDefaultLayoutParams(): LayoutParams = LayoutParams(WRAP, WRAP)
}
