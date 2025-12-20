@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "LOG_FILE=%~dp0bat.log.txt"
set "datetime="
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set "datetime=%%I"
if "!datetime!"=="" (
    set "datetime=%date% %time%"
) else (
    set "datetime=!datetime:~0,4!-!datetime:~4,2!-!datetime:~6,2! !datetime:~8,2!:!datetime:~10,2!:!datetime:~12,2!"
)

echo [!datetime!] ========================================== >> "%LOG_FILE%"
echo [!datetime!] Launcher gestartet: %~f0 >> "%LOG_FILE%"
echo [!datetime!] Verzeichnis: %~dp0 >> "%LOG_FILE%"

if not exist "%LOG_FILE%" (
    set "LOG_FILE=%TEMP%\bat.log.txt"
    echo [!datetime!] ========================================== >> "%LOG_FILE%"
    echo [!datetime!] Launcher gestartet: %~f0 >> "%LOG_FILE%"
    echo [!datetime!] Verzeichnis: %~dp0 >> "%LOG_FILE%"
    echo [!datetime!] Log-Datei: %LOG_FILE% (Fallback) >> "%LOG_FILE%"
)

if not exist "start.py" (
    echo [!datetime!] [ERROR] start.py nicht gefunden in: %~dp0 >> "%LOG_FILE%"
    echo.
    echo FEHLER: start.py nicht gefunden in: %~dp0
    echo.
    echo Log-Datei: %LOG_FILE%
    echo.
    pause
    exit /b 1
)
echo [!datetime!] [OK] start.py gefunden >> "%LOG_FILE%"

if exist "icon.ico" (
    echo [!datetime!] [INFO] Icon gefunden: icon.ico >> "%LOG_FILE%"
) else if exist "icon.png" (
    echo [!datetime!] [INFO] Icon gefunden: icon.png >> "%LOG_FILE%"
) else (
    echo [!datetime!] [WARNING] Kein Icon gefunden >> "%LOG_FILE%"
)

if not "%1"=="--no-update" (
    echo [!datetime!] [INFO] Pruefe auf Updates... >> "%LOG_FILE%"
    if exist "update_from_github.py" (
        echo [!datetime!] [INFO] Starte Update-Check... >> "%LOG_FILE%"
        set "FULL_PYTHON_PATH_UPDATE="
        where pythonw.exe >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%i in ('where pythonw.exe') do (
                set "FULL_PYTHON_PATH_UPDATE=%%i"
                goto :python_found_update
            )
        )
        for %%d in (C D E F G H) do (
            if exist "%%d:\Python*\pythonw.exe" (
                for /f "delims=" %%i in ('dir /b /s "%%d:\Python*\pythonw.exe" 2^>nul') do (
                    set "FULL_PYTHON_PATH_UPDATE=%%i"
                    goto :python_found_update
                )
            )
        )
        if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
            set "FULL_PYTHON_PATH_UPDATE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe"
            goto :python_found_update
        )
        set "FULL_PYTHON_PATH_UPDATE=pythonw.exe"
        :python_found_update
        echo [!datetime!] [INFO] Python fuer Update-Check: !FULL_PYTHON_PATH_UPDATE! >> "%LOG_FILE%"
        "!FULL_PYTHON_PATH_UPDATE!" "update_from_github.py" >> "%LOG_FILE%" 2>&1
        set UPDATE_RESULT=!errorlevel!
        if !UPDATE_RESULT! equ 0 (
            echo [!datetime!] [OK] Update-Check abgeschlossen >> "%LOG_FILE%"
        ) else (
            echo [!datetime!] [WARNING] Update-Check fehlgeschlagen (Exit-Code: !UPDATE_RESULT!) >> "%LOG_FILE%"
        )
    ) else (
        echo [!datetime!] [WARNING] update_from_github.py nicht gefunden >> "%LOG_FILE%"
    )
    echo. >> "%LOG_FILE%"
)

set PYTHON_EXE=
echo [!datetime!] [INFO] Starte Python-Suche... >> "%LOG_FILE%"

echo [!datetime!] [INFO] Methode 1: Pruefe pythonw.exe im PATH... >> "%LOG_FILE%"
where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=pythonw.exe
    echo [!datetime!] [OK] Python gefunden (Methode 1): pythonw.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

echo [!datetime!] [INFO] Methode 2: Pruefe python.exe im PATH... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [!datetime!] [OK] Python gefunden (Methode 2): python.exe im PATH >> "%LOG_FILE%"
    goto :found_python
)

echo [!datetime!] [INFO] Methode 3: Pruefe Microsoft Store Python... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Microsoft\WindowsApps\pythonw.exe
    echo [!datetime!] [OK] Python gefunden (Methode 3): %PYTHON_EXE% >> "%LOG_FILE%"
    goto :found_python
)

echo [!datetime!] [INFO] Methode 4: Suche in typischen Installationspfaden... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe" (
    for %%P in ("%LOCALAPPDATA%\Programs\Python\Python3*\pythonw.exe") do (
        set PYTHON_EXE=%%~fP
        echo [!datetime!] [OK] Python gefunden (Methode 4): !PYTHON_EXE! >> "%LOG_FILE%"
    )
    if defined PYTHON_EXE goto :found_python
)

