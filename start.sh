#!/bin/bash
# Start-Skript für Universal Downloader (Linux/macOS)
# Prüft auf Updates und startet die Anwendung

# Farben für Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Hole das Verzeichnis des Skripts
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
LOG_FILE="$LOG_DIR/start_debug_${LOG_DATE}.log"

# Prüfe ob Log-Datei beschreibbar ist
CAN_LOG=true
if ! touch "$LOG_FILE" 2>/dev/null; then
    CAN_LOG=false
    LOG_FILE="/dev/null"
    echo "⚠ Warnung: Kann nicht in Log-Datei schreiben, verwende stdout"
fi

# Funktion zum gleichzeitigen Loggen und Ausgeben
log_and_echo() {
    local use_echo_e=false
    if [ "$1" = "-e" ]; then
        use_echo_e=true
        shift
    fi
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)
    # Entferne Farbcodes für Log-Datei
    local message_no_color=$(echo -e "$message" | sed 's/\x1b\[[0-9;]*m//g')
    if [ "$CAN_LOG" = true ]; then
        echo "[$timestamp] $message_no_color" >> "$LOG_FILE" 2>/dev/null || true
    fi
    if [ "$use_echo_e" = true ]; then
        echo -e "[$timestamp] $message"
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

# Redirect stderr auch in Log-Datei (falls möglich)
if [ "$CAN_LOG" = true ]; then
    exec 2>> "$LOG_FILE" 2>/dev/null || true
fi

log_and_echo "=========================================="
log_and_echo "Universal Downloader - Launcher"
log_and_echo "=========================================="
log_and_echo "Log-Datei: $LOG_FILE"
log_and_echo "Verzeichnis: $SCRIPT_DIR"
log_debug "Skript gestartet: $0"
log_debug "Argumente: $@"

# Erkenne Betriebssystem
OS="$(uname -s)"
log_debug "Betriebssystem: $OS"
log_and_echo ""

# Prüfe Python
log_and_echo "Prüfe Python..."
log_debug "Suche nach python3 Befehl..."
if ! command -v python3 &> /dev/null; then
    log_and_echo -e "${RED}❌ Python 3 ist nicht installiert!${NC}"
    log_and_echo "Bitte installieren Sie Python 3.8 oder höher."
    log_and_echo "Siehe Log-Datei für Details: $LOG_FILE"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1)
PYTHON_PATH=$(which python3)
log_and_echo -e "${GREEN}✓${NC} Python gefunden: $PYTHON_VERSION"
log_debug "Python-Pfad: $PYTHON_PATH"
log_debug "Python-Version: $PYTHON_VERSION"
log_and_echo ""

# Prüfe auf Updates (optional, kann übersprungen werden)
if [ "$1" != "--no-update" ]; then
    log_and_echo "[INFO] Prüfe auf Updates..."
    log_debug "Update-Check aktiviert (kein --no-update Flag)"
    
    # Prüfe ob update_from_github.py existiert
    if [ -f "update_from_github.py" ]; then
        log_debug "update_from_github.py gefunden, starte Update-Check..."
        UPDATE_OUTPUT_FILE="$LOG_DIR/update_output_${LOG_DATE}.log"
        if [ "$CAN_LOG" = true ]; then
            python3 update_from_github.py 2>&1 | tee "$UPDATE_OUTPUT_FILE" | while IFS= read -r line; do
                log_and_echo "[UPDATE] $line"
            done
        else
            python3 update_from_github.py 2>&1 | while IFS= read -r line; do
                log_and_echo "[UPDATE] $line"
            done
        fi
        
        UPDATE_RESULT=${PIPESTATUS[0]}
        log_debug "Update-Check Exit-Code: $UPDATE_RESULT"
        
        if [ $UPDATE_RESULT -eq 0 ]; then
            log_and_echo -e "${GREEN}✓${NC} Update-Check abgeschlossen"
        else
            log_and_echo -e "${YELLOW}⚠${NC} Update-Check fehlgeschlagen oder keine Updates verfügbar"
            log_debug "Update-Check Details in: $UPDATE_OUTPUT_FILE"
        fi
    else
        log_and_echo -e "${YELLOW}⚠${NC} update_from_github.py nicht gefunden - überspringe Update-Check"
        log_debug "update_from_github.py nicht gefunden in: $SCRIPT_DIR"
    fi
    log_and_echo ""
