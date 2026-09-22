#!/bin/bash
# Erstellt eine .dmg für macOS (Universal Downloader)
# Voraussetzung: Auf dem Mac ausführen, Python mit venv und Abhängigkeiten
# Apple Silicon (M1–M5): baut natives arm64; vermeidet Rosetta/x86_64-venv

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Universal Downloader"
DMG_NAME="UniversalDownloader"

# Version aus version.py (per Python, damit BSD/macOS kein Problem macht)
if [ -f "version.py" ]; then
    VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null) || true
    [ -z "$VERSION" ] && VERSION="2.0.0"
else
    VERSION="2.0.0"
fi

echo "============================================================"
echo "  macOS .dmg Build: $APP_NAME v$VERSION"
echo "============================================================"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "[FEHLER] Dieses Skript muss auf macOS ausgeführt werden."
    exit 1
fi

HOST_ARCH="$(uname -m)"
echo "[INFO] Host-Architektur: $HOST_ARCH"

# Native Python bevorzugen (Apple Silicon = arm64, nicht Rosetta)
resolve_native_python() {
    if [ "$HOST_ARCH" = "arm64" ]; then
        for cand in \
            /opt/homebrew/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
            /usr/bin/python3 \
            python3
        do
            if [ -x "$cand" ] || command -v "$cand" >/dev/null 2>&1; then
                if arch -arm64 "$cand" -c "import sys; raise SystemExit(0 if sys.platform=='darwin' else 1)" 2>/dev/null; then
                    echo "arch -arm64 $cand"
                    return 0
                fi
            fi
        done
    fi
    echo "python3"
}

NATIVE_PY_CMD="$(resolve_native_python)"
echo "[INFO] Build-Python: $NATIVE_PY_CMD"

# Eigenes venv (PEP 668: Homebrew-Python erlaubt kein pip install --user/system)
BUILD_VENV="$SCRIPT_DIR/.venv_build_mac"
venv_arch_ok() {
    [ -x "$BUILD_VENV/bin/python" ] || return 1
    local va
    va="$("$BUILD_VENV/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null)" || return 1
    if [ "$HOST_ARCH" = "arm64" ] && [ "$va" != "arm64" ]; then
        echo "[WARN] Bestehende venv ist $va (Rosetta) – wird für Apple Silicon neu erstellt."
        return 1
    fi
    return 0
}

if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ ! -d "$BUILD_VENV" ] || ! venv_arch_ok; then
        rm -rf "$BUILD_VENV"
        echo "[INFO] Erstelle natives Build-venv: $BUILD_VENV"
        # shellcheck disable=SC2086
        $NATIVE_PY_CMD -m venv "$BUILD_VENV"
    fi
    # shellcheck disable=SC1091
    source "$BUILD_VENV/bin/activate"
fi
PY="${VIRTUAL_ENV:-$BUILD_VENV}/bin/python"
PIP="${VIRTUAL_ENV:-$BUILD_VENV}/bin/pip"
[ -x "$PY" ] || PY="python3"
[ -x "$PIP" ] || PIP="pip3"

echo "[INFO] venv Python: $($PY -c 'import platform,sys; print(sys.version.split()[0], platform.machine())')"

# ffmpeg-Hinweis (VideoToolbox auf Apple Silicon)
if command -v ffmpeg >/dev/null 2>&1; then
    FF_ARCH="$(file -b "$(command -v ffmpeg)" 2>/dev/null || true)"
    echo "[INFO] ffmpeg: $(command -v ffmpeg) ($FF_ARCH)"
    if [ "$HOST_ARCH" = "arm64" ] && echo "$FF_ARCH" | grep -q x86_64 && ! echo "$FF_ARCH" | grep -q arm64; then
        echo "[HINWEIS] ffmpeg läuft unter Rosetta (x86_64). Für beste Performance:"
        echo "         brew install ffmpeg"
        echo "         (natives arm64 unter /opt/homebrew/bin – ggf. zuerst Homebrew für Apple Silicon installieren)"
    fi
