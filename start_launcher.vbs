Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set objShell = CreateObject("Shell.Application")

' Hole das Verzeichnis der .vbs Datei
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = scriptPath & "\start.py"
updateScript = scriptPath & "\update_from_github.py"

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

' Prüfe auf Updates (nur wenn nicht --no-update Parameter übergeben wurde)
Dim checkUpdates
checkUpdates = True
If WScript.Arguments.Count > 0 Then
    If WScript.Arguments(0) = "--no-update" Then
        checkUpdates = False
    End If
End If

If checkUpdates Then
    WriteLog "[INFO] Prüfe auf Updates..."
    
    ' Prüfe ob update_from_github.py existiert
    If fso.FileExists(updateScript) Then
        WriteLog "[INFO] Starte Update-Check..."
        
        ' Finde Python für Update-Check (verwende python.exe statt pythonw.exe für sichtbare Ausgabe)
        Dim pythonExeUpdate, fullPythonPathUpdate
        pythonExeUpdate = "python.exe"
        fullPythonPathUpdate = ""
        
        ' Methode 1: Prüfe python.exe im PATH
        On Error Resume Next
        Dim whereResultUpdate
        Set whereResultUpdate = WshShell.Exec("where " & pythonExeUpdate)
        Dim whereOutputUpdate
        whereOutputUpdate = whereResultUpdate.StdOut.ReadAll
        whereResultUpdate.WaitOnReturn = True
        
        If whereResultUpdate.ExitCode = 0 And Len(Trim(whereOutputUpdate)) > 0 Then
            Dim whereLinesUpdate
            whereLinesUpdate = Split(whereOutputUpdate, vbCrLf)
            If UBound(whereLinesUpdate) >= 0 And Len(Trim(whereLinesUpdate(0))) > 0 Then
                fullPythonPathUpdate = Trim(whereLinesUpdate(0))
            End If
        End If
        On Error Goto 0
        
        ' Methode 2: Prüfe pythonw.exe als Fallback
        If Len(fullPythonPathUpdate) = 0 Then
            On Error Resume Next
            Set whereResultUpdate = WshShell.Exec("where pythonw.exe")
            whereOutputUpdate = whereResultUpdate.StdOut.ReadAll
            whereResultUpdate.WaitOnReturn = True
            If whereResultUpdate.ExitCode = 0 And Len(Trim(whereOutputUpdate)) > 0 Then
                whereLinesUpdate = Split(whereOutputUpdate, vbCrLf)
                If UBound(whereLinesUpdate) >= 0 And Len(Trim(whereLinesUpdate(0))) > 0 Then
                    fullPythonPathUpdate = Trim(whereLinesUpdate(0))
                End If
            End If
            On Error Goto 0
        End If
        
        ' Methode 3: Prüfe typische Installationspfade
        If Len(fullPythonPathUpdate) = 0 Then
            Dim commonPathsUpdate
            commonPathsUpdate = Array( _
                WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python") _
            )
            
            Dim pathUpdate, foundUpdate, folderUpdateUpdate, subfolderUpdate
            foundUpdate = False
            For Each pathUpdate In commonPathsUpdate
                If fso.FolderExists(pathUpdate) Then
                    Set folderUpdateUpdate = fso.GetFolder(pathUpdate)
                    For Each subfolderUpdate In folderUpdateUpdate.SubFolders
                        If fso.FileExists(subfolderUpdate.Path & "\python.exe") Then
                            fullPythonPathUpdate = subfolderUpdate.Path & "\python.exe"
                            foundUpdate = True
                            Exit For
                        End If
                    Next
                    If foundUpdate Then Exit For
                End If
            Next
        End If
        
        ' Methode 4: Fallback zu python.exe
        If Len(fullPythonPathUpdate) = 0 Then
            fullPythonPathUpdate = pythonExeUpdate
        End If
        
        WriteLog "[INFO] Python für Update-Check: " & fullPythonPathUpdate
        
        ' Führe Update-Check aus (sichtbar, damit Benutzer den Fortschritt sieht)
        Dim updateResult, updateOutput, updateDetected, updateInstalled
        updateDetected = False
        updateInstalled = False
        
        ' Erstelle temporäre Batch-Datei für sichtbare Ausgabe mit Logging
        Dim tempBatFile, tempLogFile, tempResultFile
        tempBatFile = scriptPath & "\update_temp.bat"
        tempLogFile = scriptPath & "\update_output.txt"
        tempResultFile = scriptPath & "\update_result.txt"
        Dim tempBatStream
        Set tempBatStream = fso.CreateTextFile(tempBatFile, True)
        tempBatStream.WriteLine "@echo off"
        tempBatStream.WriteLine "setlocal enabledelayedexpansion"
        tempBatStream.WriteLine "cd /d """ & scriptPath & """"
        tempBatStream.WriteLine "echo =========================================="
        tempBatStream.WriteLine "echo Universal Downloader - Update-Check"
        tempBatStream.WriteLine "echo =========================================="
        tempBatStream.WriteLine "echo."
        tempBatStream.WriteLine """" & fullPythonPathUpdate & """ """ & updateScript & """ > """ & tempLogFile & """ 2>&1"
        tempBatStream.WriteLine "set UPDATE_RESULT=!errorlevel!"
        tempBatStream.WriteLine "echo !UPDATE_RESULT! > """ & tempResultFile & """"
        tempBatStream.WriteLine "type """ & tempLogFile & """"
        tempBatStream.WriteLine "echo."
        tempBatStream.WriteLine "echo =========================================="
        tempBatStream.WriteLine "findstr /i /c:""keine updates"" /c:""bereits auf dem neuesten stand"" /c:""no updates available"" /c:""already up to date"" """ & tempLogFile & """ >nul 2>&1"
        tempBatStream.WriteLine "if !errorlevel!==0 ("
        tempBatStream.WriteLine "    echo Update-Check abgeschlossen - Bereits auf dem neuesten Stand"
        tempBatStream.WriteLine ") else ("
        tempBatStream.WriteLine "    if !UPDATE_RESULT!==0 ("
        tempBatStream.WriteLine "        echo Update-Check abgeschlossen"
        tempBatStream.WriteLine "    ) else ("
        tempBatStream.WriteLine "        echo Update-Check beendet mit Fehler (Code: !UPDATE_RESULT!)"
        tempBatStream.WriteLine "    )"
        tempBatStream.WriteLine ")"
        tempBatStream.WriteLine "echo =========================================="
        tempBatStream.WriteLine "pause"
        tempBatStream.Close
        
        On Error Resume Next
        ' Führe Update-Check in sichtbarem Fenster aus
        updateResult = WshShell.Run("""" & tempBatFile & """", 1, True) ' 1 = sichtbar
        On Error Goto 0
        
        ' Lese Exit-Code aus Result-Datei
        If fso.FileExists(tempResultFile) Then
            Dim resultStream
            Set resultStream = fso.OpenTextFile(tempResultFile, 1, False)
            Dim resultCode
            resultCode = Trim(resultStream.ReadAll)
            resultStream.Close
            If IsNumeric(resultCode) Then
                updateResult = CInt(resultCode)
            End If
            fso.DeleteFile tempResultFile
        End If
        
        ' Lese Ausgabe aus Log-Datei
        Dim updateStdOut, updateStdErr
        updateStdOut = ""
        updateStdErr = ""
        If fso.FileExists(tempLogFile) Then
            Dim logStreamUpdate
            Set logStreamUpdate = fso.OpenTextFile(tempLogFile, 1, False)
            updateStdOut = logStreamUpdate.ReadAll
            logStreamUpdate.Close
            fso.DeleteFile tempLogFile
        End If
        
        ' Lösche temporäre Batch-Datei
        If fso.FileExists(tempBatFile) Then
            fso.DeleteFile tempBatFile
        End If
        
        ' Schreibe Ausgabe ins Log
        If Len(updateStdOut) > 0 Then
            WriteLog "[INFO] Update-Skript Ausgabe: " & updateStdOut
        End If
        If Len(updateStdErr) > 0 Then
            WriteLog "[WARNING] Update-Skript Fehler: " & updateStdErr
        End If
        
        ' Prüfe ob Update erkannt oder installiert wurde
        Dim updateOutputLower
        updateOutputLower = LCase(updateStdOut & " " & updateStdErr)
        
        ' Prüfe ob "keine Updates verfügbar" oder "bereits auf dem neuesten Stand" in der Ausgabe steht
        Dim noUpdateAvailable
        noUpdateAvailable = (InStr(updateOutputLower, "keine updates") > 0 Or _
                           InStr(updateOutputLower, "bereits auf dem neuesten stand") > 0 Or _
                           InStr(updateOutputLower, "no updates available") > 0 Or _
                           InStr(updateOutputLower, "already up to date") > 0)
        
        ' Prüfe ob Update installiert wurde (Exit-Code 0 + entsprechende Meldung)
        If updateResult = 0 Then
            If InStr(updateOutputLower, "update erfolgreich abgeschlossen") > 0 Or _
               InStr(updateOutputLower, "update erfolgreich") > 0 Or _
               InStr(updateOutputLower, "erfolgreich aktualisiert") > 0 Or _
               InStr(updateOutputLower, "successfully updated") > 0 Or _
               InStr(updateOutputLower, "update completed") > 0 Then
                updateInstalled = True
                updateDetected = True
                WriteLog "[OK] Update wurde erfolgreich installiert!"
            ElseIf InStr(updateOutputLower, "update verfügbar") > 0 Or _
                   InStr(updateOutputLower, "update available") > 0 Or _
                   (InStr(updateOutputLower, "version") > 0 And (InStr(updateOutputLower, "→") > 0 Or InStr(updateOutputLower, "->") > 0)) Then
                updateDetected = True
                WriteLog "[INFO] Update wurde erkannt!"
            End If
        End If
        
        ' Behandle verschiedene Exit-Codes
        If updateResult = 0 Then
            ' Exit-Code 0: Erfolg
            If updateInstalled Then
                WriteLog "[OK] Update-Check abgeschlossen - Update wurde installiert"
                ' Zeige Meldung an Benutzer
                Dim updateMsg
                updateMsg = "Update wurde erkannt und erfolgreich installiert!" & vbCrLf & vbCrLf & _
                           "Die Anwendung wird jetzt neu gestartet, um die Änderungen zu übernehmen." & vbCrLf & vbCrLf & _
                           "Bitte warten Sie einen Moment..."
                MsgBox updateMsg, vbInformation, "Update installiert"
            ElseIf updateDetected Then
                WriteLog "[INFO] Update wurde erkannt, aber nicht installiert"
                MsgBox "Ein Update wurde erkannt, konnte aber nicht automatisch installiert werden." & vbCrLf & vbCrLf & _
                       "Bitte aktualisieren Sie manuell über Git oder laden Sie die neueste Version herunter.", vbInformation, "Update erkannt"
            Else
                WriteLog "[OK] Update-Check abgeschlossen - Bereits auf dem neuesten Stand"
            End If
        ElseIf updateResult = 1 And noUpdateAvailable Then
            ' Exit-Code 1 mit "keine Updates verfügbar" ist normal, kein Fehler
            WriteLog "[OK] Update-Check abgeschlossen - Bereits auf dem neuesten Stand"
        Else
            ' Andere Exit-Codes sind Fehler
            WriteLog "[WARNING] Update-Check fehlgeschlagen (Exit-Code: " & updateResult & ")"
        End If
    Else
        WriteLog "[WARNING] update_from_github.py nicht gefunden - überspringe Update-Check"
    End If
    WriteLog ""
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
                            Dim folder5, subfolder5
                            Set folder5 = fso.GetFolder(altPath)
                            For Each subfolder5 In folder5.SubFolders
                                If fso.FileExists(subfolder5.Path & "\pythonw.exe") Then
                                    pythonExe = subfolder5.Path & "\pythonw.exe"
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
        
        ' Warte länger nach Installation (PATH muss aktualisiert werden)
        WriteLog "[INFO] Warte auf Abschluss der Python-Installation..."
        WScript.Sleep 5000
        
        ' Aktualisiere Umgebungsvariablen (PATH)
        WriteLog "[INFO] Aktualisiere Umgebungsvariablen..."
        Dim envPath
        envPath = WshShell.ExpandEnvironmentStrings("%PATH%")
        WriteLog "[INFO] Aktueller PATH: " & envPath
        
        ' Prüfe ob Python jetzt verfügbar ist (mehrere Versuche)
        Dim pythonFoundAfterInstall
        pythonFoundAfterInstall = False
        Dim maxRetries
        maxRetries = 5
        Dim retryCount
        retryCount = 0
        
        Do While retryCount < maxRetries And Not pythonFoundAfterInstall
            retryCount = retryCount + 1
            WriteLog "[INFO] Versuch " & retryCount & " von " & maxRetries & ": Prüfe Python..."
            
            On Error Resume Next
            Set pythonCheck = WshShell.Exec("python.exe --version")
            pythonCheck.StdOut.ReadAll
            pythonCheck.WaitOnReturn = True
            If pythonCheck.ExitCode = 0 Then
                pythonExe = "python.exe"
                pythonFoundAfterInstall = True
                WriteLog "[OK] Python erfolgreich installiert: python.exe"
            Else
                Set pythonCheck2 = WshShell.Exec("pythonw.exe --version")
                pythonCheck2.StdOut.ReadAll
                pythonCheck2.WaitOnReturn = True
                If pythonCheck2.ExitCode = 0 Then
                    pythonExe = "pythonw.exe"
                    pythonFoundAfterInstall = True
                    WriteLog "[OK] Python erfolgreich installiert: pythonw.exe"
                End If
            End If
            On Error Goto 0
            
            If Not pythonFoundAfterInstall And retryCount < maxRetries Then
                WriteLog "[INFO] Python noch nicht im PATH - warte 2 Sekunden..."
                WScript.Sleep 2000
            End If
        Loop
        
        If pythonFoundAfterInstall Then
            MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                   "Die Anwendung wird jetzt konfiguriert.", vbInformation, "Erfolg"
        Else
            WriteLog "[ERROR] Python-Installation fehlgeschlagen - Python nicht im PATH gefunden"
            WriteLog "[INFO] Versuche Python in typischen Installationspfaden zu finden..."
            
            ' Versuche Python in typischen Pfaden zu finden
            Dim commonPythonPaths
            commonPythonPaths = Array( _
                WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\python.exe"), _
                WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python311\python.exe"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python311\pythonw.exe") _
            )
            
            Dim foundPythonPath
            foundPythonPath = ""
            For Each testPath In commonPythonPaths
                If fso.FileExists(testPath) Then
                    foundPythonPath = testPath
                    pythonExe = testPath
                    pythonFoundAfterInstall = True
                    WriteLog "[OK] Python gefunden in: " & foundPythonPath
                    Exit For
                End If
            Next
            
            If Not pythonFoundAfterInstall Then
                MsgBox "Python-Installation fehlgeschlagen oder noch nicht abgeschlossen." & vbCrLf & vbCrLf & _
                       "Bitte:" & vbCrLf & _
                       "1. Starten Sie den PC neu" & vbCrLf & _
                       "2. Oder installieren Sie Python manuell von:" & vbCrLf & _
                       "   https://www.python.org/downloads/" & vbCrLf & vbCrLf & _
                       "Wichtig: Aktivieren Sie 'Add Python to PATH' bei der Installation!", vbCritical, "Fehler"
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

' Erstelle/aktualisiere Shortcut (.lnk) mit Icon für Taskleiste (lokal)
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

' Erstelle Startmenü-Verknüpfung
On Error Resume Next
Dim startMenuPath, startMenuShortcutPath
startMenuPath = WshShell.SpecialFolders("StartMenu") & "\Programs"
startMenuShortcutPath = startMenuPath & "\Universal Downloader.lnk"

' Erstelle Startmenü-Ordner falls nicht vorhanden
If Not fso.FolderExists(startMenuPath) Then
    fso.CreateFolder startMenuPath
End If

' Prüfe ob Startmenü-Verknüpfung bereits existiert
Dim startMenuShortcutNeedsUpdate
startMenuShortcutNeedsUpdate = True
If fso.FileExists(startMenuShortcutPath) Then
    Dim existingStartMenuShortcut
    Set existingStartMenuShortcut = WshShell.CreateShortcut(startMenuShortcutPath)
    If InStr(LCase(existingStartMenuShortcut.TargetPath), "start_launcher.vbs") > 0 Then
        startMenuShortcutNeedsUpdate = False
        WriteLog "[INFO] Startmenü-Verknüpfung existiert bereits: " & startMenuShortcutPath
    End If
End If

' Erstelle/aktualisiere Startmenü-Verknüpfung nur wenn nötig
If startMenuShortcutNeedsUpdate Then
    WriteLog "[INFO] Erstelle Startmenü-Verknüpfung: " & startMenuShortcutPath
    Dim startMenuShortcut
    Set startMenuShortcut = WshShell.CreateShortcut(startMenuShortcutPath)
    startMenuShortcut.TargetPath = WScript.ScriptFullName
    startMenuShortcut.WorkingDirectory = scriptPath
    startMenuShortcut.Description = "Universal Downloader - Downloader für Musik und Videos"
    If iconPath <> "" Then
        startMenuShortcut.IconLocation = iconPath & ",0"
    End If
    startMenuShortcut.WindowStyle = 7
    startMenuShortcut.Save
    If Err.Number = 0 Then
        WriteLog "[OK] Startmenü-Verknüpfung erstellt: " & startMenuShortcutPath
    Else
        WriteLog "[WARNING] Konnte Startmenü-Verknüpfung nicht erstellen: " & Err.Description
    End If
End If
On Error Goto 0

' Prüfe und installiere venv (virtuelle Umgebung)
Dim venvPath
venvPath = scriptPath & "\venv"
Dim venvNeedsCreation
venvNeedsCreation = False

If Not fso.FolderExists(venvPath) Then
    WriteLog "[INFO] venv nicht gefunden - wird erstellt..."
    venvNeedsCreation = True
Else
    ' Prüfe ob venv gültig ist (enthält Scripts/python.exe oder bin/python)
    Dim venvPythonPath
    venvPythonPath = venvPath & "\Scripts\python.exe"
    If Not fso.FileExists(venvPythonPath) Then
        venvPythonPath = venvPath & "\bin\python"
        If Not fso.FileExists(venvPythonPath) Then
            WriteLog "[WARNING] venv existiert, aber ist ungültig - wird neu erstellt..."
            venvNeedsCreation = True
        End If
    End If
End If

If venvNeedsCreation Then
    WriteLog "[INFO] =========================================="
    WriteLog "[INFO] Erstelle virtuelle Umgebung (venv)..."
    WriteLog "[INFO] =========================================="
    On Error Resume Next
    
    ' Prüfe ob venv-Modul verfügbar ist
    Dim venvCheckCmd
    venvCheckCmd = fullPythonPath & " -m venv --help"
    Dim venvCheckResult
    Set venvCheckResult = WshShell.Exec(venvCheckCmd)
    venvCheckResult.StdOut.ReadAll
    venvCheckResult.WaitOnReturn = True
    
    If venvCheckResult.ExitCode = 0 Then
        Dim venvCmd
        venvCmd = fullPythonPath & " -m venv """ & venvPath & """"
        WriteLog "[INFO] venv-Befehl: " & venvCmd
        Dim venvResult
        venvResult = WshShell.Run(venvCmd, 1, True) ' 1 = sichtbar
        WriteLog "[INFO] venv Exit-Code: " & venvResult
        
        If venvResult = 0 Then
            ' Warte kurz, damit venv vollständig erstellt wird
            WScript.Sleep 2000
            
            ' Prüfe ob venv jetzt verfügbar ist
            venvPythonPath = venvPath & "\Scripts\python.exe"
            If Not fso.FileExists(venvPythonPath) Then
                venvPythonPath = venvPath & "\bin\python"
            End If
            If fso.FileExists(venvPythonPath) Then
                ' Verwende venv Python für weitere Installationen
                fullPythonPath = venvPythonPath
                WriteLog "[OK] venv erfolgreich erstellt"
                WriteLog "[INFO] Verwende venv Python: " & fullPythonPath
            Else
                WriteLog "[WARNING] venv erstellt, aber Python nicht gefunden - verwende System-Python"
            End If
        Else
            WriteLog "[WARNING] venv-Erstellung fehlgeschlagen (Exit-Code: " & venvResult & ")"
            WriteLog "[INFO] Verwende System-Python weiterhin (venv ist optional)"
        End If
    Else
        WriteLog "[WARNING] venv-Modul nicht verfügbar - überspringe venv-Erstellung"
        WriteLog "[INFO] Verwende System-Python (venv ist optional, aber empfohlen)"
    End If
    On Error Goto 0
Else
    WriteLog "[OK] venv existiert bereits"
    ' Verwende venv Python falls verfügbar
    venvPythonPath = venvPath & "\Scripts\python.exe"
    If Not fso.FileExists(venvPythonPath) Then
        venvPythonPath = venvPath & "\bin\python"
    End If
    If fso.FileExists(venvPythonPath) Then
        fullPythonPath = venvPythonPath
        WriteLog "[INFO] Verwende venv Python: " & fullPythonPath
    End If
End If

' Prüfe ob pip verfügbar ist und installiere es falls nötig
WriteLog "[INFO] =========================================="
WriteLog "[INFO] Prüfe pip..."
WriteLog "[INFO] =========================================="
On Error Resume Next
Dim pipCheck
Set pipCheck = WshShell.Exec(fullPythonPath & " -m pip --version")
Dim pipOutput
pipOutput = pipCheck.StdOut.ReadAll
pipCheck.WaitOnReturn = True
WriteLog "[INFO] pip --version Ausgabe: " & pipOutput
WriteLog "[INFO] pip --version Exit-Code: " & pipCheck.ExitCode
If pipCheck.ExitCode <> 0 Then
    WriteLog "[WARNING] pip nicht verfügbar - versuche Installation..."
    Dim ensurepipCmd
    ensurepipCmd = fullPythonPath & " -m ensurepip --upgrade --default-pip"
    WriteLog "[INFO] ensurepip-Befehl: " & ensurepipCmd
    Dim ensurepipResult
    ensurepipResult = WshShell.Run(ensurepipCmd, 1, True) ' 1 = sichtbar
    WriteLog "[INFO] ensurepip Exit-Code: " & ensurepipResult
    
    If ensurepipResult = 0 Then
        ' Prüfe nochmal ob pip jetzt verfügbar ist
        WScript.Sleep 1000
        Set pipCheck = WshShell.Exec(fullPythonPath & " -m pip --version")
        pipCheck.StdOut.ReadAll
        pipCheck.WaitOnReturn = True
        If pipCheck.ExitCode = 0 Then
            WriteLog "[OK] pip erfolgreich installiert"
        Else
            WriteLog "[WARNING] pip-Installation scheint fehlgeschlagen zu sein"
            WriteLog "[INFO] Versuche pip manuell zu installieren..."
            ' Versuche get-pip.py herunterzuladen und auszuführen
            Dim getPipUrl, getPipPath
            getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
            getPipPath = scriptPath & "\get-pip.py"
            Dim downloadPipCmd
            downloadPipCmd = "powershell.exe -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & getPipUrl & "' -OutFile '" & getPipPath & "'"""
            Dim downloadPipResult
            downloadPipResult = WshShell.Run(downloadPipCmd, 0, True)
            If downloadPipResult = 0 And fso.FileExists(getPipPath) Then
                Dim installPipCmd
                installPipCmd = fullPythonPath & " """ & getPipPath & """"
                Dim installPipResult
                installPipResult = WshShell.Run(installPipCmd, 1, True)
                If installPipResult = 0 Then
                    WriteLog "[OK] pip über get-pip.py erfolgreich installiert"
                Else
                    WriteLog "[WARNING] pip-Installation über get-pip.py fehlgeschlagen"
                End If
                If fso.FileExists(getPipPath) Then fso.DeleteFile getPipPath
            End If
        End If
    Else
        WriteLog "[WARNING] pip-Installation fehlgeschlagen (Exit-Code: " & ensurepipResult & ")"
        WriteLog "[INFO] Versuche pip manuell zu installieren..."
        ' Versuche get-pip.py herunterzuladen und auszuführen
        Dim getPipUrl2, getPipPath2
        getPipUrl2 = "https://bootstrap.pypa.io/get-pip.py"
        getPipPath2 = scriptPath & "\get-pip.py"
        Dim downloadPipCmd2
        downloadPipCmd2 = "powershell.exe -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & getPipUrl2 & "' -OutFile '" & getPipPath2 & "'"""
        Dim downloadPipResult2
        downloadPipResult2 = WshShell.Run(downloadPipCmd2, 0, True)
        If downloadPipResult2 = 0 And fso.FileExists(getPipPath2) Then
            Dim installPipCmd2
            installPipCmd2 = fullPythonPath & " """ & getPipPath2 & """"
            Dim installPipResult2
            installPipResult2 = WshShell.Run(installPipCmd2, 1, True)
            If installPipResult2 = 0 Then
                WriteLog "[OK] pip über get-pip.py erfolgreich installiert"
            Else
                WriteLog "[ERROR] pip-Installation fehlgeschlagen - requirements.txt kann nicht installiert werden"
            End If
            If fso.FileExists(getPipPath2) Then fso.DeleteFile getPipPath2
        End If
    End If
Else
    WriteLog "[OK] pip verfügbar"
End If
On Error Goto 0

' Prüfe und installiere requirements.txt
If fso.FileExists(requirementsFile) Then
    WriteLog "[INFO] =========================================="
    WriteLog "[INFO] Prüfe requirements.txt..."
    WriteLog "[INFO] =========================================="
    ' Prüfe ob pip jetzt verfügbar ist
    On Error Resume Next
    Set pipCheck = WshShell.Exec(fullPythonPath & " -m pip --version")
    pipOutput = pipCheck.StdOut.ReadAll
    pipCheck.WaitOnReturn = True
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
        
        ' Prüfe ob Installation erfolgreich war
        If pipResult = 0 Then
            WriteLog "[OK] requirements.txt erfolgreich installiert/aktualisiert"
            
            ' Prüfe ob wichtige Pakete jetzt verfügbar sind
            WriteLog "[INFO] Prüfe wichtige Pakete..."
            Dim testPackages
            testPackages = Array("requests", "yt_dlp", "mutagen")
            Dim allPackagesOk
            allPackagesOk = True
            For Each testPackage In testPackages
                On Error Resume Next
                Dim testCmd
                testCmd = fullPythonPath & " -c ""import " & testPackage & """"
                Dim testResult
                Set testResult = WshShell.Exec(testCmd)
                testResult.StdOut.ReadAll
                testResult.WaitOnReturn = True
                If testResult.ExitCode = 0 Then
                    WriteLog "[OK] Paket " & testPackage & " verfügbar"
                Else
                    WriteLog "[WARNING] Paket " & testPackage & " nicht verfügbar"
                    allPackagesOk = False
                End If
                On Error Goto 0
            Next
            
            If Not allPackagesOk Then
                WriteLog "[WARNING] Einige Pakete fehlen noch - versuche erneute Installation..."
                pipResult = WshShell.Run(pipInstallCmd, 1, True)
                WriteLog "[INFO] Zweiter Installationsversuch Exit-Code: " & pipResult
            End If
        Else
            WriteLog "[WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: " & pipResult & ")"
            WriteLog "[INFO] Versuche erneut mit --user Flag..."
            Dim pipInstallCmdUser
            pipInstallCmdUser = fullPythonPath & " -m pip install --user --upgrade -r """ & requirementsFile & """"
            pipResult = WshShell.Run(pipInstallCmdUser, 1, True)
            If pipResult = 0 Then
                WriteLog "[OK] requirements.txt erfolgreich installiert (--user)"
            Else
                WriteLog "[ERROR] requirements.txt Installation fehlgeschlagen auch mit --user Flag"
            End If
        End If
    Else
        WriteLog "[WARNING] pip nicht verfügbar - überspringe requirements.txt Installation"
    End If
    On Error Goto 0
Else
    WriteLog "[WARNING] requirements.txt nicht gefunden: " & requirementsFile
End If

' Prüfe tkinter (GUI-Bibliothek)
WriteLog "[INFO] =========================================="
WriteLog "[INFO] Prüfe tkinter..."
WriteLog "[INFO] =========================================="
On Error Resume Next
Dim tkinterCheck
Set tkinterCheck = WshShell.Exec(fullPythonPath & " -c ""import tkinter""")
Dim tkinterOutput
tkinterOutput = tkinterCheck.StdOut.ReadAll
tkinterCheck.WaitOnReturn = True
WriteLog "[INFO] tkinter-Check Exit-Code: " & tkinterCheck.ExitCode
If tkinterCheck.ExitCode <> 0 Then
    WriteLog "[WARNING] tkinter nicht verfügbar"
    WriteLog "[INFO] tkinter sollte normalerweise mit Python installiert sein"
    WriteLog "[INFO] Falls die GUI nicht startet, installieren Sie tkinter manuell"
