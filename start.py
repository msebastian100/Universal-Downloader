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
    import tempfile
    from datetime import datetime
    
    # Debug-Logging Setup
    def debug_log(message: str, level: str = "INFO"):
        """Debug-Logging für start.py"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_tag = f"[{level}]" if level != "INFO" else "[INFO]"
        print(f"{level_tag} [{timestamp}] {message}")
        
        # Schreibe auch in Log-Datei falls möglich
        try:
            log_dir = Path.home() / "Downloads" / "Universal Downloader" / "Logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"start_debug_{datetime.now().strftime('%Y-%m-%d')}.log"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{level_tag} [{timestamp}] {message}\n")
        except Exception:
            pass  # Ignoriere Fehler beim Log-Schreiben
    
    debug_log("=" * 60)
    debug_log("Universal Downloader wird gestartet...")
    debug_log(f"Python-Version: {sys.version}")
    debug_log(f"Plattform: {sys.platform}")
    debug_log(f"Executable: {sys.executable}")
    debug_log(f"Frozen: {getattr(sys, 'frozen', False)}")
    
    # Prüfe auf Restart-Flag
    restart_flag_file = Path(tempfile.gettempdir()) / "universal_downloader_restarting.flag"
    if restart_flag_file.exists():
        debug_log("Restart-Flag gefunden - lösche Flag und überspringe Abhängigkeits-Installation")
        try:
            restart_flag_file.unlink(missing_ok=True)
        except Exception as e:
            debug_log(f"Fehler beim Löschen des Restart-Flags: {e}", "WARNING")
    else:
        debug_log("Kein Restart-Flag gefunden - normaler Start")
    
    # Schnelle Prüfung der wichtigsten Abhängigkeiten (nicht blockierend)
    try:
        debug_log("Importiere auto_install_dependencies...")
        from auto_install_dependencies import check_ytdlp, check_ffmpeg, get_app_dir
        
        debug_log("Prüfe yt-dlp...")
        ytdlp_ok, ytdlp_version = check_ytdlp()
        debug_log(f"yt-dlp Status: {'OK' if ytdlp_ok else 'FEHLT'} (Version: {ytdlp_version or 'N/A'})")
        
        debug_log("Prüfe ffmpeg...")
        ffmpeg_ok, ffmpeg_version = check_ffmpeg()
        debug_log(f"ffmpeg Status: {'OK' if ffmpeg_ok else 'FEHLT'} (Version: {ffmpeg_version or 'N/A'})")
        
        # Füge ffmpeg zum PATH hinzu (falls lokal installiert)
        if not ffmpeg_ok:
            app_dir = get_app_dir()
            ffmpeg_bin = app_dir / "ffmpeg" / "bin"
            debug_log(f"Prüfe lokales ffmpeg in: {ffmpeg_bin}")
            if ffmpeg_bin.exists():
                debug_log(f"Lokales ffmpeg gefunden - füge zum PATH hinzu")
                os.environ['PATH'] = str(ffmpeg_bin) + os.pathsep + os.environ.get('PATH', '')
                # Prüfe nochmal
                ffmpeg_ok, ffmpeg_version = check_ffmpeg()
                debug_log(f"ffmpeg Status nach PATH-Update: {'OK' if ffmpeg_ok else 'FEHLT'}")
        
        # Starte GUI sofort - Abhängigkeiten werden im Hintergrund geprüft/installiert
        if not ytdlp_ok or not ffmpeg_ok:
            debug_log("Einige Abhängigkeiten fehlen - werden im Hintergrund installiert", "WARNING")
        else:
            debug_log("Alle Abhängigkeiten vorhanden")
        
    except ImportError as e:
        debug_log(f"ImportError bei auto_install_dependencies: {e}", "WARNING")
        # Fallback: Alte Methode
        missing = check_dependencies_quick()
        if missing:
            debug_log("Warnung: Einige Abhängigkeiten fehlen:", "WARNING")
            for dep in missing:
                debug_log(f"  - {dep}", "WARNING")
            debug_log("Versuche trotzdem zu starten...")
    except Exception as e:
        # Fehler bei Abhängigkeitsprüfung sind nicht kritisch - starte trotzdem
        debug_log(f"Fehler bei Abhängigkeitsprüfung: {e}", "ERROR")
        import traceback
        debug_log(f"Traceback: {traceback.format_exc()}", "ERROR")
    
    try:
        debug_log("Importiere gui...")
        from gui import main
        
        debug_log("Starte GUI...")
        main()
    except ImportError as e:
        debug_log(f"Fehler beim Importieren der Module: {e}", "ERROR")
        print(f"✗ Fehler beim Importieren der Module: {e}")
        print("\nBitte installieren Sie die Abhängigkeiten:")
        print("  pip install -r requirements.txt")
        print("\nFür detaillierte Prüfung:")
        print("  python check_dependencies.py")
        sys.exit(1)
    except Exception as e:
        debug_log(f"Fehler beim Starten der Anwendung: {e}", "ERROR")
        import traceback
        debug_log(f"Traceback: {traceback.format_exc()}", "ERROR")
        print(f"✗ Fehler beim Starten der Anwendung: {e}")
        traceback.print_exc()
        sys.exit(1)

