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
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    REM pythonw.exe gefunden - verwende es (ohne Konsolen-Fenster)
    start "" /min pythonw.exe start.py
) else (
    REM pythonw.exe nicht gefunden - versuche python.exe
    where python.exe >nul 2>&1
    if %errorlevel% == 0 (
        REM python.exe gefunden - starte versteckt
        start "" /min python.exe start.py
    ) else (
        REM Python nicht gefunden - zeige Fehler
        msgbox "Python nicht gefunden. Bitte installieren Sie Python 3.8 oder höher." 2>nul || echo Fehler: Python nicht gefunden
        timeout /t 5 >nul 2>&1
        exit /b 1
    )
)

REM Beende sofort (damit kein Konsolen-Fenster sichtbar ist)
exit /b 0
