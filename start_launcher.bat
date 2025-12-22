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

echo [!datetime!] [INFO] Warte auf Abschluss der Python-Installation... >> "%LOG_FILE%"
timeout /t 5 >nul 2>&1

echo [!datetime!] [INFO] Pruefe ob Python jetzt verfuegbar ist... >> "%LOG_FILE%"
set PYTHON_FOUND=0
set MAX_RETRIES=5
set RETRY_COUNT=0

:check_python_after_install
set /a RETRY_COUNT+=1
echo [!datetime!] [INFO] Versuch !RETRY_COUNT! von !MAX_RETRIES!: Pruefe Python... >> "%LOG_FILE%"

where python.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=python.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python erfolgreich installiert: python.exe >> "%LOG_FILE%"
    goto :python_install_success
)

where pythonw.exe >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON_EXE=pythonw.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python erfolgreich installiert: pythonw.exe >> "%LOG_FILE%"
    goto :python_install_success
)

if !RETRY_COUNT! LSS !MAX_RETRIES! (
    echo [!datetime!] [INFO] Python noch nicht im PATH - warte 2 Sekunden... >> "%LOG_FILE%"
    timeout /t 2 >nul 2>&1
    goto :check_python_after_install
)

echo [!datetime!] [WARNING] Python nicht im PATH gefunden - suche in typischen Pfaden... >> "%LOG_FILE%"
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python gefunden in: !PYTHON_EXE! >> "%LOG_FILE%"
    goto :python_install_success
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
    set PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python gefunden in: !PYTHON_EXE! >> "%LOG_FILE%"
    goto :python_install_success
)
if exist "%PROGRAMFILES%\Python311\python.exe" (
    set PYTHON_EXE=%PROGRAMFILES%\Python311\python.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python gefunden in: !PYTHON_EXE! >> "%LOG_FILE%"
    goto :python_install_success
)
if exist "%PROGRAMFILES%\Python311\pythonw.exe" (
    set PYTHON_EXE=%PROGRAMFILES%\Python311\pythonw.exe
    set PYTHON_FOUND=1
    echo [!datetime!] [OK] Python gefunden in: !PYTHON_EXE! >> "%LOG_FILE%"
    goto :python_install_success
)

if !PYTHON_FOUND! == 0 (
    echo [!datetime!] [ERROR] Python-Installation fehlgeschlagen - Python nicht gefunden >> "%LOG_FILE%"
    echo.
    echo FEHLER: Python-Installation fehlgeschlagen oder noch nicht abgeschlossen.
    echo.
    echo Bitte:
    echo 1. Starten Sie den PC neu
    echo 2. Oder installieren Sie Python manuell von: https://www.python.org/downloads/
    echo    WICHTIG: Aktivieren Sie "Add Python to PATH" waehrend der Installation!
    echo.
    echo Log-Datei: %LOG_FILE%
    del "%INSTALLER_PATH%" >nul 2>&1
    pause
    exit /b 1
)

:python_install_success
echo.
echo Python wurde erfolgreich installiert!
echo.
del "%INSTALLER_PATH%" >nul 2>&1
goto :found_python

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

REM Pruefe und erstelle venv (virtuelle Umgebung)
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Pruefe venv... >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
set VENV_PATH=%~dp0venv
set VENV_NEEDS_CREATION=0

if not exist "!VENV_PATH!" (
    echo [!datetime!] [INFO] venv nicht gefunden - wird erstellt... >> "%LOG_FILE%"
    set VENV_NEEDS_CREATION=1
) else (
    if not exist "!VENV_PATH!\Scripts\python.exe" (
        if not exist "!VENV_PATH!\bin\python" (
            echo [!datetime!] [WARNING] venv existiert, aber ist ungueltig - wird neu erstellt... >> "%LOG_FILE%"
            set VENV_NEEDS_CREATION=1
        )
    )
)

