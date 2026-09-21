#!/bin/bash
# 1. Baut die .deb (build_linux.sh)
# 2. Holt die vorherige Version vom Server (Fallback), erzeugt das APT-Repo (build_apt_repo.sh)
# 3. Lädt apt-repo/ per FTP hoch und löscht auf dem Server alles Ältere als aktuell + vorherige Version.
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

deb_version_from_name() {
    local n="$1"
    n="${n##*/}"
    n="${n#${APP_NAME}_}"
    n="${n%_all.deb}"
    printf '%s\n' "$n"
}

ftp_list() {
    curl -s --ftp-pasv -u "${FTP_USER}:${FTP_PASS}" "${FTP_BASE_NO_TRAIL}/" -l 2>/dev/null | tr -d '\r' || true
}

ftp_dele() {
    local name="$1"
    echo "[INFO] Lösche auf Server: $name"
    # Quote-Befehle direkt nach Login: erst ins APT-Verzeichnis, dann DELE.
    # +DELE zusammen mit -l (Listing) sendet curl nicht.
    if ! curl -sS --ftp-pasv -u "${FTP_USER}:${FTP_PASS}" "ftp://${FTP_HOST}/" \
        --quote "CWD ${FTP_APT_PATH}" \
        --quote "DELE $name" \
        -o /dev/null; then
        echo "[WARNUNG] Konnte $name nicht löschen."
        return 1
    fi
}

# 1. .deb bauen
echo "--- Schritt 1: .deb bauen (build_linux.sh) ---"
./build_linux.sh
echo ""

# Vorherige Version vom Server holen, damit apt-repo aktuell + Fallback enthält
CURRENT_VER=$(python3 -c "from version import __version__; print(__version__)" 2>/dev/null || true)
mkdir -p "$SCRIPT_DIR/deb_build" "$REPO_DIR"
echo "--- Vorherige Version als Fallback sichern ---"
PREV_VER=$(ftp_list | python3 -c "
import sys
from version import compare_versions
app = '${APP_NAME}'
current = '''${CURRENT_VER}'''
prev = None
for raw in sys.stdin:
    name = raw.strip()
    prefix, suffix = app + '_', '_all.deb'
    if not (name.startswith(prefix) and name.endswith(suffix)):
        continue
    ver = name[len(prefix):-len(suffix)]
    if not current or compare_versions(ver, current) >= 0:
        continue
    if prev is None or compare_versions(ver, prev) > 0:
        prev = ver
print(prev or '')
" 2>/dev/null || true)

if [ -n "$PREV_VER" ]; then
    PREV_DEB="${APP_NAME}_${PREV_VER}_all.deb"
    if [ -f "$SCRIPT_DIR/deb_build/$PREV_DEB" ] || [ -f "$REPO_DIR/$PREV_DEB" ]; then
        echo "[INFO] Vorherige Version $PREV_VER ist lokal vorhanden."
    else
        echo "[INFO] Lade Fallback $PREV_VER vom Server..."
        if curl -f -sS "https://ppa.plertanix.de/apt/${PREV_DEB}" -o "$SCRIPT_DIR/deb_build/$PREV_DEB"; then
            echo "[INFO] $PREV_DEB per HTTPS geholt."
        elif curl -f -sS --ftp-pasv -u "${FTP_USER}:${FTP_PASS}" "${FTP_BASE_NO_TRAIL}/${PREV_DEB}" -o "$SCRIPT_DIR/deb_build/$PREV_DEB"; then
            echo "[INFO] $PREV_DEB per FTP geholt."
        else
            echo "[WARNUNG] Vorherige Version $PREV_VER konnte nicht geholt werden – Repo enthält nur die aktuelle."
            rm -f "$SCRIPT_DIR/deb_build/$PREV_DEB"
        fi
    fi
else
    echo "[INFO] Keine ältere Version auf dem Server – Repo enthält nur die aktuelle."
fi
echo ""

# 2. APT-Repo erzeugen
echo "--- Schritt 2: APT-Repo erzeugen (build_apt_repo.sh) ---"
./build_apt_repo.sh
echo ""
echo "[INFO] Paketversionen im APT-Repo:"
for f in "$REPO_DIR/${APP_NAME}_"*_all.deb; do
    [ -f "$f" ] || continue
    echo "  - $(deb_version_from_name "$(basename "$f")")"
done
echo ""

if [ ! -d "$REPO_DIR" ] || [ -z "$(ls -A "$REPO_DIR" 2>/dev/null)" ]; then
    echo "[FEHLER] apt-repo/ ist leer oder fehlt."
    exit 1
fi

# 3. FTP: hochladen, danach ältere .deb (älter als aktuell + Fallback) löschen
echo "--- Schritt 3: FTP – apt-repo/ hochladen, ältere Versionen entfernen ---"

if ! command -v curl &>/dev/null; then
    echo "[FEHLER] curl wird benötigt (FTP-Upload). Bitte installieren."
    exit 1
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
echo "[INFO] Entferne ältere .deb auf dem Server (behalte aktuell + Fallback)..."
while IFS= read -r name; do
    [ -z "$name" ] && continue
    case "$name" in .|..) continue ;; esac
    case "$name" in
        ${APP_NAME}_*_all.deb)
            if [ -f "$REPO_DIR/$name" ]; then
                continue
            fi
            ftp_dele "$name" || true
            ;;
    esac
done <<< "$(ftp_list)"

echo ""
echo "============================================================"
echo "  Deploy abgeschlossen."
echo "============================================================"
