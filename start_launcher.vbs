Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Hole das Verzeichnis der .vbs Datei
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = scriptPath & "\start.py"

' Log-Datei Setup - im gleichen Verzeichnis wie start.py
Dim logFile, logStream
logFile = scriptPath & "\vbs.log.txt"
On Error Resume Next
Set logStream = fso.OpenTextFile(logFile, 8, True) ' 8 = ForAppending, True = Create if not exists
If Err.Number <> 0 Then
    ' Fallback: Versuche im Temp-Verzeichnis
    logFile = WshShell.ExpandEnvironmentStrings("%TEMP%\vbs.log.txt")
    Set logStream = fso.OpenTextFile(logFile, 8, True)
End If
On Error Goto 0

Sub WriteLog(message)
    Dim timestamp
    timestamp = Now()
    logStream.WriteLine "[" & timestamp & "] " & message
    ' Flush ist nicht für alle TextStream-Objekte verfügbar, daher verwenden wir Close/Reopen nicht
    ' Stattdessen schreiben wir direkt und schließen am Ende
End Sub

WriteLog "=========================================="
WriteLog "Launcher gestartet: " & WScript.ScriptFullName
WriteLog "Verzeichnis: " & scriptPath

' Prüfe ob start.py existiert
If Not fso.FileExists(pythonScript) Then
    WriteLog "[ERROR] start.py nicht gefunden in: " & scriptPath
    MsgBox "start.py nicht gefunden in: " & scriptPath, vbCritical, "Fehler"
    logStream.Close
    WScript.Quit
End If
WriteLog "[OK] start.py gefunden: " & pythonScript

' Versuche Python zu finden
pythonExe = ""
WriteLog "[INFO] Starte Python-Suche..."
On Error Resume Next

' Methode 1: Versuche pythonw.exe direkt (wenn im PATH)
WriteLog "[INFO] Methode 1: Prüfe pythonw.exe im PATH..."
Set pythonCheck = WshShell.Exec("pythonw.exe --version")
pythonCheck.StdOut.ReadAll
pythonCheck.WaitOnReturn = True
If pythonCheck.ExitCode = 0 Then
    pythonExe = "pythonw.exe"
    WriteLog "[OK] Python gefunden (Methode 1): pythonw.exe im PATH"