if !VENV_NEEDS_CREATION! == 1 (
    echo [!datetime!] [INFO] Erstelle virtuelle Umgebung (venv)... >> "%LOG_FILE%"
    !FULL_PYTHON_PATH! -m venv "!VENV_PATH!" >> "%LOG_FILE%" 2>&1
    set VENV_RESULT=%errorlevel%
    echo [!datetime!] [INFO] venv Exit-Code: !VENV_RESULT! >> "%LOG_FILE%"
    
    if !VENV_RESULT! == 0 (
        timeout /t 2 >nul 2>&1
        if exist "!VENV_PATH!\Scripts\python.exe" (
            set FULL_PYTHON_PATH=!VENV_PATH!\Scripts\python.exe
            echo [!datetime!] [OK] venv erfolgreich erstellt >> "%LOG_FILE%"
            echo [!datetime!] [INFO] Verwende venv Python: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
        ) else if exist "!VENV_PATH!\bin\python" (
            set FULL_PYTHON_PATH=!VENV_PATH!\bin\python
            echo [!datetime!] [OK] venv erfolgreich erstellt >> "%LOG_FILE%"
            echo [!datetime!] [INFO] Verwende venv Python: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
        ) else (
            echo [!datetime!] [WARNING] venv erstellt, aber Python nicht gefunden - verwende System-Python >> "%LOG_FILE%"
        )
    ) else (
        echo [!datetime!] [WARNING] venv-Erstellung fehlgeschlagen (Exit-Code: !VENV_RESULT!) >> "%LOG_FILE%"
        echo [!datetime!] [INFO] Verwende System-Python weiterhin (venv ist optional) >> "%LOG_FILE%"
    )
) else (
    echo [!datetime!] [OK] venv existiert bereits >> "%LOG_FILE%"
    if exist "!VENV_PATH!\Scripts\python.exe" (
        set FULL_PYTHON_PATH=!VENV_PATH!\Scripts\python.exe
        echo [!datetime!] [INFO] Verwende venv Python: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
    ) else if exist "!VENV_PATH!\bin\python" (
        set FULL_PYTHON_PATH=!VENV_PATH!\bin\python
        echo [!datetime!] [INFO] Verwende venv Python: !FULL_PYTHON_PATH! >> "%LOG_FILE%"
    )
)

REM Pruefe ob pip verfuegbar ist und installiere es falls noetig
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Pruefe pip... >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
!FULL_PYTHON_PATH! -m pip --version >> "%LOG_FILE%" 2>&1
set PIP_CHECK_RESULT=%errorlevel%
echo [!datetime!] [INFO] pip --version Exit-Code: !PIP_CHECK_RESULT! >> "%LOG_FILE%"

