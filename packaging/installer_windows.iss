[Setup]
AppName=Disk Atlas
AppVersion=2.0
DefaultDirName={autopf}\DiskAtlas
DefaultGroupName=Disk Atlas
OutputDir=..\dist
OutputBaseFilename=DiskAtlas_Inno_Setup
Compression=lzma
SolidCompression=yes
DisableDirPage=no
UninstallDisplayIcon={app}\DiskAtlas.exe
UninstallDisplayName=Disk Atlas

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\DiskAtlas\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Disk Atlas"; Filename: "{app}\DiskAtlas.exe"
Name: "{autodesktop}\Disk Atlas"; Filename: "{app}\DiskAtlas.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DiskAtlas.exe"; Description: "{cm:LaunchProgram,Disk Atlas}"; Flags: nowait postinstall skipifsilent
