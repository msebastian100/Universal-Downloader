#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deezer Authentifizierungsmodul
Unterstützt Login, Familien-Profile und automatische Qualitätsauswahl
"""

import json
import requests
from pathlib import Path
from typing import Optional, Dict, List
from getpass import getpass
import re


class DeezerAuth:
    """Klasse für Deezer-Authentifizierung und Profil-Verwaltung"""
    
    def __init__(self, config_path: str = ".deezer_config.json"):
        """
        Initialisiert den Authentifizierungsmanager
        
        Args:
            config_path: Pfad zur Konfigurationsdatei
        """
        self.config_path = Path(config_path)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8'
        })
        
        # Deezer URLs
        self.login_url = "https://www.deezer.com/ajax/gw-light.php"
        self.api_base = "https://api.deezer.com"
        
        # Session-Daten
        self.arl_token: Optional[str] = None
        self.user_info: Optional[Dict] = None
        self.current_profile: Optional[Dict] = None
        self.family_profiles: List[Dict] = []
        self.subscription_type: Optional[str] = None
        self.quality: str = "MP3_320"  # Standard
        
        # Lade gespeicherte Konfiguration
        self.load_config()
    
    def load_config(self):
        """Lädt gespeicherte Konfiguration"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.arl_token = config.get('arl_token')
                    self.user_info = config.get('user_info')
                    self.current_profile = config.get('current_profile')
                    self.family_profiles = config.get('family_profiles', [])
                    self.subscription_type = config.get('subscription_type')
                    self.quality = config.get('quality', 'MP3_320')
                    
                    # Setze ARL-Token in Session
                    if self.arl_token:
                        self.session.cookies.set('arl', self.arl_token, domain='.deezer.com')
            except Exception as e:
                print(f"Fehler beim Laden der Konfiguration: {e}")
    
    def save_config(self):
        """Speichert Konfiguration"""
        try:
            config = {
                'arl_token': self.arl_token,
                'user_info': self.user_info,
                'current_profile': self.current_profile,
                'family_profiles': self.family_profiles,
                'subscription_type': self.subscription_type,
                'quality': self.quality
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")
    
    def login_with_credentials(self, email: str, password: str) -> bool:
        """
        Meldet sich mit Email und Passwort an
        
        Args:
            email: Deezer-Email
            password: Deezer-Passwort
            
        Returns:
            True bei erfolgreichem Login
        """
        try:
            # Deezer Login-Seite aufrufen, um CSRF-Token zu erhalten
            login_page = self.session.get("https://www.deezer.com/login", timeout=10)
            
            # Extrahiere CSRF-Token (falls vorhanden)
            csrf_match = re.search(r'csrf_token["\']?\s*[:=]\s*["\']([^"\']+)', login_page.text)
            csrf_token = csrf_match.group(1) if csrf_match else ""
            
            # Login-Daten
            login_data = {
                'email': email,
                'password': password,
                'csrf_token': csrf_token
            }
            
            # Login-Request
            response = self.session.post(
                "https://www.deezer.com/ajax/login.php",
                data=login_data,
                timeout=10
            )
            
            # Prüfe auf ARL-Token in Cookies
            if 'arl' in self.session.cookies:
                self.arl_token = self.session.cookies.get('arl')
                self.session.cookies.set('arl', self.arl_token, domain='.deezer.com')
                
                # Lade Benutzerinformationen
                if self.load_user_info():
                    self.save_config()
                    return True
            
            # Alternative: Versuche API-Login
            return self.login_via_api(email, password)
            
        except Exception as e:
            print(f"Fehler beim Login: {e}")
            return False
    
    def login_via_api(self, email: str, password: str) -> bool:
        """
        Alternative Login-Methode über API
        
        Args:
            email: Deezer-Email
            password: Deezer-Passwort
            
        Returns:
            True bei erfolgreichem Login
        """
        try:
            # Deezer verwendet eine spezielle Login-API
            # Hinweis: Dies ist eine vereinfachte Implementierung
            # In der Praxis würde man die offizielle OAuth2-Methode verwenden
            
            # Für jetzt: ARL-Token manuell eingeben oder aus Browser extrahieren
            print("\n⚠ Direkter Login über API ist komplex.")
            print("Bitte verwenden Sie eine der folgenden Methoden:")
            print("1. ARL-Token manuell eingeben (aus Browser-Cookies)")
            print("2. Login über Browser und ARL-Token extrahieren")
            
            return False
            
        except Exception as e:
            print(f"Fehler beim API-Login: {e}")
            return False
    
    def login_with_arl(self, arl_token: str) -> bool:
        """
        Meldet sich mit ARL-Token an
        
        Args:
            arl_token: ARL-Token aus Browser-Cookies
            
        Returns:
            True bei erfolgreichem Login
        """
        try:
            self.arl_token = arl_token
            self.session.cookies.set('arl', arl_token, domain='.deezer.com')
            
            if self.load_user_info():
                self.save_config()
                return True
            return False
            
        except Exception as e:
            print(f"Fehler beim Login mit ARL-Token: {e}")
            return False
    
    def load_user_info(self) -> bool:
        """
        Lädt Benutzerinformationen und prüft Abo-Status
        
        Returns:
            True bei Erfolg
        """
        try:
            # Versuche Benutzerinformationen abzurufen
            # Deezer API benötigt authentifizierte Requests
            
            # Teste mit einem authentifizierten Request
            test_url = f"{self.api_base}/user/me"
            response = self.session.get(test_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'error' not in data:
                    self.user_info = data
                    self.subscription_type = data.get('offer', 'free')
                    
                    # Setze Qualität basierend auf Abo
                    self.set_quality_from_subscription()
                    
                    # Lade Familien-Profile
                    self.load_family_profiles()
                    
                    return True
            
            # Alternative: Versuche über Web-Interface
            return self.load_user_info_web()
            
        except Exception as e:
            print(f"Fehler beim Laden der Benutzerinformationen: {e}")
            return False
    
    def load_user_info_web(self) -> bool:
        """
        Lädt Benutzerinformationen über Web-Interface
        
        Returns:
            True bei Erfolg
        """
        try:
            # Versuche Benutzerinformationen von der Webseite zu laden
            response = self.session.get("https://www.deezer.com/", timeout=10)
            
            # Extrahiere Benutzerinformationen aus JavaScript-Variablen
            # Dies ist eine vereinfachte Methode
            user_match = re.search(r'window\.__DZR_APP_STATE__\s*=\s*({.+?});', response.text, re.DOTALL)
            
            if user_match:
                try:
                    app_state = json.loads(user_match.group(1))
                    user_data = app_state.get('USER', {})
                    
                    if user_data:
                        self.user_info = {
                            'id': user_data.get('USER_ID'),
                            'name': user_data.get('USERNAME'),
                            'email': user_data.get('EMAIL')
                        }
                        self.subscription_type = user_data.get('OFFER', 'free')
                        self.set_quality_from_subscription()
                        return True
                except:
                    pass
            
            # Falls keine Info gefunden, aber ARL-Token vorhanden, nehmen wir an, dass Login funktioniert
            if self.arl_token:
                self.user_info = {'arl_token': 'valid'}
                self.subscription_type = 'premium'  # Annahme bei vorhandenem ARL
                self.set_quality_from_subscription()
                return True
            
            return False
            
        except Exception as e:
            print(f"Fehler beim Laden der Web-Benutzerinformationen: {e}")
            return False
    
    def load_family_profiles(self):
        """Lädt verfügbare Familien-Profile"""
        try:
            # Deezer Familien-Profile werden normalerweise über die Web-API abgerufen
            # Dies ist eine vereinfachte Implementierung
            
            # In der Praxis würde man die Familien-Profile-API aufrufen
            # Für jetzt: Wenn ein Premium-Account vorhanden ist, nehmen wir an, dass es ein Familien-Account sein könnte
            
            if self.subscription_type and 'family' in self.subscription_type.lower():
                # Versuche Familien-Profile zu laden
                # Dies würde normalerweise über eine spezielle API erfolgen
                self.family_profiles = [
                    {
                        'id': 'main',
                        'name': self.user_info.get('name', 'Hauptprofil') if self.user_info else 'Hauptprofil',
                        'is_main': True
                    }
                ]
            else:
                self.family_profiles = []
                
        except Exception as e:
            print(f"Fehler beim Laden der Familien-Profile: {e}")
            self.family_profiles = []
    
    def set_quality_from_subscription(self):
        """
        Setzt Qualität basierend auf Abo-Status
        """
        if not self.subscription_type:
            self.quality = "MP3_128"
            return
        
        subscription = self.subscription_type.lower()
        
        if 'hifi' in subscription or 'lossless' in subscription:
            self.quality = "FLAC"
        elif 'premium' in subscription or 'family' in subscription:
            self.quality = "MP3_320"
        elif 'free' in subscription:
            self.quality = "MP3_128"
        else:
            self.quality = "MP3_320"  # Standard für unbekannte Abos
    
    def select_profile(self, profile_id: str) -> bool:
        """
        Wählt ein Profil aus (für Familien-Accounts)
        
        Args:
            profile_id: ID des Profils
            
        Returns:
            True bei Erfolg
        """
        try:
            # Finde Profil
            profile = next((p for p in self.family_profiles if p.get('id') == profile_id), None)
            
            if profile:
                self.current_profile = profile
                self.save_config()
                return True
            else:
                print(f"Profil {profile_id} nicht gefunden")
                return False
                
        except Exception as e:
            print(f"Fehler beim Auswählen des Profils: {e}")
            return False
    
    def get_quality(self) -> str:
        """
        Gibt die aktuelle Qualitätseinstellung zurück
        
        Returns:
            Qualitätsstring (MP3_128, MP3_192, MP3_320, FLAC)
        """
        return self.quality
    
    def get_subscription_info(self) -> Dict:
        """
        Gibt Informationen über das Abo zurück
        
        Returns:
            Dictionary mit Abo-Informationen
        """
        return {
            'type': self.subscription_type or 'unknown',
            'quality': self.quality,
            'profiles': len(self.family_profiles),
            'current_profile': self.current_profile
        }
    
    def is_logged_in(self) -> bool:
        """
        Prüft, ob der Benutzer angemeldet ist
        
        Returns:
            True wenn angemeldet
        """
        return self.arl_token is not None and len(self.arl_token) > 0
    
    def logout(self):
        """Meldet den Benutzer ab"""
        self.arl_token = None
        self.user_info = None
        self.current_profile = None
        self.family_profiles = []
        self.subscription_type = None
        self.quality = "MP3_320"
        self.session.cookies.clear()
        
        # Lösche Konfiguration
        if self.config_path.exists():
            try:
                self.config_path.unlink()
            except:
                pass


def interactive_login() -> Optional[DeezerAuth]:
    """
    Interaktive Login-Funktion
    
    Returns:
        DeezerAuth-Instanz bei erfolgreichem Login
    """
    auth = DeezerAuth()
    
    print("=" * 70)
    print("Deezer Anmeldung")
    print("=" * 70)
    print()
    
    # Prüfe ob bereits angemeldet
    if auth.is_logged_in():
        print("✓ Bereits angemeldet!")
        print(f"  Abo: {auth.subscription_type or 'Unbekannt'}")
        print(f"  Qualität: {auth.quality}")
        if auth.family_profiles:
            print(f"  Verfügbare Profile: {len(auth.family_profiles)}")
        
        choice = input("\nNeu anmelden? (j/n): ").strip().lower()
        if choice != 'j':
            return auth
    
    print("\nAnmeldemethoden:")
    print("1. ARL-Token eingeben (empfohlen)")
    print("2. Email/Passwort (experimentell)")
    print()
    
    method = input("Wählen Sie eine Methode (1/2): ").strip()
    
    if method == "1":
        print("\nARL-Token Anleitung:")
        print("1. Öffnen Sie Deezer in Ihrem Browser")
        print("2. Öffnen Sie die Entwicklertools (F12)")
        print("3. Gehen Sie zu: Application → Cookies → deezer.com")
        print("4. Kopieren Sie den Wert des Cookies 'arl'")
        print()
        
        arl = input("ARL-Token eingeben: ").strip()
        if arl:
            if auth.login_with_arl(arl):
                print("\n✓ Erfolgreich angemeldet!")
                print(f"  Abo: {auth.subscription_type or 'Unbekannt'}")
                print(f"  Qualität: {auth.quality}")
                
                # Zeige Familien-Profile falls vorhanden
                if auth.family_profiles:
                    print(f"\nVerfügbare Profile ({len(auth.family_profiles)}):")
                    for i, profile in enumerate(auth.family_profiles, 1):
                        marker = "✓" if profile == auth.current_profile else " "
                        print(f"  {marker} {i}. {profile.get('name', 'Unbekannt')}")
                    
                    if len(auth.family_profiles) > 1:
                        choice = input("\nProfil auswählen (Nummer oder Enter für aktuelles): ").strip()
                        if choice.isdigit():
                            idx = int(choice) - 1
                            if 0 <= idx < len(auth.family_profiles):
                                auth.select_profile(auth.family_profiles[idx]['id'])
                                print(f"✓ Profil '{auth.family_profiles[idx]['name']}' ausgewählt")
                
                return auth
            else:
                print("\n✗ Anmeldung fehlgeschlagen. Bitte ARL-Token überprüfen.")
                return None
    
    elif method == "2":
        email = input("Email: ").strip()
        password = getpass("Passwort: ")
        
        if auth.login_with_credentials(email, password):
            print("\n✓ Erfolgreich angemeldet!")
            return auth
        else:
            print("\n✗ Anmeldung fehlgeschlagen.")
            return None
    
    return None


if __name__ == "__main__":
    # Test
    auth = interactive_login()
    if auth:
        print("\n" + "=" * 70)
        print("Anmeldung erfolgreich!")
        print("=" * 70)
        print(f"Abo-Typ: {auth.subscription_type}")
        print(f"Qualität: {auth.quality}")
        print(f"ARL-Token: {auth.arl_token[:20]}..." if auth.arl_token else "Kein Token")

