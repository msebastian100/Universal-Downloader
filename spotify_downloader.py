#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spotify Downloader für privaten Gebrauch
Lädt Musik von Spotify herunter (über YouTube/Deezer-Fallback)
"""

import re
import json
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import subprocess

# Import Deezer Downloader für Fallback
try:
    from deezer_downloader import DeezerDownloader
except ImportError:
    DeezerDownloader = None

# Import Video Downloader für YouTube-Fallback
try:
    from video_downloader import VideoDownloader
except ImportError:
    VideoDownloader = None


class SpotifyDownloader:
    """Hauptklasse für Spotify-Downloads (über Fallback zu YouTube/Deezer)"""
    
    def __init__(self, download_path: str = "Downloads"):
        """
        Initialisiert den Spotify-Downloader
        
        Args:
            download_path: Pfad zum Download-Verzeichnis
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        
        # Fallback-Downloader
        self.deezer_downloader = None
        self.video_downloader = None
        
        if DeezerDownloader:
            self.deezer_downloader = DeezerDownloader(download_path=str(self.download_path))
        
        if VideoDownloader:
            self.video_downloader = VideoDownloader(
                download_path=str(self.download_path),
                quality="best",
                output_format="mp3"
            )
        
        # Session für HTTP-Requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Spotify Web API (für öffentliche Daten, kein Login nötig)
        # Client-ID und Secret können über https://developer.spotify.com/dashboard erstellt werden
        # Für öffentliche Daten ist ein einfacher Client ausreichend
        self.spotify_client_id = None
        self.spotify_client_secret = None
        self.spotify_access_token = None
        self.spotify_token_expires_at = None
        
        # Lade gespeicherte Credentials
        self._load_spotify_credentials()
        
        # Download-Statistiken
        self.download_results: List[Dict] = []
        self.download_log: List[str] = []
    
    def log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Log hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.download_log.append(log_entry)
        print(log_entry)
    
    def _load_spotify_credentials(self):
        """Lädt gespeicherte Spotify API Credentials"""
        try:
            config_file = Path.home() / ".spotify_api_config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.spotify_client_id = config.get('client_id')
                    self.spotify_client_secret = config.get('client_secret')
        except Exception as e:
            self.log(f"Fehler beim Laden der Spotify-Credentials: {e}", "WARNING")
    
    def _save_spotify_credentials(self):
        """Speichert Spotify API Credentials"""
        try:
            config_file = Path.home() / ".spotify_api_config.json"
            config = {
                'client_id': self.spotify_client_id,
                'client_secret': self.spotify_client_secret
            }
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.log(f"Fehler beim Speichern der Spotify-Credentials: {e}", "WARNING")
    
    def set_spotify_credentials(self, client_id: str, client_secret: str):
        """
        Setzt Spotify API Credentials
        
        Args:
            client_id: Spotify Client ID
            client_secret: Spotify Client Secret
        """
        self.spotify_client_id = client_id
        self.spotify_client_secret = client_secret
        self.spotify_access_token = None  # Token zurücksetzen
        self.spotify_token_expires_at = None
        self._save_spotify_credentials()
        self.log("Spotify API Credentials gespeichert", "INFO")
    
    def get_spotify_access_token(self) -> Optional[str]:
        """
        Ruft ein Access-Token für die Spotify Web API ab
        Verwendet Client Credentials Flow (für öffentliche Daten)
        
        Returns:
            Access-Token oder None
        """
        # Prüfe ob Credentials vorhanden sind
        if not self.spotify_client_id or not self.spotify_client_secret:
            return None
        
        # Wenn bereits ein gültiges Token vorhanden ist, verwende es
        if self.spotify_access_token and self.spotify_token_expires_at:
            from datetime import datetime, timedelta
            if datetime.now() < self.spotify_token_expires_at:
                return self.spotify_access_token
        
        # Hole neues Token
        try:
            import base64
            
            # Client Credentials Flow
            token_url = "https://accounts.spotify.com/api/token"
            
            # Base64-encode Client ID und Secret
            credentials = f"{self.spotify_client_id}:{self.spotify_client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'grant_type': 'client_credentials'
            }
            
            response = self.session.post(token_url, headers=headers, data=data, timeout=10)
            
            if response.status_code == 200:
                token_data = response.json()
                self.spotify_access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)  # Standard: 1 Stunde
                
                from datetime import datetime, timedelta
                self.spotify_token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # 1 Minute Puffer
                
                self.log("Spotify Access-Token erfolgreich abgerufen", "INFO")
                return self.spotify_access_token
            else:
                self.log(f"Fehler beim Abrufen des Access-Tokens: {response.status_code}", "ERROR")
                if response.status_code == 401:
                    self.log("Ungültige Client-ID oder Client-Secret", "ERROR")
                return None
        
        except Exception as e:
            self.log(f"Fehler beim Abrufen des Access-Tokens: {e}", "ERROR")
            return None
    
    def get_artist_tracks_via_api(self, artist_id: str, limit: int = 50) -> List[Dict]:
        """
        Ruft Artist-Tracks über die Spotify Web API ab
        
        Args:
            artist_id: Spotify Artist-ID
            limit: Maximale Anzahl Tracks
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        
        # Hole Access-Token
        access_token = self.get_spotify_access_token()
        if not access_token:
            return []
        
        try:
            # API-Endpoint für Artist Top Tracks
            api_url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = self.session.get(
                api_url,
                headers=headers,
                params={'market': 'DE', 'limit': min(limit, 50)},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                for track in data.get('tracks', []):
                    tracks.append({
                        'id': track['id'],
                        'title': track['name'],
                        'artist': ', '.join([artist['name'] for artist in track['artists']]),
                        'album': track['album']['name'],
                        'duration': track['duration_ms'] // 1000,
                        'url': track['external_urls']['spotify']
                    })
                self.log(f"✓ {len(tracks)} Tracks über Spotify API gefunden", "SUCCESS")
                return tracks
            elif response.status_code == 401:
                # Token abgelaufen oder ungültig
                self.spotify_access_token = None
                self.spotify_token_expires_at = None
                # Versuche erneut mit neuem Token
                access_token = self.get_spotify_access_token()
                if access_token:
                    return self.get_artist_tracks_via_api(artist_id, limit)
            else:
                self.log(f"Spotify API Fehler: {response.status_code} - {response.text[:200]}", "ERROR")
        
        except Exception as e:
            self.log(f"Fehler bei Spotify API-Aufruf: {e}", "ERROR")
        
        return []
    
    def get_album_tracks_via_api(self, album_id: str) -> List[Dict]:
        """
        Ruft Album-Tracks über die Spotify Web API ab
        
        Args:
            album_id: Spotify Album-ID
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        
        # Hole Access-Token
        access_token = self.get_spotify_access_token()
        if not access_token:
            return []
        
        try:
            # API-Endpoint für Album Tracks
            api_url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Spotify API limitiert auf 50 Tracks pro Request
            offset = 0
            limit = 50
            
            while True:
                response = self.session.get(
                    api_url,
                    headers=headers,
                    params={'limit': limit, 'offset': offset},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    if not items:
                        break
                    
                    for item in items:
                        tracks.append({
                            'id': item['id'],
                            'title': item['name'],
                            'artist': ', '.join([artist['name'] for artist in item.get('artists', [])]),
                            'album': '',  # Wird später gefüllt
                            'duration': item.get('duration_ms', 0) // 1000,
                            'url': f"https://open.spotify.com/track/{item['id']}"
                        })
                    
                    # Prüfe ob weitere Tracks vorhanden sind
                    if not data.get('next'):
                        break
                    
                    offset += limit
                else:
                    break
            
            if tracks:
                self.log(f"✓ {len(tracks)} Tracks über Spotify API gefunden", "SUCCESS")
            
        except Exception as e:
            self.log(f"Fehler bei Spotify API-Aufruf: {e}", "ERROR")
        
        return tracks
    
    def get_playlist_tracks_via_api(self, playlist_id: str) -> List[Dict]:
        """
        Ruft Playlist-Tracks über die Spotify Web API ab
        
        Args:
            playlist_id: Spotify Playlist-ID
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        
        # Hole Access-Token
        access_token = self.get_spotify_access_token()
        if not access_token:
            return []
        
        try:
            # API-Endpoint für Playlist Tracks
            api_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            offset = 0
            limit = 50
            
            while True:
                response = self.session.get(
                    api_url,
                    headers=headers,
                    params={'limit': limit, 'offset': offset, 'market': 'DE'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('items', [])
                    
                    if not items:
                        break
                    
                    for item in items:
                        track = item.get('track')
                        if track:
                            tracks.append({
                                'id': track['id'],
                                'title': track['name'],
                                'artist': ', '.join([artist['name'] for artist in track.get('artists', [])]),
                                'album': track.get('album', {}).get('name', ''),
                                'duration': track.get('duration_ms', 0) // 1000,
                                'url': track['external_urls']['spotify']
                            })
                    
                    if not data.get('next'):
                        break
                    
                    offset += limit
                else:
                    break
            
            if tracks:
                self.log(f"✓ {len(tracks)} Tracks über Spotify API gefunden", "SUCCESS")
        
        except Exception as e:
            self.log(f"Fehler bei Spotify API-Aufruf: {e}", "ERROR")
        
        return tracks
    
    def extract_id_from_url(self, url: str) -> Optional[Dict]:
        """
        Extrahiert Typ und ID aus einem Spotify-Link
        
        Args:
            url: Spotify-URL
            
        Returns:
            Dictionary mit 'type' und 'id' oder None
        """
        # Normalisiere URL (entferne locale Präfixe wie /intl-de/)
        url = re.sub(r'/intl-[a-z]{2}/', '/', url)
        
        patterns = {
            'track': r'spotify\.com/(?:[a-z]{2}/)?track/([a-zA-Z0-9]+)',
            'album': r'spotify\.com/(?:[a-z]{2}/)?album/([a-zA-Z0-9]+)',
            'playlist': r'spotify\.com/(?:[a-z]{2}/)?playlist/([a-zA-Z0-9]+)',
            'artist': r'spotify\.com/(?:[a-z]{2}/)?artist/([a-zA-Z0-9]+)',
        }
        
        for item_type, pattern in patterns.items():
            match = re.search(pattern, url)
            if match:
                return {
                    'type': item_type,
                    'id': match.group(1)
                }
        
        return None
    
    def get_track_info(self, track_id: str) -> Optional[Dict]:
        """
        Ruft Track-Informationen ab (über yt-dlp oder Web-Scraping)
        
        Args:
            track_id: Spotify Track-ID
            
        Returns:
            Dictionary mit Track-Informationen oder None
        """
        try:
            # Versuche Track-Info über yt-dlp zu bekommen
            spotify_url = f"https://open.spotify.com/track/{track_id}"
            
            from yt_dlp_helper import get_ytdlp_command
            cmd = get_ytdlp_command() + [
                '--dump-json',
                '--no-playlist',
                spotify_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    info = json.loads(result.stdout)
                    return {
                        'id': track_id,
                        'title': info.get('title', 'Unknown'),
                        'artist': info.get('artist', 'Unknown'),
                        'album': info.get('album', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'url': spotify_url
                    }
                except json.JSONDecodeError:
                    pass
            
            # Fallback: Versuche Web-Scraping
            response = self.session.get(spotify_url, timeout=10)
            if response.status_code == 200:
                # Versuche Metadaten aus HTML zu extrahieren
                html = response.text
                
                # Suche nach JSON-LD oder anderen Metadaten
                title_match = re.search(r'<title>(.*?)</title>', html)
                title = title_match.group(1).split(' | ')[0] if title_match else 'Unknown'
                
                # Versuche Artist und Album aus Title zu extrahieren
                # Format: "Song Name - Artist Name | Spotify"
                parts = title.split(' - ')
                if len(parts) >= 2:
                    track_title = parts[0].strip()
                    artist = parts[1].replace(' | Spotify', '').strip()
                else:
                    track_title = title.replace(' | Spotify', '').strip()
                    artist = 'Unknown'
                
                return {
                    'id': track_id,
                    'title': track_title,
                    'artist': artist,
                    'album': 'Unknown',
                    'duration': 0,
                    'url': spotify_url
                }
            
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Track-Info: {e}", "ERROR")
        
        return None
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """
        Ruft alle Tracks einer Playlist ab
        
        Args:
            playlist_id: Spotify Playlist-ID
            
        Returns:
            Liste von Track-Dictionaries
        """
        # Versuche zuerst über API
        api_tracks = self.get_playlist_tracks_via_api(playlist_id)
        if api_tracks:
            return api_tracks
        
        # Fallback zu yt-dlp/Web-Scraping
        tracks = []
        spotify_url = f"https://open.spotify.com/playlist/{playlist_id}"
        
        try:
            # Versuche Playlist über yt-dlp zu bekommen
            from yt_dlp_helper import get_ytdlp_command
            cmd = get_ytdlp_command() + [
                '--dump-json',
                '--flat-playlist',
                '--yes-playlist',
                spotify_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            info = json.loads(line)
                            track_url = info.get('url') or info.get('webpage_url', '')
                            
                            # Extrahiere Track-ID aus URL
                            track_match = re.search(r'/track/([a-zA-Z0-9]+)', track_url)
                            if track_match:
                                track_id = track_match.group(1)
                                track_info = self.get_track_info(track_id)
                                if track_info:
                                    tracks.append(track_info)
                        except json.JSONDecodeError:
                            continue
            
            # Fallback: Versuche Web-Scraping
            if not tracks:
                response = self.session.get(spotify_url, timeout=10)
                if response.status_code == 200:
                    # Suche nach Track-Links im HTML
                    html = response.text
                    track_matches = re.findall(r'spotify\.com/track/([a-zA-Z0-9]+)', html)
                    
                    for track_id in set(track_matches):  # Entferne Duplikate
                        track_info = self.get_track_info(track_id)
                        if track_info:
                            tracks.append(track_info)
        
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Playlist: {e}", "ERROR")
        
        return tracks
    
    def get_artist_tracks(self, artist_id: str, limit: int = 50) -> List[Dict]:
        """
        Ruft alle Tracks eines Artists ab
        
        Args:
            artist_id: Spotify Artist-ID
            limit: Maximale Anzahl Tracks (Standard: 50)
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        spotify_url = f"https://open.spotify.com/artist/{artist_id}"
        
        try:
            # Methode 1: Versuche Spotify Web API (beste Methode)
            self.log("Versuche Artist-Tracks über Spotify Web API abzurufen...")
            api_tracks = self.get_artist_tracks_via_api(artist_id, limit)
            if api_tracks:
                self.log(f"✓ {len(api_tracks)} Tracks über API gefunden")
                return api_tracks[:limit]
            
            # Methode 2: Versuche Web-Scraping mit besserer Erkennung
            self.log("API nicht verfügbar - versuche Web-Scraping...")
            response = self.session.get(spotify_url, timeout=15, headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
            })
            
            if response.status_code == 200:
                html = response.text
                
                # Suche nach eingebetteten JSON-Daten (Spotify verwendet oft window.__INITIAL_STATE__)
                # Oder nach JSON-LD
                json_data_matches = re.findall(r'<script[^>]*>(.*?window\.__INITIAL_STATE__.*?)</script>', html, re.DOTALL)
                if not json_data_matches:
                    json_data_matches = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
                
                for json_data in json_data_matches:
                    try:
                        # Versuche JSON zu extrahieren
                        if 'window.__INITIAL_STATE__' in json_data:
                            # Extrahiere JSON aus JavaScript
                            json_match = re.search(r'window\.__INITIAL_STATE__\s*=\s*({.*?});', json_data, re.DOTALL)
                            if json_match:
                                data = json.loads(json_match.group(1))
                                # Durchsuche die Datenstruktur nach Tracks
                                self._extract_tracks_from_json(data, tracks, limit)
                        else:
                            data = json.loads(json_data)
                            self._extract_tracks_from_json(data, tracks, limit)
                    except (json.JSONDecodeError, AttributeError) as e:
                        continue
                
                # Methode 3: Suche nach Track-Links im HTML (auch in verschiedenen Formaten)
                if not tracks:
                    # Spotify Track-IDs sind normalerweise 22 Zeichen Base62
                    track_matches = re.findall(r'spotify\.com/track/([a-zA-Z0-9]{22})', html)
                    # Auch kürzere IDs finden (falls vorhanden)
                    track_matches.extend(re.findall(r'/track/([a-zA-Z0-9]{15,22})', html))
                    
                    self.log(f"Gefunden: {len(set(track_matches))} Track-Links im HTML")
                    
                    for track_id in set(track_matches)[:limit]:
                        track_info = self.get_track_info(track_id)
                        if track_info:
                            tracks.append(track_info)
                
                # Methode 4: Suche nach Album-Links und lade deren Tracks
                if len(tracks) < limit:
                    album_matches = re.findall(r'spotify\.com/album/([a-zA-Z0-9]{22})', html)
                    self.log(f"Gefunden: {len(set(album_matches))} Album-Links")
                    
                    for album_id in set(album_matches)[:5]:  # Maximal 5 Alben
                        if len(tracks) >= limit:
                            break
                        album_tracks = self.get_album_tracks(album_id)
                        for track in album_tracks:
                            if len(tracks) >= limit:
                                break
                            # Prüfe auf Duplikate
                            if not any(t['id'] == track['id'] for t in tracks):
                                tracks.append(track)
                
                # Entferne Duplikate basierend auf Track-ID
                seen_ids = set()
                unique_tracks = []
                for track in tracks:
                    if track['id'] not in seen_ids:
                        seen_ids.add(track['id'])
                        unique_tracks.append(track)
                tracks = unique_tracks
                
                if tracks:
                    self.log(f"✓ {len(tracks)} Tracks über Web-Scraping gefunden")
                else:
                    self.log("⚠ Keine Tracks gefunden - Spotify-Seite ist JavaScript-rendered", "WARNING")
                    self.log("💡 Lösung: Verwenden Sie eine Playlist-URL des Artists oder einzelne Track-URLs", "INFO")
                    self.log("💡 Alternative: Erstellen Sie eine Playlist mit den gewünschten Tracks und verwenden Sie die Playlist-URL", "INFO")
            else:
                self.log(f"HTTP-Fehler: {response.status_code}", "ERROR")
        
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Artist-Tracks: {e}", "ERROR")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
        
        return tracks[:limit]  # Begrenze auf gewünschte Anzahl
    
    def get_album_tracks(self, album_id: str) -> List[Dict]:
        """
        Ruft alle Tracks eines Albums ab
        
        Args:
            album_id: Spotify Album-ID
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        spotify_url = f"https://open.spotify.com/album/{album_id}"
        
        try:
            # Versuche Album über yt-dlp zu bekommen
            from yt_dlp_helper import get_ytdlp_command
            cmd = get_ytdlp_command() + [
                '--dump-json',
                '--flat-playlist',
                '--yes-playlist',
                spotify_url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            info = json.loads(line)
                            track_url = info.get('url') or info.get('webpage_url', '')
                            
                            # Extrahiere Track-ID aus URL
                            track_match = re.search(r'/track/([a-zA-Z0-9]+)', track_url)
                            if track_match:
                                track_id = track_match.group(1)
                                track_info = self.get_track_info(track_id)
                                if track_info:
                                    tracks.append(track_info)
                        except json.JSONDecodeError:
                            continue
            
            # Fallback: Versuche Web-Scraping
            if not tracks:
                response = self.session.get(spotify_url, timeout=10)
                if response.status_code == 200:
                    html = response.text
                    track_matches = re.findall(r'spotify\.com/track/([a-zA-Z0-9]+)', html)
                    
                    for track_id in set(track_matches):
                        track_info = self.get_track_info(track_id)
                        if track_info:
                            tracks.append(track_info)
        
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Album-Tracks: {e}", "ERROR")
        
        return tracks
    
    def search_track_on_youtube(self, track_info: Dict) -> Optional[str]:
        """
        Sucht einen Track auf YouTube
        
        Args:
            track_info: Dictionary mit Track-Informationen
            
        Returns:
            YouTube-URL oder None
        """
        try:
            search_query = f"{track_info['artist']} {track_info['title']}"
            
            from yt_dlp_helper import get_ytdlp_command
            cmd = get_ytdlp_command() + [
                '--dump-json',
                f'ytsearch1:{search_query}'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                try:
                    info = json.loads(result.stdout)
                    return info.get('webpage_url') or info.get('url')
                except json.JSONDecodeError:
                    pass
        
        except Exception as e:
            self.log(f"Fehler bei YouTube-Suche: {e}", "ERROR")
        
        return None
    
    def download_track(self, track_info: Dict, output_dir: Optional[Path] = None) -> Dict:
        """
        Lädt einen Track herunter (über YouTube/Deezer-Fallback)
        
        Args:
            track_info: Dictionary mit Track-Informationen
            output_dir: Optionales Ausgabe-Verzeichnis
            
        Returns:
            Dictionary mit Download-Ergebnis
        """
        if output_dir is None:
            output_dir = self.download_path
        
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        track_name = f"{track_info['artist']} - {track_info['title']}"
        self.log(f"Lade Track herunter: {track_name}")
        
        # Methode 1: Versuche YouTube
        youtube_url = self.search_track_on_youtube(track_info)
        if youtube_url and self.video_downloader:
            self.log(f"  → Versuche Download über YouTube...")
            try:
                success, file_path, error = self.video_downloader.download_video(
                    url=youtube_url,
                    output_dir=output_dir,
                    quality="best",
                    output_format="mp3"
                )
                
                if success and file_path:
                    # Benenne Datei um (falls nötig)
                    new_path = output_dir / f"{track_name}.mp3"
                    if file_path != new_path:
                        file_path.rename(new_path)
                    
                    self.log(f"  ✓ Erfolgreich von YouTube heruntergeladen: {new_path}", "SUCCESS")
                    return {
                        'success': True,
                        'source': 'YouTube',
                        'file_path': new_path,
                        'track_info': track_info
                    }
            except Exception as e:
                self.log(f"  ✗ YouTube-Download fehlgeschlagen: {e}", "ERROR")
        
        # Methode 2: Versuche Deezer (falls verfügbar)
        if self.deezer_downloader:
            self.log(f"  → Versuche Download über Deezer...")
            try:
                # Suche Track auf Deezer
                search_query = f"{track_info['artist']} {track_info['title']}"
                deezer_url = f"https://api.deezer.com/search?q={search_query}&limit=1"
                
                response = self.session.get(deezer_url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('data') and len(data['data']) > 0:
                        deezer_track = data['data'][0]
                        deezer_track_id = str(deezer_track['id'])
                        
                        result = self.deezer_downloader.download_track(
                            track_id=deezer_track_id,
                            output_dir=output_dir,
                            use_youtube_fallback=True
                        )
                        
                        if result.success:
                            self.log(f"  ✓ Erfolgreich von Deezer heruntergeladen: {result.file_path}", "SUCCESS")
                            return {
                                'success': True,
                                'source': result.source,
                                'file_path': result.file_path,
                                'track_info': track_info
                            }
            except Exception as e:
                self.log(f"  ✗ Deezer-Download fehlgeschlagen: {e}", "ERROR")
        
        # Alle Methoden fehlgeschlagen
        error_msg = f"Download fehlgeschlagen für: {track_name}"
        self.log(f"  ✗ {error_msg}", "ERROR")
        return {
            'success': False,
            'source': 'Fehlgeschlagen',
            'file_path': None,
            'track_info': track_info,
            'error': error_msg
        }
    
    def download_from_url(self, url: str, output_dir: Optional[Path] = None) -> int:
        """
        Lädt basierend auf einer Spotify-URL herunter
        
        Args:
            url: Spotify-URL (Track, Album, Playlist)
            output_dir: Optionales Ausgabe-Verzeichnis
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        parsed = self.extract_id_from_url(url)
        if not parsed:
            self.log("Ungültige Spotify-URL", "ERROR")
            return 0
        
        item_type = parsed['type']
        item_id = parsed['id']
        
        if output_dir is None:
            output_dir = self.download_path
        
        output_dir = Path(output_dir)
        
        if item_type == 'track':
            track_info = self.get_track_info(item_id)
            if track_info:
                result = self.download_track(track_info, output_dir)
                self.download_results.append(result)
                return 1 if result['success'] else 0
        
        elif item_type == 'playlist':
            self.log(f"Lade Playlist herunter: {item_id}")
            tracks = self.get_playlist_tracks(item_id)
            
            if not tracks:
                self.log("Keine Tracks in Playlist gefunden", "ERROR")
                return 0
            
            self.log(f"Gefunden: {len(tracks)} Track(s)")
            
            successful = 0
            for i, track_info in enumerate(tracks, 1):
                self.log(f"[{i}/{len(tracks)}] {track_info['artist']} - {track_info['title']}")
                result = self.download_track(track_info, output_dir)
                self.download_results.append(result)
                if result['success']:
                    successful += 1
            
            self.log(f"Playlist-Download abgeschlossen: {successful}/{len(tracks)} erfolgreich")
            return successful
        
        elif item_type == 'album':
            self.log(f"Lade Album herunter: {item_id}")
            tracks = self.get_album_tracks(item_id)
            
            if not tracks:
                self.log("Keine Tracks im Album gefunden", "ERROR")
                return 0
            
            self.log(f"Gefunden: {len(tracks)} Track(s)")
            
            successful = 0
            for i, track_info in enumerate(tracks, 1):
                self.log(f"[{i}/{len(tracks)}] {track_info['artist']} - {track_info['title']}")
                result = self.download_track(track_info, output_dir)
                self.download_results.append(result)
                if result['success']:
                    successful += 1
            
            self.log(f"Album-Download abgeschlossen: {successful}/{len(tracks)} erfolgreich")
            return successful
        
        elif item_type == 'artist':
            self.log(f"Lade Artist-Tracks herunter: {item_id}")
            self.log("Hinweis: Es werden die beliebtesten Tracks des Artists heruntergeladen (max. 50)")
            
            tracks = self.get_artist_tracks(item_id, limit=50)
            
            if not tracks:
                self.log("Keine Tracks für diesen Artist gefunden", "ERROR")
                return 0
            
            self.log(f"Gefunden: {len(tracks)} Track(s)")
            
            successful = 0
            for i, track_info in enumerate(tracks, 1):
                self.log(f"[{i}/{len(tracks)}] {track_info['artist']} - {track_info['title']}")
                result = self.download_track(track_info, output_dir)
                self.download_results.append(result)
                if result['success']:
                    successful += 1
            
            self.log(f"Artist-Download abgeschlossen: {successful}/{len(tracks)} erfolgreich")
            return successful
        
        else:
            self.log(f"Nicht unterstützter Spotify-Typ: {item_type}", "ERROR")
            return 0
