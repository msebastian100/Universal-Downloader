#!/bin/bash
# Installationsskript für Universal Downloader

echo "=========================================="
echo "Universal Downloader - Installation"
echo "=========================================="
echo ""

# Prüfe Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 ist nicht installiert!"
    echo "Bitte installieren Sie Python 3.8 oder höher."
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "✓ Python gefunden: $PYTHON_VERSION"
echo ""

# Prüfe ob venv existiert
if [ ! -d "venv" ]; then
    echo "Erstelle virtuelle Umgebung..."
    python3 -m venv venv
    echo "✓ Virtuelle Umgebung erstellt"
    echo ""
fi

# Aktiviere venv
echo "Aktiviere virtuelle Umgebung..."
source venv/bin/activate

# Installiere Abhängigkeiten
echo "Installiere Python-Abhängigkeiten..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Prüfe System-Abhängigkeiten..."
echo ""

# Prüfe yt-dlp
if command -v yt-dlp &> /dev/null; then
    YTDLP_VERSION=$(yt-dlp --version)
    echo "✓ yt-dlp installiert: $YTDLP_VERSION"
else
    echo "⚠ yt-dlp nicht gefunden (sollte über pip installiert sein)"
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
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere ffmpeg über apt-get..."
                if sudo apt-get update && sudo apt-get install -y ffmpeg; then
                    echo "✓ ffmpeg erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von ffmpeg"
                    echo "  Bitte installieren Sie ffmpeg manuell: sudo apt-get install ffmpeg"
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

echo ""
echo "=========================================="
echo "Installation abgeschlossen!"
echo "=========================================="
echo ""
echo "Starten Sie die Anwendung mit:"
echo "  python3 start.py"
echo ""
echo "Oder prüfen Sie die Abhängigkeiten mit:"
echo "  python3 check_dependencies.py"
echo ""
