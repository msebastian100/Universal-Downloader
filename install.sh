#!/bin/bash
# Installationsskript für Universal Downloader

# Debug-Logging aktivieren
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Erstelle Logs-Verzeichnis falls nicht vorhanden (mit Fehlerbehandlung)
LOG_DIR="$SCRIPT_DIR/logs"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
    # Fallback: Versuche im aktuellen Verzeichnis zu loggen
    LOG_DIR="$SCRIPT_DIR"
fi

# Log-Datei mit Timestamp
LOG_DATE=$(date +%Y-%m-%d_%H-%M-%S 2>/dev/null || date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/install_debug_${LOG_DATE}.log"

# Prüfe ob Log-Datei beschreibbar ist
CAN_LOG=true
if ! touch "$LOG_FILE" 2>/dev/null; then
    CAN_LOG=false
    LOG_FILE="/dev/null"
    echo "⚠ Warnung: Kann nicht in Log-Datei schreiben, verwende stdout"
fi

# Funktion zum gleichzeitigen Loggen und Ausgeben
log_and_echo() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)
    if [ "$CAN_LOG" = true ]; then
        echo "[$timestamp] $message" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$timestamp] $message"
    else
        echo "[$timestamp] $message"
    fi
}

# Funktion zum Loggen ohne Echo (nur für Debug)
log_debug() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)
    if [ "$CAN_LOG" = true ]; then
        echo "[$timestamp] [DEBUG] $message" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

# Funktion für Exit mit Pause (damit Terminal offen bleibt)
exit_with_pause() {
    local exit_code=${1:-1}
    log_and_echo ""
    log_and_echo "Drücken Sie eine beliebige Taste zum Beenden..."
    read -n 1 -s
    exit $exit_code
}

# Redirect stderr auch in Log-Datei (falls möglich)
if [ "$CAN_LOG" = true ]; then
    exec 2>> "$LOG_FILE" 2>/dev/null || true
fi

log_and_echo "=========================================="
log_and_echo "Universal Downloader - Installation"
log_and_echo "=========================================="
log_and_echo "Log-Datei: $LOG_FILE"
log_and_echo ""

# Erkenne Betriebssystem
OS="$(uname -s)"
ARCH="$(uname -m)"
log_debug "Betriebssystem erkannt: OS=$OS, ARCH=$ARCH"

# Sammle System-Informationen
log_and_echo "System-Informationen:"
log_and_echo "  Betriebssystem: $OS"
log_and_echo "  Architektur: $ARCH"
log_and_echo "  Kernel: $(uname -r 2>/dev/null || echo 'unbekannt')"
log_and_echo "  Hostname: $(hostname 2>/dev/null || echo 'unbekannt')"
log_and_echo "  Benutzer: $(whoami 2>/dev/null || echo 'unbekannt')"
log_and_echo "  Home-Verzeichnis: $HOME"
log_and_echo "  Arbeitsverzeichnis: $SCRIPT_DIR"

# Prüfe installierte Pakete (Linux)
if [ "$OS" = "Linux" ]; then
    log_and_echo ""
    log_and_echo "Installierte System-Pakete (relevant):"
    
    # Python
    if command -v python3 &> /dev/null; then
        PYTHON_VER=$(python3 --version 2>&1)
        PYTHON_PATH=$(which python3)
        log_and_echo "  ✓ Python: $PYTHON_VER ($PYTHON_PATH)"
        log_debug "Python gefunden: $PYTHON_VER"
    else
        log_and_echo "  ✗ Python: nicht installiert"
    fi
    
    # pip
    if command -v pip3 &> /dev/null || python3 -m pip --version &> /dev/null; then
        PIP_VER=$(python3 -m pip --version 2>&1 | head -1)
        log_and_echo "  ✓ pip: $PIP_VER"
    else
        log_and_echo "  ✗ pip: nicht installiert"
    fi
    
    # python3-venv - prüfe ob spezifisches Paket installiert ist
    PYTHON_MINOR_CHECK=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
    VENV_PACKAGE_CHECK="python3.${PYTHON_MINOR_CHECK}-venv"
    if dpkg -l 2>/dev/null | grep -q "^ii.*${VENV_PACKAGE_CHECK}"; then
        log_and_echo "  ✓ ${VENV_PACKAGE_CHECK}: installiert"
        log_debug "${VENV_PACKAGE_CHECK} Paket gefunden"
    elif python3 -m venv --help &> /dev/null 2>&1; then
        log_and_echo "  ⚠ python3-venv: verfügbar (aber ${VENV_PACKAGE_CHECK} fehlt möglicherweise)"
        log_debug "python3-venv generisch verfügbar, aber spezifisches Paket fehlt"
    else
        log_and_echo "  ✗ python3-venv: nicht verfügbar"
        log_debug "python3-venv nicht gefunden"
    fi
    
    # tkinter
    if python3 -c "import tkinter" 2>/dev/null; then
        log_and_echo "  ✓ python3-tk: installiert"
    else
        log_and_echo "  ✗ python3-tk: nicht installiert"
    fi
    
    # ffmpeg
    if command -v ffmpeg &> /dev/null; then
        FFMPEG_VER=$(ffmpeg -version 2>/dev/null | head -1)
        log_and_echo "  ✓ ffmpeg: $FFMPEG_VER"
    else
        log_and_echo "  ✗ ffmpeg: nicht installiert"
    fi
    
    # yt-dlp
    if command -v yt-dlp &> /dev/null; then
        YTDLP_VER=$(yt-dlp --version 2>/dev/null)
        log_and_echo "  ✓ yt-dlp: $YTDLP_VER (System)"
    elif python3 -c "import yt_dlp" 2>/dev/null; then
        YTDLP_VER=$(python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null)
        log_and_echo "  ✓ yt-dlp: $YTDLP_VER (Python)"
    else
        log_and_echo "  ✗ yt-dlp: nicht installiert"
    fi
    
    # sudo
    if command -v sudo &> /dev/null; then
        SUDO_VER=$(sudo -V 2>/dev/null | head -1 || echo "verfügbar")
        log_and_echo "  ✓ sudo: $SUDO_VER"
    else
        log_and_echo "  ✗ sudo: nicht installiert"
    fi
    
    # Paket-Manager
    if command -v apt-get &> /dev/null; then
        APT_VER=$(apt-get --version 2>/dev/null | head -1)
        log_and_echo "  ✓ apt-get: $APT_VER"
    elif command -v dnf &> /dev/null; then
        DNF_VER=$(dnf --version 2>/dev/null | head -1)
        log_and_echo "  ✓ dnf: $DNF_VER"
    elif command -v pacman &> /dev/null; then
        PACMAN_VER=$(pacman --version 2>/dev/null | head -1)
        log_and_echo "  ✓ pacman: $PACMAN_VER"
    fi
