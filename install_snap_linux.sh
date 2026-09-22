#!/bin/bash
# =============================================================================
# Universal Downloader – Installation über Snap Store (Linux Mint / Ubuntu)
#
# - Entfernt die Linux-Mint-Sperre für Snap (nosnap.pref), falls vorhanden
# - Installiert snapd
# - Installiert universal-downloader aus latest/stable
#
# Nutzung:
#   chmod +x install_snap_linux.sh
#   sudo ./install_snap_linux.sh
# =============================================================================

set -u

SNAP_NAME="universal-downloader"
NOSNAP_PREF="/etc/apt/preferences.d/nosnap.pref"

SCRIPT_NAME="$(basename "$0")"
STAMP="$(date +%Y-%m-%d_%H-%M-%S 2>/dev/null || date +%Y-%m-%d)"
if [ -w /var/log ] 2>/dev/null; then
    LOG_DIR="/var/log"
elif [ -w /tmp ] 2>/dev/null; then
    LOG_DIR="/tmp"
else
    LOG_DIR="$(pwd)"
fi
LOG_FILE="${LOG_DIR}/universal-downloader-snap-install_${STAMP}.log"
ERROR_LOG="${LOG_DIR}/universal-downloader-snap-install_ERROR_${STAMP}.log"

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

# snap braucht ein Terminal für den Fortschrittsbalken.
# Umleitung ins Log wirkt wie „hängt“.
run_snap_visible() {
    local desc="$1"
    shift
    log "→ $desc"
    log "  Hinweis: Beim ersten Mal lädt Snap Abhängigkeiten (oft 200–400 MB)."
    log "  Das kann mehrere Minuten dauern – Fortschritt erscheint unten."
    echo ""
    if "$@"; then
        echo ""
        log "  OK: $desc"
        return 0
    else
        local rc=$?
        echo ""
        log_err "$desc fehlgeschlagen (Exit $rc)."
        return "$rc"
    fi
}

