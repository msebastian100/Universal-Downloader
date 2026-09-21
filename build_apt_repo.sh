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
#   deb [signed-by=/etc/apt/trusted.gpg.d/universal-downloader.gpg] https://ppa.plertanix.de/apt stable main
#   sudo apt update && sudo apt install universal-downloader
#
# Zusätzlich bleibt das flache Layout (Packages/.deb im Root) für ältere Quellen mit „./“.

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
# Pool/dists nicht mit in den flachen Packages-Index scannen
rm -rf "$REPO_DIR/pool" "$REPO_DIR/dists"

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

# AppStream / DEP-11 – damit GNOME/Cinnamon „Software“ das Paket findet
echo "[INFO] Erzeuge AppStream-Metadaten (DEP-11)..."
python3 - <<'PY'
from pathlib import Path
import gzip, hashlib, shutil, tarfile, io, os

repo = Path(".")
root = Path("..")
icon_src_64 = root / "packaging/appstream/icons/64x64/universal-downloader.png"
icon_src_48 = root / "packaging/appstream/icons/48x48/universal-downloader.png"
dep11 = repo / "dep11"
if dep11.exists():
    shutil.rmtree(dep11)
dep11.mkdir()

# Versionsnummer aus Packages (höchste Version)
version = "0"
for block in Path("Packages").read_text(encoding="utf-8").split("\n\n"):
    for line in block.splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()

# Ubuntu-Software erwartet Icon-Namen {paket}_{id}.png IM TAR-ROOT
# (nicht 64x64/…, sonst landet die Datei in …/64x64/64x64/ und die App wird versteckt).
icon_name = "universal-downloader_de.plertanix.universal-downloader.png"
yml = f"""---
File: DEP-11
Version: '0.14'
Origin: plertanix
---
Type: desktop-application
ID: de.plertanix.universal-downloader
Package: universal-downloader
Name:
  C: Universal Downloader
  de: Universal Downloader
Summary:
  C: Downloader for music, audiobooks and videos
  de: Downloader für Musik, Hörbücher und Videos
Description:
  C: >-
    <p>Universal downloader for Deezer, Spotify, Audible, YouTube, ARD, ZDF, ORF
    and other sources.</p>
  de: >-
    <p>Universeller Downloader für Deezer, Spotify, Audible, YouTube, ARD, ZDF, ORF
    und weitere Quellen.</p>
Icon:
  cached:
  - name: {icon_name}
    width: 48
    height: 48
  - name: {icon_name}
    width: 64
    height: 64
  stock: universal-downloader
Categories:
- AudioVideo
- Audio
- Video
- Network
Keywords:
  C:
  - download
  - deezer
  - youtube
  - spotify
  - audible
  - ard
  - zdf
  - orf
Launchable:
  desktop-id:
  - universal-downloader.desktop
Provides:
  binaries:
  - universal-downloader
ProjectLicense: MIT
DeveloperName:
  C: PlerTanix
Url:
  homepage: https://github.com/msebastian100/Universal-Downloader
ContentRating:
  oars-1.1: {{}}
Releases:
- version: '{version}'
  type: stable
"""
# Unkomprimiert + .gz: apt matched den IndexTarget nur gegen den
# MetaKey ohne Suffix (…/Components-arm64.yml, …/icons-64x64.tar).
yml_bytes = yml.encode("utf-8")
for arch in ("amd64", "arm64"):
    raw = dep11 / f"Components-{arch}.yml"
    raw.write_bytes(yml_bytes)
    with gzip.open(str(raw) + ".gz", "wb", compresslevel=9) as fh:
        fh.write(yml_bytes)

def write_icon_tar(src: Path, size: int):
    if not src.is_file():
        return
    tar_path = dep11 / f"icons-{size}x{size}.tar"
    buf = io.BytesIO()
    data = src.read_bytes()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        info = tarfile.TarInfo(name=icon_name)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    tar_path.write_bytes(buf.getvalue())
    with gzip.open(str(tar_path) + ".gz", "wb", compresslevel=9) as fh:
        fh.write(tar_path.read_bytes())

write_icon_tar(icon_src_48, 48)
write_icon_tar(icon_src_64, 64)
print("[OK] DEP-11 geschrieben:", ", ".join(p.name for p in sorted(dep11.iterdir())))
PY

# Release-File mit Date und SHA256 (entfernt apt-Warnungen zu Hash/Date)
echo "[INFO] Erzeuge Release..."
sha_line() {
  local f="$1"
  local listed="$2"
  [ -f "$f" ] || return 0
  printf ' %s %s %s\n' "$(sha256sum -b "$f" | awk '{print $1}')" "$(stat -c %s "$f" 2>/dev/null || wc -c < "$f")" "$listed"
}
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
  sha_line Packages Packages
  sha_line Packages.gz Packages.gz
  # Pfade wie apt sie für ein Flat-Repo mit Component „.“ erwartet
  for f in dep11/Components-amd64.yml dep11/Components-amd64.yml.gz \
           dep11/Components-arm64.yml dep11/Components-arm64.yml.gz \
           dep11/icons-48x48.tar dep11/icons-48x48.tar.gz \
           dep11/icons-64x64.tar dep11/icons-64x64.tar.gz; do
    sha_line "$f" "./$f"
    sha_line "$f" "$f"
  done
} > Release

