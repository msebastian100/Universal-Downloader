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
    """
    if is_frozen():
        # In einer .exe: Verwende yt_dlp als Python-Modul
        # sys.executable zeigt auf die .exe, aber wir können yt_dlp direkt importieren
        # und über sys.executable -m yt_dlp aufrufen
        # Oder noch besser: yt_dlp direkt als Modul verwenden
        return [sys.executable, '-m', 'yt_dlp']
    else:
        # Normale Python-Umgebung: Versuche System-Befehl
        # Prüfe ob yt-dlp im PATH ist
        if _check_ytdlp_system():
            return ['yt-dlp']
        else:
            # Fallback: Verwende Python-Modul
            return [sys.executable, '-m', 'yt_dlp']


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
    cmd = get_ytdlp_command() + args
    return subprocess.run(cmd, **kwargs)


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
