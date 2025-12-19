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

REM Methode 3: Suche in typischen Python-Installationspfaden
if exist "%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe" (
    for %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
    if defined PYTHON_EXE goto :found_python
)

if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe
    goto :found_python
)

if exist "%PROGRAMFILES%\Python3*\pythonw.exe" (
    for %%P in ("%PROGRAMFILES%\Python3*\pythonw.exe") do set PYTHON_EXE=%%~fP
    if defined PYTHON_EXE goto :found_python
)

REM Python nicht gefunden - zeige Fehler
echo.
echo ========================================
echo FEHLER: Python nicht gefunden!
echo ========================================
echo.
echo Bitte installieren Sie Python 3.8 oder hoeher.
echo Download: https://www.python.org/downloads/
echo.
echo Oder starten Sie die Anwendung mit:
echo   python start.py
echo.
timeout /t 5 >nul 2>&1
exit /b 1

:found_python
REM Starte Python-Skript (versteckt)
start "" /min "%PYTHON_EXE%" start.py

REM Beende sofort (damit kein Konsolen-Fenster sichtbar ist)
exit /b 0
