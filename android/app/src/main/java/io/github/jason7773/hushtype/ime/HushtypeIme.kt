package io.github.jason7773.hushtype.ime

import android.Manifest
import android.annotation.SuppressLint
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.GradientDrawable
import android.inputmethodservice.InputMethodService
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.Gravity
import android.view.HapticFeedbackConstants
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowInsets
import android.view.inputmethod.EditorInfo
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import io.github.jason7773.hushtype.core.ApiException
import io.github.jason7773.hushtype.core.Dictation
import io.github.jason7773.hushtype.core.Recorder
import io.github.jason7773.hushtype.core.Recording
import io.github.jason7773.hushtype.core.TextRules
import io.github.jason7773.hushtype.data.History
import io.github.jason7773.hushtype.data.HistoryEntry
import io.github.jason7773.hushtype.data.Settings
import io.github.jason7773.hushtype.data.Stats
import io.github.jason7773.hushtype.ui.AuroraView
import io.github.jason7773.hushtype.ui.GlassDrawable
import io.github.jason7773.hushtype.ui.Icon
import io.github.jason7773.hushtype.ui.IconView
import io.github.jason7773.hushtype.ui.MATCH
import io.github.jason7773.hushtype.ui.MainActivity
import io.github.jason7773.hushtype.ui.Palette
import io.github.jason7773.hushtype.ui.Ui
import io.github.jason7773.hushtype.ui.WRAP
import io.github.jason7773.hushtype.ui.lp
import java.util.concurrent.Executors

/**
 * Hushtype 鍵盤：中間一顆大麥克風。按一下開始、再按一下結束（或按住說話、放開結束），
 * 辨識整理好的文字直接輸入到目前的輸入框。
 */
class HushtypeIme : InputMethodService() {
    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val warmer = Executors.newSingleThreadExecutor()
    private val recorder = Recorder()
    private lateinit var settings: Settings

    private var pal: Palette = Palette.LIGHT
    private var mic: MicButton? = null
    private var status: TextView? = null
    private var hint: TextView? = null
    private var aurora: AuroraView? = null
    private var retryChip: View? = null
    private var undoChip: View? = null
    private var cancelChip: View? = null

    private var state = MicState.IDLE
    private var pressedAt = 0L
    private var startedWhilePressed = false
    private var failed: Recording? = null // 辨識失敗時保留錄音，可以重試
    private var lastCommitted: String? = null
    private var job = 0 // 每次處理的編號，取消後舊結果不再輸入

    private val ticker = object : Runnable {
        override fun run() {
            if (state != MicState.RECORDING) return
            mic?.level = recorder.level
            val s = recorder.elapsedSeconds.toInt()
            setStatus("聆聽中  %d:%02d".format(s / 60, s % 60), Palette.RECORDING)
            if (recorder.full) {
                stopAndProcess()
                return
            }
            main.postDelayed(this, 50)
        }
    }

    override fun onCreate() {
        super.onCreate()
        settings = Settings.get(this)
    }

    override fun onDestroy() {
        recorder.cancel()
        worker.shutdownNow()
        warmer.shutdownNow()
        super.onDestroy()
    }

