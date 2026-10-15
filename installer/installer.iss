; Inno Setup 6/7 script for EZ Bulk Rename by EZKerja.
; Built by build.py, which passes /DAppVersion from ezrename/__init__.py.
; Manual build:  ISCC /DAppVersion=1.0.0 installer\installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#define AppName      "EZ Bulk Rename"
#define AppExe       "EZ Bulk Rename.exe"
#define Publisher    "EZKerja"
#define PublisherURL "https://www.ezkerja.com"

[Setup]
; Never change AppId after the first public release: it's how upgrades find the old install.
AppId={{E70C19B9-3D76-49F9-918F-EA749FDA5DDB}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL={#PublisherURL}
AppSupportURL={#PublisherURL}
AppCopyright=Copyright 2026 EZKerja
VersionInfoCompany=Aztech AI Corp
VersionInfoDescription={#AppName} Setup
VersionInfoVersion={#AppVersion}

; Per-user install by default: no admin prompt, which office PCs often block.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={autopf}\EZKerja\{#AppName}
DefaultGroupName=EZKerja
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

OutputDir=..\dist
OutputBaseFilename=EZ-Bulk-Rename-Setup-{#AppVersion}
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

; Code signing (later). After you get a certificate, configure a sign tool named
; "signtool" in the Inno Setup IDE (Tools > Configure Sign Tools) and uncomment:
; SignTool=signtool
; SignedUninstaller=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "sendto"; Description: "Add EZ Bulk Rename to the right-click Send to menu"; GroupDescription: "File Explorer:"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
; Right-click files or folders > Send to > EZ Bulk Rename. This is only a shortcut in the user's
; own SendTo folder: no registry keys, removed again on uninstall.
Name: "{usersendto}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: sendto

; No file associations and no Explorer context-menu registry keys, on purpose: EZ File
; Searcher's installer showed that registry keys on every file or folder can trip Microsoft
; Defender's machine learning. "Send to" above gives the same right-click route without them.

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
