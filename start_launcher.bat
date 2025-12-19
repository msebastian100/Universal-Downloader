@echo off
REM Launcher für Universal Downloader
REM Versteckt das Konsolen-Fenster und startet die Anwendung

REM Hole das Verzeichnis der .bat Datei
cd /d "%~dp0"

REM Log-Datei Setup
set LOG_FILE=%~dp0start_launcher.log
echo [%date% %time%] ========================================== >> "%LOG_FILE%"
echo [%date% %time%] Launcher gestartet: %~f0 >> "%LOG_FILE%"
echo [%date% %time%] Verzeichnis: %~dp0 >> "%LOG_FILE%"

REM Prüfe ob start.py existiert
if not exist "start.py" (
    echo [%date% %time%] [ERROR] start.py nicht gefunden in: %~dp0 >> "%LOG_FILE%"
    msgbox "start.py nicht gefunden" 2>nul || echo Fehler: start.py nicht gefunden
    timeout /t 3 >nul 2>&1
    exit /b 1
)
echo [%date% %time%] [OK] start.py gefunden >> "%LOG_FILE%"

REM Versuche Python zu finden
set PYTHON_EXE=
setlocal enabledelayedexpansion

echo [%date% %time%] [INFO] Starte Python-Suche... >> "%LOG_FILE%"

REM Methode 1: Prüfe ob pythonw.exe im PATH ist
echo [%date% %time%] [INFO] Methode 1: Prüfe pythonw.exe im PATH... >> "%LOG_FILE%"
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=pythonw.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 1): pythonw.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 2: Prüfe ob python.exe im PATH ist
echo [%date% %time%] [INFO] pythonw.exe nicht im PATH gefunden >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Methode 2: Prüfe python.exe im PATH... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 2): python.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 3: Prüfe Microsoft Store Python (WindowsApps)
echo [%date% %time%] [INFO] python.exe nicht im PATH gefunden >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Methode 3: Prüfe Microsoft Store Python... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 3): %PYTHON_EXE% >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 4: Suche in typischen Python-Installationspfaden
echo [%date% %time%] [INFO] Methode 4: Suche in typischen Installationspfaden... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe" (
    for %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe") do (
        set PYTHON_EXE=%%~fP
        echo [%date% %time%] [OK] Python gefunden (Methode 4): !PYTHON_EXE! >> "%LOG_FILE%"
    )
    if defined PYTHON_EXE goto :found_python
)

if exist "%PROGRAMFILES%\Python3*\pythonw.exe" (
    for %%P in ("%PROGRAMFILES%\Python3*\pythonw.exe") do (
        set PYTHON_EXE=%%~fP
        echo [%date% %time%] [OK] Python gefunden (Methode 4): !PYTHON_EXE! >> "%LOG_FILE%"
    )
    if defined PYTHON_EXE goto :found_python
)

REM Methode 5: Prüfe Registry für Python-Installationen
echo [%date% %time%] [INFO] Methode 5: Prüfe Registry... >> "%LOG_FILE%"
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    set REG_PATH=%%B
    echo [%date% %time%] [INFO] Registry-Eintrag gefunden: !REG_PATH! >> "%LOG_FILE%"
    if exist "!REG_PATH!" (
        REM Versuche pythonw.exe im gleichen Verzeichnis zu finden
        for %%F in ("!REG_PATH!") do set PYTHON_DIR=%%~dpF
        if exist "!PYTHON_DIR!pythonw.exe" (
            set PYTHON_EXE=!PYTHON_DIR!pythonw.exe
            echo [%date% %time%] [OK] Python gefunden (Methode 5): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
    )
)

REM Methode 6: Suche auf allen Laufwerken (C:, D:, E:, etc.)
echo [%date% %time%] [INFO] Methode 6: Suche auf allen Laufwerken... >> "%LOG_FILE%"
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%D:\" (
        echo [%date% %time%] [INFO] Prüfe Laufwerk: %%D:\ >> "%LOG_FILE%"
        REM Suche in typischen Pfaden auf diesem Laufwerk
        if exist "%%D:\Program Files\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [%date% %time%] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Program Files (x86)\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files (x86)\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [%date% %time%] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [%date% %time%] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Python\pythonw.exe
            echo [%date% %time%] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
    )
)

REM Python nicht gefunden - versuche Installation
echo [%date% %time%] [WARNING] Python nicht gefunden nach allen Suchmethoden >> "%LOG_FILE%"
echo.
echo ========================================
echo FEHLER: Python nicht gefunden!
echo ========================================
echo.
echo Moechten Sie Python 3.11 automatisch herunterladen und installieren?
echo.
choice /C YN /M "Python installieren (J/N)"
if errorlevel 2 (
    echo [%date% %time%] [INFO] Benutzer hat Python-Installation abgelehnt >> "%LOG_FILE%"
    goto :no_install
)
if errorlevel 1 (
    echo [%date% %time%] [INFO] Benutzer hat Python-Installation bestätigt >> "%LOG_FILE%"
    goto :install_python
)

