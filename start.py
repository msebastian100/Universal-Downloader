#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startskript für Universal Downloader
Startet die GUI-Anwendung
"""

import sys
import os

# Füge das aktuelle Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies_quick():
    """Schnelle Prüfung der wichtigsten Abhängigkeiten"""
    missing = []
    
    # Prüfe Python-Pakete
    try:
        import requests
    except ImportError:
        missing.append("requests")
    
    try:
        import yt_dlp
    except ImportError:
        missing.append("yt-dlp")
    
    # Prüfe System-Befehle
    import subprocess
    try:
        subprocess.run(['yt-dlp', '--version'], capture_output=True, timeout=2, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        missing.append("yt-dlp (System)")
    
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        missing.append("ffmpeg")
    
    return missing

def install_ffmpeg_if_missing():
    """Versucht ffmpeg automatisch zu installieren falls es fehlt"""
    import subprocess
    import platform
    
    # Prüfe ob ffmpeg vorhanden ist
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2, check=True)
        return True  # Bereits installiert
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # Versuche Installation
    system = platform.system()
    print("⚠ ffmpeg nicht gefunden - versuche automatische Installation...")
    
    if system == 'Linux':
        # Prüfe verschiedene Paket-Manager
        if os.path.exists('/usr/bin/apt-get'):
            print("  Installiere ffmpeg über apt-get...")
            try:
                subprocess.run(['sudo', 'apt-get', 'update'], check=True, timeout=60)
                subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], check=True, timeout=120)
                print("✓ ffmpeg erfolgreich installiert")
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                print("❌ Automatische Installation fehlgeschlagen")
                return False
    elif system == 'Darwin':
        # macOS - Homebrew
        brew_paths = ['/usr/local/bin/brew', '/opt/homebrew/bin/brew']
        brew_cmd = None
        for path in brew_paths:
            if os.path.exists(path):
                brew_cmd = path
                break
        
        if brew_cmd:
            print("  Installiere ffmpeg über Homebrew...")
            try:
                subprocess.run([brew_cmd, 'install', 'ffmpeg'], check=True, timeout=300)
                print("✓ ffmpeg erfolgreich installiert")
                return True
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                print("❌ Automatische Installation fehlgeschlagen")
                return False
    
    return False

if __name__ == "__main__":
    # Schnelle Abhängigkeitsprüfung
    missing = check_dependencies_quick()
    
    # Versuche ffmpeg automatisch zu installieren falls es fehlt
    if "ffmpeg" in missing:
        install_ffmpeg_if_missing()
        # Prüfe nochmal
        missing = check_dependencies_quick()
    
    if missing:
        print("⚠ Warnung: Einige Abhängigkeiten fehlen:")
        for dep in missing:
            print(f"  - {dep}")
        print("\nFühren Sie aus für detaillierte Prüfung:")
        print("  python check_dependencies.py")
        print("\nOder installieren Sie fehlende Pakete:")
        print("  pip install -r requirements.txt")
        print("\nVersuche trotzdem zu starten...\n")
    
    try:
        from gui import main
        
        main()
    except ImportError as e:
        print(f"✗ Fehler beim Importieren der Module: {e}")
        print("\nBitte installieren Sie die Abhängigkeiten:")
        print("  pip install -r requirements.txt")
        print("\nFür detaillierte Prüfung:")
        print("  python check_dependencies.py")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Fehler beim Starten der Anwendung: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

