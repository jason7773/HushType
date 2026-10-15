package io.github.jason7773.hushtype.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.view.View

/** 線條風格的小圖示（取代 emoji），在 24×24 的格子上畫，跟著主題換色。 */
enum class Icon { MIC, KEYBOARD, BACKSPACE, ENTER, SLIDERS, HOME, BOOK, CLOCK, COPY, TRASH, CHECK, CLOSE, RETRY, UNDO, SPACE, KEY, SHIELD, CHEVRON, PLUS, ARROW }

object Icons {
    fun draw(canvas: Canvas, icon: Icon, left: Float, top: Float, size: Float, paint: Paint) {
        val s = size / 24f
        canvas.save()
        canvas.translate(left, top)
        canvas.scale(s, s)
        val p = Path()
        fun line(vararg pts: Float) {
            p.moveTo(pts[0], pts[1])
            var i = 2
            while (i < pts.size) {
                p.lineTo(pts[i], pts[i + 1])
                i += 2
            }
        }
        fun dot(x: Float, y: Float) {
            p.moveTo(x, y)
            p.lineTo(x + 0.01f, y)
        }
        when (icon) {
            Icon.MIC -> {
                p.addRoundRect(RectF(9f, 3f, 15f, 14f), 3f, 3f, Path.Direction.CW)
                p.moveTo(5.5f, 11f)
                p.arcTo(RectF(5.5f, 4.5f, 18.5f, 17.5f), 180f, -180f)
                line(12f, 17.5f, 12f, 21f)
                line(8.5f, 21f, 15.5f, 21f)
            }
            Icon.KEYBOARD -> {
                p.addRoundRect(RectF(2.5f, 6f, 21.5f, 18f), 2.5f, 2.5f, Path.Direction.CW)
                for (x in floatArrayOf(6.5f, 9.5f, 12.5f, 15.5f, 18f)) dot(x - 0.5f, 10f)
                line(8f, 14f, 16f, 14f)
            }
            Icon.BACKSPACE -> {
                line(9f, 5.5f, 19.5f, 5.5f)
                p.quadTo(21f, 5.5f, 21f, 7f)
                p.lineTo(21f, 17f)
                p.quadTo(21f, 18.5f, 19.5f, 18.5f)
                p.lineTo(9f, 18.5f)
                p.lineTo(2.5f, 12f)
                p.close()
                line(12.5f, 9.5f, 17.5f, 14.5f)
                line(17.5f, 9.5f, 12.5f, 14.5f)
            }
            Icon.ENTER -> {
                line(19.5f, 5f, 19.5f, 12f)
                p.quadTo(19.5f, 15f, 16.5f, 15f)
                p.lineTo(5f, 15f)
                line(9f, 11f, 5f, 15f, 9f, 19f)
            }
            Icon.SLIDERS -> {
                line(4f, 7f, 12.8f, 7f); line(17.2f, 7f, 20f, 7f)
                p.addCircle(15f, 7f, 2.2f, Path.Direction.CW)
                line(4f, 12f, 6.8f, 12f); line(11.2f, 12f, 20f, 12f)
                p.addCircle(9f, 12f, 2.2f, Path.Direction.CW)
                line(4f, 17f, 14.8f, 17f); line(19.2f, 17f, 20f, 17f)
                p.addCircle(17f, 17f, 2.2f, Path.Direction.CW)
            }
            Icon.HOME -> {
                line(3.5f, 11f, 12f, 4f, 20.5f, 11f)
                line(6f, 9f, 6f, 20f, 18f, 20f, 18f, 9f)
                line(10f, 20f, 10f, 15f, 14f, 15f, 14f, 20f)
            }
            Icon.BOOK -> {
                line(12f, 6.5f, 12f, 20f)
                p.moveTo(12f, 6.5f)
                p.quadTo(8f, 4f, 3.5f, 4.5f)
                p.lineTo(3.5f, 18f)
                p.quadTo(8f, 17.5f, 12f, 20f)
                p.quadTo(16f, 17.5f, 20.5f, 18f)
                p.lineTo(20.5f, 4.5f)
                p.quadTo(16f, 4f, 12f, 6.5f)
            }
            Icon.CLOCK -> {
                p.addCircle(12f, 12f, 8.5f, Path.Direction.CW)
                line(12f, 7.5f, 12f, 12f, 15.5f, 14f)
            }
            Icon.COPY -> {
                p.addRoundRect(RectF(8.5f, 8.5f, 20f, 20f), 2f, 2f, Path.Direction.CW)
                line(15.5f, 8.5f, 15.5f, 6f)
                p.quadTo(15.5f, 4f, 13.5f, 4f)
                p.lineTo(6f, 4f)
                p.quadTo(4f, 4f, 4f, 6f)
                p.lineTo(4f, 13.5f)
                p.quadTo(4f, 15.5f, 6f, 15.5f)
                p.lineTo(8.5f, 15.5f)
            }
            Icon.TRASH -> {
                line(4f, 7f, 20f, 7f)
                line(9f, 7f, 9f, 4.5f, 15f, 4.5f, 15f, 7f)
                line(6f, 7f, 7f, 20f, 17f, 20f, 18f, 7f)
                line(10f, 11f, 10f, 16f)
                line(14f, 11f, 14f, 16f)
            }
            Icon.CHECK -> line(5f, 12.5f, 10f, 17f, 19f, 7.5f)
            Icon.CLOSE -> {
                line(6.5f, 6.5f, 17.5f, 17.5f)
                line(17.5f, 6.5f, 6.5f, 17.5f)
            }
            Icon.RETRY -> {
                p.addArc(RectF(5f, 5f, 19f, 19f), -30f, 300f)
                line(9.5f, 2.5f, 12f, 5f, 9.5f, 7.5f)
            }
            Icon.UNDO -> {
                line(9f, 14f, 4f, 9f, 9f, 4f)
                line(4f, 9f, 14.5f, 9f)
                p.quadTo(20f, 9f, 20f, 14f)
                p.quadTo(20f, 19f, 14.5f, 19f)
                p.lineTo(11f, 19f)
            }
            Icon.SPACE -> line(5f, 10.5f, 5f, 15f, 19f, 15f, 19f, 10.5f)
            Icon.KEY -> {
                p.addCircle(8f, 15f, 4f, Path.Direction.CW)
                line(11f, 12f, 20f, 3f)
                line(17f, 6f, 19.5f, 8.5f)
                line(14.5f, 8.5f, 16.5f, 10.5f)
            }
            Icon.SHIELD -> {
                line(12f, 3f, 19f, 6f, 19f, 11f)
                p.quadTo(19f, 17f, 12f, 21f)
                p.quadTo(5f, 17f, 5f, 11f)
                p.lineTo(5f, 6f)
                p.close()
                line(9f, 12f, 11.2f, 14.2f, 15f, 10f)
            }
            Icon.CHEVRON -> line(9f, 5.5f, 15.5f, 12f, 9f, 18.5f)
            Icon.PLUS -> {
                line(12f, 5f, 12f, 19f)
                line(5f, 12f, 19f, 12f)
            }
            Icon.ARROW -> {
                line(4f, 12f, 19f, 12f)
                line(13.5f, 6.5f, 19f, 12f, 13.5f, 17.5f)
            }
        }
        canvas.drawPath(p, paint)
        canvas.restore()
    }

