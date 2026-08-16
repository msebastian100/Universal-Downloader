#!/bin/bash
# 1. Baut die .deb (build_linux.sh)
# 2. Erzeugt das APT-Repo (build_apt_repo.sh)
# 3. Löscht vorhandene Dateien auf dem FTP-Server im APT-Verzeichnis und lädt den Inhalt von apt-repo/ hoch.
#
# Zugangsdaten: Entweder Umgebungsvariablen FTP_HOST, FTP_USER, FTP_PASS setzen
# oder Datei .ftp-credentials anlegen (siehe .ftp-credentials.example). .ftp-credentials wird von Git ignoriert.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REPO_DIR="${SCRIPT_DIR}/apt-repo"
APP_NAME="universal-downloader"

# Zugangsdaten laden
if [ -f "$SCRIPT_DIR/.ftp-credentials" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/.ftp-credentials"
fi

FTP_HOST="${FTP_HOST:-}"
FTP_USER="${FTP_USER:-}"
FTP_PASS="${FTP_PASS:-}"
FTP_APT_PATH="${FTP_APT_PATH:-apt}"

if [ -z "$FTP_HOST" ] || [ -z "$FTP_USER" ] || [ -z "$FTP_PASS" ]; then
    echo "[FEHLER] FTP-Zugangsdaten fehlen."
    echo "  Entweder .ftp-credentials anlegen (siehe .ftp-credentials.example) oder setzen:"
    echo "  export FTP_HOST=... FTP_USER=... FTP_PASS=..."
    exit 1
fi

# Ohne abschließenden Slash für curl
FTP_BASE="ftp://${FTP_HOST}/${FTP_APT_PATH}"
FTP_BASE_NO_TRAIL="${FTP_BASE%/}"

echo "============================================================"
echo "  Deploy: .deb bauen, APT-Repo erzeugen, per FTP hochladen"
echo "============================================================"
echo ""
echo "[Hinweis] Damit 'apt upgrade' die neue Version anzeigt, muss in version.py"
echo "  eine höhere Versionsnummer stehen als die aktuell installierte."
echo ""

# 1. .deb bauen
echo "--- Schritt 1: .deb bauen (build_linux.sh) ---"
./build_linux.sh
echo ""

# 2. APT-Repo erzeugen
echo "--- Schritt 2: APT-Repo erzeugen (build_apt_repo.sh) ---"
./build_apt_repo.sh
echo ""
# Anzeige der Paketversion (damit du siehst, was hochgeladen wird)
DEB_IN_REPO=$(ls -1 "$REPO_DIR/${APP_NAME}_"*_all.deb 2>/dev/null | head -1)
if [ -n "$DEB_IN_REPO" ] && [ -f "$DEB_IN_REPO" ]; then
    echo "[INFO] Paketversion für APT-Repo: $(basename "$DEB_IN_REPO" .deb | sed "s/^${APP_NAME}_//")"
fi
echo ""

if [ ! -d "$REPO_DIR" ] || [ -z "$(ls -A "$REPO_DIR" 2>/dev/null)" ]; then
    echo "[FEHLER] apt-repo/ ist leer oder fehlt."
    exit 1
fi

# 3. FTP: vorhandene Dateien löschen, dann hochladen
echo "--- Schritt 3: FTP – alte Dateien löschen, apt-repo/ hochladen ---"

if ! command -v curl &>/dev/null; then
    echo "[FEHLER] curl wird benötigt (FTP-Upload). Bitte installieren."
    exit 1
fi

# Vorhandene Dateien auflisten und löschen
echo "[INFO] Liste vorhandene Dateien auf dem Server..."
LIST=$(curl -s -u "${FTP_USER}:${FTP_PASS}" "${FTP_BASE_NO_TRAIL}/" -l 2>/dev/null) || true
if [ -n "$LIST" ]; then
    while IFS= read -r name; do
        [ -z "$name" ] && continue
        echo "[INFO] Lösche auf Server: $name"
        curl -s -u "${FTP_USER}:${FTP_PASS}" "${FTP_BASE_NO_TRAIL}/" -Q "DELE $name" 2>/dev/null || true
    done <<< "$LIST"
fi

# Dateien in fester Reihenfolge hochladen: zuerst Inhalte, zuletzt Release
# (vermindert Cache-Probleme: Release verweist auf Größen/Hashes der bereits hochgeladenen Dateien)
echo "[INFO] Lade Dateien aus apt-repo/ hoch (Reihenfolge: Inhalte zuerst, Release zuletzt)..."
upload_file() {
    local f="$1"
    [ -f "$f" ] || return 0
    local name=$(basename "$f")
    echo "[INFO] Hochladen: $name"
    curl -s -T "$f" -u "${FTP_USER}:${FTP_PASS}" "${FTP_BASE_NO_TRAIL}/${name}" --ftp-create-dirs
}
# 1) Packages und .deb zuerst
for name in Packages Packages.gz; do
    [ -f "$REPO_DIR/$name" ] && upload_file "$REPO_DIR/$name"
done
for f in "$REPO_DIR"/*.deb; do
    [ -f "$f" ] && upload_file "$f"
done
# 2) Release-Dateien zuletzt
for name in Release Release.gpg InRelease repo-key.asc; do
    [ -f "$REPO_DIR/$name" ] && upload_file "$REPO_DIR/$name"
done
# 3) Alles Übrige (falls neue Dateien dazukommen)
for f in "$REPO_DIR"/*; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    case "$name" in Packages|Packages.gz|Release|Release.gpg|InRelease|repo-key.asc|*.deb) continue ;; esac
    upload_file "$f"
done

echo ""
echo "============================================================"
echo "  Deploy abgeschlossen."
echo "============================================================"
