; Hushtype 安裝程式（Inno Setup 6）
; 安裝到目前使用者的資料夾，不需要系統管理員權限。
; AppId 固定不變，新版安裝檔會直接覆蓋舊版；設定與統計存在 %APPDATA%\Hushtype，不受影響。
; 程式原名 dictate；AppId 沿用，舊版會直接升級成 Hushtype。

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0F5C8E-3E54-4F0B-9C2A-1D7A3E5B9F21}
AppName=Hushtype
AppVersion={#MyAppVersion}
AppVerName=Hushtype {#MyAppVersion}
AppPublisher=jason7773
DefaultDirName={localappdata}\Programs\Hushtype
DefaultGroupName=Hushtype
UsePreviousGroup=no
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Hushtype-setup-{#MyAppVersion}
SetupIconFile=..\assets\hushtype.ico
UninstallDisplayIcon={app}\Hushtype.exe
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
Source: "..\dist\Hushtype\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; 清掉舊版留下的程式檔，避免新舊版本混在一起
Type: filesandordirs; Name: "{app}\_internal"
; 改名前留下的執行檔與捷徑
Type: files; Name: "{app}\dictate.exe"
Type: files; Name: "{autodesktop}\dictate.lnk"
Type: filesandordirs; Name: "{userprograms}\dictate"

[Icons]
Name: "{group}\Hushtype"; Filename: "{app}\Hushtype.exe"
Name: "{autodesktop}\Hushtype"; Filename: "{app}\Hushtype.exe"; Tasks: desktopicon

[Registry]
; 不建立開機啟動（由程式內的開關控制），只在解除安裝時順便移除
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "Hushtype"; ValueType: none; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Hushtype.exe"; Description: "立即啟動 Hushtype"; Flags: nowait postinstall skipifsilent
; 從程式內更新時（安靜安裝並帶 /RELAUNCH），裝完自動重新開啟
Filename: "{app}\Hushtype.exe"; Flags: nowait; Check: ShouldRelaunch

[Code]
function ShouldRelaunch: Boolean;
begin
  Result := Pos('/RELAUNCH', UpperCase(GetCmdTail)) > 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  // 更新前先結束正在執行的程式（含改名前的 dictate.exe）
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Hushtype.exe /im dictate.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
    Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Hushtype.exe /im dictate.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
