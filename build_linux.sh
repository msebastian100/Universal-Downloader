#!/bin/bash
# Build-Script für Linux .deb Paket (Ubuntu / Linux Mint / Debian)
# Erstellt ein installierbares Paket inkl. Startmenü-Verknüpfung und eigener venv (kein System-pip).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="universal-downloader"
DEB_DIR="deb_build"

# Lese Versionsnummer aus version.py (per Python, gleiche Logik wie build_mac.sh)
if [ -f "version.py" ]; then
    VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null) || true
    [ -z "$VERSION" ] && VERSION="2.0.0"
else
    VERSION="2.0.0"
fi

BUILD_DIR="$DEB_DIR/$APP_NAME-$VERSION"
INSTALL_DIR="/usr/share/$APP_NAME"

echo "============================================================"
echo "Erstelle Linux .deb Paket für Universal Downloader"
echo "============================================================"
echo "Version: $VERSION"
echo ""

# Prüfe ob wir auf Linux sind
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    if [[ "$GITHUB_ACTIONS" == "true" ]]; then
        echo "[INFO] Laeuft in GitHub Actions, fortfahren..."
    elif [ -t 0 ]; then
        echo "[HINWEIS] Dieses Script ist für Linux (Debian/Ubuntu/Mint) gedacht."
        read -p "Trotzdem fortfahren? (j/n): " response
        if [[ ! "$response" =~ ^[jJ]$ ]]; then
            exit 1
        fi
    else
        echo "[HINWEIS] Kein Linux und nicht interaktiv – .deb sollte auf Linux gebaut werden."
        echo "  Auf Linux ausführen: ./build_linux.sh"
        exit 1
    fi
fi

# Prüfe ob dpkg-deb vorhanden ist
if ! command -v dpkg-deb &> /dev/null; then
    echo "[ERROR] dpkg-deb nicht gefunden. Bitte installieren:"
    echo "  sudo apt-get install dpkg-dev"
    exit 1
fi

# Lösche alte Builds
if [ -d "$DEB_DIR" ]; then
    rm -rf "$DEB_DIR"
fi

# Verzeichnisstruktur
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR$INSTALL_DIR"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

# Alle Python-Module der Anwendung (ohne Build-/Test-Skripte).
# Bei neuen .py-Dateien im Projektroot: hier ergänzen (sonst ModuleNotFoundError z. B. unter Linux).
PY_FILES=(
    start.py gui.py version.py changelog.py path_helper.py yt_dlp_helper.py
    deezer_downloader.py deezer_auth.py spotify_downloader.py
    video_downloader.py audible_integration.py
    updater.py update_from_github.py auto_install_dependencies.py
    install_ffmpeg.py create_shortcut.py check_dependencies.py
    audiobook_providers.py audiobook_search.py stream_automation.py
    audio_recorder.py audio_device_detector.py setup_audio_recording.py
)

echo "Kopiere Anwendungsdateien..."
for f in "${PY_FILES[@]}"; do
    if [ -f "$f" ]; then
        cp "$f" "$BUILD_DIR$INSTALL_DIR/"
    else
        echo "[WARNUNG] Nicht gefunden: $f"
    fi
done

cp requirements.txt "$BUILD_DIR$INSTALL_DIR/" || exit 1

# Icon: für Desktop-Verknüpfung (Startmenü) und im Installationsordner fürs Fenster-Icon
if [ -f "icon.png" ]; then
    cp icon.png "$BUILD_DIR/usr/share/pixmaps/$APP_NAME.png"
    cp icon.png "$BUILD_DIR$INSTALL_DIR/"  # App sucht Icon in script_dir (Path(__file__).parent)
fi
if [ -f "icon.ico" ]; then
    cp icon.ico "$BUILD_DIR$INSTALL_DIR/"  # optional, für Fenster-Icon unter Linux
fi

# Wrapper-Skript: startet die App mit der venv (wird in postinst angelegt)
cat > "$BUILD_DIR/usr/bin/$APP_NAME" << EOF
#!/bin/bash
INSTALL_DIR="$INSTALL_DIR"
if [ -x "\$INSTALL_DIR/venv/bin/python3" ]; then
    exec "\$INSTALL_DIR/venv/bin/python3" "\$INSTALL_DIR/start.py" "\$@"
else
    echo "Fehler: Virtuelle Umgebung nicht gefunden. Bitte Paket neu installieren oder postinst ausführen."
    exit 1
fi
EOF
chmod +x "$BUILD_DIR/usr/bin/$APP_NAME"

