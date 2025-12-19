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
        
        ' Methode 4: Prüfe Registry für Python-Installationen
        If pythonExe = "" Then
            Err.Clear
            Dim reg, pythonPath
            Set reg = WshShell.RegRead("HKEY_LOCAL_MACHINE\SOFTWARE\Python\PythonCore\3.11\InstallPath\ExecutablePath")
            If Not IsEmpty(reg) And reg <> "" Then
                ' Versuche pythonw.exe im gleichen Verzeichnis zu finden
                Dim execPath
                execPath = fso.GetParentFolderName(reg)
                If fso.FileExists(execPath & "\pythonw.exe") Then
                    pythonExe = execPath & "\pythonw.exe"
                ElseIf fso.FileExists(reg) Then
                    pythonExe = reg
                End If
            End If
            On Error Resume Next
        End If
        
        ' Methode 5: Suche auf allen Laufwerken (C:, D:, E:, etc.)
        If pythonExe = "" Then
            Err.Clear
            Dim drives, drive, drivePath
            Set drives = fso.Drives
            For Each drive In drives
                If drive.IsReady And drive.DriveType = 2 Then ' Fixed Disk
                    drivePath = drive.DriveLetter & ":\"
                    ' Suche in typischen Pfaden auf diesem Laufwerk
                    Dim altPaths
                    altPaths = Array( _
                        drivePath & "Program Files\Python", _
                        drivePath & "Program Files (x86)\Python", _
                        drivePath & "Python", _
                        drivePath & "Python3*", _
                        drivePath & "Program Files\Python3*" _
                    )
                    For Each altPath In altPaths
                        If fso.FolderExists(altPath) Then
                            If fso.FileExists(altPath & "\pythonw.exe") Then
                                pythonExe = altPath & "\pythonw.exe"
                                Exit For
                            End If
                            ' Suche in Unterordnern
                            Set folder = fso.GetFolder(altPath)
                            For Each subfolder In folder.SubFolders
                                If fso.FileExists(subfolder.Path & "\pythonw.exe") Then
                                    pythonExe = subfolder.Path & "\pythonw.exe"
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
    Dim response
    response = MsgBox("Python nicht gefunden!" & vbCrLf & vbCrLf & _
           "Möchten Sie Python 3.11 automatisch herunterladen und installieren?" & vbCrLf & vbCrLf & _
           "Hinweis: Dies erfordert Administrator-Rechte.", _
           vbYesNo + vbQuestion + vbDefaultButton1, "Python installieren")
    
    If response = vbYes Then
        ' Versuche Python automatisch zu installieren
        Dim installerPath, installerUrl
        installerPath = WshShell.ExpandEnvironmentStrings("%TEMP%\python-installer.exe")
        installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        
        ' Lade Python-Installer herunter mit PowerShell (zuverlässiger für binäre Dateien)
        On Error Resume Next
        Dim downloadCmd
        downloadCmd = "powershell.exe -Command ""[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '" & installerUrl & "' -OutFile '" & installerPath & "'"""
        WshShell.Run downloadCmd, 0, True
        
        If Not fso.FileExists(installerPath) Then
            MsgBox "Konnte Python-Installer nicht herunterladen." & vbCrLf & vbCrLf & _
                   "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                   "https://www.python.org/downloads/", vbCritical, "Fehler"
            WScript.Quit
        End If
        
        ' Installiere Python im Silent-Modus
        ' /quiet = Silent installation
        ' /prependpath = Füge Python zum PATH hinzu
        ' InstallAllUsers = 1 = Für alle Benutzer
        Dim installCmd
        installCmd = installerPath & " /quiet InstallAllUsers=1 PrependPath=1 Include_test=0"
        
        ' Führe Installation mit Administrator-Rechten aus
        WshShell.Run "powershell.exe -Command ""Start-Process -FilePath '" & installerPath & "' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait""", 1, True
        
        ' Warte kurz und prüfe ob Python jetzt verfügbar ist
        WScript.Sleep 3000
        
        ' Prüfe erneut (auch mit erweiterten Suchmethoden)
        On Error Resume Next
        Set pythonCheck = WshShell.Exec("python.exe --version")
        pythonCheck.StdOut.ReadAll
        pythonCheck.WaitOnReturn = True
        If pythonCheck.ExitCode = 0 Then
            pythonExe = "python.exe"
            MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                   "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
        Else
            ' Versuche pythonw.exe
            Set pythonCheck2 = WshShell.Exec("pythonw.exe --version")
            pythonCheck2.StdOut.ReadAll
            pythonCheck2.WaitOnReturn = True
            If pythonCheck2.ExitCode = 0 Then
                pythonExe = "pythonw.exe"
                MsgBox "Python wurde erfolgreich installiert!" & vbCrLf & _
                       "Die Anwendung wird jetzt gestartet.", vbInformation, "Erfolg"
            Else
                MsgBox "Python-Installation fehlgeschlagen oder noch nicht abgeschlossen." & vbCrLf & vbCrLf & _
                       "Bitte installieren Sie Python manuell von:" & vbCrLf & _
                       "https://www.python.org/downloads/" & vbCrLf & vbCrLf & _
                       "Wichtig: Aktivieren Sie 'Add Python to PATH' während der Installation!", _
                       vbCritical, "Fehler"
                ' Lösche Installer
                If fso.FileExists(installerPath) Then fso.DeleteFile installerPath
                WScript.Quit
            End If
        End If
        On Error Goto 0
        
        ' Lösche Installer
        If fso.FileExists(installerPath) Then fso.DeleteFile installerPath
    Else
        ' Benutzer hat abgelehnt
        MsgBox "Python ist erforderlich, um die Anwendung zu starten." & vbCrLf & vbCrLf & _
               "Bitte installieren Sie Python 3.8 oder höher von:" & vbCrLf & _
               "https://www.python.org/downloads/", vbInformation, "Python erforderlich"
        WScript.Quit
    End If
End If

' Starte Python-Skript ohne Konsolen-Fenster
' Verwende CreateObject("WScript.Shell").Run mit WindowStyle=0 (versteckt)
WshShell.CurrentDirectory = scriptPath
WshShell.Run pythonExe & " """ & pythonScript & """", 0, False
