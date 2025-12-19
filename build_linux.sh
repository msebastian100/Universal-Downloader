#!/bin/bash
# Build-Script für Linux .deb Paket

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="universal-downloader"
DEB_DIR="deb_build"

# Lese Versionsnummer aus version.py
if [ -f "version.py" ]; then
    VERSION=$(grep -E "^__version__\s*=\s*['\"]" version.py | sed -E "s/^__version__\s*=\s*['\"]([^'\"]+)['\"].*/\1/")
    if [ -z "$VERSION" ]; then
        echo "[WARNING] Konnte Versionsnummer nicht aus version.py lesen, verwende 2.0.0"
        VERSION="2.0.0"
    fi
else
    echo "[WARNING] version.py nicht gefunden, verwende 2.0.0"
    VERSION="2.0.0"
fi

BUILD_DIR="$DEB_DIR/$APP_NAME-$VERSION"

echo "============================================================"
echo "Erstelle Linux .deb Paket für Universal Downloader"
echo "============================================================"

# Prüfe ob wir auf Linux sind
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    # In GitHub Actions automatisch fortfahren
    if [[ "$GITHUB_ACTIONS" == "true" ]]; then
        echo "[WARNING] Laeuft in GitHub Actions, fortfahren..."
    else
        echo "[WARNING] Dieses Script ist fuer Linux gedacht."
        read -p "Fortfahren? (j/n): " response
        if [[ ! "$response" =~ ^[jJ]$ ]]; then
            exit 1
        fi
    fi
fi

# Prüfe ob dpkg-deb vorhanden ist
if ! command -v dpkg-deb &> /dev/null; then
    echo "[ERROR] dpkg-deb nicht gefunden. Bitte installieren Sie:"
    echo "  sudo apt-get install dpkg-dev"
    exit 1
fi

# Lösche alte Builds
if [ -d "$DEB_DIR" ]; then
    rm -rf "$DEB_DIR"
fi

# Erstelle Verzeichnisstruktur
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/share/$APP_NAME"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

# Kopiere Dateien
echo "Kopiere Dateien..."
cp start.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp gui.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp deezer_downloader.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp deezer_auth.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp spotify_downloader.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp video_downloader.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp audible_integration.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp install_ffmpeg.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp requirements.txt "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp updater.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1
cp version.py "$BUILD_DIR/usr/share/$APP_NAME/" || exit 1

# Kopiere Icon falls vorhanden
if [ -f "icon.png" ]; then
    cp icon.png "$BUILD_DIR/usr/share/pixmaps/$APP_NAME.png"
fi

# Erstelle Start-Script
cat > "$BUILD_DIR/usr/bin/$APP_NAME" << 'EOF'
#!/bin/bash
cd /usr/share/universal-downloader
python3 start.py "$@"
EOF
chmod +x "$BUILD_DIR/usr/bin/$APP_NAME"

# Erstelle Desktop-Datei
cat > "$BUILD_DIR/usr/share/applications/$APP_NAME.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Universal Downloader
Comment=Downloader für Musik und Videos
Exec=$APP_NAME
Icon=$APP_NAME
Terminal=false
Categories=AudioVideo;Network;
EOF

# Erstelle control-Datei
cat > "$BUILD_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $VERSION
Section: multimedia
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-pip, python3-tk, ffmpeg, yt-dlp
Maintainer: Universal Downloader Team
Description: Universal Downloader für Musik und Videos
 Ein universeller Downloader für:
 - Deezer Musik
 - Spotify Musik (über YouTube/Deezer Fallback)
 - Videos von öffentlich-rechtlichen Sendern
 - Audible Hörbücher
EOF

# Erstelle postinst-Script
cat > "$BUILD_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/bash
# Installiere Python-Abhängigkeiten
cd /usr/share/universal-downloader
if [ -f requirements.txt ]; then
    pip3 install -r requirements.txt --break-system-packages 2>/dev/null || \
    pip3 install -r requirements.txt --user 2>/dev/null || \
    pip3 install -r requirements.txt 2>/dev/null || true
fi

# Aktualisiere Desktop-Datenbank
update-desktop-database 2>/dev/null || true
EOF
chmod +x "$BUILD_DIR/DEBIAN/postinst"

# Erstelle prerm-Script (optional)
cat > "$BUILD_DIR/DEBIAN/prerm" << 'EOF'
#!/bin/bash
# Optional: Aufräumen beim Deinstallieren
EOF
chmod +x "$BUILD_DIR/DEBIAN/prerm"

# Erstelle .deb Paket
echo ""
echo "Erstelle .deb Paket..."
DEB_FILENAME="${APP_NAME}_v${VERSION}_all.deb"
if ! dpkg-deb --build "$BUILD_DIR" "$DEB_DIR/$DEB_FILENAME"; then
    echo "[ERROR] Fehler beim Erstellen des .deb Pakets"
    exit 1
fi

# Prüfe ob .deb erstellt wurde
if [ ! -f "$DEB_DIR/$DEB_FILENAME" ]; then
    echo "[ERROR] .deb Datei wurde nicht erstellt"
    exit 1
fi

echo ""
echo "============================================================"
echo "[OK] Build erfolgreich!"
echo "============================================================"
echo ""
echo "Das .deb Paket befindet sich in:"
echo "  $DEB_DIR/$DEB_FILENAME"
echo ""
echo "Installation:"
echo "  sudo dpkg -i $DEB_DIR/$DEB_FILENAME"
echo "  sudo apt-get install -f  # Falls Abhängigkeiten fehlen"
echo ""
