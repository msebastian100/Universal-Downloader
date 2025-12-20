@echo off
REM Launcher für Universal Downloader
REM Prüft auf Updates, installiert Abhängigkeiten und startet die Anwendung

REM Hole das Verzeichnis der .bat Datei
cd /d "%~dp0"

REM Log-Datei Setup
set "LOG_FILE=%~dp0bat.log.txt"
echo [%date% %time%] ========================================== >> "%LOG_FILE%"
echo [%date% %time%] Launcher gestartet: %~f0 >> "%LOG_FILE%"
echo [%date% %time%] Verzeichnis: %~dp0 >> "%LOG_FILE%"

REM Pruefe ob Log geschrieben werden kann
if not exist "%LOG_FILE%" (
    set "LOG_FILE=%TEMP%\bat.log.txt"
    echo [%date% %time%] ========================================== >> "%LOG_FILE%"
    echo [%date% %time%] Launcher gestartet: %~f0 >> "%LOG_FILE%"
    echo [%date% %time%] Verzeichnis: %~dp0 >> "%LOG_FILE%"
    echo [%date% %time%] Log-Datei: %LOG_FILE% (Fallback) >> "%LOG_FILE%"
)

REM Prüfe ob start.py existiert
if not exist "start.py" (
    echo [%date% %time%] [ERROR] start.py nicht gefunden in: %~dp0 >> "%LOG_FILE%"
    echo.
    echo FEHLER: start.py nicht gefunden in: %~dp0
    echo.
    echo Log-Datei: %LOG_FILE%
    echo.
    pause
    exit /b 1
)
echo [%date% %time%] [OK] start.py gefunden >> "%LOG_FILE%"

REM Prüfe ob Icon existiert
if exist "icon.ico" (
    echo [%date% %time%] [INFO] Icon gefunden: icon.ico >> "%LOG_FILE%"
) else if exist "icon.png" (
    echo [%date% %time%] [INFO] Icon gefunden: icon.png >> "%LOG_FILE%"
) else (
    echo [%date% %time%] [WARNING] Kein Icon gefunden >> "%LOG_FILE%"
)

REM Prüfe auf Updates (nur wenn nicht --no-update Parameter übergeben wurde)
if not "%1"=="--no-update" (
    echo [%date% %time%] [INFO] Pruefe auf Updates... >> "%LOG_FILE%"
    
    REM Prüfe ob update_from_github.py existiert
    if exist "update_from_github.py" (
        echo [%date% %time%] [INFO] Starte Update-Check... >> "%LOG_FILE%"
        
        REM Finde Python für Update-Check (vereinfachte Suche)
        set "FULL_PYTHON_PATH_UPDATE="
        
        REM Methode 1: Prüfe pythonw.exe im PATH
        where pythonw.exe >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%i in ('where pythonw.exe') do (
                set "FULL_PYTHON_PATH_UPDATE=%%i"
                goto :python_found_update
            )
        )
        
        REM Methode 2: Prüfe typische Installationspfade
        for %%d in (C D E F G H) do (
            if exist "%%d:\Python*\pythonw.exe" (
                for /f "delims=" %%i in ('dir /b /s "%%d:\Python*\pythonw.exe" 2^>nul') do (
                    set "FULL_PYTHON_PATH_UPDATE=%%i"
                    goto :python_found_update
                )
            )
        )
        
        REM Methode 3: Prüfe Microsoft Store Python
        if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
            set "FULL_PYTHON_PATH_UPDATE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
            goto :python_found_update
        )
        
        REM Methode 4: Fallback zu pythonw.exe
        set "FULL_PYTHON_PATH_UPDATE=pythonw.exe"
        
        :python_found_update
        echo [%date% %time%] [INFO] Python für Update-Check: !FULL_PYTHON_PATH_UPDATE! >> "%LOG_FILE%"
        
        REM Führe Update-Check aus
        "!FULL_PYTHON_PATH_UPDATE!" "update_from_github.py" >> "%LOG_FILE%" 2>&1
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

REM Versuche Python zu finden (auf allen Laufwerken)
set PYTHON_EXE=
setlocal enabledelayedexpansion

echo [%date% %time%] [INFO] Starte Python-Suche auf allen Laufwerken... >> "%LOG_FILE%"

REM Methode 1: PATH
echo [%date% %time%] [INFO] Methode 1: Pruefe pythonw.exe im PATH... >> "%LOG_FILE%"
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=pythonw.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 1): pythonw.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 2: python.exe im PATH
echo [%date% %time%] [INFO] pythonw.exe nicht im PATH gefunden >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Methode 2: Pruefe python.exe im PATH... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 2): python.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 3: Microsoft Store Python
echo [%date% %time%] [INFO] python.exe nicht im PATH gefunden >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Methode 3: Pruefe Microsoft Store Python... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe
    echo [%date% %time%] [OK] Python gefunden (Methode 3): %PYTHON_EXE% >> "%LOG_FILE%"
    goto :found_python
)

REM Methode 4: Typische Installationspfade
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