    fun strokePaint(color: Int, width: Float = 1.8f) = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeWidth = width
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
        this.color = color
    }

    /** Hushtype 標誌：聲波 + 文字游標。畫在 64×64 的格子上。 */
    fun drawLogo(canvas: Canvas, left: Float, top: Float, size: Float, background: Boolean = true) {
        val s = size / 64f
        canvas.save()
        canvas.translate(left, top)
        canvas.scale(s, s)
        if (background) {
            val bg = Paint(Paint.ANTI_ALIAS_FLAG).apply {
                shader = android.graphics.LinearGradient(0f, 0f, 64f, 64f, Palette.BRAND[0], Palette.BRAND[1], android.graphics.Shader.TileMode.CLAMP)
            }
            canvas.drawRoundRect(RectF(2f, 2f, 62f, 62f), 15f, 15f, bg)
        }
        val fill = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = Color.WHITE }
        val w = 5.2f
        for ((x, h) in listOf(12f to 12f, 20f to 22f, 28f to 30f, 36f to 17f)) {
            canvas.drawRoundRect(RectF(x, 32 - h / 2, x + w, 32 + h / 2), w / 2, w / 2, fill)
        }
        val pen = strokePaint(Color.WHITE, 3.6f)
        canvas.drawLine(47.5f, 16f, 47.5f, 48f, pen)
        canvas.drawLine(43f, 16f, 52f, 16f, pen)
        canvas.drawLine(43f, 48f, 52f, 48f, pen)
        canvas.restore()
    }
}

class IconView(context: Context, icon: Icon, color: Int, private val stroke: Float = 1.8f) : View(context) {
    var icon: Icon = icon
        set(value) {
            field = value
            invalidate()
        }
    var color: Int = color
        set(value) {
            field = value
            paint.color = value
            invalidate()
        }
    private val paint = Icons.strokePaint(color, stroke)

    override fun onDraw(canvas: Canvas) {
        val size = minOf(width - paddingLeft - paddingRight, height - paddingTop - paddingBottom).toFloat()
        val left = paddingLeft + (width - paddingLeft - paddingRight - size) / 2
        val top = paddingTop + (height - paddingTop - paddingBottom - size) / 2
        Icons.draw(canvas, icon, left, top, size, paint)
    }
}

class LogoView(context: Context) : View(context) {
    override fun onDraw(canvas: Canvas) {
        val size = minOf(width, height).toFloat()
        Icons.drawLogo(canvas, (width - size) / 2, (height - size) / 2, size)
    }
}
