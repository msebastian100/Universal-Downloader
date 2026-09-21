#!/bin/bash
# Baut das Flatpak auf Linux bzw. auf der Repo-Test-VM.
# Noch kein Flathub-Upload (dafür extra Review + pip-Hashes).
#
# Nutzung: ./build_flatpak.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_ID="de.plertanix.universal-downloader"
BUILD_HOST="${RP_BUILD_HOST:-repo-test}"
REMOTE_DIR="${RP_REMOTE_DIR:-universal-downloader-build}"
SSH_KEY="${RP_SSH_KEY:-$HOME/.ssh/id_repo_test}"
MANIFEST="flatpak/${APP_ID}.yml"

build_on_linux() {
    if ! command -v flatpak-builder >/dev/null 2>&1; then
        echo "[INFO] Installiere flatpak-builder…"
        sudo apt-get update
        sudo apt-get install -y flatpak flatpak-builder
    fi
    sudo flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
    sudo flatpak install -y flathub \
        org.freedesktop.Platform//24.08 \
        org.freedesktop.Sdk//24.08 \
        org.freedesktop.Platform.ffmpeg-full//24.08

    mkdir -p flatpak-build
    flatpak-builder --user --install --force-clean \
        --state-dir .flatpak-builder \
        flatpak-build "$MANIFEST"
    echo
    echo "[OK] Installiert. Start:"
    echo "  flatpak run $APP_ID"
}

if [[ "${OSTYPE:-}" == linux-gnu* ]]; then
    build_on_linux
else
    echo "[INFO] Flatpak wird auf $BUILD_HOST gebaut…"
    rsync -az \
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
        --exclude '.flatpak-builder/' \
        --exclude 'flatpak-build/' \
        --exclude '*.snap' \
        --exclude '*.flatpak' \
        --exclude '.ftp-credentials' \
        --exclude 'Logs/' \
        --exclude 'logs' \
        --exclude '*.log' \
        --exclude 'vbs.log.txt' \
        --exclude '.cursor/' \
        --exclude '.DS_Store' \
        "$SCRIPT_DIR/" \
        "${BUILD_HOST}:~/${REMOTE_DIR}/"
    ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes "$BUILD_HOST" \
        "REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$HOME/$REMOTE_DIR"
chmod +x build_flatpak.sh
./build_flatpak.sh
REMOTE
fi
