#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Updater für Universal Downloader
Prüft auf Updates und ermöglicht automatische Installation
"""

import json
import os
import time
import requests
import sys
import platform
import subprocess
from pathlib import Path
from typing import Callable, Optional, Dict, Tuple
from version import get_version, compare_versions

APT_PACKAGE = "universal-downloader"

class UpdateChecker:
    """Klasse zum Prüfen und Installieren von Updates"""
    
    def __init__(self, update_url: Optional[str] = None, timeout: int = 10):
        """
        Initialisiert den Update-Checker
        
        Args:
            update_url: URL zur Update-Information (JSON oder GitHub API)
            timeout: Timeout für HTTP-Requests in Sekunden
        """
        from version import UPDATE_CHECK_URL
        self.update_url = update_url or UPDATE_CHECK_URL
        self.timeout = timeout
        self.current_version = get_version()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'UniversalDownloader/Updater'
        })
    
    def _check_apt_update(self) -> Optional[Dict]:
        """Linux: neuere Version im konfigurierten APT-Repo (ppa.plertanix.de)."""
        try:
            result = subprocess.run(
                ['apt-cache', 'policy', APT_PACKAGE],
                capture_output=True, text=True, timeout=20,
                env={**os.environ, 'LC_ALL': 'C'},
            )
            if result.returncode != 0:
                return None
            installed = candidate = None
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith('Installed:'):
                    installed = stripped.split(':', 1)[1].strip()
                elif stripped.startswith('Candidate:'):
                    candidate = stripped.split(':', 1)[1].strip()
            if not candidate or candidate in ('(none)', 'none'):
                return None
            if not installed or installed in ('(none)', 'none'):
                installed = '0.0.0'
            if compare_versions(installed, candidate) < 0:
                return {
                    'version': candidate,
                    'download_url': f'apt:{APT_PACKAGE}',
                    'changelog': '',
                    'release_date': '',
                    'release_url': 'https://ppa.plertanix.de/apt/',
                    'install_method': 'apt',
                }
        except (OSError, subprocess.SubprocessError):
            return None
        return None

    def _linux_uses_apt(self) -> bool:
        """True, wenn das Paket über APT installiert/kandidatisch ist (kein GitHub-.exe)."""
        try:
            result = subprocess.run(
                ['apt-cache', 'policy', APT_PACKAGE],
                capture_output=True, text=True, timeout=20,
                env={**os.environ, 'LC_ALL': 'C'},
            )
            if result.returncode != 0:
                return False
            for line in result.stdout.splitlines():
                stripped = line.strip()
                if stripped.startswith('Installed:') and '(none)' not in stripped:
                    return True
                if stripped.startswith('Candidate:') and '(none)' not in stripped and stripped.split(':', 1)[1].strip() not in ('none',):
                    return True
            return 'ppa.plertanix.de' in result.stdout
        except (OSError, subprocess.SubprocessError):
            return False

    def install_linux_update(self, deb_path: Optional[Path] = None) -> Tuple[bool, str]:
        """
        Installiert unter Linux per APT (Passwort-Dialog über pkexec).
        deb_path nur als Fallback, wenn es wirklich ein .deb ist.
        """
        pkexec = shutil_which('pkexec')
        if not pkexec:
            return False, (
                "pkexec fehlt. Bitte im Terminal:\n"
                "sudo apt update && sudo apt install --only-upgrade universal-downloader"
            )

        if deb_path and deb_path.is_file() and _is_debian_package(deb_path):
            cmd = [pkexec, 'apt-get', 'install', '-y', str(deb_path)]
        else:
            cmd = [
                pkexec, '/bin/bash', '-lc',
                'export DEBIAN_FRONTEND=noninteractive; '
                'apt-get update -qq && apt-get install -y universal-downloader',
            ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            return False, "Zeitüberschreitung bei der Installation."
        except OSError as exc:
            return False, str(exc)
        output = ((result.stderr or '') + '\n' + (result.stdout or '')).strip()
        if result.returncode == 0:
            return True, output
        return False, output or f"Exit-Code {result.returncode}"

    def check_for_updates(self) -> Tuple[bool, Optional[Dict]]:
        """
        Prüft auf verfügbare Updates
        
        Returns:
            Tuple (update_available, update_info)
            update_info enthält: version, download_url, changelog, release_date
        """
        # Linux mit APT-Paket: nur das Repo, nie GitHub ohne .deb (sonst Windows-Release-Warnung)
        if platform.system().lower() == 'linux':
            apt_info = self._check_apt_update()
            if apt_info:
                return True, apt_info
            if self._linux_uses_apt():
                return False, None

        try:
            response = self.session.get(self.update_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Prüfe ob es GitHub API oder eigene JSON ist
            data = response.json()
            
            if 'tag_name' in data:
                # GitHub Releases Format
                latest_version = data['tag_name'].lstrip('v').lstrip('.')
                download_url = None
                
                # Suche nach passender Asset-Datei
                assets = data.get('assets', [])
                system = platform.system().lower()
                
                if system == 'windows':
                    # Zuerst den Installer, danach eine Programm-.exe.
                    download_url = None
                    plain_exe = None
                    any_exe = None
                    for asset in assets:
                        name = asset['name']
                        if not name.endswith('.exe'):
                            continue
                        url = asset['browser_download_url']
                        if any_exe is None:
                            any_exe = url
                        if 'UniversalDownloader' not in name:
                            continue
                        if 'setup' in name.lower():
                            download_url = url
                            break
                        if plain_exe is None:
                            plain_exe = url
                    if not download_url:
                        download_url = plain_exe or any_exe
                elif system == 'linux':
                    # Nur echte .deb-Dateien – niemals Windows-.exe als Linux-Update
                    for asset in assets:
                        name = asset['name'].lower()
                        if name.endswith('.deb') and 'universal-downloader' in name:
                            download_url = asset['browser_download_url']
                            break
                    if not download_url:
                        for asset in assets:
                            if asset['name'].endswith('.deb'):
                                download_url = asset['browser_download_url']
                                break
                elif system == 'darwin':
                    # Passende .dmg: Apple Silicon vs. Intel
                    mach = platform.machine().lower()
                    apple = mach in ("arm64", "aarch64")
                    ranked = []
                    for asset in assets:
                        name = asset["name"].lower()
                        if not name.endswith((".dmg", ".pkg")):
                            continue
                        if apple:
                            if "arm64" in name or "aarch64" in name:
                                rank = 0
                            elif "x86_64" in name or "intel" in name:
                                rank = 2
                            else:
                                rank = 1
                        else:
                            if "x86_64" in name or "intel" in name:
                                rank = 0
                            elif "arm64" in name or "aarch64" in name:
                                rank = 2
                            else:
                                rank = 1
                        ranked.append((rank, asset))
                    ranked.sort(key=lambda x: x[0])
                    if ranked:
                        download_url = ranked[0][1]["browser_download_url"]
                
                update_info = {
                    'version': latest_version,
                    'download_url': download_url,
                    'changelog': data.get('body', ''),
                    'release_date': data.get('published_at', ''),
                    'release_url': data.get('html_url', ''),
                    'assets': assets  # Für Debugging
                }
            else:
                # Eigene JSON-Struktur
                latest_version = data.get('version', '')
                update_info = {
                    'version': latest_version,
                    'download_url': data.get('download_url', ''),
                    'changelog': data.get('changelog', ''),
                    'release_date': data.get('release_date', ''),
                    'release_url': data.get('release_url', '')
                }
            
            # Vergleiche Versionen
            if latest_version and compare_versions(self.current_version, latest_version) < 0:
                return True, update_info
            else:
                return False, None
                
        except requests.exceptions.RequestException as e:
            # Netzwerkfehler - keine Updates verfügbar oder Server nicht erreichbar
            return False, None
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            # Ungültiges Format
            return False, None
    
    def download_update(
        self,
        download_url: str,
        save_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """
        Lädt ein Update herunter.

        progress_callback(bereits_bytes, gesamt_bytes) wird während des Ladens
        aufgerufen. gesamt_bytes ist 0, wenn der Server keine Größe nennt.
        """
        if not download_url:
            return False
        if download_url.startswith('apt:'):
            return True
        
        try:
            if save_path is None:
                # Standard-Pfad: Downloads-Ordner
                save_path = Path.home() / "Downloads" / f"UniversalDownloader_Update_{self.current_version}.exe"
            
            response = self.session.get(download_url, timeout=(20, 120), stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            last_report = 0.0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        now = time.monotonic()
                        if progress_callback and (now - last_report >= 0.3 or downloaded == total_size):
                            last_report = now
                            progress_callback(downloaded, total_size)
            if downloaded < 1024:
                return False
            with open(save_path, 'rb') as fh:
                if fh.read(2) != b'MZ':
                    return False
            return True
            
        except requests.exceptions.RequestException:
            return False
        except IOError:
            return False
    
    def is_update_available(self) -> bool:
        """Kurze Prüfung ob ein Update verfügbar ist"""
        available, _ = self.check_for_updates()
        return available


def shutil_which(cmd: str) -> Optional[str]:
    from shutil import which
    return which(cmd)


def _is_debian_package(path: Path) -> bool:
    try:
        with open(path, 'rb') as fh:
            return fh.read(8).startswith(b'!<arch>\n')
    except OSError:
        return False


def check_updates_simple() -> Tuple[bool, Optional[str]]:
    """
    Einfache Update-Prüfung (für schnelle Checks)
    
    Returns:
        Tuple (update_available, latest_version)
    """
    checker = UpdateChecker()
    available, info = checker.check_for_updates()
    if available and info:
        return True, info.get('version')
    return False, None


if __name__ == "__main__":
    # Test-Modus
    print(f"Aktuelle Version: {get_version()}")
    print("Prüfe auf Updates...")
    
    checker = UpdateChecker()
    available, info = checker.check_for_updates()
    
    if available:
        print(f"✓ Update verfügbar: {info['version']}")
        print(f"  Download: {info.get('download_url', 'N/A')}")
        if info.get('changelog'):
            print(f"  Changelog: {info['changelog'][:100]}...")
    else:
        print("✓ Keine Updates verfügbar")
