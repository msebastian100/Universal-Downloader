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

' Hilfsfunktion: Führt Python-Befehl aus und loggt die komplette Ausgabe
Function RunPythonCommand(cmd, description, showWindow)
    ' showWindow: 0 = versteckt, 1 = sichtbar
    Dim tempOutputFile, tempErrorFile, resultFile
    tempOutputFile = scriptPath & "\temp_python_output_" & Timer & ".txt"
    tempErrorFile = scriptPath & "\temp_python_error_" & Timer & ".txt"
    resultFile = scriptPath & "\temp_python_result_" & Timer & ".txt"
    
    WriteLog "[DEBUG] =========================================="
    WriteLog "[DEBUG] Python-Befehl: " & description
    WriteLog "[DEBUG] =========================================="
    WriteLog "[DEBUG] Befehl: " & cmd
    
    ' Erstelle Batch-Datei für Ausführung mit Ausgabe-Umleitung
    Dim batFile
    batFile = scriptPath & "\temp_python_cmd_" & Timer & ".bat"
    Dim batStream
    Set batStream = fso.CreateTextFile(batFile, True)
    batStream.WriteLine "@echo off"
    batStream.WriteLine "cd /d """ & scriptPath & """"
    batStream.WriteLine cmd & " > """ & tempOutputFile & """ 2> """ & tempErrorFile & """"
    batStream.WriteLine "echo %errorlevel% > """ & resultFile & """"
    batStream.Close
    
    ' Führe Batch-Datei aus
    Dim runResult
    runResult = WshShell.Run("""" & batFile & """", showWindow, True)
    
    ' Lese Ausgabe
    Dim output, errorOutput, exitCode
    output = ""
    errorOutput = ""
    exitCode = -1
    
    If fso.FileExists(tempOutputFile) Then
        On Error Resume Next
        Dim outputStream
        Set outputStream = fso.OpenTextFile(tempOutputFile, 1, False)
        output = outputStream.ReadAll
        outputStream.Close
        On Error Goto 0
    End If
    
    If fso.FileExists(tempErrorFile) Then
        On Error Resume Next
        Dim errorStream
        Set errorStream = fso.OpenTextFile(tempErrorFile, 1, False)
        errorOutput = errorStream.ReadAll
        errorStream.Close
        On Error Goto 0
    End If
    
    If fso.FileExists(resultFile) Then
        On Error Resume Next
        Dim resultStream
        Set resultStream = fso.OpenTextFile(resultFile, 1, False)
        Dim resultCode
        resultCode = Trim(resultStream.ReadAll)
        resultStream.Close
        If IsNumeric(resultCode) Then
            exitCode = CInt(resultCode)
        End If
        On Error Goto 0
    End If
    
    ' Logge Ausgabe
    WriteLog "[DEBUG] Exit-Code: " & exitCode
    If Len(output) > 0 Then
        WriteLog "[DEBUG] StdOut:"
        Dim outputLines
        outputLines = Split(output, vbCrLf)
        Dim line
        For Each line In outputLines
            If Len(Trim(line)) > 0 Then
                WriteLog "[DEBUG]   " & line
            End If
        Next
    End If
    If Len(errorOutput) > 0 Then
        WriteLog "[DEBUG] StdErr:"
        Dim errorLines
        errorLines = Split(errorOutput, vbCrLf)
        For Each line In errorLines
            If Len(Trim(line)) > 0 Then
                WriteLog "[DEBUG]   [ERROR] " & line
            End If
        Next
    End If
    WriteLog "[DEBUG] =========================================="
    
    ' Aufräumen
    On Error Resume Next
    If fso.FileExists(tempOutputFile) Then fso.DeleteFile tempOutputFile
    If fso.FileExists(tempErrorFile) Then fso.DeleteFile tempErrorFile
    If fso.FileExists(resultFile) Then fso.DeleteFile resultFile
    If fso.FileExists(batFile) Then fso.DeleteFile batFile
    On Error Goto 0
    
    ' Setze Rückgabewert
    RunPythonCommand = exitCode
End Function

WriteLog "=========================================="
WriteLog "Launcher gestartet: " & WScript.ScriptFullName
WriteLog "Verzeichnis: " & scriptPath
WriteLog "Log-Datei: " & logFile
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] System-Informationen:"
WriteLog "[DEBUG] =========================================="
On Error Resume Next
Dim osVersion, osArch, userName, computerName
osVersion = WshShell.RegRead("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProductName")
osArch = WshShell.ExpandEnvironmentStrings("%PROCESSOR_ARCHITECTURE%")
userName = WshShell.ExpandEnvironmentStrings("%USERNAME%")
computerName = WshShell.ExpandEnvironmentStrings("%COMPUTERNAME%")
WriteLog "[DEBUG] Betriebssystem: " & osVersion
WriteLog "[DEBUG] Architektur: " & osArch
WriteLog "[DEBUG] Benutzer: " & userName
WriteLog "[DEBUG] Computer: " & computerName
WriteLog "[DEBUG] Windows-Version: " & WshShell.RegRead("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows NT\CurrentVersion\CurrentVersion")
WriteLog "[DEBUG] PATH: " & WshShell.ExpandEnvironmentStrings("%PATH%")
WriteLog "[DEBUG] =========================================="
On Error Goto 0
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
        
        ' Hilfsfunktion: Prüft ob ein Python-Pfad wirklich funktioniert (nicht nur Stub)
        Function IsValidPython(pythonPath)
            IsValidPython = False
            On Error Resume Next
            ' Prüfe ob Pfad WindowsApps enthält (Stub)
            If InStr(LCase(pythonPath), "windowsapps") > 0 Then
                Exit Function
            End If
            ' Prüfe ob Datei existiert
            If Not fso.FileExists(pythonPath) Then
                Exit Function
            End If
        ' Prüfe ob Python wirklich funktioniert (--version sollte Ausgabe geben)
        Dim testResult
        Set testResult = WshShell.Exec("""" & pythonPath & """ --version")
        Dim testOutput
        testOutput = testResult.StdOut.ReadAll
        Dim testError
        testError = testResult.StdErr.ReadAll
        testResult.WaitOnReturn = True
        ' Prüfe Exit-Code UND ob Ausgabe vorhanden ist
        If testResult.ExitCode = 0 And Len(Trim(testOutput)) > 0 Then
            ' Prüfe ob Ausgabe wie eine Version aussieht (enthält "Python" oder Zahlen)
            If InStr(testOutput, "Python") > 0 Or InStr(testOutput, ".") > 0 Then
                IsValidPython = True
            End If
        End If
        ' Debug-Logging für Python-Validierung
        If Not IsValidPython Then
            WriteLog "[DEBUG] Python-Validierung fehlgeschlagen für: " & pythonPath
            WriteLog "[DEBUG]   Exit-Code: " & testResult.ExitCode
            WriteLog "[DEBUG]   StdOut: " & testOutput
            WriteLog "[DEBUG]   StdErr: " & testError
        End If
            On Error Goto 0
        End Function
        
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
            Dim lineUpdate
            For Each lineUpdate In whereLinesUpdate
                Dim candidatePath
                candidatePath = Trim(lineUpdate)
                If Len(candidatePath) > 0 Then
                    ' Prüfe ob es wirklich funktioniert (nicht WindowsApps-Stub)
                    If IsValidPython(candidatePath) Then
                        fullPythonPathUpdate = candidatePath
                        Exit For
                    End If
                End If
            Next
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
                Dim lineUpdate2
                For Each lineUpdate2 In whereLinesUpdate
                    candidatePath = Trim(lineUpdate2)
                    If Len(candidatePath) > 0 Then
                        ' Prüfe ob es wirklich funktioniert (nicht WindowsApps-Stub)
                        If IsValidPython(candidatePath) Then
                            fullPythonPathUpdate = candidatePath
                            Exit For
                        End If
                    End If
                Next
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
                        Dim testPythonPathUpdate
                        testPythonPathUpdate = subfolderUpdate.Path & "\python.exe"
                        If fso.FileExists(testPythonPathUpdate) Then
                            If IsValidPython(testPythonPathUpdate) Then
                                fullPythonPathUpdate = testPythonPathUpdate
                                foundUpdate = True
                                Exit For
                            End If
                        End If
                    Next
                    If foundUpdate Then Exit For
                End If
            Next
        End If
        
        ' Methode 4: Verwende das gleiche Python wie für die Hauptanwendung (falls bereits gefunden)
        ' HINWEIS: pythonExe wird später gesetzt, daher prüfen wir hier nur, ob wir es später verwenden können
        ' Für jetzt: Wenn kein Python gefunden wurde, verwende python.exe als letzten Fallback
        ' (wird später durch die Haupt-Python-Suche überschrieben, wenn ein gültiges Python gefunden wird)
        If Len(fullPythonPathUpdate) = 0 Then
            ' Versuche python.exe, aber nur wenn es nicht WindowsApps ist
            On Error Resume Next
            Dim testPythonExe
            Set whereResultUpdate = WshShell.Exec("where python.exe")
            whereOutputUpdate = whereResultUpdate.StdOut.ReadAll
            whereResultUpdate.WaitOnReturn = True
            If whereResultUpdate.ExitCode = 0 And Len(Trim(whereOutputUpdate)) > 0 Then
                whereLinesUpdate = Split(whereOutputUpdate, vbCrLf)
                For Each lineUpdate In whereLinesUpdate
                    candidatePath = Trim(lineUpdate)
                    If Len(candidatePath) > 0 And IsValidPython(candidatePath) Then
                        fullPythonPathUpdate = candidatePath
                        Exit For
                    End If
                Next
            End If
            On Error Goto 0
            ' Letzter Fallback: python.exe (wird später durch Haupt-Python-Suche überschrieben)
            If Len(fullPythonPathUpdate) = 0 Then
                fullPythonPathUpdate = pythonExeUpdate
            End If
        End If
        
        WriteLog "[INFO] Python für Update-Check: " & fullPythonPathUpdate
        WriteLog "[DEBUG] Update-Check Python-Validierung:"
        If Len(fullPythonPathUpdate) > 0 Then
            If IsValidPython(fullPythonPathUpdate) Then
                WriteLog "[DEBUG]   ✓ Python ist gültig und funktioniert"
            Else
                WriteLog "[DEBUG]   ✗ Python ist ungültig oder funktioniert nicht"
            End If
        Else
            WriteLog "[DEBUG]   ✗ Kein Python-Pfad gefunden"
        End If
        
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
        tempBatStream.WriteLine "echo [DEBUG] Arbeitsverzeichnis: %CD%"
        tempBatStream.WriteLine "echo [DEBUG] Python: """ & fullPythonPathUpdate & """"
        tempBatStream.WriteLine "echo [DEBUG] Skript: """ & updateScript & """"
        tempBatStream.WriteLine "echo [DEBUG] =========================================="
        tempBatStream.WriteLine "cd /d """ & scriptPath & """"
        tempBatStream.WriteLine "echo [DEBUG] Nach cd: %CD%"
        tempBatStream.WriteLine "if exist version.py (echo [DEBUG] ✓ version.py gefunden) else (echo [DEBUG] ✗ version.py nicht gefunden)"
        tempBatStream.WriteLine "if exist updater.py (echo [DEBUG] ✓ updater.py gefunden) else (echo [DEBUG] ✗ updater.py nicht gefunden)"
        tempBatStream.WriteLine "echo [DEBUG] Python: """ & fullPythonPathUpdate & """"
        tempBatStream.WriteLine "echo [DEBUG] Skript: """ & updateScript & """"
        tempBatStream.WriteLine "echo [DEBUG] =========================================="
        tempBatStream.WriteLine "echo."
        tempBatStream.WriteLine "echo Fuehre Update-Check aus..."
        tempBatStream.WriteLine "echo."
        ' Führe Python-Skript aus - zeige direkt an UND logge in Datei
        ' Methode: Führe aus, zeige an, dann logge auch
        tempBatStream.WriteLine """" & fullPythonPathUpdate & """ """ & updateScript & """"
        tempBatStream.WriteLine "set UPDATE_RESULT=!errorlevel!"
        tempBatStream.WriteLine "echo !UPDATE_RESULT! > """ & tempResultFile & """"
        ' Führe nochmal aus für Log-Datei (mit vollständiger Ausgabe)
        tempBatStream.WriteLine """" & fullPythonPathUpdate & """ """ & updateScript & """ > """ & tempLogFile & """ 2>&1"
        tempBatStream.WriteLine "echo."
        tempBatStream.WriteLine "echo =========================================="
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

