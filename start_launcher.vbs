Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("Shell.Application")

' Hole das Verzeichnis der .vbs Datei
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = scriptPath & "\start.py"

' Finde Icon-Datei (icon.ico oder icon.png)
Dim iconPath
iconPath = ""
If fso.FileExists(scriptPath & "\icon.ico") Then
    iconPath = scriptPath & "\icon.ico"
ElseIf fso.FileExists(scriptPath & "\icon.png") Then
    iconPath = scriptPath & "\icon.png"
End If

' Log-Datei Setup - IMMER ins Arbeitsverzeichnis
Dim logFile, logStream
logFile = scriptPath & "\vbs.log.txt"
On Error Resume Next
Set logStream = fso.OpenTextFile(logFile, 8, True)
If Err.Number <> 0 Then
    ' Versuche es nochmal mit explizitem Pfad
    Err.Clear
    Set logStream = fso.OpenTextFile(logFile, 2, True) ' 2 = ForWriting, True = Create
    If Err.Number <> 0 Then
        ' Fallback zu Temp nur wenn wirklich nötig
        logFile = WshShell.ExpandEnvironmentStrings("%TEMP%\vbs.log.txt")
        Set logStream = fso.OpenTextFile(logFile, 8, True)
    End If
End If
On Error Goto 0

Sub WriteLog(message)
    On Error Resume Next
    Dim timestamp
    timestamp = Now()
    If Not logStream Is Nothing Then
        logStream.WriteLine "[" & timestamp & "] " & message
        ' Flush sofort (schließe und öffne neu)
        logStream.Close
        Set logStream = fso.OpenTextFile(logFile, 8, True)
    End If
    On Error Goto 0
End Sub

WriteLog "=========================================="
WriteLog "Launcher gestartet: " & WScript.ScriptFullName
WriteLog "Verzeichnis: " & scriptPath
WriteLog "Log-Datei: " & logFile
If iconPath <> "" Then
    WriteLog "[INFO] Icon gefunden: " & iconPath
Else
    WriteLog "[WARNING] Kein Icon gefunden"
End If

' Shortcut wird nach Python-Suche erstellt (siehe weiter unten)
Dim shortcutPath
shortcutPath = scriptPath & "\Universal Downloader.lnk"

' Prüfe ob start.py existiert
If Not fso.FileExists(pythonScript) Then
    WriteLog "[ERROR] start.py nicht gefunden in: " & scriptPath
    MsgBox "start.py nicht gefunden in: " & scriptPath, vbCritical, "Fehler"
    If Not logStream Is Nothing Then logStream.Close
    WScript.Quit
End If
WriteLog "[OK] start.py gefunden: " & pythonScript

' Prüfe ob requirements.txt existiert
Dim requirementsFile
requirementsFile = scriptPath & "\requirements.txt"
If fso.FileExists(requirementsFile) Then
    WriteLog "[OK] requirements.txt gefunden: " & requirementsFile
Else
    WriteLog "[WARNING] requirements.txt nicht gefunden: " & requirementsFile
End If

' Versuche Python zu finden (auf allen Laufwerken)
pythonExe = ""
WriteLog "[INFO] =========================================="
WriteLog "[INFO] Starte Python-Suche auf allen Laufwerken..."
WriteLog "[INFO] =========================================="
On Error Resume Next

' Methode 1: PATH
WriteLog "[INFO] Methode 1: Prüfe pythonw.exe im PATH..."
Set pythonCheck = WshShell.Exec("pythonw.exe --version")
Dim pythonOutput
pythonOutput = pythonCheck.StdOut.ReadAll
pythonCheck.WaitOnReturn = True
WriteLog "[INFO] pythonw.exe --version Ausgabe: " & pythonOutput
WriteLog "[INFO] pythonw.exe --version Exit-Code: " & pythonCheck.ExitCode
If pythonCheck.ExitCode = 0 Then
    pythonExe = "pythonw.exe"
    WriteLog "[OK] Python gefunden (Methode 1): pythonw.exe im PATH"