fi

log_and_echo ""

# Prüfe Root-Zugriff (sudo oder su)
SUDO_CMD=""
IS_ROOT=false

# Prüfe ob wir bereits root sind
if [ "$EUID" -eq 0 ]; then
    IS_ROOT=true
    SUDO_CMD=""
    log_debug "Bereits als root ausgeführt"
elif command -v sudo &> /dev/null; then
    SUDO_CMD="sudo"
    log_debug "sudo gefunden"
    # Teste ob sudo funktioniert
    if sudo -n true 2>/dev/null; then
        log_debug "sudo funktioniert ohne Passwort"
    else
        log_and_echo "⚠ sudo benötigt Passwort - Sie werden möglicherweise nach Ihrem Passwort gefragt"
    fi
elif command -v su &> /dev/null; then
    log_and_echo "⚠ sudo nicht verfügbar, aber su gefunden"
    log_and_echo "  Versuche sudo zu installieren..."
    # Versuche sudo zu installieren (benötigt root)
    if command -v apt-get &> /dev/null; then
        log_and_echo "  Bitte geben Sie das Root-Passwort ein, um sudo zu installieren:"
        if su -c "apt-get update && apt-get install -y sudo" 2>&1 | tee -a "$LOG_FILE"; then
            SUDO_CMD="sudo"
            log_and_echo "✓ sudo erfolgreich installiert"
        else
            log_and_echo "❌ sudo Installation fehlgeschlagen"
            log_and_echo "  Bitte installieren Sie sudo manuell oder führen Sie dieses Skript als root aus"
            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
            exit_with_pause 1
        fi
    else
        log_and_echo "❌ sudo nicht verfügbar und kann nicht automatisch installiert werden"
        log_and_echo "  Bitte installieren Sie sudo manuell oder führen Sie dieses Skript als root aus"
        log_and_echo "  Oder geben Sie das Root-Passwort ein, wenn Sie nach 'su' gefragt werden"
        # Frage nach Root-Passwort für su
        log_and_echo ""
        log_and_echo "Bitte geben Sie das Root-Passwort ein:"
        SUDO_CMD="su -c"
    fi
else
    log_and_echo "❌ Weder sudo noch su gefunden"
    log_and_echo "  Bitte installieren Sie sudo oder führen Sie dieses Skript als root aus"
    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
    exit_with_pause 1
fi

log_debug "SUDO_CMD: $SUDO_CMD, IS_ROOT: $IS_ROOT"

# Prüfe und installiere Python3
log_and_echo "Prüfe Python3..."
if ! command -v python3 &> /dev/null; then
    log_and_echo "⚠ Python 3 nicht gefunden - versuche Installation..."
    log_debug "python3 Befehl nicht gefunden, starte Installation"
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                log_and_echo "  Installiere Python3 über apt-get..."
                log_debug "Starte apt-get update..."
                if $SUDO_CMD apt-get update 2>&1 | tee -a "$LOG_FILE"; then
                    log_debug "apt-get update erfolgreich"
                    log_debug "Starte apt-get install python3 python3-pip python3-venv python3-tk..."
                    if $SUDO_CMD apt-get install -y python3 python3-pip python3-venv python3-tk 2>&1 | tee -a "$LOG_FILE"; then
                        log_and_echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                    else
                        log_and_echo "❌ Fehler bei der Installation von Python3"
                        log_and_echo "  Bitte installieren Sie Python3 manuell: $SUDO_CMD apt-get install python3 python3-pip python3-venv python3-tk"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit_with_pause 1
                    fi
                else
                    log_and_echo "❌ Fehler bei apt-get update"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                log_and_echo "  Installiere Python3 über dnf..."
                if $SUDO_CMD dnf install -y python3 python3-pip python3-tkinter 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                else
                    log_and_echo "❌ Fehler bei der Installation von Python3"
                    log_and_echo "  Bitte installieren Sie Python3 manuell: $SUDO_CMD dnf install python3 python3-pip python3-tkinter"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                log_and_echo "  Installiere Python3 über pacman..."
                if $SUDO_CMD pacman -S --noconfirm python python-pip tk 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                else
                    log_and_echo "❌ Fehler bei der Installation von Python3"
                    log_and_echo "  Bitte installieren Sie Python3 manuell: $SUDO_CMD pacman -S python python-pip tk"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            else
                log_and_echo "❌ Paket-Manager nicht erkannt"
                log_and_echo "  Bitte installieren Sie Python3 manuell über Ihren Paket-Manager"
                exit_with_pause 1
            fi
            ;;
        Darwin*)
            log_and_echo "❌ Python3 nicht gefunden auf macOS"
            log_and_echo "  Bitte installieren Sie Python3 über Homebrew: brew install python3"
            log_and_echo "  Oder laden Sie es von https://www.python.org/downloads/"
            exit_with_pause 1
            ;;
        *)
            log_and_echo "❌ Betriebssystem nicht unterstützt für automatische Python3-Installation"
            log_and_echo "  Bitte installieren Sie Python3 manuell: https://www.python.org/downloads/"
            exit_with_pause 1
            ;;
    esac
