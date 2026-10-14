# 打包 Hushtype：PyInstaller → 簽章 → Inno Setup 安裝檔 → 簽章
# 用法：pwsh packaging/build.ps1 -Version 0.2.0
# 有設定環境變數 CERT_PFX_BASE64 與 CERT_PASSWORD 時才會簽章。
param([string]$Version = "0.0.0")

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot
Set-Location $root

function Sign-File([string]$Path) {
    if (-not $env:CERT_PFX_BASE64) {
        Write-Warning "沒有設定簽章憑證，$Path 未簽章"
        return
    }
    $bytes = [Convert]::FromBase64String($env:CERT_PFX_BASE64)
    $cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new(
        $bytes, $env:CERT_PASSWORD,
        [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable)
    $sig = Set-AuthenticodeSignature -FilePath $Path -Certificate $cert -HashAlgorithm SHA256 `
        -TimestampServer "http://timestamp.digicert.com"
    if ($sig.Status -notin @("Valid", "UnknownError")) {
        # UnknownError 代表自簽憑證在打包機上不受信任，但簽章本身已寫入
        throw "簽章失敗：$($sig.StatusMessage)"
    }
    Write-Host "已簽章：$Path"
}

# 寫入版本號
$init = "hushtype\__init__.py"
(Get-Content $init -Raw) -replace '__version__ = ".*"', "__version__ = `"$Version`"" |
    Set-Content $init -NoNewline -Encoding utf8

# 1. 先產生 UI Automation 的 COM 介面（判斷有沒有輸入框用），再打包成 dist\Hushtype\Hushtype.exe
python -c "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"
if ($LASTEXITCODE) { throw "無法產生 UI Automation 介面" }
python -m PyInstaller --noconfirm --clean --windowed `
    --name Hushtype `
    --icon assets\hushtype.ico `
    --collect-data opencc `
    --hidden-import keyring.backends.Windows `
    --collect-submodules comtypes.gen `
    --exclude-module numpy `
    --exclude-module PySide6.QtNetwork `
    --exclude-module tkinter `
    --distpath dist --workpath build `
    hushtype.pyw
if ($LASTEXITCODE) { throw "PyInstaller 失敗" }

# 拿掉用不到的 Qt 檔案：軟體 OpenGL、翻譯檔、圖片格式與其他外掛（介面全部是自己畫的）
$qt = "dist\Hushtype\_internal\PySide6"
$unused = @(
    "$qt\opengl32sw.dll", "$qt\translations", "$qt\Qt6Network.dll", "$qt\Qt6Pdf.dll",
    "$qt\Qt6Qml.dll", "$qt\Qt6QmlModels.dll", "$qt\Qt6Quick.dll", "$qt\Qt6Svg.dll", "$qt\Qt6VirtualKeyboard.dll",
    "$qt\plugins\imageformats", "$qt\plugins\tls", "$qt\plugins\networkinformation",
    "$qt\plugins\generic", "$qt\plugins\iconengines", "$qt\plugins\platforminputcontexts",
    "$qt\plugins\styles",
    # Qt 網路模組自帶的 OpenSSL（Python 連線用的是另一份 libssl-3.dll / libcrypto-3.dll，要保留）
    "dist\Hushtype\_internal\libcrypto-3-x64.dll", "dist\Hushtype\_internal\libssl-3-x64.dll"
)
foreach ($path in $unused) {
    if (Test-Path $path) { Remove-Item $path -Recurse -Force; Write-Host "已移除 $path" }
}
# 只留下 Windows 平台外掛
Get-ChildItem "$qt\plugins\platforms" -Filter *.dll | Where-Object Name -ne "qwindows.dll" | Remove-Item -Force
Sign-File "dist\Hushtype\Hushtype.exe"

# 2. 安裝檔
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    choco install innosetup -y --no-progress | Out-Host
}
& $iscc "/DMyAppVersion=$Version" "packaging\hushtype.iss"
if ($LASTEXITCODE) { throw "Inno Setup 失敗" }
Sign-File "dist\Hushtype-setup-$Version.exe"

# 改名前的版本（dictate 0.5.x）只認得 dictate-setup-*.exe，多放一份同樣的安裝檔讓它們也能自動更新
Copy-Item "dist\Hushtype-setup-$Version.exe" "dist\dictate-setup-$Version.exe"