if exist "%PROGRAMFILES%\Python3*\pythonw.exe" (
    for %%P in ("%PROGRAMFILES%\Python3*\pythonw.exe") do (
        set PYTHON_EXE=%%~fP
        echo [!datetime!] [OK] Python gefunden (Methode 4): !PYTHON_EXE! >> "%LOG_FILE%"
    )
    if defined PYTHON_EXE goto :found_python
)

echo [!datetime!] [INFO] Methode 5: Pruefe Registry... >> "%LOG_FILE%"
for /f "tokens=2*" %%A in ('reg query "HKLM\SOFTWARE\Python\PythonCore" /s /v "ExecutablePath" 2^>nul ^| findstr /i "ExecutablePath"') do (
    set REG_PATH=%%B
    echo [!datetime!] [INFO] Registry-Eintrag gefunden: !REG_PATH! >> "%LOG_FILE%"
    if exist "!REG_PATH!" (
        for %%F in ("!REG_PATH!") do set PYTHON_DIR=%%~dpF
        if exist "!PYTHON_DIR!pythonw.exe" (
            set PYTHON_EXE=!PYTHON_DIR!pythonw.exe
            echo [!datetime!] [OK] Python gefunden (Methode 5): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
    )
)

echo [!datetime!] [INFO] Methode 6: Suche auf allen Laufwerken... >> "%LOG_FILE%"
for %%D in (C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    if exist "%%D:\" (
        echo [!datetime!] [INFO] Pruefe Laufwerk: %%D:\ >> "%LOG_FILE%"
        if exist "%%D:\Program Files\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Program Files (x86)\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Program Files (x86)\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python3*\pythonw.exe" (
            for %%P in ("%%D:\Python3*\pythonw.exe") do (
                set PYTHON_EXE=%%~fP
                echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            )
            if defined PYTHON_EXE goto :found_python
        )
        if exist "%%D:\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Python\pythonw.exe
            echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
        if exist "%%D:\Program Files\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Program Files\Python\pythonw.exe
            echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
        if exist "%%D:\Program Files (x86)\Python\pythonw.exe" (
            set PYTHON_EXE=%%D:\Program Files (x86)\Python\pythonw.exe
            echo [!datetime!] [OK] Python gefunden (Methode 6): !PYTHON_EXE! >> "%LOG_FILE%"
            goto :found_python
        )
    )
)

echo [!datetime!] [WARNING] Python nicht gefunden nach allen Suchmethoden >> "%LOG_FILE%"
echo.
echo ========================================
echo FEHLER: Python nicht gefunden!
echo ========================================
echo.
echo Moechten Sie Python 3.11 automatisch herunterladen und installieren?
echo.
choice /C YN /M "Python installieren (J/N)"
if errorlevel 2 (
    echo [!datetime!] [INFO] Benutzer hat Python-Installation abgelehnt >> "%LOG_FILE%"
    goto :no_install
)
if errorlevel 1 (
    echo [!datetime!] [INFO] Benutzer hat Python-Installation bestaetigt >> "%LOG_FILE%"
    goto :install_python
)

:install_python
echo.
echo Lade Python-Installer herunter...
echo [!datetime!] [INFO] Starte Python-Download... >> "%LOG_FILE%"
set INSTALLER_PATH=%TEMP%\python-installer.exe
set INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%INSTALLER_URL%' -OutFile '%INSTALLER_PATH%'}"
set DOWNLOAD_RESULT=%errorlevel%
echo [!datetime!] [INFO] Download-Befehl beendet mit Exit-Code: !DOWNLOAD_RESULT! >> "%LOG_FILE%"

if not exist "%INSTALLER_PATH%" (
    echo [!datetime!] [ERROR] Python-Installer nicht heruntergeladen >> "%LOG_FILE%"
    echo.
    echo FEHLER: Konnte Python-Installer nicht herunterladen.
    echo Bitte installieren Sie Python manuell von: https://www.python.org/downloads/
    echo.
    echo Log-Datei: %LOG_FILE%
    pause
    exit /b 1
)
echo [!datetime!] [OK] Python-Installer heruntergeladen >> "%LOG_FILE%"

echo.
echo Installiere Python (dies erfordert Administrator-Rechte)...
echo [!datetime!] [INFO] Starte Python-Installation mit Administrator-Rechten... >> "%LOG_FILE%"

powershell -Command "Start-Process -FilePath '%INSTALLER_PATH%' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Verb RunAs -Wait"
set INSTALL_RESULT=%errorlevel%
echo [!datetime!] [INFO] Installations-Befehl beendet mit Exit-Code: !INSTALL_RESULT! >> "%LOG_FILE%"

timeout /t 3 >nul 2>&1