REM Methode 5: Registry
echo [%date% %time%] [INFO] Methode 5: Pruefe Registry... >> "%LOG_FILE%"
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    set REG_PATH=%%B
    echo [%date% %time%] [INFO] Registry-Eintrag gefunden: !REG_PATH! >> "%LOG_FILE%"
    if exist "!REG_PATH!" (
        for %%F in ("!REG_PATH!") do set PYTHON_DIR=%%~dpF
        if exist "!PYTHON_DIR!pythonw.exe" (
            set PYTHON_EXE=!PYTHON_DIR!pythonw.exe
            echo [%date% %time%] [OK] Python gefunden (Methode 5): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
    )
)

REM Methode 6: Suche auf ALLEN Laufwerken (C:, D:, E:, etc.)
echo [%date% %time%] [INFO] Methode 6: Suche auf allen Laufwerken... >> "%LOG_FILE%"
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%D:\" (
        echo [%date% %time%] [INFO] Pruefe Laufwerk: %%D:\ >> "%LOG_FILE%"
        REM Suche in typischen Pfaden
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
        if exist "%%D:\Program Files\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Program Files\Python\pythonw.exe
            echo [%date% %time%] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
        if exist "%%D:\Program Files (x86)\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Program Files (x86)\Python\pythonw.exe
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
    echo [%date% %time%] [INFO] Benutzer hat Python-Installation bestaetigt >> "%LOG_FILE%"
    goto :install_python
)

:install_python
echo.
echo Lade Python-Installer herunter...
echo [%date% %time%] [INFO] Starte Python-Download... >> "%LOG_FILE%"
set INSTALLER_PATH=%TEMP%\python-installer.exe
set INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER_PATH%'}"
set DOWNLOAD_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Download-Befehl beendet mit Exit-Code: !DOWNLOAD_RESULT! >> "%LOG_FILE%"

if not exist "%INSTALLER_PATH%" (
    echo [%date% %time%] [ERROR] Python-Installer nicht heruntergeladen >> "%LOG_FILE%"
    echo.
    echo FEHLER: Konnte Python-Installer nicht herunterladen.
    echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
    echo.
    echo Log-Datei: %LOG_FILE%
    pause
    exit /b 1
)
echo [%date% %time%] [OK] Python-Installer heruntergeladen >> "%LOG_FILE%"

echo.
echo Installiere Python (dies erfordert Administrator-Rechte)...
echo [%date% %time%] [INFO] Starte Python-Installation mit Administrator-Rechten... >> "%LOG_FILE%"

powershell -Command "Start-Process -FilePath '%INSTALLER_PATH%' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"
set INSTALL_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Installations-Befehl beendet mit Exit-Code: !INSTALL_RESULT! >> "%LOG_FILE%"

timeout /t 3 >nul 2>&1

echo [%date% %time%] [INFO] Pruefe ob Python jetzt verfuegbar ist... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [%date% %time%] [OK] Python erfolgreich installiert: python.exe >> "%LOG_FILE%"
    echo.
    echo Python wurde erfolgreich installiert!
    echo.
    del "%INSTALLER_PATH%" >nul 2>&1
    goto :found_python
) else (
    where pythonw.exe >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_EXE=pythonw.exe
        echo [%date% %time%] [OK] Python erfolgreich installiert: pythonw.exe >> "%LOG_FILE%"
        echo.
        echo Python wurde erfolgreich installiert!
        echo.
        del "%INSTALLER_PATH%" >nul 2>&1
        goto :found_python
    ) else (
        echo [%date% %time%] [ERROR] Python-Installation fehlgeschlagen >> "%LOG_FILE%"
        echo.
        echo FEHLER: Python-Installation fehlgeschlagen oder noch nicht abgeschlossen.
        echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
        echo WICHTIG: Aktivieren Sie "Add Python to PATH" waehrend der Installation!
        echo.
        echo Log-Datei: %LOG_FILE%
        del "%INSTALLER_PATH%" >nul 2>&1
        pause
        exit /b 1
    )
)

:no_install
echo.
echo ========================================
echo Python ist erforderlich!
echo ========================================
echo.
echo Python ist erforderlich, um die Anwendung zu starten.
echo Bitte installieren Sie Python 3.8 oder hoeher von: https://www.python.org/downloads/
echo.
echo Log-Datei: %LOG_FILE%
echo.
pause
exit /b 1

:found_python
REM Finde vollständigen Python-Pfad
set "FULL_PYTHON_PATH=%PYTHON_EXE%"
if not exist "%PYTHON_EXE%" (
    where "%PYTHON_EXE%" >nul 2>&1
    if %errorlevel% == 0 (
        for /f "delims=" %%P in ('where "%PYTHON_EXE%" 2^>nul') do (
            set "FULL_PYTHON_PATH=%%P"
            goto :found_full_path
        )
    )
)
:found_full_path
if "!FULL_PYTHON_PATH!"=="" set "FULL_PYTHON_PATH=%PYTHON_EXE%"

echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Python gefunden: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Arbeitsverzeichnis: %~dp0 >> "%LOG_FILE%"
echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"

