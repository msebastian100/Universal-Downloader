#!/bin/bash
# Baut den Snap (lokal auf Linux bzw. auf der Repo-Test-VM).
# Veröffentlichung in den Snap Store: extra, braucht Ubuntu-One-Login.
#
# Nutzung:
#   ./publish_snap.sh              # nur bauen
#   ./publish_snap.sh --upload     # bauen + upload (snapcraft muss eingeloggt sein)
#
# Mehrere Architekturen (amd64+arm64) für Ubuntu Software:
#   snapcraft remote-build --launchpad-accept-public-upload
# danach: snapcraft upload --release=stable *.snap

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="universal-downloader"
BUILD_HOST="${RP_BUILD_HOST:-repo-test}"
REMOTE_DIR="${RP_REMOTE_DIR:-universal-downloader-build}"
SSH_KEY="${RP_SSH_KEY:-$HOME/.ssh/id_repo_test}"
VMX_DEFAULT="/Volumes/Externe/Virtuellemaschiene/Ubuntu 24.04 ARM Repo-Test.vmwarevm/Ubuntu 24.04 ARM Repo-Test.vmx"
VMX="${RP_BUILD_VMX:-$VMX_DEFAULT}"
DO_UPLOAD=0
[ "${1:-}" = "--upload" ] && DO_UPLOAD=1

VERSION=$(python3 -c "from version import __version__; print(__version__)")
echo "============================================================"
echo "  Snap-Build  →  ${APP_NAME}  (Version $VERSION)"
echo "============================================================"

mkdir -p snap/gui
if [ -f snap/gui/icon-store-256.png ]; then
    cp -f snap/gui/icon-store-256.png snap/gui/universal-downloader.png
else
    cp -f icon.png snap/gui/universal-downloader.png
fi

ssh_cmd() {
    ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=8 "$BUILD_HOST" "$@"
}

ensure_builder() {
    if ssh_cmd 'echo ok' >/dev/null 2>&1; then
        echo "[INFO] Builder erreichbar: $BUILD_HOST"
        return 0
    fi
    if [ ! -f "$VMX" ]; then
        echo "[FEHLER] $BUILD_HOST nicht erreichbar und VMX fehlt: $VMX"
        exit 1
    fi
    echo "[INFO] Starte Builder-VM..."
    vmrun -T fusion start "$VMX" gui 2>/dev/null || vmrun -T fusion start "$VMX" nogui
    for _ in $(seq 1 60); do
        ssh_cmd 'echo ok' >/dev/null 2>&1 && return 0
        sleep 3
    done
    echo "[FEHLER] Builder-VM startet, aber SSH kommt nicht."
    exit 1
}

rsync_to_builder() {
    rsync -az --delete \
        -e "ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes" \
        --exclude '.git/' \
        --exclude '__pycache__/' \
        --exclude '*.pyc' \
        --exclude '.venv*' \
        --exclude 'venv/' \
        --exclude 'deb_build/' \
        --exclude 'apt-repo/' \
        --exclude 'dist/' \
        --exclude 'build/' \
        --exclude 'parts/' \
        --exclude 'stage/' \
        --exclude 'prime/' \
        --exclude '*.snap' \
        --exclude '.ftp-credentials' \
        --exclude 'Logs/' \
        --exclude 'logs' \
        --exclude '*.log' \
        --exclude '*.log.txt' \
        --exclude 'vbs.log.txt' \
        --exclude '.ytdlp_update_check.json' \
        --exclude '.cursor/' \
        --exclude '.deezer_config.json' \
        --exclude '.audible_config.json' \
        --exclude 'settings.json' \
        --exclude '.DS_Store' \
        "$SCRIPT_DIR/" \
        "${BUILD_HOST}:~/${REMOTE_DIR}/"
}

build_on_linux() {
    if ! command -v snapcraft >/dev/null 2>&1; then
        echo "[INFO] Installiere snapcraft…"
        sudo snap install snapcraft --classic
    fi
    snapcraft pack --destructive-mode
}

if [[ "${OSTYPE:-}" == linux-gnu* ]]; then
    build_on_linux
else
    ensure_builder
    echo "[INFO] Quellcode zur Builder-VM..."
    rsync_to_builder
    echo "[INFO] Snap auf der VM bauen (destructive-mode)..."
    ssh_cmd "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$HOME/$REMOTE_DIR"
if ! command -v snapcraft >/dev/null 2>&1; then
    echo "[INFO] Installiere snapcraft…"
    sudo snap install snapcraft --classic
fi
# Kern-Snaps für core24/gnome, sonst hängt pack an Downloads
sudo snap install desktop-gtk-common-themes 2>/dev/null || true
snapcraft pack --destructive-mode
REMOTE
    mkdir -p "$SCRIPT_DIR/dist"
    rsync -az -e "ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes" \
        --include '*.snap' --exclude '*' \
        "${BUILD_HOST}:~/${REMOTE_DIR}/" \
        "$SCRIPT_DIR/dist/"
fi

SNAP_FILE=$(ls -1t "$SCRIPT_DIR"/dist/*.snap "$SCRIPT_DIR"/*.snap 2>/dev/null | head -n 1 || true)
echo
if [ -n "${SNAP_FILE:-}" ]; then
    echo "[OK] Snap: $SNAP_FILE"
else
    echo "[WARNUNG] Keine .snap-Datei gefunden."
fi

if [ "$DO_UPLOAD" -eq 1 ]; then
    if ! command -v snapcraft >/dev/null 2>&1; then
        echo "[FEHLER] snapcraft fehlt lokal – Upload auf Linux oder nach 'snapcraft login'."
        exit 1
    fi
    [ -n "${SNAP_FILE:-}" ] || { echo "[FEHLER] Nichts zum Hochladen."; exit 1; }
    echo "[INFO] Name registrieren (einmalig, ignoriert wenn schon da)…"
    snapcraft register "$APP_NAME" || true
    snapcraft upload --release=stable "$SNAP_FILE"
else
    echo
    echo "Damit Ubuntu-Software die App für jeden findet:"
    echo "  1. Konto: https://snapcraft.io  (Ubuntu One)"
    echo "  2. snapcraft login"
    echo "  3. snapcraft register $APP_NAME"
    echo "  4. Für amd64+arm64:  snapcraft remote-build --launchpad-accept-public-upload"
    echo "  5. snapcraft upload --release=stable ${APP_NAME}_*.snap"
    echo
    echo "Lokal testen (auf der Linux-VM):"
    echo "  sudo snap install --dangerous ${APP_NAME}_*.snap"
fi
