@echo off
REM Launcher für Universal Downloader
REM Versteckt das Konsolen-Fenster und startet die Anwendung

REM Hole das Verzeichnis der .bat Datei
cd /d "%~dp0"

REM Prüfe ob start.py existiert
if not exist "start.py" (
    echo Fehler: start.py nicht gefunden
    pause
    exit /b 1
)

REM Starte Python-Skript ohne Konsolen-Fenster (pythonw.exe)
start "" pythonw.exe start.py

REM Beende sofort (damit kein Konsolen-Fenster sichtbar ist)
exit /b 0
