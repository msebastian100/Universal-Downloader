#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build-Script für Windows .exe mit PyInstaller
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Für PyInstaller spec-Datei
if __name__ != "__main__":
    import os

def check_pyinstaller():
    """Prüft ob PyInstaller installiert ist"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    """Installiert PyInstaller"""
    print("Installiere PyInstaller...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    print("✓ PyInstaller installiert")

def build_exe():
    """Erstellt die .exe Datei"""
    print("=" * 70)
    print("Erstelle Windows .exe Datei...")
    print("=" * 70)
    
    # Prüfe ob PyInstaller vorhanden ist
    if not check_pyinstaller():
        print("PyInstaller nicht gefunden. Installiere...")
        install_pyinstaller()
    
    # Erstelle Build-Verzeichnis
    build_dir = Path("build")
    dist_dir = Path("dist")
    
    # Lösche alte Builds
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    # Verwende .spec Datei falls vorhanden, sonst manuelle Parameter
    spec_file = Path("UniversalDownloader.spec")
    
    if spec_file.exists():
        print("Verwende UniversalDownloader.spec für Build...")
        pyinstaller_cmd = [
            sys.executable, "-m", "PyInstaller",
            "--clean",  # Bereinige Cache
            str(spec_file)
        ]
    else:
        print("Keine .spec Datei gefunden, verwende manuelle Parameter...")
        # PyInstaller-Befehle
        pyinstaller_cmd = [
            sys.executable, "-m", "PyInstaller",
            "--name=UniversalDownloader",
            "--onefile",
            "--windowed",  # Kein Konsolen-Fenster
            "--icon=icon.png" if Path("icon.png").exists() else "",
            "--add-data=icon.png;." if Path("icon.png").exists() else "",
            "--hidden-import=tkinter",
            "--hidden-import=PIL",
            "--hidden-import=mutagen",
            "--hidden-import=deezer",
            "--hidden-import=yt_dlp",
            "--hidden-import=requests",
            "--hidden-import=beautifulsoup4",
            "--hidden-import=selenium",
            "--hidden-import=audible",
            "--hidden-import=browser_cookie3",
            "--hidden-import=deezer_auth",
            "--hidden-import=deezer_downloader",
            "--hidden-import=spotify_downloader",
            "--hidden-import=video_downloader",
            "--hidden-import=audible_integration",
            "--hidden-import=updater",
            "--hidden-import=version",
            "--collect-all=yt_dlp",
            "--collect-all=PIL",
            "--collect-all=mutagen",
            "start.py"
        ]
        
        # Entferne leere Einträge
        pyinstaller_cmd = [x for x in pyinstaller_cmd if x]
    
    print(f"\nFühre aus: {' '.join(pyinstaller_cmd)}\n")
    
    try:
        result = subprocess.run(pyinstaller_cmd, check=True, capture_output=False)
        print("\n" + "=" * 70)
        print("✓ Build erfolgreich!")
        print("=" * 70)
        
        # Prüfe ob .exe erstellt wurde
        exe_path = dist_dir / "UniversalDownloader.exe"
        if exe_path.exists():
            print(f"\nDie .exe Datei befindet sich in: {dist_dir.absolute()}")
            print(f"Dateiname: UniversalDownloader.exe")
            print(f"Größe: {exe_path.stat().st_size / (1024*1024):.2f} MB")
            return True
        else:
            print(f"\n⚠ Warnung: .exe Datei nicht gefunden in {dist_dir}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build fehlgeschlagen: {e}")
        print(f"Returncode: {e.returncode}")
        if hasattr(e, 'stderr') and e.stderr:
            print(f"Fehlerausgabe: {e.stderr.decode()}")
        return False
    except Exception as e:
        print(f"\n✗ Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # In GitHub Actions keine interaktive Eingabe
    if os.getenv('GITHUB_ACTIONS') == 'true':
        # Automatisch fortfahren in CI/CD
        success = build_exe()
        sys.exit(0 if success else 1)
    elif sys.platform != "win32":
        print("⚠ Warnung: Dieses Script ist für Windows gedacht.")
        print("Sie können es trotzdem ausführen, aber die .exe wird nur auf Windows funktionieren.")
        response = input("Fortfahren? (j/n): ")
        if response.lower() != 'j':
            sys.exit(0)
    
    success = build_exe()
    sys.exit(0 if success else 1)