# Desktop-Datei für Startmenü / Anwendungsmenü (Icon = absoluter Pfad, damit Startmenü es immer findet)
cat > "$BUILD_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Universal Downloader
Name[de]=Universal Downloader
Comment=Downloader für Musik, Hörbücher und Videos (Deezer, Audible, ORF, ARD, ZDF, YouTube, …)
Comment[de]=Downloader für Musik, Hörbücher und Videos (Deezer, Audible, ORF, ARD, ZDF, YouTube, …)
Exec=$APP_NAME
Icon=$INSTALL_DIR/icon.png
Terminal=false
Categories=AudioVideo;Audio;Video;Network;
Keywords=download;music;video;deezer;youtube;ard;zdf;orf;audible;
StartupNotify=true
EOF

# Paket-Metadaten
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: multimedia
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-venv, python3-tk, ffmpeg
Maintainer: Universal Downloader Team
Description: Universal Downloader für Musik, Hörbücher und Videos
 Ein universeller Downloader für:
 - Deezer & Spotify (Musik)
 - Audible (Hörbücher)
 - YouTube, ARD, ZDF, ORF, SWR, BR, Arte u. a. (Videos)
 - Eigene venv, keine System-Python-Pakete nötig (PEP 668-konform)
EOF

# postinst: venv anlegen und Abhängigkeiten installieren (mit venv-pip, kein System-pip)
# Hinweis: Nicht venv/bin/pip aufrufen – auf manchen Distros fehlt das Skript; immer python3 -m pip.
cat > "$BUILD_DIR/DEBIAN/postinst" << 'POSTINST'
#!/bin/bash
set -e
INSTALL_DIR="/usr/share/universal-downloader"
cd "$INSTALL_DIR" || { echo "Fehler: Installationsverzeichnis fehlt: $INSTALL_DIR"; exit 1; }

PY="venv/bin/python3"

# venv nur neu anlegen, wenn kein nutzbares venv-Python da ist (pip-Datei kann fehlen!)
if [ ! -x "$PY" ]; then
    rm -rf venv
    python3 -m venv venv || { echo "Fehler: python3-venv erforderlich (z. B. sudo apt install python3-venv)."; exit 1; }
    PY="venv/bin/python3"
fi

# Pip im venv sicherstellen (Minimal-Images / ältere venv ohne Scripts)
if ! "$PY" -m pip --version >/dev/null 2>&1; then
    "$PY" -m ensurepip --upgrade 2>/dev/null || true
fi
if ! "$PY" -m pip --version >/dev/null 2>&1; then
    echo "Fehler: pip im venv nicht verfügbar. Bitte z. B.: sudo apt install --reinstall python3-venv"
    echo "  Dann: sudo rm -rf $INSTALL_DIR/venv && sudo apt install --reinstall universal-downloader"
    exit 1
fi

# Abhängigkeiten nur mit venv-Python (PEP 668-konform, kein System-pip nötig)
if [ -f "requirements.txt" ]; then
    "$PY" -m pip install --upgrade pip -q
    "$PY" -m pip install -r requirements.txt -q || true
fi
# yt-dlp mind. 2026 (ZDF/ARD/ORF) – immer aktuelle Version von PyPI
"$PY" -m pip install --upgrade "yt-dlp>=2026" -q || true

# Desktop-Datenbank aktualisieren (Startmenü)
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi
POSTINST
chmod 755 "$BUILD_DIR/DEBIAN/postinst"

# prerm: optional
cat > "$BUILD_DIR/DEBIAN/prerm" << 'PRERM'
#!/bin/bash
# Beim Deinstallieren nichts Erzwungenes
exit 0
PRERM
chmod 755 "$BUILD_DIR/DEBIAN/prerm"

# .deb bauen
echo ""
echo "Baue .deb Paket..."
DEB_FILENAME="${APP_NAME}_${VERSION}_all.deb"
if ! dpkg-deb --build "$BUILD_DIR" "$DEB_DIR/$DEB_FILENAME"; then
    echo "[ERROR] Fehler beim Erstellen des .deb Pakets"
    exit 1
fi

if [ ! -f "$DEB_DIR/$DEB_FILENAME" ]; then
    echo "[ERROR] .deb Datei wurde nicht erstellt"
    exit 1
fi

DEB_ABSPATH="$(cd "$DEB_DIR" && pwd)/$DEB_FILENAME"

echo ""
echo "============================================================"
echo "[OK] Build erfolgreich!"
echo "============================================================"
echo ""
echo "Paket: $DEB_DIR/$DEB_FILENAME"
echo "Absoluter Pfad: $DEB_ABSPATH"
echo ""
echo "Installation unter Linux Mint / Ubuntu / Debian:"
echo ""
echo "  Empfohlen (Abhängigkeiten werden automatisch installiert, kein apt-get install -f nötig):"
echo "  sudo apt install \"$DEB_ABSPATH\""
echo ""
echo "  Alternative (manuell; danach ggf. fehlende Abhängigkeiten nachziehen):"
echo "  sudo dpkg -i \"$DEB_ABSPATH\""
echo "  sudo apt-get install -f"
echo ""
echo "Nach der Installation erscheint 'Universal Downloader' im Startmenü."
echo ""
