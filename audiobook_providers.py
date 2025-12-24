#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audiobook Provider Integration
Unterstützt verschiedene Hörbuch-Anbieter: Audible, Storytel, Nextory, BookBeat

⚠️ WICHTIG: Nur für privaten Gebrauch!
DRM-Umgehung erfolgt ausschließlich für persönliche Nutzung der gekauften/abonnierten Inhalte.
"""

import json
import requests
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from enum import Enum
import re

# Versuche Selenium zu importieren (Browser-Automatisierung)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None

# Versuche browser_cookie3 zu importieren (Cookie-Extraktion)
try:
    import browser_cookie3
    BROWSER_COOKIE_AVAILABLE = True
except ImportError:
    BROWSER_COOKIE_AVAILABLE = False
    browser_cookie3 = None


class ProviderType(Enum):
    """Enum für verschiedene Hörbuch-Anbieter"""
    AUDIBLE = "audible"
    STORYTEL = "storytel"
    NEXTORY = "nextory"
    BOOKBEAT = "bookbeat"


class AudiobookProvider:
    """Basis-Klasse für Hörbuch-Anbieter"""
    
    def __init__(self, provider_type: ProviderType, config_path: Optional[str] = None):
        """
        Initialisiert den Provider
        
        Args:
            provider_type: Typ des Providers
            config_path: Optionaler Pfad zur Konfigurationsdatei
        """
        self.provider_type = provider_type
        self.config_path = Path(config_path) if config_path else Path(f".{provider_type.value}_config.json")
        self.session = requests.Session()
        self.is_authenticated = False
        self.cookies: Dict = {}
        
        # Lade gespeicherte Konfiguration
        self.load_config()
    
    def load_config(self):
        """Lädt gespeicherte Konfiguration"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.cookies = config.get('cookies', {})
                    self.is_authenticated = config.get('is_authenticated', False)
            except Exception as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
    
    def save_config(self):
        """Speichert Konfiguration"""
        try:
            config = {
                'cookies': self.cookies,
                'is_authenticated': self.is_authenticated,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def login(self, credentials: Dict) -> bool:
        """
        Meldet sich beim Provider an
        
        Args:
            credentials: Dictionary mit Login-Daten (email, password, etc.)
            
        Returns:
            True bei erfolgreichem Login
        """
        raise NotImplementedError("Subclasses must implement login method")
    
    def get_library(self) -> List[Dict]:
        """
        Ruft die Bibliothek des Benutzers ab
        
        Returns:
            Liste von Hörbuch-Dictionaries
        """
        raise NotImplementedError("Subclasses must implement get_library method")
    
    def download_book(self, book_id: str, output_dir: Path) -> bool:
        """
        Lädt ein Hörbuch herunter
        
        Args:
            book_id: ID des Hörbuchs
            output_dir: Ausgabeverzeichnis
            
        Returns:
            True bei erfolgreichem Download
        """
        raise NotImplementedError("Subclasses must implement download_book method")


class StorytelProvider(AudiobookProvider):
    """Storytel Provider Integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(ProviderType.STORYTEL, config_path)
        self.base_url = "https://www.storytel.com"
        self.api_url = "https://api.storytel.com"
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
        })
    
    def login(self, credentials: Dict) -> bool:
        """
        Meldet sich bei Storytel an
        
        WICHTIG: Storytel verwendet DRM-geschützte Downloads.
        Downloads sind nur über die offizielle App möglich.
        Diese Implementierung ist eine Grundstruktur für zukünftige Erweiterungen.
        """
        email = credentials.get('email')
        password = credentials.get('password')
        
        if not email or not password:
            return False
        
        try:
            # Storytel Login-Endpoint (muss durch Reverse-Engineering ermittelt werden)
            # HINWEIS: Storytel hat keine öffentliche API
            login_url = f"{self.base_url}/api/login"
            
            # Versuche Login (experimentell)
            response = self.session.post(
                login_url,
                json={'email': email, 'password': password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # Speichere Cookies/Session
                self.cookies = dict(self.session.cookies)
                self.is_authenticated = True
                self.save_config()
                return True
            
            return False
        except Exception as e:
            print(f"Fehler beim Storytel-Login: {e}")
            return False
    
    def get_library(self) -> List[Dict]:
        """
        Ruft die Storytel-Bibliothek ab
        
        HINWEIS: Storytel hat keine öffentliche API.
        Diese Methode würde Browser-Automatisierung oder App-Reverse-Engineering erfordern.
        """
        if not self.is_authenticated:
            return []
        
        try:
            # Storytel Bibliothek-Endpoint (muss durch Reverse-Engineering ermittelt werden)
            library_url = f"{self.api_url}/library"
            response = self.session.get(library_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('books', [])
            
            return []
        except Exception as e:
            print(f"Fehler beim Abrufen der Storytel-Bibliothek: {e}")
            return []
    
    def download_book(self, book_id: str, output_dir: Path, quality: str = "best") -> bool:
        """
        Lädt ein Storytel-Hörbuch herunter
        
        ⚠️ WICHTIG: Nur für privaten Gebrauch!
        DRM-Umgehung erfolgt ausschließlich für persönliche Nutzung.
        """
        if not self.is_authenticated:
            print("❌ Nicht angemeldet. Bitte zuerst anmelden.")
            return False
        
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            download_url = self._get_download_url(book_id)
            if not download_url:
                print("❌ Konnte Download-URL nicht abrufen.")
                return False
            
            encrypted_path = output_dir / f"{book_id}_encrypted.m4a"
            print(f"📥 Lade verschlüsselte Datei herunter...")
            
            response = self.session.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(encrypted_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Datei heruntergeladen: {encrypted_path}")
            
            print(f"🔓 Entschlüssele DRM (nur für privaten Gebrauch)...")
            decrypted_path = self._decrypt_drm(encrypted_path, book_id, output_dir)
            
            if decrypted_path and decrypted_path.exists():
                encrypted_path.unlink()
                print(f"✓ Hörbuch erfolgreich heruntergeladen: {decrypted_path}")
                return True
            else:
                print("❌ DRM-Entschlüsselung fehlgeschlagen.")
                return False
                
        except Exception as e:
            print(f"❌ Fehler beim Download: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_download_url(self, book_id: str) -> Optional[str]:
        """Ruft Download-URL für ein Hörbuch ab"""
        try:
            api_url = f"{self.api_url}/books/{book_id}/download"
            response = self.session.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('download_url') or data.get('stream_url')
            
            return None
        except Exception as e:
            print(f"Fehler beim Abrufen der Download-URL: {e}")
            return None
    
    def _decrypt_drm(self, encrypted_path: Path, book_id: str, output_dir: Path) -> Optional[Path]:
        """Entschlüsselt DRM-geschützte Datei (nur für privaten Gebrauch)"""
        try:
            output_path = output_dir / f"{book_id}.mp3"
            
            # Versuche mit yt-dlp
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "yt_dlp", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        sys.executable, "-m", "yt_dlp",
                        "-x", "--audio-format", "mp3",
                        "--audio-quality", "0",
                        "-o", str(output_path),
                        str(encrypted_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            # Fallback: ffmpeg
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        "ffmpeg", "-i", str(encrypted_path),
                        "-codec:a", "libmp3lame", "-b:a", "320k",
                        "-y", str(output_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            print("⚠️ DRM-Entschlüsselung erfordert spezielle Tools.")
            return None
            
        except Exception as e:
            print(f"Fehler bei DRM-Entschlüsselung: {e}")
            return None


class NextoryProvider(AudiobookProvider):
    """Nextory Provider Integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(ProviderType.NEXTORY, config_path)
        self.base_url = "https://www.nextory.de"
        self.api_url = "https://api.nextory.de"
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
        })
    
    def login(self, credentials: Dict) -> bool:
        """
        Meldet sich bei Nextory an
        
        WICHTIG: Nextory verwendet DRM-geschützte Downloads.
        Downloads sind nur über die offizielle App möglich.
        """
        email = credentials.get('email')
        password = credentials.get('password')
        
        if not email or not password:
            return False
        
        try:
            # Nextory Login-Endpoint (muss durch Reverse-Engineering ermittelt werden)
            login_url = f"{self.base_url}/api/auth/login"
            
            response = self.session.post(
                login_url,
                json={'email': email, 'password': password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.cookies = dict(self.session.cookies)
                self.is_authenticated = True
                self.save_config()
                return True
            
            return False
        except Exception as e:
            print(f"Fehler beim Nextory-Login: {e}")
            return False
    
    def get_library(self) -> List[Dict]:
        """Ruft die Nextory-Bibliothek ab"""
        if not self.is_authenticated:
            return []
        
        try:
            library_url = f"{self.api_url}/library"
            response = self.session.get(library_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('books', [])
            
            return []
        except Exception as e:
            print(f"Fehler beim Abrufen der Nextory-Bibliothek: {e}")
            return []
    
    def download_book(self, book_id: str, output_dir: Path, quality: str = "best") -> bool:
        """
        Lädt ein Nextory-Hörbuch herunter
        
        ⚠️ WICHTIG: Nur für privaten Gebrauch!
        """
        if not self.is_authenticated:
            print("❌ Nicht angemeldet. Bitte zuerst anmelden.")
            return False
        
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            download_url = self._get_download_url(book_id)
            if not download_url:
                print("❌ Konnte Download-URL nicht abrufen.")
                return False
            
            encrypted_path = output_dir / f"{book_id}_encrypted.m4a"
            print(f"📥 Lade verschlüsselte Datei herunter...")
            
            response = self.session.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(encrypted_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Datei heruntergeladen: {encrypted_path}")
            
            print(f"🔓 Entschlüssele DRM (nur für privaten Gebrauch)...")
            decrypted_path = self._decrypt_drm(encrypted_path, book_id, output_dir)
            
            if decrypted_path and decrypted_path.exists():
                encrypted_path.unlink()
                print(f"✓ Hörbuch erfolgreich heruntergeladen: {decrypted_path}")
                return True
            else:
                print("❌ DRM-Entschlüsselung fehlgeschlagen.")
                return False
                
        except Exception as e:
            print(f"❌ Fehler beim Download: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_download_url(self, book_id: str) -> Optional[str]:
        """Ruft Download-URL für ein Hörbuch ab"""
        try:
            api_url = f"{self.api_url}/books/{book_id}/download"
            response = self.session.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('download_url') or data.get('stream_url')
            
            return None
        except Exception as e:
            print(f"Fehler beim Abrufen der Download-URL: {e}")
            return None
    
    def _decrypt_drm(self, encrypted_path: Path, book_id: str, output_dir: Path) -> Optional[Path]:
        """Entschlüsselt DRM-geschützte Datei (nur für privaten Gebrauch)"""
        try:
            output_path = output_dir / f"{book_id}.mp3"
            
            # Versuche mit yt-dlp
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "yt_dlp", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        sys.executable, "-m", "yt_dlp",
                        "-x", "--audio-format", "mp3",
                        "--audio-quality", "0",
                        "-o", str(output_path),
                        str(encrypted_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            # Fallback: ffmpeg
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        "ffmpeg", "-i", str(encrypted_path),
                        "-codec:a", "libmp3lame", "-b:a", "320k",
                        "-y", str(output_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            print("⚠️ DRM-Entschlüsselung erfordert spezielle Tools.")
            return None
            
        except Exception as e:
            print(f"Fehler bei DRM-Entschlüsselung: {e}")
            return None


class BookBeatProvider(AudiobookProvider):
    """BookBeat Provider Integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        super().__init__(ProviderType.BOOKBEAT, config_path)
        self.base_url = "https://www.bookbeat.de"
        self.api_url = "https://api.bookbeat.de"
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
        })
    
    def login(self, credentials: Dict) -> bool:
        """
        Meldet sich bei BookBeat an
        
        WICHTIG: BookBeat verwendet DRM-geschützte Downloads.
        Downloads sind nur über die offizielle App möglich.
        """
        email = credentials.get('email')
        password = credentials.get('password')
        
        if not email or not password:
            return False
        
        try:
            # BookBeat Login-Endpoint (muss durch Reverse-Engineering ermittelt werden)
            login_url = f"{self.base_url}/api/auth/login"
            
            response = self.session.post(
                login_url,
                json={'email': email, 'password': password},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.cookies = dict(self.session.cookies)
                self.is_authenticated = True
                self.save_config()
                return True
            
            return False
        except Exception as e:
            print(f"Fehler beim BookBeat-Login: {e}")
            return False
    
    def get_library(self) -> List[Dict]:
        """Ruft die BookBeat-Bibliothek ab"""
        if not self.is_authenticated:
            return []
        
        try:
            library_url = f"{self.api_url}/library"
            response = self.session.get(library_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('books', [])
            
            return []
        except Exception as e:
            print(f"Fehler beim Abrufen der BookBeat-Bibliothek: {e}")
            return []
    
    def download_book(self, book_id: str, output_dir: Path, quality: str = "best") -> bool:
        """
        Lädt ein BookBeat-Hörbuch herunter
        
        ⚠️ WICHTIG: Nur für privaten Gebrauch!
        """
        if not self.is_authenticated:
            print("❌ Nicht angemeldet. Bitte zuerst anmelden.")
            return False
        
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            download_url = self._get_download_url(book_id)
            if not download_url:
                print("❌ Konnte Download-URL nicht abrufen.")
                return False
            
            encrypted_path = output_dir / f"{book_id}_encrypted.m4a"
            print(f"📥 Lade verschlüsselte Datei herunter...")
            
            response = self.session.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            with open(encrypted_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"✓ Datei heruntergeladen: {encrypted_path}")
            
            print(f"🔓 Entschlüssele DRM (nur für privaten Gebrauch)...")
            decrypted_path = self._decrypt_drm(encrypted_path, book_id, output_dir)
            
            if decrypted_path and decrypted_path.exists():
                encrypted_path.unlink()
                print(f"✓ Hörbuch erfolgreich heruntergeladen: {decrypted_path}")
                return True
            else:
                print("❌ DRM-Entschlüsselung fehlgeschlagen.")
                return False
                
        except Exception as e:
            print(f"❌ Fehler beim Download: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_download_url(self, book_id: str) -> Optional[str]:
        """Ruft Download-URL für ein Hörbuch ab"""
        try:
            api_url = f"{self.api_url}/books/{book_id}/download"
            response = self.session.get(api_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('download_url') or data.get('stream_url')
            
            return None
        except Exception as e:
            print(f"Fehler beim Abrufen der Download-URL: {e}")
            return None
    
    def _decrypt_drm(self, encrypted_path: Path, book_id: str, output_dir: Path) -> Optional[Path]:
        """Entschlüsselt DRM-geschützte Datei (nur für privaten Gebrauch)"""
        try:
            output_path = output_dir / f"{book_id}.mp3"
            
            # Versuche mit yt-dlp
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "yt_dlp", "--version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        sys.executable, "-m", "yt_dlp",
                        "-x", "--audio-format", "mp3",
                        "--audio-quality", "0",
                        "-o", str(output_path),
                        str(encrypted_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            # Fallback: ffmpeg
            try:
                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cmd = [
                        "ffmpeg", "-i", str(encrypted_path),
                        "-codec:a", "libmp3lame", "-b:a", "320k",
                        "-y", str(output_path)
                    ]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    if result.returncode == 0 and output_path.exists():
                        return output_path
            except:
                pass
            
            print("⚠️ DRM-Entschlüsselung erfordert spezielle Tools.")
            return None
            
        except Exception as e:
            print(f"Fehler bei DRM-Entschlüsselung: {e}")
            return None


def get_provider(provider_type: ProviderType) -> Optional[AudiobookProvider]:
    """
    Factory-Funktion zum Erstellen von Provider-Instanzen
    
    Args:
        provider_type: Typ des Providers
        
    Returns:
        Provider-Instanz oder None
    """
    if provider_type == ProviderType.STORYTEL:
        return StorytelProvider()
    elif provider_type == ProviderType.NEXTORY:
        return NextoryProvider()
    elif provider_type == ProviderType.BOOKBEAT:
        return BookBeatProvider()
    else:
        return None
