#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für yt-dlp Aufrufe
Unterstützt sowohl System-Befehle als auch Python-Modul-Aufrufe
"""

import sys
import subprocess
import os
import platform


def is_frozen():
    """Prüft ob die Anwendung als .exe gebaut wurde (PyInstaller)"""
    return getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')


def _running_from_app_venv():
    """True wenn die App aus einer eigenen venv läuft (z. B. nach .deb-Install: /usr/share/universal-downloader/venv)."""
    exe = getattr(sys, 'executable', '') or ''
    norm = os.path.normpath(exe)
    # venv: .../venv/bin/python3  oder  .../universal-downloader/venv/...
    if 'venv' in norm and ('universal-downloader' in norm or os.path.basename(os.path.dirname(norm)) == 'bin'):
        return True
    return False


def _version_parts(text):
    parts = []
    for piece in (text or "").strip().split("."):
        number = ""
        for char in piece:
            if char.isdigit():
                number += char
            else:
                break
        if not number:
            break
        parts.append(int(number))
    return tuple(parts)


def _ytdlp_is_current(version_text):
    """YouTube Music braucht mindestens yt-dlp 2026. Ältere Stände melden „The page needs to be reloaded“."""
    return _version_parts(version_text) >= (2026, 1, 1)


def _command_version(cmd):
    try:
        result = subprocess.run(
            list(cmd) + ["--version"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            return (result.stdout or result.stderr or "").strip()
    except Exception:
        return ""
    return ""


def _find_ytdlp_binary():
    """Eigenständiges yt-dlp (nicht python -m). Nur das liefert im .app laufenden Fortschritt."""
    candidates = []
    if platform.system() == "Darwin":
        candidates.extend([
            "/opt/homebrew/bin/yt-dlp",
            "/usr/local/bin/yt-dlp",
        ])
    elif platform.system() == "Windows":
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else ""
        if exe_dir:
            candidates.append(os.path.join(exe_dir, "yt-dlp.exe"))
    else:
        candidates.extend(["/usr/local/bin/yt-dlp", "/usr/bin/yt-dlp"])
    try:
        import shutil
        found = shutil.which("yt-dlp")
        if found:
            candidates.insert(0, found)
    except Exception:
        pass
    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            if _ytdlp_is_current(_command_version([path])):
                return [path]
    return None


def get_ytdlp_command():
    """
    Gibt den richtigen yt-dlp Befehl zurück
    
    Returns:
        Liste mit Befehl und Argumenten für subprocess.run
        Oder None wenn yt_dlp direkt als Modul verwendet werden sollte
    """
    if is_frozen():
        # Windows: 1) yt-dlp.exe neben der App, 2) gebündeltes Python (python/python.exe) aus Installer
        if platform.system() == 'Windows':
            exe_dir = os.path.dirname(sys.executable)
            ytdlp_exe = os.path.join(exe_dir, 'yt-dlp.exe')
            if os.path.isfile(ytdlp_exe):
                return [ytdlp_exe]
            python_embed = os.path.join(exe_dir, 'python', 'python.exe')
            if os.path.isfile(python_embed):
                return [python_embed, '-u', '-m', 'yt_dlp']
        # .app/.exe: externes yt-dlp als Prozess, sonst gibt es keinen Live-Fortschritt
        binary = _find_ytdlp_binary()
        if binary:
            return binary
        # Sonst: System-Python mit yt_dlp-Modul suchen (für Fortschritt/Abbruch per Subprocess)
        python_exe = _find_python_executable()
        if python_exe:
            return [python_exe, '-u', '-m', 'yt_dlp']
        # Fallback: eingebettetes yt_dlp-Modul (run_ytdlp_direct) — puffert die Ausgabe bis zum Ende
        return None
    else:
        # Nach .deb-Install: App läuft mit venv (dort yt-dlp>=2026). System-yt-dlp (2024) nicht verwenden.
        if _running_from_app_venv():
            return [sys.executable, '-u', '-m', 'yt_dlp']
        # Normale Umgebung: System-yt-dlp wenn im PATH, sonst Python-Modul
        if _check_ytdlp_system():
            return ['yt-dlp']
        return [sys.executable, '-u', '-m', 'yt_dlp']


def _find_python_executable():
    """Versucht Python-Executable zu finden (für .exe/.app Builds)"""
    possible_paths = []
    if platform.system() == 'Darwin':
        # macOS (.app): System-Python oder Homebrew, damit Subprocess-Fortschritt funktioniert
        possible_paths.extend([
            '/usr/bin/python3',
            '/opt/homebrew/bin/python3',
            '/usr/local/bin/python3',
        ])
    possible_paths.extend([
        os.path.join(os.path.dirname(sys.executable), 'python.exe'),
        'python.exe',
        'python3.exe',
        'python',
        'python3'
    ])
    # PATH-Prüfung (z. B. venv unter macOS)
    try:
        import shutil
        for name in ('python3', 'python'):
            p = shutil.which(name)
            if p and p not in possible_paths:
                possible_paths.insert(0, p)
    except Exception:
        pass

    _kwargs = dict(capture_output=True, timeout=2, check=True)
    if platform.system() == 'Windows':
        _kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    for path in possible_paths:
        try:
            # Prüfe ob Python verfügbar ist
            result = subprocess.run([path, '--version'], **_kwargs)
            # Prüfe ob yt_dlp verfügbar ist
            result2 = subprocess.run([path, '-m', 'yt_dlp', '--version'], **_kwargs)
            version = (result2.stdout or b"").decode("utf-8", "replace") if isinstance(result2.stdout, bytes) else (result2.stdout or "")
            if _ytdlp_is_current(version):
                return path
        except Exception:
            continue
    
    return None


def _check_ytdlp_system():
    """Prüft ob ein aktuelles yt-dlp als System-Befehl verfügbar ist."""
    return _ytdlp_is_current(_command_version(["yt-dlp"]))


def run_ytdlp(args, **kwargs):
    """
    Führt yt-dlp mit den gegebenen Argumenten aus
    
    Args:
        args: Liste mit yt-dlp Argumenten (ohne 'yt-dlp' selbst)
        **kwargs: Weitere Argumente für subprocess.run oder subprocess.Popen
    
    Returns:
        subprocess.CompletedProcess oder subprocess.Popen Ergebnis
        Oder FakeCompletedProcess in .exe Builds wenn direkte API verwendet wird
    """
    # Prüfe ob Popen gewünscht ist (für Prozessüberwachung)
    use_popen = kwargs.pop('use_popen', False)
    
    # Verstecke Konsolen-Fenster auf Windows (keine aufblitzenden CMD-Fenster)
    creation_flags = 0
    if platform.system() == 'Windows':
        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    
    # In .exe Builds: Synchrone Aufrufe (get_video_info, get_series_episodes) immer mit eingebetteter API.
    # Für Download (Popen): gebündeltes yt-dlp.exe oder System-Python nutzen, sonst eingebettete API.
    if is_frozen():
        if not use_popen:
            return run_ytdlp_direct(args, **kwargs)
        cmd = get_ytdlp_command()
        if cmd is not None:
            # Gebündeltes yt-dlp.exe oder gefundenes Python mit yt_dlp
            import subprocess as sp
            kwargs_with_flags = kwargs.copy()
            if creation_flags:
                kwargs_with_flags['creationflags'] = creation_flags
            if platform.system() != 'Windows':
                kwargs_with_flags['start_new_session'] = True
            return sp.Popen(cmd + args, **kwargs_with_flags)
        return _EmbeddedYtdlp(args, cwd=kwargs.get("cwd"))
    
    # Normale Python-Umgebung: Verwende subprocess
    cmd = get_ytdlp_command()
    if cmd is None:
        # Fallback: Versuche System-Befehl; -u = unbuffered für sofortige Ausgabe
        cmd = ['yt-dlp'] if _check_ytdlp_system() else [sys.executable, '-u', '-m', 'yt_dlp']
    
    if use_popen:
        import subprocess as sp
        kwargs_with_flags = kwargs.copy()
        if creation_flags:
            kwargs_with_flags['creationflags'] = creation_flags
        # Unix: Eigene Prozessgruppe, damit "Download abbrechen" nur yt-dlp beendet, nicht die ganze App
        if platform.system() != 'Windows':
            kwargs_with_flags['start_new_session'] = True
        return sp.Popen(cmd + args, **kwargs_with_flags)
    else:
        import subprocess as sp
        kwargs_with_flags = kwargs.copy()
        if creation_flags:
            kwargs_with_flags['creationflags'] = creation_flags
        return sp.run(cmd + args, **kwargs_with_flags)


class _QueueWriter:
    """Schreibt yt-dlp-Zeilen in eine Queue, damit der Fortschritt live ankommt."""

    def __init__(self, line_queue):
        self._queue = line_queue
        self._buf = ""

    def write(self, text):
        if not text:
            return
        self._buf += text.replace("\r\n", "\n").replace("\r", "\n")
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._queue.put(line + "\n")

    def flush(self):
        if self._buf:
            self._queue.put(self._buf + "\n")
            self._buf = ""

    def isatty(self):
        return False


class _LineReader:
    def __init__(self, line_queue):
        self._queue = line_queue

    def __iter__(self):
        while True:
            item = self._queue.get()
            if item is None:
                return
            yield item


class _EmbeddedYtdlp:
    """yt-dlp im Programm selbst, mit lesbarem Fortschritt wie bei einem eigenen Prozess."""

    def __init__(self, args, cwd=None):
        import queue
        import threading
        self._queue = queue.Queue()
        self.stdout = _LineReader(self._queue)
        self.returncode = None
        self.pid = -1
        self._cwd = cwd
        self._thread = threading.Thread(target=self._run, args=(list(args),), daemon=True)
        self._thread.start()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise subprocess.TimeoutExpired(["yt-dlp"], timeout)
        return 0 if self.returncode is None else self.returncode

    def terminate(self):
        if self.returncode is None:
            self.returncode = -1

    def kill(self):
        self.terminate()

    def _run(self, args):
        import yt_dlp
        writer = _QueueWriter(self._queue)
        old_argv = sys.argv
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        old_cwd = os.getcwd()
        try:
            if self._cwd:
                os.chdir(self._cwd)
            sys.argv = ["yt-dlp"] + args
            sys.stdout = writer
            sys.stderr = writer
            try:
                yt_dlp.main()
                code = 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            except Exception as exc:
                writer.write(str(exc) + "\n")
                code = 1
        finally:
            writer.flush()
            sys.argv = old_argv
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            try:
                os.chdir(old_cwd)
            except Exception:
                pass
            if self.returncode is None:
                self.returncode = code
            self._queue.put(None)


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
            _kw = kwargs.copy()
            if platform.system() == 'Windows':
                _kw['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            return subprocess.run([python_exe, '-m', 'yt_dlp'] + args, **_kw)
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