Else
    WriteLog "[INFO] pythonw.exe nicht im PATH gefunden"
    ' Methode 2: python.exe im PATH
    Err.Clear
    WriteLog "[INFO] Methode 2: Prüfe python.exe im PATH..."
    Set pythonCheck2 = WshShell.Exec("python.exe --version")
    Dim pythonOutput2
    pythonOutput2 = pythonCheck2.StdOut.ReadAll
    pythonCheck2.WaitOnReturn = True
    WriteLog "[INFO] python.exe --version Ausgabe: " & pythonOutput2
    WriteLog "[INFO] python.exe --version Exit-Code: " & pythonCheck2.ExitCode
    If pythonCheck2.ExitCode = 0 Then
        pythonExe = "python.exe"
        WriteLog "[OK] Python gefunden (Methode 2): python.exe im PATH"
    Else
        WriteLog "[INFO] python.exe nicht im PATH gefunden"
        ' Methode 3: Typische Installationspfade
        Err.Clear
        WriteLog "[INFO] Methode 3: Suche in typischen Installationspfaden..."
        Dim searchPaths, searchPath, folder, subfolder
        searchPaths = Array( _
            WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
            WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Microsoft\WindowsApps"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python") _
        )
        
        For Each searchPath In searchPaths
            WriteLog "[INFO] Prüfe Pfad: " & searchPath
            If fso.FolderExists(searchPath) Then
                Set folder = fso.GetFolder(searchPath)
                If fso.FileExists(searchPath & "\pythonw.exe") Then
                    pythonExe = searchPath & "\pythonw.exe"
                    WriteLog "[OK] Python gefunden (Methode 3): " & pythonExe
                    Exit For
                End If
                For Each subfolder In folder.SubFolders
                    If fso.FileExists(subfolder.Path & "\pythonw.exe") Then
                        pythonExe = subfolder.Path & "\pythonw.exe"
                        WriteLog "[OK] Python gefunden (Methode 3): " & pythonExe
                        Exit For
                    End If
                Next
                If pythonExe <> "" Then Exit For
            End If
        Next
        
        ' Methode 4: Registry
        If pythonExe = "" Then
            Err.Clear
            WriteLog "[INFO] Methode 4: Prüfe Registry..."
            Dim reg, execPath
            On Error Resume Next
            ' Prüfe verschiedene Python-Versionen
            Dim versions
            versions = Array("3.11", "3.12", "3.13", "3.10", "3.9", "3.8")
            For Each version In versions
                reg = ""
                Err.Clear
                reg = WshShell.RegRead("HKEY_LOCAL_MACHINE\SOFTWARE\Python\PythonCore\" & version & "\InstallPath\ExecutablePath")
                If Err.Number = 0 And reg <> "" Then
                    WriteLog "[INFO] Registry-Eintrag gefunden (Python " & version & "): " & reg
                    execPath = fso.GetParentFolderName(reg)
                    If fso.FileExists(execPath & "\pythonw.exe") Then
                        pythonExe = execPath & "\pythonw.exe"
                        WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                        Exit For
                    ElseIf fso.FileExists(reg) Then
                        pythonExe = reg
                        WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                        Exit For
                    End If
                End If
            Next
            On Error Resume Next
        End If
        
        ' Methode 5: Suche auf ALLEN Laufwerken (C:, D:, E:, etc.)
        If pythonExe = "" Then
            Err.Clear
            WriteLog "[INFO] Methode 5: Suche auf allen Laufwerken..."
            Dim drives, drive, drivePath
            Set drives = fso.Drives
            For Each drive In drives
                If drive.IsReady And drive.DriveType = 2 Then ' Fixed Disk
                    drivePath = drive.DriveLetter & ":\"
                    WriteLog "[INFO] Prüfe Laufwerk: " & drivePath
                    ' Suche in typischen Pfaden
                    Dim altPaths
                    altPaths = Array( _
                        drivePath & "Program Files\Python", _
                        drivePath & "Program Files (x86)\Python", _
                        drivePath & "Python", _
                        drivePath & "Program Files\Python3", _
                        drivePath & "Program Files (x86)\Python3" _
                    )
                    For Each altPath In altPaths
                        If fso.FolderExists(altPath) Then
                            WriteLog "[INFO] Prüfe Pfad: " & altPath
                            If fso.FileExists(altPath & "\pythonw.exe") Then
                                pythonExe = altPath & "\pythonw.exe"
                                WriteLog "[OK] Python gefunden (Methode 5): " & pythonExe
                                Exit For
                            End If
                            ' Suche in Unterordnern (Python3.11, Python3.12, etc.)
                            Set folder = fso.GetFolder(altPath)
                            For Each subfolder In folder.SubFolders
                                If fso.FileExists(subfolder.Path & "\pythonw.exe") Then
                                    pythonExe = subfolder.Path & "\pythonw.exe"
                                    WriteLog "[OK] Python gefunden (Methode 5): " & pythonExe
                                    Exit For
                                End If
                            Next
                            If pythonExe <> "" Then Exit For
                        End If
                    Next
                    If pythonExe <> "" Then Exit For
                End If
            Next
            On Error Resume Next
        End If
    End If
End If
On Error Goto 0

' Falls Python nicht gefunden wurde, versuche Installation
If pythonExe = "" Then
    WriteLog "[WARNING] =========================================="
    WriteLog "[WARNING] Python nicht gefunden nach allen Suchmethoden"
    WriteLog "[WARNING] =========================================="
    Dim response
    response = MsgBox("Python nicht gefunden!" & vbCrLf & vbCrLf & _
           "Möchten Sie Python 3.11 automatisch herunterladen und installieren?" & vbCrLf & vbCrLf & _
           "Hinweis: Dies erfordert Administrator-Rechte.", _
           vbYesNo + vbQuestion + vbDefaultButton1, "Python installieren")
    
    If response = vbYes Then
        WriteLog "[INFO] Benutzer hat Python-Installation bestätigt"
        Dim installerPath, installerUrl
        installerPath = WshShell.ExpandEnvironmentStrings("%TEMP%\python-installer.exe")
        installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        
        WriteLog "[INFO] Starte Python-Download von: " & installerUrl
        WriteLog "[INFO] Ziel: " & installerPath
        Dim downloadCmd
        downloadCmd = "powershell.exe -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & installerUrl & "' -OutFile '" & installerPath & "'"""
        Dim downloadResult
        downloadResult = WshShell.Run(downloadCmd, 0, True)
        WriteLog "[INFO] Download-Befehl beendet mit Exit-Code: " & downloadResult
        
        If Not fso.FileExists(installerPath) Then
            WriteLog "[ERROR] Python-Installer nicht heruntergeladen"
            MsgBox "Konnte Python-Installer nicht herunterladen." & vbCrLf & vbCrLf & _
                   "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                   "https://www.python.org/downloads/", vbCritical, "Fehler"
            If Not logStream Is Nothing Then logStream.Close
            WScript.Quit
        End If
        WriteLog "[OK] Python-Installer heruntergeladen: " & installerPath
        
        Dim installCmd
        installCmd = "powershell.exe -Command ""Start-Process -FilePath '" & installerPath & "' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"""
        WriteLog "[INFO] Starte Python-Installation mit Administrator-Rechten..."
        WriteLog "[INFO] Installations-Befehl: " & installCmd
        Dim installResult
        installResult = WshShell.Run(installCmd, 1, True)
        WriteLog "[INFO] Installations-Befehl beendet mit Exit-Code: " & installResult
        
        WScript.Sleep 3000
        
        WriteLog "[INFO] Prüfe ob Python jetzt verfügbar ist..."
        On Error Resume Next
        Set pythonCheck = WshShell.Exec("python.exe --version")
        pythonCheck.StdOut.ReadAll
        pythonCheck.WaitOnReturn = True
        If pythonCheck.ExitCode = 0 Then
            pythonExe = "python.exe"
            WriteLog "[OK] Python erfolgreich installiert: python.exe"
            MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                   "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
        Else
            Set pythonCheck2 = WshShell.Exec("pythonw.exe --version")
            pythonCheck2.StdOut.ReadAll
            pythonCheck2.WaitOnReturn = True
            If pythonCheck2.ExitCode = 0 Then
                pythonExe = "pythonw.exe"
                WriteLog "[OK] Python erfolgreich installiert: pythonw.exe"
                MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                       "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
            Else
                WriteLog "[ERROR] Python-Installation fehlgeschlagen"
                MsgBox "Python-Installation fehlgeschlagen oder noch nicht abgeschlossen." & vbCrLf & vbCrLf & _
                       "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                       "https://www.python.org/downloads/", vbCritical, "Fehler"
                If fso.FileExists(installerPath) Then fso.DeleteFile installerPath
                If Not logStream Is Nothing Then logStream.Close
                WScript.Quit
            End If
        End If
        On Error Goto 0
        
        If fso.FileExists(installerPath) Then fso.DeleteFile installerPath
    Else
        WriteLog "[INFO] Benutzer hat Python-Installation abgelehnt"
        MsgBox "Python ist erforderlich, um die Anwendung zu starten." & vbCrLf & vbCrLf & _
               "Bitte installieren Sie Python 3.8 oder höher von:" & vbCrLf & _
               "https://www.python.org/downloads/", vbInformation, "Python erforderlich"
        If Not logStream Is Nothing Then logStream.Close
        WScript.Quit
    End If
End If

' Finde vollständigen Python-Pfad
Dim fullPythonPath
If InStr(pythonExe, "\") > 0 Then
    fullPythonPath = pythonExe
Else
    On Error Resume Next
    Dim whereResult
    Set whereResult = WshShell.Exec("where " & pythonExe)
    Dim whereOutput
    whereOutput = whereResult.StdOut.ReadAll
    whereResult.WaitOnReturn = True
    WriteLog "[INFO] where " & pythonExe & " Ausgabe: " & whereOutput
    WriteLog "[INFO] where " & pythonExe & " Exit-Code: " & whereResult.ExitCode
    If whereResult.ExitCode = 0 And Trim(whereOutput) <> "" Then
        Dim lines
        lines = Split(whereOutput, vbCrLf)
        If UBound(lines) >= 0 Then
            fullPythonPath = Trim(lines(0))
        Else
            fullPythonPath = pythonExe
        End If
    Else
        fullPythonPath = pythonExe
    End If
    On Error Goto 0
End If

If fullPythonPath = "" Then
    fullPythonPath = pythonExe
End If

WriteLog "[INFO] =========================================="
WriteLog "[INFO] Python gefunden: " & fullPythonPath
WriteLog "[INFO] Arbeitsverzeichnis: " & scriptPath
WriteLog "[INFO] =========================================="

' Erstelle/aktualisiere Shortcut (.lnk) mit Icon für Taskleiste
' WICHTIG: Shortcut zeigt auf die VBS-Datei, nicht direkt auf pythonw.exe
' Die VBS startet dann pythonw.exe, und start.py setzt die App User Model ID
' Das verhindert, dass Windows die .lnk-Datei als "pythonw.exe" erkennt
Dim shortcutNeedsUpdate
shortcutNeedsUpdate = True

' Prüfe ob Shortcut bereits existiert und korrekt ist
If fso.FileExists(shortcutPath) Then
    On Error Resume Next
    Dim existingShortcut
    Set existingShortcut = WshShell.CreateShortcut(shortcutPath)
    ' Prüfe ob Shortcut auf die VBS-Datei zeigt (nicht auf pythonw.exe)
    If InStr(LCase(existingShortcut.TargetPath), "start_launcher.vbs") > 0 Then
        shortcutNeedsUpdate = False
        WriteLog "[INFO] Shortcut existiert bereits und zeigt korrekt auf VBS"
    End If
    On Error Goto 0
End If

' Erstelle/aktualisiere Shortcut nur wenn nötig
If shortcutNeedsUpdate Then
    WriteLog "[INFO] Erstelle/aktualisiere Shortcut: " & shortcutPath
    On Error Resume Next
    Dim shortcut
    Set shortcut = WshShell.CreateShortcut(shortcutPath)
    ' WICHTIG: Shortcut zeigt auf die VBS-Datei, nicht auf pythonw.exe
    ' Die VBS startet dann pythonw.exe mit start.py
    ' start.py setzt die App User Model ID, damit Windows die Anwendung korrekt erkennt
    shortcut.TargetPath = WScript.ScriptFullName
    shortcut.WorkingDirectory = scriptPath
    shortcut.Description = "Universal Downloader"
    If iconPath <> "" Then
        shortcut.IconLocation = iconPath & ",0"
    End If
    ' Setze WindowStyle auf Minimized (7) damit kein Konsolen-Fenster erscheint
    shortcut.WindowStyle = 7
    shortcut.Save
    If Err.Number = 0 Then
        WriteLog "[OK] Shortcut erstellt: " & shortcutPath
        WriteLog "[INFO] Shortcut zeigt auf: " & WScript.ScriptFullName
        WriteLog "[INFO] VBS startet dann: " & fullPythonPath & " " & pythonScript
        If iconPath <> "" Then
            WriteLog "[INFO] Shortcut Icon: " & iconPath
        End If
    Else
        WriteLog "[WARNING] Konnte Shortcut nicht erstellen: " & Err.Description
    End If
    On Error Goto 0
End If

' Prüfe und installiere requirements.txt
If fso.FileExists(requirementsFile) Then
    WriteLog "[INFO] =========================================="
    WriteLog "[INFO] Prüfe requirements.txt..."
    WriteLog "[INFO] =========================================="
    ' Prüfe ob pip verfügbar ist
    On Error Resume Next
    Dim pipCheck
    Set pipCheck = WshShell.Exec(fullPythonPath & " -m pip --version")
    Dim pipOutput
    pipOutput = pipCheck.StdOut.ReadAll
    pipCheck.WaitOnReturn = True
    WriteLog "[INFO] pip --version Ausgabe: " & pipOutput
    WriteLog "[INFO] pip --version Exit-Code: " & pipCheck.ExitCode
    If pipCheck.ExitCode = 0 Then
        WriteLog "[OK] pip verfügbar"
        ' Installiere/aktualisiere requirements.txt
        Dim pipInstallCmd
        pipInstallCmd = fullPythonPath & " -m pip install --upgrade -r """ & requirementsFile & """"
        WriteLog "[INFO] =========================================="
        WriteLog "[INFO] Starte requirements.txt Installation..."
        WriteLog "[INFO] Befehl: " & pipInstallCmd
        WriteLog "[INFO] =========================================="
        Dim pipResult
        pipResult = WshShell.Run(pipInstallCmd, 1, True) ' 1 = sichtbar, damit Ausgabe gesehen wird
        WriteLog "[INFO] pip install Exit-Code: " & pipResult
        If pipResult = 0 Then
            WriteLog "[OK] requirements.txt erfolgreich installiert/aktualisiert"
        Else
            WriteLog "[WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: " & pipResult & ")"
        End If
    Else
        WriteLog "[WARNING] pip nicht verfügbar - überspringe requirements.txt Installation"
    End If
    On Error Goto 0
Else
    WriteLog "[WARNING] requirements.txt nicht gefunden: " & requirementsFile
End If

' Starte start.py mit ShellExecute
WshShell.CurrentDirectory = scriptPath
Dim startCmd
startCmd = Chr(34) & fullPythonPath & Chr(34) & " " & Chr(34) & pythonScript & Chr(34)
WriteLog "[INFO] =========================================="
WriteLog "[INFO] Starte Anwendung..."
WriteLog "[INFO] Start-Befehl: " & startCmd
WriteLog "[INFO] Arbeitsverzeichnis: " & scriptPath
WriteLog "[INFO] =========================================="

On Error Resume Next
objShell.ShellExecute fullPythonPath, pythonScript, scriptPath, "open", 0
Dim startResult
If Err.Number = 0 Then
    startResult = 0
    WriteLog "[INFO] Start-Befehl ausgeführt (ShellExecute), Exit-Code: " & startResult
Else
    WriteLog "[WARNING] ShellExecute fehlgeschlagen, verwende WshShell.Run: " & Err.Description
    WshShell.CurrentDirectory = scriptPath
    startResult = WshShell.Run(startCmd, 0, False)
    WriteLog "[INFO] Start-Befehl ausgeführt (WshShell.Run), Exit-Code: " & startResult
End If
On Error Goto 0

' Prüfe ob Prozess gestartet wurde
WScript.Sleep 2000
On Error Resume Next
Dim pythonExeName
pythonExeName = fso.GetBaseName(fullPythonPath) & ".exe"
Dim processCheck
Set processCheck = WshShell.Exec("tasklist /FI ""IMAGENAME eq " & pythonExeName & """ /FO CSV /NH")
Dim processOutput
processOutput = processCheck.StdOut.ReadAll
processCheck.WaitOnReturn = True
WriteLog "[INFO] tasklist Ausgabe: " & processOutput
WriteLog "[INFO] tasklist Exit-Code: " & processCheck.ExitCode
If processCheck.ExitCode = 0 And InStr(processOutput, pythonExeName) > 0 Then
    WriteLog "[OK] Python-Prozess läuft: " & pythonExeName
Else
    WriteLog "[WARNING] Python-Prozess scheint nicht zu laufen"
    Set processCheck2 = WshShell.Exec("tasklist /FI ""IMAGENAME eq python.exe"" /FO CSV /NH")
    Dim processOutput2
    processOutput2 = processCheck2.StdOut.ReadAll
    processCheck2.WaitOnReturn = True
    If InStr(processOutput2, "python.exe") > 0 Then
        WriteLog "[OK] Python-Prozess gefunden (python.exe)"
    Else
        WriteLog "[WARNING] Kein Python-Prozess gefunden - start.py wurde möglicherweise sofort beendet"
    End If
End If
On Error Goto 0

WriteLog "[OK] =========================================="
WriteLog "[OK] Launcher beendet erfolgreich"
WriteLog "[OK] =========================================="
On Error Resume Next
If Not logStream Is Nothing Then
    logStream.Close
    Set logStream = Nothing
End If
On Error Goto 0