sign_release() {
  # Signiert Release im aktuellen Verzeichnis (Release.gpg + InRelease).
  local label="$1"
  if ! command -v gpg &>/dev/null; then
    echo "[Hinweis] gpg nicht installiert – $label wird nicht signiert."
    rm -f Release.gpg InRelease
    return 0
  fi
  SIGNING_KEY="${APT_SIGNING_KEY:-}"
  [ -z "$SIGNING_KEY" ] && SIGNING_KEY=$(gpg --list-secret-keys --with-colons 2>/dev/null | awk -F: '$1=="sec"{print $5;exit}')
  if [ -z "$SIGNING_KEY" ]; then
    echo "[Hinweis] Kein GPG-Schlüssel – $label ohne Release.gpg/InRelease."
    rm -f Release.gpg InRelease
    return 0
  fi
  rm -f Release.gpg InRelease
  if gpg -abs -u "$SIGNING_KEY" -o Release.gpg Release 2>/dev/null; then
    echo "[INFO] $label signiert (Release.gpg)."
    gpg --clearsign -u "$SIGNING_KEY" -o InRelease Release 2>/dev/null && echo "[INFO] $label InRelease erstellt."
    return 0
  fi
  echo "[WARNUNG] Signatur von $label fehlgeschlagen."
}

# Optional: Release mit GPG signieren → „Ign: ... Release.gpg“ und „Ign: ... InRelease“ verschwinden
sign_release "Flat-Release"
if [ -n "${SIGNING_KEY:-}" ]; then
  gpg --export --armor "$SIGNING_KEY" > repo-key.asc 2>/dev/null && echo "[INFO] Öffentlicher Schlüssel: apt-repo/repo-key.asc – nach https://ppa.plertanix.de/apt/ hochladen."
fi

# Standard-Debian-Layout: GNOME/Cinnamon „Software“ holt DEP-11 nur bei
# Component „main“ (nicht bei flachem „./“ – dort fehlt apt der flatMetaKey).
echo "[INFO] Erzeuge dists/stable/main (Suite + Component für AppStream)..."
POOL_REL="pool/main/u/${APP_NAME}"
rm -rf pool dists
mkdir -p "$POOL_REL"
for f in ${APP_NAME}_*_all.deb; do
  [ -f "$f" ] && cp "$f" "$POOL_REL/"
done
DIST_PKGS="Packages.dists"
sed "s|^Filename: |Filename: ${POOL_REL}/|" Packages > "$DIST_PKGS"
gzip -9c "$DIST_PKGS" > "${DIST_PKGS}.gz"
for arch in all amd64 arm64; do
  bin_dir="dists/stable/main/binary-${arch}"
  mkdir -p "$bin_dir"
  cp "$DIST_PKGS" "$bin_dir/Packages"
  cp "${DIST_PKGS}.gz" "$bin_dir/Packages.gz"
done
mkdir -p dists/stable/main/dep11
cp -a dep11/. dists/stable/main/dep11/
rm -f "$DIST_PKGS" "${DIST_PKGS}.gz"

{
  echo "Origin: Universal Downloader"
  echo "Label: Universal Downloader"
  echo "Suite: stable"
  echo "Codename: stable"
  echo "Architectures: amd64 arm64"
  echo "Components: main"
  echo "Description: Universal Downloader - APT Repository"
  echo "Date: $(LC_ALL=C date -u +"%a, %d %b %Y %H:%M:%S UTC")"
  echo "SHA256:"
  (
    cd dists/stable
    for f in main/binary-all/Packages main/binary-all/Packages.gz \
             main/binary-amd64/Packages main/binary-amd64/Packages.gz \
             main/binary-arm64/Packages main/binary-arm64/Packages.gz \
             main/dep11/Components-amd64.yml main/dep11/Components-amd64.yml.gz \
             main/dep11/Components-arm64.yml main/dep11/Components-arm64.yml.gz \
             main/dep11/icons-48x48.tar main/dep11/icons-48x48.tar.gz \
             main/dep11/icons-64x64.tar main/dep11/icons-64x64.tar.gz; do
      [ -f "$f" ] || continue
      printf ' %s %s %s\n' "$(sha256sum -b "$f" | awk '{print $1}')" "$(stat -c %s "$f" 2>/dev/null || wc -c < "$f")" "$f"
    done
  )
} > dists/stable/Release

(
  cd dists/stable
  sign_release "dists/stable/Release"
)

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
