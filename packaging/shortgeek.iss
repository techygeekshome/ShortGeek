; Inno Setup script for ShortGeek.
;
; Installs per-user into LOCALAPPDATA, so no administrator rights are needed and
; the app can write its own data folder. The version is passed in by the build
; workflow with /DMyAppVersion so the installer and the app can never disagree.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName    "ShortGeek"
#define MyAppExeName "ShortGeek.exe"
#define MyPublisher  "TechyGeeksHome"
#define MyAppURL     "https://techygeekshome.info/shortgeek/"

[Setup]
AppId={{3F7B2C91-6D48-4A15-9E33-0B7C5A2E81D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL=https://github.com/techygeekshome/ShortGeek/issues
AppUpdatesURL=https://github.com/techygeekshome/ShortGeek/releases
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=ShortGeekSetup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
LicenseFile=..\LICENSE
UninstallDisplayName={#MyAppName} {#MyAppVersion}
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} installer

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\ShortGeek\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Only the install folder. The user's settings, clips and rendered videos live in
; {localappdata}\ShortGeek and are deliberately left behind on uninstall, so a
; reinstall or an upgrade does not throw away their work.
Type: filesandordirs; Name: "{app}\_internal"