fi

PYTHON_VERSION=$(python3 --version 2>&1)
log_and_echo "✓ Python gefunden: $PYTHON_VERSION"
log_debug "Python-Version: $PYTHON_VERSION"

# Prüfe Python-Version (mindestens 3.8)
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    log_and_echo "❌ Python 3.8 oder höher ist erforderlich (gefunden: $PYTHON_VERSION)"
    log_and_echo "  Bitte aktualisieren Sie Python3"
    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
    exit_with_pause 1
fi

log_and_echo ""

# Prüfe und installiere pip
log_and_echo "Prüfe pip..."
log_debug "Prüfe pip Verfügbarkeit..."
if ! python3 -m pip --version &> /dev/null; then
    log_and_echo "⚠ pip nicht gefunden - versuche Installation..."
    log_debug "pip nicht gefunden, starte Installation"
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere pip über apt-get..."
                log_debug "Starte apt-get install python3-pip..."
                if $SUDO_CMD apt-get install -y python3-pip 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ pip erfolgreich installiert"
                else
                    log_and_echo "⚠ apt-get Installation fehlgeschlagen, versuche get-pip.py..."
                    log_debug "Lade get-pip.py herunter..."
                    if curl -f https://bootstrap.pypa.io/get-pip.py -o get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                        log_debug "Starte python3 get-pip.py..."
                        if python3 get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                            log_and_echo "✓ pip erfolgreich installiert"
                            rm -f get-pip.py
                        else
                            log_and_echo "❌ Fehler bei der Installation von pip"
                            log_and_echo "  Bitte installieren Sie pip manuell: $SUDO_CMD apt-get install python3-pip"
                            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                            exit_with_pause 1
                        fi
                    else
                        log_and_echo "❌ Fehler beim Herunterladen von get-pip.py"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit_with_pause 1
                    fi
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                log_and_echo "  Installiere pip über dnf..."
                if $SUDO_CMD dnf install -y python3-pip 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ pip erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von pip"
                    log_and_echo "  Bitte installieren Sie pip manuell: $SUDO_CMD dnf install python3-pip"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                log_and_echo "  Installiere pip über pacman..."
                if $SUDO_CMD pacman -S --noconfirm python-pip 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ pip erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von pip"
                    log_and_echo "  Bitte installieren Sie pip manuell: $SUDO_CMD pacman -S python-pip"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            else
                log_and_echo "⚠ Paket-Manager nicht erkannt, versuche get-pip.py..."
                if curl -f https://bootstrap.pypa.io/get-pip.py -o get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                    if python3 get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                        log_and_echo "✓ pip erfolgreich installiert"
                        rm -f get-pip.py
                    else
                        log_and_echo "❌ Fehler bei der Installation von pip"
                        log_and_echo "  Bitte installieren Sie pip manuell"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit_with_pause 1
                    fi
                else
                    log_and_echo "❌ Fehler beim Herunterladen von get-pip.py"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            fi
            ;;
        Darwin*)
            log_and_echo "⚠ pip nicht gefunden auf macOS"
            log_and_echo "  Versuche Installation über get-pip.py..."
            if curl -f https://bootstrap.pypa.io/get-pip.py -o get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                if python3 get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ pip erfolgreich installiert"
                    rm -f get-pip.py
                else
                    log_and_echo "❌ Fehler bei der Installation von pip"
                    log_and_echo "  Bitte installieren Sie pip manuell: brew install python3"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            else
                log_and_echo "❌ Fehler beim Herunterladen von get-pip.py"
                log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                exit_with_pause 1
            fi
            ;;
        *)
            log_and_echo "⚠ pip nicht gefunden, versuche get-pip.py..."
            if curl -f https://bootstrap.pypa.io/get-pip.py -o get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                if python3 get-pip.py 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ pip erfolgreich installiert"
                    rm -f get-pip.py
                else
                    log_and_echo "❌ Fehler bei der Installation von pip"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            else
                log_and_echo "❌ Fehler beim Herunterladen von get-pip.py"
                log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                exit_with_pause 1
            fi
            ;;
    esac
fi

PIP_VERSION=$(python3 -m pip --version 2>&1)
log_and_echo "✓ pip gefunden: $PIP_VERSION"
log_debug "pip-Version: $PIP_VERSION"
log_and_echo ""