else
    echo "[HINWEIS] ffmpeg fehlt – Video-Konvertierung/GPU brauchen ffmpeg."
    echo "         brew install ffmpeg"
fi

# Abhängigkeiten aus requirements.txt (yt-dlp>=2026 für ZDF/ARD/ORF)
if [ -f "requirements.txt" ]; then
    echo "[INFO] Installiere/aktualisiere Abhängigkeiten (inkl. yt-dlp>=2026)..."
    "$PIP" install -r requirements.txt -q
fi

# PyInstaller
if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
    echo "[INFO] PyInstaller wird installiert..."
    "$PIP" install PyInstaller
fi

# Optional: .icns aus icon.png erzeugen (für App-Icon)
if [ ! -f "icon.icns" ] && [ -f "icon.png" ]; then
    echo "[INFO] Erzeuge icon.icns aus icon.png (iconset)..."
    ICONSET="icon.iconset"
    mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size icon.png --out "$ICONSET/icon_${size}x${size}.png" 2>/dev/null || true
        [ $size -le 256 ] && size2=$((size*2)) && sips -z $size2 $size2 icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" 2>/dev/null || true
    done
    iconutil -c icns "$ICONSET" -o icon.icns 2>/dev/null && rm -rf "$ICONSET" || echo "[HINWEIS] icon.icns konnte nicht erstellt werden, App verwendet Standard-Icon."
fi

# Alte Builds löschen (dist-Ordner nicht komplett, sonst "Directory not empty")
rm -rf build
rm -rf "dist/$APP_NAME.app" "dist/dmg_layout"
rm -f "dist/${DMG_NAME}"_*.dmg

# Mit Mac-Spec bauen (.app Bundle)
echo ""
echo "[1/2] Baue .app mit PyInstaller..."
export UNIVERSAL_DOWNLOADER_TARGET_ARCH="$HOST_ARCH"
if [ -f "UniversalDownloader_mac.spec" ]; then
    "$PY" -m PyInstaller --noconfirm UniversalDownloader_mac.spec
else
    "$PY" -m PyInstaller --noconfirm --onedir --windowed --name "Universal Downloader" \
        --target-architecture "$HOST_ARCH" \
        --hidden-import=tkinter --hidden-import=PIL --hidden-import=mutagen \
        --hidden-import=deezer --hidden-import=yt_dlp --hidden-import=yt_dlp_helper \
        --hidden-import=path_helper --hidden-import=video_downloader --hidden-import=audible_integration \
        --hidden-import=mac_platform --hidden-import=series_watch --hidden-import=series_watch_tray --hidden-import=pystray \
        start.py
fi

APP_PATH="dist/$APP_NAME.app"
if [ ! -d "$APP_PATH" ]; then
    echo "[FEHLER] $APP_PATH wurde nicht erstellt."
    exit 1
fi

# .dmg erstellen (mit App + Alias „Programme“)
echo ""
echo "[2/2] Erstelle .dmg (mit Programme-Ordner-Alias)..."
DMG_FILE="dist/${DMG_NAME}_${VERSION}.dmg"
rm -f "$DMG_FILE"

DMG_LAYOUT="dist/dmg_layout"
rm -rf "$DMG_LAYOUT"
mkdir -p "$DMG_LAYOUT"
cp -R "$APP_PATH" "$DMG_LAYOUT/"
ln -s /Applications "$DMG_LAYOUT/Programme"

hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_LAYOUT" -ov -format UDZO "$DMG_FILE"
rm -rf "$DMG_LAYOUT"

if [ ! -f "$DMG_FILE" ]; then
    echo "[FEHLER] .dmg wurde nicht erstellt."
    exit 1
fi

echo ""
echo "============================================================"
echo "  [OK] .dmg erstellt: $DMG_FILE"
echo "============================================================"
echo ""
echo "Öffnen: open $DMG_FILE"
echo ""
