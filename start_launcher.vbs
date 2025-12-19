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

' Methode 1: Versuche pythonw.exe direkt (wenn im PATH)
Set pythonCheck = WshShell.Exec("pythonw.exe --version")
pythonCheck.StdOut.ReadAll
pythonCheck.WaitOnReturn = True
If pythonCheck.ExitCode = 0 Then
    pythonExe = "pythonw.exe"
Else
    ' Methode 2: Versuche python.exe (wenn im PATH)
    Err.Clear
    Set pythonCheck2 = WshShell.Exec("python.exe --version")
    pythonCheck2.StdOut.ReadAll
    pythonCheck2.WaitOnReturn = True
    If pythonCheck2.ExitCode = 0 Then
        pythonExe = "python.exe"
    Else
        ' Methode 3: Suche in typischen Python-Installationspfaden
        Err.Clear
        Dim searchPaths, searchPath, folder, file, subfolder
        searchPaths = Array( _
            WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python"), _
            WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Microsoft\WindowsApps"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES%\Python"), _
            WshShell.ExpandEnvironmentStrings("%PROGRAMFILES(X86)%\Python") _
        )
        
        For Each searchPath In searchPaths
            If fso.FolderExists(searchPath) Then
                Set folder = fso.GetFolder(searchPath)
                ' Suche direkt nach pythonw.exe
                If fso.FileExists(searchPath & "\pythonw.exe") Then
                    pythonExe = searchPath & "\pythonw.exe"
                    Exit For
                End If
                ' Suche in Unterordnern (z.B. Python3.11, Python3.12)
                For Each subfolder In folder.SubFolders
                    If fso.FileExists(subfolder.Path & "\pythonw.exe") Then
                        pythonExe = subfolder.Path & "\pythonw.exe"
                        Exit For
                    End If
                Next
                If pythonExe <> "" Then Exit For
            End If
        Next
    End If
End If
On Error Goto 0

' Falls Python immer noch nicht gefunden wurde, zeige Fehler
If pythonExe = "" Then
    MsgBox "Python nicht gefunden!" & vbCrLf & vbCrLf & _
           "Bitte installieren Sie Python 3.8 oder höher." & vbCrLf & _
           "Download: https://www.python.org/downloads/" & vbCrLf & vbCrLf & _
           "Oder starten Sie die Anwendung mit:" & vbCrLf & _
           "python start.py", vbCritical, "Fehler"
    WScript.Quit
End If

' Starte Python-Skript ohne Konsolen-Fenster
' Verwende CreateObject("WScript.Shell").Run mit WindowStyle=0 (versteckt)
WshShell.CurrentDirectory = scriptPath
WshShell.Run pythonExe & " """ & pythonScript & """", 0, False
