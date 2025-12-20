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

# Import Version-Checker
try:
    from version import get_version, compare_versions, GITHUB_REPO_URL
    from updater import UpdateChecker
except ImportError:
    print("[ERROR] Konnte Version-Module nicht importieren")
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
        if not git_dir.exists():
            # Initialisiere Git-Repository
            subprocess.run(['git', 'init'], cwd=repo_path, check=True, timeout=10)
            subprocess.run(['git', 'remote', 'add', 'origin', repo_url], 
                          cwd=repo_path, check=True, timeout=10)
        
        # Hole neueste Änderungen
        subprocess.run(['git', 'fetch', 'origin', 'main'], 
                      cwd=repo_path, 
                      check=True, 
                      timeout=60)
        
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
            'venv'
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
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], 
                      cwd=repo_path, 
                      check=True, 
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
            'venv'
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
    
    # Prüfe auf Updates über Version
    try:
        checker = UpdateChecker()
        available, info = checker.check_for_updates()
        
        if available and info:
            latest_version = info.get('version', '')
            current_version = get_version()
            print(f"[INFO] Update verfügbar: {current_version} → {latest_version}")
        elif not force:
            print("[INFO] Keine Updates verfügbar")
            return False, "Bereits auf dem neuesten Stand"
    except Exception as e:
        print(f"[WARNING] Konnte Version nicht prüfen: {e}")
        if not force:
            # Wenn wir die Version nicht prüfen können, aber force=False, überspringe Update
            return False, "Konnte Version nicht prüfen"
    
    # Prüfe ob Git verfügbar ist
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
