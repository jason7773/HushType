# 第三方軟體授權聲明

Hushtype（悄聲）本身以 [MIT 授權](LICENSE) 釋出。安裝檔內附帶下列第三方元件，各自依其授權條款使用。

| 元件 | 用途 | 授權 |
|---|---|---|
| [Python](https://www.python.org/) | 執行環境 | PSF License |
| [Qt for Python (PySide6)](https://doc.qt.io/qtforpython/) | 介面 | LGPL-3.0 |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) 與 [PortAudio](http://www.portaudio.com/) | 錄音 | MIT |
| [pyperclip](https://github.com/asweigart/pyperclip) | 剪貼簿 | BSD-3-Clause |
| [Requests](https://github.com/psf/requests) | 呼叫 API | Apache-2.0 |
| [opencc-python-reimplemented](https://github.com/yichen0831/opencc-python) 與 OpenCC 字典 | 簡轉繁 | Apache-2.0 |
| [keyring](https://github.com/jaraco/keyring) | 存取 Windows 認證管理員 | MIT |
| [comtypes](https://github.com/enthought/comtypes) | UI Automation（判斷輸入框） | MIT |
| [PyInstaller](https://pyinstaller.org/) 啟動程式 | 打包 | GPL-2.0，附 bootloader 例外條款（可用於任何授權的程式） |
| [Inno Setup](https://jrsoftware.org/isinfo.php) | 安裝程式 | Inno Setup License |
| Inno Setup 繁體中文語言檔 | 安裝畫面翻譯 | 原作者署名保留於 `packaging/ChineseTraditional.isl` |

## 關於 Qt（LGPL-3.0）

安裝後的 `_internal` 資料夾內，Qt 與 PySide6 以獨立的動態連結程式庫（.dll / .pyd）存在，你可以用相容版本自行替換。
Qt 的原始碼可在 <https://download.qt.io/> 取得，授權全文見 <https://www.gnu.org/licenses/lgpl-3.0.html>。
