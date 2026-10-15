package io.github.jason7773.hushtype.ui

import android.os.Handler
import android.os.Looper
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.EditText
import android.widget.LinearLayout
import io.github.jason7773.hushtype.BuildConfig
import io.github.jason7773.hushtype.core.ApiClient
import io.github.jason7773.hushtype.core.ApiException
import io.github.jason7773.hushtype.core.Provider
import io.github.jason7773.hushtype.data.History
import io.github.jason7773.hushtype.data.Stats

class SettingsPage(activity: MainActivity) : Page(activity) {
    private val main = Handler(Looper.getMainLooper())

    override fun build(): LinearLayout = column {
        addView(activity.pageTitle("設定"))
        addView(serviceCard())
        addView(modelCard())
        addView(inputCard())
        addView(historyCard())
        addView(lookCard())
        addView(aboutCard())
    }

    private fun serviceCard(): View = ui.card {
        val p = settings.provider
        addView(ui.heading("語音服務"))
        addView(ui.segmented(Provider.entries.map { it.id to it.label }, p.id) { id ->
            settings.provider = Provider.of(id)
            activity.refresh()
        })
        addView(ui.muted(
            when (p) {
                Provider.GROQ -> "速度最快，有免費額度。辨識用 Whisper，整理用 GPT-OSS。"
                Provider.OPENAI -> "辨識準確，依用量付費。"
                Provider.GEMINI -> "注意：Gemini 免費方案可能用你的內容改進 Google 的產品，機密內容請改用付費方案或其他服務。"
            },
        ).apply { if (p == Provider.GEMINI) setTextColor(pal.warn) })

        val saved = settings.hasApiKey(p)
        val field = ui.input(if (saved) "已儲存，貼上新的金鑰可以取代" else "貼上 ${p.label} API 金鑰", password = true)
        addView(field)
        val result = status()
        addView(ui.horizontal(spacing = 10) {
            addView(ui.primaryButton(if (saved) "儲存並測試" else "儲存", Icon.CHECK) {
                val key = field.text.toString().trim()
                if (key.isNotEmpty()) {
                    settings.setApiKey(p, key)
                    field.setText("")
                    field.hint = "已儲存，貼上新的金鑰可以取代"
                }
                if (!settings.hasApiKey(p)) {
                    result.show("請先貼上金鑰", pal.bad)
                    return@primaryButton
                }
                test(p, result)
            })
            addView(ui.secondaryButton("取得金鑰", Icon.KEY) { activity.openUrl(p.keyUrl) })
        })
        addView(result)
        if (saved) {
            addView(ui.horizontal {
                addView(ui.muted("金鑰已加密存在這支手機"), lp(0, WRAP, 1f))
                addView(ui.text("刪除金鑰", 13.5f, pal.bad).apply {
                    setPadding(dp(8), dp(6), dp(8), dp(6))
                    setOnClickListener {
                        settings.setApiKey(p, "")
                        activity.refresh()
                    }
                })
            })
        }
    }

    private fun test(p: Provider, result: android.widget.TextView) {
        result.show("測試連線中…", pal.textMuted)
        val key = settings.apiKey(p)
        val models = listOfNotNull(settings.sttModel, settings.cleanupModel.takeIf { settings.cleanupEnabled }).distinct()
        Thread {
            val error = try {
                ApiClient(p, key).check(models)
                null
            } catch (e: ApiException) {
                e.message
            } catch (e: Exception) {
                "連線失敗：${e.message}"
            }
            main.post {
                if (error == null) result.show("連線成功，金鑰與型號都可以使用", pal.good) else result.show(error, pal.bad)
            }
        }.start()
    }

    private fun modelCard(): View = ui.card {
        val p = settings.provider
        addView(ui.heading("模型"))
        addView(ui.text("語音辨識", 14.5f, pal.text, MEDIUM))
        addView(modelPicker(settings.sttModel, p.sttModels) { settings.sttModel = it })
        addView(ui.divider())
        addView(ui.switchRow("AI 整理", "去掉贅字、處理說錯改口、加上標點與分段", settings.cleanupEnabled) {
            settings.cleanupEnabled = it
            activity.refresh()
        })
        if (settings.cleanupEnabled) addView(modelPicker(settings.cleanupModel, p.cleanupModels) { settings.cleanupModel = it })
    }

    /** 可以直接輸入型號，或點下面的常用型號。 */
    private fun modelPicker(current: String, options: List<String>, onChange: (String) -> Unit): View = ui.vertical(spacing = 8) {
        val field: EditText = ui.input("型號名稱", current)
        field.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                val v = s.toString().trim()
                if (v.isNotEmpty()) onChange(v)
            }
        })
        addView(field)
        addView(ui.segmented(options.map { it to it }, current) { id ->
            onChange(id)
            activity.refresh()
        })
    }

    private fun inputCard(): View = ui.card {
        addView(ui.heading("輸入"))
        addView(ui.switchRow("轉成繁體中文", "辨識結果是簡體字時自動轉成繁體", settings.toTraditional) { settings.toTraditional = it })
        addView(ui.divider())
        addView(ui.switchRow("震動回饋", "按下鍵盤按鈕時輕震一下", settings.haptics) { settings.haptics = it })
        addView(ui.divider())
        addView(ui.switchRow("輸入後切回原本的鍵盤", "說完一段話自動回到你平常用的鍵盤", settings.switchBack) { settings.switchBack = it })
    }

    private fun historyCard(): View = ui.card {
        addView(ui.heading("歷史紀錄保留"))
        val options = listOf("session" to "關閉 App 前", "1d" to "1 天", "7d" to "1 週", "30d" to "1 個月", "forever" to "永久")
        addView(ui.segmented(options, settings.historyRetention) { id ->
            settings.historyRetention = id
            History.retentionChanged(activity)
            activity.refresh()
        })
        addView(ui.muted(
            if (settings.historyRetention == "session") "只放在記憶體，App 被系統關閉後就清除。"
            else "用手機安全晶片裡的金鑰加密後存在本機，不會備份到雲端，換手機也不會帶走。",
        ))
    }

    private fun lookCard(): View = ui.card {
        addView(ui.heading("外觀"))
        val themes = listOf("system" to "跟隨系統", "light" to "淺色", "dark" to "深色")
        addView(ui.segmented(themes, settings.theme) { id ->
            settings.theme = id
            activity.restyle()
        })
        addView(ui.switchRow("動態背景", "流動的極光背景與換頁動畫", settings.animations) {
            settings.animations = it
            activity.restyle()
        })
    }

    private fun aboutCard(): View = ui.card {
        addView(ui.heading("關於"))
        addView(ui.body("Hushtype 悄聲 ${BuildConfig.VERSION_NAME}\n開放原始碼（MIT 授權），沒有自己的伺服器，不收集任何資料。"))
        addView(ui.horizontal(spacing = 10) {
            addView(ui.secondaryButton("原始碼與更新") { activity.openUrl("https://github.com/jason7773/hushtype/releases") })
            addView(ui.secondaryButton("清除統計", Icon.TRASH) {
                Stats.clear(activity)
                activity.toast("已清除使用統計")
            })
        })
    }
}