else
    log_debug "Update-Check übersprungen (--no-update Flag gesetzt)"
fi

# Prüfe ob start.py existiert
log_debug "Prüfe ob start.py existiert..."
if [ ! -f "start.py" ]; then
    log_and_echo -e "${RED}❌ start.py nicht gefunden!${NC}"
    log_and_echo "Bitte stellen Sie sicher, dass Sie im richtigen Verzeichnis sind."
    log_and_echo "Aktuelles Verzeichnis: $SCRIPT_DIR"
    log_and_echo "Siehe Log-Datei für Details: $LOG_FILE"
    log_and_echo ""
    log_and_echo "Drücken Sie eine beliebige Taste zum Beenden..."
    read -n 1 -s
    exit 1
fi

log_debug "start.py gefunden"

# Prüfe ob Installation durchgeführt wurde
log_and_echo "[INFO] Prüfe Installation..."
log_debug "Prüfe ob venv existiert und Abhängigkeiten installiert sind..."

NEEDS_INSTALL=false
MISSING_PACKAGES=()

# Prüfe venv
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    log_and_echo "⚠ Virtuelle Umgebung fehlt oder ist unvollständig"
    log_debug "venv fehlt oder ist unvollständig"
    NEEDS_INSTALL=true
else
    log_debug "venv existiert"
    
    # Aktiviere venv für Prüfung
    source venv/bin/activate 2>/dev/null
    log_debug "venv aktiviert für Prüfung: $(which python3)"
    
    # Prüfe wichtige Pakete aus requirements.txt
    log_debug "Prüfe Python-Pakete..."
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
        
        if ! python3 -c "import $import_name" 2>/dev/null; then
            MISSING_PACKAGES+=("$package")
            log_debug "Paket $package ($import_name) FEHLT"
        else
            log_debug "Paket $package ($import_name) ist installiert"
        fi
    done
    
    # Prüfe tkinter
    if ! python3 -c "import tkinter" 2>/dev/null; then
        MISSING_PACKAGES+=("python3-tk")
        log_debug "tkinter FEHLT"
    fi
    
    deactivate 2>/dev/null || true
fi

# Prüfe System-Abhängigkeiten
if ! command -v ffmpeg &> /dev/null; then
    MISSING_PACKAGES+=("ffmpeg")
    log_debug "ffmpeg FEHLT"
fi

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    NEEDS_INSTALL=true
    log_and_echo "⚠ Fehlende Abhängigkeiten erkannt: ${MISSING_PACKAGES[*]}"
    log_debug "Fehlende Pakete: ${MISSING_PACKAGES[*]}"
fi

