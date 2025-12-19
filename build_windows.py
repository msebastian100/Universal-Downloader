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
        "--collect-all=yt_dlp",
        "--collect-all=PIL",
        "--collect-all=mutagen",
        "start.py"
    ]
    
    # Entferne leere Einträge
    pyinstaller_cmd = [x for x in pyinstaller_cmd if x]
    
    print(f"\nFühre aus: {' '.join(pyinstaller_cmd)}\n")
    
    try:
        result = subprocess.run(pyinstaller_cmd, check=True)
        print("\n" + "=" * 70)
        print("✓ Build erfolgreich!")
        print("=" * 70)
        print(f"\nDie .exe Datei befindet sich in: {dist_dir.absolute()}")
        print(f"Dateiname: UniversalDownloader.exe")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Build fehlgeschlagen: {e}")
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
