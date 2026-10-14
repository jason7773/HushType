# dictate

Windows 語音輸入工具：在任何程式裡按住快捷鍵說話，放開後自動辨識、整理文字，貼到游標位置。

- 常駐系統匣，圖示顏色顯示狀態（藍：待命、紅：錄音中、黃：處理中、灰：暫停或需要設定）
- 錄音時螢幕下方正中間出現小視窗，五條音波跟著聲音跳動；放開後顯示「轉譯中」，貼上後自動消失
- 淺色／深色模式，可跟隨 Windows 或手動切換
- 所有設定都在程式視窗內完成：快捷鍵、麥克風、服務、模型、整理規則、詞彙、開機自動啟動
- 使用統計儀表板：每天、每月的使用時間、字數、估計省下的時間
- 語音辨識與文字整理目前接 **Groq**，也可以換成任何 OpenAI 相容服務（包括在自己電腦跑的模型）

## 隱私

- 錄音只放在記憶體，不寫入硬碟
- 預設不顯示、不保存辨識出的文字
- API 金鑰存在 Windows 認證管理員，不寫進設定檔
- 使用統計只記錄時間與字數，不含任何內容，存在 `%APPDATA%\dictate\usage.db`
- 只有語音與逐字稿會送到你在設定頁選擇的服務，沒有其他任何連線

## 安裝與更新

1. 到 [Releases](../../releases) 下載最新的 `dictate-setup-x.y.z.exe`
2. 執行安裝檔（不需要系統管理員權限）
3. 打開 dictate，到「設定」頁貼上 [Groq API 金鑰](https://console.groq.com/keys)，按「儲存」

**更新**：下載新版安裝檔直接執行即可，會自動關閉舊版並覆蓋，設定與統計都會保留，不需要先解除安裝。

### 程式碼簽章（自簽憑證）

在自己的電腦執行一次 `packaging\setup-signing.bat`，它會：

1. 建立一張只屬於你的程式碼簽章憑證（有效 5 年）
2. 讓這台電腦信任它（Windows 會跳出確認視窗，按「是」）
3. 引導你把憑證存到 GitHub Secrets，之後自動打包的安裝檔都會簽上你的名字

自簽憑證只有在匯入過的電腦上被信任。從瀏覽器下載的檔案第一次執行時，Windows SmartScreen 仍可能提示「已保護您的電腦」，按「其他資訊 → 仍要執行」即可；或在檔案上按右鍵 →「內容」→ 勾選「解除封鎖」。

## 發佈新版

把 `dictate/__init__.py` 的 `__version__` 改成新版本號並推到 `main`，GitHub 就會自動打包、建立 `v版本號` 的 Release。

版本號沒變的 commit 也會打包，安裝檔放在 Actions 的 Artifacts（版本號加上 `-dev.N`）。

## 開發

```
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt pytest
.venv\Scripts\pythonw dictate.pyw            # 開啟應用程式
.venv\Scripts\python -m dictate --console    # 在 terminal 執行（除錯用）
.venv\Scripts\python -m pytest
```

本機打包需要 [Inno Setup 6](https://jrsoftware.org/isdl.php) 與 `pip install pyinstaller`，然後執行 `pwsh packaging\build.ps1 -Version 0.2.0`。

### 架構

```
dictate/
  engine.py       快捷鍵、錄音、處理、貼上；以事件回報狀態（介面與主控台共用）
  pipeline.py     辨識 → 繁體 → LLM 整理 → 替換（與平台無關）
  providers/      服務介面、註冊表與各家實作
  audio.py        麥克風錄音，輸出記憶體中的 WAV
  output.py       剪貼簿貼上或模擬打字
  config.py       設定檔讀寫與預設整理規則
  keystore.py     API 金鑰存取（Windows 認證管理員）
  autostart.py    開機自動啟動
  stats.py        本機使用紀錄（SQLite）與彙總
  dashboard.py    匯出 HTML 統計報表
  gui/            主視窗、系統匣、錄音小視窗、狀態／設定／統計頁
packaging/        PyInstaller + Inno Setup 打包、簽章腳本
```

### 新增其他服務

OpenAI 相容的服務在設定頁選「其他 OpenAI 相容服務」並填網址即可。其他服務在 `dictate/providers/` 新增模組：

```python
from .base import SpeechToText, register_stt

@register_stt("azure")
class AzureSTT(SpeechToText):
    def __init__(self, region: str, api_key_env: str = "AZURE_SPEECH_KEY", **kw): ...
    def transcribe(self, wav: bytes, *, prompt: str | None = None) -> str: ...
```

再到 `dictate/providers/__init__.py` 匯入它。文字整理服務同理，用 `TextCleaner` 與 `@register_cleaner`。

## 作者

[@jason7773](https://github.com/jason7773)（抹茶），與 Claude 協作開發。
