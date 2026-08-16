#!/bin/bash
# Erzeugt aus dem gebauten .deb ein APT-Repository (ein Verzeichnis mit Packages.gz).
# Dieses Verzeichnis auf https://ppa.plertanix.de/apt/ bereitstellen.
#
# Ablauf:
#   1. ./build_linux.sh   (falls noch nicht geschehen)
#   2. ./build_apt_repo.sh
#   3. Inhalt von apt-repo/ auf den Server kopieren (z.B. nach /var/www/apt/)
#
# Nutzer fügen dann hinzu:
#   deb [trusted=yes] https://ppa.plertanix.de/apt/ ./
#   sudo apt update && sudo apt install universal-downloader

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

REPO_DIR="${SCRIPT_DIR}/apt-repo"
DEB_SOURCE_DIR="${SCRIPT_DIR}/deb_build"

APP_NAME="universal-downloader"

echo "============================================================"
echo "  APT-Repository vorbereiten (für eigene Domain)"
echo "============================================================"
echo ""

# Prüfen ob .deb existiert (neueste zuerst nach Änderungszeit, falls mehrere)
DEB_FILE=$(ls -t "$DEB_SOURCE_DIR"/${APP_NAME}_*_all.deb 2>/dev/null | head -1)
if [ -z "$DEB_FILE" ] || [ ! -f "$DEB_FILE" ]; then
    echo "[FEHLER] Keine .deb gefunden. Zuerst bauen: ./build_linux.sh"
    exit 1
fi

mkdir -p "$REPO_DIR"
cp "$DEB_FILE" "$REPO_DIR/"

# Packages-Index erzeugen (für APT) – sowohl Packages als auch Packages.gz
# Filename: ./file.deb → Filename: file.deb (manche APT-Setups haben mit ./ Probleme)
echo "[INFO] Erzeuge Packages-Index..."
cd "$REPO_DIR"
dpkg-scanpackages . /dev/null 2>/dev/null | sed 's|^Filename: \./|Filename: |' > Packages
gzip -9c Packages > Packages.gz

# Release-File mit Date und SHA256 (entfernt apt-Warnungen zu Hash/Date)
echo "[INFO] Erzeuge Release..."
{
  echo "Origin: Universal Downloader"
  echo "Label: Universal Downloader"
  echo "Suite: ./"
  echo "Codename: ./"
  echo "Architectures: all"
  echo "Components: ."
  echo "Description: Universal Downloader - APT Repository"
  # RFC 2822, UTC – erforderlich damit apt den Date-Eintrag akzeptiert (kein "Ungültiger Date-Eintrag")
  echo "Date: $(LC_ALL=C date -u +"%a, %d %b %Y %H:%M:%S UTC")"
  echo "SHA256:"
  printf ' %s %s %s\n' "$(sha256sum -b Packages    | awk '{print $1}')" "$(stat -c %s Packages 2>/dev/null || wc -c < Packages)" "Packages"
  printf ' %s %s %s\n' "$(sha256sum -b Packages.gz | awk '{print $1}')" "$(stat -c %s Packages.gz 2>/dev/null || wc -c < Packages.gz)" "Packages.gz"
} > Release

# Optional: Release mit GPG signieren → „Ign: ... Release.gpg“ und „Ign: ... InRelease“ verschwinden
if command -v gpg &>/dev/null; then
  SIGNING_KEY="${APT_SIGNING_KEY:-}"
  [ -z "$SIGNING_KEY" ] && SIGNING_KEY=$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1=="sec"{print $5;exit}')
  if [ -n "$SIGNING_KEY" ]; then
    if gpg -abs -u "$SIGNING_KEY" -o Release.gpg Release 2>/dev/null; then
      echo "[INFO] Release signiert (Release.gpg)."
      gpg --clearsign -u "$SIGNING_KEY" -o InRelease Release 2>/dev/null && echo "[INFO] InRelease erstellt (clearsigned)."
      gpg --export --armor "$SIGNING_KEY" > repo-key.asc 2>/dev/null && echo "[INFO] Öffentlicher Schlüssel: apt-repo/repo-key.asc – nach https://ppa.plertanix.de/apt/ hochladen."
    fi
  else
    echo "[Hinweis] Kein GPG-Schlüssel – Release.gpg/InRelease nicht erstellt. Deploy löscht alte InRelease auf dem Server; apt nutzt dann Release ([trusted=yes])."
  fi
else
  echo "[Hinweis] gpg nicht installiert – Release wird nicht signiert."
fi

cd "$SCRIPT_DIR"

echo ""
echo "[OK] Repository liegt in: $REPO_DIR"
echo ""
echo "Inhalt:"
ls -la "$REPO_DIR"
echo ""
echo "Nächste Schritte:"
echo "  1. Ordner apt-repo/ auf deinen Server kopieren (z.B. rsync oder FTP)."
echo "  2. Inhalt von apt-repo/ nach https://ppa.plertanix.de/apt/ hochladen."
echo "  3. Nutzer-Anleitung: siehe APT_REPO.md"
echo ""
