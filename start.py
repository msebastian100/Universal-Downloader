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

# Setze Prozess-Icon auf Windows (wird im Task-Manager und Taskleiste angezeigt)
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        
        # Setze App User Model ID (für Windows 7+ Taskleiste)
        # Dies hilft Windows, die Anwendung korrekt zu identifizieren und das Icon anzuzeigen
        try:
            shell32 = ctypes.windll.shell32
            app_id = "UniversalDownloader.UniversalDownloader.1.0"
            shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass
        
        # Finde Icon-Datei
        script_dir = Path(__file__).parent.absolute()
        icon_paths = [
            script_dir / "icon.ico",
            script_dir / "icon.png",
        ]
        
        icon_path = None
        for path in icon_paths:
            if path.exists():
                icon_path = path
                break
        
        # Das Icon wird in gui.py für das Fenster gesetzt
        # Hier setzen wir nur die App User Model ID für die Taskleiste
    except Exception:
        pass


def _safe_print(text: str) -> None:
    """Gibt Text auf der Konsole aus; vermeidet UnicodeEncodeError unter Windows (cp1252)."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: nur ASCII/ersetzte Zeichen (z. B. unter Windows-Konsole)
        print(text.encode("ascii", errors="replace").decode("ascii"))


def check_ffmpeg():
    """Prüft ob ffmpeg verfügbar ist"""
    import subprocess
    from path_helper import win_hidden_kwargs
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=2,
            check=True,
            **win_hidden_kwargs(),
        )
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
    from path_helper import win_hidden_kwargs
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2, check=True, **win_hidden_kwargs())
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

def _hide_windows_console() -> None:
    """Konsolenfenster sofort weg, auch bei der gepackten EXE."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
        kernel32.FreeConsole()
    except Exception:
        pass
    _silence_child_consoles()


def _silence_child_consoles() -> None:
    """Kindprozesse (yt-dlp, ffmpeg, Player) ohne eigenes CMD-Fenster."""
    if sys.platform != "win32":
        return
    import subprocess

    flag = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    if getattr(subprocess.Popen, "_ud_no_console", False):
        return
    original = subprocess.Popen

    class _NoConsolePopen(original):
        _ud_no_console = True

        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = (kwargs.get("creationflags") or 0) | flag
            super().__init__(*args, **kwargs)

    subprocess.Popen = _NoConsolePopen


