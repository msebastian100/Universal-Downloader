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

log_and_echo "Betriebssystem: $OS"
log_and_echo "Architektur: $ARCH"
log_and_echo ""

# Prüfe und installiere Python3
log_and_echo "Prüfe Python3..."
if ! command -v python3 &> /dev/null; then
    log_and_echo "⚠ Python 3 nicht gefunden - versuche Installation..."
    log_debug "python3 Befehl nicht gefunden, starte Installation"
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere Python3 über apt-get..."
                log_debug "Starte apt-get update..."
                if sudo apt-get update 2>&1 | tee -a "$LOG_FILE"; then
                    log_debug "apt-get update erfolgreich"
                    log_debug "Starte apt-get install python3 python3-pip python3-venv python3-tk..."
                    if sudo apt-get install -y python3 python3-pip python3-venv python3-tk 2>&1 | tee -a "$LOG_FILE"; then
                        log_and_echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                    else
                        log_and_echo "❌ Fehler bei der Installation von Python3"
                        log_and_echo "  Bitte installieren Sie Python3 manuell: sudo apt-get install python3 python3-pip python3-venv python3-tk"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit 1
                    fi
                else
                    log_and_echo "❌ Fehler bei apt-get update"
                    log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                    exit 1
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                echo "  Installiere Python3 über dnf..."
                if sudo dnf install -y python3 python3-pip python3-tkinter; then
                    echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                else
                    echo "❌ Fehler bei der Installation von Python3"
                    echo "  Bitte installieren Sie Python3 manuell: sudo dnf install python3 python3-pip python3-tkinter"
                    exit 1
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                echo "  Installiere Python3 über pacman..."
                if sudo pacman -S --noconfirm python python-pip tk; then
                    echo "✓ Python3 erfolgreich installiert (inkl. tkinter)"
                else
                    echo "❌ Fehler bei der Installation von Python3"
                    echo "  Bitte installieren Sie Python3 manuell: sudo pacman -S python python-pip tk"
                    exit 1
                fi
            else
                echo "❌ Paket-Manager nicht erkannt"
                echo "  Bitte installieren Sie Python3 manuell über Ihren Paket-Manager"
                exit 1
            fi
            ;;
        Darwin*)
            echo "❌ Python3 nicht gefunden auf macOS"
            echo "  Bitte installieren Sie Python3 über Homebrew: brew install python3"
            echo "  Oder laden Sie es von https://www.python.org/downloads/"
            exit 1
            ;;
        *)
            echo "❌ Betriebssystem nicht unterstützt für automatische Python3-Installation"
            echo "  Bitte installieren Sie Python3 manuell: https://www.python.org/downloads/"
            exit 1
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
    exit 1
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
                if sudo apt-get install -y python3-pip 2>&1 | tee -a "$LOG_FILE"; then
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
                            log_and_echo "  Bitte installieren Sie pip manuell: sudo apt-get install python3-pip"
                            log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                            exit 1
                        fi
                    else
                        log_and_echo "❌ Fehler beim Herunterladen von get-pip.py"
                        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
                        exit 1
                    fi
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                echo "  Installiere pip über dnf..."
                if sudo dnf install -y python3-pip; then
                    echo "✓ pip erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von pip"
                    echo "  Bitte installieren Sie pip manuell: sudo dnf install python3-pip"
                    exit 1
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                echo "  Installiere pip über pacman..."
                if sudo pacman -S --noconfirm python-pip; then
                    echo "✓ pip erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von pip"
                    echo "  Bitte installieren Sie pip manuell: sudo pacman -S python-pip"
                    exit 1
                fi
            else
                echo "⚠ Paket-Manager nicht erkannt, versuche get-pip.py..."
                curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
                if python3 get-pip.py; then
                    echo "✓ pip erfolgreich installiert"
                    rm get-pip.py
                else
                    echo "❌ Fehler bei der Installation von pip"
                    echo "  Bitte installieren Sie pip manuell"
                    exit 1
                fi
            fi
            ;;
        Darwin*)
            echo "⚠ pip nicht gefunden auf macOS"
            echo "  Versuche Installation über get-pip.py..."
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            if python3 get-pip.py; then
                echo "✓ pip erfolgreich installiert"
                rm get-pip.py
            else
                echo "❌ Fehler bei der Installation von pip"
                echo "  Bitte installieren Sie pip manuell: brew install python3"
                exit 1
            fi
            ;;
        *)
            echo "⚠ pip nicht gefunden, versuche get-pip.py..."
            curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
            if python3 get-pip.py; then
                echo "✓ pip erfolgreich installiert"
                rm get-pip.py
            else
                echo "❌ Fehler bei der Installation von pip"
                exit 1
            fi
            ;;
    esac
fi

PIP_VERSION=$(python3 -m pip --version 2>&1)
log_and_echo "✓ pip gefunden: $PIP_VERSION"
log_debug "pip-Version: $PIP_VERSION"
log_and_echo ""

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    log_and_echo "Erstelle virtuelle Umgebung..."
    log_debug "Erstelle venv in: $SCRIPT_DIR/venv"
    if python3 -m venv venv 2>&1 | tee -a "$LOG_FILE"; then
        log_and_echo "✓ Virtuelle Umgebung erstellt"
    else
        log_and_echo "❌ Fehler beim Erstellen der virtuellen Umgebung"
        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
        exit 1
    fi
    log_and_echo ""
else
    log_debug "venv existiert bereits"
fi

