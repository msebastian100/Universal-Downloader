#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erstellt zip_for_Windows.zip mit allem, was für Windows benötigt wird:
- Portable .exe (Universal Downloader)
- Installer (falls gebaut)
- Kurze Anleitung (README-Windows.txt)

Aufruf: python build_zip_windows.py
Optional: Zuerst build_windows.py und ggf. build_installer.py ausführen.
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Encoding-Fix für Windows
if sys.platform == "win32" or os.getenv("GITHUB_ACTIONS") == "true":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:
        pass


def get_version():
    """Liest die Versionsnummer aus version.py"""
    try:
        version_file = Path(__file__).parent / "version.py"
        if version_file.exists():
            content = version_file.read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"[WARNING] Versionsnummer nicht lesbar: {e}")
    return "0.0.0"


def ensure_exe(root: Path):
    """Stellt sicher, dass eine Windows-.exe in dist/ existiert (baut bei Bedarf)."""
    dist = root / "dist"
    versioned = list(dist.glob("universal-downloader_v*.exe")) if dist.exists() else []
    if versioned:
        print(f"[OK] Gefunden: {versioned[0].name}")
        return versioned[0]
    print("Keine .exe in dist/ gefunden. Starte build_windows.py ...")
    r = subprocess.run([sys.executable, "build_windows.py"], cwd=root)
    if r.returncode != 0:
        print("[FEHLER] build_windows.py ist fehlgeschlagen.")
        return None
    versioned = list((root / "dist").glob("universal-downloader_v*.exe"))
    return versioned[0] if versioned else None


def create_readme_windows(version: str) -> str:
    """Inhalt für README-Windows.txt im ZIP."""
    return f"""Universal Downloader – Windows (v{version})
============================================

PORTABLE NUTZUNG
----------------
  • universal-downloader_v{version}.exe starten – keine Installation nötig.
  • Beliebig verschieben (z. B. USB-Stick, eigener Ordner).

INSTALLATION (optional)
----------------------
  • UniversalDownloader_Setup_v{version}.exe ausführen.
  • Programm wird ins Startmenü eingetragen, optional Desktop/Taskleiste.
  • Deinstallieren über Startmenü: "Universal Downloader deinstallieren".

ANFORDERUNGEN
------------
  • Windows 10 oder neuer (64 Bit empfohlen).
  • Keine zusätzliche Software nötig – alles in der .exe enthalten.
"""


def main():
    root = Path(__file__).parent
    os.chdir(root)

    version = get_version()
    print(f"Version: {version}")
    print("Erstelle zip_for_Windows ...")

    exe_path = ensure_exe(root)
    if not exe_path:
        sys.exit(1)

    dist = root / "dist"
    dist.mkdir(exist_ok=True)

    # Installer optional einpacken (falls vorhanden)
    dist_installer = root / "dist_installer"
    setup_exe = dist_installer / f"UniversalDownloader_Setup_v{version}.exe" if dist_installer.exists() else None
    if setup_exe and not setup_exe.exists():
        setup_exe = None

    zip_name = f"zip_for_Windows_v{version}.zip"
    zip_path = dist / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Portable EXE
        zf.write(exe_path, exe_path.name)
        # Installer (falls vorhanden)
        if setup_exe:
            zf.write(setup_exe, setup_exe.name)
        # Anleitung
        readme = create_readme_windows(version)
        zf.writestr("README-Windows.txt", readme.encode("utf-8"))

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print("=" * 60)
    print("[OK] ZIP erstellt:")
    print(f"    {zip_path.absolute()}")
    print(f"    Größe: {size_mb:.2f} MB")
    print("=" * 60)
    if not setup_exe:
        print("[Hinweis] Installer nicht im ZIP (build_installer.py ausführen für Setup.exe).")


if __name__ == "__main__":
    main()