Else
    WriteLog "[INFO] pythonw.exe nicht im PATH gefunden"
    ' Methode 2: Versuche python.exe (wenn im PATH)
    Err.Clear
    WriteLog "[INFO] Methode 2: Prüfe python.exe im PATH..."
    Set pythonCheck2 = WshShell.Exec("python.exe --version")
    pythonCheck2.StdOut.ReadAll
    pythonCheck2.WaitOnReturn = True
    If pythonCheck2.ExitCode = 0 Then
        pythonExe = "python.exe"
        WriteLog "[OK] Python gefunden (Methode 2): python.exe im PATH"
    Else
        WriteLog "[INFO] python.exe nicht im PATH gefunden"
        ' Methode 3: Suche in typischen Python-Installationspfaden
        Err.Clear
        WriteLog "[INFO] Methode 3: Suche in typischen Installationspfaden..."
        Dim searchPaths, searchPath, folder, file, subfolder
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
                ' Suche direkt nach pythonw.exe
                If fso.FileExists(searchPath & "\pythonw.exe") Then
                    pythonExe = searchPath & "\pythonw.exe"
                    WriteLog "[OK] Python gefunden (Methode 3): " & pythonExe
                    Exit For
                End If
                ' Suche in Unterordnern (z.B. Python3.11, Python3.12)
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
        
        ' Methode 4: Prüfe Registry für Python-Installationen
        If pythonExe = "" Then
            Err.Clear
            WriteLog "[INFO] Methode 4: Prüfe Registry..."
            Dim reg, pythonPath
            On Error Resume Next
            reg = WshShell.RegRead("HKEY_LOCAL_MACHINE\SOFTWARE\Python\PythonCore\3.11\InstallPath\ExecutablePath")
            If Err.Number = 0 And reg <> "" Then
                WriteLog "[INFO] Registry-Eintrag gefunden: " & reg
                ' Versuche pythonw.exe im gleichen Verzeichnis zu finden
                Dim execPath
                execPath = fso.GetParentFolderName(reg)
                If fso.FileExists(execPath & "\pythonw.exe") Then
                    pythonExe = execPath & "\pythonw.exe"
                    WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                ElseIf fso.FileExists(reg) Then
                    pythonExe = reg
                    WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                End If
            Else
                WriteLog "[INFO] Kein Registry-Eintrag für Python 3.11 gefunden"
            End If
            On Error Resume Next
        End If
        
        ' Methode 5: Suche auf allen Laufwerken (C:, D:, E:, etc.)
        If pythonExe = "" Then
            Err.Clear
            WriteLog "[INFO] Methode 5: Suche auf allen Laufwerken..."
            Dim drives, drive, drivePath
            Set drives = fso.Drives
            For Each drive In drives
                If drive.IsReady And drive.DriveType = 2 Then ' Fixed Disk
                    drivePath = drive.DriveLetter & ":\"
                    WriteLog "[INFO] Prüfe Laufwerk: " & drivePath
                    ' Suche in typischen Pfaden auf diesem Laufwerk
                    Dim altPaths
                    altPaths = Array( _
                        drivePath & "Program Files\Python", _
                        drivePath & "Program Files (x86)\Python", _
                        drivePath & "Python" _
                    )
                    For Each altPath In altPaths
                        If fso.FolderExists(altPath) Then
                            WriteLog "[INFO] Prüfe Pfad: " & altPath
                            If fso.FileExists(altPath & "\pythonw.exe") Then
                                pythonExe = altPath & "\pythonw.exe"
                                WriteLog "[OK] Python gefunden (Methode 5): " & pythonExe
                                Exit For
                            End If
                            ' Suche in Unterordnern
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

