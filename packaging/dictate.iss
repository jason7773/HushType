; dictate 安裝程式（Inno Setup 6）
; 安裝到目前使用者的資料夾，不需要系統管理員權限。
; AppId 固定不變，新版安裝檔會直接覆蓋舊版；設定與統計存在 %APPDATA%\dictate，不受影響。

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0F5C8E-3E54-4F0B-9C2A-1D7A3E5B9F21}
AppName=dictate
AppVersion={#MyAppVersion}
AppVerName=dictate {#MyAppVersion}
AppPublisher=jason7773
DefaultDirName={localappdata}\Programs\dictate
DefaultGroupName=dictate
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=dictate-setup-{#MyAppVersion}
SetupIconFile=..\assets\dictate.ico
UninstallDisplayIcon={app}\dictate.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no
ShowLanguageDialog=no

[Languages]
Name: "chinesetraditional"; MessagesFile: "ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "其他："

[Files]
Source: "..\dist\dictate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; 清掉舊版留下的程式檔，避免新舊版本混在一起
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\dictate"; Filename: "{app}\dictate.exe"
Name: "{autodesktop}\dictate"; Filename: "{app}\dictate.exe"; Tasks: desktopicon

[Registry]
; 不建立開機啟動（由程式內的開關控制），只在解除安裝時順便移除
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "dictate"; ValueType: none; Flags: uninsdeletevalue

[Run]
Filename: "{app}\dictate.exe"; Description: "立即啟動 dictate"; Flags: nowait postinstall skipifsilent
; 從程式內更新時（安靜安裝並帶 /RELAUNCH），裝完自動重新開啟
Filename: "{app}\dictate.exe"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := Pos('/RELAUNCH', UpperCase(GetCmdTail)) > 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // 更新前先結束正在執行的 dictate
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im dictate.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im dictate.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
