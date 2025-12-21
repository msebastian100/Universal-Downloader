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
    exit 1
fi

log_debug "start.py gefunden, starte Anwendung..."

# Starte Anwendung
log_and_echo "[INFO] Starte Universal Downloader..."
log_and_echo ""
log_debug "Starte: python3 start.py"
log_debug "Python-Pfad: $(which python3)"
log_debug "Arbeitsverzeichnis: $(pwd)"

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
