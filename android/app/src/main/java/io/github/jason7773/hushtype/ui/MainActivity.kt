package io.github.jason7773.hushtype.ui

import android.Manifest
import android.app.Activity
import android.content.ClipData
import android.content.ClipDescription
import android.content.ClipboardManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PersistableBundle
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import io.github.jason7773.hushtype.data.Settings

/** App 主畫面：首頁、字典、歷史紀錄、設定。 */
class MainActivity : Activity() {
    companion object {
        const val ACTION_REQUEST_MIC = "io.github.jason7773.hushtype.REQUEST_MIC"
        const val ACTION_SETTINGS = "io.github.jason7773.hushtype.SETTINGS"
        private const val REQ_MIC = 1
    }

    enum class Tab(val label: String, val icon: Icon) {
        HOME("首頁", Icon.HOME),
        DICTIONARY("字典", Icon.BOOK),
        HISTORY("歷史", Icon.CLOCK),
        SETTINGS("設定", Icon.SLIDERS),
    }

    lateinit var pal: Palette
        private set
    lateinit var ui: Ui
        private set
    val settings: Settings by lazy { Settings.get(this) }

    private lateinit var container: FrameLayout
    private lateinit var nav: LinearLayout
    private lateinit var aurora: AuroraView
    private var tab = Tab.HOME
    private var page: Page? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        tab = savedInstanceState?.getString("tab")?.let { runCatching { Tab.valueOf(it) }.getOrNull() } ?: Tab.HOME
        pal = Palette.of(this)
        ui = Ui(this, pal)
        setupWindow()
        setContentView(buildRoot())
        handleIntent(intent)
        showTab(tab, animate = false)
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString("tab", tab.name)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    override fun onResume() {
        super.onResume()
        // 從系統設定回來時（例如剛啟用鍵盤），更新畫面上的狀態
        page?.onResume()
    }

    override fun onDestroy() {
        page?.onHidden()
        super.onDestroy()
    }

    private fun handleIntent(intent: Intent?) {
        when (intent?.action) {
            ACTION_REQUEST_MIC -> {
                tab = Tab.HOME
                requestMic()
            }
            ACTION_SETTINGS -> {
                tab = Tab.SETTINGS
                if (::container.isInitialized) showTab(tab)
            }
        }
    }

    private fun setupWindow() {
        @Suppress("DEPRECATION")
        window.setDecorFitsSystemWindows(false)
        @Suppress("DEPRECATION")
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        @Suppress("DEPRECATION")
        window.navigationBarColor = android.graphics.Color.TRANSPARENT
        window.isNavigationBarContrastEnforced = false
        val light = if (pal.dark) 0 else
            WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS
        window.decorView.post {
            window.insetsController?.setSystemBarsAppearance(
                light,
                WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS or WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS,
            )
        }
    }

    private fun buildRoot(): View {
        val root = FrameLayout(this)
        aurora = AuroraView(this, pal).apply { animate = settings.animations }
        root.addView(aurora, FrameLayout.LayoutParams(MATCH, MATCH))

        val column = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val header = ui.horizontal(spacing = 12) {
            setPadding(dp(20), dp(14), dp(20), dp(6))
            addView(LogoView(context), LinearLayout.LayoutParams(dp(34), dp(34)))
            addView(ui.text("Hushtype", 21f, pal.text, BOLD))
            addView(ui.text("悄聲", 21f, pal.textSecondary, MEDIUM))
        }
        column.addView(header)
        container = FrameLayout(this)
        column.addView(container, lp(MATCH, 0, 1f))
        root.addView(column, FrameLayout.LayoutParams(MATCH, MATCH))

        nav = ui.horizontal(spacing = 4) {
            setPadding(dp(6), dp(6), dp(6), dp(6))
            background = GlassDrawable(pal, dpf(26), dpf(1), intArrayOf(
                if (pal.dark) 0xE61C1C30.toInt() else 0xEBFFFFFF.toInt(),
                if (pal.dark) 0xE6141424.toInt() else 0xE0F6F7FD.toInt(),
            ))
            elevation = dpf(8)
        }
        val navLp = FrameLayout.LayoutParams(MATCH, WRAP, Gravity.BOTTOM).apply {
            leftMargin = dp(16)
            rightMargin = dp(16)
        }
        root.addView(nav, navLp)

        root.setOnApplyWindowInsetsListener { _, insets ->
            val bars = insets.getInsets(WindowInsets.Type.systemBars())
            val ime = insets.getInsets(WindowInsets.Type.ime()).bottom
            column.setPadding(bars.left, bars.top, bars.right, ime)
            navLp.bottomMargin = bars.bottom + dp(12)
            nav.layoutParams = navLp
            nav.visibility = if (ime > 0) View.GONE else View.VISIBLE
            insets
        }
        return root
    }

