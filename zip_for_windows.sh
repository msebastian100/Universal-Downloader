#!/bin/bash
# Erstellt UniversalDownloader-<Version>-windows.zip mit allen Projektdateien für den Windows-Build
# und den Installer (installer.iss) nötig sind. ZIP auf Windows entpacken, dann:
#   python build_windows.py
#   python build_installer.py   (mit installiertem Inno Setup)
# ergibt die .exe und die Setup-Installer-Datei.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Version für ZIP-Namen (optional)
if [ -f "version.py" ]; then
    VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null) || true
    [ -z "$VERSION" ] && VERSION="snapshot"
else
    VERSION="snapshot"
fi

ZIP_NAME="UniversalDownloader-${VERSION}-windows.zip"

echo "Erstelle ZIP für Windows-Build: $ZIP_NAME"
echo "  Enthält: Quellcode, installer.iss, .spec, Build-Skripte, icon.ico – alles für EXE + Installer."
echo ""

# Von Projektordner-Ebene aus zippen, damit ein Wurzelordner (z. B. Downloader) im ZIP liegt
cd "$SCRIPT_DIR/.."
PROJECT_DIR="$(basename "$SCRIPT_DIR")"

zip -r "$SCRIPT_DIR/$ZIP_NAME" "$PROJECT_DIR" \
  -x "*/venv/*" \
  -x "*/.venv/*" \
  -x "*/env/*" \
  -x "*/dist/*" \
  -x "*/build/*" \
  -x "*/dist_installer/*" \
  -x "*__pycache__*" \
  -x "*.pyc" \
  -x "*.pyo" \
  -x "*/.git/*" \
  -x "*/.gnupg/*" \
  -x "*/.gnupg.zip" \
  -x "*/.cursor/*" \
  -x "*/.idea/*" \
  -x "*/.DS_Store" \
  -x "*/__MACOSX*" \
  -x "*/Logs/*" \
  -x "*/logs" \
  -x "*/logs/*" \
  -x "*vbs.log.txt" \
  -x "*.log.txt" \
  -x "*.dmg" \
  -x "*.deb" \
  -x "*.log" \
  -x "*/.deps_ok" \
  -x "*/.ytdlp_update_check.json" \
  -x "*/UniversalDownloader-*-linux.zip" \
  -x "*/UniversalDownloader-*-windows.zip"

cd "$SCRIPT_DIR"
echo ""
echo "Fertig: $ZIP_NAME"
echo "  Auf Windows: ZIP entpacken, dann im entpackten Ordner:"
echo "    1. Python 3 installieren, Abhängigkeiten: pip install -r requirements.txt"
echo "    2. python build_windows.py"
echo "    3. Inno Setup 6 installieren, danach: python build_installer.py"
echo ""