# Prüfe und installiere python3-venv falls nötig (für venv-Erstellung)
if [ "$OS" = "Linux" ]; then
    log_and_echo "Prüfe python3-venv..."
    log_debug "Prüfe ob python3-venv installiert ist..."
    
    PYTHON_MAJOR_VERSION=$(python3 -c "import sys; print(sys.version_info.major)" 2>/dev/null)
    PYTHON_MINOR_VERSION=$(python3 -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
    log_debug "Python Version: $PYTHON_MAJOR_VERSION.$PYTHON_MINOR_VERSION"
    log_debug "Architektur: $ARCH"
    
    VENV_PACKAGE_INSTALLED=false
    
    if command -v apt-get &> /dev/null; then
        # Prüfe ob python3.X-venv Paket installiert ist (Ubuntu/Debian)
        VENV_PACKAGE_NAME="python3.${PYTHON_MINOR_VERSION}-venv"
        log_debug "Prüfe ob $VENV_PACKAGE_NAME installiert ist..."
        log_debug "Suche in dpkg -l nach: $VENV_PACKAGE_NAME"
        
        if dpkg -l 2>/dev/null | grep -q "^ii.*${VENV_PACKAGE_NAME}"; then
            VENV_PACKAGE_INSTALLED=true
            log_debug "$VENV_PACKAGE_NAME ist installiert"
        else
            log_debug "$VENV_PACKAGE_NAME ist NICHT installiert"
            # Prüfe auch mit apt-cache ob Paket verfügbar ist
            log_debug "Prüfe ob $VENV_PACKAGE_NAME in Repository verfügbar ist..."
            if apt-cache search "^${VENV_PACKAGE_NAME}" 2>/dev/null | grep -q "^${VENV_PACKAGE_NAME}"; then
                log_debug "$VENV_PACKAGE_NAME ist im Repository verfügbar"
            else
                log_debug "$VENV_PACKAGE_NAME ist NICHT im Repository verfügbar"
            fi
        fi
        
        # Prüfe auch python3-venv (generisches Paket)
        if [ "$VENV_PACKAGE_INSTALLED" = false ]; then
            if dpkg -l | grep -q "^ii.*python3-venv"; then
                log_debug "python3-venv (generisch) ist installiert"
                # Teste ob es funktioniert
                if python3 -m venv --help &> /dev/null 2>&1; then
                    # Teste ob venv tatsächlich erstellt werden kann
                    TEST_VENV_DIR="/tmp/test_venv_$$"
                    if python3 -m venv "$TEST_VENV_DIR" &> /dev/null 2>&1; then
                        VENV_PACKAGE_INSTALLED=true
                        rm -rf "$TEST_VENV_DIR"
                        log_debug "python3-venv funktioniert"
                    else
                        rm -rf "$TEST_VENV_DIR"
                        log_debug "python3-venv installiert, aber funktioniert nicht (benötigt $VENV_PACKAGE_NAME)"
                    fi
                fi
            fi
        fi
        
        if [ "$VENV_PACKAGE_INSTALLED" = false ]; then
            log_and_echo "⚠ $VENV_PACKAGE_NAME nicht installiert - versuche Installation..."
            log_debug "Starte Installation von $VENV_PACKAGE_NAME..."
            log_debug "Befehl: $SUDO_CMD apt-get install -y $VENV_PACKAGE_NAME"
            
            # System-Logs: Zeige verfügbare python3-venv Pakete
            log_and_echo ""
            log_and_echo "=== SYSTEM-LOGS: Verfügbare python3-venv Pakete ==="
            apt-cache search "^python3.*venv" 2>/dev/null | head -20 | tee -a "$LOG_FILE" || true
            log_and_echo "=================================================="
            log_and_echo ""
            
            if $SUDO_CMD apt-get update 2>&1 | tee -a "$LOG_FILE"; then
                APT_UPDATE_EXIT=${PIPESTATUS[0]}
                log_debug "apt-get update Exit-Code: $APT_UPDATE_EXIT"
                if [ $APT_UPDATE_EXIT -eq 0 ]; then
                    log_debug "apt-get update erfolgreich"
                    
                    # System-Logs: Zeige Paket-Informationen
                    log_and_echo ""
                    log_and_echo "=== SYSTEM-LOGS: Paket-Informationen ==="
                    apt-cache show "$VENV_PACKAGE_NAME" 2>/dev/null | head -30 | tee -a "$LOG_FILE" || log_and_echo "Paket $VENV_PACKAGE_NAME nicht gefunden in Repository"
                    log_and_echo "========================================"
                    log_and_echo ""
                    
                    INSTALL_OUTPUT=$($SUDO_CMD apt-get install -y "$VENV_PACKAGE_NAME" 2>&1)
                    INSTALL_EXIT=$?
                    echo "$INSTALL_OUTPUT" | tee -a "$LOG_FILE"
                    log_debug "apt-get install Exit-Code: $INSTALL_EXIT"
                    
                    if [ $INSTALL_EXIT -eq 0 ]; then
                        # Prüfe ob Paket wirklich installiert wurde
                        if dpkg -l 2>/dev/null | grep -q "^ii.*${VENV_PACKAGE_NAME}"; then
                            log_and_echo "✓ $VENV_PACKAGE_NAME erfolgreich installiert"
                            VENV_PACKAGE_INSTALLED=true
                        else
                            log_and_echo "⚠ Warnung: Installation meldete Erfolg, aber Paket ist nicht installiert"
                            log_debug "Paket-Status nach Installation:"
                            dpkg -l | grep -i "python.*venv" | tee -a "$LOG_FILE" || true
                        fi
                    else
                        log_and_echo "❌ $VENV_PACKAGE_NAME Installation fehlgeschlagen (Exit-Code: $INSTALL_EXIT)"
                        log_and_echo "  Fehler-Ausgabe:"
                        echo "$INSTALL_OUTPUT" | grep -i "error\|fehl\|kann nicht" | tee -a "$LOG_FILE" || echo "$INSTALL_OUTPUT" | tail -5 | tee -a "$LOG_FILE"
                        log_and_echo "  Versuche auch python3-venv zu installieren..."
                        if $SUDO_CMD apt-get install -y python3-venv 2>&1 | tee -a "$LOG_FILE"; then
                            INSTALL2_EXIT=${PIPESTATUS[0]}
                            if [ $INSTALL2_EXIT -eq 0 ]; then
                                log_and_echo "✓ python3-venv installiert (als Fallback)"
                            else
                                log_and_echo "⚠ Warnung: Beide venv-Pakete konnten nicht installiert werden"
                                log_and_echo "  Versuche venv trotzdem zu erstellen..."
                            fi
                        fi
                    fi
                else
                    log_and_echo "❌ apt-get update fehlgeschlagen (Exit-Code: $APT_UPDATE_EXIT)"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                fi
            else
                log_and_echo "❌ apt-get update fehlgeschlagen"
                log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
            fi
        else
            log_debug "python3-venv ist bereits installiert"
        fi
    elif command -v dnf &> /dev/null; then
        # Fedora/RHEL
        if rpm -q python3-venv &> /dev/null; then
            VENV_PACKAGE_INSTALLED=true
            log_debug "python3-venv ist installiert (rpm)"
        else
            log_and_echo "⚠ python3-venv nicht installiert - versuche Installation..."
            if $SUDO_CMD dnf install -y python3-venv 2>&1 | tee -a "$LOG_FILE"; then
                log_and_echo "✓ python3-venv erfolgreich installiert"
                VENV_PACKAGE_INSTALLED=true
            else
                log_and_echo "⚠ Warnung: python3-venv Installation fehlgeschlagen"
            fi
        fi
    fi
    
    log_and_echo ""
fi

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    log_and_echo "Erstelle virtuelle Umgebung..."
    log_debug "Erstelle venv in: $SCRIPT_DIR/venv"
    log_debug "Python-Version: $PYTHON_MAJOR_VERSION.$PYTHON_MINOR_VERSION"
    log_debug "Architektur: $ARCH"
    
    # Lösche eventuell vorhandenes fehlerhaftes venv-Verzeichnis
    if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
        log_debug "Lösche fehlerhaftes venv-Verzeichnis..."
        rm -rf venv
    fi
    
    VENV_OUTPUT=$(python3 -m venv venv 2>&1)
    VENV_EXIT=$?
    echo "$VENV_OUTPUT" | tee -a "$LOG_FILE"
    log_debug "venv Exit-Code: $VENV_EXIT"
    
    if [ $VENV_EXIT -eq 0 ] && [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        log_and_echo "✓ Virtuelle Umgebung erstellt"
        log_debug "venv erfolgreich erstellt: $(ls -la venv/bin/activate 2>/dev/null || echo 'nicht gefunden')"
    else
        log_and_echo "❌ Fehler beim Erstellen der virtuellen Umgebung"
        log_and_echo "  Fehler: $VENV_OUTPUT"
        log_debug "venv-Verzeichnis existiert: $([ -d "venv" ] && echo 'ja' || echo 'nein')"
        log_debug "venv/bin/activate existiert: $([ -f "venv/bin/activate" ] && echo 'ja' || echo 'nein')"
        
        if echo "$VENV_OUTPUT" | grep -q "ensurepip is not available"; then
            log_and_echo "  $VENV_PACKAGE_NAME fehlt - versuche Installation..."
            if [ "$OS" = "Linux" ] && command -v apt-get &> /dev/null; then
                log_debug "Starte apt-get update..."
                
                # System-Logs: Zeige verfügbare Pakete
                log_and_echo ""
                log_and_echo "=== SYSTEM-LOGS: Verfügbare python3-venv Pakete ==="
                apt-cache search "^python3.*venv" 2>/dev/null | head -20 | tee -a "$LOG_FILE" || true
                log_and_echo "=================================================="
                log_and_echo ""
                
                if $SUDO_CMD apt-get update 2>&1 | tee -a "$LOG_FILE"; then
                    APT_UPDATE_EXIT=${PIPESTATUS[0]}
                    log_debug "apt-get update Exit-Code: $APT_UPDATE_EXIT"
                    
                    if [ $APT_UPDATE_EXIT -eq 0 ]; then
                        log_debug "Installiere $VENV_PACKAGE_NAME..."
                        
                        # System-Logs: Zeige Paket-Informationen
                        log_and_echo ""
                        log_and_echo "=== SYSTEM-LOGS: Paket-Informationen für $VENV_PACKAGE_NAME ==="
                        apt-cache show "$VENV_PACKAGE_NAME" 2>/dev/null | head -30 | tee -a "$LOG_FILE" || log_and_echo "Paket $VENV_PACKAGE_NAME nicht gefunden"
                        log_and_echo "=============================================================="
                        log_and_echo ""
                        
                        INSTALL_OUTPUT=$($SUDO_CMD apt-get install -y "$VENV_PACKAGE_NAME" 2>&1)
                        INSTALL_EXIT=$?
                        echo "$INSTALL_OUTPUT" | tee -a "$LOG_FILE"
                        log_debug "apt-get install Exit-Code: $INSTALL_EXIT"
                        
                        if [ $INSTALL_EXIT -eq 0 ]; then
                            # Prüfe ob Paket wirklich installiert wurde
                            if dpkg -l 2>/dev/null | grep -q "^ii.*${VENV_PACKAGE_NAME}"; then
                                log_and_echo "  $VENV_PACKAGE_NAME installiert, versuche venv erneut zu erstellen..."
                                # Lösche fehlerhaftes venv-Verzeichnis
                                rm -rf venv
                                log_debug "Erstelle venv erneut..."
                                VENV_OUTPUT2=$(python3 -m venv venv 2>&1)
                                VENV_EXIT2=$?
                                echo "$VENV_OUTPUT2" | tee -a "$LOG_FILE"
                                log_debug "venv Exit-Code (2. Versuch): $VENV_EXIT2"
                                
                                if [ $VENV_EXIT2 -eq 0 ] && [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
                                    log_and_echo "✓ Virtuelle Umgebung erstellt"
                                else
                                    log_and_echo "❌ venv-Erstellung fehlgeschlagen (auch nach Installation)"
                                    log_and_echo "  Fehler: $VENV_OUTPUT2"
                                    
                                    # System-Logs: Zeige installierte python3-venv Pakete
                                    log_and_echo ""
                                    log_and_echo "=== SYSTEM-LOGS: Installierte python3-venv Pakete ==="
                                    dpkg -l | grep -i "python.*venv" | tee -a "$LOG_FILE" || log_and_echo "Keine python3-venv Pakete gefunden"
                                    log_and_echo "======================================================"
                                    log_and_echo ""
                                    
                                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                                    exit_with_pause 1
                                fi
                            else
                                log_and_echo "❌ Installation meldete Erfolg, aber Paket ist nicht installiert"
                                log_debug "Paket-Status:"
                                dpkg -l | grep -i "python.*venv" | tee -a "$LOG_FILE" || true
                                exit_with_pause 1
                            fi
                        else
                            log_and_echo "❌ $VENV_PACKAGE_NAME Installation fehlgeschlagen (Exit-Code: $INSTALL_EXIT)"
                            log_and_echo "  Fehler-Ausgabe:"
                            echo "$INSTALL_OUTPUT" | grep -i "error\|fehl\|kann nicht\|nicht gefunden" | tee -a "$LOG_FILE" || echo "$INSTALL_OUTPUT" | tail -10 | tee -a "$LOG_FILE"
                            
                            # System-Logs: Zeige alle verfügbaren python3 Pakete
                            log_and_echo ""
                            log_and_echo "=== SYSTEM-LOGS: Alle verfügbaren python3.*-venv Pakete ==="
                            apt-cache search "^python3\." | grep "venv" | tee -a "$LOG_FILE" || true
                            log_and_echo "=========================================================="
                            log_and_echo ""
                            
                            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                            log_and_echo "  Versuchen Sie manuell: $SUDO_CMD apt-get install $VENV_PACKAGE_NAME"
                            exit_with_pause 1
                        fi
                    else
                        log_and_echo "❌ apt-get update fehlgeschlagen (Exit-Code: $APT_UPDATE_EXIT)"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit_with_pause 1
                    fi
                else
                    log_and_echo "❌ apt-get update fehlgeschlagen"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit_with_pause 1
                fi
            else
                log_and_echo "  Bitte installieren Sie $VENV_PACKAGE_NAME manuell"
                log_and_echo "  Ubuntu/Debian ARM: $SUDO_CMD apt-get install $VENV_PACKAGE_NAME"
                log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                exit_with_pause 1
            fi
        else
            log_and_echo "  Unbekannter Fehler beim Erstellen der venv"
            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
            exit_with_pause 1
        fi
    fi
    log_and_echo ""
else
    log_debug "venv existiert bereits"
fi

# Aktiviere venv (nur wenn erfolgreich erstellt)
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    log_and_echo "Aktiviere virtuelle Umgebung..."
    log_debug "Aktiviere venv: source $SCRIPT_DIR/venv/bin/activate"
    source venv/bin/activate
    log_debug "venv aktiviert, Python: $(which python3)"
    
    # Installiere Abhängigkeiten
    log_and_echo "Installiere Python-Abhängigkeiten..."
    log_debug "Upgrade pip..."
    PIP_UPGRADE_OUTPUT=$(pip install --upgrade pip 2>&1)
    PIP_UPGRADE_EXIT=$?
    echo "$PIP_UPGRADE_OUTPUT" | tee -a "$LOG_FILE"
    log_debug "pip upgrade Exit-Code: $PIP_UPGRADE_EXIT"
    
    if [ $PIP_UPGRADE_EXIT -eq 0 ]; then
        log_debug "pip upgrade erfolgreich"
    else
        log_and_echo "⚠ Warnung: pip upgrade fehlgeschlagen, fahre fort..."
        log_debug "pip upgrade Fehler: $PIP_UPGRADE_OUTPUT"
    fi
    
    log_debug "Installiere requirements.txt..."
    if [ -f "requirements.txt" ]; then
        log_debug "requirements.txt gefunden, starte Installation..."
        log_and_echo "  Lade Pakete aus requirements.txt..."
        
        # Zeige Inhalt von requirements.txt
        log_and_echo ""
        log_and_echo "=== SYSTEM-LOGS: Inhalt von requirements.txt ==="
        cat requirements.txt | tee -a "$LOG_FILE"
        log_and_echo "================================================"
        log_and_echo ""
        
        PIP_INSTALL_OUTPUT=$(pip install -r requirements.txt 2>&1)
        PIP_INSTALL_EXIT=$?
        echo "$PIP_INSTALL_OUTPUT" | tee -a "$LOG_FILE"
        log_debug "pip install Exit-Code: $PIP_INSTALL_EXIT"
        
        if [ $PIP_INSTALL_EXIT -eq 0 ]; then
            log_and_echo "✓ Python-Abhängigkeiten installiert"
        else
            log_and_echo "❌ Fehler bei der Installation der Abhängigkeiten (Exit-Code: $PIP_INSTALL_EXIT)"
            log_and_echo "  Fehler-Ausgabe:"
            echo "$PIP_INSTALL_OUTPUT" | grep -i "error\|fehl\|failed" | head -20 | tee -a "$LOG_FILE" || echo "$PIP_INSTALL_OUTPUT" | tail -20 | tee -a "$LOG_FILE"
            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
            log_and_echo "  Versuchen Sie manuell: pip install -r requirements.txt"
        fi
    else
        log_and_echo "⚠ Warnung: requirements.txt nicht gefunden!"
        log_debug "requirements.txt nicht gefunden in: $SCRIPT_DIR"
    fi
else
    log_and_echo "⚠ Warnung: venv konnte nicht erstellt werden - überspringe Python-Abhängigkeiten Installation"
    log_and_echo "  Bitte erstellen Sie die venv manuell und installieren Sie dann die Abhängigkeiten"
fi

log_and_echo ""
log_and_echo "Prüfe System-Abhängigkeiten..."
log_and_echo ""

# Prüfe yt-dlp (als Python-Modul, da es über pip installiert wird)
log_and_echo "Prüfe yt-dlp..."
log_debug "Prüfe yt-dlp Verfügbarkeit..."
if python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null; then
    YTDLP_VERSION=$(python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null)
    log_and_echo "✓ yt-dlp installiert (Python-Modul): $YTDLP_VERSION"
    log_debug "yt-dlp Version: $YTDLP_VERSION"
elif command -v yt-dlp &> /dev/null; then
    YTDLP_VERSION=$(yt-dlp --version 2>/dev/null || echo "unbekannt")
    log_and_echo "✓ yt-dlp installiert (System-Befehl): $YTDLP_VERSION"
    log_debug "yt-dlp als System-Befehl gefunden"
else
    log_and_echo "⚠ yt-dlp nicht gefunden"
    log_and_echo "  Versuche Installation über pip..."
    log_debug "Installiere yt-dlp über pip..."
    if pip install --upgrade yt-dlp 2>&1 | tee -a "$LOG_FILE"; then
        if python3 -c "import yt_dlp" 2>/dev/null; then
            YTDLP_VERSION=$(python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null)
            log_and_echo "✓ yt-dlp erfolgreich installiert: $YTDLP_VERSION"
        else
            log_and_echo "❌ yt-dlp Installation fehlgeschlagen"
        fi
    else
        log_and_echo "❌ yt-dlp Installation fehlgeschlagen"
        log_debug "pip install yt-dlp fehlgeschlagen"
    fi
fi

# Prüfe und installiere ffmpeg falls nötig
log_debug "Prüfe ffmpeg Verfügbarkeit..."
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -1)
    log_and_echo "✓ ffmpeg bereits installiert: $FFMPEG_VERSION"
    log_debug "ffmpeg gefunden: $(which ffmpeg)"
else
    log_and_echo "⚠ ffmpeg nicht gefunden - versuche automatische Installation..."
    log_debug "ffmpeg nicht gefunden, starte Installation..."
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint/Ubuntu ARM)
            if command -v apt-get &> /dev/null; then
                log_and_echo "  Installiere ffmpeg über apt-get..."
                log_and_echo "  (Unterstützt: Ubuntu, Ubuntu ARM, Linux Mint, Debian)"
                log_debug "Starte apt-get install ffmpeg..."
                if $SUDO_CMD apt-get update 2>&1 | tee -a "$LOG_FILE" && $SUDO_CMD apt-get install -y ffmpeg 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ ffmpeg erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von ffmpeg"
                    log_and_echo "  Bitte installieren Sie ffmpeg manuell: $SUDO_CMD apt-get install ffmpeg"
                    log_and_echo "  Für Ubuntu ARM: $SUDO_CMD apt-get install ffmpeg (funktioniert gleich)"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                log_and_echo "  Installiere ffmpeg über dnf..."
                if $SUDO_CMD dnf install -y ffmpeg 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ ffmpeg erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von ffmpeg"
                    log_and_echo "  Bitte installieren Sie ffmpeg manuell: $SUDO_CMD dnf install ffmpeg"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                log_and_echo "  Installiere ffmpeg über pacman..."
                if $SUDO_CMD pacman -S --noconfirm ffmpeg 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ ffmpeg erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von ffmpeg"
                    log_and_echo "  Bitte installieren Sie ffmpeg manuell: $SUDO_CMD pacman -S ffmpeg"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                fi
            else
                log_and_echo "❌ Paket-Manager nicht erkannt"
                log_and_echo "  Bitte installieren Sie ffmpeg manuell über Ihren Paket-Manager"
            fi
            ;;
        Darwin*)
            # macOS - prüfe ob Homebrew installiert ist
            if command -v brew &> /dev/null; then
                log_and_echo "  Installiere ffmpeg über Homebrew..."
                if brew install ffmpeg 2>&1 | tee -a "$LOG_FILE"; then
                    log_and_echo "✓ ffmpeg erfolgreich installiert"
                else
                    log_and_echo "❌ Fehler bei der Installation von ffmpeg"
                    log_and_echo "  Bitte installieren Sie ffmpeg manuell: brew install ffmpeg"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                fi
            else
                log_and_echo "❌ Homebrew nicht gefunden"
                log_and_echo "  Installieren Sie Homebrew: https://brew.sh"
                log_and_echo "  Dann: brew install ffmpeg"
            fi
            ;;
        *)
            log_and_echo "❌ Betriebssystem nicht unterstützt für automatische Installation"
            log_and_echo "  Bitte installieren Sie ffmpeg manuell:"
            log_and_echo "    Linux: $SUDO_CMD apt-get install ffmpeg (oder entsprechendes Paket-Manager)"
            log_and_echo "    macOS: brew install ffmpeg"
            log_and_echo "    Windows: https://ffmpeg.org/download.html"
            ;;
    esac
