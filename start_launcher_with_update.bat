@echo off
REM Start-Skript für Universal Downloader (Windows)
REM Prüft auf Updates und startet die Anwendung

setlocal enabledelayedexpansion

REM Hole das Verzeichnis des Skripts
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo ==========================================
echo Universal Downloader - Launcher
echo ==========================================
echo.

REM Log-Datei Setup
set "LOG_FILE=%SCRIPT_DIR%bat.log.txt"
if not exist "%LOG_FILE%" (
    echo [%date% %time%] ========================================== > "%LOG_FILE%"
    echo [%date% %time%] Launcher mit Update-Check gestartet: %~f0 >> "%LOG_FILE%"
    echo [%date% %time%] Verzeichnis: %SCRIPT_DIR% >> "%LOG_FILE%"
) else (
    echo [%date% %time%] ========================================== >> "%LOG_FILE%"
    echo [%date% %time%] Launcher mit Update-Check gestartet: %~f0 >> "%LOG_FILE%"
    echo [%date% %time%] Verzeichnis: %SCRIPT_DIR% >> "%LOG_FILE%"
)

REM Prüfe ob start.py existiert
if not exist "start.py" (
    echo [%date% %time%] [ERROR] start.py nicht gefunden >> "%LOG_FILE%"
    echo.
    echo Fehler: start.py nicht gefunden!
    echo Bitte stellen Sie sicher, dass Sie im richtigen Verzeichnis sind.
    pause
    exit /b 1
)

echo [%date% %time%] [OK] start.py gefunden >> "%LOG_FILE%"

REM Prüfe auf Updates (nur wenn nicht --no-update Parameter übergeben wurde)
if not "%1"=="--no-update" (
    echo [%date% %time%] [INFO] Pruefe auf Updates... >> "%LOG_FILE%"
    
    REM Prüfe ob update_from_github.py existiert
    if exist "update_from_github.py" (
        echo [%date% %time%] [INFO] Starte Update-Check... >> "%LOG_FILE%"
        
        REM Finde Python
        set "FULL_PYTHON_PATH="
        
        REM Methode 1: Prüfe pythonw.exe im PATH
        where pythonw.exe >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%i in ('where pythonw.exe') do (
                set "FULL_PYTHON_PATH=%%i"
                goto :python_found
            )
        )
        
        REM Methode 2: Prüfe typische Installationspfade
        for %%d in (C D E F G H) do (
            if exist "%%d:\Python*\pythonw.exe" (
                for /f "delims=" %%i in ('dir /b /s "%%d:\Python*\pythonw.exe" 2^>nul') do (
                    set "FULL_PYTHON_PATH=%%i"
                    goto :python_found
                )
            )
        )
        
        REM Methode 3: Prüfe Microsoft Store Python
        if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
            set "FULL_PYTHON_PATH=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
            goto :python_found
        )
        
        REM Methode 4: Fallback zu pythonw.exe
        set "FULL_PYTHON_PATH=pythonw.exe"
        
        :python_found
        echo [%date% %time%] [INFO] Python gefunden: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
        
        REM Führe Update-Check aus
        "!FULL_PYTHON_PATH!" "update_from_github.py" >> "%LOG_FILE%" 2>&1
        set UPDATE_RESULT=!errorlevel!
        
        if !UPDATE_RESULT! equ 0 (
            echo [%date% %time%] [OK] Update-Check abgeschlossen >> "%LOG_FILE%"
        ) else (
            echo [%date% %time%] [WARNING] Update-Check fehlgeschlagen oder keine Updates verfuegbar (Exit-Code: !UPDATE_RESULT!) >> "%LOG_FILE%"
        )
    ) else (
        echo [%date% %time%] [WARNING] update_from_github.py nicht gefunden - ueberspringe Update-Check >> "%LOG_FILE%"
    )
    echo. >> "%LOG_FILE%"
)

REM Finde Python für start.py
set "FULL_PYTHON_PATH="

REM Methode 1: Prüfe pythonw.exe im PATH
where pythonw.exe >nul 2>&1
if !errorlevel! equ 0 (
    for /f "delims=" %%i in ('where pythonw.exe') do (
        set "FULL_PYTHON_PATH=%%i"
        goto :python_found2
    )
)

REM Methode 2: Prüfe typische Installationspfade
for %%d in (C D E F G H) do (
    if exist "%%d:\Python*\pythonw.exe" (
        for /f "delims=" %%i in ('dir /b /s "%%d:\Python*\pythonw.exe" 2^>nul') do (
            set "FULL_PYTHON_PATH=%%i"
            goto :python_found2
        )
    )
)

REM Methode 3: Prüfe Microsoft Store Python
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set "FULL_PYTHON_PATH=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
    goto :python_found2
)

REM Methode 4: Fallback zu pythonw.exe
set "FULL_PYTHON_PATH=pythonw.exe"

:python_found2
echo [%date% %time%] [INFO] Starte Anwendung mit: !FULL_PYTHON_PATH! start.py >> "%LOG_FILE%"

REM Starte Anwendung
start "" /B /MIN "!FULL_PYTHON_PATH!" "start.py"

REM Warte kurz
timeout /t 2 /nobreak >nul

REM Prüfe ob Prozess gestartet wurde
tasklist /FI "IMAGENAME eq pythonw.exe" /FI "WINDOWTITLE eq *start.py*" 2>nul | find /I "pythonw.exe" >nul
if !errorlevel! equ 0 (
    echo [%date% %time%] [OK] Anwendung erfolgreich gestartet >> "%LOG_FILE%"
) else (
    echo [%date% %time%] [WARNING] Prozess nicht gefunden - Anwendung moeglicherweise nicht gestartet >> "%LOG_FILE%"
)

echo [%date% %time%] [OK] Launcher beendet >> "%LOG_FILE%"

endlocal