    override fun onCreateInputView(): View {
        pal = Palette.of(this)
        val ui = Ui(this, pal)
        val root = FrameLayout(this)
        aurora = AuroraView(this, pal).also {
            it.animate = false
            root.addView(it, FrameLayout.LayoutParams(MATCH, MATCH))
        }
        val glass = View(this).apply { background = GlassDrawable(pal, 0f, 0f) }
        root.addView(glass, FrameLayout.LayoutParams(MATCH, MATCH))

        val column = ui.vertical(spacing = 6) {
            setPadding(dp(10), dp(8), dp(10), dp(10))
            addView(ui.horizontal {
                addView(ui.iconButton(Icon.SLIDERS, pal.textSecondary, "Hushtype 設定") { openApp(null) })
                status = ui.text("", 14f, pal.textSecondary).apply { gravity = Gravity.CENTER }
                addView(status, lp(0, WRAP, 1f))
                addView(ui.iconButton(Icon.KEYBOARD, pal.textSecondary, "切換鍵盤") { switchKeyboard() }.apply {
                    setOnLongClickListener {
                        imm().showInputMethodPicker()
                        true
                    }
                })
            })
            addView(ui.horizontal(spacing = 8) {
                gravity = Gravity.CENTER
                minimumHeight = dp(34)
                retryChip = chip(ui, Icon.RETRY, "重試") { retry() }
                undoChip = chip(ui, Icon.UNDO, "復原") { undo() }
                cancelChip = chip(ui, Icon.CLOSE, "取消") { cancel() }
                addView(retryChip)
                addView(undoChip)
                addView(cancelChip)
            })
            mic = MicButton(context).apply {
                contentDescription = "語音輸入"
                setOnTouchListener { v, e -> onMicTouch(v, e) }
            }
            addView(mic, lp(MATCH, dp(132)))
            hint = ui.muted("按一下開始，再按一下結束；也可以按住說話").apply { gravity = Gravity.CENTER }
            addView(hint)
            addView(ui.horizontal(spacing = 8) {
                setPadding(0, dp(6), 0, 0)
                addView(key(ui, Icon.SPACE, "空白") { commit(" ") }, lp(0, dp(46), 1f))
                addView(repeatKey(ui, Icon.BACKSPACE, "刪除") { backspace() }, lp(dp(76), dp(46)))
                addView(key(ui, Icon.ENTER, "換行") { enter() }, lp(dp(76), dp(46)))
            })
        }
        root.addView(column, FrameLayout.LayoutParams(MATCH, WRAP))
        // 手勢導覽列在鍵盤下方，留出空間
        root.setOnApplyWindowInsetsListener { v, insets ->
            val nav = insets.getInsets(WindowInsets.Type.navigationBars()).bottom
            column.setPadding(column.paddingLeft, column.paddingTop, column.paddingRight, dp(10) + nav)
            insets
        }
        render()
        return root
    }

    private fun dp(v: Number) = (v.toFloat() * resources.displayMetrics.density + 0.5f).toInt()

    private fun chip(ui: Ui, icon: Icon, label: String, onClick: () -> Unit): View = ui.horizontal(spacing = 6) {
        setPadding(dp(12), dp(6), dp(14), dp(6))
        background = GradientDrawable().apply {
            cornerRadius = dp(16).toFloat()
            setColor(pal.accentSoft)
        }
        addView(IconView(context, icon, pal.accent), LinearLayout.LayoutParams(dp(16), dp(16)))
        addView(ui.text(label, 13.5f, pal.accent))
        isClickable = true
        setOnClickListener {
            haptic(it)
            onClick()
        }
        visibility = View.GONE
    }

    private fun keyView(ui: Ui, icon: Icon, label: String): FrameLayout = FrameLayout(this).apply {
        background = GlassDrawable(pal, dp(14).toFloat(), dp(1).toFloat())
        contentDescription = label
        addView(
            IconView(context, icon, pal.text).apply { setPadding(0, dp(12), 0, dp(12)) },
            FrameLayout.LayoutParams(MATCH, MATCH),
        )
        isClickable = true
    }

    private fun key(ui: Ui, icon: Icon, label: String, action: () -> Unit): View = keyView(ui, icon, label).apply {
        setOnClickListener {
            haptic(it)
            action()
        }
    }

    /** 按住會連續刪除。 */
    @SuppressLint("ClickableViewAccessibility")
    private fun repeatKey(ui: Ui, icon: Icon, label: String, action: () -> Unit): View {
        val v = keyView(ui, icon, label)
        val repeat = object : Runnable {
            override fun run() {
                action()
                main.postDelayed(this, 50)
            }
        }
        v.setOnTouchListener { view, e ->
            when (e.action) {
                MotionEvent.ACTION_DOWN -> {
                    view.isPressed = true
                    haptic(view)
                    action()
                    main.postDelayed(repeat, 400)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    view.isPressed = false
                    main.removeCallbacks(repeat)
                }
            }
            true
        }
        return v
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        if (!restarting) {
            lastCommitted = null
        }
        // 主題可能在 App 裡改過
        val now = Palette.of(this)
        if (now !== pal) setInputView(onCreateInputView())
        render()
    }

