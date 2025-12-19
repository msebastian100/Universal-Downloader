#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-Updater für Universal Downloader
Prüft auf Updates und ermöglicht automatische Installation
"""

import json
import requests
import sys
import platform
from pathlib import Path
from typing import Optional, Dict, Tuple
from version import get_version, compare_versions

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
    
    def check_for_updates(self) -> Tuple[bool, Optional[Dict]]:
        """
        Prüft auf verfügbare Updates
        
        Returns:
            Tuple (update_available, update_info)
            update_info enthält: version, download_url, changelog, release_date
        """
        try:
            response = self.session.get(self.update_url, timeout=self.timeout)
            response.raise_for_status()
            
            # Prüfe ob es GitHub API oder eigene JSON ist
            data = response.json()
            
            if 'tag_name' in data:
                # GitHub Releases Format
                latest_version = data['tag_name'].lstrip('v')
                download_url = None
                
                # Suche nach passender Asset-Datei
                assets = data.get('assets', [])
                system = platform.system().lower()
                
                if system == 'windows':
                    # Suche nach .exe
                    for asset in assets:
                        if asset['name'].endswith('.exe'):
                            download_url = asset['browser_download_url']
                            break
                elif system == 'linux':
                    # Suche nach .deb
                    for asset in assets:
                        if asset['name'].endswith('.deb'):
                            download_url = asset['browser_download_url']
                            break
                elif system == 'darwin':
                    # Suche nach .dmg oder .pkg
                    for asset in assets:
                        if asset['name'].endswith(('.dmg', '.pkg')):
                            download_url = asset['browser_download_url']
                            break
                
                update_info = {
                    'version': latest_version,
                    'download_url': download_url,
                    'changelog': data.get('body', ''),
                    'release_date': data.get('published_at', ''),
                    'release_url': data.get('html_url', '')
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
    
    def download_update(self, download_url: str, save_path: Optional[Path] = None) -> bool:
        """
        Lädt ein Update herunter
        
        Args:
            download_url: URL zum Download
            save_path: Pfad zum Speichern (optional)
        
        Returns:
            True wenn erfolgreich, False sonst
        """
        if not download_url:
            return False
        
        try:
            if save_path is None:
                # Standard-Pfad: Downloads-Ordner
                save_path = Path.home() / "Downloads" / f"UniversalDownloader_Update_{self.current_version}.exe"
            
            response = self.session.get(download_url, timeout=300, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            return True
            
        except requests.exceptions.RequestException:
            return False
        except IOError:
            return False
    
    def is_update_available(self) -> bool:
        """Kurze Prüfung ob ein Update verfügbar ist"""
        available, _ = self.check_for_updates()
        return available


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
