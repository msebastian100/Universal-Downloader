#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Auto-Updater für Universal Downloader
Prüft auf Updates und aktualisiert das Repository automatisch
"""

import sys
import os
import platform
import subprocess
import shutil
import zipfile
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import json
import time

# Füge das Skript-Verzeichnis zum Python-Pfad hinzu (für Imports)
# Mehrere Methoden, um das Skript-Verzeichnis zu finden
script_dir = None

# Methode 1: __file__ (funktioniert normalerweise)
try:
    if __file__:
        script_dir = Path(__file__).parent.absolute()
except (NameError, AttributeError):
    pass

# Methode 2: sys.argv[0] (Fallback)
if script_dir is None or not script_dir.exists():
    try:
        script_dir = Path(sys.argv[0]).parent.absolute()
    except (IndexError, AttributeError):
        pass

# Methode 3: Aktuelles Arbeitsverzeichnis (letzter Fallback)
if script_dir is None or not script_dir.exists():
    script_dir = Path.cwd()

# Stelle sicher, dass das Arbeitsverzeichnis das Skript-Verzeichnis ist
try:
    os.chdir(str(script_dir))
except (OSError, PermissionError):
    pass

# Füge zum Python-Pfad hinzu
if script_dir and str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

# Prüfe ob die benötigten Dateien existieren
version_file = script_dir / "version.py"
updater_file = script_dir / "updater.py"

# Debug-Ausgabe (sofort, damit sie sichtbar ist)
import sys as sys_module
sys_module.stdout.flush()
sys_module.stderr.flush()

print(f"[DEBUG] ==========================================", flush=True)
print(f"[DEBUG] Update-Skript Debug-Informationen", flush=True)
print(f"[DEBUG] ==========================================", flush=True)
print(f"[DEBUG] Skript-Verzeichnis: {script_dir}", flush=True)
print(f"[DEBUG] Skript-Verzeichnis existiert: {script_dir.exists() if script_dir else False}", flush=True)
print(f"[DEBUG] Aktuelles Arbeitsverzeichnis: {os.getcwd()}", flush=True)
print(f"[DEBUG] Python-Pfad (erste 5): {sys.path[:5]}", flush=True)
print(f"[DEBUG] version.py existiert: {version_file.exists()}", flush=True)
if version_file.exists():
    print(f"[DEBUG] version.py Pfad: {version_file}", flush=True)
    print(f"[DEBUG] version.py Größe: {version_file.stat().st_size} Bytes", flush=True)
print(f"[DEBUG] updater.py existiert: {updater_file.exists()}", flush=True)
if updater_file.exists():
    print(f"[DEBUG] updater.py Pfad: {updater_file}", flush=True)
    print(f"[DEBUG] updater.py Größe: {updater_file.stat().st_size} Bytes", flush=True)
print(f"[DEBUG] ==========================================", flush=True)

# Import Version-Checker
print(f"[DEBUG] Versuche Import von version und updater...", flush=True)

# Versuche zuerst direkten Import über importlib (robuster)
import importlib.util

# Importiere version.py
version_imported = False
if version_file.exists():
    try:
        print(f"[DEBUG] Lade version.py direkt über importlib...", flush=True)
        spec = importlib.util.spec_from_file_location("version", str(version_file))
        if spec and spec.loader:
            version_module = importlib.util.module_from_spec(spec)
            sys.modules['version'] = version_module
            spec.loader.exec_module(version_module)
            # Importiere aus dem Modul
            get_version = version_module.get_version
            compare_versions = version_module.compare_versions
            GITHUB_REPO_URL = version_module.GITHUB_REPO_URL
            version_imported = True
            print(f"[DEBUG] ✓ version.py direkt geladen", flush=True)
    except Exception as e:
        print(f"[DEBUG] Direkter Import fehlgeschlagen: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)

# Fallback: Normaler Import
if not version_imported:
    try:
        from version import get_version, compare_versions, GITHUB_REPO_URL
        version_imported = True
        print(f"[DEBUG] ✓ version.py über normalen Import geladen", flush=True)
    except ImportError as e:
        print(f"[DEBUG] ✗ version.py Import fehlgeschlagen: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)

# Importiere updater.py
updater_imported = False
if updater_file.exists():
    try:
        print(f"[DEBUG] Lade updater.py direkt über importlib...", flush=True)
        spec = importlib.util.spec_from_file_location("updater", str(updater_file))
        if spec and spec.loader:
            updater_module = importlib.util.module_from_spec(spec)
            sys.modules['updater'] = updater_module
            spec.loader.exec_module(updater_module)
            # Importiere aus dem Modul
            UpdateChecker = updater_module.UpdateChecker
            updater_imported = True
            print(f"[DEBUG] ✓ updater.py direkt geladen", flush=True)
    except Exception as e:
        print(f"[DEBUG] Direkter Import fehlgeschlagen: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)

# Fallback: Normaler Import
if not updater_imported:
    try:
        from updater import UpdateChecker
        updater_imported = True
        print(f"[DEBUG] ✓ updater.py über normalen Import geladen", flush=True)
    except ImportError as e:
        print(f"[DEBUG] ✗ updater.py Import fehlgeschlagen: {e}", flush=True)
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}", flush=True)

# Prüfe ob beide Module importiert wurden
if not version_imported or not updater_imported:
    e_msg = "Version-Module nicht importiert: "
    if not version_imported:
        e_msg += "version.py fehlt; "
    if not updater_imported:
        e_msg += "updater.py fehlt; "
    print(f"[ERROR] {e_msg}", flush=True)
    print(f"[DEBUG] Finale Prüfung:", flush=True)
    print(f"[DEBUG]   version_imported: {version_imported}", flush=True)
    print(f"[DEBUG]   updater_imported: {updater_imported}", flush=True)
    print(f"[DEBUG]   version_file.exists(): {version_file.exists()}", flush=True)
    print(f"[DEBUG]   updater_file.exists(): {updater_file.exists()}", flush=True)
    print(f"[DEBUG] Python-Pfad: {sys.path}", flush=True)
    print(f"[DEBUG] Skript-Verzeichnis: {script_dir}", flush=True)
    print(f"[DEBUG] Aktuelles Arbeitsverzeichnis: {os.getcwd()}", flush=True)
    print(f"[DEBUG] __file__: {__file__ if '__file__' in globals() else 'N/A'}", flush=True)
    print(f"[DEBUG] sys.argv[0]: {sys.argv[0] if len(sys.argv) > 0 else 'N/A'}", flush=True)
    
    # Versuche version.py direkt zu finden
    if version_file.exists():
        print(f"[DEBUG] version.py Pfad: {version_file}", flush=True)
        print(f"[DEBUG] version.py Größe: {version_file.stat().st_size} Bytes", flush=True)
    else:
        print(f"[DEBUG] ✗ version.py nicht gefunden in: {script_dir}", flush=True)
        # Suche in anderen Verzeichnissen
        for search_dir in [Path.cwd(), Path.home(), Path(__file__).parent if '__file__' in globals() else None]:
            if search_dir and search_dir.exists():
                test_version = search_dir / "version.py"
                if test_version.exists():
                    print(f"[DEBUG] version.py gefunden in: {test_version}", flush=True)
                    if str(search_dir) not in sys.path:
                        sys.path.insert(0, str(search_dir))
                    try:
                        from version import get_version, compare_versions, GITHUB_REPO_URL
                        from updater import UpdateChecker
                        print(f"[DEBUG] ✓ Module erfolgreich importiert nach Pfad-Erweiterung", flush=True)
                        version_imported = True
                        updater_imported = True
                        break
                    except ImportError as e:
                        print(f"[DEBUG] Import nach Pfad-Erweiterung fehlgeschlagen: {e}", flush=True)
    
    if updater_file.exists():
        print(f"[DEBUG] updater.py Pfad: {updater_file}", flush=True)
    else:
        print(f"[DEBUG] ✗ updater.py nicht gefunden in: {script_dir}", flush=True)
    
    # Wenn immer noch nicht importiert, beende mit Fehler
    if not version_imported or not updater_imported:
        print(f"[ERROR] Import endgültig fehlgeschlagen", flush=True)
        sys.exit(1)


def check_git_available() -> bool:
    """Prüft ob Git verfügbar ist"""
    try:
        subprocess.run(['git', '--version'], 
                      capture_output=True, 
                      check=True,
                      timeout=5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_current_commit_hash(repo_path: Path) -> Optional[str]:
    """Gibt den aktuellen Git-Commit-Hash zurück"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_latest_commit_hash(repo_url: str) -> Optional[str]:
    """Ruft den neuesten Commit-Hash von GitHub ab"""
    try:
        # Verwende GitHub API
        import requests
        api_url = repo_url.replace('https://github.com/', 'https://api.github.com/repos/')
        if not api_url.endswith('/'):
            api_url += '/'
        api_url += 'commits/main'
        
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('sha', '').strip()
    except Exception:
        return None