fi

log_and_echo ""
log_and_echo "=========================================="
log_and_echo "Installations-Status"
log_and_echo "=========================================="
log_and_echo ""

# Prüfe alle Abhängigkeiten und zeige Status
ALL_OK=true

# Prüfe requirements.txt Pakete
log_and_echo "Python-Pakete aus requirements.txt:"
for package in requests mutagen Pillow deezer-python yt-dlp beautifulsoup4 selenium audible browser-cookie3; do
    if [ "$package" = "Pillow" ]; then
        import_name="PIL"
    elif [ "$package" = "beautifulsoup4" ]; then
        import_name="bs4"
    elif [ "$package" = "deezer-python" ]; then
        import_name="deezer"
    elif [ "$package" = "browser-cookie3" ]; then
        import_name="browser_cookie3"
    elif [ "$package" = "yt-dlp" ]; then
        import_name="yt_dlp"
    else
        import_name=$(echo "$package" | sed 's/-/_/g')
    fi
    
    if python3 -c "import $import_name" 2>/dev/null; then
        log_and_echo "  ✓ $package"
        log_debug "Paket $package ($import_name) ist installiert"
    else
        log_and_echo "  ✗ $package"
        log_debug "Paket $package ($import_name) FEHLT"
        ALL_OK=false
    fi
