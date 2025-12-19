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

' Starte Python-Skript ohne Konsolen-Fenster
WshShell.Run "pythonw.exe """ & pythonScript & """", 0, False
