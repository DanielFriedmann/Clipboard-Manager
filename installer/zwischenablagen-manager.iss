; Installer für den Zwischenablagen Manager (Inno Setup 7)

#define MyAppName "Zwischenablagen Manager"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "dadanschel"
#define MyAppExeName "Zwischenablagen-Manager.exe"
; muss zum Namen in single_instance.py passen (ohne "Local\")
#define MyAppMutex "Abkoo.Zwischenablagen.Manager"

[Setup]
; Eindeutige Kennung, NIE ändern. Erste Klammer doppelt, letzte einfach.
AppId={{B5A469AA-EA94-4DAE-BFEB-B00931C8C895}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
AppMutex={#MyAppMutex}
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=..\installer_output
OutputBaseFilename=Zwischenablagen-Manager-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "Beim Anmelden automatisch starten"; GroupDescription: "Autostart:"; Flags: unchecked

[Files]
Source: "..\dist\Zwischenablagen-Manager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
// Beim Deinstallieren fragen, ob die gespeicherten Daten gelöscht werden sollen
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\ClipboardManager');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Sollen auch Ihre gespeicherten Einträge, Gruppen und Einstellungen gelöscht werden?'
                + #13#10#13#10 + 'Die Daten sind verschlüsselt und können danach nicht wiederhergestellt werden.'
                + #13#10#13#10 + DataDir,
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;