done

log_and_echo ""
log_and_echo "System-Abhängigkeiten:"

# Prüfe tkinter (GUI-Bibliothek)
log_debug "Prüfe tkinter..."
if python3 -c "import tkinter" 2>/dev/null; then
    log_and_echo "  ✓ tkinter (GUI-Bibliothek)"
    log_debug "tkinter ist verfügbar"
else
    log_and_echo "  ✗ tkinter (GUI-Bibliothek) - FEHLT!"
    log_and_echo "    Versuche automatische Installation..."
    
    if [ "$OS" = "Linux" ]; then
        if command -v apt-get &> /dev/null; then
            log_debug "Installiere python3-tk über apt-get..."
            INSTALL_TK_OUTPUT=$($SUDO_CMD apt-get install -y python3-tk 2>&1)
            INSTALL_TK_EXIT=$?
            echo "$INSTALL_TK_OUTPUT" | tee -a "$LOG_FILE"
            log_debug "apt-get install python3-tk Exit-Code: $INSTALL_TK_EXIT"
            
            if [ $INSTALL_TK_EXIT -eq 0 ]; then
                if python3 -c "import tkinter" 2>/dev/null; then
                    log_and_echo "  ✓ tkinter erfolgreich installiert"
                else
                    log_and_echo "  ⚠ Installation meldete Erfolg, aber tkinter kann nicht importiert werden"
                    ALL_OK=false
                fi
            else
                log_and_echo "  ❌ Installation fehlgeschlagen"
                log_and_echo "    Installieren Sie es manuell: $SUDO_CMD apt-get install python3-tk"
                ALL_OK=false
            fi
        elif command -v dnf &> /dev/null; then
            log_debug "Installiere python3-tkinter über dnf..."
            if $SUDO_CMD dnf install -y python3-tkinter 2>&1 | tee -a "$LOG_FILE"; then
                if python3 -c "import tkinter" 2>/dev/null; then
                    log_and_echo "  ✓ tkinter erfolgreich installiert"
                else
                    log_and_echo "  ⚠ Installation meldete Erfolg, aber tkinter kann nicht importiert werden"
                    ALL_OK=false
                fi
            else
                log_and_echo "  ❌ Installation fehlgeschlagen"
                log_and_echo "    Installieren Sie es manuell: $SUDO_CMD dnf install python3-tkinter"
                ALL_OK=false
            fi
        elif command -v pacman &> /dev/null; then
            log_debug "Installiere tk über pacman..."
            if $SUDO_CMD pacman -S --noconfirm tk 2>&1 | tee -a "$LOG_FILE"; then
                if python3 -c "import tkinter" 2>/dev/null; then
                    log_and_echo "  ✓ tkinter erfolgreich installiert"
                else
                    log_and_echo "  ⚠ Installation meldete Erfolg, aber tkinter kann nicht importiert werden"
                    ALL_OK=false
                fi
            else
                log_and_echo "  ❌ Installation fehlgeschlagen"
                log_and_echo "    Installieren Sie es manuell: $SUDO_CMD pacman -S tk"
                ALL_OK=false
            fi
        else
            log_and_echo "    Installieren Sie es manuell:"
            log_and_echo "      Ubuntu/Debian/Mint: sudo apt-get install python3-tk"
            log_and_echo "      Fedora/RHEL: sudo dnf install python3-tkinter"
            log_and_echo "      Arch Linux: sudo pacman -S tk"
            ALL_OK=false
        fi
    else
        log_and_echo "    Installieren Sie es manuell:"
        log_and_echo "      Ubuntu/Debian/Mint: sudo apt-get install python3-tk"
        log_and_echo "      Fedora/RHEL: sudo dnf install python3-tkinter"
        log_and_echo "      Arch Linux: sudo pacman -S tk"
        ALL_OK=false
    fi
    log_debug "tkinter FEHLT - Python kann es nicht importieren"