:install_python
echo.
echo Lade Python-Installer herunter...
echo [%date% %time%] [INFO] Starte Python-Download von: https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe >> "%LOG_FILE%"
set INSTALLER_PATH=%TEMP%\python-installer.exe
set INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
echo [%date% %time%] [INFO] Ziel: %INSTALLER_PATH% >> "%LOG_FILE%"

REM Lade Installer herunter mit PowerShell
echo [%date% %time%] [INFO] Führe Download-Befehl aus... >> "%LOG_FILE%"
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER_PATH%'}"
set DOWNLOAD_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Download-Befehl beendet mit Exit-Code: !DOWNLOAD_RESULT! >> "%LOG_FILE%"

if not exist "%INSTALLER_PATH%" (
    echo [%date% %time%] [ERROR] Python-Installer nicht heruntergeladen: %INSTALLER_PATH% >> "%LOG_FILE%"
    echo.
    echo FEHLER: Konnte Python-Installer nicht herunterladen.
    echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
    timeout /t 5 >nul 2>&1
    exit /b 1
)
echo [%date% %time%] [OK] Python-Installer heruntergeladen: %INSTALLER_PATH% >> "%LOG_FILE%"

echo.
echo Installiere Python (dies erfordert Administrator-Rechte)...
echo Bitte bestaetigen Sie die UAC-Abfrage.
echo [%date% %time%] [INFO] Starte Python-Installation mit Administrator-Rechten... >> "%LOG_FILE%"

REM Installiere Python im Silent-Modus mit Administrator-Rechten
powershell -Command "Start-Process -FilePath '%INSTALLER_PATH%' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"
set INSTALL_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Installations-Befehl beendet mit Exit-Code: !INSTALL_RESULT! >> "%LOG_FILE%"

REM Warte kurz
echo [%date% %time%] [INFO] Warte 3 Sekunden auf Installation... >> "%LOG_FILE%"
timeout /t 3 >nul 2>&1

REM Prüfe ob Python jetzt verfügbar ist
echo [%date% %time%] [INFO] Prüfe ob Python jetzt verfügbar ist... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [%date% %time%] [OK] Python erfolgreich installiert und gefunden: python.exe >> "%LOG_FILE%"
    echo.
    echo Python wurde erfolgreich installiert!
    echo.
    REM Lösche Installer
    del "%INSTALLER_PATH%" >nul 2>&1
    echo [%date% %time%] [INFO] Installer-Datei gelöscht >> "%LOG_FILE%"
    goto :found_python
) else (
    REM Versuche pythonw.exe
    echo [%date% %time%] [INFO] python.exe nicht gefunden, versuche pythonw.exe... >> "%LOG_FILE%"
    where pythonw.exe >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_EXE=pythonw.exe
        echo [%date% %time%] [OK] Python erfolgreich installiert und gefunden: pythonw.exe >> "%LOG_FILE%"
        echo.
        echo Python wurde erfolgreich installiert!
        echo.
        REM Lösche Installer
        del "%INSTALLER_PATH%" >nul 2>&1
        echo [%date% %time%] [INFO] Installer-Datei gelöscht >> "%LOG_FILE%"
        goto :found_python
    ) else (
        echo [%date% %time%] [ERROR] Python-Installation fehlgeschlagen - python.exe und pythonw.exe nicht gefunden >> "%LOG_FILE%"
        echo.
        echo FEHLER: Python-Installation fehlgeschlagen oder noch nicht abgeschlossen.
        echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
        echo WICHTIG: Aktivieren Sie "Add Python to PATH" waehrend der Installation!
        REM Lösche Installer
        del "%INSTALLER_PATH%" >nul 2>&1
        timeout /t 5 >nul 2>&1
        exit /b 1
    )
)

:no_install
echo.
echo Python ist erforderlich, um die Anwendung zu starten.
echo Bitte installieren Sie Python 3.8 oder hoeher von: https://www.python.org/downloads/
timeout /t 5 >nul 2>&1
exit /b 1

:found_python
echo [%date% %time%] [INFO] Starte Anwendung mit: %PYTHON_EXE% start.py >> "%LOG_FILE%"
REM Starte Python-Skript (versteckt)
start "" /min "%PYTHON_EXE%" start.py
set START_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Start-Befehl ausgeführt, Exit-Code: !START_RESULT! >> "%LOG_FILE%"
echo [%date% %time%] [OK] Launcher beendet erfolgreich >> "%LOG_FILE%"

REM Beende sofort (damit kein Konsolen-Fenster sichtbar ist)
REM Warte kurz, damit Log geschrieben wird
timeout /t 1 >nul 2>&1
exit /b 0
