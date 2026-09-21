#!/bin/bash
# Erzeugt aus den gebauten .deb-Dateien ein APT-Repository (Packages.gz + Release).
# Dieses Verzeichnis auf https://ppa.plertanix.de/apt/ bereitstellen.
#
# Es bleiben die aktuelle und die vorherige Version im Index (Fallback, falls
# die neue Version Probleme macht): apt install universal-downloader=X.Y.Z
#
# Ablauf:
#   1. ./build_linux.sh   (falls noch nicht geschehen)
#   2. ./build_apt_repo.sh
#   3. Inhalt von apt-repo/ auf den Server kopieren (z.B. nach /var/www/apt/)
#
# Nutzer fügen dann hinzu:
#   deb [signed-by=/etc/apt/trusted.gpg.d/universal-downloader.gpg] https://ppa.plertanix.de/apt/ ./
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

deb_version() {
    # universal-downloader_2.1.14_all.deb → 2.1.14
    local n
    n="$(basename "$1" .deb)"
    n="${n#${APP_NAME}_}"
    n="${n%_all}"
    printf '%s\n' "$n"
}

mkdir -p "$REPO_DIR"

# Kandidaten: frisch gebaut (deb_build) plus bereits im Repo (vorherige Version)
VERSIONS=$( {
    ls -1 "$DEB_SOURCE_DIR"/${APP_NAME}_*_all.deb 2>/dev/null || true
    ls -1 "$REPO_DIR"/${APP_NAME}_*_all.deb 2>/dev/null || true
} | while IFS= read -r f; do
    [ -f "$f" ] || continue
    deb_version "$f"
done | sort -uV )

if [ -z "$VERSIONS" ]; then
    echo "[FEHLER] Keine .deb gefunden. Zuerst bauen: ./build_linux.sh"
    exit 1
fi

# Aktuelle + vorherige Version (höchstens zwei)
KEEP_VERS=$(printf '%s\n' "$VERSIONS" | tail -2)
echo "[INFO] Versionen im Repo (aktuell + Fallback):"
printf '%s\n' "$KEEP_VERS" | sed 's/^/  - /'

# Alte .deb aus apt-repo entfernen, Keep-Dateien bereitstellen (deb_build hat Vorrang)
for f in "$REPO_DIR"/${APP_NAME}_*_all.deb; do
    [ -f "$f" ] || continue
    ver="$(deb_version "$f")"
    if ! printf '%s\n' "$KEEP_VERS" | grep -Fxq "$ver"; then
        echo "[INFO] Entferne ältere lokale .deb: $(basename "$f")"
        rm -f "$f"
    fi
done
while IFS= read -r ver; do
    [ -n "$ver" ] || continue
    src=""
    [ -f "$DEB_SOURCE_DIR/${APP_NAME}_${ver}_all.deb" ] && src="$DEB_SOURCE_DIR/${APP_NAME}_${ver}_all.deb"
    [ -z "$src" ] && [ -f "$REPO_DIR/${APP_NAME}_${ver}_all.deb" ] && src="$REPO_DIR/${APP_NAME}_${ver}_all.deb"
    if [ -n "$src" ]; then
        cp "$src" "$REPO_DIR/"
    else
        echo "[FEHLER] .deb für Version $ver nicht gefunden."
        exit 1
    fi
done <<< "$KEEP_VERS"

# Packages-Index erzeugen (für APT) – sowohl Packages als auch Packages.gz
# Filename: ./file.deb → Filename: file.deb (manche APT-Setups haben mit ./ Probleme)
echo "[INFO] Erzeuge Packages-Index..."
cd "$REPO_DIR"
if command -v dpkg-scanpackages >/dev/null 2>&1; then
  dpkg-scanpackages -m . /dev/null 2>/dev/null | sed 's|^Filename: \./|Filename: |' > Packages
else
  echo "[Hinweis] dpkg-scanpackages fehlt – erzeuge Packages per Fallback (ar/zstd/tar)."
  python3 - <<'PY'
import hashlib, io, os, struct, subprocess, tarfile
from pathlib import Path

repo = Path(".")
entries = []

def read_ar_members(data: bytes):
    assert data[:8] == b"!<arch>\n", "kein ar-Archiv"
    off = 8
    while off + 60 <= len(data):
        hdr = data[off:off + 60]
        off += 60
        name = hdr[0:16].decode("ascii", "replace").strip()
        if name.endswith("/"):
            name = name[:-1]
        size = int(hdr[48:58].decode("ascii").strip())
        body = data[off:off + size]
        off += size + (size % 2)
        yield name, body

def control_from_deb(path: Path) -> str:
    data = path.read_bytes()
    for name, body in read_ar_members(data):
        if not name.startswith("control.tar"):
            continue
        raw = body
        if name.endswith(".zst") or name.endswith(".zstd"):
            raw = subprocess.check_output(["zstd", "-d", "-c"], input=body)
            mode = "r:"
        elif name.endswith(".xz"):
            mode = "r:xz"
        elif name.endswith(".gz"):
            mode = "r:gz"
        else:
            mode = "r:"
        with tarfile.open(fileobj=io.BytesIO(raw), mode=mode) as tf:
            for m in tf.getmembers():
                base = m.name.split("/")[-1]
                if base == "control" and m.isfile():
                    return tf.extractfile(m).read().decode("utf-8", "replace")
    raise RuntimeError(f"Kein control in {path.name}")

for deb in sorted(repo.glob("*.deb")):
    ctrl = control_from_deb(deb).strip() + "\n"
    size = deb.stat().st_size
    md5 = hashlib.md5(deb.read_bytes()).hexdigest()
    sha1 = hashlib.sha1(deb.read_bytes()).hexdigest()
    sha256 = hashlib.sha256(deb.read_bytes()).hexdigest()
    # bestehende Hash-Zeilen entfernen und neu setzen
    lines = []
    for line in ctrl.splitlines():
        if line.startswith(("MD5sum:", "SHA1:", "SHA256:", "Size:", "Filename:")):
            continue
        lines.append(line)
    while lines and not lines[-1].strip():
        lines.pop()
    lines.append(f"Filename: {deb.name}")
    lines.append(f"Size: {size}")
    lines.append(f"MD5sum: {md5}")
    lines.append(f"SHA1: {sha1}")
    lines.append(f"SHA256: {sha256}")
    entries.append("\n".join(lines) + "\n")

Path("Packages").write_text("\n".join(entries) + ("\n" if entries else ""), encoding="utf-8")
print(f"[OK] Packages für {len(entries)} Paket(e) geschrieben.")
PY
fi
if [ ! -s Packages ]; then
  echo "[FEHLER] Packages-Index ist leer."
  exit 1
fi
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
    rm -f Release.gpg InRelease
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
  rm -f Release.gpg InRelease
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