fi

# Prüfe ffmpeg
log_debug "Prüfe ffmpeg..."
if command -v ffmpeg &> /dev/null; then
    log_and_echo "  ✓ ffmpeg"
    log_debug "ffmpeg gefunden: $(which ffmpeg)"
else
    log_and_echo "  ✗ ffmpeg"
    log_debug "ffmpeg FEHLT - Befehl nicht gefunden"
    ALL_OK=false
fi

# Prüfe yt-dlp (als Python-Modul oder System-Befehl)
log_debug "Prüfe yt-dlp..."
if python3 -c "import yt_dlp" 2>/dev/null || command -v yt-dlp &> /dev/null; then
    log_and_echo "  ✓ yt-dlp"
    log_debug "yt-dlp gefunden"
else
    log_and_echo "  ✗ yt-dlp"
    log_debug "yt-dlp FEHLT"
    ALL_OK=false
fi

log_and_echo ""
log_and_echo "=========================================="
if [ "$ALL_OK" = true ]; then
    log_and_echo "✓ Alle Abhängigkeiten sind installiert!"
    log_and_echo "=========================================="
    log_and_echo ""
    log_and_echo "System-Informationen:"
    log_and_echo "  Betriebssystem: $OS"
    log_and_echo "  Architektur: $ARCH"
    log_and_echo "  Python: $PYTHON_VERSION"
    log_and_echo "  pip: $PIP_VERSION"
    log_and_echo ""
    log_and_echo "Starten Sie die Anwendung mit:"
    log_and_echo "  source venv/bin/activate"
    log_and_echo "  python3 start.py"
    log_and_echo ""
    log_and_echo "Log-Datei: $LOG_FILE"
else
    log_and_echo "⚠ Einige Abhängigkeiten fehlen!"
    log_and_echo "=========================================="
    log_and_echo ""
    log_and_echo "System-Informationen:"
    log_and_echo "  Betriebssystem: $OS"
    log_and_echo "  Architektur: $ARCH"
    log_and_echo "  Python: $PYTHON_VERSION"
    log_and_echo "  pip: $PIP_VERSION"
    log_and_echo ""
    log_and_echo "Bitte installieren Sie fehlende Pakete:"
    log_and_echo "  source venv/bin/activate"
    log_and_echo "  pip install -r requirements.txt"
    log_and_echo ""
    log_and_echo "Oder prüfen Sie die Abhängigkeiten mit:"
    log_and_echo "  python3 check_dependencies.py"
    log_and_echo ""
    log_and_echo "Detaillierte Fehlerinformationen finden Sie in der Log-Datei:"
    log_and_echo "  $LOG_FILE"
fi
log_and_echo ""

# Pause am Ende, damit Terminal offen bleibt
log_and_echo "Drücken Sie eine beliebige Taste zum Beenden..."
read -n 1 -s
