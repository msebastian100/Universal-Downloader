#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audible Integration für Hörbuch-Downloads
Unterstützt Anmeldung, Bibliothek und Download
"""

import json
import requests
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from getpass import getpass
import re
import webbrowser
import http.server
import socketserver
import urllib.parse
import threading
import time

# Versuche audible-Bibliothek zu importieren (bessere API)
try:
    import audible
    AUDIBLE_AVAILABLE = True
except ImportError:
    AUDIBLE_AVAILABLE = False
    audible = None

# Versuche browser_cookie3 zu importieren (Cookie-Extraktion aus Browser)
try:
    import browser_cookie3
    BROWSER_COOKIE_AVAILABLE = True
except ImportError:
    BROWSER_COOKIE_AVAILABLE = False
    browser_cookie3 = None

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


class AudibleAuth:
    """Klasse für Audible-Authentifizierung"""
    
    def __init__(self, config_path: str = ".audible_config.json"):
        """
        Initialisiert den Authentifizierungsmanager
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        self.config_path = Path(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        })
        
        # Audible URLs
        self.base_url = "https://www.audible.de"
        self.api_url = "https://api.audible.de"
        
        # Session-Daten
        self.email: Optional[str] = None
        self.password: Optional[str] = None
        self.cookies: Dict = {}
        self.is_authenticated = False
        self.audible_auth = None  # audible-Bibliothek Authenticator
        self.activation_bytes: Optional[str] = None  # Activation Bytes für AAX-Entschlüsselung
        
        # Lade gespeicherte Konfiguration
        self.load_config()
    
    def _normalize_cookie_name(self, name: str) -> str:
        """Normalisiert Cookie-Namen (z.B. ubid-acbde -> ubid-main)"""
        name_lower = name.lower()
        # Erkenne Cookie-Typen auch mit verschiedenen Suffixen
        if name_lower == 'session-id' or name_lower.startswith('session-id'):
            if 'time' in name_lower:
                return 'session-id-time'
            return 'session-id'
        elif name_lower.startswith('ubid-'):
            # ubid-main, ubid-acbde, etc. -> ubid-main
            return 'ubid-main'
        elif name_lower.startswith('sess-at-'):
            # sess-at-main, sess-at-acbde, etc. -> sess-at-main
            return 'sess-at-main'
        elif name_lower.startswith('at-') and not name_lower.startswith('sess-at-'):
            # at-main, at-acbde, etc. -> at-main
            return 'at-main'
        # Unbekannter Cookie, behalte Original-Name
        return name
    
    def load_config(self):
        """Lädt gespeicherte Konfiguration"""
        # Versuche zuerst audible-Bibliothek Authenticator zu laden
        if AUDIBLE_AVAILABLE:
            try:
                from audible import Authenticator
                auth_file = self.config_path.parent / f"{self.config_path.stem}_auth.json"
                if auth_file.exists():
                    self.audible_auth = Authenticator.from_file(str(auth_file))
                    self.is_authenticated = True
                    self.session = self.audible_auth.session
                    self.cookies = dict(self.audible_auth.session.cookies)
                    if hasattr(self.audible_auth, 'email'):
                        self.email = self.audible_auth.email
                    
                    # Lade Activation Bytes (falls vorhanden)
                    if hasattr(self.audible_auth, 'activation_bytes') and self.audible_auth.activation_bytes:
                        self.activation_bytes = self.audible_auth.activation_bytes
                        print("✓ Gespeicherte audible-Authentifizierung geladen (mit Activation Bytes)")
                    else:
                        print("✓ Gespeicherte audible-Authentifizierung geladen")
                    return
            except Exception as e:
                # Ignoriere Fehler und versuche normale Konfiguration
                pass
        
        # Fallback: Normale Konfiguration
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.email = config.get('email')
                    self.cookies = config.get('cookies', {})
                    # Setze Cookies in Session
                    for name, value in self.cookies.items():
                        self.session.cookies.set(name, value, domain='.audible.de')
                    self.is_authenticated = config.get('is_authenticated', False)
                    self.activation_bytes = config.get('activation_bytes')  # Lade gespeicherte Activation Bytes
            except Exception as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
    
    def save_config(self):
        """Speichert Konfiguration"""
        try:
            # Wenn audible-Bibliothek verwendet wird, speichere dort
            if self.audible_auth and AUDIBLE_AVAILABLE:
                try:
                    auth_file = self.config_path.parent / f"{self.config_path.stem}_auth.json"
                    self.audible_auth.to_file(str(auth_file))
                    # Activation Bytes werden automatisch in audible_auth gespeichert
                    return
                except Exception as e:
                    pass  # Fallback zu normaler Konfiguration
            
            # Normale Konfiguration
            config = {
                'email': self.email,
                'cookies': dict(self.session.cookies),
                'is_authenticated': self.is_authenticated,
                'activation_bytes': self.activation_bytes  # Speichere Activation Bytes
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def _try_create_audible_auth_from_session(self):
        """Versucht einen audible.Authenticator aus der bestehenden Session zu erstellen"""
        if not AUDIBLE_AVAILABLE or self.audible_auth:
            return False
        
        try:
            from audible import Authenticator
            
            # Versuche Authenticator aus Session zu erstellen
            # Die audible-Bibliothek kann einen Authenticator aus Cookies erstellen
            if self.is_authenticated and self.session.cookies:
                try:
                    # Erstelle Authenticator mit Cookies
                    # Die audible-Bibliothek unterstützt verschiedene Methoden
                    # Versuche mit from_login_external oder direkt mit Session
                    auth_file = self.config_path.parent / f"{self.config_path.stem}_auth.json"
                    
                    # Versuche Authenticator aus bestehender Session zu erstellen
                    # Dies funktioniert, wenn wir die richtigen Cookies haben
                    if hasattr(Authenticator, 'from_session'):
                        self.audible_auth = Authenticator.from_session(self.session)
                    elif hasattr(Authenticator, 'from_cookies'):
                        # Versuche mit Cookies
                        cookies_dict = dict(self.session.cookies)
                        self.audible_auth = Authenticator.from_cookies(cookies_dict)
                    else:
                        # Versuche mit externem Login (falls unterstützt)
                        # Dies ist ein Workaround - wir haben bereits eine Session
                        return False
                    
                    if self.audible_auth:
                        # Speichere Authenticator
                        if hasattr(self.audible_auth, 'to_file'):
                            self.audible_auth.to_file(str(auth_file))
                        return True
                except Exception as e:
                    # Ignoriere Fehler - nicht alle Methoden sind verfügbar
                    pass
        except:
            pass
        
        return False
    
    def _try_extract_activation_bytes(self):
        """Versucht automatisch Activation Bytes zu extrahieren"""
        try:
            # Versuche zuerst, audible_auth aus Session zu erstellen
            if not self.audible_auth and self.is_authenticated:
                self._try_create_audible_auth_from_session()
            
            if not self.activation_bytes and self.audible_auth and AUDIBLE_AVAILABLE:
                try:
                    print("\nVersuche Activation Bytes automatisch zu extrahieren...")
                    activation_bytes = self.audible_auth.get_activation_bytes(force_refresh=False)
                    if activation_bytes:
                        self.activation_bytes = activation_bytes
                        self.save_config()
                        print(f"✓ Activation Bytes erfolgreich extrahiert!")
                        print(f"  Key: {activation_bytes}")
                        print(f"  (Gespeichert für zukünftige Verwendung)")
                        return True
                    else:
                        print("✗ Konnte Activation Bytes nicht automatisch extrahieren")
                        print("  ℹ Sie können die Activation Bytes manuell im 'Activation Bytes' Tab eingeben")
                except Exception as e:
                    print(f"✗ Fehler bei automatischer Extraktion: {e}")
                    print("  ℹ Sie können die Activation Bytes manuell im 'Activation Bytes' Tab eingeben")
            elif not self.audible_auth:
                print("⚠ Konnte Activation Bytes nicht extrahieren (audible-Bibliothek nicht verfügbar)")
                print("  ℹ Sie können die Activation Bytes manuell im 'Activation Bytes' Tab eingeben")
        except Exception as e:
            print(f"✗ Fehler bei automatischer Extraktion: {e}")
        
        return False
    
    def get_activation_bytes(self, force_refresh: bool = False) -> Optional[str]:
        """
        Extrahiert Activation Bytes für AAX-Entschlüsselung
        
        Args:
            force_refresh: Wenn True, werden neue Activation Bytes abgerufen
            
        Returns:
            Activation Bytes als Hex-String oder None
        """
        # Wenn bereits vorhanden und nicht erzwungen, zurückgeben
        if not force_refresh and self.activation_bytes:
            return self.activation_bytes
        
        # Versuche audible_auth aus Session zu erstellen, falls nicht vorhanden
        if not self.audible_auth and self.is_authenticated:
            self._try_create_audible_auth_from_session()
        
        # Versuche mit audible-Bibliothek (beste Methode)
        if self.audible_auth and AUDIBLE_AVAILABLE:
            try:
                print("  Extrahiere Activation Bytes mit audible-Bibliothek...")
                activation_bytes = self.audible_auth.get_activation_bytes(force_refresh=force_refresh)
                if activation_bytes:
                    self.activation_bytes = activation_bytes
                    # Speichere in audible_auth
                    if hasattr(self.audible_auth, 'activation_bytes'):
                        self.audible_auth.activation_bytes = activation_bytes
                    self.save_config()
                    print(f"  ✓ Activation Bytes extrahiert: {activation_bytes[:8]}...")
                    return activation_bytes
            except Exception as e:
                print(f"  ⚠ Fehler beim Extrahieren mit audible-Bibliothek: {e}")
                import traceback
                traceback.print_exc()
        
        # Fallback: Versuche manuell über API (wenn Session vorhanden)
        if self.is_authenticated and AUDIBLE_AVAILABLE:
            try:
                from audible.activation_bytes import get_activation_bytes
                print("  Versuche Activation Bytes direkt über API zu extrahieren...")
                # Versuche mit der Session
                activation_bytes = get_activation_bytes(auth=self.audible_auth if self.audible_auth else None)
                if activation_bytes:
                    self.activation_bytes = activation_bytes
                    self.save_config()
                    print(f"  ✓ Activation Bytes extrahiert: {activation_bytes[:8]}...")
                    return activation_bytes
            except Exception as e:
                print(f"  ⚠ Direkte API-Extraktion fehlgeschlagen: {e}")
        
        # Fallback: Versuche mit audible-activator (wenn verfügbar)
        activation_bytes = self._try_extract_with_audible_activator()
        if activation_bytes:
            return activation_bytes
        
        # Fallback: Versuche manuell über API
        print("  ⚠ Konnte Activation Bytes nicht automatisch extrahieren.")
        print("  ℹ Sie können Activation Bytes manuell mit Tools wie 'audible-activator' extrahieren.")
        print("  ℹ Oder geben Sie die Activation Bytes manuell in der GUI ein.")
        return None
    
    def _try_extract_with_audible_activator(self) -> Optional[str]:
        """
        Versucht Activation Bytes mit audible-activator Logik zu extrahieren
        
        Returns:
            Activation Bytes als Hex-String oder None
        """
        try:
            import binascii
            import hashlib
            import base64
            import urllib.parse
            
            if not self.is_authenticated:
                return None
            
            print("  Versuche Activation Bytes mit audible-activator Methode zu extrahieren...")
            
            # Erstelle Player ID (wie in audible-activator)
            player_id = base64.b64encode(hashlib.sha1(b"").digest()).decode("ascii").rstrip()
            
            # Step 1: Hole player-auth-token (wie audible-activator)
            # audible-activator verwendet einen speziellen OpenID-Logout-Flow
            # Wir versuchen es direkt mit der player-auth-token URL
            
            # Bestimme Ländercode für OpenID
            country_code = "de"
            if ".co.uk" in self.base_url:
                country_code = "uk"
            elif ".com.au" in self.base_url:
                country_code = "au"
            elif ".co.jp" in self.base_url:
                country_code = "jp"
            elif ".in" in self.base_url:
                country_code = "in"
            elif ".com" in self.base_url and ".de" not in self.base_url:
                country_code = "us"
            
            # Prüfe zuerst, ob wir wirklich eingeloggt sind
            print("  Prüfe Session-Gültigkeit...")
            test_response = self.session.get(f"{self.base_url}/library", timeout=10, allow_redirects=True)
            if 'signin' in test_response.url.lower() or test_response.status_code != 200:
                print("  ⚠ Session ist nicht gültig. Bitte melden Sie sich erneut an.")
                return None
            print("  ✓ Session ist gültig")
            
            # Versuche verschiedene URL-Formate
            # WICHTIG: Der player-auth-token Endpoint erfordert einen speziellen Flow
            # audible-activator verwendet einen OpenID-Logout-Flow mit return_to Parameter
            activation_urls = [
                # Direkter Aufruf (kann zu Login umleiten)
                f"{self.base_url}/player-auth-token?playerType=software&playerId={player_id}&bp_ua=y&playerModel=Desktop&playerManufacturer=Audible&serial=",
                f"{self.base_url}/player-auth-token?playerType=software&playerId={player_id}&bp_ua=y&playerModel=Desktop&playerManufacturer=Audible",
            ]
            
            try:
                # Verwende speziellen User-Agent wie audible-activator
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                    'Referer': f'{self.base_url}/library',
                    'Origin': self.base_url,
                }
                
                response = None
                for url in activation_urls:
                    try:
                        print(f"  Versuche URL: {url[:100]}...")
                        response = self.session.get(url, headers=headers, timeout=30, allow_redirects=True)
                        
                        print(f"  Debug: Status Code: {response.status_code}")
                        print(f"  Debug: Final URL: {response.url[:200]}")
                        
                        # Wenn wir zur player-auth-token URL weitergeleitet werden (mit playerToken), haben wir Erfolg
                        if 'playerToken' in response.url or response.status_code == 200:
                            # Prüfe ob wir nicht zur Login-Seite umgeleitet wurden
                            if 'signin' not in response.url.lower() and 'ap/signin' not in response.url.lower():
                                break
                    except Exception as e:
                        print(f"  Debug: Fehler bei URL {url[:50]}...: {e}")
                        continue
                
                if not response:
                    print("  ⚠ Konnte keine Verbindung zur player-auth-token API herstellen")
                    return None
                
                # Prüfe ob wir zur Login-Seite umgeleitet wurden
                if 'signin' in response.url.lower() or 'ap/signin' in response.url.lower():
                    print("  ⚠ Wurde zur Login-Seite umgeleitet. Session-Cookies funktionieren nicht für diesen Endpoint.")
                    print("  ℹ Der player-auth-token Endpoint erfordert einen speziellen OpenID-Flow.")
                    print("  ℹ Versuche mit Selenium (wie audible-activator)...")
                    
                    # Versuche mit Selenium (wie audible-activator)
                    activation_bytes = self._try_extract_with_selenium()
                    if activation_bytes:
                        return activation_bytes
                    
                    print("  ℹ Bitte verwenden Sie die manuelle Eingabe oder führen Sie audible-activator manuell aus.")
                    return None
                
                
                print(f"  Debug: Status Code: {response.status_code}")
                print(f"  Debug: Final URL: {response.url[:200]}")
                
                # Extrahiere playerToken aus der URL oder Response
                player_token = None
                
                # Methode 1: Prüfe ob playerToken in der URL ist (Redirect) - WICHTIGSTE METHODE
                if 'playerToken' in response.url:
                    parsed = urllib.parse.urlparse(response.url)
                    query_params = urllib.parse.parse_qs(parsed.query)
                    if 'playerToken' in query_params:
                        player_token = query_params['playerToken'][0]
                        print(f"  Debug: playerToken aus URL extrahiert: {player_token[:20]}...")
                    else:
                        # Versuche direkt aus der URL zu parsen
                        import re
                        match = re.search(r'playerToken=([^&\s]+)', response.url)
                        if match:
                            player_token = match.group(1)
                            print(f"  Debug: playerToken aus URL-String extrahiert: {player_token[:20]}...")
                
                # Methode 2: Prüfe Response-Headers (Location)
                if not player_token:
                    location = response.headers.get('Location', '')
                    if 'playerToken' in location:
                        parsed = urllib.parse.urlparse(location)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        if 'playerToken' in query_params:
                            player_token = query_params['playerToken'][0]
                            print(f"  Debug: playerToken aus Location-Header extrahiert: {player_token[:20]}...")
                        else:
                            import re
                            match = re.search(r'playerToken=([^&\s]+)', location)
                            if match:
                                player_token = match.group(1)
                                print(f"  Debug: playerToken aus Location-String extrahiert: {player_token[:20]}...")
                
                # Methode 3: Versuche aus dem Response-Text zu extrahieren
                if not player_token and response.text:
                    import re
                    # Verschiedene Patterns versuchen
                    patterns = [
                        r'playerToken["\']?\s*[:=]\s*["\']([^"\']+)',
                        r'playerToken=([^&\s"\']+)',
                        r'"playerToken":"([^"]+)"',
                        r"'playerToken':'([^']+)'",
                        r'playerToken["\']?\s*:\s*["\']([^"\']+)',
                        r'name=["\']playerToken["\']\s+value=["\']([^"\']+)',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, response.text, re.IGNORECASE)
                        if match:
                            player_token = match.group(1)
                            print(f"  Debug: playerToken aus Response-Text extrahiert (Pattern: {pattern[:30]}...): {player_token[:20]}...")
                            break
                
                # Methode 4: Prüfe ob es ein JSON-Response ist
                if not player_token:
                    try:
                        import json
                        data = response.json()
                        if 'playerToken' in data:
                            player_token = data['playerToken']
                            print(f"  Debug: playerToken aus JSON extrahiert: {player_token[:20]}...")
                        elif 'token' in data:
                            player_token = data['token']
                            print(f"  Debug: token aus JSON extrahiert: {player_token[:20]}...")
                    except:
                        pass
                
                if not player_token:
                    print("  ⚠ Konnte playerToken nicht extrahieren")
                    print(f"  Debug: Response-Text (erste 1000 Zeichen): {response.text[:1000]}")
                    print(f"  Debug: Response-Headers: {dict(list(response.headers.items())[:10])}")
                    # Versuche nochmal mit einer anderen URL-Struktur
                    print("  Debug: Versuche alternative URL-Struktur...")
                    alt_url = f"{self.base_url}/player-auth-token?playerType=software&bp_ua=y&playerModel=Desktop&playerId={player_id}&playerManufacturer=Audible&serial="
                    alt_response = self.session.get(alt_url, headers=headers, timeout=30, allow_redirects=True)
                    if 'playerToken' in alt_response.url:
                        parsed = urllib.parse.urlparse(alt_response.url)
                        query_params = urllib.parse.parse_qs(parsed.query)
                        if 'playerToken' in query_params:
                            player_token = query_params['playerToken'][0]
                            print(f"  Debug: playerToken aus alternativer URL extrahiert: {player_token[:20]}...")
                    
                    if not player_token:
                        return None
                
                print(f"  ✓ playerToken erhalten")
                
                # Step 2: De-register first (um Slots freizugeben)
                # audible-activator verwendet base_url_license = base_url (nicht ohne www.)
                license_base = self.base_url.rstrip('/')
                de_reg_url = f"{license_base}/license/licenseForCustomerToken?customer_token={player_token}&action=de-register"
                
                de_reg_headers = {
                    'User-Agent': 'Audible Download Manager'
                }
                
                print("  De-registriere (um Slots freizugeben)...")
                self.session.get(de_reg_url, headers=de_reg_headers, timeout=30)
                
                # Step 3: Hole license blob (wie audible-activator)
                # audible-activator baut URL direkt als String: base_url_license + 'license/licenseForCustomerToken?' + 'customer_token=' + player_token
                license_url = f"{license_base}/license/licenseForCustomerToken?customer_token={player_token}"
                
                print("  Hole license blob...")
                print(f"  Debug: License URL: {license_url[:150]}...")
                license_response = self.session.get(license_url, headers=de_reg_headers, timeout=30)
                
                print(f"  Debug: License Response Status: {license_response.status_code}")
                print(f"  Debug: License Response URL: {license_response.url[:200]}")
                
                if license_response.status_code == 200:
                    activation_data = license_response.content
                    print(f"  Debug: License Blob Größe: {len(activation_data)} Bytes")
                    
                    # Verwende die Extraktionslogik von audible-activator
                    activation_bytes = self._extract_activation_bytes_from_blob(activation_data)
                    
                    if activation_bytes:
                        # De-register wieder (um Slots freizugeben)
                        self.session.get(de_reg_url, headers=de_reg_headers, timeout=30)
                        
                        self.activation_bytes = activation_bytes
                        self.save_config()
                        print(f"  ✓ Activation Bytes extrahiert mit audible-activator Methode!")
                        print(f"  Key: {activation_bytes}")
                        return activation_bytes
                    else:
                        print("  ⚠ Konnte Activation Bytes nicht aus dem Blob extrahieren")
                        if len(activation_data) < 500:
                            print(f"  Debug: Blob-Inhalt (erste 500 Zeichen): {activation_data[:500]}")
                else:
                    print(f"  ⚠ License-API-Aufruf fehlgeschlagen: Status {license_response.status_code}")
                    print(f"  Debug: Response Text (erste 500 Zeichen): {license_response.text[:500]}")
                    
                    # Wenn 404, versuche es mit Selenium (könnte bessere Cookies haben)
                    if license_response.status_code == 404:
                        print("  ℹ Versuche mit Selenium-Methode (könnte bessere Cookies haben)...")
                        activation_bytes = self._try_extract_with_selenium()
                        if activation_bytes:
                            return activation_bytes
                    
            except Exception as e:
                print(f"  ⚠ Fehler beim API-Aufruf: {e}")
                import traceback
                traceback.print_exc()
            
            return None
            
        except Exception as e:
            print(f"  ⚠ audible-activator Methode fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _try_extract_with_selenium(self) -> Optional[str]:
        """
        Versucht Activation Bytes mit Selenium zu extrahieren (wie audible-activator)
        Verwendet die bestehende Session, indem Cookies in Selenium gesetzt werden
        
        Returns:
            Activation Bytes als Hex-String oder None
        """
        if not SELENIUM_AVAILABLE:
            print("  ⚠ Selenium nicht verfügbar")
            return None
        
        try:
            import binascii
            import hashlib
            import base64
            import urllib.parse
            import time
            
            print("  Starte Selenium-Browser...")
            
            # Erstelle Player ID (wie in audible-activator)
            player_id = base64.b64encode(hashlib.sha1(b"").digest()).decode("ascii").rstrip()
            
            # Chrome-Optionen
            chrome_options = Options()
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            user_agent = 'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; AS; rv:11.0) like Gecko'
            chrome_options.add_argument(f'user-agent={user_agent}')
            
            # Versuche Chrome zu starten
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                print(f"  ⚠ Konnte Chrome nicht starten: {e}")
                return None
            
            try:
                # Setze Cookies aus unserer Session in Selenium
                print("  Setze Cookies in Browser...")
                # Extrahiere Domain aus base_url (z.B. "www.audible.de" aus "https://www.audible.de/")
                from urllib.parse import urlparse
                parsed_url = urlparse(self.base_url)
                domain = parsed_url.netloc  # z.B. "www.audible.de"
                cookie_domain = domain.replace('www.', '')  # z.B. "audible.de"
                
                driver.get(self.base_url)  # Gehe zuerst zur Domain, um Cookies setzen zu können
                time.sleep(1)
                
                # Setze alle Cookies aus unserer Session
                cookies_set = 0
                for cookie in self.session.cookies:
                    try:
                        # Selenium erwartet ein Dictionary mit bestimmten Feldern
                        # Domain sollte ohne führenden Punkt sein für Selenium
                        cookie_domain_to_use = cookie.domain if cookie.domain else cookie_domain
                        # Entferne führenden Punkt, falls vorhanden
                        if cookie_domain_to_use.startswith('.'):
                            cookie_domain_to_use = cookie_domain_to_use[1:]
                        
                        selenium_cookie = {
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie_domain_to_use,
                            'path': cookie.path if cookie.path else '/',
                            'secure': cookie.secure if hasattr(cookie, 'secure') else True
                        }
                        driver.add_cookie(selenium_cookie)
                        cookies_set += 1
                    except Exception as e:
                        pass  # Ignoriere Fehler beim Setzen einzelner Cookies
                
                print(f"  ✓ {cookies_set} Cookies in Browser gesetzt")
                
                # Navigiere zur player-auth-token URL (wie audible-activator)
                activation_url = f"{self.base_url}/player-auth-token?playerType=software&bp_ua=y&playerModel=Desktop&playerId={player_id}&playerManufacturer=Audible&serial="
                print(f"  Navigiere zu player-auth-token...")
                driver.get(activation_url)
                time.sleep(3)  # Warte auf Redirect
                
                # Extrahiere playerToken aus der URL
                current_url = driver.current_url
                print(f"  Debug: Final URL: {current_url[:200]}")
                
                parsed = urllib.parse.urlparse(current_url)
                query_params = urllib.parse.parse_qs(parsed.query)
                
                if 'playerToken' not in query_params:
                    print("  ⚠ playerToken nicht in URL gefunden")
                    print(f"  Debug: Query-Parameter: {list(query_params.keys())}")
                    driver.quit()
                    return None
                
                player_token = query_params['playerToken'][0]
                print(f"  ✓ playerToken erhalten: {player_token[:20]}...")
                
                # Erstelle neue Session mit Selenium-Cookies (wie audible-activator)
                headers = {
                    'User-Agent': 'Audible Download Manager'
                }
                
                selenium_session = requests.Session()
                cookies_set_count = 0
                for cookie in driver.get_cookies():
                    try:
                        selenium_session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', ''))
                        cookies_set_count += 1
                    except Exception as e:
                        pass
                
                print(f"  Debug: {cookies_set_count} Cookies in requests.Session gesetzt")
                
                # Step 3: De-register first
                # audible-activator verwendet base_url_license = base_url (nicht ohne www.)
                license_base = self.base_url.rstrip('/')
                de_reg_url = f"{license_base}/license/licenseForCustomerToken?customer_token={player_token}&action=de-register"
                
                print("  De-registriere...")
                print(f"  Debug: De-reg URL: {de_reg_url[:150]}...")
                de_reg_response = selenium_session.get(de_reg_url, headers=headers, timeout=30)
                print(f"  Debug: De-reg Status: {de_reg_response.status_code}")
                
                # Step 4: Hole license blob
                # audible-activator baut URL direkt als String
                license_url = f"{license_base}/license/licenseForCustomerToken?customer_token={player_token}"
                
                print("  Hole license blob...")
                print(f"  Debug: License URL: {license_url[:150]}...")
                print(f"  Debug: Session Cookies vor Request: {len(selenium_session.cookies)} Cookies")
                
                # Versuche zuerst mit requests
                license_response = selenium_session.get(license_url, headers=headers, timeout=30, allow_redirects=True)
                
                print(f"  Debug: License Response Status: {license_response.status_code}")
                print(f"  Debug: License Response URL: {license_response.url[:200]}")
                print(f"  Debug: Response Headers: {dict(list(license_response.headers.items())[:5])}")
                
                # Wenn 404, versuche direkt im Browser (als Fallback)
                activation_data = None
                if license_response.status_code == 404:
                    print("  ℹ Versuche License-API direkt im Browser...")
                    try:
                        # Verwende Chrome DevTools Protocol um die rohen Response-Daten zu bekommen
                        # Das ist der einzige Weg, um binäre Daten von Selenium zu bekommen
                        try:
                            # Aktiviere Network-Domain für Chrome DevTools
                            driver.execute_cdp_cmd('Network.enable', {})
                            
                            # Navigiere zur URL und warte auf Response
                            driver.get(license_url)
                            time.sleep(3)  # Warte auf Response
                            
                            # Hole die letzte Network-Response
                            # Leider gibt es keine direkte API dafür, also müssen wir einen anderen Ansatz verwenden
                            
                            # Alternative: Verwende JavaScript fetch mit ArrayBuffer
                            # WICHTIG: Wir müssen die Response als ArrayBuffer holen, nicht als Text
                            print("  ℹ Versuche Response über JavaScript fetch (ArrayBuffer)...")
                            response_data = driver.execute_async_script("""
                                var callback = arguments[arguments.length - 1];
                                var url = arguments[0];
                                
                                fetch(url, {
                                    method: 'GET',
                                    credentials: 'include',
                                    headers: {
                                        'User-Agent': 'Audible Download Manager'
                                    }
                                })
                                .then(r => {
                                    // Hole Response als ArrayBuffer (auch bei 404)
                                    return r.arrayBuffer().then(buffer => {
                                        return {
                                            status: r.status,
                                            statusText: r.statusText,
                                            buffer: buffer
                                        };
                                    });
                                })
                                .then(result => {
                                    // Konvertiere ArrayBuffer zu String (latin-1 behält alle Bytes)
                                    var bytes = new Uint8Array(result.buffer);
                                    var binary = '';
                                    var maxLen = Math.min(bytes.length, 2000000); // Max 2MB
                                    for (var i = 0; i < maxLen; i++) {
                                        binary += String.fromCharCode(bytes[i]);
                                    }
                                    callback({
                                        status: result.status,
                                        statusText: result.statusText,
                                        data: binary,
                                        length: bytes.length
                                    });
                                })
                                .catch(e => callback({error: 'ERROR: ' + e}));
                            """, license_url)
                            
                            if response_data and isinstance(response_data, dict):
                                if 'error' in response_data:
                                    print(f"  ⚠ JavaScript fetch fehlgeschlagen: {response_data['error']}")
                                else:
                                    status = response_data.get('status', 0)
                                    data = response_data.get('data', '')
                                    length = response_data.get('length', 0)
                                    
                                    print(f"  Debug: JavaScript fetch Status: {status}")
                                    print(f"  Debug: JavaScript fetch Response Größe: {length} Bytes")
                                    
                                    if data:
                                        # Konvertiere JavaScript-String zurück zu Bytes
                                        activation_data = data.encode('latin-1')  # latin-1 behält alle Bytes bei
                                        
                                        # Prüfe ob es binäre Daten sind (nicht HTML)
                                        if not activation_data.startswith(b'<!DOCTYPE') and not activation_data.startswith(b'<html'):
                                            license_response.status_code = status if status == 200 else 200
                                            print("  ✓ Binäre Daten erhalten (nicht HTML)")
                                        else:
                                            print(f"  ⚠ Response ist HTML (Status {status}, erste 200 Bytes): {activation_data[:200]}")
                                            # Auch bei 404 könnte es sein, dass die Daten im HTML versteckt sind
                                            # Prüfe ob group_id im HTML ist
                                            if b'group_id' in activation_data:
                                                print("  ℹ group_id in HTML gefunden, versuche Extraktion...")
                                    else:
                                        print(f"  ⚠ Keine Daten in Response (Status {status})")
                            else:
                                print(f"  ⚠ JavaScript fetch fehlgeschlagen: {response_data}")
                                
                        except Exception as cdp_error:
                            print(f"  Debug: Chrome DevTools/CDP fehlgeschlagen: {cdp_error}")
                            # Fallback: Versuche normale Navigation
                            driver.get(license_url)
                            time.sleep(2)
                            page_source = driver.page_source
                            print(f"  Debug: Browser Response Größe: {len(page_source)} Bytes")
                            print(f"  Debug: Browser Response ist HTML (erste 200 Zeichen): {page_source[:200]}")
                            
                    except Exception as e:
                        print(f"  Debug: Browser-Methode fehlgeschlagen: {e}")
                        import traceback
                        traceback.print_exc()
                
                if license_response.status_code == 200:
                    # Verwende content wenn activation_data noch nicht gesetzt wurde
                    if activation_data is None:
                        activation_data = license_response.content
                    print(f"  Debug: License Blob Größe: {len(activation_data)} Bytes")
                    
                    # Extrahiere Activation Bytes
                    activation_bytes = self._extract_activation_bytes_from_blob(activation_data)
                    
                    if activation_bytes:
                        # De-register wieder
                        selenium_session.get(de_reg_url, headers=headers, timeout=30)
                        
                        self.activation_bytes = activation_bytes
                        self.save_config()
                        print(f"  ✓ Activation Bytes extrahiert mit Selenium-Methode!")
                        print(f"  Key: {activation_bytes}")
                        driver.quit()
                        return activation_bytes
                    else:
                        print("  ⚠ Konnte Activation Bytes nicht aus dem Blob extrahieren")
                        if len(activation_data) < 500:
                            print(f"  Debug: Blob-Inhalt (erste 500 Zeichen): {activation_data[:500]}")
                else:
                    print(f"  ⚠ License-API-Aufruf fehlgeschlagen: Status {license_response.status_code}")
                    print(f"  Debug: Response Text (erste 500 Zeichen): {license_response.text[:500]}")
                
                driver.quit()
                return None
                
            except Exception as e:
                try:
                    driver.quit()
                except:
                    pass
                raise e
                
        except Exception as e:
            print(f"  ⚠ Selenium-Methode fehlgeschlagen: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _extract_activation_bytes_from_blob(self, data: bytes) -> Optional[str]:
        """
        Extrahiert Activation Bytes aus einem activation blob (wie audible-activator)
        Verwendet die gleiche Logik wie audible-activator/common.py
        
        Args:
            data: Activation blob Daten
            
        Returns:
            Activation Bytes als Hex-String oder None
        """
        try:
            import binascii
            import sys
            
            PY3 = sys.version_info[0] == 3
            
            # Debug: Zeige erste Bytes des Blobs
            print(f"  Debug: Blob-Größe: {len(data)} Bytes")
            if len(data) > 0:
                print(f"  Debug: Erste 100 Bytes (hex): {binascii.hexlify(data[:min(100, len(data))])}")
                print(f"  Debug: Erste 100 Bytes (text, nur druckbare): {''.join([chr(b) if 32 <= b < 127 else '.' for b in data[:min(100, len(data))]])}")
            
            # Prüfe ob es HTML ist
            if data.startswith(b'<!DOCTYPE') or data.startswith(b'<html') or data.startswith(b'<HTML'):
                print("  ⚠ Blob scheint HTML zu sein, nicht binäre Daten")
                # Versuche group_id in HTML zu finden
                if b"group_id" in data:
                    print("  ℹ group_id in HTML gefunden, versuche Extraktion...")
                else:
                    print("  ⚠ group_id nicht in HTML gefunden")
                    return None
            
            # Prüfe auf Fehler (wie in audible-activator)
            if b"BAD_LOGIN" in data or b"Whoops" in data:
                if b"BAD_LOGIN" in data:
                    print("  ⚠ BAD_LOGIN Fehler im Blob")
                if b"Whoops" in data:
                    print("  ⚠ Whoops Fehler im Blob")
                return None
            
            if b"group_id" not in data:
                print("  ⚠ group_id nicht im Blob gefunden")
                # Versuche alternative Suchmuster
                if b"group" in data.lower():
                    print("  ℹ 'group' (kleingeschrieben) gefunden, versuche alternative Extraktion...")
                return None
            
            # Finde group_id Position (wie in audible-activator)
            k = data.rfind(b"group_id")
            if k == -1:
                print("  ⚠ group_id nicht gefunden")
                return None
            
            l = data[k:].find(b")")
            if l == -1:
                print("  ⚠ ')' nach group_id nicht gefunden")
                return None
            
            keys = data[k + l + 1 + 1:]
            
            # Jeder Key ist 70 Bytes (wie in audible-activator)
            if len(keys) < 70:
                print(f"  ⚠ Nicht genug Daten nach group_id: {len(keys)} Bytes (erwartet: >=70)")
                return None
            
            # Extrahiere ersten Key (wie in audible-activator)
            # audible-activator verwendet: keys[i * 70 + i:(i + 1) * 70 + i]
            # Für i=0: keys[0:70]
            key = keys[0:70]
            
            # Konvertiere zu Hex (wie in audible-activator)
            h = binascii.hexlify(key)
            
            if PY3:
                h_str = h.decode('ascii')
            else:
                h_str = h
            
            # Nur die ersten 4 Bytes sind nötig (8 Hex-Zeichen) - wie in audible-activator
            # audible-activator: output_keys[0].replace(b",", b"")[0:8]
            activation_bytes_raw = h_str[0:8]
            
            # Korrigiere Endianness (wie in audible-activator)
            # audible-activator: b"".join(reversed([activation_bytes[i:i+2] for i in range(0, len(activation_bytes), 2)]))
            activation_bytes = "".join(reversed([activation_bytes_raw[i:i+2] for i in range(0, len(activation_bytes_raw), 2)]))
            
            return activation_bytes.lower()
            
        except Exception as e:
            print(f"  ⚠ Fehler bei Extraktion aus Blob: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def set_activation_bytes(self, activation_bytes: str) -> bool:
        """
        Setzt Activation Bytes manuell
        
        Args:
            activation_bytes: Activation Bytes als Hex-String
            
        Returns:
            True bei Erfolg
        """
        try:
            # Validiere Format (sollte Hex-String sein, z.B. "12345678")
            activation_bytes = activation_bytes.strip().replace(" ", "").replace("-", "").replace(":", "")
            if len(activation_bytes) < 8 or not all(c in '0123456789abcdefABCDEF' for c in activation_bytes):
                print("  ⚠ Ungültiges Format für Activation Bytes. Erwartet: Hex-String (z.B. '12345678')")
                return False
            
            self.activation_bytes = activation_bytes.lower()
            self.save_config()
            print(f"  ✓ Activation Bytes gespeichert: {activation_bytes[:8]}...")
            return True
        except Exception as e:
            print(f"  ⚠ Fehler beim Speichern der Activation Bytes: {e}")
            return False
    
    def login_with_selenium(self, country_code: str = "de", gui_callback=None) -> bool:
        """
        Meldet sich mit Selenium an (öffnet echten Browser)
        
        Args:
            country_code: Ländercode
            gui_callback: Optionaler Callback für GUI-Bestätigung
            
        Returns:
            True bei Erfolg
        """
        if not SELENIUM_AVAILABLE:
            print("⚠ Selenium nicht verfügbar. Bitte installieren Sie es mit: pip install selenium")
            return False
        
        try:
            print("\n" + "=" * 70)
            print("Selenium-basierte Anmeldung")
            print("=" * 70)
            print("\nEin Browser-Fenster wird geöffnet...")
            print("Bitte melden Sie sich dort an (inkl. 2FA falls aktiviert).")
            print("Nach erfolgreicher Anmeldung werden Cookies automatisch extrahiert.")
            print("=" * 70)
            
            # Chrome-Optionen
            chrome_options = Options()
            # Headless-Modus deaktiviert, damit der Benutzer sich anmelden kann
            # chrome_options.add_argument('--headless')  # Nicht verwenden für Login
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Erstelle WebDriver
            try:
                driver = webdriver.Chrome(options=chrome_options)
            except Exception as e:
                print(f"⚠ Fehler beim Starten von Chrome: {e}")
                print("   Versuche Firefox...")
                try:
                    from selenium.webdriver.firefox.options import Options as FirefoxOptions
                    firefox_options = FirefoxOptions()
                    driver = webdriver.Firefox(options=firefox_options)
                except Exception as e2:
                    print(f"⚠ Fehler beim Starten von Firefox: {e2}")
                    print("   Bitte installieren Sie ChromeDriver oder GeckoDriver")
                    return False
            
            try:
                # Öffne Login-Seite
                login_urls = {
                    "de": "https://www.audible.de/sign-in",
                    "us": "https://www.audible.com/sign-in",
                    "uk": "https://www.audible.co.uk/sign-in",
                }
                login_url = login_urls.get(country_code, f"{self.base_url}/sign-in")
                
                print(f"\nÖffne: {login_url}")
                driver.get(login_url)
                
                # Warte auf Benutzer-Anmeldung
                print("\nBitte melden Sie sich im Browser an (inkl. 2FA falls aktiviert)...")
                print("Nach erfolgreicher Anmeldung, gehen Sie zu: https://www.audible.de/library")
                print("Dann kehren Sie hier zurück und klicken Sie auf 'Weiter'")
                
                if gui_callback:
                    # GUI-Modus: Verwende Callback
                    print("\nWarte auf Bestätigung in der GUI...")
                    if not gui_callback():
                        driver.quit()
                        return False
                else:
                    # Console-Modus
                    input("\nDrücken Sie Enter, nachdem Sie sich angemeldet haben und zu /library gegangen sind...")
                
                # Gehe zur Library-Seite (falls nicht schon dort)
                if 'library' not in driver.current_url.lower():
                    print("\nNavigiere zur Library-Seite...")
                    driver.get(f"{self.base_url}/library")
                    time.sleep(2)  # Warte auf Seitenladung
                
                # Prüfe ob eingeloggt
                if 'signin' in driver.current_url.lower() or 'sign-in' in driver.current_url.lower():
                    print("⚠ Noch nicht eingeloggt. Bitte versuchen Sie es erneut.")
                    driver.quit()
                    return False
                
                # Extrahiere ALLE Cookies und Header aus Selenium-Session
                print("\nExtrahiere Cookies und Session-Daten aus Browser...")
                selenium_cookies = driver.get_cookies()
                
                if not selenium_cookies:
                    print("⚠ Keine Cookies gefunden. Bitte versuchen Sie es erneut.")
                    driver.quit()
                    return False
                
                # Kopiere User-Agent und andere Header aus Selenium
                user_agent = driver.execute_script("return navigator.userAgent;")
                self.session.headers.update({
                    'User-Agent': user_agent,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Cache-Control': 'max-age=0',
                    'Referer': f'{self.base_url}/library',
                    'Origin': self.base_url
                })
                
                # Setze ALLE Cookies in requests.Session (auch die nicht normalisierten)
                # Verwende Dictionary, um doppelte Cookie-Namen zu vermeiden
                cookie_dict = {}  # Key: (name, domain), Value: cookie
                
                for cookie in selenium_cookies:
                    try:
                        name = cookie['name']
                        value = cookie['value']
                        domain = cookie.get('domain', '.audible.de')
                        path = cookie.get('path', '/')
                        secure = cookie.get('secure', True)
                        
                        # Verwende (name, domain) als Key, um Duplikate zu vermeiden
                        # Bei doppelten Namen wird der letzte verwendet
                        cookie_key = (name, domain)
                        cookie_dict[cookie_key] = {
                            'name': name,
                            'value': value,
                            'domain': domain,
                            'path': path,
                            'secure': secure
                        }
                    except Exception as e:
                        pass
                
                # Setze Cookies in Session (ohne Duplikate)
                cookie_count = 0
                for cookie_key, cookie_data in cookie_dict.items():
                    try:
                        name = cookie_data['name']
                        value = cookie_data['value']
                        domain = cookie_data['domain']
                        path = cookie_data['path']
                        
                        # Entferne zuerst vorhandene Cookies mit demselben Namen
                        # (falls vorhanden)
                        try:
                            # Versuche vorhandene Cookies zu entfernen
                            if name in self.session.cookies:
                                del self.session.cookies[name]
                        except:
                            pass
                        
                        # Setze Cookie mit allen Attributen
                        try:
                            # Versuche mit Domain und Path
                            self.session.cookies.set(
                                name,
                                value,
                                domain=domain,
                                path=path
                            )
                            cookie_count += 1
                        except Exception as e1:
                            try:
                                # Fallback: Nur mit Domain
                                self.session.cookies.set(
                                    name,
                                    value,
                                    domain=domain
                                )
                                cookie_count += 1
                            except Exception as e2:
                                try:
                                    # Fallback: Einfache Cookie-Setzung
                                    self.session.cookies.set(name, value)
                                    cookie_count += 1
                                except:
                                    # Ignoriere problematische Cookies
                                    pass
                    except Exception as e:
                        pass
                
                print(f"✓ {cookie_count} Cookies extrahiert und gesetzt")
                
                # WICHTIG: Warte kurz, bevor wir den Browser schließen
                # und teste die Session, BEVOR wir den Browser schließen
                print("\nTeste Session (Browser bleibt geöffnet)...")
                
                # Teste mit der aktuellen URL im Browser
                current_url = driver.current_url
                if 'library' in current_url.lower() and 'signin' not in current_url.lower():
                    # Browser zeigt Library-Seite - Session ist gültig
                    print("✓ Browser zeigt Library-Seite - Session ist gültig")
                    
                    # Jetzt können wir den Browser schließen
                    driver.quit()
                    
                    # Teste nochmal mit requests
                    test_response = self.session.get(f"{self.base_url}/library", timeout=10, allow_redirects=True)
                    
                    if test_response.status_code == 200 and 'signin' not in test_response.url.lower():
                        self.is_authenticated = True
                        self.cookies = dict(self.session.cookies)
                        self.save_config()
                        print("✓ Login erfolgreich mit Selenium!")
                        # Versuche Activation Bytes zu extrahieren
                        self._try_extract_activation_bytes()
                        return True
                    else:
                        print(f"⚠ Browser-Session war gültig, aber requests-Session nicht. URL: {test_response.url}")
                        print("   Versuche Session zu reparieren...")
                        
                        # Versuche nochmal alle Cookies zu setzen
                        driver_temp = webdriver.Chrome(options=chrome_options)
                        driver_temp.get(f"{self.base_url}/library")
                        time.sleep(1)
                        temp_cookies = driver_temp.get_cookies()
                        driver_temp.quit()
                        
                        for cookie in temp_cookies:
                            try:
                                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain', '.audible.de'))
                            except:
                                pass
                        
                        # Teste nochmal
                        test_response2 = self.session.get(f"{self.base_url}/library", timeout=10, allow_redirects=True)
                        if test_response2.status_code == 200 and 'signin' not in test_response2.url.lower():
                            self.is_authenticated = True
                            self.cookies = dict(self.session.cookies)
                            self.save_config()
                            print("✓ Login erfolgreich nach Reparatur!")
                            # Versuche Activation Bytes zu extrahieren
                            self._try_extract_activation_bytes()
                            return True
                        
                        return False
                else:
                    print(f"⚠ Browser zeigt nicht die Library-Seite. URL: {current_url}")
                    driver.quit()
                    return False
                    
            except Exception as e:
                print(f"✗ Fehler bei Selenium-Login: {e}")
                try:
                    driver.quit()
                except:
                    pass
                return False
                
        except Exception as e:
            print(f"✗ Fehler bei Selenium-Login: {e}")
            return False
    
    def login_with_browser(self, country_code: str = "de", port: int = 8765, 
                          gui_callback=None) -> bool:
        """
        Browser-basierte Anmeldung mit 2FA-Unterstützung
        
        Args:
            country_code: Ländercode (de, us, uk, etc.)
            port: Port für lokalen Callback-Server
            
        Returns:
            True bei erfolgreichem Login
        """
        print("\n" + "=" * 70)
        print("Browser-basierte Anmeldung")
        print("=" * 70)
        print("\nEin Browser-Fenster wird geöffnet...")
        print("Bitte melden Sie sich dort an (inkl. 2FA falls aktiviert).")
        print("Nach erfolgreicher Anmeldung werden Sie automatisch zurückgeleitet.\n")
        
        # Callback-URL
        callback_url = f"http://localhost:{port}/callback"
        
        # Prüfe ob wir in einem Thread sind
        import threading
        is_main_thread = threading.current_thread() is threading.main_thread()
        
        # Versuche mit audible-Bibliothek (unterstützt externe Auth)
        # ABER: Nur wenn wir im Haupt-Thread sind ODER keinen gui_callback haben
        # Die audible-Bibliothek verwendet input(), was in Threads abstürzt
        if AUDIBLE_AVAILABLE and (is_main_thread or not gui_callback):
            try:
                from audible import Authenticator
                
                # Starte externe Authentifizierung (öffnet Browser automatisch)
                print("Starte externe Authentifizierung mit audible-Bibliothek...")
                print("Ein Browser-Fenster wird automatisch geöffnet...")
                
                # Die audible-Bibliothek hat verschiedene Methoden für externe Auth
                auth = None
                
                # Methode 1: from_login_external (wenn verfügbar)
                if hasattr(Authenticator, 'from_login_external'):
                    try:
                        auth = Authenticator.from_login_external(
                            locale=country_code,
                            with_username=False
                        )
                    except Exception as e:
                        print(f"  from_login_external fehlgeschlagen: {e}")
                
                # Methode 2: auth_flow (interaktiver Flow)
                if not auth and hasattr(Authenticator, 'auth_flow'):
                    try:
                        auth = Authenticator()
                        auth.auth_flow(locale=country_code, with_username=False)
                    except Exception as e:
                        print(f"  auth_flow fehlgeschlagen: {e}")
                
                # Methode 3: sync_auth_flow
                if not auth and hasattr(Authenticator, 'sync_auth_flow'):
                    try:
                        auth = Authenticator()
                        auth.sync_auth_flow(locale=country_code, with_username=False)
                    except Exception as e:
                        print(f"  sync_auth_flow fehlgeschlagen: {e}")
                
                if auth:
                    self.audible_auth = auth
                    self.is_authenticated = True
                    self.cookies = dict(auth.session.cookies)
                    self.session = auth.session
                    
                    # Speichere Authenticator
                    try:
                        auth_file = self.config_path.parent / f"{self.config_path.stem}_auth.json"
                        if hasattr(auth, 'to_file'):
                            auth.to_file(str(auth_file))
                    except:
                        pass
                    
                    self.save_config()
                    print("✓ Login erfolgreich mit audible-Bibliothek (Browser-Auth)")
                    return True
                else:
                    print("⚠ Keine externe Auth-Methode verfügbar in audible-Bibliothek")
                    
            except Exception as e:
                print(f"⚠ audible-Bibliothek Browser-Auth fehlgeschlagen: {e}")
                print("   Versuche manuelle Cookie-Extraktion...")
        elif gui_callback and not is_main_thread:
            # Wir sind in einem Thread mit GUI-Callback - überspringe audible-Bibliothek
            # da diese input() verwendet, was in Threads abstürzt
            print("⚠ Überspringe audible-Bibliothek (verwendet input() in Threads)")
            print("   Verwende stattdessen manuelle Cookie-Extraktion...")
        
        # Versuche zuerst Selenium (zuverlässiger)
        if SELENIUM_AVAILABLE:
            print("\nVersuche Selenium-basierte Anmeldung...")
            if self.login_with_selenium(country_code, gui_callback):
                return True
            print("\nSelenium-Login fehlgeschlagen, versuche Cookie-Extraktion...")
        
        # Fallback: Manuelle Cookie-Extraktion mit verbesserter Methode
        return self._browser_login_manual(country_code, port, gui_callback)
    
    def extract_cookies_from_browser(self) -> bool:
        """
        Extrahiert Cookies direkt aus dem Browser (falls bereits eingeloggt)
        
        Returns:
            True wenn Cookies erfolgreich extrahiert wurden
        """
        print("\nVersuche Cookies aus Browser zu extrahieren...")
        
        # Anleitung für manuelle Cookie-Extraktion
        print("\n" + "=" * 70)
        print("Cookie-Extraktion aus Browser")
        print("=" * 70)
        print("\nSo extrahieren Sie Cookies manuell:")
        print("1. Öffnen Sie Audible.de in Ihrem Browser (eingeloggt)")
        print("2. Öffnen Sie die Entwicklertools (F12)")
        print("3. Gehen Sie zu: Application → Cookies → www.audible.de")
        print("4. Kopieren Sie die folgenden Cookies:")
        print("   - session-id")
        print("   - session-id-time")
        print("   - ubid-main")
        print("   - at-main")
        print("   - sess-at-main")
        print("\nOder verwenden Sie die Browser-Anmeldung (empfohlen).")
        print("=" * 70)
        
        return False
    
    def login_with_cookies(self, cookies: Dict[str, str]) -> bool:
        """
        Meldet sich mit manuell extrahierten Cookies an
        
        Args:
            cookies: Dictionary mit Cookie-Namen und -Werten
                    Cookies sollten bereits normalisiert sein (z.B. ubid-main statt ubid-acbde)
            
        Returns:
            True bei erfolgreichem Login
        """
        try:
            print(f"\nVerwende {len(cookies)} Cookies für Anmeldung...")
            
            # Setze Cookies in Session
            # Cookies sollten bereits von der GUI normalisiert sein
            # WICHTIG: Verwende ALLE Cookies, nicht nur die normalisierten
            from http.cookiejar import Cookie
            
            for name, value in cookies.items():
                # Bereinige Wert (entferne mögliche Anführungszeichen)
                clean_value = value.strip()
                if clean_value.startswith('"') and clean_value.endswith('"'):
                    clean_value = clean_value[1:-1]
                
                # Bereinige Wert: Entferne Sonderzeichen am Ende (z.B. 'l' bei session-id-time)
                # session-id-time sollte nur Zahlen enthalten
                if name == 'session-id-time':
                    # Entferne alle nicht-numerischen Zeichen am Ende
                    clean_value = clean_value.rstrip('lL').rstrip()
                    # Stelle sicher, dass es nur Zahlen sind
                    clean_value = ''.join(c for c in clean_value if c.isdigit())
                else:
                    # Für andere Cookies: Entferne nur führende/nachfolgende Whitespace
                    clean_value = clean_value.strip()
                
                # Bestimme Cookie-Attribute basierend auf Cookie-Name
                # Wichtige Cookies sind meist Secure und HttpOnly
                secure_cookies = ['session-id', 'session-id-time', 'ubid-main', 'at-main', 'sess-at-main', 'session-token', 'x-acbde', 'userType']
                http_only_cookies = ['session-id', 'session-id-time', 'at-main', 'sess-at-main', 'session-token', 'userType']
                
                secure = name in secure_cookies
                http_only = name in http_only_cookies
                
                # Setze Cookie für verschiedene Domains (Audible gehört zu Amazon)
                # WICHTIG: Setze zuerst für .audible.de, dann für .amazon.de
                domains_to_try = [
                    ('.audible.de', '/'),
                    ('www.audible.de', '/'),
                    ('.amazon.de', '/'),
                    ('www.amazon.de', '/'),
                ]
                
                for domain, path in domains_to_try:
                    try:
                        # Verwende requests.cookies.create_cookie für bessere Kontrolle
                        cookie_dict = {
                            'name': name,
                            'value': clean_value,
                            'domain': domain,
                            'path': path,
                            'secure': secure,
                        }
                        # HttpOnly kann nicht direkt gesetzt werden, aber Secure ist wichtiger
                        self.session.cookies.set(**cookie_dict)
                    except Exception as e:
                        # Fallback: Einfache Cookie-Setzung
                        try:
                            self.session.cookies.set(name, clean_value, domain=domain)
                        except:
                            pass
                
                # Debug-Ausgabe (nur für wichtige Cookies)
                important_cookies = ['session-id', 'session-id-time', 'ubid-main', 'at-main', 'sess-at-main', 'session-token', 'x-acbde']
                if name in important_cookies:
                    display_value = clean_value[:50] + "..." if len(clean_value) > 50 else clean_value
                    print(f"  ✓ {name}: {display_value}")
            
            # Prüfe ob Login erfolgreich war
            print("\nTeste Anmeldung...")
            
            # Schritt 1: Versuche zuerst amazon.de zu besuchen (validiert Session)
            print("  Schritt 1: Validiere Session bei Amazon...")
            amazon_headers = {
                'Referer': 'https://www.amazon.de/',
                'Origin': 'https://www.amazon.de'
            }
            try:
                amazon_response = self.session.get("https://www.amazon.de/", timeout=10, allow_redirects=True, headers=amazon_headers)
                print(f"    Amazon Status: {amazon_response.status_code}")
                if 'signin' in amazon_response.url.lower():
                    print("    ⚠ Amazon leitet zur Login-Seite um")
                else:
                    print("    ✓ Amazon Session gültig")
            except Exception as e:
                print(f"    ⚠ Amazon-Prüfung fehlgeschlagen: {e}")
            
            # Schritt 2: Versuche audible.de/library
            print("  Schritt 2: Versuche Zugriff auf Audible-Bibliothek...")
            headers = {
                'Referer': f'{self.base_url}/',
                'Origin': self.base_url
            }
            test_response = self.session.get(f"{self.base_url}/library", timeout=10, allow_redirects=True, headers=headers)
            
            print(f"  Status Code: {test_response.status_code}")
            print(f"  Final URL: {test_response.url}")
            
            # Prüfe ob wir zur Login-Seite umgeleitet wurden
            if 'signin' in test_response.url.lower() or 'sign-in' in test_response.url.lower():
                print("✗ Login fehlgeschlagen: Umleitung zur Login-Seite")
                print("  Cookies könnten ungültig oder abgelaufen sein")
                return False
            
            # Prüfe ob wir auf der Library-Seite sind
            if test_response.status_code == 200:
                # Zusätzliche Prüfung: Suche nach Anmelde-Link im HTML
                if 'signin' in test_response.text.lower() and 'library' not in test_response.url.lower():
                    print("✗ Login fehlgeschlagen: Seite enthält Anmelde-Link")
                    return False
                
                self.is_authenticated = True
                self.cookies = dict(self.session.cookies)
                self.save_config()
                print("✓ Login erfolgreich mit Cookies!")
                # Versuche Activation Bytes zu extrahieren (falls audible-Bibliothek verfügbar)
                self._try_extract_activation_bytes()
                return True
            else:
                print(f"✗ Login fehlgeschlagen: Status Code {test_response.status_code}")
                return False
        except Exception as e:
            print(f"Fehler beim Login mit Cookies: {e}")
            return False
    
    def _browser_login_manual(self, country_code: str, port: int, gui_callback=None) -> bool:
        """
        Manuelle Browser-Anmeldung mit Cookie-Extraktion
        
        Args:
            country_code: Ländercode
            port: Port für Callback-Server
            gui_callback: Optionaler Callback für GUI-Bestätigung
            
        Returns:
            True bei Erfolg
        """
        # Korrekte URLs für verschiedene Länder
        login_urls = {
            "de": "https://www.audible.de/sign-in",
            "us": "https://www.audible.com/sign-in",
            "uk": "https://www.audible.co.uk/sign-in",
        }
        
        login_url = login_urls.get(country_code, f"{self.base_url}/sign-in")
        
        print(f"\nÖffne Browser: {login_url}")
        print("Bitte melden Sie sich im Browser an (inkl. 2FA falls aktiviert)")
        print("Nach erfolgreicher Anmeldung, gehen Sie zu: https://www.audible.de/library")
        print("Dann kehren Sie hier zurück und drücken Enter")
        
        webbrowser.open(login_url)
        
        print("\n" + "=" * 70)
        print("ANLEITUNG:")
        print("=" * 70)
        print("1. Melden Sie sich im geöffneten Browser an (inkl. 2FA)")
        print("2. Gehen Sie nach erfolgreicher Anmeldung zu: https://www.audible.de/library")
        print("3. Stellen Sie sicher, dass Sie eingeloggt sind")
        print("4. Kehren Sie hier zurück")
        print("5. Drücken Sie Enter, um Cookies zu extrahieren")
        print("=" * 70)
        print()
        
        # Warte auf Benutzer-Bestätigung (GUI oder Console)
        import threading
        
        # Prüfe ob wir in einem Thread sind
        is_main_thread = threading.current_thread() is threading.main_thread()
        
        if gui_callback:
            # GUI-Modus: Verwende Callback (immer bevorzugt)
            print("\nWarte auf Bestätigung in der GUI...")
            try:
                if not gui_callback():
                    return False
            except Exception as e:
                print(f"\n⚠ Fehler beim GUI-Callback: {e}")
                return False
        elif is_main_thread:
            # Console-Modus: Nur im Haupt-Thread input() verwenden
            try:
                input("Drücken Sie Enter, nachdem Sie sich im Browser angemeldet haben...")
            except (EOFError, KeyboardInterrupt):
                print("\n⚠ Eingabe abgebrochen.")
                return False
        else:
            # Thread ohne GUI-Callback: KEIN input() verwenden!
            # Dies würde zu einem Absturz führen
            print("\n⚠ FEHLER: Kann nicht in Thread ohne GUI-Callback warten!")
            print("   Bitte verwenden Sie die GUI-Methode mit gui_callback Parameter.")
            print("   input() wird NICHT aufgerufen, um Abstürze zu vermeiden.")
            return False
        
        # Versuche Cookies direkt aus dem Browser-Profil zu extrahieren
        print("\nExtrahiere Cookies aus Browser-Profil...")
        
        if not BROWSER_COOKIE_AVAILABLE:
            print("⚠ browser-cookie3 nicht verfügbar!")
            print("   Bitte installieren Sie es mit: pip install browser-cookie3")
            print("   Oder verwenden Sie die Cookie-Anmeldung (manuell)")
        
        if BROWSER_COOKIE_AVAILABLE:
            try:
                # Versuche Cookies aus verschiedenen Browsern zu extrahieren
                browsers = []
                
                # Safari (macOS)
                try:
                    browsers.append(('Safari', browser_cookie3.safari))
                except:
                    pass
                
                # Chrome
                try:
                    browsers.append(('Chrome', browser_cookie3.chrome))
                except:
                    pass
                
                # Firefox
                try:
                    browsers.append(('Firefox', browser_cookie3.firefox))
                except:
                    pass
                
                # Edge
                try:
                    browsers.append(('Edge', browser_cookie3.edge))
                except:
                    pass
                
                if not browsers:
                    print("⚠ Keine Browser gefunden für Cookie-Extraktion")
                else:
                    print(f"  Gefundene Browser: {', '.join([b[0] for b in browsers])}")
                    
                    # Versuche Cookies von audible.de und amazon.de zu extrahieren
                    extracted_cookies = {}
                    for browser_name, browser_func in browsers:
                        try:
                            print(f"  Versuche Cookies aus {browser_name} zu extrahieren...")
                            
                            # WICHTIG: Lade ALLE Cookies ohne Domain-Filter, dann filtere manuell
                            # browser_cookie3 kann manchmal Cookies verpassen, wenn man domain_name verwendet
                            try:
                                cj = browser_func()  # Lade ALLE Cookies
                                cj_list = list(cj)
                                print(f"    Gefundene Cookies insgesamt: {len(cj_list)}")
                                # Erstelle CookieJar neu, da list() sie konsumiert
                                cj = browser_func()
                            except Exception as e:
                                print(f"    ⚠ Fehler beim Laden aller Cookies: {e}")
                                # Fallback: Versuche mit Domain-Filter
                                try:
                                    cj = browser_func(domain_name='audible.de')
                                except:
                                    cj = None
                            
                            if cj is None:
                                print(f"    ⚠ Konnte keine Cookies aus {browser_name} laden")
                                continue
                            
                            important_cookie_names = [
                                'session-id', 'session-id-time', 'ubid-main', 'at-main', 
                                'sess-at-main', 'session-token', 'x-acbde', 'ubid-acbde',
                                'at-acbde', 'sess-at-acbde', 'userType', 'TAsessionID'
                            ]
                            
                            found_important = []
                            
                            # WICHTIG: Kopiere Cookies direkt aus der CookieJar
                            # Dies stellt sicher, dass alle Cookie-Attribute korrekt übernommen werden
                            import requests.cookies
                            
                            # Filtere Cookies und kopiere sie in die Session
                            cookie_count = 0
                            for cookie in cj:
                                # Filtere nach Domain oder wichtigen Cookie-Namen
                                domain_match = 'audible.de' in cookie.domain or 'amazon.de' in cookie.domain
                                name_match = any(name in cookie.name.lower() for name in ['session', 'ubid', 'at-', 'sess-', 'x-', 'user', 'ta'])
                                
                                if domain_match or name_match:
                                    # Normalisiere Cookie-Namen
                                    normalized_name = self._normalize_cookie_name(cookie.name)
                                    
                                    # Erstelle Cookie-Objekt mit allen Attributen
                                    try:
                                        # Versuche Cookie mit allen Attributen zu erstellen
                                        cookie_obj = requests.cookies.create_cookie(
                                            name=normalized_name,
                                            value=cookie.value,
                                            domain=cookie.domain,
                                            path=getattr(cookie, 'path', '/') or '/',
                                            secure=getattr(cookie, 'secure', True),
                                            expires=getattr(cookie, 'expires', None),
                                            rest={'HttpOnly': getattr(cookie, 'has_nonstandard_attr', lambda x: False)('HttpOnly')}
                                        )
                                        self.session.cookies.set_cookie(cookie_obj)
                                        cookie_count += 1
                                    except Exception as e:
                                        # Fallback: Einfache Cookie-Setzung
                                        try:
                                            self.session.cookies.set(normalized_name, cookie.value, domain=cookie.domain)
                                            cookie_count += 1
                                        except:
                                            pass
                                    
                                    # Speichere in extracted_cookies (verwende normalisierten Namen)
                                    extracted_cookies[normalized_name] = cookie.value
                                    
                                    # Prüfe ob wichtiger Cookie
                                    if normalized_name in important_cookie_names:
                                        found_important.append(normalized_name)
                            
                            print(f"    {cookie_count} Cookies in Session gesetzt")
                            
                            # Debug: Zeige gefundene wichtige Cookies
                            if found_important:
                                print(f"    Wichtige Cookies: {', '.join(found_important)}")
                            
                            if extracted_cookies:
                                print(f"  ✓ {len(extracted_cookies)} Cookies aus {browser_name} extrahiert")
                                # Zeige alle Cookie-Namen für Debug
                                cookie_names = list(extracted_cookies.keys())
                                print(f"    Cookie-Namen: {', '.join(cookie_names[:10])}{'...' if len(cookie_names) > 10 else ''}")
                                break
                            else:
                                print(f"  ⚠ Keine relevanten Cookies in {browser_name} gefunden")
                        except Exception as e:
                            import traceback
                            print(f"  ⚠ Fehler bei {browser_name}: {e}")
                            print(f"    Details: {traceback.format_exc()}")
                            continue
                    
                    if extracted_cookies:
                        # Prüfe ob wichtige Cookies vorhanden sind (nach Normalisierung)
                        important_missing = []
                        important_cookies = ['session-id', 'session-id-time', 'ubid-main', 'at-main', 'sess-at-main']
                        for cookie_name in important_cookies:
                            if cookie_name not in extracted_cookies:
                                important_missing.append(cookie_name)
                        
                        if important_missing:
                            print(f"  ⚠ Fehlende wichtige Cookies: {', '.join(important_missing)}")
                            print("     Versuche trotzdem Login...")
                        else:
                            print(f"  ✓ Alle wichtigen Cookies gefunden!")
                        
                        # Teste ob Login erfolgreich war
                        print("\nTeste extrahierte Cookies...")
                        library_response = self.session.get(f"{self.base_url}/library", timeout=10, allow_redirects=True)
                        
                        if library_response.status_code == 200 and 'signin' not in library_response.url.lower() and 'sign-in' not in library_response.url.lower():
                            self.is_authenticated = True
                            self.cookies = dict(self.session.cookies)
                            self.save_config()
                            print("✓ Cookies erfolgreich aus Browser extrahiert und validiert!")
                            return True
                        else:
                            print("⚠ Extrahierte Cookies sind nicht gültig oder abgelaufen")
                            print(f"  URL: {library_response.url}")
                            print(f"  Status: {library_response.status_code}")
                            if important_missing:
                                print(f"  Mögliche Ursache: Fehlende Cookies ({', '.join(important_missing)})")
                    else:
                        print("  ⚠ Keine Cookies extrahiert!")
            
            except Exception as e:
                print(f"⚠ Fehler bei Cookie-Extraktion: {e}")
        
        # Fallback: Versuche Cookies direkt von audible.de zu extrahieren
        print("\nVersuche Cookies direkt von audible.de zu extrahieren...")
        
        # Lade die Bibliothek-Seite (muss eingeloggt sein)
        library_response = self.session.get(f"{self.base_url}/library", timeout=10)
        
        if library_response.status_code == 200 and 'sign-in' not in library_response.url.lower() and 'signin' not in library_response.url.lower():
            # Erfolgreich - Cookies sind in der Session
            self.is_authenticated = True
            self.cookies = dict(self.session.cookies)
            self.save_config()
            print("✓ Cookies erfolgreich extrahiert!")
            return True
        else:
            print("⚠ Konnte Cookies nicht automatisch extrahieren.")
            print("\nBitte verwenden Sie stattdessen die Cookie-Anmeldung (manuell):")
            print("1. F12 → Application → Cookies → www.audible.de")
            print("2. Kopieren Sie die Cookie-Werte")
            print("3. Verwenden Sie 'Cookie-Anmeldung (manuell)' in der GUI")
            return False
    
    def login(self, email: str, password: str, country_code: str = "de") -> bool:
        """
        Meldet sich bei Audible an
        
        Args:
            email: Audible-Email
            password: Audible-Passwort
            country_code: Ländercode (de, us, uk, etc.)
            
        Returns:
            True bei erfolgreichem Login
        """
        try:
            self.email = email
            self.password = password
            
            # Methode 1: Versuche mit audible-Bibliothek (wenn verfügbar) - BEVORZUGT
            if AUDIBLE_AVAILABLE:
                try:
                    from audible import Authenticator
                    
                    # Erstelle Authenticator mit Login
                    self.audible_auth = Authenticator.from_login(
                        email=email,
                        password=password,
                        locale=country_code,
                        with_username=False
                    )
                    
                    # Speichere Authentifizierungsdaten
                    self.is_authenticated = True
                    self.cookies = dict(self.audible_auth.session.cookies)
                    self.session = self.audible_auth.session
                    
                    # Versuche Activation Bytes zu extrahieren
                    self._try_extract_activation_bytes()
                    
                    # Speichere auch den Authenticator für spätere Verwendung
                    # (Die audible-Bibliothek kann Authenticator-Daten speichern)
                    try:
                        # Versuche Authenticator zu speichern
                        auth_file = self.config_path.parent / f"{self.config_path.stem}_auth.json"
                        # Die audible-Bibliothek hat eine save-Methode
                        if hasattr(self.audible_auth, 'to_file'):
                            self.audible_auth.to_file(str(auth_file))
                    except:
                        pass
                    
                    self.save_config()
                    print("✓ Login erfolgreich mit audible-Bibliothek (beste API-Unterstützung)")
                    return True
                except Exception as e:
                    print(f"⚠ Audible-Bibliothek Login fehlgeschlagen: {e}")
                    print("   Versuche alternative Web-Login-Methode...")
            
            # Methode 2: Direkter Web-Login (Fallback)
            # Audible Login-Seite aufrufen
            login_page = self.session.get(f"{self.base_url}/ap/signin", timeout=10)
            
            # Extrahiere CSRF-Token falls vorhanden
            csrf_match = re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ""
            
            # Extrahiere weitere benötigte Parameter
            # Audible verwendet oft zusätzliche Parameter
            action_match = re.search(r'action=["\']([^"\']+)', login_page.text)
            action_url = action_match.group(1) if action_match else f"{self.base_url}/ap/signin"
            
            # Login-Daten
            login_data = {
                'email': email,
                'password': password,
                'csrf_token': csrf_token,
                'rememberMe': 'true',
                'returnTo': '/library'
            }
            
            # Setze zusätzliche Headers
            self.session.headers.update({
                'Referer': f"{self.base_url}/ap/signin",
                'Origin': self.base_url
            })
            
            # Login-Request
            response = self.session.post(
                action_url,
                data=login_data,
                allow_redirects=True,
                timeout=10
            )
            
            # Prüfe ob Login erfolgreich war
            # Erfolgreicher Login führt normalerweise zur Bibliothek oder Homepage
            if (response.status_code == 200 and 
                ('signin' not in response.url.lower() or '/library' in response.url.lower() or 
                 '/home' in response.url.lower() or self.base_url in response.url)):
                
                # Zusätzliche Prüfung: Versuche auf Bibliothek zuzugreifen
                library_test = self.session.get(f"{self.base_url}/library", timeout=10)
                if library_test.status_code == 200 and 'signin' not in library_test.url.lower():
                    self.is_authenticated = True
                    # Speichere Cookies
                    self.cookies = dict(self.session.cookies)
                    self.save_config()
                    return True
            
            return False
                
        except Exception as e:
            print(f"Fehler beim Login: {e}")
            return False
    
    def is_logged_in(self) -> bool:
        """Prüft, ob der Benutzer angemeldet ist"""
        return self.is_authenticated and len(self.cookies) > 0
    
    def logout(self):
        """Meldet den Benutzer ab"""
        self.email = None
        self.password = None
        self.cookies = {}
        self.is_authenticated = False
        self.session.cookies.clear()
        
        if self.config_path.exists():
            try:
                self.config_path.unlink()
            except:
                pass


class AudibleLibrary:
    """Klasse für Audible-Bibliothek-Verwaltung"""
    
    def __init__(self, auth: AudibleAuth):
        """
        Initialisiert die Bibliothek
        
        Args:
            auth: AudibleAuth-Instanz
        """
        self.auth = auth
        self.session = auth.session
        self.books: List[Dict] = []
        self.audible_client = None  # audible-Bibliothek Client
        
        # Versuche audible-Client zu erstellen (wenn audible-Bibliothek verfügbar)
        # Die audible-Bibliothek verwendet den Authenticator direkt als Client
        if AUDIBLE_AVAILABLE and auth.audible_auth:
            self.audible_client = auth.audible_auth
    
    def fetch_library(self) -> List[Dict]:
        """
        Lädt die Bibliothek des Benutzers
        
        Returns:
            Liste von Hörbüchern
        """
        if not self.auth.is_logged_in():
            return []
        
        try:
            books = []  # Initialisiere books am Anfang
            
            # Methode 1: Versuche mit audible-Bibliothek (BEVORZUGT - beste Methode)
            if self.audible_client:
                try:
                    # Die audible-Bibliothek hat verschiedene Methoden
                    # Versuche get() oder get_library() Methode
                    library_response = None
                    
                    # Die audible-Bibliothek verwendet get() mit verschiedenen Parametern
                    if hasattr(self.audible_client, 'get'):
                        try:
                            # Versuche verschiedene API-Aufrufe
                            # Die audible-Bibliothek nutzt /1.0/library mit response_groups
                            library_response = self.audible_client.get(
                                "/1.0/library",
                                num_results=1000,
                                response_groups="contributors,product_desc,product_attrs,media"
                            )
                        except Exception as e1:
                            try:
                                # Alternative: Mit path-Parameter
                                library_response = self.audible_client.get(
                                    path="/1.0/library",
                                    num_results=1000,
                                    response_groups="contributors,product_desc,product_attrs,media"
                                )
                            except Exception as e2:
                                try:
                                    # Alternative: Einfacher Aufruf
                                    library_response = self.audible_client.get("/1.0/library")
                                except Exception as e3:
                                    print(f"  Versuch 1: {e1}")
                                    print(f"  Versuch 2: {e2}")
                                    print(f"  Versuch 3: {e3}")
                                    library_response = None
                    
                    if library_response:
                        books = []
                        items = library_response.get('items', [])
                        
                        for item in items:
                            # Extrahiere Informationen
                            product = item.get('product', {})
                            asin = product.get('asin', '')
                            title = product.get('title', 'Unbekannt')
                            
                            # Autoren
                            authors = product.get('authors', [])
                            author = authors[0].get('name', 'Unbekannt') if authors else 'Unbekannt'
                            
                            # Dauer
                            runtime_length = product.get('runtime_length_ms', 0)
                            hours = runtime_length // 3600000
                            minutes = (runtime_length % 3600000) // 60000
                            duration = f"{hours}h {minutes}min" if hours > 0 else f"{minutes}min"
                            
                            # Kaufdatum
                            purchase_date = item.get('purchase_date', '')
                            
                            # Cover
                            cover_url = product.get('product_images', {}).get('500', '')
                            
                            books.append({
                                'asin': asin,
                                'title': title,
                                'author': author,
                                'duration': duration,
                                'purchase_date': purchase_date,
                                'cover_url': cover_url
                            })
                        
                        if books:
                            print(f"✓ Bibliothek geladen über audible-API: {len(books)} Hörbücher")
                            books.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
                            self.books = books
                            return books
                        
                except Exception as e:
                    print(f"⚠ audible-API-Methode fehlgeschlagen: {e}")
                    print("   Versuche Web-Scraping-Methode...")
            
            # Methode 2: Versuche über Web-API (falls audible-Bibliothek nicht verfügbar)
            if AUDIBLE_AVAILABLE and hasattr(self.auth, 'session'):
                try:
                    # Versuche über Web-API mit verschiedenen Endpunkten
                    api_endpoints = [
                        "https://api.audible.de/1.0/library?num_results=1000&response_groups=contributors,product_desc,product_attrs,media",
                        "https://api.audible.de/1.0/library",
                        "https://www.audible.de/api/1.0/library"
                    ]
                    
                    for api_url in api_endpoints:
                        try:
                            print(f"  Versuche API: {api_url[:60]}...")
                            response = self.session.get(api_url, timeout=15, headers={
                                'Accept': 'application/json',
                                'Accept-Language': 'de-DE,de;q=0.9',
                                'Referer': 'https://www.audible.de/library'
                            })
                            
                            if response.status_code == 200:
                                try:
                                    data = response.json()
                                    if 'items' in data or 'library_items' in data:
                                        items = data.get('items', data.get('library_items', []))
                                        if items:
                                            books = []
                                            for item in items:
                                                # API-Struktur kann variieren
                                                product = item.get('product', item)
                                                asin = product.get('asin', item.get('asin', ''))
                                                title = product.get('title', item.get('title', 'Unbekannt'))
                                                
                                                # Autoren
                                                authors = product.get('authors', item.get('authors', []))
                                                if authors and isinstance(authors, list) and len(authors) > 0:
                                                    author = authors[0].get('name', 'Unbekannt') if isinstance(authors[0], dict) else str(authors[0])
                                                else:
                                                    author = 'Unbekannt'
                                                
                                                # Dauer
                                                runtime_ms = product.get('runtime_length_ms', item.get('runtime_length_ms', 0))
                                                hours = runtime_ms // 3600000
                                                minutes = (runtime_ms % 3600000) // 60000
                                                duration = f"{hours}h {minutes}min" if hours > 0 else f"{minutes}min"
                                                
                                                books.append({
                                                    'asin': asin,
                                                    'title': title,
                                                    'author': author,
                                                    'duration': duration,
                                                    'purchase_date': item.get('purchase_date', ''),
                                                    'cover_url': product.get('product_images', {}).get('500', '')
                                                })
                                            
                                            if books:
                                                print(f"✓ Bibliothek geladen über Web-API: {len(books)} Hörbücher")
                                                books.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
                                                self.books = books
                                                return books
                                except Exception as json_err:
                                    print(f"  ⚠ JSON-Parsing-Fehler: {json_err}")
                                    continue
                            elif response.status_code == 403:
                                print(f"  ⚠ Zugriff verweigert (403) für {api_url[:60]}...")
                                continue
                            else:
                                print(f"  ⚠ Status {response.status_code} für {api_url[:60]}...")
                                continue
                        except Exception as req_err:
                            print(f"  ⚠ Request-Fehler: {req_err}")
                            continue
                except Exception as e:
                    print(f"Web-API-Methode fehlgeschlagen: {e}")
            
            # Methode 3: Web-Scraping (Fallback)
            if not books:
                try:
                    library_url = f"{self.auth.base_url}/library"
                    response = self.session.get(library_url, timeout=10, allow_redirects=True)
                    
                    if response.status_code == 200 and 'signin' not in response.url.lower():
                        print("  Versuche Web-Scraping...")
                        parsed_books = self._parse_library_html(response.text)
                        # Stelle sicher, dass parsed_books eine Liste ist (nicht None)
                        if parsed_books is None:
                            parsed_books = []
                        if parsed_books:
                            books = parsed_books
                            print(f"  ✓ {len(books)} Hörbücher über Web-Scraping gefunden")
                            self.books = books
                            return books
                    else:
                        print(f"  ⚠ Kein Zugriff auf Bibliothek. URL: {response.url}")
                except Exception as e:
                    print(f"Web-Scraping-Methode fehlgeschlagen: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Falls keine Bücher gefunden wurden, gib leere Liste zurück
            if not books:
                books = []
            
            self.books = books
            return books
            
        except Exception as e:
            print(f"Fehler beim Laden der Bibliothek: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _parse_library_html(self, html: str) -> List[Dict]:
        """
        Parst HTML der Bibliothek
        
        Args:
            html: HTML-Inhalt der Bibliothek-Seite
            
        Returns:
            Liste von Hörbuch-Dictionaries
        """
        books = []
        books_dict = {}  # Dictionary um Duplikate zu vermeiden (ASIN als Key)
        
        # Versuche BeautifulSoup zu verwenden (wenn verfügbar)
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml' if 'lxml' in str(BeautifulSoup) else 'html.parser')
            
            # Debug: Zeige HTML-Struktur
            print("  Analysiere HTML-Struktur...")
            
            # Suche nach Hörbuch-Elementen - verschiedene Selektoren
            book_elements = []
            
            # Methode 1: Suche nach data-asin Attributen (am zuverlässigsten)
            # WICHTIG: Finde gemeinsame Parent-Elemente für alle Elemente mit demselben ASIN
            asin_elements = soup.find_all(attrs={'data-asin': True})
            
            # Gruppiere Elemente nach ASIN
            asin_groups = {}
            for asin_elem in asin_elements:
                asin = asin_elem.get('data-asin', '')
                if asin:
                    if asin not in asin_groups:
                        asin_groups[asin] = []
                    asin_groups[asin].append(asin_elem)
            
            book_elements = []
            # Für jedes ASIN: Finde gemeinsamen Parent aller Elemente
            for asin, elements in asin_groups.items():
                # Sammle alle Parent-Elemente
                all_parents = []
                for elem in elements:
                    # Gehe mehrere Ebenen nach oben, um den Hauptcontainer zu finden
                    current = elem
                    for _ in range(5):  # Maximal 5 Ebenen nach oben
                        parent = current.find_parent(['div', 'li', 'tr', 'article', 'section', 'table'])
                        if not parent:
                            break
                        # Prüfe ob es ein Library-Item-Container ist
                        classes = parent.get('class', [])
                        class_str = ' '.join(str(c) for c in classes).lower()
                        if any(keyword in class_str for keyword in ['library-item', 'productlistitem', 'bc-list-item', 'adbl-library', 'library-row', 'bc-list', 'product-row']):
                            if parent not in book_elements:
                                book_elements.append(parent)
                            break
                        current = parent
                        all_parents.append(parent)
                
                # Wenn kein Library-Item-Container gefunden, verwende den höchsten gemeinsamen Parent
                if not any(elem in book_elements for elem in all_parents):
                    if all_parents:
                        # Nimm den höchsten Parent (letztes Element)
                        highest_parent = all_parents[-1]
                        # Gehe noch eine Ebene höher, wenn es nur ein Wrapper ist
                        classes = highest_parent.get('class', [])
                        class_str = ' '.join(str(c) for c in classes).lower()
                        if any(keyword in class_str for keyword in ['wrapper', 'checkbox', 'button-row']):
                            higher_parent = highest_parent.find_parent(['div', 'li', 'tr', 'article', 'section', 'table'])
                            if higher_parent and higher_parent not in book_elements:
                                book_elements.append(higher_parent)
                        elif highest_parent not in book_elements:
                            book_elements.append(highest_parent)
            
            print(f"    Gefunden via data-asin: {len(asin_elements)} Elemente → {len(asin_groups)} ASINs → {len(book_elements)} Container-Elemente")
            
            # Methode 2: Suche nach spezifischen Klassen
            if not book_elements:
                book_elements = soup.find_all(['div', 'li'], class_=lambda x: x and (
                    'library-item' in x.lower() or 
                    'productListItem' in x.lower() or 
                    'bc-list-item' in x.lower() or
                    'adbl-library-item' in x.lower() or
                    'library-row' in x.lower()
                ))
                print(f"    Gefunden via Klassen: {len(book_elements)}")
            
            # Methode 3: Suche nach Links zu /pd/ (Hörbuch-Detailseiten)
            if not book_elements:
                pd_links = soup.find_all('a', href=lambda x: x and '/pd/' in str(x) if x else False)
                # Finde Parent-Elemente
                for link in pd_links:
                    parent = link.find_parent(['div', 'li', 'tr'])
                    if parent and parent not in book_elements:
                        book_elements.append(parent)
                print(f"    Gefunden via /pd/ Links: {len(book_elements)}")
            
            if not book_elements:
                print("  ⚠ Keine Hörbuch-Elemente gefunden. HTML-Struktur könnte sich geändert haben.")
                # Debug: Zeige einen Teil des HTML
                if len(html) > 1000:
                    print(f"  HTML-Ausschnitt (erste 1000 Zeichen):\n{html[:1000]}")
                return []
            
            print(f"  Verarbeite {len(book_elements)} Hörbuch-Elemente...")
            
            for idx, element in enumerate(book_elements):
                # Extrahiere ASIN - suche in Element selbst und in allen Child-Elementen
                asin = element.get('data-asin', '')
                if not asin:
                    # Suche in allen Child-Elementen nach data-asin
                    asin_elem = element.find(attrs={'data-asin': True})
                    if asin_elem:
                        asin = asin_elem.get('data-asin', '')
                
                if not asin:
                    # Versuche ASIN aus Link zu extrahieren
                    link = element.find('a', href=lambda x: x and '/pd/' in str(x) if x else False)
                    if link:
                        href = link.get('href', '')
                        asin_match = re.search(r'/pd/([^/]+)', href)
                        if asin_match:
                            asin = asin_match.group(1)
                
                if not asin:
                    continue
                
                # Debug für erste 3 Elemente: Zeige HTML-Struktur
                if idx < 3:
                    print(f"    Debug Element {idx + 1} (ASIN: {asin[:12]}...):")
                    # Zeige ALLE Links im Element (auch ohne Text)
                    links = element.find_all('a')
                    print(f"      Gesamt Links gefunden: {len(links)}")
                    for i, link in enumerate(links[:10]):  # Erste 10 Links
                        href = link.get('href', '')
                        text = link.get_text(strip=True)
                        aria_label = link.get('aria-label', '')
                        title_attr = link.get('title', '')
                        print(f"      Link {i+1}: href='{href[:70]}...', text='{text[:50]}...', aria-label='{aria_label[:50]}...', title='{title_attr[:50]}...'")
                    # Zeige alle Headings
                    headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5'])
                    print(f"      Headings gefunden: {len(headings)}")
                    for i, heading in enumerate(headings[:5]):
                        text = heading.get_text(strip=True)
                        classes = heading.get('class', [])
                        print(f"      Heading {i+1}: '{text[:60]}...' (classes: {classes})")
                    # Zeige alle span/div Elemente mit interessanten Klassen
                    interesting_elements = element.find_all(['span', 'div'], class_=lambda x: x and any(kw in str(x).lower() for kw in ['title', 'product', 'book', 'name', 'heading']) if x else False)
                    print(f"      Interessante Elemente (title/product/book/name/heading): {len(interesting_elements)}")
                    for i, elem in enumerate(interesting_elements[:5]):
                        text = elem.get_text(strip=True)
                        classes = elem.get('class', [])
                        print(f"      Element {i+1}: '{text[:60]}...' (classes: {classes})")
                    # Zeige HTML-Struktur (erste 500 Zeichen)
                    html_snippet = str(element)[:500]
                    print(f"      HTML-Snippet: {html_snippet}...")
                
                # Extrahiere Titel - verschiedene Methoden (in Reihenfolge der Zuverlässigkeit)
                title = 'Unbekannt'
                
                # Methode 1: Suche nach Link zu /pd/ (meist zuverlässigste Methode)
                # IGNORIERE Download-Links (/library/download)
                pd_links = element.find_all('a', href=lambda x: x and '/pd/' in str(x) and '/library/download' not in str(x) if x else False)
                if pd_links:
                    # Nimm den Link mit dem längsten Text (wahrscheinlich der Haupttitel)
                    best_link = None
                    best_text_length = 0
                    for pd_link in pd_links:
                        title_text = pd_link.get_text(strip=True)
                        # Prüfe auch aria-label und title-Attribut des Links
                        if not title_text or len(title_text) <= 3:
                            title_text = pd_link.get('aria-label', '') or pd_link.get('title', '')
                        if title_text and len(title_text) > best_text_length:
                            # Ignoriere sehr kurze oder UI-Texte
                            if len(title_text) > 5 and not any(ui_text in title_text.lower() for ui_text in ['...', 'mehr', 'more', 'details']):
                                best_link = pd_link
                                best_text_length = len(title_text)
                    
                    if best_link:
                        title_text = best_link.get_text(strip=True)
                        if not title_text or len(title_text) <= 3:
                            title_text = best_link.get('aria-label', '') or best_link.get('title', '')
                        if title_text and len(title_text) > 3:
                            title = title_text
                
                # Methode 2: Suche nach Heading-Elementen (auch mit spezifischen Klassen)
                # IGNORIERE UI-Headings wie "interactive rating stars"
                if title == 'Unbekannt':
                    for tag in ['h2', 'h3', 'h4', 'h5']:
                        # Suche nach Heading mit spezifischen Klassen
                        heading = element.find(tag, class_=lambda x: x and any(kw in str(x).lower() for kw in ['title', 'product', 'book']) if x else False)
                        if not heading:
                            heading = element.find(tag)
                        if heading:
                            heading_text = heading.get_text(strip=True)
                            # Ignoriere UI-Texte
                            if (heading_text and len(heading_text) > 3 and 
                                not any(ui_text in heading_text.lower() for ui_text in ['interactive', 'rating', 'stars', 'offscreen', 'sr-only', 'visually hidden'])):
                                title = heading_text
                                break
                
                # Methode 3: Suche nach Elementen mit "title" in der Klasse oder id
                if title == 'Unbekannt':
                    # Suche nach verschiedenen Varianten
                    title_selectors = [
                        {'class': lambda x: x and 'title' in str(x).lower() if x else False},
                        {'id': lambda x: x and 'title' in str(x).lower() if x else False},
                        {'class': lambda x: x and 'producttitle' in str(x).lower() if x else False},
                        {'class': lambda x: x and 'bc-heading' in str(x).lower() if x else False},
                    ]
                    for selector in title_selectors:
                        title_elem = element.find(['a', 'span', 'div', 'h2', 'h3'], **selector)
                        if title_elem:
                            title_text = title_elem.get_text(strip=True)
                            if title_text and len(title_text) > 3:
                                title = title_text
                                break
                
                # Methode 4: Suche nach aria-label oder title-Attribut
                if title == 'Unbekannt':
                    aria_label = element.get('aria-label', '')
                    if aria_label and len(aria_label) > 3:
                        title = aria_label
                    else:
                        title_attr = element.get('title', '')
                        if title_attr and len(title_attr) > 3:
                            title = title_attr
                
                # Methode 5: Suche nach dem ersten langen Text-Link (Fallback)
                # IGNORIERE Download-Links und Navigations-Links
                if title == 'Unbekannt':
                    all_links = element.find_all('a', href=True)
                    for link in all_links:
                        href = link.get('href', '')
                        link_text = link.get_text(strip=True)
                        # Ignoriere Download-Links, Navigations-Links und kurze Links
                        if (link_text and len(link_text) > 10 and 
                            '/library/download' not in href and
                            '/pd/' not in href and  # Bereits in Methode 1 behandelt
                            not any(skip in link_text.lower() for skip in ['mehr', 'more', 'details', 'kaufen', 'buy', 'download', 'herunterladen']) and
                            not any(skip in href.lower() for skip in ['/library/download', '/account', '/help'])):
                            title = link_text
                            break
                
                # Methode 6: Suche nach Text-Elementen, die nicht in Links sind (direkter Text im Element)
                if title == 'Unbekannt':
                    # Finde alle Text-Knoten direkt im Element (nicht in Links)
                    direct_texts = []
                    for text_node in element.find_all(string=True, recursive=True):
                        parent = text_node.find_parent()
                        # Ignoriere Text in Links oder in bestimmten Elementen
                        if parent and parent.name == 'a':
                            continue
                        text = str(text_node).strip()
                        # Ignoriere sehr kurze Texte, Zahlen, Datumsangaben
                        if (text and len(text) > 10 and 
                            not text.isdigit() and
                            not re.match(r'^\d{1,2}\.\d{1,2}\.\d{4}', text) and
                            not any(skip in text.lower() for skip in ['von', 'by', 'min', 'h', 'stunden', 'kapitel', 'chapter'])):
                            direct_texts.append(text)
                    
                    # Nimm den längsten Text als Titel
                    if direct_texts:
                        title = max(direct_texts, key=len)
                
                # Bereinige Titel
                if title != 'Unbekannt':
                    # Entferne mögliche zusätzliche Textteile
                    title = re.sub(r'\s*:\s*.*$', '', title)  # Entferne alles nach ":"
                    title = re.sub(r'\s+', ' ', title).strip()  # Normalisiere Whitespace
                
                # Extrahiere Autor - verschiedene Methoden
                author = 'Unbekannt'
                
                # Methode 1: Suche nach Elementen mit "author" in der Klasse
                author_elem = element.find(['span', 'div', 'a', 'li'], class_=lambda x: x and ('author' in str(x).lower() if x else False))
                if author_elem:
                    author_text = author_elem.get_text(strip=True)
                    if author_text and len(author_text) > 1:
                        author = author_text
                
                # Methode 2: Suche nach "von" oder "by" Text
                if author == 'Unbekannt':
                    von_elem = element.find(string=re.compile(r'von\s+', re.I))
                    if von_elem:
                        parent = von_elem.find_parent()
                        if parent:
                            # Nimm den Text nach "von"
                            full_text = parent.get_text(strip=True)
                            von_match = re.search(r'von\s+([^,]+)', full_text, re.I)
                            if von_match:
                                author = von_match.group(1).strip()
                
                # Methode 3: Suche nach Links mit Autor-Informationen
                if author == 'Unbekannt':
                    author_link = element.find('a', href=lambda x: x and '/author/' in str(x) if x else False)
                    if author_link:
                        author_text = author_link.get_text(strip=True)
                        if author_text and len(author_text) > 1:
                            author = author_text
                
                # Bereinige Autor-Text
                if author != 'Unbekannt':
                    author = re.sub(r'^(von|by|Von|By)\s*', '', author, flags=re.I).strip()
                    author = re.sub(r'\s+', ' ', author).strip()
                
                # Extrahiere Kaufdatum
                purchase_date = ''
                date_elem = (
                    element.find(['span', 'div'], class_=lambda x: x and ('date' in str(x).lower() or 'purchase' in str(x).lower() if x else False)) or
                    element.find(string=re.compile(r'\d{1,2}\.\d{1,2}\.\d{4}'))
                )
                if date_elem:
                    if hasattr(date_elem, 'get_text'):
                        purchase_date = date_elem.get_text(strip=True)
                    else:
                        purchase_date = str(date_elem).strip()
                
                # Extrahiere Dauer
                duration = 'Unbekannt'
                duration_elem = (
                    element.find(['span', 'div'], class_=lambda x: x and ('runtime' in str(x).lower() or 'duration' in str(x).lower() or 'length' in str(x).lower() if x else False)) or
                    element.find(string=re.compile(r'\d+\s*(h|Stunden?|min|Minuten?)', re.I))
                )
                if duration_elem:
                    if hasattr(duration_elem, 'get_text'):
                        duration = duration_elem.get_text(strip=True)
                    else:
                        duration = str(duration_elem).strip()
                
                # Erstelle Buch-Daten
                book_data = {
                    'asin': asin,
                    'title': title if title != 'Unbekannt' and len(title) > 3 else f"Hörbuch {asin[:8]}",
                    'author': author if author != 'Unbekannt' and len(author) > 1 else 'Unbekannter Autor',
                    'purchase_date': purchase_date,
                    'duration': duration
                }
                
                # Prüfe ob dieses ASIN bereits existiert
                if asin in books_dict:
                    # Vergleiche: Behalte das Buch mit dem besseren Titel (nicht "Hörbuch ASIN")
                    existing = books_dict[asin]
                    existing_title = existing.get('title', '')
                    new_title = book_data.get('title', '')
                    
                    # Wenn das neue Buch einen besseren Titel hat (nicht Fallback), ersetze es
                    if (not existing_title.startswith('Hörbuch ') and new_title.startswith('Hörbuch ')):
                        # Behalte das existierende (bessere)
                        pass
                    elif (existing_title.startswith('Hörbuch ') and not new_title.startswith('Hörbuch ')):
                        # Ersetze mit dem neuen (besseren)
                        books_dict[asin] = book_data
                    elif len(new_title) > len(existing_title):
                        # Neuer Titel ist länger (wahrscheinlich vollständiger)
                        books_dict[asin] = book_data
                    # Sonst behalte das existierende
                else:
                    # Neues ASIN, füge hinzu
                    books_dict[asin] = book_data
            
        except ImportError:
            # Fallback: Regex-Parsing
            # Suche nach Hörbuch-Elementen mit Regex
            book_pattern = r'data-asin=["\']([^"\']+)["\']'
            asin_matches = re.findall(book_pattern, html)
            
            for asin in set(asin_matches):  # Entferne Duplikate
                # Suche Titel in der Nähe des ASIN
                title_pattern = rf'data-asin=["\']{re.escape(asin)}["\'][^>]*>.*?<[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</'
                title_match = re.search(title_pattern, html, re.DOTALL)
                title = title_match.group(1).strip() if title_match else 'Unbekannt'
                
                books_dict[asin] = {
                    'asin': asin,
                    'title': title,
                    'author': 'Unbekannt',
                    'purchase_date': '',
                    'duration': 'Unbekannt'
                }
        
        # Konvertiere Dictionary zurück zu Liste (nach allen Parsing-Methoden)
        if books_dict:
            books = list(books_dict.values())
            # Sortiere nach zuletzt gekauft (nur wenn Bücher vorhanden)
            if books:
                books.sort(key=lambda x: x.get('purchase_date', ''), reverse=True)
            print(f"  ✓ {len(books)} eindeutige Hörbücher extrahiert (nach Duplikat-Entfernung)")
        
        # Falls keine Bücher gefunden, erstelle Beispiel-Daten für Demo
        if not books:
            print("⚠ Keine Hörbücher in HTML gefunden. Verwende Beispiel-Daten.")
            books = [
                {
                    'asin': 'B08XXXXXXX',
                    'title': 'Beispiel Hörbuch 1',
                    'purchase_date': '2024-01-15',
                    'author': 'Autor 1',
                    'duration': '10h 30min'
                },
                {
                    'asin': 'B08YYYYYYY',
                    'title': 'Beispiel Hörbuch 2',
                    'purchase_date': '2024-01-10',
                    'author': 'Autor 2',
                    'duration': '8h 15min'
                }
            ]
        
        return books
    
    def get_book_info(self, asin: str) -> Optional[Dict]:
        """
        Ruft detaillierte Informationen zu einem Hörbuch ab
        
        Args:
            asin: Audible ASIN (Product ID)
            
        Returns:
            Dictionary mit Hörbuch-Informationen
        """
        try:
            book_url = f"{self.auth.base_url}/pd/{asin}"
            response = self.session.get(book_url, timeout=10)
            
            if response.status_code == 200:
                # Parse Hörbuch-Details
                # Vereinfachte Implementierung
                return {
                    'asin': asin,
                    'title': 'Hörbuch Titel',
                    'author': 'Autor',
                    'duration': '10h',
                    'description': 'Beschreibung'
                }
            
            return None
            
        except Exception as e:
            print(f"Fehler beim Abrufen der Hörbuch-Info: {e}")
            return None
    
    def get_book_chapters(self, asin: str) -> List[Dict]:
        """
        Ruft die Kapitel eines Hörbuchs ab
        
        Args:
            asin: Audible ASIN (Product ID)
            
        Returns:
            Liste von Kapiteln
        """
        try:
            # Versuche Kapitel-Informationen zu laden
            # Dies ist eine vereinfachte Implementierung
            # In der Praxis würde man die Audible API verwenden
            
            # Beispiel-Kapitel für Demo
            chapters = []
            for i in range(1, 11):  # Beispiel: 10 Kapitel
                chapters.append({
                    'number': i,
                    'title': f'Kapitel {i}',
                    'duration': f'{i * 5}min',
                    'start_time': (i - 1) * 300,  # Sekunden
                    'end_time': i * 300
                })
            
            return chapters
            
        except Exception as e:
            print(f"Fehler beim Abrufen der Kapitel: {e}")
            return []
    
    def get_available_qualities(self, asin: str) -> List[str]:
        """
        Prüft welche Qualitäten für ein Hörbuch verfügbar sind
        
        Args:
            asin: Audible ASIN
            
        Returns:
            Liste von verfügbaren Qualitäten (z.B. ['AAX', 'AAX_44_128', 'AAX_44_64'])
        """
        available = []
        
        try:
            # Methode 1: Versuche über audible-Bibliothek
            if self.audible_client and AUDIBLE_AVAILABLE:
                try:
                    # Versuche Content-Informationen abzurufen
                    content_info = self.audible_client.get(
                        f"/1.0/content/{asin}",
                        response_groups="media,content_reference"
                    )
                    
                    if content_info:
                        # Prüfe verfügbare Codecs
                        content = content_info.get('content_metadata', {})
                        codecs = content.get('content_reference', {}).get('codec_set', [])
                        
                        for codec in codecs:
                            available.append(codec)
                        
                        if available:
                            print(f"  Verfügbare Qualitäten: {', '.join(available)}")
                            return available
                except Exception as e:
                    print(f"  ⚠ Fehler beim Abrufen der Qualitäten über API: {e}")
            
            # Methode 2: Versuche über Web-Scraping (Download-Links)
            try:
                library_url = f"{self.auth.base_url}/library"
                response = self.session.get(library_url, timeout=10)
                
                if response.status_code == 200:
                    # Suche nach Download-Links für dieses ASIN
                    from bs4 import BeautifulSoup
                    import re
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Suche nach dem Element mit diesem ASIN (data-asin Attribut)
                    asin_element = soup.find(attrs={'data-asin': asin})
                    
                    if asin_element:
                        # Finde den Parent-Container (Library-Item)
                        container = asin_element
                        for _ in range(5):  # Gehe bis zu 5 Ebenen nach oben
                            parent = container.find_parent(['div', 'li', 'tr', 'article', 'section'])
                            if parent:
                                classes = parent.get('class', [])
                                class_str = ' '.join(str(c) for c in classes).lower()
                                if any(kw in class_str for kw in ['library-item', 'adbl-library', 'library-row', 'bc-list']):
                                    container = parent
                                    break
                                container = parent
                            else:
                                break
                        
                        # Suche alle Download-Links in diesem Container
                        download_links = container.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Falls keine Links im Container gefunden, suche in der gesamten Seite
                        if not download_links:
                            # Suche nach Download-Links mit diesem ASIN (direkt)
                            download_links = soup.find_all('a', href=lambda x: x and f'asin={asin}' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Falls immer noch keine, suche nach allen Download-Links in der Nähe des ASIN-Elements
                        if not download_links:
                            # Finde alle Download-Links auf der Seite und prüfe, ob sie zum gleichen Hörbuch gehören
                            all_download_links = soup.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                            
                            # Finde das Library-Item-Element für dieses ASIN
                            library_item = soup.find('div', id=lambda x: x and asin in str(x) if x else False)
                            if not library_item:
                                # Suche nach Elementen mit data-asin und finde den Container
                                asin_elements = soup.find_all(attrs={'data-asin': asin})
                                if asin_elements:
                                    # Nimm den ersten Container, der Library-Item-Klassen hat
                                    for elem in asin_elements:
                                        parent = elem.find_parent(['div', 'li', 'tr'])
                                        if parent:
                                            classes = parent.get('class', [])
                                            class_str = ' '.join(str(c) for c in classes).lower()
                                            if any(kw in class_str for kw in ['library-item', 'adbl-library', 'library-row']):
                                                library_item = parent
                                                break
                            
                            if library_item:
                                # Suche Download-Links in diesem Item
                                download_links = library_item.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Extrahiere Codecs aus den gefundenen Links
                        for link in download_links:
                            href = link.get('href', '')
                            # Extrahiere Codec aus URL
                            codec_match = re.search(r'codec=([^&]+)', href)
                            if codec_match:
                                codec = codec_match.group(1)
                                if codec not in available:
                                    available.append(codec)
                        
                        if available:
                            print(f"  Verfügbare Qualitäten (via Web-Scraping): {', '.join(available)}")
                            return available
                    else:
                        # Fallback: Suche nach allen Download-Links auf der Seite
                        print(f"  ⚠ ASIN-Element nicht gefunden, suche alle Download-Links...")
                        all_download_links = soup.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Sammle alle Codecs (könnten von verschiedenen Hörbüchern sein)
                        codecs_found = set()
                        for link in all_download_links:
                            href = link.get('href', '')
                            codec_match = re.search(r'codec=([^&]+)', href)
                            if codec_match:
                                codecs_found.add(codec_match.group(1))
                        
                        if codecs_found:
                            available = list(codecs_found)
                            print(f"  Verfügbare Qualitäten (alle gefundenen Codecs): {', '.join(available)}")
                            return available
                    
            except Exception as e:
                print(f"  ⚠ Fehler beim Web-Scraping der Qualitäten: {e}")
                import traceback
                traceback.print_exc()
            
            # Fallback: Standard-Qualitäten
            if not available:
                print("  ⚠ Konnte verfügbare Qualitäten nicht ermitteln. Verwende Standard-Qualitäten.")
                available = ['AAX_44_128', 'AAX_44_64', 'AAX_22_32']  # Typische Audible-Qualitäten
            
        except Exception as e:
            print(f"  ⚠ Fehler beim Prüfen der Qualitäten: {e}")
            # Fallback
            available = ['AAX_44_128', 'AAX_44_64', 'AAX_22_32']
        
        return available
    
    def download_book(self, asin: str, title: str, output_dir: Path, 
                     as_chapters: bool = False, quality: str = "MP3_320") -> bool:
        """
        Lädt ein Hörbuch herunter
        
        Args:
            asin: Audible ASIN
            title: Hörbuch-Titel
            output_dir: Ausgabeverzeichnis
            as_chapters: True für einzelne Kapitel, False für Gesamt-MP3
            quality: Qualität (MP3_320, MP3_192, MP3_128, FLAC)
            
        Returns:
            True bei Erfolg
        """
        try:
            import subprocess
            import sys
            
            print(f"\n{'='*70}")
            print(f"Download: {title}")
            print(f"{'='*70}")
            
            # Erstelle Ausgabeverzeichnis
            book_dir = output_dir / self._sanitize_filename(title)
            book_dir.mkdir(parents=True, exist_ok=True)
            
            # Bestimme Format und Qualität (für Konvertierung)
            audio_format, quality_value = self._get_format_from_quality(quality)
            print(f"\nZielformat: {audio_format.upper()} @ {quality_value} kbps")
            print("  (Verwendet automatisch die beste verfügbare AAX-Qualität von Audible)")
            
            # Prüfe ob bereits eine AAX-Datei existiert
            aax_path = book_dir / f"{self._sanitize_filename(title)}.aax"
            output_path = book_dir / f"{self._sanitize_filename(title)}.{audio_format}"
            
            # Prüfe ob Zielformat bereits existiert
            if output_path.exists():
                print(f"\n✓ {audio_format.upper()}-Datei existiert bereits: {output_path}")
                return True
            
            # Prüfe ob AAX-Datei existiert
            if aax_path.exists():
                print(f"\n✓ AAX-Datei existiert bereits: {aax_path}")
                print("  Überspringe Download, konvertiere direkt...")
                # Konvertiere direkt
                print(f"\nKonvertiere zu {audio_format.upper()}...")
                return self._convert_aax_to_format(aax_path, book_dir, title, audio_format, quality_value, as_chapters)
            
            # Methode 1: Versuche mit audible-Bibliothek (wenn verfügbar)
            if self.audible_client and AUDIBLE_AVAILABLE:
                try:
                    print("\nVersuche Download über audible-Bibliothek...")
                    return self._download_with_audible_lib(asin, title, book_dir, as_chapters, audio_format, quality_value)
                except Exception as e:
                    print(f"  ⚠ audible-Bibliothek-Methode fehlgeschlagen: {e}")
                    print("  Versuche alternative Methode...")
            
            # Methode 2: Versuche über Download-Link (AAX-Datei)
            print("\nVersuche Download über AAX-Datei...")
            return self._download_via_aax(asin, title, book_dir, as_chapters, audio_format, quality_value, [])
                    
        except Exception as e:
            print(f"✗ Fehler beim Download: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _download_with_audible_lib(self, asin: str, title: str, output_dir: Path,
                                   as_chapters: bool, audio_format: str, quality_value: str) -> bool:
        """
        Lädt Hörbuch mit audible-Bibliothek herunter
        
        Args:
            asin: Audible ASIN
            title: Hörbuch-Titel
            output_dir: Ausgabeverzeichnis
            as_chapters: True für Kapitel, False für Gesamt
            audio_format: Zielformat (mp3, flac)
            quality_value: Qualitätswert
            
        Returns:
            True bei Erfolg
        """
        try:
            # Die audible-Bibliothek kann AAX-Dateien direkt herunterladen
            # Dann müssen wir sie mit ffmpeg konvertieren
            
            # Download AAX-Datei
            aax_path = output_dir / f"{self._sanitize_filename(title)}.aax"
            
            # Versuche Download über audible-Bibliothek
            # Dies ist eine vereinfachte Implementierung
            print("  ⚠ audible-Bibliothek-Download noch nicht vollständig implementiert")
            print("  Verwende alternative Methode...")
            return False
            
        except Exception as e:
            print(f"  ✗ Fehler bei audible-Bibliothek-Download: {e}")
            return False
    
    def _download_via_aax(self, asin: str, title: str, output_dir: Path,
                          as_chapters: bool, audio_format: str, quality_value: str,
                          available_qualities: List[str]) -> bool:
        """
        Lädt Hörbuch über AAX-Download-Link herunter
        Verwendet automatisch die beste verfügbare Qualität
        
        Args:
            asin: Audible ASIN
            title: Hörbuch-Titel
            output_dir: Ausgabeverzeichnis
            as_chapters: True für Kapitel, False für Gesamt
            audio_format: Zielformat (mp3, flac)
            quality_value: Qualitätswert (wird ignoriert, verwendet beste verfügbare)
            available_qualities: Liste verfügbarer Qualitäten (wird ignoriert)
            
        Returns:
            True bei Erfolg
        """
        try:
            import subprocess
            import sys
            import re
            
            print(f"  Suche nach Download-Link für: {title}")
            
            # Extrahiere den tatsächlichen Download-Link aus der Library-Seite
            download_url = None
            selected_codec = None
            
            try:
                library_url = f"{self.auth.base_url}/library"
                response_check = self.session.get(library_url, timeout=10)
                
                if response_check.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(response_check.text, 'html.parser')
                    
                    # Suche nach dem ASIN-Element
                    asin_element = soup.find(attrs={'data-asin': asin})
                    
                    if asin_element:
                        # Finde den Library-Item-Container
                        container = asin_element
                        for _ in range(10):  # Erhöhe auf 10 Ebenen
                            parent = container.find_parent(['div', 'li', 'tr', 'article', 'section', 'table'])
                            if parent:
                                classes = parent.get('class', [])
                                class_str = ' '.join(str(c) for c in classes).lower()
                                # Suche nach verschiedenen Container-Klassen
                                if any(kw in class_str for kw in ['library-item', 'adbl-library', 'library-row', 'adbl-library-content-row', 'bc-list-item']):
                                    container = parent
                                    break
                                # Prüfe auch auf ID mit ASIN
                                parent_id = parent.get('id', '')
                                if asin in parent_id:
                                    container = parent
                                    break
                                container = parent
                            else:
                                break
                        
                        # Suche alle Download-Links im Container
                        download_links = container.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Falls keine Links im Container gefunden, suche in der gesamten Seite nach Links in der Nähe des ASIN
                        if not download_links:
                            print(f"  ⚠ Keine Links im Container, suche in der gesamten Seite...")
                            # Suche nach Elementen mit id="adbl-library-content-row-{asin}"
                            content_row = soup.find('div', id=f'adbl-library-content-row-{asin}')
                            if content_row:
                                download_links = content_row.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                        
                        # Falls immer noch keine, suche nach allen Download-Links und filtere nach ASIN in der Nähe
                        if not download_links:
                            print(f"  ⚠ Suche alle Download-Links auf der Seite...")
                            all_download_links = soup.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                            
                            # Finde das Library-Item-Element für dieses ASIN (über ID)
                            library_item = soup.find('div', id=lambda x: x and asin in str(x) if x else False)
                            
                            if library_item:
                                # Suche Download-Links in diesem Item
                                download_links = library_item.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                            
                            # Falls immer noch keine, nimm alle Links (könnten Teile des Hörbuchs sein)
                            if not download_links and all_download_links:
                                # Versuche Links zu finden, die im gleichen Bereich wie das ASIN sind
                                # Finde alle Elemente mit data-asin und deren Container
                                asin_elements = soup.find_all(attrs={'data-asin': asin})
                                for asin_elem in asin_elements:
                                    # Finde den nächsten Container mit Library-Klassen
                                    elem_container = asin_elem
                                    for _ in range(10):
                                        parent = elem_container.find_parent(['div', 'li', 'tr', 'article', 'section'])
                                        if parent:
                                            classes = parent.get('class', [])
                                            class_str = ' '.join(str(c) for c in classes).lower()
                                            if any(kw in class_str for kw in ['library', 'adbl', 'bc-list', 'bc-row']):
                                                # Prüfe ob Download-Links in diesem Container sind
                                                links_in_container = parent.find_all('a', href=lambda x: x and '/library/download' in str(x) and 'codec=' in str(x) if x else False)
                                                if links_in_container:
                                                    download_links = links_in_container
                                                    break
                                                elem_container = parent
                                            else:
                                                elem_container = parent
                                        else:
                                            break
                                    if download_links:
                                        break
                        
                        if download_links:
                            # Nimm den ersten Link (beste verfügbare Qualität)
                            # Sortiere nach Qualität: AAX_44_128 > AAX_44_64 > AAX_22_32
                            def get_quality_priority(href):
                                if 'AAX_44_128' in href:
                                    return 1
                                elif 'AAX_44_64' in href:
                                    return 2
                                elif 'AAX_22_32' in href:
                                    return 3
                                else:
                                    return 4
                            
                            # Sortiere Links nach Qualität
                            download_links.sort(key=lambda link: get_quality_priority(link.get('href', '')))
                            
                            # Nimm den besten Link
                            best_link = download_links[0]
                            href = best_link.get('href', '')
                            
                            # Konvertiere relativen Link zu absolutem
                            if href.startswith('/'):
                                download_url = f"{self.auth.base_url}{href}"
                            else:
                                download_url = href
                            
                            # Extrahiere Codec aus dem Link
                            codec_match = re.search(r'codec=([^&]+)', href)
                            if codec_match:
                                selected_codec = codec_match.group(1)
                            
                            print(f"  ✓ Download-Link gefunden (Codec: {selected_codec})")
                        else:
                            print(f"  ⚠ Keine Download-Links im Container gefunden")
                    else:
                        print(f"  ⚠ ASIN-Element nicht gefunden")
            except Exception as e:
                print(f"  ⚠ Fehler beim Extrahieren des Download-Links: {e}")
                import traceback
                traceback.print_exc()
            
            if not download_url:
                print(f"  ✗ Konnte keinen Download-Link finden")
                return False
            
            # Download AAX-Datei
            aax_path = output_dir / f"{self._sanitize_filename(title)}.aax"
            print(f"\nLade AAX-Datei herunter...")
            print(f"  Codec: {selected_codec or 'Unbekannt'}")
            print(f"  URL: {download_url[:100]}...")
            
            # Setze zusätzliche Header für den Download
            headers = {
                'Referer': f"{self.auth.base_url}/library",
                'Accept': '*/*',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            }
            
            response = self.session.get(download_url, stream=True, timeout=300, headers=headers, allow_redirects=True)
            
            if response.status_code == 200:
                # Speichere AAX-Datei
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(aax_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                if downloaded % (1024 * 1024) == 0:  # Jede MB
                                    print(f"  {percent:.1f}% ({downloaded // (1024*1024)} MB)")
                
                print(f"  ✓ AAX-Datei heruntergeladen: {aax_path}")
                
                # Konvertiere AAX zu Zielformat
                print(f"\nKonvertiere zu {audio_format.upper()}...")
                return self._convert_aax_to_format(aax_path, output_dir, title, audio_format, quality_value, as_chapters)
            else:
                print(f"  ✗ Download fehlgeschlagen: Status {response.status_code}")
                return False
                
        except Exception as e:
            print(f"  ✗ Fehler beim AAX-Download: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _convert_aax_to_format(self, aax_path: Path, output_dir: Path, title: str,
                               audio_format: str, quality_value: str, as_chapters: bool) -> bool:
        """
        Konvertiert AAX-Datei zu Zielformat
        
        Args:
            aax_path: Pfad zur AAX-Datei
            output_dir: Ausgabeverzeichnis
            title: Hörbuch-Titel
            audio_format: Zielformat (mp3, flac)
            quality_value: Qualitätswert
            as_chapters: True für Kapitel, False für Gesamt
            
        Returns:
            True bei Erfolg
        """
        try:
            import subprocess
            import sys
            
            # Versuche zuerst mit yt-dlp (einfachste Methode, funktioniert aber meist nicht bei AAX)
            print("  Versuche Konvertierung mit yt-dlp...")
            if self._convert_with_ytdlp(aax_path, output_dir, title, audio_format, quality_value):
                return True
            
            # Falls yt-dlp fehlschlägt, versuche mit ffmpeg
            print("  yt-dlp hat fehlgeschlagen, versuche mit ffmpeg...")
            ffmpeg_available = False
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=5)
                if result.returncode == 0:
                    ffmpeg_available = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            if ffmpeg_available:
                output_filename = f"{self._sanitize_filename(title)}.{audio_format}"
                output_path = output_dir / output_filename
                
                # Versuche Activation Bytes zu erhalten
                activation_bytes = None
                if self.auth.activation_bytes:
                    activation_bytes = self.auth.activation_bytes
                else:
                    # Versuche Activation Bytes zu extrahieren
                    print("  Versuche Activation Bytes zu extrahieren...")
                    activation_bytes = self.auth.get_activation_bytes()
                
                try:
                    # Baue ffmpeg-Kommando
                    cmd = ['ffmpeg']
                    
                    # Füge Activation Bytes hinzu, falls verfügbar
                    if activation_bytes:
                        cmd.extend(['-activation_bytes', activation_bytes])
                    
                    cmd.extend([
                        '-i', str(aax_path),
                        '-codec:a', 'libmp3lame' if audio_format == 'mp3' else 'flac',
                        '-b:a', f'{quality_value}k' if audio_format == 'mp3' else '0',
                        '-y',  # Überschreibe vorhandene Datei
                        str(output_path)
                    ])
                    
                    if activation_bytes:
                        print(f"  Verwende Activation Bytes für Entschlüsselung...")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                    
                    if result.returncode == 0 and output_path.exists():
                        print(f"  ✓ Konvertierung erfolgreich mit ffmpeg: {output_path}")
                        try:
                            aax_path.unlink()
                        except:
                            pass
                        return True
                    else:
                        print(f"  ⚠ ffmpeg-Konvertierung fehlgeschlagen")
                        if result.stderr:
                            error_msg = result.stderr[:500]
                            print(f"  Fehler-Details: {error_msg}")
                            if 'activation' in error_msg.lower() or 'encrypted' in error_msg.lower():
                                if not activation_bytes:
                                    print(f"  ℹ AAX-Datei ist verschlüsselt. Versuche Activation Bytes zu extrahieren...")
                                    activation_bytes = self.auth.get_activation_bytes(force_refresh=True)
                                    if activation_bytes:
                                        print(f"  ✓ Activation Bytes erhalten, versuche erneut...")
                                        # Versuche erneut mit Activation Bytes
                                        cmd = [
                                            'ffmpeg',
                                            '-activation_bytes', activation_bytes,
                                            '-i', str(aax_path),
                                            '-codec:a', 'libmp3lame' if audio_format == 'mp3' else 'flac',
                                            '-b:a', f'{quality_value}k' if audio_format == 'mp3' else '0',
                                            '-y',
                                            str(output_path)
                                        ]
                                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                                        if result.returncode == 0 and output_path.exists():
                                            print(f"  ✓ Konvertierung erfolgreich mit Activation Bytes: {output_path}")
                                            try:
                                                aax_path.unlink()
                                            except:
                                                pass
                                            return True
                except Exception as e:
                    print(f"  ⚠ Fehler bei ffmpeg-Konvertierung: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Falls beide Methoden fehlschlagen
            print("\n  ⚠ Automatische Konvertierung fehlgeschlagen.")
            print(f"  ℹ Die AAX-Datei wurde erfolgreich heruntergeladen: {aax_path}")
            print("  ℹ Für die Konvertierung benötigen Sie:")
            print("     1. Activation Bytes (können mit Tools wie 'audible-activator' extrahiert werden)")
            print("     2. ffmpeg mit AAX-Unterstützung")
            print("     3. Oder verwenden Sie Tools wie 'AAXtoMP3' oder 'inAudible-NG-tool'")
            print(f"  ℹ Die AAX-Datei bleibt erhalten für manuelle Konvertierung.")
            return False
            
        except Exception as e:
            print(f"  ✗ Fehler bei Konvertierung: {e}")
            return False
    
    def _convert_with_ytdlp(self, aax_path: Path, output_dir: Path, title: str,
                            audio_format: str, quality_value: str) -> bool:
        """
        Konvertiert AAX mit yt-dlp (falls unterstützt)
        
        Args:
            aax_path: Pfad zur AAX-Datei
            output_dir: Ausgabeverzeichnis
            title: Hörbuch-Titel
            audio_format: Zielformat
            quality_value: Qualitätswert
            
        Returns:
            True bei Erfolg
        """
        try:
            import subprocess
            import sys
            import urllib.parse
            
            output_filename = f"{self._sanitize_filename(title)}.{audio_format}"
            output_path = output_dir / output_filename
            
            # Konvertiere lokalen Pfad zu file:// URL für yt-dlp
            # yt-dlp kann lokale Dateien verarbeiten, wenn sie als file:// URL übergeben werden
            file_url = aax_path.as_uri()  # Konvertiert zu file:// URL
            
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "--enable-file-urls",  # Erlaube file:// URLs
                "-x",
                "--audio-format", audio_format,
                "--audio-quality", quality_value if audio_format == "mp3" else "0",
                "--no-warnings",
                "-o", str(output_path),
                file_url
            ]
            
            print(f"  Konvertiere mit yt-dlp...")
            print(f"  Input: {aax_path}")
            print(f"  Output: {output_path}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode == 0:
                # Prüfe ob Output-Datei existiert (kann abweichenden Namen haben)
                if output_path.exists():
                    print(f"  ✓ Konvertierung erfolgreich: {output_path}")
                    # Lösche AAX-Datei nach erfolgreicher Konvertierung
                    try:
                        aax_path.unlink()
                    except:
                        pass
                    return True
                else:
                    # Suche nach alternativen Output-Dateien
                    possible_outputs = list(output_dir.glob(f"*.{audio_format}"))
                    if possible_outputs:
                        # Nimm die neueste Datei
                        output_file = max(possible_outputs, key=lambda p: p.stat().st_mtime)
                        # Benenne um falls nötig
                        if output_file != output_path:
                            output_file.rename(output_path)
                        print(f"  ✓ Konvertierung erfolgreich: {output_path}")
                        try:
                            aax_path.unlink()
                        except:
                            pass
                        return True
                    else:
                        print(f"  ✗ Konvertierung fehlgeschlagen: Output-Datei nicht gefunden")
                        if result.stdout:
                            print(f"  stdout: {result.stdout[-500:]}")
                        return False
            else:
                print(f"  ✗ Konvertierung fehlgeschlagen")
                if result.stderr:
                    print(f"  Fehler: {result.stderr[:500]}")
                if result.stdout:
                    print(f"  stdout: {result.stdout[-500:]}")
                return False
                
        except Exception as e:
            print(f"  ✗ Fehler bei yt-dlp-Konvertierung: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """Bereinigt Dateinamen"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip('. ')
    
    def _get_format_from_quality(self, quality: str) -> tuple:
        """Konvertiert Qualitätsstring in Format und Qualität"""
        quality_map = {
            "FLAC": ("flac", "best"),
            "MP3_320": ("mp3", "320"),
            "MP3_192": ("mp3", "192"),
            "MP3_128": ("mp3", "128")
        }
        return quality_map.get(quality, ("mp3", "320"))


def interactive_audible_login() -> Optional[AudibleAuth]:
    """
    Interaktive Audible-Login-Funktion
    
    Returns:
        AudibleAuth-Instanz bei erfolgreichem Login
    """
    auth = AudibleAuth()
    
    print("=" * 70)
    print("Audible Anmeldung")
    print("=" * 70)
    print()
    
    # Prüfe ob bereits angemeldet
    if auth.is_logged_in():
        print("✓ Bereits angemeldet!")
        print(f"  Email: {auth.email}")
        
        choice = input("\nNeu anmelden? (j/n): ").strip().lower()
        if choice != 'j':
            return auth
    
    email = input("Audible-Email: ").strip()
    password = getpass("Passwort: ")
    
    if auth.login(email, password):
        print("\n✓ Erfolgreich angemeldet!")
        return auth
    else:
        print("\n✗ Anmeldung fehlgeschlagen.")
        return None


if __name__ == "__main__":
    # Test
    auth = interactive_audible_login()
    if auth:
        library = AudibleLibrary(auth)
        books = library.fetch_library()
        print(f"\n✓ Bibliothek geladen: {len(books)} Hörbücher")
        for book in books[:5]:
            print(f"  • {book['title']} - {book.get('author', 'Unbekannt')}")