' Falls Python immer noch nicht gefunden wurde, versuche Installation
If pythonExe = "" Then
    WriteLog "[WARNING] Python nicht gefunden nach allen Suchmethoden"
    Dim response
    response = MsgBox("Python nicht gefunden!" & vbCrLf & vbCrLf & _
           "Möchten Sie Python 3.11 automatisch herunterladen und installieren?" & vbCrLf & vbCrLf & _
           "Hinweis: Dies erfordert Administrator-Rechte.", _
           vbYesNo + vbQuestion + vbDefaultButton1, "Python installieren")
    
    If response = vbYes Then
        WriteLog "[INFO] Benutzer hat Python-Installation bestätigt"
        ' Versuche Python automatisch zu installieren
        Dim installerPath, installerUrl
        installerPath = WshShell.ExpandEnvironmentStrings("%TEMP%\python-installer.exe")
        installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        
        WriteLog "[INFO] Starte Python-Download von: " & installerUrl
        WriteLog "[INFO] Ziel: " & installerPath
        
        ' Lade Python-Installer herunter mit PowerShell (zuverlässiger für binäre Dateien)
        On Error Resume Next
        Dim downloadCmd
        downloadCmd = "powershell.exe -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & installerUrl & "' -OutFile '" & installerPath & "'"""
        WriteLog "[INFO] Führe Download-Befehl aus..."
        Dim downloadResult
        downloadResult = WshShell.Run(downloadCmd, 0, True)
        WriteLog "[INFO] Download-Befehl beendet mit Exit-Code: " & downloadResult
        
        If Not fso.FileExists(installerPath) Then
            WriteLog "[ERROR] Python-Installer nicht heruntergeladen: " & installerPath
            MsgBox "Konnte Python-Installer nicht herunterladen." & vbCrLf & vbCrLf & _
                   "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                   "https://www.python.org/downloads/", vbCritical, "Fehler"
            logStream.Close
            WScript.Quit
        End If
        WriteLog "[OK] Python-Installer heruntergeladen: " & installerPath
        
        ' Installiere Python im Silent-Modus
        ' /quiet = Silent installation
        ' /prependpath = Füge Python zum PATH hinzu
        ' InstallAllUsers = 1 = Für alle Benutzer
        Dim installCmd
        installCmd = "powershell.exe -Command ""Start-Process -FilePath '" & installerPath & "' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"""
        
        WriteLog "[INFO] Starte Python-Installation mit Administrator-Rechten..."
        Dim installResult
        installResult = WshShell.Run(installCmd, 1, True)
        WriteLog "[INFO] Installations-Befehl beendet mit Exit-Code: " & installResult
        
        ' Warte kurz und prüfe ob Python jetzt verfügbar ist
        WriteLog "[INFO] Warte 3 Sekunden auf Installation..."
        WScript.Sleep 3000
        
        ' Prüfe erneut (auch mit erweiterten Suchmethoden)
        WriteLog "[INFO] Prüfe ob Python jetzt verfügbar ist..."
        On Error Resume Next
        Set pythonCheck = WshShell.Exec("python.exe --version")
        pythonCheck.StdOut.ReadAll
        pythonCheck.WaitOnReturn = True
        If pythonCheck.ExitCode = 0 Then
            pythonExe = "python.exe"
            WriteLog "[OK] Python erfolgreich installiert und gefunden: python.exe"
            MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                   "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
        Else
            ' Versuche pythonw.exe
            WriteLog "[INFO] python.exe nicht gefunden, versuche pythonw.exe..."
            Set pythonCheck2 = WshShell.Exec("pythonw.exe --version")
            pythonCheck2.StdOut.ReadAll
            pythonCheck2.WaitOnReturn = True
            If pythonCheck2.ExitCode = 0 Then
                pythonExe = "pythonw.exe"
                WriteLog "[OK] Python erfolgreich installiert und gefunden: pythonw.exe"
                MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                       "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
            Else
                WriteLog "[ERROR] Python-Installation fehlgeschlagen - python.exe und pythonw.exe nicht gefunden"
                MsgBox "Python-Installation fehlgeschlagen oder noch nicht abgeschlossen." & vbCrLf & vbCrLf & _
                       "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                       "https://www.python.org/downloads/" & vbCrLf & vbCrLf & _
                       "Wichtig: Aktivieren Sie 'Add Python to PATH' während der Installation!", _
                       vbCritical, "Fehler"
                ' Lösche Installer
                If fso.FileExists(installerPath) Then fso.DeleteFile installerPath
                logStream.Close
                WScript.Quit
            End If
        End If
        On Error Goto 0
        
        ' Lösche Installer
        If fso.FileExists(installerPath) Then
            fso.DeleteFile installerPath
            WriteLog "[INFO] Installer-Datei gelöscht"
        End If
    Else
        ' Benutzer hat abgelehnt
        WriteLog "[INFO] Benutzer hat Python-Installation abgelehnt"
        MsgBox "Python ist erforderlich, um die Anwendung zu starten." & vbCrLf & vbCrLf & _
               "Bitte installieren Sie Python 3.8 oder höher von:" & vbCrLf & _
               "https://www.python.org/downloads/", vbInformation, "Python erforderlich"
        logStream.Close
        WScript.Quit
    End If
End If

' Starte Python-Skript ohne Konsolen-Fenster
' Verwende CreateObject("WScript.Shell").Run mit WindowStyle=0 (versteckt)
WriteLog "[INFO] Starte Anwendung mit: " & pythonExe & " " & pythonScript
WshShell.CurrentDirectory = scriptPath
Dim startResult
startResult = WshShell.Run(pythonExe & " """ & pythonScript & """", 0, False)
WriteLog "[INFO] Start-Befehl ausgeführt, Exit-Code: " & startResult
WriteLog "[OK] Launcher beendet erfolgreich"
logStream.Close