def update_via_git(repo_path: Path, repo_url: str) -> Tuple[bool, str]:
    """
    Aktualisiert das Repository über Git
    
    Returns:
        (success, message)
    """
    try:
        # Prüfe ob es bereits ein Git-Repository ist
        git_dir = repo_path / '.git'
        is_new_repo = False
        if not git_dir.exists():
            # Initialisiere Git-Repository
            subprocess.run(['git', 'init'], cwd=repo_path, check=True, timeout=10)
            # Prüfe ob remote bereits existiert
            check_remote = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if check_remote.returncode != 0:
                subprocess.run(['git', 'remote', 'add', 'origin', repo_url], 
                              cwd=repo_path, check=True, timeout=10)
            else:
                # Remote existiert bereits, aktualisiere URL falls nötig
                subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], 
                              cwd=repo_path, check=True, timeout=10)
            is_new_repo = True
        
        # Hole neueste Änderungen
        subprocess.run(['git', 'fetch', 'origin', 'main'], 
                      cwd=repo_path, 
                      check=True, 
                      timeout=60)
        
        # Prüfe ob lokaler HEAD existiert
        head_check = subprocess.run(
            ['git', 'rev-parse', '--verify', 'HEAD'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        has_local_head = (head_check.returncode == 0)
        
        if not has_local_head or is_new_repo:
            # Kein lokaler HEAD -> Update definitiv nötig
            print("[INFO] Lokales Repository hat noch keinen Commit - Update erforderlich")
            # Erstelle lokalen Branch und setze auf origin/main
            branch_check = subprocess.run(
                ['git', 'branch', '--show-current'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if branch_check.returncode != 0 or not branch_check.stdout.strip():
                # Kein lokaler Branch, erstelle main Branch
                subprocess.run(['git', 'branch', 'main', 'origin/main'], 
                              cwd=repo_path, check=False, timeout=5)
                subprocess.run(['git', 'checkout', 'main'], 
                              cwd=repo_path, check=False, timeout=5)
        else:
            # Prüfe ob Updates verfügbar sind
            result = subprocess.run(
                ['git', 'rev-list', 'HEAD..origin/main', '--count'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                commits_behind = int(result.stdout.strip())
                if commits_behind == 0:
                    return True, "Bereits auf dem neuesten Stand"
        
        # Erstelle Backup wichtiger Dateien
        backup_dir = repo_path / '.update_backup'
        backup_dir.mkdir(exist_ok=True)
        
        important_files = [
            'settings.json',
            'Downloads',
            '.deezer_config.json',
            'ffmpeg',
            'venv',
            'vbs.log.txt',  # VBS-Launcher Log-Datei (kann während Update geöffnet sein)
            'logs'  # Log-Verzeichnis
        ]
        
        for item in important_files:
            src = repo_path / item
            if src.exists():
                dst = backup_dir / item
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        
        # Führe Hard-Reset durch (überschreibt lokale Änderungen)
        # Ignoriere Fehler bei geöffneten Dateien (z.B. vbs.log.txt, venv-Dateien)
        reset_result = subprocess.run(['git', 'reset', '--hard', 'origin/main'], 
                                      cwd=repo_path, 
                                      capture_output=True,
                                      text=True,
                                      timeout=30)
        if reset_result.returncode != 0:
            # Wenn Reset fehlschlägt (z.B. wegen geöffneter Dateien), versuche sanftere Methoden
            print("[WARNING] git reset --hard fehlgeschlagen, versuche sanftere Methode...")
            stderr_lower = reset_result.stderr.lower()
            
            # Prüfe ob es wegen geöffneter Dateien ist
            if 'unlink' in stderr_lower or 'zugriff verweigert' in stderr_lower or 'access denied' in stderr_lower:
                print("[INFO] Dateien sind geöffnet (z.B. vbs.log.txt oder venv) - überspringe diese beim Reset")
                
                # Prüfe ob lokaler HEAD existiert
                head_check = subprocess.run(
                    ['git', 'rev-parse', '--verify', 'HEAD'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                has_local_head = (head_check.returncode == 0)
                
                if has_local_head:
                    # HEAD existiert - verwende checkout für einzelne Dateien
                    # Versuche checkout ohne die problematischen Dateien
                    checkout_result = subprocess.run(
                        ['git', 'checkout', 'origin/main', '--', '.'], 
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if checkout_result.returncode == 0:
                        print("[INFO] git checkout erfolgreich (einige Dateien wurden übersprungen)")
                    else:
                        print(f"[WARNING] git checkout fehlgeschlagen: {checkout_result.stderr[:200]}")
                    
                    # Versuche geöffnete Dateien aus dem Index zu entfernen (nur wenn HEAD existiert)
                    locked_files = ['vbs.log.txt']
                    for locked_file in locked_files:
                        locked_path = repo_path / locked_file
                        if locked_path.exists():
                            reset_head_result = subprocess.run(
                                ['git', 'reset', 'HEAD', locked_file], 
                                cwd=repo_path,
                                capture_output=True,
                                timeout=5
                            )
                            if reset_head_result.returncode == 0:
                                print(f"[INFO] {locked_file} aus Index entfernt")
                else:
                    # Kein HEAD - verwende checkout mit -f (force)
                    print("[INFO] Kein lokaler HEAD - verwende git checkout -f")
                    checkout_result = subprocess.run(
                        ['git', 'checkout', '-f', 'origin/main'], 
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if checkout_result.returncode != 0:
                        print(f"[WARNING] git checkout -f fehlgeschlagen: {checkout_result.stderr[:200]}")
            else:
                # Bei anderen Fehlern, versuche es nochmal
                print(f"[WARNING] Unbekannter Fehler: {reset_result.stderr[:200]}")
                subprocess.run(['git', 'reset', '--hard', 'origin/main'], 
                              cwd=repo_path,
                              capture_output=True,
                              timeout=30)
        
        # Stelle wichtige Dateien wieder her
        for item in important_files:
            src = backup_dir / item
            dst = repo_path / item
            if src.exists():
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        
        # Lösche Backup
        shutil.rmtree(backup_dir, ignore_errors=True)
        
        return True, "Erfolgreich aktualisiert"
        
    except subprocess.CalledProcessError as e:
        return False, f"Git-Fehler: {e}"
    except Exception as e:
        return False, f"Fehler: {e}"


def update_via_zip(repo_path: Path, repo_url: str) -> Tuple[bool, str]:
    """
    Aktualisiert das Repository über ZIP-Download
    
    Returns:
        (success, message)
    """
    try:
        import requests
        import tempfile
        
        # GitHub ZIP-URL
        zip_url = repo_url.replace('https://github.com/', 'https://github.com/')
        if not zip_url.endswith('/'):
            zip_url += '/'
        zip_url += 'archive/refs/heads/main.zip'
        
        # Erstelle temporäres Verzeichnis
        temp_dir = Path(tempfile.mkdtemp())
        zip_path = temp_dir / 'update.zip'
        
        print(f"[INFO] Lade Update von GitHub herunter...")
        response = requests.get(zip_url, stream=True, timeout=300)
        response.raise_for_status()
        
        # Download ZIP
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        percent = (downloaded * 100) // total_size
                        print(f"\r[INFO] Download: {percent}%", end='', flush=True)
        
        print()  # Neue Zeile
        
        # Erstelle Backup wichtiger Dateien
        backup_dir = repo_path / '.update_backup'
        backup_dir.mkdir(exist_ok=True)
        
        important_files = [
            'settings.json',
            'Downloads',
            '.deezer_config.json',
            'ffmpeg',
            'venv',
            'vbs.log.txt',  # VBS-Launcher Log-Datei (kann während Update geöffnet sein)
            'logs'  # Log-Verzeichnis
        ]
        
        for item in important_files:
            src = repo_path / item
            if src.exists():
                dst = backup_dir / item
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        
        # Entpacke ZIP
        extract_dir = temp_dir / 'extract'
        extract_dir.mkdir()
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Finde das entpackte Verzeichnis (normalerweise Universal-Downloader-main)
        extracted_dirs = list(extract_dir.iterdir())
        if not extracted_dirs:
            return False, "Keine Dateien im ZIP gefunden"
        
        source_dir = extracted_dirs[0]
        
        # Überschreibe Dateien (außer wichtigen)
        for item in source_dir.iterdir():
            if item.name.startswith('.'):
                continue
            
            dst = repo_path / item.name
            
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                if dst.exists():
                    dst.unlink()
                shutil.copy2(item, dst)
        
        # Stelle wichtige Dateien wieder her
        for item in important_files:
            src = backup_dir / item
            dst = repo_path / item
            if src.exists():
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        
        # Aufräumen
        shutil.rmtree(temp_dir, ignore_errors=True)
        shutil.rmtree(backup_dir, ignore_errors=True)
        
        return True, "Erfolgreich aktualisiert"
        
    except Exception as e:
        return False, f"Fehler: {e}"


def check_and_update(repo_path: Optional[Path] = None, 
                     repo_url: str = GITHUB_REPO_URL,
                     force: bool = False) -> Tuple[bool, str]:
    """
    Prüft auf Updates und aktualisiert wenn nötig
    
    Args:
        repo_path: Pfad zum Repository (Standard: Aktuelles Verzeichnis)
        repo_url: GitHub Repository URL
        force: Wenn True, aktualisiere auch wenn keine neuen Versionen verfügbar sind
    
    Returns:
        (updated, message)
    """
    if repo_path is None:
        repo_path = Path(__file__).parent
    
    repo_path = Path(repo_path).resolve()
    
    print(f"[INFO] Prüfe auf Updates...")
    print(f"[INFO] Repository-Pfad: {repo_path}")
    print(f"[INFO] Repository-URL: {repo_url}")
    
    # Prüfe zuerst auf Git-Commits (unabhängig von Releases)
    # Das ermöglicht Updates auch ohne neue Release-Version
    update_needed = False
    version_update_info = None
    
    if check_git_available():
        print("[INFO] Prüfe auf Git-Commits...")
        try:
            # Initialisiere Git-Repository falls nötig
            git_dir = repo_path / '.git'
            is_new_repo = False
            
            # Prüfe ob es ein vollständiges Git-Repository ist
            # Ein vollständiges Repository hat einen HEAD oder einen refs/heads Branch
            has_valid_repo = False
            if git_dir.exists():
                # Prüfe ob HEAD auf einen gültigen Commit zeigt
                head_check_pre = subprocess.run(
                    ['git', 'rev-parse', '--verify', 'HEAD'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                has_valid_repo = (head_check_pre.returncode == 0)
                print(f"[DEBUG] Git-Verzeichnis existiert: {git_dir.exists()}, has_valid_repo: {has_valid_repo}")
            
            if not git_dir.exists() or not has_valid_repo:
                if not has_valid_repo and git_dir.exists():
                    print("[INFO] Git-Repository ist unvollständig - initialisiere neu...")
                    # Versuche zuerst, index.lock zu löschen (kann Git-Operationen blockieren)
                    index_lock = git_dir / 'index.lock'
                    if index_lock.exists():
                        try:
                            import time
                            import os
                            # Warte kurz, falls die Datei gerade geschrieben wird
                            time.sleep(0.5)
                            index_lock.unlink()
                            print("[INFO] index.lock Datei gelöscht")
                        except Exception as e:
                            print(f"[WARNING] Konnte index.lock nicht löschen: {e}")
                    
                    # Lösche unvollständiges .git Verzeichnis
                    import shutil
                    try:
                        shutil.rmtree(git_dir)
                        print("[INFO] Unvollständiges .git Verzeichnis gelöscht")
                    except Exception as e:
                        print(f"[WARNING] Konnte .git nicht löschen: {e}")
                        # Versuche erneut, index.lock zu löschen und dann nochmal
                        if index_lock.exists():
                            try:
                                index_lock.unlink()
                                shutil.rmtree(git_dir)
                                print("[INFO] .git Verzeichnis nach Löschen von index.lock gelöscht")
                            except Exception as e2:
                                print(f"[WARNING] Konnte .git auch nach Löschen von index.lock nicht löschen: {e2}")
                
                print("[INFO] Initialisiere Git-Repository...")
                if not git_dir.exists():
                    subprocess.run(['git', 'init'], cwd=repo_path, check=True, timeout=10)
                
                # Prüfe ob remote bereits existiert
                check_remote = subprocess.run(
                    ['git', 'remote', 'get-url', 'origin'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if check_remote.returncode != 0:
                    # Remote existiert nicht, füge ihn hinzu
                    add_remote_result = subprocess.run(
                        ['git', 'remote', 'add', 'origin', repo_url], 
                        cwd=repo_path, 
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if add_remote_result.returncode != 0:
                        # Wenn add fehlschlägt, könnte der Remote bereits existieren (aber get-url hat fehlgeschlagen)
                        # Versuche set-url stattdessen
                        print(f"[WARNING] git remote add fehlgeschlagen: {add_remote_result.stderr}")
                        print("[INFO] Versuche git remote set-url stattdessen...")
                        subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], 
                                      cwd=repo_path, 
                                      capture_output=True,
                                      timeout=10)
                else:
                    # Remote existiert bereits, aktualisiere URL falls nötig
                    subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], 
                                  cwd=repo_path, 
                                  capture_output=True,
                                  timeout=10)
                is_new_repo = True
                print(f"[DEBUG] is_new_repo gesetzt auf: {is_new_repo}")
            
            # Hole neueste Änderungen
            print("[INFO] Hole neueste Änderungen von GitHub...")
            fetch_result = subprocess.run(
                ['git', 'fetch', 'origin', 'main'], 
                cwd=repo_path, 
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if fetch_result.returncode != 0:
                print(f"[WARNING] Git fetch fehlgeschlagen: {fetch_result.stderr}")
            else:
                # Prüfe ob lokaler HEAD existiert
                head_check = subprocess.run(
                    ['git', 'rev-parse', '--verify', 'HEAD'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                has_local_head = (head_check.returncode == 0)
                
                # Debug-Ausgabe
                print(f"[DEBUG] is_new_repo: {is_new_repo}, has_local_head: {has_local_head}")
                
                # Wenn Repository neu initialisiert wurde ODER kein HEAD existiert -> Update definitiv nötig
                if is_new_repo:
                    print("[INFO] Repository wurde neu initialisiert - Update erforderlich")
                    update_needed = True
                elif not has_local_head:
                    print("[INFO] Lokales Repository hat noch keinen Commit - Update erforderlich")
                    update_needed = True
                else:
                    # Prüfe ob neue Commits verfügbar sind
                    result = subprocess.run(
                        ['git', 'rev-list', 'HEAD..origin/main', '--count'],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        commits_behind = int(result.stdout.strip())
                        print(f"[DEBUG] Commits hinter origin/main: {commits_behind}")
                        if commits_behind > 0:
                            update_needed = True
                            print(f"[INFO] {commits_behind} neue Commit(s) verfügbar")
                        else:
                            print("[INFO] Keine neuen Commits verfügbar")
                    else:
                        print(f"[DEBUG] git rev-list fehlgeschlagen: {result.stderr}")
                        # Fallback: Prüfe ob HEAD und origin/main unterschiedlich sind
                        local_hash = subprocess.run(
                            ['git', 'rev-parse', 'HEAD'],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        remote_hash = subprocess.run(
                            ['git', 'rev-parse', 'origin/main'],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        
                        if local_hash.returncode == 0 and remote_hash.returncode == 0:
                            local_commit = local_hash.stdout.strip()
                            remote_commit = remote_hash.stdout.strip()
                            print(f"[DEBUG] Lokaler Commit: {local_commit[:8]}...")
                            print(f"[DEBUG] Remote Commit: {remote_commit[:8]}...")
                            if local_commit != remote_commit:
                                update_needed = True
                                print("[INFO] Lokaler und Remote-Commit unterscheiden sich - Update erforderlich")
                            else:
                                print("[INFO] Bereits auf dem neuesten Stand")
                        else:
                            # Wenn wir den Remote-Hash nicht bekommen können, aber HEAD existiert, 
                            # nehmen wir an, dass ein Update nötig ist (sicherer Fall)
                            if remote_hash.returncode != 0:
                                print("[WARNING] Konnte Remote-Hash nicht ermitteln - Update wird durchgeführt")
                                update_needed = True
                
                print(f"[DEBUG] update_needed nach Git-Prüfung: {update_needed}")
        except Exception as e:
            print(f"[WARNING] Konnte Git-Status nicht prüfen: {e}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    # Prüfe zusätzlich auf Version-Updates (als Information)
    try:
        checker = UpdateChecker()
        available, info = checker.check_for_updates()
        
        if available and info:
            latest_version = info.get('version', '')
            current_version = get_version()
            version_update_info = f"{current_version} → {latest_version}"
            print(f"[INFO] Version-Update verfügbar: {current_version} → {latest_version}")
            if not update_needed:
                update_needed = True
    except Exception as e:
        print(f"[WARNING] Konnte Version nicht prüfen: {e}")
    
    # Wenn kein Update benötigt wird und force=False, beende
    if not update_needed and not force:
        print("[INFO] Keine Updates verfügbar")
        return False, "Bereits auf dem neuesten Stand"
    
    # Führe Update durch
    if check_git_available():
        print("[INFO] Verwende Git für Update...")
        success, message = update_via_git(repo_path, repo_url)
    else:
        print("[INFO] Git nicht verfügbar, verwende ZIP-Download...")
        success, message = update_via_zip(repo_path, repo_url)
    
    if success:
        print(f"[OK] {message}")
        return True, message
    else:
        print(f"[ERROR] {message}")
        return False, message


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='GitHub Auto-Updater für Universal Downloader')
    parser.add_argument('--force', action='store_true', 
                       help='Aktualisiere auch wenn keine neuen Versionen verfügbar sind')
    parser.add_argument('--path', type=str, 
                       help='Pfad zum Repository (Standard: Aktuelles Verzeichnis)')
    
    args = parser.parse_args()
    
    repo_path = Path(args.path) if args.path else None
    
    updated, message = check_and_update(repo_path=repo_path, force=args.force)
    
    if updated:
        print("\n[OK] Update erfolgreich abgeschlossen!")
        print("[INFO] Bitte starten Sie die Anwendung neu.")
        sys.exit(0)
    else:
        print(f"\n[INFO] {message}")
        sys.exit(1)
