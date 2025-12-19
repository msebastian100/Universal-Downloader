#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatische Installation von Abhängigkeiten beim ersten Start
"""

import sys
import subprocess
import platform
import os
import shutil
import zipfile
import urllib.request
from pathlib import Path


def is_frozen():
    """Prüft ob die Anwendung als .exe gebaut wurde (PyInstaller)"""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')


def get_app_dir():
    """Gibt das Anwendungsverzeichnis zurück"""
    if is_frozen():
        # In .exe: Verwende das Verzeichnis der .exe
        return Path(sys.executable).parent
    else:
        # Normale Python-Umgebung
        return Path(__file__).parent


def check_ytdlp():
    """Prüft ob yt-dlp verfügbar ist (als Python-Modul)"""
    try:
        import yt_dlp
        # Versuche Version abzurufen
        try:
            version = yt_dlp.version.__version__
            return True, version
        except:
            return True, "unknown"
    except ImportError:
        return False, None


def install_ytdlp():
    """Installiert yt-dlp über pip"""
    try:
        print("[INFO] Installiere yt-dlp...")
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', 'yt-dlp'],
            check=True,
            capture_output=True,
            timeout=120
        )
        print("[OK] yt-dlp erfolgreich installiert")
        return True
    except Exception as e:
        print(f"[ERROR] Fehler bei yt-dlp Installation: {e}")
        return False


def check_ffmpeg():
    """Prüft ob ffmpeg verfügbar ist"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, version_line
    except Exception:
        pass
    return False, None


def install_ffmpeg_windows():
    """Installiert ffmpeg auf Windows"""
    app_dir = get_app_dir()
    ffmpeg_dir = app_dir / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "bin" / "ffmpeg.exe"
    
    # Prüfe ob bereits installiert
    if ffmpeg_exe.exists():
        # Füge zum PATH hinzu für diese Session
        os.environ['PATH'] = str(ffmpeg_dir / "bin") + os.pathsep + os.environ.get('PATH', '')
        return True, "bereits vorhanden"
    
    try:
        print("[INFO] Lade ffmpeg für Windows herunter...")
        
        # Erstelle ffmpeg Verzeichnis
        ffmpeg_dir.mkdir(exist_ok=True)
        
        # Download-URL für Windows ffmpeg (statische Builds von gyan.dev)
        # Verwende eine stabile Version
        ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = ffmpeg_dir / "ffmpeg.zip"
        
        # Download
        print("[INFO] Lade ffmpeg herunter (dies kann einige Minuten dauern)...")
        urllib.request.urlretrieve(ffmpeg_url, zip_path)
        
        # Entpacken
        print("[INFO] Entpacke ffmpeg...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(ffmpeg_dir)
        
        # Finde das bin-Verzeichnis
        for root, dirs, files in os.walk(ffmpeg_dir):
            if 'ffmpeg.exe' in files:
                bin_dir = Path(root)
                # Verschiebe alle Dateien eine Ebene nach oben, falls nötig
                if bin_dir.parent.name != 'bin':
                    # Erstelle bin-Verzeichnis
                    target_bin = ffmpeg_dir / "bin"
                    target_bin.mkdir(exist_ok=True)
                    # Kopiere ffmpeg.exe
                    shutil.copy2(bin_dir / "ffmpeg.exe", target_bin / "ffmpeg.exe")
                    # Kopiere andere benötigte Dateien
                    for file in files:
                        if file.endswith(('.exe', '.dll')):
                            shutil.copy2(bin_dir / file, target_bin / file)
                break
        
        # Lösche ZIP-Datei
        zip_path.unlink(missing_ok=True)
        
        # Füge zum PATH hinzu für diese Session
        os.environ['PATH'] = str(ffmpeg_dir / "bin") + os.pathsep + os.environ.get('PATH', '')
        
        # Prüfe ob es jetzt funktioniert
        if ffmpeg_exe.exists() or check_ffmpeg()[0]:
            print("[OK] ffmpeg erfolgreich installiert")
            return True, "installiert"
        else:
            print("[WARNING] ffmpeg wurde heruntergeladen, aber nicht gefunden")
            return False, "nicht gefunden"
            
    except Exception as e:
        print(f"[ERROR] Fehler bei ffmpeg Installation: {e}")
        return False, str(e)


def install_ffmpeg_linux():
    """Installiert ffmpeg auf Linux"""
    try:
        print("[INFO] Installiere ffmpeg über Paket-Manager...")
        
        # Prüfe verschiedene Paket-Manager
        if shutil.which('apt-get'):
            subprocess.run(['sudo', 'apt-get', 'update'], check=True, timeout=60)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], check=True, timeout=120)
        elif shutil.which('dnf'):
            subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True, timeout=120)
        elif shutil.which('pacman'):
            subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'ffmpeg'], check=True, timeout=120)
        else:
            return False, "Paket-Manager nicht gefunden"
        
        print("[OK] ffmpeg erfolgreich installiert")
        return True, "installiert"
    except Exception as e:
        return False, str(e)


