#!/bin/bash
# Erstellt ein ZIP des Projekts ohne venv/dist/build – damit unter Linux Mint
# beim Entpacken kein Fehler auftritt (Symlinks und macOS-Binärdateien werden ausgeschlossen).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Name des ZIP (mit Version falls version.py existiert)
if [ -f "version.py" ]; then
    VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null) || true
    [ -z "$VERSION" ] && VERSION="snapshot"
else
    VERSION="snapshot"
fi

ZIP_NAME="UniversalDownloader-${VERSION}-linux.zip"

echo "Erstelle Linux-taugliches ZIP: $ZIP_NAME"
echo "  (ohne venv, dist, build, __pycache__, .git – verhindert Entpack-Fehler unter Linux Mint)"
echo ""

# Dateien/Ordner, die Probleme unter Linux machen oder nicht nötig sind:
# - venv/    : viele Symlinks, Python-Installation
# - dist/    : gebaute .app mit vielen Symlinks und macOS-Binaries
# - build/   : Build-Artefakte, enthält Symlinks
# - deb_build/ : gebaute .deb-Artefakte
# - __pycache__/ : Bytecode
# - .git/    : kann sehr groß sein, viele kleine Dateien
# - Logs/    : nicht nötig für Weitergabe
# - __MACOSX  : wird von zip auf Mac manchmal ergänzt, vermeiden
# - .gnupg/   : GPG-Schlüssel (privat), nicht mit ins ZIP

cd "$SCRIPT_DIR/.."
zip -r "$SCRIPT_DIR/$ZIP_NAME" "$(basename "$SCRIPT_DIR")" \
  -x "*/venv/*" \
  -x "*/dist/*" \
  -x "*/build/*" \
  -x "*/deb_build/*" \
  -x "*__pycache__*" \
  -x "*.pyc" \
  -x "*/.git/*" \
  -x "*/Logs/*" \
  -x "*/logs" \
  -x "*/logs/*" \
  -x "*vbs.log.txt" \
  -x "*.log" \
  -x "*/.cursor/*" \
  -x "*/.ytdlp_update_check.json" \
  -x "*/.ftp-credentials" \
  -x "*/settings.json" \
  -x "*/.deezer_config.json" \
  -x "*/.audible_config.json" \
  -x "*/.gnupg/*" \
  -x "*/.gnupg.zip" \
  -x "*/.DS_Store" \
  -x "*/__MACOSX*" \
  -x "*.dmg" \
  -x "*.deb" \

cd "$SCRIPT_DIR"
echo ""
echo "Fertig: $ZIP_NAME"
echo "  Dieses ZIP unter Linux Mint entpacken – es sollte ohne Fehler durchlaufen."
echo ""
