package io.github.jason7773.hushtype.ui

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorFilter
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.RadialGradient
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.drawable.Drawable
import android.view.View
import android.view.animation.LinearInterpolator
import kotlin.math.cos
import kotlin.math.max
import kotlin.math.sin

/** 半透明玻璃卡片：上亮下暗的填色，加上一圈由亮到淡的漸層邊框。 */
class GlassDrawable(
    private val pal: Palette,
    private val radius: Float,
    private val borderWidth: Float,
    private val fillOverride: IntArray? = null,
) : Drawable() {
    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val border = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = borderWidth
    }
    private val rect = RectF()

    override fun onBoundsChange(bounds: Rect) {
        rect.set(bounds)
        rect.inset(borderWidth / 2, borderWidth / 2)
        val colors = fillOverride ?: intArrayOf(pal.glassTop, pal.glassBottom)
        fill.shader = if (colors.size == 1) null else
            LinearGradient(0f, rect.top, rect.width() * 0.3f, rect.bottom, colors[0], colors[1], Shader.TileMode.CLAMP)
        if (colors.size == 1) fill.color = colors[0]
        border.shader = LinearGradient(
            rect.left, rect.top, rect.right, rect.bottom,
            pal.glassBorderStart, pal.glassBorderEnd, Shader.TileMode.CLAMP,
        )
    }

    override fun draw(canvas: Canvas) {
        canvas.drawRoundRect(rect, radius, radius, fill)
        if (borderWidth > 0) canvas.drawRoundRect(rect, radius, radius, border)
    }

    override fun setAlpha(alpha: Int) {
        fill.alpha = alpha
        border.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        fill.colorFilter = colorFilter
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity() = PixelFormat.TRANSLUCENT
}

/** 品牌漸層的圓角形狀（主要按鈕、Logo 底色）。 */
class GradientPillDrawable(private val colors: IntArray, private val radius: Float) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rect = RectF()

    override fun onBoundsChange(bounds: Rect) {
        rect.set(bounds)
        paint.shader = LinearGradient(rect.left, rect.top, rect.right, rect.bottom, colors[0], colors[1], Shader.TileMode.CLAMP)
    }

    override fun draw(canvas: Canvas) = canvas.drawRoundRect(rect, radius, radius, paint)
    override fun setAlpha(alpha: Int) {
        paint.alpha = alpha
    }

    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
    }

    @Deprecated("Deprecated in Java")
    override fun getOpacity() = PixelFormat.TRANSLUCENT
}

/**
 * 流動的極光背景：幾團柔和的色光緩慢飄移。錄音時變紅、處理時變琥珀色。
 * 只在畫面看得到、而且使用者沒有關掉動態效果時才會動。
 */
class AuroraView(context: Context, private var pal: Palette) : View(context) {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private var colors: IntArray = pal.aurora
    private var phase = 0f
    private var animator: ValueAnimator? = null
    var animate = true
        set(value) {
            field = value
            updateAnimation()
        }

    fun setColors(c: IntArray?) {
        colors = c ?: pal.aurora
        invalidate()
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        updateAnimation()
    }

    override fun onDetachedFromWindow() {
        animator?.cancel()
        animator = null
        super.onDetachedFromWindow()
    }

    override fun onWindowVisibilityChanged(visibility: Int) {
        super.onWindowVisibilityChanged(visibility)
        updateAnimation()
    }

    private fun updateAnimation() {
        val run = animate && isAttachedToWindow && windowVisibility == VISIBLE
        if (run && animator == null) {
            animator = ValueAnimator.ofFloat(0f, (Math.PI * 2).toFloat()).apply {
                duration = 24_000
                repeatCount = ValueAnimator.INFINITE
                interpolator = LinearInterpolator()
                addUpdateListener {
                    phase = it.animatedValue as Float
                    invalidate()
                }
                start()
            }
        } else if (!run) {
            animator?.cancel()
            animator = null
        }
    }

    override fun onDraw(canvas: Canvas) {
        canvas.drawColor(pal.bg)
        val w = width.toFloat()
        val h = height.toFloat()
        val r = max(w, h) * 0.62f
        // 每團光的基準位置與飄移幅度
        val spots = arrayOf(
            floatArrayOf(0.15f, 0.12f, 0.10f, 0.06f),
            floatArrayOf(0.90f, 0.30f, 0.08f, 0.10f),
            floatArrayOf(0.25f, 0.85f, 0.12f, 0.05f),
            floatArrayOf(0.85f, 0.95f, 0.06f, 0.08f),
        )
        val alpha = if (pal.dark) 0.55f else 0.50f
        for (i in spots.indices) {
            val s = spots[i]
            val p = phase + i * 1.7f
            val cx = (s[0] + s[2] * sin(p)) * w
            val cy = (s[1] + s[3] * cos(p * 0.8f)) * h
            val color = colors[i % colors.size]
            val center = Color.argb((alpha * 255).toInt(), Color.red(color), Color.green(color), Color.blue(color))
            paint.shader = RadialGradient(cx, cy, r * (0.75f + 0.1f * i), center, Color.TRANSPARENT, Shader.TileMode.CLAMP)
            canvas.drawRect(0f, 0f, w, h, paint)
        }
    }
}
