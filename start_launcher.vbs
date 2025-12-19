Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Hole das Verzeichnis der .vbs Datei
scriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
pythonScript = scriptPath & "\start.py"

' Prüfe ob start.py existiert
If Not fso.FileExists(pythonScript) Then
    MsgBox "start.py nicht gefunden in: " & scriptPath, vbCritical, "Fehler"
    WScript.Quit
End If

' Versuche Python zu finden
pythonExe = ""
On Error Resume Next
' Versuche pythonw.exe zu finden
Set pythonCheck = WshShell.Exec("pythonw.exe --version")
pythonCheck.StdOut.ReadAll
If pythonCheck.ExitCode = 0 Or Err.Number = 0 Then
    pythonExe = "pythonw.exe"
Else
    ' Versuche python.exe zu finden
    Err.Clear
    Set pythonCheck = WshShell.Exec("python.exe --version")
    pythonCheck.StdOut.ReadAll
    If pythonCheck.ExitCode = 0 Or Err.Number = 0 Then
        pythonExe = "python.exe"
    End If
End If
On Error Goto 0

' Falls Python nicht gefunden wurde, versuche es trotzdem mit pythonw.exe
If pythonExe = "" Then
    pythonExe = "pythonw.exe"
End If

' Starte Python-Skript ohne Konsolen-Fenster
' Verwende CreateObject("WScript.Shell").Run mit WindowStyle=0 (versteckt)
WshShell.CurrentDirectory = scriptPath
WshShell.Run pythonExe & " """ & pythonScript & """", 0, False
