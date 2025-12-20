#!/bin/bash
# Installationsskript für Universal Downloader

echo "=========================================="
echo "Universal Downloader - Installation"
echo "=========================================="
echo ""

# Erkenne Betriebssystem
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "Betriebssystem: $OS"
echo "Architektur: $ARCH"
echo ""

# Prüfe und installiere Python3
echo "Prüfe Python3..."
if ! command -v python3 &> /dev/null; then
    echo "⚠ Python 3 nicht gefunden - versuche Installation..."
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere Python3 über apt-get..."
                if sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv; then
                    echo "✓ Python3 erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von Python3"
                    echo "  Bitte installieren Sie Python3 manuell: sudo apt-get install python3 python3-pip python3-venv"
                    exit 1
                fi
            # Prüfe ob dnf verfügbar ist (Fedora/RHEL)
            elif command -v dnf &> /dev/null; then
                echo "  Installiere Python3 über dnf..."
                if sudo dnf install -y python3 python3-pip; then
                    echo "✓ Python3 erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von Python3"
                    echo "  Bitte installieren Sie Python3 manuell: sudo dnf install python3 python3-pip"
                    exit 1
                fi
            # Prüfe ob pacman verfügbar ist (Arch Linux)
            elif command -v pacman &> /dev/null; then
                echo "  Installiere Python3 über pacman..."
                if sudo pacman -S --noconfirm python python-pip; then
                    echo "✓ Python3 erfolgreich installiert"
                else
                    echo "❌ Fehler bei der Installation von Python3"
                    echo "  Bitte installieren Sie Python3 manuell: sudo pacman -S python python-pip"
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

PYTHON_VERSION=$(python3 --version)
echo "✓ Python gefunden: $PYTHON_VERSION"

# Prüfe Python-Version (mindestens 3.8)
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "❌ Python 3.8 oder höher ist erforderlich (gefunden: $PYTHON_VERSION)"
    echo "  Bitte aktualisieren Sie Python3"
    exit 1
fi

echo ""

# Prüfe und installiere pip
echo "Prüfe pip..."
if ! python3 -m pip --version &> /dev/null; then
    echo "⚠ pip nicht gefunden - versuche Installation..."
    
    case "${OS}" in
        Linux*)
            # Prüfe ob apt-get verfügbar ist (Debian/Ubuntu/Mint)
            if command -v apt-get &> /dev/null; then
                echo "  Installiere pip über apt-get..."
                if sudo apt-get update && sudo apt-get install -y python3-pip; then
                    echo "✓ pip erfolgreich installiert"
                else
                    echo "⚠ apt-get Installation fehlgeschlagen, versuche get-pip.py..."
                    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
                    if python3 get-pip.py; then
                        echo "✓ pip erfolgreich installiert"
                        rm get-pip.py
                    else
                        echo "❌ Fehler bei der Installation von pip"
                        echo "  Bitte installieren Sie pip manuell: sudo apt-get install python3-pip"
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

PIP_VERSION=$(python3 -m pip --version)
echo "✓ pip gefunden: $PIP_VERSION"
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
    echo "System-Informationen:"
    echo "  Betriebssystem: $OS"
    echo "  Architektur: $ARCH"
    echo "  Python: $PYTHON_VERSION"
    echo "  pip: $PIP_VERSION"
    echo ""
    echo "Starten Sie die Anwendung mit:"
    echo "  source venv/bin/activate"
    echo "  python3 start.py"
else
    echo "⚠ Einige Abhängigkeiten fehlen!"
    echo "=========================================="
    echo ""
    echo "System-Informationen:"
    echo "  Betriebssystem: $OS"
    echo "  Architektur: $ARCH"
    echo "  Python: $PYTHON_VERSION"
    echo "  pip: $PIP_VERSION"
    echo ""
    echo "Bitte installieren Sie fehlende Pakete:"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo ""
    echo "Oder prüfen Sie die Abhängigkeiten mit:"
    echo "  python3 check_dependencies.py"
fi
echo ""
