#!/bin/bash
# GH-Update: GitHub-Release für die Version aus version.py (Tag + Push).
# Baut/lädt NICHT das APT-Repo. Dafür: ./rp-update.sh
#
# GitHub Actions (.github/workflows/build.yml) baut Windows/.deb/macOS-.dmg als Release-Assets,
# sobald der Tag vX.Y.Z existiert. Lokal gebaute dist/*.dmg werden mit gh hochgeladen.
#
# Nutzung: ./gh-update.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VERSION=$(python3 -c "from version import __version__; print(__version__)")
TAG="v${VERSION}"

echo "============================================================"
echo "  GH-Update  →  GitHub   (Tag $TAG)"
echo "============================================================"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
    echo "[FEHLER] Kein Git-Repository."
    exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[FEHLER] Es gibt uncommittete Änderungen. Erst committen, dann GH-Update."
    git status -sb
    exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo "[INFO] Tag $TAG existiert schon lokal."
else
    git tag -a "$TAG" -m "Release $TAG"
    echo "[INFO] Tag $TAG angelegt."
fi

echo "[INFO] Push nach origin (Branch + Tag)..."
git push origin HEAD
git push origin "$TAG"

if command -v gh >/dev/null 2>&1; then
    echo "[INFO] GitHub-Release (falls noch nicht vorhanden)..."
    gh release view "$TAG" >/dev/null 2>&1 || \
        gh release create "$TAG" --title "Release $TAG" --generate-notes
    shopt -s nullglob
    mac_dmgs=(
        dist/UniversalDownloader_"${VERSION}"_arm64.dmg
        dist/UniversalDownloader_"${VERSION}"_x86_64.dmg
    )
    if ((${#mac_dmgs[@]})); then
        echo "[INFO] Lade macOS-.dmg hoch: ${mac_dmgs[*]}"
        gh release upload "$TAG" "${mac_dmgs[@]}" --clobber
    fi
else
    echo "[Hinweis] gh CLI fehlt – Actions startet trotzdem durch den Tag-Push (inkl. macOS-.dmg)."
fi

echo
echo "[OK] GH-Update angestoßen. APT/FTP extra mit: ./rp-update.sh"