def install_ffmpeg_macos():
    """Installiert ffmpeg auf macOS"""
    try:
        brew_paths = ['/usr/local/bin/brew', '/opt/homebrew/bin/brew']
        brew_cmd = None
        for path in brew_paths:
            if os.path.exists(path):
                brew_cmd = path
                break
        
        if not brew_cmd:
            return False, "Homebrew nicht gefunden"
        
        print("[INFO] Installiere ffmpeg über Homebrew...")
        subprocess.run([brew_cmd, 'install', 'ffmpeg'], check=True, timeout=300)
        print("[OK] ffmpeg erfolgreich installiert")
        return True, "installiert"
    except Exception as e:
        return False, str(e)


def ensure_dependencies():
    """
    Stellt sicher, dass alle Abhängigkeiten vorhanden sind
    Gibt (ytdlp_ok, ffmpeg_ok, messages) zurück
    """
    messages = []
    ytdlp_ok = False
    ffmpeg_ok = False
    
    # Prüfe yt-dlp
    ytdlp_available, ytdlp_version = check_ytdlp()
    if ytdlp_available:
        ytdlp_ok = True
        messages.append(f"[OK] yt-dlp verfügbar (Version: {ytdlp_version})")
    else:
        messages.append("[WARNING] yt-dlp nicht gefunden - versuche Installation...")
        if install_ytdlp():
            ytdlp_ok = True
            messages.append("[OK] yt-dlp erfolgreich installiert")
        else:
            messages.append("[ERROR] yt-dlp Installation fehlgeschlagen")
    
    # Prüfe ffmpeg
    ffmpeg_available, ffmpeg_version = check_ffmpeg()
    if ffmpeg_available:
        ffmpeg_ok = True
        messages.append(f"[OK] ffmpeg verfügbar: {ffmpeg_version}")
    else:
        messages.append("[WARNING] ffmpeg nicht gefunden - versuche Installation...")
        system = platform.system()
        success = False
        status = ""
        
        if system == 'Windows':
            success, status = install_ffmpeg_windows()
        elif system == 'Linux':
            success, status = install_ffmpeg_linux()
        elif system == 'Darwin':
            success, status = install_ffmpeg_macos()
        else:
            messages.append(f"[ERROR] Betriebssystem '{system}' nicht unterstützt")
        
        if success:
            ffmpeg_ok = True
            messages.append(f"[OK] ffmpeg Installation: {status}")
        else:
            messages.append(f"[ERROR] ffmpeg Installation fehlgeschlagen: {status}")
            messages.append("[INFO] Bitte installieren Sie ffmpeg manuell:")
            if system == 'Windows':
                messages.append("  Download von: https://ffmpeg.org/download.html")
            elif system == 'Linux':
                messages.append("  sudo apt-get install ffmpeg (oder entsprechendes Paket-Manager)")
            elif system == 'Darwin':
                messages.append("  brew install ffmpeg")
    
    return ytdlp_ok, ffmpeg_ok, messages


if __name__ == "__main__":
    print("=" * 60)
    print("Automatische Installation von Abhängigkeiten")
    print("=" * 60)
    print()
    
    ytdlp_ok, ffmpeg_ok, messages = ensure_dependencies()
    
    for msg in messages:
        print(msg)
    
    print()
    if ytdlp_ok and ffmpeg_ok:
        print("[OK] Alle Abhängigkeiten sind verfügbar!")
        sys.exit(0)
    else:
        print("[WARNING] Einige Abhängigkeiten fehlen noch")
        sys.exit(1)
