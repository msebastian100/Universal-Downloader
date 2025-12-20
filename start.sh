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

echo "=========================================="
echo "Universal Downloader - Launcher"
echo "=========================================="
echo ""

# Prüfe Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 ist nicht installiert!${NC}"
    echo "Bitte installieren Sie Python 3.8 oder höher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} Python gefunden: $PYTHON_VERSION"
echo ""

# Prüfe auf Updates (optional, kann übersprungen werden)
if [ "$1" != "--no-update" ]; then
    echo "[INFO] Prüfe auf Updates..."
    
    # Prüfe ob update_from_github.py existiert
    if [ -f "update_from_github.py" ]; then
        python3 update_from_github.py 2>&1 | while IFS= read -r line; do
            echo "[UPDATE] $line"
        done
        
        UPDATE_RESULT=${PIPESTATUS[0]}
        if [ $UPDATE_RESULT -eq 0 ]; then
            echo -e "${GREEN}✓${NC} Update-Check abgeschlossen"
        else
            echo -e "${YELLOW}⚠${NC} Update-Check fehlgeschlagen oder keine Updates verfügbar"
        fi
    else
        echo -e "${YELLOW}⚠${NC} update_from_github.py nicht gefunden - überspringe Update-Check"
    fi
    echo ""
fi

# Prüfe ob start.py existiert
if [ ! -f "start.py" ]; then
    echo -e "${RED}❌ start.py nicht gefunden!${NC}"
    echo "Bitte stellen Sie sicher, dass Sie im richtigen Verzeichnis sind."
    exit 1
fi

# Starte Anwendung
echo "[INFO] Starte Universal Downloader..."
echo ""

python3 start.py

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Anwendung wurde mit Fehler beendet (Exit-Code: $EXIT_CODE)${NC}"
    echo ""
    echo "Drücken Sie eine Taste zum Beenden..."
    read -n 1 -s
fi

exit $EXIT_CODE