Else
    WriteLog "[OK] tkinter verfügbar"
End If
On Error Goto 0

' Prüfe ffmpeg (für Video/Audio-Verarbeitung)
WriteLog "[INFO] =========================================="
WriteLog "[INFO] Prüfe ffmpeg..."
WriteLog "[INFO] =========================================="
On Error Resume Next
Dim ffmpegCheck
Set ffmpegCheck = WshShell.Exec("ffmpeg -version")
Dim ffmpegOutput
ffmpegOutput = ffmpegCheck.StdOut.ReadAll
ffmpegCheck.WaitOnReturn = True
WriteLog "[INFO] ffmpeg-Check Exit-Code: " & ffmpegCheck.ExitCode
If ffmpegCheck.ExitCode <> 0 Then
    WriteLog "[WARNING] ffmpeg nicht im PATH gefunden"
    WriteLog "[INFO] ffmpeg wird für Video/Audio-Verarbeitung benötigt"
    WriteLog "[INFO] Download von: https://ffmpeg.org/download.html"
    WriteLog "[INFO] Oder installieren Sie über: winget install ffmpeg (falls winget verfügbar)"
    
    ' Versuche winget Installation
    On Error Resume Next
    Dim wingetCheck
    Set wingetCheck = WshShell.Exec("winget --version")
    wingetCheck.WaitOnReturn = True
    If wingetCheck.ExitCode = 0 Then
        WriteLog "[INFO] winget verfügbar - versuche ffmpeg Installation..."
        Dim wingetCmd
        wingetCmd = "winget install -e --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements"
        WriteLog "[INFO] winget-Befehl: " & wingetCmd
        Dim wingetResult
        wingetResult = WshShell.Run(wingetCmd, 0, True) ' 0 = versteckt
        WriteLog "[INFO] winget Exit-Code: " & wingetResult
        If wingetResult = 0 Then
            WriteLog "[OK] ffmpeg erfolgreich über winget installiert"
        Else
            WriteLog "[WARNING] ffmpeg-Installation über winget fehlgeschlagen"
        End If
    Else
        WriteLog "[INFO] winget nicht verfügbar - überspringe automatische ffmpeg-Installation"
    End If
    On Error Goto 0
Else
    WriteLog "[OK] ffmpeg verfügbar"
End If
On Error Goto 0

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
