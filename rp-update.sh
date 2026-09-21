#!/bin/bash
# RP-Update: Linux-.deb bauen, APT-Repo signieren, per FTP nach ppa.plertanix.de hochladen.
# Behält die vorherige Version als Fallback. GitHub bleibt unberührt.
#
# Nutzung: ./rp-update.sh
# Auf dem Mac über die Repo-Test-VM (SSH-Host repo-test). Auf Linux direkt lokal.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="universal-downloader"
BUILD_HOST="${RP_BUILD_HOST:-repo-test}"
REMOTE_DIR="${RP_REMOTE_DIR:-universal-downloader-build}"
VMX_DEFAULT="/Volumes/Externe/Virtuellemaschiene/Ubuntu 24.04 ARM Repo-Test.vmwarevm/Ubuntu 24.04 ARM Repo-Test.vmx"
VMX="${RP_BUILD_VMX:-$VMX_DEFAULT}"
SSH_KEY="${RP_SSH_KEY:-$HOME/.ssh/id_repo_test}"
SIGNING_KEY="${APT_SIGNING_KEY:-2D0851F0234BBEC3}"

VERSION=$(python3 -c "from version import __version__; print(__version__)")
echo "============================================================"
echo "  RP-Update  →  APT/FTP   (Version $VERSION)"
echo "============================================================"

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
    local ip=""
    for _ in $(seq 1 60); do
        if ssh_cmd 'echo ok' >/dev/null 2>&1; then
            echo "[INFO] SSH steht."
            return 0
        fi
        ip=$(vmrun -T fusion getGuestIPAddress "$VMX" 2>/dev/null || true)
        if [ -n "$ip" ] && [ "$ip" != "Error: Unable to get the IP address" ]; then
            ssh -i "$SSH_KEY" -o IdentitiesOnly=yes -o BatchMode=yes -o ConnectTimeout=5 \
                -o StrictHostKeyChecking=accept-new "basti@$ip" 'echo ok' >/dev/null 2>&1 && {
                echo "[INFO] SSH über $ip – Host repo-test in ~/.ssh/config prüfen."
                BUILD_HOST="basti@$ip"
                return 0
            }
        fi
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
        --exclude '*.dmg' \
        --exclude '*.iso' \
        --exclude '*.zip' \
        --exclude '.DS_Store' \
        --exclude 'UniversalDownloader*' \
        "$SCRIPT_DIR/" \
        "${BUILD_HOST}:~/${REMOTE_DIR}/"
}

build_on_builder() {
    local prev
    prev=$(curl -fsS https://ppa.plertanix.de/apt/Packages | python3 -c "
import sys
from version import compare_versions
current = '''$VERSION'''
prev = None
ver = None
for line in sys.stdin:
    if line.startswith('Version:'):
        ver = line.split(':', 1)[1].strip()
        if compare_versions(ver, current) < 0:
            if prev is None or compare_versions(ver, prev) > 0:
                prev = ver
print(prev or '')
")
    ssh_cmd "PREV='$prev' SIGNING_KEY='$SIGNING_KEY' REMOTE_DIR='$REMOTE_DIR' bash -s" <<'REMOTE'
set -euo pipefail
cd "$HOME/$REMOTE_DIR"
export GNUPGHOME="$HOME/$REMOTE_DIR/.gnupg"
export APT_SIGNING_KEY="$SIGNING_KEY"
chmod 700 "$GNUPGHOME" 2>/dev/null || true
if [ -d "$GNUPGHOME/private-keys-v1.d" ]; then
    chmod 700 "$GNUPGHOME/private-keys-v1.d"
    chmod 600 "$GNUPGHOME"/private-keys-v1.d/*.key 2>/dev/null || true
fi
if [ -f "$GNUPGHOME/gpg.conf" ] && ! grep -q 'pinentry-mode loopback' "$GNUPGHOME/gpg.conf"; then
    printf '\npinentry-mode loopback\nbatch\n' >> "$GNUPGHOME/gpg.conf"
fi
./build_linux.sh
if [ -n "${PREV:-}" ]; then
    echo "[INFO] Fallback $PREV holen..."
    curl -f -sS "https://ppa.plertanix.de/apt/${APP_NAME:-universal-downloader}_${PREV}_all.deb" \
        -o "deb_build/universal-downloader_${PREV}_all.deb" || true
fi
./build_apt_repo.sh
REMOTE
    rsync -az --delete \
        -e "ssh -i $SSH_KEY -o IdentitiesOnly=yes -o BatchMode=yes" \
        "${BUILD_HOST}:~/${REMOTE_DIR}/apt-repo/" \
        "$SCRIPT_DIR/apt-repo/"
}

if [[ "${OSTYPE:-}" == linux-gnu* ]]; then
    ./deploy_apt_to_ftp.sh
else
    ensure_builder
    echo "[INFO] Quellcode zur Builder-VM..."
    rsync_to_builder
    echo "[INFO] .deb + signiertes APT-Repo auf der VM..."
    build_on_builder
    echo "[INFO] FTP-Upload..."
    SKIP_BUILD=1 ./deploy_apt_to_ftp.sh
fi

echo
echo "[OK] RP-Update fertig. Live:"
curl -sS https://ppa.plertanix.de/apt/Packages | grep -E '^(Package|Version|Filename):' || true
echo "--- dists/stable ---"
curl -sS -I https://ppa.plertanix.de/apt/dists/stable/InRelease | head -n 5 || true