    private fun renderNav() {
        nav.removeAllViews()
        for (t in Tab.entries) {
            val selected = t == tab
            val color = if (selected) pal.accent else pal.textMuted
            val item = ui.vertical(spacing = 2) {
                gravity = Gravity.CENTER
                setPadding(0, dp(7), 0, dp(7))
                if (selected) background = android.graphics.drawable.GradientDrawable().apply {
                    cornerRadius = dpf(20)
                    setColor(pal.accentSoft)
                }
                addView(IconView(context, t.icon, color), LinearLayout.LayoutParams(dp(22), dp(22)).apply { gravity = Gravity.CENTER_HORIZONTAL })
                addView(ui.text(t.label, 12f, color, if (selected) MEDIUM else null).apply { gravity = Gravity.CENTER })
                isClickable = true
                contentDescription = t.label
                setOnClickListener { if (t != tab) showTab(t) }
            }
            nav.addView(item, lp(0, WRAP, 1f))
        }
    }

    fun showTab(t: Tab, animate: Boolean = true) {
        tab = t
        page?.onHidden()
        page = when (t) {
            Tab.HOME -> HomePage(this)
            Tab.DICTIONARY -> DictionaryPage(this)
            Tab.HISTORY -> HistoryPage(this)
            Tab.SETTINGS -> SettingsPage(this)
        }
        renderNav()
        refresh(animate)
    }

    /** 重新產生目前這一頁（資料改變時）。 */
    fun refresh(animate: Boolean = false) {
        val p = page ?: return
        val scroll = container.getChildAt(0) as? ScrollView
        val y = if (animate) 0 else scroll?.scrollY ?: 0
        container.removeAllViews()
        val content = p.build()
        val sv = ScrollView(this).apply {
            isFillViewport = true
            isVerticalScrollBarEnabled = false
            clipToPadding = false
            addView(content.apply { setPadding(dp(16), dp(8), dp(16), dp(120)) })
        }
        container.addView(sv, FrameLayout.LayoutParams(MATCH, MATCH))
        if (y > 0) sv.post { sv.scrollTo(0, y) }
        if (animate && settings.animations) {
            sv.alpha = 0f
            sv.translationY = dpf(12)
            sv.animate().alpha(1f).translationY(0f).setDuration(220).start()
        }
    }

    /** 主題或動態效果改變時，整個畫面重建。 */
    fun restyle() = recreate()

    fun requestMic() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), REQ_MIC)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_MIC) {
            if (grantResults.firstOrNull() != android.content.pm.PackageManager.PERMISSION_GRANTED &&
                !shouldShowRequestPermissionRationale(Manifest.permission.RECORD_AUDIO)
            ) {
                // 使用者選了「不再詢問」，只能到系統設定開
                toast("請在系統設定裡允許 Hushtype 使用麥克風")
                startActivity(Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:$packageName")))
            }
            page?.onResume()
        }
    }

    fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: Exception) {
            toast("找不到可以開啟連結的 App")
        }
    }

    fun copy(text: String) {
        val cm = getSystemService(CLIPBOARD_SERVICE) as ClipboardManager
        val clip = ClipData.newPlainText("Hushtype", text)
        // 標記為敏感內容，系統的剪貼簿預覽不會顯示文字
        if (Build.VERSION.SDK_INT >= 33) {
            clip.description.extras = PersistableBundle().apply { putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true) }
        }
        cm.setPrimaryClip(clip)
        if (Build.VERSION.SDK_INT < 33) toast("已複製")
    }

    fun toast(text: String) = Toast.makeText(this, text, Toast.LENGTH_SHORT).show()

    fun pageTitle(title: String, subtitle: String? = null): View = ui.vertical(spacing = 2) {
        setPadding(dp(4), dp(6), dp(4), dp(2))
        addView(ui.text(title, 26f, pal.text, BOLD))
        if (subtitle != null) addView(ui.body(subtitle))
    }
}

/** 一個分頁。build() 每次重新產生整頁的內容。 */
abstract class Page(val activity: MainActivity) {
    val ui: Ui get() = activity.ui
    val pal: Palette get() = activity.pal
    val settings: Settings get() = activity.settings

    fun dp(v: Number) = activity.dp(v)
    fun dpf(v: Number) = activity.dpf(v)

    abstract fun build(): LinearLayout
    open fun onResume() {}
    open fun onHidden() {}

    fun column(block: LinearLayout.() -> Unit): LinearLayout = ui.vertical(spacing = 14, block = block)

    fun status(): TextView = ui.muted("").apply { visibility = View.GONE }

    fun TextView.show(text: String, color: Int) {
        this.text = text
        setTextColor(color)
        visibility = View.VISIBLE
    }
}
