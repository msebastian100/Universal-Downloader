#!/bin/bash
# =============================================================================
# Universal Downloader – Installation über APT-Repository (Linux Mint / Ubuntu / Debian)
#
# - Importiert den öffentlichen Repo-Schlüssel (ohne sudo in der Pipe)
# - Trägt die APT-Quelle ein
# - Fallback ohne Schlüssel ([trusted=yes]), falls Key/SSL scheitert
# - Schreibt bei Fehlern ein Fehler-Log
#
# Nutzung:
#   chmod +x install_apt_linux.sh
#   sudo ./install_apt_linux.sh
# =============================================================================

set -u

REPO_BASE_URL="https://ppa.plertanix.de/apt"
KEY_URL="${REPO_BASE_URL}/repo-key.asc"
KEY_TMP="/tmp/universal-downloader-repo-key.asc"
KEY_DEST="/etc/apt/trusted.gpg.d/universal-downloader.gpg"
LIST_DEST="/etc/apt/sources.list.d/universal-downloader.list"
PKG_NAME="universal-downloader"

SCRIPT_NAME="$(basename "$0")"
STAMP="$(date +%Y-%m-%d_%H-%M-%S 2>/dev/null || date +%Y-%m-%d)"
# Log: bevorzugt /var/log (root), sonst /tmp, sonst aktuelles Verzeichnis
if [ -w /var/log ] 2>/dev/null; then
    LOG_DIR="/var/log"
elif [ -w /tmp ] 2>/dev/null; then
    LOG_DIR="/tmp"
else
    LOG_DIR="$(pwd)"
fi
LOG_FILE="${LOG_DIR}/universal-downloader-install_${STAMP}.log"
ERROR_LOG="${LOG_DIR}/universal-downloader-install_ERROR_${STAMP}.log"

USED_TRUSTED_YES=0
HAD_ERROR=0

log() {
    local msg="$*"
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)"
    echo "[$ts] $msg" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$ts] $msg"
}

log_err() {
    local msg="$*"
    HAD_ERROR=1
    local ts
    ts="$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)"
    echo "[$ts] [FEHLER] $msg" | tee -a "$LOG_FILE" "$ERROR_LOG" 2>/dev/null || echo "[$ts] [FEHLER] $msg"
}

run_logged() {
    # Befehl ausführen, stdout+stderr ins Log; Exit-Code zurückgeben
    local desc="$1"
    shift
    log "→ $desc: $*"
    if "$@" >>"$LOG_FILE" 2>&1; then
        log "  OK: $desc"
        return 0
    else
        local rc=$?
        log_err "$desc fehlgeschlagen (Exit $rc). Details in $LOG_FILE"
        return "$rc"
    fi
}

finish_with_error() {
    local summary="$1"
    log_err "$summary"
    {
        echo "============================================================"
        echo "Universal Downloader – Installationsfehler"
        echo "Zeit: $(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date)"
        echo "Zusammenfassung: $summary"
        echo "Vollständiges Log: $LOG_FILE"
        echo "Dieses Fehler-Log: $ERROR_LOG"
        echo "============================================================"
        echo ""
        echo "Letzte Log-Zeilen:"
        tail -n 40 "$LOG_FILE" 2>/dev/null || true
    } >>"$ERROR_LOG" 2>/dev/null || true
    echo ""
    echo "❌ Installation fehlgeschlagen."
    echo "   Fehler-Log: $ERROR_LOG"
    echo "   Detail-Log: $LOG_FILE"
    exit 1
}

download_file() {
    local url="$1"
    local out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fL --connect-timeout 20 --max-time 120 -o "$out" "$url"
        return $?
    fi
    if command -v wget >/dev/null 2>&1; then
        wget -q -O "$out" --timeout=20 "$url"
        return $?
    fi
    return 127
}

is_pgp_ascii_key() {
    local f="$1"
    [ -s "$f" ] || return 1
    grep -q "BEGIN PGP PUBLIC KEY BLOCK" "$f" 2>/dev/null
}

