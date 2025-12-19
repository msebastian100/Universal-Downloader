@echo off
REM Launcher für Universal Downloader
REM Versteckt das Konsolen-Fenster und startet die Anwendung

REM Hole das Verzeichnis der .bat Datei
cd /d "%~dp0"

REM Prüfe ob start.py existiert
if not exist "start.py" (
    msgbox "start.py nicht gefunden" 2>nul || echo Fehler: start.py nicht gefunden
    timeout /t 3 >nul 2>&1
    exit /b 1
)

REM Versuche Python zu finden
set PYTHON_EXE=
setlocal enabledelayedexpansion

REM Methode 1: Prüfe ob pythonw.exe im PATH ist
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=pythonw.exe
    goto :found_python
)

REM Methode 2: Prüfe ob python.exe im PATH ist
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    goto :found_python
)

REM Methode 3: Prüfe Microsoft Store Python (WindowsApps)
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe
    goto :found_python
)

REM Methode 4: Suche in typischen Python-Installationspfaden
if exist "%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe" (
    for %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
    if defined PYTHON_EXE goto :found_python
)

if exist "%PROGRAMFILES%\Python3*\pythonw.exe" (
    for %%P in ("%PROGRAMFILES%\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
    if defined PYTHON_EXE goto :found_python
)

REM Methode 5: Prüfe Registry für Python-Installationen
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    set REG_PATH=%%B
    if exist "!REG_PATH!" (
        REM Versuche pythonw.exe im gleichen Verzeichnis zu finden
        for %%F in ("!REG_PATH!") do set PYTHON_DIR=%%~dpF
        if exist "!PYTHON_DIR!pythonw.exe" (
            set PYTHON_EXE=!PYTHON_DIR!pythonw.exe
            goto :found_python
        )
    )
)

REM Methode 6: Suche auf allen Laufwerken (C:, D:, E:, etc.)
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%D:\" (
        REM Suche in typischen Pfaden auf diesem Laufwerk
        if exist "%%D:\Program Files\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Program Files (x86)\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files (x86)\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Python\pythonw.exe
            goto :found_python
        )
    )
)

REM Python nicht gefunden - versuche Installation
echo.
echo ========================================
echo FEHLER: Python nicht gefunden!
echo ========================================
echo.
echo Moechten Sie Python 3.11 automatisch herunterladen und installieren?
echo.
choice /C YN /M "Python installieren (J/N)"
if errorlevel 2 goto :no_install
if errorlevel 1 goto :install_python

:install_python
echo.
echo Lade Python-Installer herunter...
set INSTALLER_PATH=%TEMP%\python-installer.exe
set INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

REM Lade Installer herunter mit PowerShell
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER_PATH%'}"

if not exist "%INSTALLER_PATH%" (
    echo.
    echo FEHLER: Konnte Python-Installer nicht herunterladen.
    echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
    timeout /t 5 >nul 2>&1
    exit /b 1
)

echo.
echo Installiere Python (dies erfordert Administrator-Rechte)...
echo Bitte bestaetigen Sie die UAC-Abfrage.

REM Installiere Python im Silent-Modus mit Administrator-Rechten
powershell -Command "Start-Process -FilePath '%INSTALLER_PATH%' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"

REM Warte kurz
timeout /t 3 >nul 2>&1

REM Prüfe ob Python jetzt verfügbar ist
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo.
    echo Python wurde erfolgreich installiert!
    echo.
    REM Lösche Installer
    del "%INSTALLER_PATH%" >nul 2>&1
    goto :found_python
) else (
    echo.
    echo FEHLER: Python-Installation fehlgeschlagen oder noch nicht abgeschlossen.
    echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
    echo WICHTIG: Aktivieren Sie "Add Python to PATH" waehrend der Installation!
    REM Lösche Installer
    del "%INSTALLER_PATH%" >nul 2>&1
    timeout /t 5 >nul 2>&1
    exit /b 1
)

:no_install
echo.
echo Python ist erforderlich, um die Anwendung zu starten.
echo Bitte installieren Sie Python 3.8 oder hoeher von: https://www.python.org/downloads/
timeout /t 5 >nul 2>&1
exit /b 1

:found_python
REM Starte Python-Skript (versteckt)
start "" /min "%PYTHON_EXE%" start.py

REM Beende sofort (damit kein Konsolen-Fenster sichtbar ist)
exit /b 0