REM Prüfe und installiere requirements.txt
if exist "requirements.txt" (
    echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
    echo [%date% %time%] [INFO] Pruefe requirements.txt... >> "%LOG_FILE%"
    echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
    REM Prüfe ob pip verfügbar ist
    echo [%date% %time%] [INFO] Pruefe pip-Verfuegbarkeit... >> "%LOG_FILE%"
    !FULL_PYTHON_PATH! -m pip --version >> "%LOG_FILE%" 2>&1
    set PIP_CHECK_RESULT=%errorlevel%
    echo [%date% %time%] [INFO] pip --version Exit-Code: !PIP_CHECK_RESULT! >> "%LOG_FILE%"
    if !PIP_CHECK_RESULT! == 0 (
        echo [%date% %time%] [OK] pip verfügbar >> "%LOG_FILE%"
        echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
        echo [%date% %time%] [INFO] Starte requirements.txt Installation... >> "%LOG_FILE%"
        echo [%date% %time%] [INFO] Befehl: !FULL_PYTHON_PATH! -m pip install --upgrade -r "requirements.txt" >> "%LOG_FILE%"
        echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
        REM Führe Installation aus und leite Ausgabe ins Log um
        !FULL_PYTHON_PATH! -m pip install --upgrade -r "requirements.txt" >> "%LOG_FILE%" 2>&1
        set PIP_RESULT=%errorlevel%
        echo [%date% %time%] [INFO] pip install Exit-Code: !PIP_RESULT! >> "%LOG_FILE%"
        if !PIP_RESULT! == 0 (
            echo [%date% %time%] [OK] requirements.txt erfolgreich installiert/aktualisiert >> "%LOG_FILE%"
        ) else (
            echo [%date% %time%] [WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: !PIP_RESULT!) >> "%LOG_FILE%"
        )
    ) else (
        echo [%date% %time%] [WARNING] pip nicht verfügbar - überspringe requirements.txt Installation >> "%LOG_FILE%"
    )
) else (
    echo [%date% %time%] [WARNING] requirements.txt nicht gefunden >> "%LOG_FILE%"
)

REM Starte start.py
cd /d "%~dp0"
echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Starte Anwendung... >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Start-Befehl: "!FULL_PYTHON_PATH!" "start.py" >> "%LOG_FILE%"
echo [%date% %time%] [INFO] Arbeitsverzeichnis: %~dp0 >> "%LOG_FILE%"
echo [%date% %time%] [INFO] ========================================== >> "%LOG_FILE%"
start "" /B /MIN "!FULL_PYTHON_PATH!" "start.py"
set START_RESULT=%errorlevel%
echo [%date% %time%] [INFO] Start-Befehl ausgefuehrt, Exit-Code: !START_RESULT! >> "%LOG_FILE%"

REM Warte kurz und pruefe ob Prozess laeuft
timeout /t 2 >nul 2>&1
for %%F in ("!FULL_PYTHON_PATH!") do set "PYTHON_EXE_NAME=%%~nxF"
echo [%date% %time%] [INFO] Pruefe ob Python-Prozess laeuft: !PYTHON_EXE_NAME! >> "%LOG_FILE%"
tasklist /FI "IMAGENAME eq !PYTHON_EXE_NAME!" /FO CSV /NH >> "%LOG_FILE%" 2>&1
tasklist /FI "IMAGENAME eq !PYTHON_EXE_NAME!" /FO CSV /NH 2>nul | find /i "!PYTHON_EXE_NAME!" >nul 2>&1
if %errorlevel% == 0 (
    echo [%date% %time%] [OK] Python-Prozess laeuft (!PYTHON_EXE_NAME!) >> "%LOG_FILE%"
) else (
    echo [%date% %time%] [WARNING] Python-Prozess scheint nicht zu laufen >> "%LOG_FILE%"
    REM Pruefe auch python.exe
    tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH >> "%LOG_FILE%" 2>&1
    tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2>nul | find /i "python.exe" >nul 2>&1
    if %errorlevel% == 0 (
        echo [%date% %time%] [OK] Python-Prozess gefunden (python.exe) >> "%LOG_FILE%"
    ) else (
        echo [%date% %time%] [WARNING] Kein Python-Prozess gefunden >> "%LOG_FILE%"
        echo.
        echo ========================================
        echo WARNUNG: Python-Prozess wurde nicht gefunden!
        echo ========================================
        echo.
        echo Log-Datei: %LOG_FILE%
        echo.
        echo Bitte pruefen Sie die Log-Datei fuer Details.
        echo.
        pause
    )
)

echo [%date% %time%] [OK] ========================================== >> "%LOG_FILE%"
echo [%date% %time%] [OK] Launcher beendet erfolgreich >> "%LOG_FILE%"
echo [%date% %time%] [OK] ========================================== >> "%LOG_FILE%"

if errorlevel 1 (
    echo.
    echo ========================================
    echo FEHLER beim Starten der Anwendung!
    echo ========================================
    echo.
    echo Log-Datei: %LOG_FILE%
    echo.
    pause
    exit /b 1
)

timeout /t 1 >nul 2>&1
exit /b 0