if !PIP_CHECK_RESULT! NEQ 0 (
    echo [!datetime!] [WARNING] pip nicht verfuegbar - versuche Installation... >> "%LOG_FILE%"
    !FULL_PYTHON_PATH! -m ensurepip --upgrade --default-pip >> "%LOG_FILE%" 2>&1
    set ENSUREPIP_RESULT=%errorlevel%
    echo [!datetime!] [INFO] ensurepip Exit-Code: !ENSUREPIP_RESULT! >> "%LOG_FILE%"
    
    if !ENSUREPIP_RESULT! == 0 (
        timeout /t 1 >nul 2>&1
        !FULL_PYTHON_PATH! -m pip --version >> "%LOG_FILE%" 2>&1
        if %errorlevel% == 0 (
            echo [!datetime!] [OK] pip erfolgreich installiert >> "%LOG_FILE%"
        ) else (
            echo [!datetime!] [WARNING] pip-Installation scheint fehlgeschlagen zu sein >> "%LOG_FILE%"
            echo [!datetime!] [INFO] Versuche pip ueber get-pip.py zu installieren... >> "%LOG_FILE%"
            set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py
            set GET_PIP_PATH=%~dp0get-pip.py
            powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP_PATH%'}" >> "%LOG_FILE%" 2>&1
            if exist "!GET_PIP_PATH!" (
                !FULL_PYTHON_PATH! "!GET_PIP_PATH!" >> "%LOG_FILE%" 2>&1
                if %errorlevel% == 0 (
                    echo [!datetime!] [OK] pip ueber get-pip.py erfolgreich installiert >> "%LOG_FILE%"
                ) else (
                    echo [!datetime!] [WARNING] pip-Installation ueber get-pip.py fehlgeschlagen >> "%LOG_FILE%"
                )
                del "!GET_PIP_PATH!" >nul 2>&1
            )
        )
    ) else (
        echo [!datetime!] [WARNING] pip-Installation fehlgeschlagen (Exit-Code: !ENSUREPIP_RESULT!) >> "%LOG_FILE%"
        echo [!datetime!] [INFO] Versuche pip ueber get-pip.py zu installieren... >> "%LOG_FILE%"
        set GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py
        set GET_PIP_PATH=%~dp0get-pip.py
        powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%GET_PIP_PATH%'}" >> "%LOG_FILE%" 2>&1
        if exist "!GET_PIP_PATH!" (
            !FULL_PYTHON_PATH! "!GET_PIP_PATH!" >> "%LOG_FILE%" 2>&1
            if %errorlevel% == 0 (
                echo [!datetime!] [OK] pip ueber get-pip.py erfolgreich installiert >> "%LOG_FILE%"
            ) else (
                echo [!datetime!] [ERROR] pip-Installation fehlgeschlagen - requirements.txt kann nicht installiert werden >> "%LOG_FILE%"
            )
            del "!GET_PIP_PATH!" >nul 2>&1
        )
    )
) else (
    echo [!datetime!] [OK] pip verfuegbar >> "%LOG_FILE%"
)

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
            
            REM Pruefe ob wichtige Pakete jetzt verfuegbar sind
            echo [!datetime!] [INFO] Pruefe wichtige Pakete... >> "%LOG_FILE%"
            set ALL_PACKAGES_OK=1
            
            !FULL_PYTHON_PATH! -c "import requests" >> "%LOG_FILE%" 2>&1
            if %errorlevel% == 0 (
                echo [!datetime!] [OK] Paket requests verfuegbar >> "%LOG_FILE%"
            ) else (
                echo [!datetime!] [WARNING] Paket requests nicht verfuegbar >> "%LOG_FILE%"
                set ALL_PACKAGES_OK=0
            )
            
            !FULL_PYTHON_PATH! -c "import yt_dlp" >> "%LOG_FILE%" 2>&1
            if %errorlevel% == 0 (
                echo [!datetime!] [OK] Paket yt_dlp verfuegbar >> "%LOG_FILE%"
            ) else (
                echo [!datetime!] [WARNING] Paket yt_dlp nicht verfuegbar >> "%LOG_FILE%"
                set ALL_PACKAGES_OK=0
            )
            
            !FULL_PYTHON_PATH! -c "import mutagen" >> "%LOG_FILE%" 2>&1
            if %errorlevel% == 0 (
                echo [!datetime!] [OK] Paket mutagen verfuegbar >> "%LOG_FILE%"
            ) else (
                echo [!datetime!] [WARNING] Paket mutagen nicht verfuegbar >> "%LOG_FILE%"
                set ALL_PACKAGES_OK=0
            )
            
            if !ALL_PACKAGES_OK! == 0 (
                echo [!datetime!] [WARNING] Einige Pakete fehlen noch - versuche erneute Installation... >> "%LOG_FILE%"
                !FULL_PYTHON_PATH! -m pip install --upgrade -r "requirements.txt" >> "%LOG_FILE%" 2>&1
                set PIP_RESULT=%errorlevel%
                echo [!datetime!] [INFO] Zweiter Installationsversuch Exit-Code: !PIP_RESULT! >> "%LOG_FILE%"
            )
        ) else (
            echo [!datetime!] [WARNING] requirements.txt Installation fehlgeschlagen (Exit-Code: !PIP_RESULT!) >> "%LOG_FILE%"
            echo [!datetime!] [INFO] Versuche erneut mit --user Flag... >> "%LOG_FILE%"
            !FULL_PYTHON_PATH! -m pip install --user --upgrade -r "requirements.txt" >> "%LOG_FILE%" 2>&1
            if %errorlevel% == 0 (
                echo [!datetime!] [OK] requirements.txt erfolgreich installiert (--user) >> "%LOG_FILE%"
            ) else (
                echo [!datetime!] [ERROR] requirements.txt Installation fehlgeschlagen auch mit --user Flag >> "%LOG_FILE%"
            )
        )
    ) else (
        echo [!datetime!] [WARNING] pip nicht verfuegbar - ueberspringe requirements.txt Installation >> "%LOG_FILE%"
    )
) else (
    echo [!datetime!] [WARNING] requirements.txt nicht gefunden >> "%LOG_FILE%"
)

