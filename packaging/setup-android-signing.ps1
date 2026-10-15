# 建立 Hushtype Android 版專用的簽章金鑰，並產生要貼到 GitHub 的兩個 Secret
# （ANDROID_KEYSTORE_BASE64、ANDROID_KEYSTORE_PASSWORD）。
# 之後每一版 APK 都用同一把金鑰簽章，手機上才能直接覆蓋安裝、保留設定。
# 私鑰只存在你的電腦（Windows 憑證存放區）與你的 GitHub Secrets，不會出現在程式碼裡。

$ErrorActionPreference = "Stop"
$subject = "CN=Hushtype Android (jason7773)"

$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $subject -and $_.NotAfter -gt (Get-Date) -and $_.HasPrivateKey } |
    Select-Object -First 1
if ($cert) {
    Write-Host "使用已存在的 Android 簽章金鑰（到期日 $($cert.NotAfter.ToString('yyyy-MM-dd'))）"
} else {
    $cert = New-SelfSignedCertificate -Type Custom -Subject $subject -KeyUsage DigitalSignature `
        -CertStoreLocation Cert:\CurrentUser\My -KeyExportPolicy Exportable `
        -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(30) -FriendlyName "hushtype"
    Write-Host "已建立新的 Android 簽章金鑰（有效 30 年）"
}

$password = [guid]::NewGuid().ToString("N")
$pfx = Join-Path $env:TEMP "hushtype-android.pfx"
Export-PfxCertificate -Cert $cert -FilePath $pfx -CryptoAlgorithmOption AES256_SHA256 `
    -Password (ConvertTo-SecureString $password -AsPlainText -Force) | Out-Null
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($pfx))
Remove-Item $pfx

$url = "https://github.com/jason7773/hushtype/settings/secrets/actions/new"
Write-Host ""
Write-Host "接下來要在 GitHub 新增兩個 Secret：$url"
Start-Process $url

Set-Clipboard -Value $b64
Write-Host ""
Write-Host "1) 第一個 Secret 的內容已複製到剪貼簿。"
Write-Host "   Name 填 ANDROID_KEYSTORE_BASE64，Secret 欄位貼上，按 Add secret。"
Read-Host "   完成後按 Enter"

Set-Clipboard -Value $password
Write-Host "2) 第二個 Secret 的內容已複製到剪貼簿。"
Write-Host "   再按一次 New repository secret，Name 填 ANDROID_KEYSTORE_PASSWORD，Secret 欄位貼上，按 Add secret。"
Read-Host "   完成後按 Enter"

Set-Clipboard -Value " "
Write-Host ""
Write-Host "全部完成，剪貼簿已清空。之後建置的 Android 版都會用這把金鑰簽章。"
Write-Host "請不要刪除 Windows 憑證裡的「hushtype」，換電腦前可以再執行一次這個檔案確認金鑰還在。"
Read-Host "按 Enter 關閉"
