#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für yt-dlp Aufrufe
Unterstützt sowohl System-Befehle als auch Python-Modul-Aufrufe
"""

import sys
import subprocess
import os


def is_frozen():
    """Prüft ob die Anwendung als .exe gebaut wurde (PyInstaller)"""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')


def get_ytdlp_command():
    """
    Gibt den richtigen yt-dlp Befehl zurück
    
    Returns:
        Liste mit Befehl und Argumenten für subprocess.run
        Oder None wenn yt_dlp direkt als Modul verwendet werden sollte
    """
    if is_frozen():
        # In einer .exe: Versuche Python zu finden, das mit der .exe gebaut wurde
        # Oder verwende yt_dlp direkt als Modul (wird in run_ytdlp_direct behandelt)
        # Für subprocess: Versuche Python aus dem System zu finden
        python_exe = _find_python_executable()
        if python_exe:
            return [python_exe, '-m', 'yt_dlp']
        else:
            # Fallback: Verwende yt_dlp direkt (wird in run_ytdlp_direct behandelt)
            return None
    else:
        # Normale Python-Umgebung: Versuche System-Befehl
        # Prüfe ob yt-dlp im PATH ist
        if _check_ytdlp_system():
            return ['yt-dlp']
        else:
            # Fallback: Verwende Python-Modul
            return [sys.executable, '-m', 'yt_dlp']


def _find_python_executable():
    """Versucht Python-Executable zu finden (für .exe Builds)"""
    # In einer .exe: Versuche Python aus verschiedenen Orten
    possible_paths = [
        os.path.join(os.path.dirname(sys.executable), 'python.exe'),
        'python.exe',
        'python3.exe',
        'python',
        'python3'
    ]
    
    for path in possible_paths:
        try:
            # Prüfe ob Python verfügbar ist
            result = subprocess.run(
                [path, '--version'],
                capture_output=True,
                timeout=2,
                check=True
            )
            # Prüfe ob yt_dlp verfügbar ist
            result2 = subprocess.run(
                [path, '-m', 'yt_dlp', '--version'],
                capture_output=True,
                timeout=2,
                check=True
            )
            return path
        except:
            continue
    
    return None


def _check_ytdlp_system():
    """Prüft ob yt-dlp als System-Befehl verfügbar ist"""
    try:
        subprocess.run(['yt-dlp', '--version'], 
                      capture_output=True, 
                      timeout=2, 
                      check=True)
        return True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_ytdlp(args, **kwargs):
    """
    Führt yt-dlp mit den gegebenen Argumenten aus
    
    Args:
        args: Liste mit yt-dlp Argumenten (ohne 'yt-dlp' selbst)
        **kwargs: Weitere Argumente für subprocess.run
    
    Returns:
        subprocess.CompletedProcess Ergebnis
    """
    # In .exe Builds: Verwende immer direkte API
    if is_frozen():
        return run_ytdlp_direct(args, **kwargs)
    
    # Normale Python-Umgebung: Verwende subprocess
    cmd = get_ytdlp_command()
    if cmd is None:
        # Fallback: Versuche System-Befehl
        cmd = ['yt-dlp'] if _check_ytdlp_system() else [sys.executable, '-m', 'yt_dlp']
    
    return subprocess.run(cmd + args, **kwargs)


def run_ytdlp_direct(args, **kwargs):
    """
    Führt yt-dlp direkt über die Python-API aus (für .exe Builds)
    
    Args:
        args: Liste mit yt-dlp Argumenten
        **kwargs: Weitere Argumente (werden ignoriert, da direkter Aufruf)
    
    Returns:
        subprocess.CompletedProcess-ähnliches Objekt
    """
    try:
        import yt_dlp
        from io import StringIO
        import sys as sys_module
        
        # Konvertiere args zu sys.argv-Format
        old_argv = sys_module.argv
        sys_module.argv = ['yt-dlp'] + args
        
        # Fange stdout/stderr ab
        old_stdout = sys_module.stdout
        old_stderr = sys_module.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()
        
        try:
            sys_module.stdout = stdout_capture
            sys_module.stderr = stderr_capture
            
            # Führe yt-dlp aus
            yt_dlp.main()
            returncode = 0
        except SystemExit as e:
            returncode = e.code if e.code is not None else 0
        except Exception as e:
            returncode = 1
            stderr_capture.write(str(e))
        finally:
            sys_module.argv = old_argv
            sys_module.stdout = old_stdout
            sys_module.stderr = old_stderr
        
        # Erstelle CompletedProcess-ähnliches Objekt
        class FakeCompletedProcess:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr
        
        return FakeCompletedProcess(
            returncode,
            stdout_capture.getvalue(),
            stderr_capture.getvalue()
        )
    except ImportError:
        # Fallback: Versuche subprocess mit Python
        python_exe = _find_python_executable()
        if python_exe:
            return subprocess.run([python_exe, '-m', 'yt_dlp'] + args, **kwargs)
        else:
            raise RuntimeError("yt-dlp nicht verfügbar und Python nicht gefunden")


def get_ytdlp_version():
    """
    Gibt die yt-dlp Version zurück
    
    Returns:
        Version-String oder None bei Fehler
    """
    try:
        result = run_ytdlp(['--version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    
    # Fallback: Versuche über Python-Modul
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        pass
    
    return None