REM Pruefe tkinter (GUI-Bibliothek)
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Pruefe tkinter... >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
!FULL_PYTHON_PATH! -c "import tkinter" >> "%LOG_FILE%" 2>&1
if %errorlevel% == 0 (
    echo [!datetime!] [OK] tkinter verfuegbar >> "%LOG_FILE%"
) else (
    echo [!datetime!] [WARNING] tkinter nicht verfuegbar >> "%LOG_FILE%"
    echo [!datetime!] [INFO] tkinter sollte normalerweise mit Python installiert sein >> "%LOG_FILE%"
    echo [!datetime!] [INFO] Falls die GUI nicht startet, installieren Sie tkinter manuell >> "%LOG_FILE%"
)

REM Pruefe ffmpeg (fuer Video/Audio-Verarbeitung)
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Pruefe ffmpeg... >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
ffmpeg -version >> "%LOG_FILE%" 2>&1
if %errorlevel% == 0 (
    echo [!datetime!] [OK] ffmpeg verfuegbar >> "%LOG_FILE%"
) else (
    echo [!datetime!] [WARNING] ffmpeg nicht im PATH gefunden >> "%LOG_FILE%"
    echo [!datetime!] [INFO] ffmpeg wird fuer Video/Audio-Verarbeitung benoetigt >> "%LOG_FILE%"
    echo [!datetime!] [INFO] Download von: https://ffmpeg.org/download.html >> "%LOG_FILE%"
    echo [!datetime!] [INFO] Oder installieren Sie ueber: winget install ffmpeg (falls winget verfuegbar) >> "%LOG_FILE%"
    
    REM Versuche winget Installation
    winget --version >> "%LOG_FILE%" 2>&1
    if %errorlevel% == 0 (
        echo [!datetime!] [INFO] winget verfuegbar - versuche ffmpeg Installation... >> "%LOG_FILE%"
        winget install -e --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements >> "%LOG_FILE%" 2>&1
        if %errorlevel% == 0 (
            echo [!datetime!] [OK] ffmpeg erfolgreich ueber winget installiert >> "%LOG_FILE%"
        ) else (
            echo [!datetime!] [WARNING] ffmpeg-Installation ueber winget fehlgeschlagen >> "%LOG_FILE%"
        )
    ) else (
        echo [!datetime!] [INFO] winget nicht verfuegbar - ueberspringe automatische ffmpeg-Installation >> "%LOG_FILE%"
    )
)

cd /d "%~dp0"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"
echo [!datetime!] [INFO] Starte Anwendung... >> "%LOG_FILE%"
echo [!datetime!] [INFO] Start-Befehl: "!FULL_PYTHON_PATH!" "start.py" >> "%LOG_FILE%"
echo [!datetime!] [INFO] Arbeitsverzeichnis: %~dp0 >> "%LOG_FILE%"
echo [!datetime!] [INFO] ========================================== >> "%LOG_FILE%"

REM Setze Umgebungsvariable, um zu signalisieren, dass wir über den Launcher gestartet wurden
REM Dies verhindert, dass das Abhängigkeits-Popup in der GUI erscheint
set "UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER=1"
echo [!datetime!] [INFO] Setze Umgebungsvariable: UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER=1 >> "%LOG_FILE%"

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
