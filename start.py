#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Startskript für Universal Downloader
Startet die GUI-Anwendung
"""

import sys
import os
from pathlib import Path

# Füge das aktuelle Verzeichnis zum Python-Pfad hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_ffmpeg():
    """Prüft ob ffmpeg verfügbar ist"""
    import subprocess
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2, check=True)
        if result.returncode == 0:
            return True, result.stdout.decode('utf-8', errors='ignore').split('\n')[0]
    except Exception:
        pass
    return False, None

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
    
    # Prüfe ffmpeg
    ffmpeg_ok, _ = check_ffmpeg()
    if not ffmpeg_ok:
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
    # Automatische Installation von Abhängigkeiten
    try:
        from auto_install_dependencies import ensure_dependencies
        
        print("[INFO] Prüfe Abhängigkeiten...")
        ytdlp_ok, ffmpeg_ok, messages = ensure_dependencies()
        
        # Zeige nur wichtige Meldungen
        for msg in messages:
            if "[ERROR]" in msg or "[WARNING]" in msg or "[OK]" in msg:
                print(msg)
        
        # Füge ffmpeg zum PATH hinzu (falls lokal installiert)
        if not ffmpeg_ok:
            from pathlib import Path
            app_dir = Path(__file__).parent if not getattr(sys, 'frozen', False) else Path(sys.executable).parent
            ffmpeg_bin = app_dir / "ffmpeg" / "bin"
            if ffmpeg_bin.exists():
                os.environ['PATH'] = str(ffmpeg_bin) + os.pathsep + os.environ.get('PATH', '')
                # Prüfe nochmal
                ffmpeg_ok, _ = check_ffmpeg()
        
    except ImportError:
        # Fallback: Alte Methode
        missing = check_dependencies_quick()
        if "ffmpeg" in missing:
            install_ffmpeg_if_missing()
            missing = check_dependencies_quick()
        
        if missing:
            print("⚠ Warnung: Einige Abhängigkeiten fehlen:")
            for dep in missing:
                print(f"  - {dep}")
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