# Aktiviere venv
log_and_echo "Aktiviere virtuelle Umgebung..."
log_debug "Aktiviere venv: source $SCRIPT_DIR/venv/bin/activate"
source venv/bin/activate
log_debug "venv aktiviert, Python: $(which python3)"

# Installiere Abhängigkeiten
log_and_echo "Installiere Python-Abhängigkeiten..."
log_debug "Upgrade pip..."
if pip install --upgrade pip 2>&1 | tee -a "$LOG_FILE"; then
    log_debug "pip upgrade erfolgreich"
else
    log_and_echo "⚠ Warnung: pip upgrade fehlgeschlagen, fahre fort..."
fi

log_debug "Installiere requirements.txt..."
if [ -f "requirements.txt" ]; then
    log_debug "requirements.txt gefunden, starte Installation..."
    if pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"; then
        log_and_echo "✓ Python-Abhängigkeiten installiert"
    else
        log_and_echo "❌ Fehler bei der Installation der Abhängigkeiten"
        log_and_echo "  Siehe Log-Datei für Details: $LOG_FILE"
        log_and_echo "  Versuchen Sie manuell: pip install -r requirements.txt"
    fi
else
    log_and_echo "⚠ Warnung: requirements.txt nicht gefunden!"
    log_debug "requirements.txt nicht gefunden in: $SCRIPT_DIR"
fi

log_and_echo ""
log_and_echo "Prüfe System-Abhängigkeiten..."
log_and_echo ""

# Prüfe yt-dlp (als Python-Modul, da es über pip installiert wird)
echo "Prüfe yt-dlp..."
if python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null; then
    YTDLP_VERSION=$(python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null)
    echo "✓ yt-dlp installiert (Python-Modul): $YTDLP_VERSION"
elif command -v yt-dlp &> /dev/null; then
    YTDLP_VERSION=$(yt-dlp --version)
    echo "✓ yt-dlp installiert (System-Befehl): $YTDLP_VERSION"
else
    echo "⚠ yt-dlp nicht gefunden"
    echo "  Versuche Installation über pip..."
    pip install --upgrade yt-dlp
    if python3 -c "import yt_dlp" 2>/dev/null; then
        YTDLP_VERSION=$(python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" 2>/dev/null)
        echo "✓ yt-dlp erfolgreich installiert: $YTDLP_VERSION"
    else
        echo "❌ yt-dlp Installation fehlgeschlagen"
    fi
fi

# Prüfe und installiere ffmpeg falls nötig
if command -v ffmpeg &> /dev/null; then
    FFMPEG_VERSION=$(ffmpeg -version | head -1)
    echo "✓ ffmpeg bereits installiert: $FFMPEG_VERSION"
else
    echo "⚠ ffmpeg nicht gefunden - versuche automatische Installation..."
    
    # Erkenne Betriebssystem
    OS="$(uname -s)"
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint/Ubuntu ARM)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere ffmpeg über apt-get..."
                echo "  (Unterstützt: Ubuntu, Ubuntu ARM, Linux Mint, Debian)"
                if sudo apt-get update && sudo apt-get install -y ffmpeg; then
                    echo "✓ ffmpeg erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von ffmpeg"
                    echo "  Bitte installieren Sie ffmpeg manuell: sudo apt-get install ffmpeg"
                    echo "  Für Ubuntu ARM: sudo apt-get install ffmpeg (funktioniert gleich)"
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                echo "  Installiere ffmpeg über dnf..."
                if sudo dnf install -y ffmpeg; then
                    echo "✓ ffmpeg erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von ffmpeg"
                    echo "  Bitte installieren Sie ffmpeg manuell: sudo dnf install ffmpeg"
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                echo "  Installiere ffmpeg über pacman..."
                if sudo pacman -S --noconfirm ffmpeg; then
                    echo "✓ ffmpeg erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von ffmpeg"
                    echo "  Bitte installieren Sie ffmpeg manuell: sudo pacman -S ffmpeg"
                fi
            else
                echo "❌ Paket-Manager nicht erkannt"
                echo "  Bitte installieren Sie ffmpeg manuell über Ihren Paket-Manager"
            fi
            ;;
        Darwin*)
            # macOS - prüfe ob Homebrew installiert ist
            if command -v brew &> /dev/null; then
                echo "  Installiere ffmpeg über Homebrew..."
                if brew install ffmpeg; then
                    echo "✓ ffmpeg erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von ffmpeg"
                    echo "  Bitte installieren Sie ffmpeg manuell: brew install ffmpeg"
                fi
            else
                echo "❌ Homebrew nicht gefunden"
                echo "  Installieren Sie Homebrew: https://brew.sh"
                echo "  Dann: brew install ffmpeg"
            fi
            ;;
        *)
            echo "❌ Betriebssystem nicht unterstützt für automatische Installation"
            echo "  Bitte installieren Sie ffmpeg manuell:"
            echo "    Linux: sudo apt-get install ffmpeg (oder entsprechendes Paket-Manager)"
            echo "    macOS: brew install ffmpeg"
            echo "    Windows: https://ffmpeg.org/download.html"
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
    log_and_echo "    Installieren Sie es mit:"
    log_and_echo "      Ubuntu/Debian/Mint: sudo apt-get install python3-tk"
    log_and_echo "      Fedora/RHEL: sudo dnf install python3-tkinter"
    log_and_echo "      Arch Linux: sudo pacman -S tk"
    log_debug "tkinter FEHLT - Python kann es nicht importieren"
    ALL_OK=false
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