' Hilfsfunktion: Prüft ob ein Python-Pfad wirklich funktioniert (nicht nur Stub)
Function IsValidPythonMain(pythonPath)
    IsValidPythonMain = False
    On Error Resume Next
    ' Prüfe ob Pfad WindowsApps enthält (Stub)
    If InStr(LCase(pythonPath), "windowsapps") > 0 Then
        Exit Function
    End If
    ' Prüfe ob Datei existiert
    If Not fso.FileExists(pythonPath) Then
        Exit Function
    End If
    ' Prüfe ob Python wirklich funktioniert (--version sollte Ausgabe geben)
    Dim testResult
    Set testResult = WshShell.Exec("""" & pythonPath & """ --version")
    Dim testOutput
    testOutput = testResult.StdOut.ReadAll
    testResult.WaitOnReturn = True
    ' Prüfe Exit-Code UND ob Ausgabe vorhanden ist
    If testResult.ExitCode = 0 And Len(Trim(testOutput)) > 0 Then
        ' Prüfe ob Ausgabe wie eine Version aussieht (enthält "Python" oder Zahlen)
        If InStr(testOutput, "Python") > 0 Or InStr(testOutput, ".") > 0 Then
            IsValidPythonMain = True
        End If
    End If
    On Error Goto 0
End Function

' Methode 1: PATH
WriteLog "[INFO] Methode 1: Prüfe pythonw.exe im PATH..."
On Error Resume Next
Dim whereResult
Set whereResult = WshShell.Exec("where pythonw.exe")
Dim whereOutput
whereOutput = whereResult.StdOut.ReadAll
whereResult.WaitOnReturn = True
On Error Goto 0

Dim pythonFound
pythonFound = False
If whereResult.ExitCode = 0 And Len(Trim(whereOutput)) > 0 Then
    Dim whereLines
    whereLines = Split(whereOutput, vbCrLf)
    Dim line
    For Each line In whereLines
        Dim candidatePath
        candidatePath = Trim(line)
        If Len(candidatePath) > 0 Then
            ' Prüfe ob es wirklich funktioniert (nicht WindowsApps-Stub)
            If IsValidPythonMain(candidatePath) Then
                pythonExe = candidatePath
                pythonFound = True
                WriteLog "[OK] Python gefunden (Methode 1): " & pythonExe
                Exit For
            End If
        End If
    Next
End If

If Not pythonFound Then
    WriteLog "[INFO] pythonw.exe nicht im PATH gefunden oder ungültig"
    ' Methode 2: python.exe im PATH
    Err.Clear
    WriteLog "[INFO] Methode 2: Prüfe python.exe im PATH..."
    On Error Resume Next
    Set whereResult = WshShell.Exec("where python.exe")
    whereOutput = whereResult.StdOut.ReadAll
    whereResult.WaitOnReturn = True
    On Error Goto 0
    
    If whereResult.ExitCode = 0 And Len(Trim(whereOutput)) > 0 Then
        whereLines = Split(whereOutput, vbCrLf)
        For Each line In whereLines
            candidatePath = Trim(line)
            If Len(candidatePath) > 0 Then
                ' Prüfe ob es wirklich funktioniert (nicht WindowsApps-Stub)
                If IsValidPythonMain(candidatePath) Then
                    pythonExe = candidatePath
                    pythonFound = True
                    WriteLog "[OK] Python gefunden (Methode 2): " & pythonExe
                    Exit For
                End If
            End If
        Next
    End If
    
    If Not pythonFound Then
        WriteLog "[INFO] python.exe nicht im PATH gefunden oder ungültig"
        ' Methode 3: Typische Installationspfade
        Err.Clear
        WriteLog "[INFO] Methode 3: Suche in typischen Installationspfaden..."
        Dim searchPaths, searchPath, folder, subfolder
        searchPaths = Array( _
            WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python") _
        )
        ' HINWEIS: WindowsApps wird ausgeschlossen, da es nur Stubs enthält
        
        For Each searchPath In searchPaths
            WriteLog "[INFO] Prüfe Pfad: " & searchPath
            If fso.FolderExists(searchPath) Then
                Set folder = fso.GetFolder(searchPath)
                Dim testPythonPath
                testPythonPath = searchPath & "\pythonw.exe"
                If fso.FileExists(testPythonPath) Then
                    If IsValidPythonMain(testPythonPath) Then
                        pythonExe = testPythonPath
                        WriteLog "[OK] Python gefunden (Methode 3): " & pythonExe
                        pythonFound = True
                        Exit For
                    End If
                End If
                For Each subfolder In folder.SubFolders
                    testPythonPath = subfolder.Path & "\pythonw.exe"
                    If fso.FileExists(testPythonPath) Then
                        If IsValidPythonMain(testPythonPath) Then
                            pythonExe = testPythonPath
                            WriteLog "[OK] Python gefunden (Methode 3): " & pythonExe
                            pythonFound = True
                            Exit For
                        End If
                    End If
                Next
                If pythonFound Then Exit For
                If pythonExe <> "" Then Exit For
            End If
        Next
        
        ' Methode 4: Registry
        If Not pythonFound Then
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
                    testPythonPath = execPath & "\pythonw.exe"
                    If fso.FileExists(testPythonPath) Then
                        If IsValidPythonMain(testPythonPath) Then
                            pythonExe = testPythonPath
                            WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                            pythonFound = True
                            Exit For
                        End If
                    ElseIf fso.FileExists(reg) Then
                        If IsValidPythonMain(reg) Then
                            pythonExe = reg
                            WriteLog "[OK] Python gefunden (Methode 4): " & pythonExe
                            pythonFound = True
                            Exit For
                        End If
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
                            testPythonPath = altPath & "\pythonw.exe"
                            If fso.FileExists(testPythonPath) Then
                                If IsValidPythonMain(testPythonPath) Then
                                    pythonExe = testPythonPath
                                    WriteLog "[OK] Python gefunden (Methode 5): " & pythonExe
                                    pythonFound = True
                                    Exit For
                                End If
                            End If
                            ' Suche in Unterordnern (Python3.11, Python3.12, etc.)
                            Dim folder5, subfolder5
                            Set folder5 = fso.GetFolder(altPath)
                            For Each subfolder5 In folder5.SubFolders
                                testPythonPath = subfolder5.Path & "\pythonw.exe"
                                If fso.FileExists(testPythonPath) Then
                                    If IsValidPythonMain(testPythonPath) Then
                                        pythonExe = testPythonPath
                                        WriteLog "[OK] Python gefunden (Methode 5): " & pythonExe
                                        pythonFound = True
                                        Exit For
                                    End If
                                End If
                            Next
                            If pythonFound Then Exit For
                        End If
                    Next
                    If pythonFound Then Exit For
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

' WICHTIG: Aktualisiere Update-Check Python-Pfad mit dem gefundenen Python (falls gültig)
' Dies stellt sicher, dass der Update-Check das gleiche Python verwendet wie die Hauptanwendung
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Aktualisiere Update-Check Python-Pfad..."
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Gefundener Python-Pfad: " & fullPythonPath
If Len(fullPythonPath) > 0 And InStr(LCase(fullPythonPath), "windowsapps") = 0 Then
    ' Konvertiere pythonw.exe zu python.exe für Update-Check (sichtbare Ausgabe)
    Dim updatePythonPath
    updatePythonPath = fullPythonPath
    WriteLog "[DEBUG] Original-Pfad: " & updatePythonPath
    If InStr(LCase(updatePythonPath), "pythonw.exe") > 0 Then
        updatePythonPath = Replace(LCase(updatePythonPath), "pythonw.exe", "python.exe")
        WriteLog "[DEBUG] Konvertiert zu: " & updatePythonPath
        ' Prüfe ob python.exe existiert
        If Not fso.FileExists(updatePythonPath) Then
            WriteLog "[DEBUG] python.exe nicht gefunden, verwende pythonw.exe"
            ' Fallback: Verwende pythonw.exe
            updatePythonPath = fullPythonPath
        Else
            WriteLog "[DEBUG] python.exe gefunden"
        End If
    End If
    ' Prüfe ob das Python wirklich funktioniert
    WriteLog "[DEBUG] Validiere Python-Pfad: " & updatePythonPath
    If IsValidPython(updatePythonPath) Then
        fullPythonPathUpdate = updatePythonPath
        WriteLog "[INFO] Update-Check Python-Pfad aktualisiert: " & fullPythonPathUpdate
        WriteLog "[DEBUG] ✓ Python-Validierung erfolgreich"
    Else
        WriteLog "[WARNING] Update-Check Python-Pfad konnte nicht validiert werden"
        WriteLog "[DEBUG] ✗ Python-Validierung fehlgeschlagen"
    End If
Else
    If InStr(LCase(fullPythonPath), "windowsapps") > 0 Then
        WriteLog "[DEBUG] ✗ Python-Pfad enthält WindowsApps (Stub) - überspringe"
    Else
        WriteLog "[DEBUG] ✗ Kein Python-Pfad gefunden"
    End If
End If
WriteLog "[DEBUG] =========================================="

If fullPythonPath = "" Then
    fullPythonPath = pythonExe
End If

WriteLog "[INFO] =========================================="
WriteLog "[INFO] Python gefunden: " & fullPythonPath
WriteLog "[INFO] Arbeitsverzeichnis: " & scriptPath
WriteLog "[INFO] =========================================="
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Python-Details:"
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Python-Executable: " & pythonExe
WriteLog "[DEBUG] Vollständiger Pfad: " & fullPythonPath
If fso.FileExists(fullPythonPath) Then
    WriteLog "[DEBUG] ✓ Python-Datei existiert"
    Dim fileInfo
    Set fileInfo = fso.GetFile(fullPythonPath)
    WriteLog "[DEBUG] Dateigröße: " & fileInfo.Size & " Bytes"
    WriteLog "[DEBUG] Erstellt: " & fileInfo.DateCreated
    WriteLog "[DEBUG] Geändert: " & fileInfo.DateLastModified
Else
    WriteLog "[DEBUG] ✗ Python-Datei existiert nicht!"
End If
' Prüfe Python-Version
On Error Resume Next
Dim versionCheck
Set versionCheck = WshShell.Exec("""" & fullPythonPath & """ --version")
Dim versionOutput
versionOutput = versionCheck.StdOut.ReadAll
versionCheck.WaitOnReturn = True
If versionCheck.ExitCode = 0 Then
    WriteLog "[DEBUG] Python-Version: " & Trim(versionOutput)
Else
    WriteLog "[DEBUG] ✗ Konnte Python-Version nicht ermitteln (Exit-Code: " & versionCheck.ExitCode & ")"
End If
On Error Goto 0
WriteLog "[DEBUG] =========================================="

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
    Dim venvCheckOutput
    venvCheckOutput = venvCheckResult.StdOut.ReadAll
    Dim venvCheckError
    venvCheckError = venvCheckResult.StdErr.ReadAll
    venvCheckResult.WaitOnReturn = True
    If Len(venvCheckError) > 0 Then
        WriteLog "[DEBUG] venv --help StdErr: " & venvCheckError
    End If
    
    If venvCheckResult.ExitCode = 0 Then
        Dim venvCmd
        venvCmd = fullPythonPath & " -m venv """ & venvPath & """"
        WriteLog "[INFO] venv-Befehl: " & venvCmd
        Dim venvResult
        venvResult = RunPythonCommand(venvCmd, "venv-Erstellung", 0) ' 0 = versteckt
        WriteLog "[INFO] venv Exit-Code: " & venvResult
        
        If venvResult = 0 Then
            ' Warte kurz, damit venv vollständig erstellt wird
            WScript.Sleep 2000
            WriteLog "[DEBUG] =========================================="
            WriteLog "[DEBUG] venv-Erstellung Details:"
            WriteLog "[DEBUG] =========================================="
            WriteLog "[DEBUG] venv-Pfad: " & venvPath
            WriteLog "[DEBUG] Exit-Code: " & venvResult
            WriteLog "[DEBUG] Prüfe venv-Verzeichnis..."
            
            ' Prüfe ob venv jetzt verfügbar ist
            venvPythonPath = venvPath & "\Scripts\python.exe"
            WriteLog "[DEBUG] Prüfe Windows-Pfad: " & venvPythonPath
            If Not fso.FileExists(venvPythonPath) Then
                venvPythonPath = venvPath & "\bin\python"
                WriteLog "[DEBUG] Prüfe Linux-Pfad: " & venvPythonPath
            End If
            If fso.FileExists(venvPythonPath) Then
                ' Verwende venv Python für weitere Installationen
                fullPythonPath = venvPythonPath
                WriteLog "[OK] venv erfolgreich erstellt"
                WriteLog "[INFO] Verwende venv Python: " & fullPythonPath
                WriteLog "[DEBUG] ✓ venv Python gefunden und wird verwendet"
            Else
                WriteLog "[WARNING] venv erstellt, aber Python nicht gefunden - verwende System-Python"
                WriteLog "[DEBUG] ✗ venv Python nicht gefunden in beiden Pfaden"
                If fso.FolderExists(venvPath) Then
                    WriteLog "[DEBUG] venv-Verzeichnis existiert, aber Python fehlt"
                Else
                    WriteLog "[DEBUG] venv-Verzeichnis existiert nicht"
                End If
            End If
            WriteLog "[DEBUG] =========================================="
        Else
            WriteLog "[WARNING] venv-Erstellung fehlgeschlagen (Exit-Code: " & venvResult & ")"
            WriteLog "[INFO] Verwende System-Python weiterhin (venv ist optional)"
            WriteLog "[DEBUG] =========================================="
            WriteLog "[DEBUG] venv-Erstellung Fehler-Details:"
            WriteLog "[DEBUG] =========================================="
            WriteLog "[DEBUG] venv-Befehl: " & venvCmd
            WriteLog "[DEBUG] Exit-Code: " & venvResult
            WriteLog "[DEBUG] venv-Pfad: " & venvPath
            WriteLog "[DEBUG] =========================================="
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
        Dim pipError
        pipError = pipCheck.StdErr.ReadAll
        If Len(pipError) > 0 Then
            WriteLog "[DEBUG] pip --version StdErr: " & pipError
        End If
        If pipCheck.ExitCode <> 0 Then
    WriteLog "[WARNING] pip nicht verfügbar - versuche Installation..."
    Dim ensurepipCmd
    ensurepipCmd = fullPythonPath & " -m ensurepip --upgrade --default-pip"
    WriteLog "[INFO] ensurepip-Befehl: " & ensurepipCmd
    Dim ensurepipResult
    ensurepipResult = RunPythonCommand(ensurepipCmd, "ensurepip-Installation", 0) ' 0 = versteckt
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
                installPipResult = RunPythonCommand(installPipCmd, "get-pip.py Installation", 0) ' 0 = versteckt
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
            installPipResult2 = RunPythonCommand(installPipCmd2, "get-pip.py Installation (Fallback)", 0) ' 0 = versteckt
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

' Prüfe und installiere requirements.txt (nur wenn nötig)
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
        
        ' Prüfe ob wichtige Pakete bereits installiert sind
        Dim packagesInstalled
        packagesInstalled = True
        Dim testPackages
        testPackages = Array("requests", "yt_dlp", "mutagen")
        WriteLog "[INFO] Prüfe ob Pakete bereits installiert sind..."
        For Each testPackage In testPackages
            Dim testCmd
            testCmd = fullPythonPath & " -c ""import " & testPackage & """"
            Dim testResult
            Set testResult = WshShell.Exec(testCmd)
            Dim testOutput
            testOutput = testResult.StdOut.ReadAll
            Dim testError
            testError = testResult.StdErr.ReadAll
            testResult.WaitOnReturn = True
            If testResult.ExitCode <> 0 Then
                packagesInstalled = False
                WriteLog "[INFO] Paket " & testPackage & " fehlt - Installation erforderlich"
                If Len(testError) > 0 Then
                    WriteLog "[DEBUG] Import-Fehler: " & testError
                End If
                Exit For
            End If
        Next
        
        ' Installiere/aktualisiere requirements.txt nur wenn Pakete fehlen
        If Not packagesInstalled Then
            Dim pipInstallCmd
            pipInstallCmd = fullPythonPath & " -m pip install --upgrade -r """ & requirementsFile & """"
            WriteLog "[INFO] =========================================="
            WriteLog "[INFO] Starte requirements.txt Installation..."
            WriteLog "[INFO] Befehl: " & pipInstallCmd
            WriteLog "[INFO] =========================================="
            Dim pipResult
            pipResult = RunPythonCommand(pipInstallCmd, "requirements.txt Installation", 0) ' 0 = versteckt
            WriteLog "[INFO] pip install Exit-Code: " & pipResult
            
            ' Prüfe ob Installation erfolgreich war
        If pipResult = 0 Then
            WriteLog "[OK] requirements.txt erfolgreich installiert/aktualisiert"
            WriteLog "[DEBUG] ✓ pip install erfolgreich abgeschlossen"
            
            ' Prüfe ob wichtige Pakete jetzt verfügbar sind
            WriteLog "[INFO] Prüfe wichtige Pakete..."
            WriteLog "[DEBUG] =========================================="
            WriteLog "[DEBUG] Paket-Verfügbarkeits-Prüfung:"
            WriteLog "[DEBUG] =========================================="
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
                    WriteLog "[DEBUG]   ✓ " & testPackage & " erfolgreich importiert"
                Else
                    WriteLog "[WARNING] Paket " & testPackage & " nicht verfügbar"
                    WriteLog "[DEBUG]   ✗ " & testPackage & " konnte nicht importiert werden (Exit-Code: " & testResult.ExitCode & ")"
                    Dim testError
                    testError = testResult.StdErr.ReadAll
                    If Len(testError) > 0 Then
                        WriteLog "[DEBUG]   Fehler-Ausgabe: " & testError
                    End If
                    allPackagesOk = False
                End If
                On Error Goto 0
            Next
            WriteLog "[DEBUG] =========================================="
            
            If Not allPackagesOk Then
                WriteLog "[WARNING] Einige Pakete fehlen noch - versuche erneute Installation..."
                pipResult = RunPythonCommand(pipInstallCmd, "requirements.txt Installation (Wiederholung)", 0) ' 0 = versteckt
                WriteLog "[INFO] Zweiter Installationsversuch Exit-Code: " & pipResult
            End If
        Else
            WriteLog "[WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: " & pipResult & ")"
            WriteLog "[INFO] Versuche erneut mit --user Flag..."
            Dim pipInstallCmdUser
            pipInstallCmdUser = fullPythonPath & " -m pip install --user --upgrade -r """ & requirementsFile & """"
            pipResult = RunPythonCommand(pipInstallCmdUser, "requirements.txt Installation (--user)", 0) ' 0 = versteckt
            If pipResult = 0 Then
                WriteLog "[OK] requirements.txt erfolgreich installiert (--user)"
            Else
                WriteLog "[ERROR] requirements.txt Installation fehlgeschlagen auch mit --user Flag"
            End If
        Else
            WriteLog "[OK] Alle Pakete bereits installiert - überspringe Installation"
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
    
    ' Prüfe ob ffmpeg bereits lokal installiert ist (in app_dir/ffmpeg/bin)
    Dim appDir, localFfmpeg
    appDir = scriptPath
    localFfmpeg = appDir & "\ffmpeg\bin\ffmpeg.exe"
    If fso.FileExists(localFfmpeg) Then
        WriteLog "[OK] ffmpeg lokal gefunden: " & localFfmpeg
    Else
        ' Versuche winget Installation (nur einmal, nicht bei jedem Start)
        On Error Resume Next
        Dim wingetCheck
        Set wingetCheck = WshShell.Exec("winget --version")
        wingetCheck.WaitOnReturn = True
        If wingetCheck.ExitCode = 0 Then
            ' Prüfe ob bereits versucht wurde (Flag-Datei)
            Dim ffmpegInstallFlag
            ffmpegInstallFlag = scriptPath & "\.ffmpeg_install_attempted"
            If Not fso.FileExists(ffmpegInstallFlag) Then
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
                ' Erstelle Flag-Datei, damit nicht bei jedem Start versucht wird
                On Error Resume Next
                Dim flagStream
                Set flagStream = fso.CreateTextFile(ffmpegInstallFlag, True)
                flagStream.WriteLine Now()
                flagStream.Close
                On Error Goto 0
            Else
                WriteLog "[INFO] ffmpeg-Installation wurde bereits versucht - überspringe"
            End If
        Else
            WriteLog "[INFO] winget nicht verfügbar - überspringe automatische ffmpeg-Installation"
        End If
        On Error Goto 0
    End If
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

' Setze Umgebungsvariable, um zu signalisieren, dass wir über den Launcher gestartet wurden
' Dies verhindert, dass das Abhängigkeits-Popup in der GUI erscheint
WshShell.Environment("Process")("UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER") = "1"
WriteLog "[INFO] Setze Umgebungsvariable: UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER=1"

WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Starte Anwendung..."
WriteLog "[DEBUG] =========================================="
WriteLog "[DEBUG] Python-Pfad: " & fullPythonPath
WriteLog "[DEBUG] Script-Pfad: " & pythonScript
WriteLog "[DEBUG] Arbeitsverzeichnis: " & scriptPath
WriteLog "[DEBUG] Start-Befehl: " & startCmd
WriteLog "[DEBUG] Umgebungsvariable: UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER=1"
On Error Resume Next
objShell.ShellExecute fullPythonPath, pythonScript, scriptPath, "open", 0
Dim startResult
If Err.Number = 0 Then
    startResult = 0
    WriteLog "[INFO] Start-Befehl ausgeführt (ShellExecute), Exit-Code: " & startResult
    WriteLog "[DEBUG] ✓ ShellExecute erfolgreich"
Else
    WriteLog "[WARNING] ShellExecute fehlgeschlagen, verwende WshShell.Run: " & Err.Description
    WriteLog "[DEBUG] Fehler-Nummer: " & Err.Number
    WriteLog "[DEBUG] Fehler-Quelle: " & Err.Source
    WshShell.CurrentDirectory = scriptPath
    startResult = WshShell.Run(startCmd, 0, False)
    WriteLog "[INFO] Start-Befehl ausgeführt (WshShell.Run), Exit-Code: " & startResult
    WriteLog "[DEBUG] ✓ WshShell.Run erfolgreich"
End If
On Error Goto 0
WriteLog "[DEBUG] =========================================="

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