write_sources_signed() {
    echo "deb [signed-by=${KEY_DEST}] ${REPO_BASE_URL}/ ./" >"$LIST_DEST"
}

write_sources_trusted() {
    echo "deb [trusted=yes] ${REPO_BASE_URL}/ ./" >"$LIST_DEST"
    USED_TRUSTED_YES=1
}

# ---------- Start ----------
umask 022
touch "$LOG_FILE" 2>/dev/null || true
: >"$ERROR_LOG" 2>/dev/null || true

log "============================================================"
log "Universal Downloader – APT-Installation"
log "Skript: $SCRIPT_NAME"
log "Log: $LOG_FILE"
log "Fehler-Log (bei Problemen): $ERROR_LOG"
log "============================================================"

# Root nötig für apt/gpg-Zielpfade
if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo ./$SCRIPT_NAME"
    # Auch ohne Root zumindest Hinweis loggen, falls Log schreibbar
    log_err "Nicht als root gestartet. Bitte: sudo ./$SCRIPT_NAME"
    echo "Fehler-Log: $ERROR_LOG"
    exit 1
fi

# Distribution grob prüfen
if [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    log "System: ${PRETTY_NAME:-$NAME $VERSION_ID}"
else
    log "System: $(uname -a)"
fi

if ! command -v apt-get >/dev/null 2>&1; then
    finish_with_error "apt-get nicht gefunden – dieses Skript ist für Debian/Ubuntu/Linux Mint."
fi

# Hilfswerkzeuge sicherstellen (gnupg, curl/wget, ca-certificates)
log "Prüfe Hilfspakete (ca-certificates, gnupg, curl)…"
export DEBIAN_FRONTEND=noninteractive
if ! run_logged "apt-get update (Vorbereitung)" apt-get update -y; then
    log "Warnung: apt-get update vorab fehlgeschlagen – versuche trotzdem weiter."
fi
MISSING_HELPERS=()
command -v gpg >/dev/null 2>&1 || MISSING_HELPERS+=(gnupg)
command -v curl >/dev/null 2>&1 || command -v wget >/dev/null 2>&1 || MISSING_HELPERS+=(curl)
dpkg -s ca-certificates >/dev/null 2>&1 || MISSING_HELPERS+=(ca-certificates)
if [ "${#MISSING_HELPERS[@]}" -gt 0 ]; then
    if ! run_logged "Hilfspakete installieren (${MISSING_HELPERS[*]})" \
        apt-get install -y "${MISSING_HELPERS[@]}"; then
        finish_with_error "Konnte Hilfspakete nicht installieren: ${MISSING_HELPERS[*]}"
    fi
fi

# ---------- Schlüssel ----------
KEY_OK=0
log "Lade öffentlichen Schlüssel: $KEY_URL"
rm -f "$KEY_TMP" 2>/dev/null || true

if download_file "$KEY_URL" "$KEY_TMP"; then
    log "Schlüsseldatei gespeichert: $KEY_TMP ($(wc -c <"$KEY_TMP" 2>/dev/null || echo '?') Bytes)"
    if is_pgp_ascii_key "$KEY_TMP"; then
        log "Schlüssel sieht gültig aus (BEGIN PGP PUBLIC KEY BLOCK)."
        # Wichtig: NICHT „curl | sudo gpg“ – sudo fragt sonst Passwort aus der Pipe
        if gpg --dearmor -o "$KEY_DEST" "$KEY_TMP" >>"$LOG_FILE" 2>&1; then
            chmod 644 "$KEY_DEST" 2>/dev/null || true
            log "Schlüssel installiert: $KEY_DEST"
            KEY_OK=1
        else
            log_err "gpg --dearmor fehlgeschlagen."
            head -n 5 "$KEY_TMP" >>"$ERROR_LOG" 2>/dev/null || true
        fi
    else
        log_err "Heruntergeladene Datei ist kein gültiger OpenPGP-Schlüssel."
        log "Erste Zeilen der Datei:"
        head -n 8 "$KEY_TMP" 2>/dev/null | tee -a "$LOG_FILE" "$ERROR_LOG" || true
    fi
else
    log_err "Download des Schlüssels fehlgeschlagen (SSL/Netz/404?). URL: $KEY_URL"
fi

# ---------- Quellenliste ----------
if [ "$KEY_OK" -eq 1 ]; then
    log "Trage APT-Quelle mit signed-by ein…"
    write_sources_signed
else
    log "Fallback: APT-Quelle ohne Schlüsselprüfung ([trusted=yes])…"
    log "  (Nur nutzen, wenn Sie der Quelle ${REPO_BASE_URL} vertrauen.)"
    write_sources_trusted
fi
chmod 644 "$LIST_DEST" 2>/dev/null || true
log "Quellenliste: $LIST_DEST"
log "  Inhalt: $(tr -d '\n' <"$LIST_DEST" 2>/dev/null || true)"

# ---------- apt update + ggf. Fallback ----------
if ! run_logged "apt-get update" apt-get update -y; then
    if [ "$USED_TRUSTED_YES" -eq 0 ]; then
        log "apt update mit Schlüssel fehlgeschlagen – wechsle auf [trusted=yes]…"
        write_sources_trusted
        log "  Neue Liste: $(tr -d '\n' <"$LIST_DEST" 2>/dev/null || true)"
        if ! run_logged "apt-get update (Fallback trusted=yes)" apt-get update -y; then
            finish_with_error "apt-get update fehlgeschlagen (auch mit trusted=yes). Netz/SSL/Repo prüfen."
        fi
    else
        finish_with_error "apt-get update fehlgeschlagen. Netz/SSL/Repo prüfen: $REPO_BASE_URL/"
    fi
fi

# ---------- Paket installieren ----------
if dpkg -s "$PKG_NAME" >/dev/null 2>&1; then
    log "Paket $PKG_NAME ist bereits installiert – Update/Neuinstallation…"
    if ! run_logged "apt-get install --only-upgrade / reinstall" \
        apt-get install -y --reinstall "$PKG_NAME"; then
        # manchen Systemen fehlt --reinstall-Kombi; Fallback upgrade
        if ! run_logged "apt-get install (Upgrade)" apt-get install -y "$PKG_NAME"; then
            finish_with_error "Installation/Update von $PKG_NAME fehlgeschlagen."
        fi
    fi
else
    if ! run_logged "apt-get install $PKG_NAME" apt-get install -y "$PKG_NAME"; then
        finish_with_error "Installation von $PKG_NAME fehlgeschlagen."
    fi
fi

# ---------- Erfolg ----------
VER="$(dpkg-query -W -f='${Version}' "$PKG_NAME" 2>/dev/null || echo 'unbekannt')"
log "============================================================"
log "✓ Installation erfolgreich: $PKG_NAME Version $VER"
if [ "$USED_TRUSTED_YES" -eq 1 ]; then
    log "Hinweis: Repository läuft mit [trusted=yes] (ohne Schlüsselverifikation)."
fi
log "Start: Menüeintrag „Universal Downloader“ oder: universal-downloader"
log "Updates: sudo apt update && sudo apt install --only-upgrade $PKG_NAME"
log "Log: $LOG_FILE"
if [ "$HAD_ERROR" -eq 1 ]; then
    log "Es gab Zwischenfehler (Fallback genutzt). Fehler-Log: $ERROR_LOG"
else
    # Kein Fehler → leeres Fehler-Log entfernen
    rm -f "$ERROR_LOG" 2>/dev/null || true
fi
log "============================================================"

echo ""
echo "✓ Universal Downloader ist installiert (Version $VER)."
echo "  Details: $LOG_FILE"
if [ "$USED_TRUSTED_YES" -eq 1 ]; then
    echo "  Hinweis: Quelle ohne Schlüsselprüfung ([trusted=yes])."
fi
exit 0