    override fun onWindowHidden() {
        super.onWindowHidden()
        // 鍵盤收起來時不在背景偷偷錄音
        if (state == MicState.RECORDING) cancel()
    }

    override fun onEvaluateFullscreenMode(): Boolean = false

    // ---- 錄音流程 ----

    @SuppressLint("ClickableViewAccessibility")
    private fun onMicTouch(v: View, e: MotionEvent): Boolean {
        when (e.action) {
            MotionEvent.ACTION_DOWN -> {
                pressedAt = SystemClock.uptimeMillis()
                haptic(v)
                when (state) {
                    MicState.IDLE -> {
                        startedWhilePressed = startRecording()
                    }
                    MicState.RECORDING -> {
                        startedWhilePressed = false
                        stopAndProcess()
                    }
                    MicState.PROCESSING -> startedWhilePressed = false
                }
            }
            MotionEvent.ACTION_UP -> {
                // 按住超過半秒才放開：當作「按住說話」，放開就結束
                if (startedWhilePressed && state == MicState.RECORDING && SystemClock.uptimeMillis() - pressedAt > 500) {
                    haptic(v)
                    stopAndProcess()
                }
                startedWhilePressed = false
                v.performClick()
            }
            MotionEvent.ACTION_CANCEL -> startedWhilePressed = false
        }
        return true
    }