if __name__ == "__main__":
    _hide_windows_console()
    # Eigenständiger Serien-Wächter (System-Tray / Menüleiste), auch aus der gepackten .exe
    if "--series-watch-tray" in sys.argv:
        # LSUIElement setzen, BEVOR irgendwer NSApplication.startet – sonst Dock-Icon.
        if sys.platform == "darwin":
            try:
                import Foundation  # type: ignore[import-untyped]
                from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

                ns_bundle = getattr(Foundation, "NSBundle", None)
                if ns_bundle is None:
                    raise RuntimeError("NSBundle fehlt")
                info = ns_bundle.mainBundle().infoDictionary()
                if info is not None:
                    info["LSUIElement"] = True
                # Vor dem Tray-Start, sonst bleibt ein zweites Dock-Icon stehen.
                NSApplication.sharedApplication().setActivationPolicy_(
                    NSApplicationActivationPolicyAccessory
                )
            except Exception:
                pass
        _tray_argv = [a for a in sys.argv[1:] if a != "--series-watch-tray"]
        from series_watch_tray import main as tray_main
        raise SystemExit(tray_main(_tray_argv))

    # macOS: Sofort Single-Instance-Lock (vor allen anderen Imports), reduziert Doppelstart
    _lock_handle = None
    if sys.platform == "darwin":
        try:
            from mac_platform import ensure_macos_native_path
            ensure_macos_native_path()
        except Exception:
            # Fallback: Homebrew-arm64 voranstellen
            _hb = "/opt/homebrew/bin"
            if os.path.isdir(_hb):
                os.environ["PATH"] = _hb + os.pathsep + os.environ.get("PATH", "")
        try:
            import fcntl
            _lock_file = Path.home() / ".universal_downloader.lock"
            _f = open(_lock_file, "w")
            try:
                fcntl.flock(_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                _f.write(str(os.getpid()))
                _f.flush()
                _lock_handle = _f  # Halten, damit Lock bestehen bleibt
            except (IOError, OSError):
                _f.close()
                _old_pid = 0
                try:
                    with open(_lock_file, "r") as _rf:
                        _old_pid = int(_rf.read().strip())
                    os.kill(_old_pid, 0)
                except (ProcessLookupError, ValueError, OSError):
                    _old_pid = 0
                if _old_pid:
                    try:
                        import subprocess
                        subprocess.run(
                            [
                                "osascript",
                                "-e",
                                f'tell application "System Events" to set frontmost of '
                                f"(first process whose unix id is {_old_pid}) to true",
                            ],
                            capture_output=True,
                            timeout=2,
                        )
                    except Exception:
                        pass
                os._exit(0)
        except Exception:
            pass

    import tempfile
    from datetime import datetime
    
    # Plattform-spezifische Imports für Lock-Mechanismus
    msvcrt = None
    fcntl = None
    if sys.platform == "win32":
        try:
            import msvcrt as _msvcrt
            msvcrt = _msvcrt
        except ImportError:
            pass
    else:
        try:
            import fcntl as _fcntl
            fcntl = _fcntl
        except ImportError:
            pass
    
    # Single-Instance: Fester Pfad im Benutzerverzeichnis (unter macOS/Programme sonst oft zweite Instanz)
    lock_file = Path.home() / ".universal_downloader.lock"
    lock_file_handle = _lock_handle  # Unter macOS bereits geholt
    
    def acquire_lock():
        """Erwirbt eine Lock-Datei, um sicherzustellen, dass nur eine Instanz läuft"""
        global lock_file_handle
        try:
            if sys.platform == "win32":
                if msvcrt is None:
                    return True
                # Windows: Verwende msvcrt
                lock_file_handle = open(lock_file, 'w')
                try:
                    msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    # Schreibe PID in Lock-Datei
                    lock_file_handle.write(str(os.getpid()))
                    lock_file_handle.flush()
                    return True
                except IOError:
                    # Lock bereits vorhanden - andere Instanz läuft
                    lock_file_handle.close()
                    return False
            else:
                if fcntl is None:
                    return True
                # Unix/Linux/macOS: Verwende fcntl.
                # Nicht mit "w" öffnen: das leert die PID, bevor die Sperre greift,
                # und eine zweite Instanz startet dann doch ein Fenster.
                lock_file_handle = open(lock_file, 'a+')
                try:
                    fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    lock_file_handle.seek(0)
                    lock_file_handle.truncate()
                    lock_file_handle.write(str(os.getpid()))
                    lock_file_handle.flush()
                    return True
                except IOError:
                    # Lock bereits vorhanden - andere Instanz läuft
                    lock_file_handle.close()
                    return False
        except Exception as e:
            # Bei Fehler: Versuche trotzdem zu starten
            print(f"[WARNING] Konnte Lock nicht setzen: {e}")
            return True  # Erlaube Start trotzdem
    
    def release_lock():
        """Gibt die Lock-Datei frei"""
        global lock_file_handle
        try:
            if lock_file_handle:
                if sys.platform == "win32":
                    if msvcrt:
                        try:
                            msvcrt.locking(lock_file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                        except:
                            pass
                else:
                    if fcntl:
                        try:
                            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_UN)
                        except:
                            pass
                try:
                    lock_file_handle.close()
                except:
                    pass
                lock_file_handle = None
            # Warte kurz, damit die Datei vollständig geschlossen ist
            import time
            time.sleep(0.1)
            # Versuche Lock-Datei zu löschen (mehrmals mit Retry)
            if lock_file.exists():
                for attempt in range(3):
                    try:
                        lock_file.unlink(missing_ok=True)
                        break
                    except (PermissionError, OSError) as e:
                        if attempt < 2:
                            time.sleep(0.2)
                        else:
                            # Bei letztem Versuch: Ignoriere Fehler
                            pass
        except Exception:
            pass
    
    # Prüfe ob bereits eine Instanz läuft (unter macOS ggf. schon oben geholt)
    if lock_file_handle is None and not acquire_lock():
        # Fenster der laufenden Instanz nach vorn, statt still zu enden.
        try:
            from path_helper import get_app_base_path
            (Path(get_app_base_path()) / "series_watch_show_window").write_text("1", encoding="utf-8")
        except Exception:
            pass
        if sys.platform == "win32":
            try:
                import series_watch as _sw_show
                _shown_pid = _sw_show._gui_lock_pid()
                if _shown_pid:
                    _sw_show._windows_activate_pid(_shown_pid)
            except Exception:
                pass
        # Prüfe ob die andere Instanz noch läuft
        try:
            if lock_file.exists():
                try:
                    with open(lock_file, 'r') as f:
                        old_pid = int(f.read().strip())
                except (PermissionError, OSError):
                    # Unter Windows: Datei von anderer Instanz gesperrt → andere Instanz läuft
                    print("[INFO] Eine andere Instanz läuft bereits.")
                    sys.exit(0)
                # Prüfe ob Prozess noch läuft
                if sys.platform == "win32":
                    import subprocess
                    try:
                        from path_helper import win_hidden_kwargs
                        result = subprocess.run(
                            ['tasklist', '/FI', f'PID eq {old_pid}'],
                            capture_output=True,
                            text=True,
                            timeout=2,
                            **win_hidden_kwargs(),
                        )
                        if str(old_pid) in result.stdout:
                            # Prozess läuft noch - beende diese Instanz
                            print(f"[INFO] Eine andere Instanz läuft bereits (PID: {old_pid})")
                            print("[INFO] Diese Instanz wird beendet...")
                            sys.exit(0)
                    except:
                        pass
                else:
                    # Unix/macOS: Prüfe mit kill -0
                    try:
                        os.kill(old_pid, 0)  # Signal 0 prüft nur ob Prozess existiert
                        # Prozess läuft noch - beende diese Instanz
                        print(f"[INFO] Eine andere Instanz läuft bereits (PID: {old_pid})")
                        print("[INFO] Diese Instanz wird beendet...")
                        try:
                            import series_watch as _sw
                            _sw._request_show_main_window()
                        except Exception:
                            pass
                        if sys.platform == "darwin":
                            # macOS: Laufende Instanz in den Vordergrund holen, damit nur ein Fenster sichtbar ist
                            try:
                                import subprocess
                                subprocess.run(
                                    [
                                        "osascript",
                                        "-e",
                                        f'tell application "System Events" to set frontmost of '
                                        f"(first process whose unix id is {old_pid}) to true",
                                    ],
                                    capture_output=True,
                                    timeout=2,
                                )
                            except Exception:
                                pass
                        os._exit(0)  # Sofort beenden, keine atexit-Handler
                    except ProcessLookupError:
                        # Prozess existiert nicht mehr - lösche alte Lock-Datei
                        lock_file.unlink(missing_ok=True)
                        # Versuche Lock erneut zu erwerben
                        if not acquire_lock():
                            print("[WARNING] Konnte Lock nicht erwerben - beende...")
                            sys.exit(0)
        except (PermissionError, OSError):
            # Unter Windows: Lock-Datei oft von anderer Instanz gehalten – nicht löschen, nur beenden
            print("[INFO] Eine andere Instanz läuft vermutlich bereits.")
            sys.exit(0)
        except Exception:
            # Bei anderem Fehler: Lock-Datei löschen nur wenn möglich (unter Windows oft noch in Benutzung)
            try:
                lock_file.unlink(missing_ok=True)
            except (PermissionError, OSError):
                pass
            if not acquire_lock():
                print("[WARNING] Konnte Lock nicht erwerben - beende...")
                sys.exit(0)
    
    # Cleanup beim Beenden
    import atexit
    atexit.register(release_lock)
    
    # Debug-Logging Setup
    def debug_log(message: str, level: str = "INFO"):
        """Debug-Logging für start.py"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level_tag = f"[{level}]" if level != "INFO" else "[INFO]"
        print(f"{level_tag} [{timestamp}] {message}")
        
        # Schreibe auch in Log-Datei falls möglich
        try:
            # Verwende path_helper um den echten Download-Ordner zu erkennen
            try:
                from path_helper import get_app_base_path
                app_base = get_app_base_path()
                log_dir = app_base / "Logs"
            except ImportError:
                # Fallback: Alte Methode
                log_dir = Path.home() / "Downloads" / "Universal Downloader" / "Logs"
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except (PermissionError, OSError):
                    # Fallback: Verwende AppData oder Temp
                    if sys.platform == "win32":
                        appdata = os.getenv('APPDATA', Path.home() / "AppData" / "Roaming")
                        log_dir = Path(appdata) / "Universal Downloader" / "Logs"
                    else:
                        log_dir = Path.home() / ".universal-downloader" / "Logs"
                    log_dir.mkdir(parents=True, exist_ok=True)
            
            # WICHTIG: Stelle sicher, dass der Ordner existiert, bevor wir die Datei öffnen
            log_dir.mkdir(parents=True, exist_ok=True)
            
            log_file = log_dir / f"start_debug_{datetime.now().strftime('%Y-%m-%d')}.log"
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"{level_tag} [{timestamp}] {message}\n")
                f.flush()  # Sofort schreiben
        except Exception as e:
            # Ignoriere Fehler beim Log-Schreiben, aber logge es
            print(f"[WARNING] Konnte Log-Datei nicht schreiben: {e}")
    
    debug_log("=" * 60)
    debug_log("Universal Downloader wird gestartet...")
    debug_log(f"Python-Version: {sys.version}")
    debug_log(f"Plattform: {sys.platform}")
    debug_log(f"Executable: {sys.executable}")
    debug_log(f"Frozen: {getattr(sys, 'frozen', False)}")
    debug_log(f"PID: {os.getpid()}")
    # Verwende path_helper um den echten Download-Ordner zu erkennen
    try:
        from path_helper import get_app_base_path
        app_base = get_app_base_path()
        log_file_path = app_base / 'Logs' / f'start_debug_{datetime.now().strftime("%Y-%m-%d")}.log'
    except ImportError:
        # Fallback: Alte Methode
        log_file_path = Path.home() / 'Downloads' / 'Universal Downloader' / 'Logs' / f'start_debug_{datetime.now().strftime("%Y-%m-%d")}.log'
    debug_log(f"Log-Datei: {log_file_path}")
    
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
        _safe_print(f"Fehler beim Importieren der Module: {e}")
        _safe_print("\nBitte installieren Sie die Abhängigkeiten:")
        _safe_print("  pip install -r requirements.txt")
        _safe_print("\nFuer detaillierte Pruefung:")
        _safe_print("  python check_dependencies.py")
        sys.exit(1)
    except Exception as e:
        debug_log(f"Fehler beim Starten der Anwendung: {e}", "ERROR")
        import traceback
        debug_log(f"Traceback: {traceback.format_exc()}", "ERROR")
        _safe_print(f"Fehler beim Starten der Anwendung: {e}")
        traceback.print_exc()
        sys.exit(1)

