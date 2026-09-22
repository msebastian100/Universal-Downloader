#!/bin/bash
# Erstellt .dmg für macOS (Universal Downloader)
# Architektur: Host (Standard), oder: ./build_mac.sh arm64 | x86_64 | both
# Apple Silicon: natives arm64; Intel: x86_64 (auf ARM-Host unter Rosetta)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Universal Downloader"
DMG_NAME="UniversalDownloader"

if [ -f "version.py" ]; then
    VERSION=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null) || true
    [ -z "$VERSION" ] && VERSION="2.0.0"
else
    VERSION="2.0.0"
fi

if [ "$(uname -s)" != "Darwin" ]; then
    echo "[FEHLER] Dieses Skript muss auf macOS ausgeführt werden."
    exit 1
fi

HOST_ARCH="$(uname -m)"
REQUEST="${1:-}"
if [ -z "$REQUEST" ]; then
    REQUEST="$HOST_ARCH"
fi

FRAMEWORK_PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
[ -x "$FRAMEWORK_PY" ] || FRAMEWORK_PY="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

resolve_python_for_arch() {
    local arch="$1"
    if [ -x "$FRAMEWORK_PY" ]; then
        if arch -"$arch" "$FRAMEWORK_PY" -c "import sys; raise SystemExit(0 if sys.platform=='darwin' else 1)" 2>/dev/null; then
            echo "arch -$arch $FRAMEWORK_PY"
            return 0
        fi
    fi
    if [ "$arch" = "$HOST_ARCH" ]; then
        if [ "$arch" = "arm64" ] && [ -x /opt/homebrew/bin/python3 ]; then
            echo "arch -arm64 /opt/homebrew/bin/python3"
            return 0
        fi
        echo "python3"
        return 0
    fi
    echo "[FEHLER] Kein Python für $arch (python.org Universal-Installer 3.13 empfohlen)." >&2
    return 1
}

build_one_arch() {
    local ARCH="$1"
    local NATIVE_PY_CMD BUILD_VENV PY PIP APP_PATH DMG_FILE DMG_LAYOUT

    echo "============================================================"
    echo "  macOS .dmg Build: $APP_NAME v$VERSION ($ARCH)"
    echo "============================================================"
    echo "[INFO] Host-Architektur: $HOST_ARCH"

    NATIVE_PY_CMD="$(resolve_python_for_arch "$ARCH")" || exit 1
    echo "[INFO] Build-Python: $NATIVE_PY_CMD"

    deactivate 2>/dev/null || true
    unset VIRTUAL_ENV

    BUILD_VENV="$SCRIPT_DIR/.venv_build_mac_${ARCH}"
    venv_arch_ok() {
        [ -x "$BUILD_VENV/bin/python" ] || return 1
        local va
        va="$(arch -"$ARCH" "$BUILD_VENV/bin/python" -c "import platform; print(platform.machine())" 2>/dev/null)" || return 1
        [ "$va" = "$ARCH" ]
    }

    if [ -z "${VIRTUAL_ENV:-}" ]; then
        if [ ! -d "$BUILD_VENV" ] || ! venv_arch_ok; then
            rm -rf "$BUILD_VENV"
            echo "[INFO] Erstelle Build-venv ($ARCH): $BUILD_VENV"
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

    echo "[INFO] venv Python: $(arch -"$ARCH" "$PY" -c 'import platform,sys; print(sys.version.split()[0], platform.machine())')"

    if command -v ffmpeg >/dev/null 2>&1; then
        echo "[INFO] ffmpeg: $(command -v ffmpeg) ($(file -b "$(command -v ffmpeg)" 2>/dev/null || true))"
    else
        echo "[HINWEIS] ffmpeg fehlt – Video-Konvertierung/GPU brauchen ffmpeg."
    fi

    if [ -f "requirements.txt" ]; then
        echo "[INFO] Installiere/aktualisiere Abhängigkeiten (inkl. yt-dlp>=2026)..."
        arch -"$ARCH" "$PIP" install -r requirements.txt -q
    fi

    if ! arch -"$ARCH" "$PY" -c "import PyInstaller" 2>/dev/null; then
        echo "[INFO] PyInstaller wird installiert..."
        arch -"$ARCH" "$PIP" install PyInstaller
    fi

    if [ ! -f "icon.icns" ] && [ -f "icon.png" ]; then
        echo "[INFO] Erzeuge icon.icns aus icon.png (iconset)..."
        ICONSET="icon.iconset"
        mkdir -p "$ICONSET"
        for size in 16 32 64 128 256 512; do
            sips -z $size $size icon.png --out "$ICONSET/icon_${size}x${size}.png" 2>/dev/null || true
            [ $size -le 256 ] && size2=$((size*2)) && sips -z $size2 $size2 icon.png --out "$ICONSET/icon_${size}x${size}@2x.png" 2>/dev/null || true
        done
        iconutil -c icns "$ICONSET" -o icon.icns 2>/dev/null && rm -rf "$ICONSET" || echo "[HINWEIS] icon.icns konnte nicht erstellt werden."
    fi

    rm -rf build
    rm -rf "dist/$APP_NAME.app" "dist/dmg_layout"

    echo ""
    echo "[1/2] Baue .app mit PyInstaller ($ARCH)..."
    export UNIVERSAL_DOWNLOADER_TARGET_ARCH="$ARCH"
    if [ -f "UniversalDownloader_mac.spec" ]; then
        arch -"$ARCH" "$PY" -m PyInstaller --noconfirm UniversalDownloader_mac.spec
    else
        arch -"$ARCH" "$PY" -m PyInstaller --noconfirm --onedir --windowed --name "Universal Downloader" \
            --target-architecture "$ARCH" \
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

    echo ""
    echo "[2/2] Erstelle .dmg ($ARCH)..."
    DMG_FILE="dist/${DMG_NAME}_${VERSION}_${ARCH}.dmg"
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

    # Ohne Arch-Suffix: Host-Build (Updater-Fallback)
    if [ "$ARCH" = "$HOST_ARCH" ]; then
        cp -f "$DMG_FILE" "dist/${DMG_NAME}_${VERSION}.dmg"
    fi

    echo ""
    echo "============================================================"
    echo "  [OK] .dmg erstellt: $DMG_FILE"
    echo "============================================================"
    echo ""

    if [ -n "${VIRTUAL_ENV:-}" ] && [ "${VIRTUAL_ENV}" = "$BUILD_VENV" ]; then
        deactivate 2>/dev/null || true
    fi
}

case "$REQUEST" in
    both|all)
        build_one_arch arm64
        build_one_arch x86_64
        ;;
    arm64|aarch64)
        build_one_arch arm64
        ;;
    x86_64|intel|amd64)
        build_one_arch x86_64
        ;;
    *)
        build_one_arch "$HOST_ARCH"
        ;;
esac

echo "Fertige Dateien:"
ls -lh dist/${DMG_NAME}_${VERSION}*.dmg 2>/dev/null || true
echo ""