# Führe Installation durch falls nötig
if [ "$NEEDS_INSTALL" = true ]; then
    log_and_echo ""
    log_and_echo "=========================================="
    log_and_echo "Automatische Installation wird gestartet"
    log_and_echo "=========================================="
    log_and_echo ""
    log_and_echo "Fehlende Abhängigkeiten:"
    for pkg in "${MISSING_PACKAGES[@]}"; do
        log_and_echo "  - $pkg"
    done
    log_and_echo ""
    log_and_echo "Starte install.sh..."
    log_and_echo ""
    
    # Rufe install.sh auf
    if [ -f "install.sh" ]; then
        log_debug "Rufe install.sh auf..."
        chmod +x install.sh 2>/dev/null || true
        
        # Führe install.sh aus und fange Ausgabe
        INSTALL_OUTPUT=$(bash install.sh 2>&1)
        INSTALL_EXIT=$?
        echo "$INSTALL_OUTPUT" | tee -a "$LOG_FILE"
        log_debug "install.sh Exit-Code: $INSTALL_EXIT"
        
        if [ $INSTALL_EXIT -eq 0 ]; then
            log_and_echo ""
            log_and_echo -e "${GREEN}✓${NC} Installation erfolgreich abgeschlossen"
            log_and_echo ""
        else
            log_and_echo ""
            log_and_echo -e "${YELLOW}⚠${NC} Installation mit Warnungen beendet (Exit-Code: $INSTALL_EXIT)"
            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
            log_and_echo ""
        fi
    else
        log_and_echo -e "${RED}❌ install.sh nicht gefunden!${NC}"
        log_and_echo "  Bitte führen Sie die Installation manuell durch:"
        log_and_echo "    bash install.sh"
        log_and_echo ""
        log_and_echo "  Oder installieren Sie fehlende Pakete manuell:"
        for pkg in "${MISSING_PACKAGES[@]}"; do
            log_and_echo "    - $pkg"
        done
        log_and_echo ""
        log_and_echo "Drücken Sie eine beliebige Taste zum Beenden..."
        read -n 1 -s
        exit 1
    fi
    
    # Prüfe erneut nach Installation
    log_and_echo "[INFO] Prüfe Installation erneut..."
    MISSING_AFTER_INSTALL=()
    
    if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
        source venv/bin/activate 2>/dev/null
        
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
            
            if ! python3 -c "import $import_name" 2>/dev/null; then
                MISSING_AFTER_INSTALL+=("$package")
                log_and_echo -e "${YELLOW}⚠${NC} Paket $package fehlt immer noch"
                log_debug "Paket $package fehlt nach Installation"
            fi
        done
        
        if ! python3 -c "import tkinter" 2>/dev/null; then
            MISSING_AFTER_INSTALL+=("python3-tk")
            log_and_echo -e "${YELLOW}⚠${NC} tkinter fehlt immer noch"
        fi
        
        deactivate 2>/dev/null || true
    else
        log_and_echo -e "${YELLOW}⚠${NC} venv konnte nicht erstellt werden"
        MISSING_AFTER_INSTALL+=("venv")
    fi
    
    if ! command -v ffmpeg &> /dev/null; then
        MISSING_AFTER_INSTALL+=("ffmpeg")
        log_and_echo -e "${YELLOW}⚠${NC} ffmpeg fehlt immer noch"
    fi
    
    if [ ${#MISSING_AFTER_INSTALL[@]} -gt 0 ]; then
        log_and_echo ""
        log_and_echo -e "${YELLOW}⚠${NC} Einige Abhängigkeiten fehlen noch:"
        for pkg in "${MISSING_AFTER_INSTALL[@]}"; do
            log_and_echo "  - $pkg"
        done
        log_and_echo ""
        log_and_echo "=== FEHLENDE ABHÄNGIGKEITEN IN LOG ===" >> "$LOG_FILE"
        echo "Fehlende Pakete nach Installation:" >> "$LOG_FILE"
        for pkg in "${MISSING_AFTER_INSTALL[@]}"; do
            echo "  - $pkg" >> "$LOG_FILE"
        done
        echo "=============================================" >> "$LOG_FILE"
        log_and_echo "  Details wurden in Log-Datei geschrieben: $LOG_FILE"
        log_and_echo ""
    else
        log_and_echo -e "${GREEN}✓${NC} Alle Abhängigkeiten sind installiert"
        log_and_echo ""
    fi
else
    log_and_echo -e "${GREEN}✓${NC} Alle Voraussetzungen erfüllt"
    log_and_echo ""
fi

# Erstelle Startmenü-Verknüpfung beim ersten Start (nur wenn nicht bereits vorhanden)
log_and_echo "[INFO] Prüfe Startmenü-Verknüpfung..."
log_debug "Prüfe ob create_shortcut.py existiert..."
SHORTCUT_CREATED=false
if [ -f "create_shortcut.py" ]; then
    log_debug "Rufe create_shortcut.py auf..."
    SHORTCUT_OUTPUT=$(python3 create_shortcut.py 2>&1)
    SHORTCUT_EXIT=$?
    echo "$SHORTCUT_OUTPUT" | tee -a "$LOG_FILE"
    
    if [ $SHORTCUT_EXIT -eq 0 ]; then
        log_and_echo -e "${GREEN}✓${NC} Startmenü-Verknüpfung erstellt oder bereits vorhanden"
        # Prüfe ob Verknüpfung erstellt wurde (nicht nur "existiert bereits")
        if echo "$SHORTCUT_OUTPUT" | grep -q "erstellt"; then
            SHORTCUT_CREATED=true
        fi
    else
        log_and_echo -e "${YELLOW}⚠${NC} Konnte Startmenü-Verknüpfung nicht erstellen"
        log_debug "create_shortcut.py Exit-Code: $SHORTCUT_EXIT"
    fi
else
    log_debug "create_shortcut.py nicht gefunden"
fi

# Aktualisiere Desktop-Datenbank auf Linux (falls Verknüpfung erstellt wurde)
if [ "$OS" = "Linux" ] && [ "$SHORTCUT_CREATED" = true ]; then
    log_and_echo "[INFO] Aktualisiere Desktop-Datenbank..."
    log_debug "Rufe update-desktop-database auf..."
    DESKTOP_DIR="$HOME/.local/share/applications"
    if [ -d "$DESKTOP_DIR" ]; then
        if command -v update-desktop-database &> /dev/null; then
            if update-desktop-database "$DESKTOP_DIR" 2>&1 | tee -a "$LOG_FILE"; then
                log_and_echo -e "${GREEN}✓${NC} Desktop-Datenbank aktualisiert"
            else
                log_and_echo -e "${YELLOW}⚠${NC} Konnte Desktop-Datenbank nicht aktualisieren"
            fi
        else
            log_debug "update-desktop-database nicht gefunden - überspringe"
        fi
    fi
fi
log_and_echo ""

log_debug "starte Anwendung..."

# Starte Anwendung
log_and_echo "[INFO] Starte Universal Downloader..."
log_and_echo ""
log_debug "Starte: python3 start.py"
log_debug "Python-Pfad: $(which python3)"
log_debug "Arbeitsverzeichnis: $(pwd)"

# Aktiviere venv falls vorhanden
if [ -d "venv" ] && [ -f "venv/bin/activate" ]; then
    log_debug "Aktiviere venv vor Start..."
    source venv/bin/activate
    log_debug "venv aktiviert: $(which python3)"
fi

# Führe start.py aus und logge alle Ausgaben
if [ "$CAN_LOG" = true ]; then
    python3 start.py 2>&1 | tee -a "$LOG_FILE"
else
    python3 start.py 2>&1
fi

EXIT_CODE=${PIPESTATUS[0]}
log_debug "Anwendung beendet mit Exit-Code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
    log_and_echo ""
    log_and_echo -e "${RED}❌ Anwendung wurde mit Fehler beendet (Exit-Code: $EXIT_CODE)${NC}"
    log_and_echo ""
    
    # Prüfe ob Fehler mit fehlenden Modulen zusammenhängt
    if grep -q "No module named" "$LOG_FILE" 2>/dev/null; then
        log_and_echo "=== FEHLENDE MODULE ERKANNT ==="
        MISSING_MODULES=$(grep "No module named" "$LOG_FILE" | sed 's/.*No module named //' | sort -u)
        log_and_echo "Fehlende Module:"
        echo "$MISSING_MODULES" | while read -r module; do
            log_and_echo "  - $module"
        done
        log_and_echo ""
        log_and_echo "=== FEHLENDE MODULE IN LOG ===" >> "$LOG_FILE"
        echo "$MISSING_MODULES" | while read -r module; do
            echo "  - $module" >> "$LOG_FILE"
        done
        echo "====================================" >> "$LOG_FILE"
        log_and_echo "Versuchen Sie die Installation erneut:"
        log_and_echo "  bash install.sh"
        log_and_echo "  Oder installieren Sie manuell:"
        log_and_echo "  source venv/bin/activate"
        log_and_echo "  pip install -r requirements.txt"
        log_and_echo ""
    fi
    
    log_and_echo "Detaillierte Fehlerinformationen finden Sie in der Log-Datei:"
    log_and_echo "  $LOG_FILE"
else
    log_debug "Anwendung erfolgreich beendet"
fi

log_and_echo ""
if [ "$CAN_LOG" = true ]; then
    log_and_echo "Log-Datei: $LOG_FILE"
fi
log_and_echo ""
log_and_echo "Drücken Sie eine beliebige Taste zum Beenden..."
read -n 1 -s

exit $EXIT_CODE
