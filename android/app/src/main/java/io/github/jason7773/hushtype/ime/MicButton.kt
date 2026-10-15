package io.github.jason7773.hushtype.ime

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.RectF
import android.graphics.Shader
import android.view.View
import android.view.animation.LinearInterpolator
import io.github.jason7773.hushtype.ui.Icon
import io.github.jason7773.hushtype.ui.Icons
import io.github.jason7773.hushtype.ui.Palette
import kotlin.math.min
import kotlin.math.sin

enum class MicState { IDLE, RECORDING, PROCESSING }

/**
 * 鍵盤中間的大麥克風按鈕。待命時是品牌漸層；錄音時變紅，裡面五條音波跟著聲音跳動；
 * 處理時變琥珀色並顯示轉圈。
 */
class MicButton(context: Context) : View(context) {
    var state = MicState.IDLE
        set(value) {
            field = value
            updateAnimation()
            invalidate()
        }

    /** 0–1，由錄音器提供。 */
    var level = 0f

    private val fill = Paint(Paint.ANTI_ALIAS_FLAG)
    private val glow = Paint(Paint.ANTI_ALIAS_FLAG)
    private val white = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
    private val arc = Icons.strokePaint(Color.WHITE, 1f)
    private val iconPaint = Icons.strokePaint(Color.WHITE, 1.9f)
    private val bars = FloatArray(5)
    private var phase = 0f
    private var smooth = 0f
    private var animator: ValueAnimator? = null

    private fun updateAnimation() {
        val run = state != MicState.IDLE && isAttachedToWindow
        if (run && animator == null) {
            animator = ValueAnimator.ofFloat(0f, 1f).apply {
                duration = 1000
                repeatCount = ValueAnimator.INFINITE
                interpolator = LinearInterpolator()
                addUpdateListener {
                    phase += 0.06f
                    invalidate()
                }
                start()
            }
        } else if (!run) {
            animator?.cancel()
            animator = null
            smooth = 0f
        }
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

    override fun onDraw(canvas: Canvas) {
        val cx = width / 2f
        val cy = height / 2f
        val maxR = min(width, height) / 2f
        val r = maxR * 0.74f
        val colors = when (state) {
            MicState.IDLE -> Palette.BRAND
            MicState.RECORDING -> intArrayOf(Color.parseColor("#ff5f87"), Color.parseColor("#ff8a5c"))
            MicState.PROCESSING -> intArrayOf(Color.parseColor("#ffb020"), Color.parseColor("#ff7a59"))
        }
        smooth += (level - smooth) * 0.35f

        // 外圈光暈：錄音時跟著音量放大
        val glowR = if (state == MicState.RECORDING) r * (1.08f + 0.27f * smooth) else r * 1.12f
        val glowColor = colors[0]
        glow.shader = RadialGradient(
            cx, cy, maxOf(glowR, 1f),
            intArrayOf(Color.argb(110, Color.red(glowColor), Color.green(glowColor), Color.blue(glowColor)), Color.TRANSPARENT),
            floatArrayOf(0.7f, 1f), Shader.TileMode.CLAMP,
        )
        canvas.drawCircle(cx, cy, glowR, glow)

        fill.shader = LinearGradient(cx - r, cy - r, cx + r, cy + r, colors[0], colors[1], Shader.TileMode.CLAMP)
        canvas.drawCircle(cx, cy, r, fill)

        when (state) {
            MicState.IDLE -> {
                val s = r * 0.95f
                Icons.draw(canvas, Icon.MIC, cx - s / 2, cy - s / 2, s, iconPaint)
            }
            MicState.RECORDING -> {
                val bw = r * 0.13f
                val gap = r * 0.09f
                val total = bw * 5 + gap * 4
                for (i in 0 until 5) {
                    val wave = 0.55f + 0.45f * sin(phase * 2.2f + i * 1.3f)
                    val shape = floatArrayOf(0.55f, 0.8f, 1f, 0.8f, 0.55f)[i]
                    val target = 0.18f + 0.82f * min(1f, smooth * 2.2f) * wave * shape
                    bars[i] += (target - bars[i]) * 0.4f
                    val h = r * 1.0f * bars[i].coerceIn(0.16f, 1f)
                    val x = cx - total / 2 + i * (bw + gap)
                    canvas.drawRoundRect(RectF(x, cy - h / 2, x + bw, cy + h / 2), bw / 2, bw / 2, white)
                }
            }
            MicState.PROCESSING -> {
                arc.strokeWidth = r * 0.1f
                val a = r * 0.42f
                canvas.drawArc(RectF(cx - a, cy - a, cx + a, cy + a), phase * 300f % 360f, 260f, false, arc)
            }
        }
    }
}