    private fun startRecording(): Boolean {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            setStatus("請先允許使用麥克風", pal.bad)
            openApp(MainActivity.ACTION_REQUEST_MIC)
            return false
        }
        if (!settings.hasApiKey()) {
            setStatus("請先在設定裡填入 API 金鑰", pal.bad)
            openApp(MainActivity.ACTION_SETTINGS)
            return false
        }
        if (!recorder.start()) {
            setStatus("無法使用麥克風，可能正被其他程式占用", pal.bad)
            return false
        }
        failed = null
        lastCommitted = null
        state = MicState.RECORDING
        // 先跟服務建好連線，放開時就能直接上傳
        val config = settings.dictationConfig()
        warmer.execute { Dictation(config).warmUp() }
        render()
        main.post(ticker)
        return true
    }

    private fun stopAndProcess() {
        if (state != MicState.RECORDING) return
        main.removeCallbacks(ticker)
        val rec = recorder.stop()
        if (rec.seconds < 0.4 || rec.rms < 120) {
            state = MicState.IDLE
            render()
            setStatus("沒有聽到聲音", pal.textMuted)
            return
        }
        process(rec)
    }

    private fun process(rec: Recording) {
        state = MicState.PROCESSING
        failed = null
        render()
        val config = settings.dictationConfig()
        val id = ++job
        val started = SystemClock.elapsedRealtime()
        worker.execute {
            val result = try {
                Result.success(Dictation(config).run(rec))
            } catch (e: ApiException) {
                Result.failure(e)
            } catch (e: Exception) {
                Result.failure(ApiException("發生錯誤：${e.message ?: e.javaClass.simpleName}"))
            }
            main.post {
                if (id != job) return@post
                state = MicState.IDLE
                result.onSuccess { r ->
                    if (r.text.isEmpty()) {
                        render()
                        setStatus("沒有辨識出文字", pal.textMuted)
                        return@onSuccess
                    }
                    val placed = commit(r.text)
                    lastCommitted = if (placed) r.text else null
                    val chars = TextRules.countChars(r.text)
                    Stats.record(this, rec.seconds, chars)
                    History.add(
                        this,
                        HistoryEntry(System.currentTimeMillis(), System.currentTimeMillis(), r.text, rec.seconds, r.sttMs, r.cleanupMs),
                    )
                    render()
                    val took = (SystemClock.elapsedRealtime() - started) / 1000.0
                    when {
                        !placed -> setStatus("找不到輸入框，結果已存在歷史紀錄", pal.warn)
                        r.cleanupFailed -> setStatus("AI 整理失敗，已輸入原始辨識結果", pal.warn)
                        else -> setStatus("已輸入 %d 字 · %.1f 秒".format(chars, took), pal.good)
                    }
                    if (placed && settings.switchBack) main.postDelayed({ switchKeyboard() }, 600)
                }.onFailure { e ->
                    failed = rec
                    render()
                    setStatus(e.message ?: "辨識失敗", pal.bad)
                }
            }
        }
    }

    private fun retry() {
        val rec = failed ?: return
        process(rec)
    }

    private fun cancel() {
        when (state) {
            MicState.RECORDING -> {
                main.removeCallbacks(ticker)
                recorder.cancel()
            }
            MicState.PROCESSING -> job++
            MicState.IDLE -> return
        }
        state = MicState.IDLE
        render()
        setStatus("已取消", pal.textMuted)
    }

    /** 刪掉剛剛輸入的文字（游標前面還是那段文字時才刪）。 */
    private fun undo() {
        val text = lastCommitted ?: return
        val ic = currentInputConnection ?: return
        if (ic.getTextBeforeCursor(text.length, 0)?.toString() == text) {
            ic.deleteSurroundingText(text.length, 0)
            setStatus("已復原", pal.textMuted)
        }
        lastCommitted = null
        render()
    }

    // ---- 輸入 ----

    private fun commit(text: String): Boolean {
        val ic = currentInputConnection ?: return false
        return ic.commitText(text, 1)
    }

    private fun backspace() {
        val ic = currentInputConnection ?: return
        lastCommitted = null
        val selected = ic.getSelectedText(0)
        if (!selected.isNullOrEmpty()) ic.commitText("", 1) else sendDownUpKeyEvents(KeyEvent.KEYCODE_DEL)
        if (undoChip?.visibility == View.VISIBLE) render()
    }

    private fun enter() {
        val info = currentInputEditorInfo
        val action = (info?.imeOptions ?: 0) and EditorInfo.IME_MASK_ACTION
        val noEnterAction = ((info?.imeOptions ?: 0) and EditorInfo.IME_FLAG_NO_ENTER_ACTION) != 0
        val multiline = ((info?.inputType ?: 0) and android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE) != 0
        if (!multiline && !noEnterAction && action != EditorInfo.IME_ACTION_NONE && action != EditorInfo.IME_ACTION_UNSPECIFIED) {
            currentInputConnection?.performEditorAction(action)
        } else {
            sendDownUpKeyEvents(KeyEvent.KEYCODE_ENTER)
        }
    }

    private fun switchKeyboard() {
        if (!switchToPreviousInputMethod()) imm().showInputMethodPicker()
    }

    private fun imm() = getSystemService(INPUT_METHOD_SERVICE) as android.view.inputmethod.InputMethodManager

    private fun openApp(action: String?) {
        val intent = Intent(this, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
            if (action != null) this.action = action
        }
        startActivity(intent)
    }

    // ---- 畫面 ----

    private fun haptic(v: View) {
        if (settings.haptics) v.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
    }

    private fun setStatus(text: String, color: Int) {
        status?.text = text
        status?.setTextColor(color)
    }

    private fun render() {
        mic?.state = state
        aurora?.setColors(
            when (state) {
                MicState.RECORDING -> Palette.AURORA_RECORDING
                MicState.PROCESSING -> Palette.AURORA_PROCESSING
                MicState.IDLE -> null
            },
        )
        aurora?.animate = state != MicState.IDLE && settings.animations
        retryChip?.visibility = if (state == MicState.IDLE && failed != null) View.VISIBLE else View.GONE
        undoChip?.visibility = if (state == MicState.IDLE && lastCommitted != null) View.VISIBLE else View.GONE
        cancelChip?.visibility = if (state != MicState.IDLE) View.VISIBLE else View.GONE
        when (state) {
            MicState.IDLE -> {
                if (failed == null && lastCommitted == null) setStatus(settings.provider.label + " · 待命中", pal.textSecondary)
                hint?.text = "按一下開始，再按一下結束；也可以按住說話"
            }
            MicState.RECORDING -> hint?.text = "再按一下結束"
            MicState.PROCESSING -> {
                setStatus("轉譯中…", Palette.PROCESSING)
                hint?.text = "正在辨識與整理"
            }
        }
    }
}
