; Inno Setup Script für Universal Downloader
; Erstellt Installer mit Startmenü, optional Desktop/Taskleiste, Deinstaller
; Vor dem Kompilieren: zuerst build_windows.py ausführen, dann: iscc installer.iss
; Oder: python build_installer.py (macht beides und setzt Version)

#define MyAppName "Universal Downloader"
#define MyAppExe "UniversalDownloader.exe"
#define MyAppPublisher "Universal Downloader"
; Version wird von build_installer.py eingetragen (Suche nach 0.0.0 und ersetze)
#define MyAppVersion "0.0.0"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; Installation ohne Admin: Benutzerordner (empfohlen, kein UAC)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=dist_installer
OutputBaseFilename=UniversalDownloader_Setup_v{#MyAppVersion}
; Eigenes Icon nur, wenn icon.ico im Projektordner liegt
#ifexist "icon.ico"
SetupIconFile=icon.ico
#endif
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardImageFile=compiler:WizClassicImage.bmp
WizardSmallImageFile=compiler:WizClassicSmallImage.bmp
; Deutsche Oberfläche
ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem &Desktop erstellen"; GroupDescription: "Zusätzliche Verknüpfungen:"
Name: "taskbarpin"; Description: "An &Taskleiste anheften (Verknüpfung anheften)"; GroupDescription: "Zusätzliche Verknüpfungen:"

[Files]
; Onedir-Build (schneller Start, kein Entpacken bei jedem Start)
#ifexist "dist\UniversalDownloader\UniversalDownloader.exe"
Source: "dist\UniversalDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
#else
Source: "dist\UniversalDownloader.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif
; yt-dlp Standalone-EXE (damit Download auch ohne System-Python läuft, z. B. Sandbox)
#ifexist "dist\yt-dlp.exe"
Source: "dist\yt-dlp.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif
; Gebündeltes Python (Embeddable + yt-dlp) – falls von build_installer.py erstellt
#ifexist "dist\python_embed\python.exe"
Source: "dist\python_embed\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
; ffmpeg mit ausliefern (wird von build_installer.py nach dist\ffmpeg geladen)
#ifexist "dist\ffmpeg\bin\ffmpeg.exe"
Source: "dist\ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs
#endif
; Optional: Icon für Verknüpfungen (falls nicht in EXE eingebettet)
; Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Startmenü – immer (WorkingDir: "{app}" damit EXE und ffmpeg gefunden werden)
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Comment: "Universal Downloader starten"; IconFilename: "{app}\{#MyAppExe}"
Name: "{group}\Universal Downloader deinstallieren"; Filename: "{uninstallexe}"; Comment: "Programm entfernen"
; Desktop – nur wenn Aufgabe gewählt
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Tasks: desktopicon; Comment: "Universal Downloader"; IconFilename: "{app}\{#MyAppExe}"

[Run]
; Programm nach Installation starten (optional, direkt nutzbar)
Filename: "{app}\{#MyAppExe}"; Description: "&Programm jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
// Optional: Nach Installation Taskleisten-Verknüpfung anlegen (falls Quick Launch / TaskBar-Ordner existiert)
procedure CurStepChanged(CurStep: TSetupStep);
var
  TaskBarPath: string;
  Shell, Link: Variant;
begin
  if CurStep = ssPostInstall then
  begin
    if WizardIsTaskSelected('taskbarpin') then
    begin
      TaskBarPath := ExpandConstant('{userappdata}') + '\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar';
      if DirExists(TaskBarPath) then
      begin
        try
          Shell := CreateOleObject('WScript.Shell');
          Link := Shell.CreateShortcut(TaskBarPath + '\Universal Downloader.lnk');
          Link.TargetPath := ExpandConstant('{app}\{#MyAppExe}');
          Link.WorkingDirectory := ExpandConstant('{app}');
          Link.Description := 'Universal Downloader';
          Link.Save;
        except
          // Fehler still ignorieren – Nutzer kann manuell anheften
        end;
      end;
    end;
  end;
end;
