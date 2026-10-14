# 建立 Hushtype 專用的自簽程式碼簽章憑證，讓這台電腦信任它，
# 並產生要貼到 GitHub 的兩個 Secret（CERT_PFX_BASE64、CERT_PASSWORD）。
# 私鑰只存在你的電腦與你的 GitHub Secrets，不會出現在程式碼裡。

$ErrorActionPreference = "Stop"
$subject = "CN=Hushtype (jason7773)"

$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq $subject -and $_.NotAfter -gt (Get-Date) -and $_.HasPrivateKey } |
    Select-Object -First 1
if ($cert) {
    Write-Host "使用已存在的憑證（到期日 $($cert.NotAfter.ToString('yyyy-MM-dd'))）"
} else {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $subject `
        -CertStoreLocation Cert:\CurrentUser\My -KeyExportPolicy Exportable `
        -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 `
        -NotAfter (Get-Date).AddYears(5) -FriendlyName "Hushtype 程式碼簽章"
    Write-Host "已建立新憑證（有效 5 年）"
}

# 讓這台電腦信任這張憑證。匯入「受信任的根憑證」時 Windows 會跳出確認視窗，請按「是」。
$cer = Join-Path $env:TEMP "hushtype.cer"
Export-Certificate -Cert $cert -FilePath $cer | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\TrustedPublisher | Out-Null
Remove-Item $cer
Write-Host "這台電腦已信任 Hushtype 的簽章"

# 產生 GitHub Secrets
$password = [guid]::NewGuid().ToString("N")
$pfx = Join-Path $env:TEMP "hushtype.pfx"
Export-PfxCertificate -Cert $cert -FilePath $pfx -Password (ConvertTo-SecureString $password -AsPlainText -Force) | Out-Null
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($pfx))
Remove-Item $pfx

$url = "https://github.com/jason7773/hushtype/settings/secrets/actions/new"
Write-Host ""
Write-Host "接下來要在 GitHub 新增兩個 Secret：$url"
Start-Process $url

Set-Clipboard -Value $b64
Write-Host ""
Write-Host "1) 第一個 Secret 的內容已複製到剪貼簿。"
Write-Host "   Name 填 CERT_PFX_BASE64，Secret 欄位貼上，按 Add secret。"
Read-Host "   完成後按 Enter"

Set-Clipboard -Value $password
Write-Host "2) 第二個 Secret 的內容已複製到剪貼簿。"
Write-Host "   再按一次 New repository secret，Name 填 CERT_PASSWORD，Secret 欄位貼上，按 Add secret。"
Read-Host "   完成後按 Enter"

Set-Clipboard -Value " "
Write-Host ""
Write-Host "全部完成，剪貼簿已清空。之後打包的安裝檔都會簽上你的憑證。"
Read-Host "按 Enter 關閉"
