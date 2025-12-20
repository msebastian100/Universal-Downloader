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


def get_latest_ytdlp_version():
    """Ruft die neueste yt-dlp Version von PyPI ab"""
    try:
        import urllib.request
        import json
        
        # PyPI API für yt-dlp
        url = "https://pypi.org/pypi/yt-dlp/json"
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read())
            latest_version = data['info']['version']
            return latest_version
    except Exception:
        return None


def update_ytdlp():
    """Aktualisiert yt-dlp auf die neueste Version"""
    try:
        print("[INFO] Aktualisiere yt-dlp auf die neueste Version...")
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'],
            check=True,
            capture_output=True,
            timeout=180
        )
        print("[OK] yt-dlp erfolgreich aktualisiert")
        return True
    except Exception as e:
        print(f"[WARNING] Fehler bei yt-dlp Update: {e}")
        return False


def check_and_update_ytdlp():
    """Prüft ob yt-dlp aktualisiert werden muss und aktualisiert es falls nötig
    
    Returns:
        tuple: (success: bool, was_updated: bool, message: str)
    """
    ytdlp_available, current_version = check_ytdlp()
    
    if not ytdlp_available:
        result = install_ytdlp()
        return result, result, "Installiert" if result else "Installation fehlgeschlagen"
    
    # Prüfe auf Updates (nur alle X Tage, um nicht bei jedem Start zu prüfen)
    was_updated = False
    update_message = None
    try:
        from pathlib import Path
        import json
        from datetime import datetime, timedelta
        
        app_dir = get_app_dir()
        update_check_file = app_dir / ".ytdlp_update_check.json"
        
        # Prüfe wann zuletzt geprüft wurde
        should_check = True
        if update_check_file.exists():
            try:
                with open(update_check_file, 'r') as f:
                    data = json.load(f)
                    last_check = datetime.fromisoformat(data.get('last_check', '2000-01-01'))
                    # Prüfe nur alle 7 Tage
                    if datetime.now() - last_check < timedelta(days=7):
                        should_check = False
            except:
                pass
        
        if should_check:
            print("[INFO] Prüfe auf yt-dlp Updates...")
            latest_version = get_latest_ytdlp_version()
            
            if latest_version and latest_version != current_version:
                print(f"[INFO] Neue yt-dlp Version verfügbar: {latest_version} (aktuell: {current_version})")
                update_message = f"Update verfügbar: {current_version} → {latest_version}"
                if update_ytdlp():
                    was_updated = True
                    update_message = f"Erfolgreich aktualisiert: {current_version} → {latest_version}"
                    # Speichere Check-Datum
                    with open(update_check_file, 'w') as f:
                        json.dump({
                            'last_check': datetime.now().isoformat(),
                            'updated_to': latest_version
                        }, f)
                else:
                    update_message = f"Update fehlgeschlagen: {current_version} → {latest_version}"
            else:
                # Speichere Check-Datum auch wenn keine Updates verfügbar
                with open(update_check_file, 'w') as f:
                    json.dump({
                        'last_check': datetime.now().isoformat(),
                        'current_version': current_version
                    }, f)
    except Exception as e:
        # Fehler bei Update-Check sind nicht kritisch
        print(f"[INFO] Update-Check übersprungen: {e}")
    
    return ytdlp_available, was_updated, update_message


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
    # Prüfe zuerst ob ffmpeg im PATH ist
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
    
    # Prüfe lokale Installation (Windows)
    if sys.platform == "win32":
        try:
            app_dir = get_app_dir()
            ffmpeg_exe = app_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
            if ffmpeg_exe.exists():
                # Prüfe ob es funktioniert
                result = subprocess.run(
                    [str(ffmpeg_exe), '-version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    # Füge zum PATH hinzu für diese Session
                    ffmpeg_bin = app_dir / "ffmpeg" / "bin"
                    if str(ffmpeg_bin) not in os.environ.get('PATH', ''):
                        os.environ['PATH'] = str(ffmpeg_bin) + os.pathsep + os.environ.get('PATH', '')
                    return True, version_line
        except Exception:
            pass
    
    return False, None


def install_ffmpeg_windows(progress_callback=None):
    """Installiert ffmpeg auf Windows"""
    app_dir = get_app_dir()
    ffmpeg_dir = app_dir / "ffmpeg"
    ffmpeg_exe = ffmpeg_dir / "bin" / "ffmpeg.exe"
    
    # Prüfe ob bereits installiert
    if ffmpeg_exe.exists():
        # Füge zum PATH hinzu für diese Session
        os.environ['PATH'] = str(ffmpeg_dir / "bin") + os.pathsep + os.environ.get('PATH', '')
        if progress_callback:
            progress_callback("[OK] ffmpeg bereits vorhanden")
        return True, "bereits vorhanden"
    
    try:
        if progress_callback:
            progress_callback("[INFO] Lade ffmpeg für Windows herunter...")
        print("[INFO] Lade ffmpeg für Windows herunter...")
        
        # Erstelle ffmpeg Verzeichnis
        ffmpeg_dir.mkdir(exist_ok=True)
        
        # Download-URL für Windows ffmpeg (statische Builds von gyan.dev)
        # Verwende eine stabile Version
        ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        zip_path = ffmpeg_dir / "ffmpeg.zip"
        
        # Download mit Progress-Tracking und sofortigem Schreiben
        if progress_callback:
            progress_callback("[INFO] Lade ffmpeg herunter (dies kann einige Minuten dauern)...")
        print("[INFO] Lade ffmpeg herunter (dies kann einige Minuten dauern)...")
        try:
            import requests
            
            # Download mit Progress-Tracking
            response = requests.get(ffmpeg_url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_percent = -1
            
            # Öffne Datei im Binary-Mode und schreibe direkt mit Flush
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        f.flush()  # Wichtig: Sofort schreiben
                        os.fsync(f.fileno())  # Force write to disk
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded * 100) // total_size
                            # Aktualisiere häufiger: alle 1% oder alle 1MB für bessere Echtzeit-Anzeige
                            if percent != last_percent and (percent % 1 == 0 or downloaded % (1*1024*1024) == 0):
                                downloaded_mb = downloaded // (1024*1024)
                                total_mb = total_size // (1024*1024)
                                progress_msg = f"[INFO] Download Fortschritt: {percent}% ({downloaded_mb}MB / {total_mb}MB)"
                                print(f"\r{progress_msg}", end='', flush=True)
                                if progress_callback:
                                    try:
                                        progress_callback(progress_msg)
                                    except:
                                        pass
                                last_percent = percent
                print()  # Neue Zeile nach Progress
        except ImportError:
            # Fallback: Verwende urllib mit besserem Schreiben
            print("[INFO] Verwende Fallback-Download-Methode...")
            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    percent = min(100, (count * block_size * 100) // total_size)
                    downloaded_mb = (count * block_size) // (1024*1024)
                    total_mb = total_size // (1024*1024)
                    print(f"\r[INFO] Download Fortschritt: {percent}% ({downloaded_mb}MB / {total_mb}MB)", end='', flush=True)
            
            urllib.request.urlretrieve(ffmpeg_url, zip_path, reporthook=reporthook)
            print()  # Neue Zeile nach Progress
        except Exception as e:
            print(f"[ERROR] Fehler beim Download: {e}")
            raise
        
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
        if progress_callback:
            progress_callback("[INFO] Prüfe ffmpeg Installation...")
        ffmpeg_ok, ffmpeg_version = check_ffmpeg()
        if ffmpeg_ok:
            if progress_callback:
                progress_callback(f"[OK] ffmpeg erfolgreich installiert: {ffmpeg_version}")
            print("[OK] ffmpeg erfolgreich installiert")
            return True, "installiert"
        else:
            if progress_callback:
                progress_callback("[WARNING] ffmpeg wurde heruntergeladen, aber nicht gefunden")
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


def check_requirements_txt(progress_callback=None):
    """
    Prüft ob alle Pakete aus requirements.txt installiert sind
    
    Returns:
        tuple: (all_installed: bool, missing_packages: list)
    """
    try:
        requirements_file = get_app_dir() / "requirements.txt"
        if not requirements_file.exists():
            if progress_callback:
                progress_callback("[WARNING] requirements.txt nicht gefunden")
            return True, []  # Wenn keine requirements.txt, gehen wir davon aus, dass alles OK ist
        
        # Lese requirements.txt
        missing_packages = []
        with open(requirements_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Parse Paketname (entferne Versionsangaben)
                package_name = line.split('>=')[0].split('==')[0].split('<')[0].split(',')[0].strip()
                if not package_name:
                    continue
                
                # Prüfe ob Paket installiert ist
                try:
                    # Versuche Import
                    if package_name == 'yt-dlp':
                        import_name = 'yt_dlp'
                    elif package_name == 'Pillow':
                        import_name = 'PIL'
                    elif package_name == 'beautifulsoup4':
                        import_name = 'bs4'
                    elif package_name == 'browser-cookie3':
                        import_name = 'browser_cookie3'
                    elif package_name == 'deezer-python':
                        import_name = 'deezer'
                    else:
                        import_name = package_name.replace('-', '_')
                    
                    __import__(import_name)
                except ImportError:
                    missing_packages.append(package_name)
        
        if missing_packages:
            if progress_callback:
                progress_callback(f"[WARNING] Fehlende Pakete: {', '.join(missing_packages)}")
            return False, missing_packages
        else:
            if progress_callback:
                progress_callback("[OK] Alle Pakete aus requirements.txt sind installiert")
            return True, []
    except Exception as e:
        if progress_callback:
            progress_callback(f"[ERROR] Fehler beim Prüfen von requirements.txt: {e}")
        return False, []


def install_requirements_txt(progress_callback=None):
    """
    Installiert Pakete aus requirements.txt
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        requirements_file = get_app_dir() / "requirements.txt"
        if not requirements_file.exists():
            return False, "requirements.txt nicht gefunden"
        
        if progress_callback:
            progress_callback("[INFO] Installiere Pakete aus requirements.txt...")
        print("[INFO] Installiere Pakete aus requirements.txt...")
        
        # Führe pip install aus
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '--upgrade', '-r', str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=600  # 10 Minuten Timeout
        )
        
        if result.returncode == 0:
            if progress_callback:
                progress_callback("[OK] requirements.txt erfolgreich installiert")
            print("[OK] requirements.txt erfolgreich installiert")
            return True, "installiert"
        else:
            error_msg = result.stderr[:200] if result.stderr else "Unbekannter Fehler"
            if progress_callback:
                progress_callback(f"[ERROR] Installation fehlgeschlagen: {error_msg}")
            print(f"[ERROR] Installation fehlgeschlagen: {error_msg}")
            return False, error_msg
    except subprocess.TimeoutExpired:
        if progress_callback:
            progress_callback("[ERROR] Installation-Timeout (über 10 Minuten)")
        print("[ERROR] Installation-Timeout")
        return False, "Timeout"
    except Exception as e:
        if progress_callback:
            progress_callback(f"[ERROR] Fehler bei Installation: {e}")
        print(f"[ERROR] Fehler bei Installation: {e}")
        return False, str(e)


def ensure_dependencies():
    """
    Stellt sicher, dass alle Abhängigkeiten vorhanden sind
    Gibt (ytdlp_ok, ffmpeg_ok, messages, has_updates) zurück
    """
    messages = []
    ytdlp_ok = False
    ffmpeg_ok = False
    has_updates = False
    
    # Progress-Callback für alle Funktionen
    progress_callback = getattr(ensure_dependencies, '_progress_callback', None)
    
    # Prüfe und installiere requirements.txt
    requirements_ok, missing_packages = check_requirements_txt(progress_callback)
    if not requirements_ok:
        messages.append("[WARNING] Einige Pakete aus requirements.txt fehlen - versuche Installation...")
        success, status = install_requirements_txt(progress_callback)
        if success:
            messages.append(f"[OK] requirements.txt Installation: {status}")
            has_updates = True
        else:
            messages.append(f"[ERROR] requirements.txt Installation fehlgeschlagen: {status}")
    else:
        messages.append("[OK] Alle Pakete aus requirements.txt sind installiert")
    
    # Prüfe und aktualisiere yt-dlp
    ytdlp_ok, ytdlp_updated, ytdlp_message = check_and_update_ytdlp()
    if ytdlp_ok:
        ytdlp_available, ytdlp_version = check_ytdlp()
        if ytdlp_updated:
            messages.append(f"[OK] yt-dlp erfolgreich aktualisiert: {ytdlp_message}")
            has_updates = True
        elif ytdlp_message:
            messages.append(f"[INFO] yt-dlp: {ytdlp_message}")
            has_updates = True
        else:
            messages.append(f"[OK] yt-dlp verfügbar (Version: {ytdlp_version})")
    else:
        messages.append("[ERROR] yt-dlp Installation/Update fehlgeschlagen")
    
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
            # Verwende Progress-Callback falls vorhanden
            progress_callback = getattr(ensure_dependencies, '_progress_callback', None)
            success, status = install_ffmpeg_windows(progress_callback=progress_callback)
        elif system == 'Linux':
            success, status = install_ffmpeg_linux()
        elif system == 'Darwin':
            success, status = install_ffmpeg_macos()
        else:
            messages.append(f"[ERROR] Betriebssystem '{system}' nicht unterstützt")
        
        if success:
            ffmpeg_ok = True
            messages.append(f"[OK] ffmpeg Installation: {status}")
            # Markiere als Update, wenn ffmpeg installiert wurde (nicht nur wenn es bereits vorhanden war)
            if status == "installiert":
                has_updates = True
        else:
            messages.append(f"[ERROR] ffmpeg Installation fehlgeschlagen: {status}")
            messages.append("[INFO] Bitte installieren Sie ffmpeg manuell:")
            if system == 'Windows':
                messages.append("  Download von: https://ffmpeg.org/download.html")
            elif system == 'Linux':
                messages.append("  sudo apt-get install ffmpeg (oder entsprechendes Paket-Manager)")
            elif system == 'Darwin':
                messages.append("  brew install ffmpeg")
    
    return ytdlp_ok, ffmpeg_ok, messages, has_updates


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
