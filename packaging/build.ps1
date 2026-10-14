# 打包 dictate：PyInstaller → 簽章 → Inno Setup 安裝檔 → 簽章
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
$init = "dictate\__init__.py"
(Get-Content $init -Raw) -replace '__version__ = ".*"', "__version__ = `"$Version`"" |
    Set-Content $init -NoNewline -Encoding utf8

# 1. 先產生 UI Automation 的 COM 介面（判斷有沒有輸入框用），再打包成 dist\dictate\dictate.exe
python -c "import comtypes.client; comtypes.client.GetModule('UIAutomationCore.dll')"
if ($LASTEXITCODE) { throw "無法產生 UI Automation 介面" }
python -m PyInstaller --noconfirm --clean --windowed `
    --name dictate `
    --icon assets\dictate.ico `
    --collect-data opencc `
    --hidden-import keyring.backends.Windows `
    --collect-submodules comtypes.gen `
    --distpath dist --workpath build `
    dictate.pyw
if ($LASTEXITCODE) { throw "PyInstaller 失敗" }
Sign-File "dist\dictate\dictate.exe"

# 2. 安裝檔
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $iscc)) {
    choco install innosetup -y --no-progress | Out-Host
}
& $iscc "/DMyAppVersion=$Version" "packaging\dictate.iss"
if ($LASTEXITCODE) { throw "Inno Setup 失敗" }
Sign-File "dist\dictate-setup-$Version.exe"
