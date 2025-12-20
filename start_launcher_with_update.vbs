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

' Log-Datei Setup
Dim logFile, logStream
logFile = scriptPath & "\vbs.log.txt"
On Error Resume Next
Set logStream = fso.OpenTextFile(logFile, 8, True)
If Err.Number <> 0 Then
    Err.Clear
    Set logStream = fso.OpenTextFile(logFile, 2, True)
    If Err.Number <> 0 Then
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
        logStream.Close
        Set logStream = fso.OpenTextFile(logFile, 8, True)
    End If
    On Error Goto 0
End Sub

WriteLog "=========================================="
WriteLog "Launcher mit Update-Check gestartet: " & WScript.ScriptFullName
WriteLog "Verzeichnis: " & scriptPath
WriteLog ""

' Prüfe ob start.py existiert
If Not fso.FileExists(pythonScript) Then
    WriteLog "[ERROR] start.py nicht gefunden: " & pythonScript
    MsgBox "start.py nicht gefunden!" & vbCrLf & vbCrLf & "Pfad: " & pythonScript, vbCritical, "Fehler"
    WScript.Quit 1
End If

WriteLog "[OK] start.py gefunden: " & pythonScript

' Prüfe auf Updates (nur wenn nicht --no-update Parameter übergeben wurde)
If WScript.Arguments.Count = 0 Or WScript.Arguments(0) <> "--no-update" Then
    WriteLog "[INFO] Prüfe auf Updates..."
    
    ' Prüfe ob update_from_github.py existiert
    If fso.FileExists(updateScript) Then
        WriteLog "[INFO] Starte Update-Check..."
        
        ' Finde Python
        Dim pythonExe, fullPythonPath
        pythonExe = "pythonw.exe"
        fullPythonPath = ""
        
        ' Methode 1: Prüfe pythonw.exe im PATH
        On Error Resume Next
        Dim whereResult
        Set whereResult = WshShell.Exec("where " & pythonExe)
        whereResult.StdOut.ReadLine ' Warte auf erste Zeile
        whereResult.StdOut.SkipLine
        Dim whereOutput
        whereOutput = whereResult.StdOut.ReadAll
        whereResult.StdOut.Close
        whereResult.WaitOnReturn = True
        
        If whereResult.ExitCode = 0 And Len(whereOutput) > 0 Then
            Dim whereLines
            whereLines = Split(whereOutput, vbCrLf)
            If UBound(whereLines) >= 0 Then
                fullPythonPath = Trim(whereLines(0))
            End If
        End If
        On Error Goto 0
        
        ' Methode 2: Prüfe typische Installationspfade
        If Len(fullPythonPath) = 0 Then
            Dim commonPaths
            commonPaths = Array( _
                WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python*\pythonw.exe"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python*\pythonw.exe"), _
                WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python*\pythonw.exe"), _
                "C:\Python*\pythonw.exe", _
                "D:\Python*\pythonw.exe" _
            )
            
            Dim path, found
            found = False
            For Each path In commonPaths
                Dim matches
                Set matches = fso.GetFolder(fso.GetParentFolderName(path)).GetFiles(fso.GetFileName(path))
                If matches.Count > 0 Then
                    fullPythonPath = matches(0).Path
                    found = True
                    Exit For
                End If
            Next
        End If
        
        ' Methode 3: Fallback zu pythonw.exe
        If Len(fullPythonPath) = 0 Then
            fullPythonPath = pythonExe
        End If
        
        WriteLog "[INFO] Python gefunden: " & fullPythonPath
        
        ' Führe Update-Check aus
        Dim updateResult
        On Error Resume Next
        updateResult = WshShell.Run("""" & fullPythonPath & """ """ & updateScript & """", 0, True)
        On Error Goto 0
        
        If updateResult = 0 Then
            WriteLog "[OK] Update-Check abgeschlossen"
        Else
            WriteLog "[WARNING] Update-Check fehlgeschlagen oder keine Updates verfügbar (Exit-Code: " & updateResult & ")"
        End If
    Else
        WriteLog "[WARNING] update_from_github.py nicht gefunden - überspringe Update-Check"
    End If
    WriteLog ""
End If

' Finde Python für start.py
Dim pythonExe2, fullPythonPath2
pythonExe2 = "pythonw.exe"
fullPythonPath2 = ""

' Methode 1: Prüfe pythonw.exe im PATH
On Error Resume Next
Dim whereResult2
Set whereResult2 = WshShell.Exec("where " & pythonExe2)
whereResult2.StdOut.ReadLine
whereResult2.StdOut.SkipLine
Dim whereOutput2
whereOutput2 = whereResult2.StdOut.ReadAll
whereResult2.StdOut.Close
whereResult2.WaitOnReturn = True

If whereResult2.ExitCode = 0 And Len(whereOutput2) > 0 Then
    Dim whereLines2
    whereLines2 = Split(whereOutput2, vbCrLf)
    If UBound(whereLines2) >= 0 Then
        fullPythonPath2 = Trim(whereLines2(0))
    End If
End If
On Error Goto 0

' Methode 2: Prüfe typische Installationspfade
If Len(fullPythonPath2) = 0 Then
    Dim commonPaths2
    commonPaths2 = Array( _
        WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python*\pythonw.exe"), _
        WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python*\pythonw.exe"), _
        WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python*\pythonw.exe"), _
        "C:\Python*\pythonw.exe", _
        "D:\Python*\pythonw.exe" _
    )
    
    Dim path2, found2
    found2 = False
    For Each path2 In commonPaths2
        Dim matches2
        Set matches2 = fso.GetFolder(fso.GetParentFolderName(path2)).GetFiles(fso.GetFileName(path2))
        If matches2.Count > 0 Then
            fullPythonPath2 = matches2(0).Path
            found2 = True
            Exit For
        End If
    Next
End If

' Methode 3: Fallback zu pythonw.exe
If Len(fullPythonPath2) = 0 Then
    fullPythonPath2 = pythonExe2
End If

WriteLog "[INFO] Starte Anwendung mit: " & fullPythonPath2 & " " & pythonScript

' Starte Anwendung
On Error Resume Next
objShell.ShellExecute fullPythonPath2, Chr(34) & pythonScript & Chr(34), scriptPath, "open", 0
On Error Goto 0

' Warte kurz und prüfe ob Prozess gestartet wurde
WScript.Sleep 2000

Dim processFound
processFound = False
On Error Resume Next
Dim processList
Set processList = GetObject("winmgmts:").ExecQuery("SELECT * FROM Win32_Process WHERE Name='pythonw.exe' OR Name='python.exe'")
For Each proc In processList
    Dim cmdLine
    cmdLine = proc.CommandLine
    If InStr(cmdLine, "start.py") > 0 Then
        processFound = True
        Exit For
    End If
Next
On Error Goto 0

If processFound Then
    WriteLog "[OK] Anwendung erfolgreich gestartet"
Else
    WriteLog "[WARNING] Prozess nicht gefunden - Anwendung möglicherweise nicht gestartet"
End If

WriteLog "[OK] Launcher beendet"
logStream.Close
