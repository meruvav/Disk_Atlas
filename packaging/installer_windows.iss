; Disk Atlas — Windows Installer (Inno Setup)
;
; Single source of installer truth for Windows. Replaces the old
; PyInstaller/tkinter setup wizard (installer.py + DiskAtlas_Setup.spec).
;
; Built by packaging/build_windows.py, which passes /DMyAppVersion.
; Requires Inno Setup 6.3+ (ArchitecturesInstallIn64BitMode=x64compatible).
; Can also be compiled standalone with Inno Setup 6:
;   iscc /DMyAppVersion=2.0.0 packaging\installer_windows.iss
;
; The AppId GUID below identifies Disk Atlas to Windows for upgrades and
; uninstall. NEVER change it after the first public release.

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif

#define MyAppName "Disk Atlas"
#define MyAppPublisher "Meruva"
#define MyAppURL "https://github.com/meruvav/Disk_Atlas"
#define MyAppExeName "DiskAtlas.exe"

[Setup]
AppId={{99D5FC4C-325C-4321-BB58-B844F375B96C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Where the setup executable lands
OutputDir=..\dist
OutputBaseFilename=DiskAtlas_Setup_{#MyAppVersion}
SetupIconFile=assets\diskatlas.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Install location: per-machine Program Files by default, with a dialog
; option to install per-user (no admin required).
DefaultDirName={autopf}\DiskAtlas
DefaultGroupName={#MyAppName}
PrivilegesRequiredOverridesAllowed=dialog

; Metadata shown in Windows Settings > Apps and the setup exe Properties
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=MIT License

; Compression & behavior
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
WizardStyle=modern
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible
DisableDirPage=no
DisableProgramGroupPage=yes

; Upgrade hygiene: close a running Disk Atlas via Restart Manager and
; relaunch it afterwards if it was running.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\DiskAtlas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove stale caches created under the install dir; user data, logs and
; lock files live in %LOCALAPPDATA%\DiskAtlas and are intentionally kept
; so settings and logs survive reinstalls.
Type: filesandordirs; Name: "{app}\__pycache__"