finish_with_error() {
    local summary="$1"
    log_err "$summary"
    {
        echo "============================================================"
        echo "Universal Downloader – Snap-Installationsfehler"
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

# ---------- Start ----------
umask 022
touch "$LOG_FILE" 2>/dev/null || true
: >"$ERROR_LOG" 2>/dev/null || true

log "============================================================"
log "Universal Downloader – Snap-Installation"
log "Skript: $SCRIPT_NAME"
log "Log: $LOG_FILE"
log "============================================================"

if [ "$(id -u)" -ne 0 ]; then
    echo "Bitte mit sudo ausführen:"
    echo "  sudo ./$SCRIPT_NAME"
    log_err "Nicht als root gestartet. Bitte: sudo ./$SCRIPT_NAME"
    echo "Fehler-Log: $ERROR_LOG"
    exit 1
fi

if [ -f /etc/os-release ]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    log "System: ${PRETTY_NAME:-$NAME $VERSION_ID}"
else
    log "System: $(uname -a)"
fi
log "Architektur: $(uname -m)"

if ! command -v apt-get >/dev/null 2>&1; then
    finish_with_error "apt-get nicht gefunden – dieses Skript ist für Debian/Ubuntu/Linux Mint."
fi

export DEBIAN_FRONTEND=noninteractive

# Linux Mint blockiert Snap standardmäßig
if [ -f "$NOSNAP_PREF" ]; then
    log "Linux-Mint-Snap-Sperre gefunden – entferne $NOSNAP_PREF"
    if ! run_logged "nosnap.pref entfernen" rm -f "$NOSNAP_PREF"; then
        finish_with_error "Konnte $NOSNAP_PREF nicht entfernen."
    fi
else
    log "Keine nosnap.pref vorhanden – Snap ist nicht durch Mint gesperrt."
fi

if ! run_logged "apt-get update" apt-get update -y; then
    finish_with_error "apt-get update fehlgeschlagen."
fi

if dpkg -s snapd >/dev/null 2>&1; then
    log "snapd ist bereits installiert."
else
    if ! run_logged "apt-get install snapd" apt-get install -y snapd; then
        finish_with_error "Installation von snapd fehlgeschlagen."
    fi
fi

run_logged "snapd.socket aktivieren" systemctl enable --now snapd.socket || true
run_logged "snapd starten" systemctl enable --now snapd || true

if ! command -v snap >/dev/null 2>&1; then
    finish_with_error "Befehl snap nicht gefunden, obwohl snapd installiert sein sollte."
fi

# Erste Nutzung: Seed abwarten, sonst schlägt snap install oft fehl
if ! run_logged "snap seed abwarten" snap wait system seed.loaded; then
    log "Warnung: snap wait system seed.loaded fehlgeschlagen – versuche trotzdem weiter."
fi

if snap list "$SNAP_NAME" >/dev/null 2>&1; then
    log "$SNAP_NAME ist bereits installiert – aktualisiere aus latest/stable…"
    if ! run_snap_visible "snap refresh $SNAP_NAME" snap refresh "$SNAP_NAME"; then
        log "Warnung: refresh fehlgeschlagen – versuche Neuinstallation."
        if ! run_snap_visible "snap install $SNAP_NAME" snap install "$SNAP_NAME"; then
            finish_with_error "Konnte $SNAP_NAME nicht aktualisieren oder installieren."
        fi
    fi
else
    if ! run_snap_visible "snap install $SNAP_NAME" snap install "$SNAP_NAME"; then
        finish_with_error "Installation von $SNAP_NAME aus dem Snap Store fehlgeschlagen."
    fi
fi

install_menu_shortcut() {
    # Linux Mint / Cinnamon liest /var/lib/snapd/desktop oft nicht
    # (XDG_DATA_DIRS ohne Snap-Pfad). Deshalb extra .desktop + Icon.
    local snap_desktop="/var/lib/snapd/desktop/applications/${SNAP_NAME}_${SNAP_NAME}.desktop"
    local snap_icon="/snap/${SNAP_NAME}/current/meta/gui/${SNAP_NAME}.png"
    local menu_desktop="/usr/share/applications/${SNAP_NAME}.desktop"
    local menu_icon="/usr/share/pixmaps/${SNAP_NAME}.png"
    local real_user="${SUDO_USER:-}"
    local real_home=""
    local desktop_dir=""

    log "Lege Startmenü-Verknüpfung an…"

    if [ -f "$snap_icon" ]; then
        install -d /usr/share/pixmaps
        cp -f "$snap_icon" "$menu_icon"
        chmod 644 "$menu_icon"
        log "  Icon: $menu_icon"
    else
        log "  Warnung: Snap-Icon nicht gefunden ($snap_icon)"
        menu_icon="${SNAP_NAME}"
    fi

    cat >"$menu_desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Universal Downloader
Name[de]=Universal Downloader
Comment=Downloader for music, audiobooks and videos
Comment[de]=Downloader für Musik, Hörbücher und Videos
Exec=/snap/bin/${SNAP_NAME}
Icon=${menu_icon}
Terminal=false
Categories=AudioVideo;Audio;Video;Network;Utility;
Keywords=download;music;video;deezer;youtube;ard;zdf;orf;audible;
StartupNotify=true
StartupWMClass=Tk
EOF
    chmod 644 "$menu_desktop"
    log "  Menüeintrag: $menu_desktop"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
    fi

    if [ -n "$real_user" ] && [ "$real_user" != "root" ]; then
        real_home="$(getent passwd "$real_user" | cut -d: -f6)"
        if [ -n "$real_home" ] && [ -d "$real_home" ]; then
            install -d -o "$real_user" -g "$real_user" "$real_home/.local/share/applications"
            cp -f "$menu_desktop" "$real_home/.local/share/applications/${SNAP_NAME}.desktop"
            chown "$real_user:$real_user" "$real_home/.local/share/applications/${SNAP_NAME}.desktop"
            chmod 644 "$real_home/.local/share/applications/${SNAP_NAME}.desktop"
            log "  Benutzer-Menü: $real_home/.local/share/applications/${SNAP_NAME}.desktop"

            if [ -n "${SUDO_UID:-}" ]; then
                desktop_dir="$(sudo -u "$real_user" -H xdg-user-dir DESKTOP 2>/dev/null || true)"
            fi
            if [ -z "$desktop_dir" ] || [ ! -d "$desktop_dir" ]; then
                if [ -d "$real_home/Schreibtisch" ]; then
                    desktop_dir="$real_home/Schreibtisch"
                elif [ -d "$real_home/Desktop" ]; then
                    desktop_dir="$real_home/Desktop"
                fi
            fi
            if [ -n "$desktop_dir" ] && [ -d "$desktop_dir" ]; then
                cp -f "$menu_desktop" "$desktop_dir/${SNAP_NAME}.desktop"
                chown "$real_user:$real_user" "$desktop_dir/${SNAP_NAME}.desktop"
                chmod 755 "$desktop_dir/${SNAP_NAME}.desktop"
                if [ -n "${SUDO_UID:-}" ] && [ -S "/run/user/${SUDO_UID}/bus" ]; then
                    sudo -u "$real_user" \
                        env DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${SUDO_UID}/bus" \
                        gio set "$desktop_dir/${SNAP_NAME}.desktop" metadata::trusted true >/dev/null 2>&1 || true
                fi
                log "  Desktop: $desktop_dir/${SNAP_NAME}.desktop"
            fi
        fi
    fi
}

install_menu_shortcut

VER="$(snap list "$SNAP_NAME" 2>/dev/null | awk 'NR==2 {print $2}')"
REV="$(snap list "$SNAP_NAME" 2>/dev/null | awk 'NR==2 {print $3}')"
log "============================================================"
log "✓ Installation erfolgreich: $SNAP_NAME ${VER:-?} (Rev. ${REV:-?})"
log "Start: Menüeintrag „Universal Downloader“ oder: universal-downloader"
log "Updates: sudo snap refresh $SNAP_NAME"
log "Log: $LOG_FILE"
log "============================================================"

if [ "$HAD_ERROR" -eq 0 ]; then
    rm -f "$ERROR_LOG" 2>/dev/null || true
fi

echo ""
echo "✓ Universal Downloader (Snap) ist installiert (Version ${VER:-?}, Rev. ${REV:-?})."
echo "  Start: universal-downloader"
echo "  Details: $LOG_FILE"
exit 0
