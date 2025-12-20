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
echo "Installations-Status"
echo "=========================================="
echo ""

# Prüfe alle Abhängigkeiten und zeige Status
ALL_OK=true

# Prüfe requirements.txt Pakete
echo "Python-Pakete aus requirements.txt:"
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
        echo "  ✓ $package"
    else
        echo "  ✗ $package"
        ALL_OK=false
    fi
done

echo ""
echo "System-Abhängigkeiten:"

# Prüfe ffmpeg
if command -v ffmpeg &> /dev/null; then
    echo "  ✓ ffmpeg"
else
    echo "  ✗ ffmpeg"
    ALL_OK=false
fi

# Prüfe yt-dlp (als Python-Modul oder System-Befehl)
if python3 -c "import yt_dlp" 2>/dev/null || command -v yt-dlp &> /dev/null; then
    echo "  ✓ yt-dlp"
else
    echo "  ✗ yt-dlp"
    ALL_OK=false
fi

echo ""
echo "=========================================="
if [ "$ALL_OK" = true ]; then
    echo "✓ Alle Abhängigkeiten sind installiert!"
    echo "=========================================="
    echo ""
    echo "Starten Sie die Anwendung mit:"
    echo "  source venv/bin/activate"
    echo "  python3 start.py"
else
    echo "⚠ Einige Abhängigkeiten fehlen!"
    echo "=========================================="
    echo ""
    echo "Bitte installieren Sie fehlende Pakete:"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Oder prüfen Sie die Abhängigkeiten mit:"
    echo "  python3 check_dependencies.py"
fi
echo ""