echo [!datetime!] [INFO] Pruefe ob Python jetzt verfuegbar ist... >> "%LOG_FILE%"
where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    echo [!datetime!] [OK] Python erfolgreich installiert: python.exe >> "%LOG_FILE%"
    echo.
    echo Python wurde erfolgreich installiert!
    echo.
    del "%INSTALLER_PATH%" >nul 2>&1
    goto :found_python
) else (
    where pythonw.exe >nul 2>&1
    if %errorlevel% == 0 (
        set PYTHON_EXE=pythonw.exe
        echo [!datetime!] [OK] Python erfolgreich installiert: pythonw.exe >> "%LOG_FILE%"
        echo.
        echo Python wurde erfolgreich installiert!
        echo.
        del "%INSTALLER_PATH%" >nul 2>&1
        goto :found_python
    ) else (
        echo [!datetime!] [ERROR] Python-Installation fehlgeschlagen >> "%LOG_FILE%"
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

echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Python gefunden: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
echo [!datetime!] [INFO] Arbeitsverzeichnis: %~dp0 >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"

if exist "requirements.txt" (
    echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
    echo [!datetime!] [INFO] Pruefe requirements.txt... >> "%LOG_FILE%"
    echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
    echo [!datetime!] [INFO] Pruefe pip-Verfuegbarkeit... >> "%LOG_FILE%"
    !FULL_PYTHON_PATH! -m pip --version >> "%LOG_FILE%" 2>&1
    set PIP_CHECK_RESULT=%errorlevel%
    echo [!datetime!] [INFO] pip --version Exit-Code: !PIP_CHECK_RESULT! >> "%LOG_FILE%"
    if !PIP_CHECK_RESULT! == 0 (
        echo [!datetime!] [OK] pip verfuegbar >> "%LOG_FILE%"
        echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
        echo [!datetime!] [INFO] Starte requirements.txt Installation... >> "%LOG_FILE%"
        echo [!datetime!] [INFO] Befehl: !FULL_PYTHON_PATH! -m pip install --upgrade -r "requirements.txt" >> "%LOG_FILE%"
        echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
        !FULL_PYTHON_PATH! -m pip install --upgrade -r "requirements.txt" >> "%LOG_FILE%" 2>&1
        set PIP_RESULT=%errorlevel%
        echo [!datetime!] [INFO] pip install Exit-Code: !PIP_RESULT! >> "%LOG_FILE%"
        if !PIP_RESULT! == 0 (
            echo [!datetime!] [OK] requirements.txt erfolgreich installiert/aktualisiert >> "%LOG_FILE%"
        ) else (
            echo [!datetime!] [WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: !PIP_RESULT!) >> "%LOG_FILE%"
        )
    ) else (
        echo [!datetime!] [WARNING] pip nicht verfuegbar - ueberspringe requirements.txt Installation >> "%LOG_FILE%"
    )
) else (
    echo [!datetime!] [WARNING] requirements.txt nicht gefunden >> "%LOG_FILE%"
)

cd /d "%~dp0"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Starte Anwendung... >> "%LOG_FILE%"
echo [!datetime!] [INFO] Start-Befehl: "!FULL_PYTHON_PATH!" "start.py" >> "%LOG_FILE%"
echo [!datetime!] [INFO] Arbeitsverzeichnis: %~dp0 >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
start "" /B /MIN "!FULL_PYTHON_PATH!" "start.py"
set START_RESULT=%errorlevel%
echo [!datetime!] [INFO] Start-Befehl ausgefuehrt, Exit-Code: !START_RESULT! >> "%LOG_FILE%"

timeout /t 2 >nul 2>&1
for %%F in ("!FULL_PYTHON_PATH!") do set "PYTHON_EXE_NAME=%%~nxF"
echo [!datetime!] [INFO] Pruefe ob Python-Prozess laeuft: !PYTHON_EXE_NAME! >> "%LOG_FILE%"
tasklist /FI "IMAGENAME eq !PYTHON_EXE_NAME!" /FO CSV /NH >> "%LOG_FILE%" 2>&1
tasklist /FI "IMAGENAME eq !PYTHON_EXE_NAME!" /FO CSV /NH 2>nul | find /i "!PYTHON_EXE_NAME!" >nul 2>&1
if %errorlevel% == 0 (
    echo [!datetime!] [OK] Python-Prozess laeuft (!PYTHON_EXE_NAME!) >> "%LOG_FILE%"
) else (
    echo [!datetime!] [WARNING] Python-Prozess scheint nicht zu laufen >> "%LOG_FILE%"
    tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH >> "%LOG_FILE%" 2>&1
    tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2>nul | find /i "python.exe" >nul 2>&1
    if %errorlevel% == 0 (
        echo [!datetime!] [OK] Python-Prozess gefunden (python.exe) >> "%LOG_FILE%"
    ) else (
        echo [!datetime!] [WARNING] Kein Python-Prozess gefunden >> "%LOG_FILE%"
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

echo [!datetime!] [OK] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [OK] Launcher beendet erfolgreich >> "%LOG_FILE%"
echo [!datetime!] [OK] ========================================== >> "%LOG_FILE%"

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
