#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video-Downloader für öffentlich-rechtliche Sender (ARD, ZDF, ORF, SWR, etc.)
Verwendet yt-dlp für Downloads
"""

import subprocess
import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import sys
import logging
import os
import signal

# Unterstützte Sender
SUPPORTED_SENDERS = {
    'youtube': ['youtube.com', 'youtu.be', 'm.youtube.com'],
    'ard': ['ardmediathek.de', 'ard.de'],
    'ardplus': ['ardplus.de', 'ard-plus.de'],
    'zdf': ['zdf.de', 'zdfmediathek.de'],
    'orf': ['orf.at', 'tvthek.orf.at'],
    'swr': ['swr.de', 'swrmediathek.de'],
    'br': ['br.de', 'br-mediathek.de'],
    'wdr': ['wdr.de', 'wdrmediathek.de'],
    'mdr': ['mdr.de', 'mdrmediathek.de'],
    'ndr': ['ndr.de', 'ndrmediathek.de'],
    'hr': ['hr.de', 'hr-mediathek.de'],
    'rbb': ['rbb.de', 'rbbmediathek.de'],
    'sr': ['sr.de', 'srmediathek.de'],
    'rbtv': ['rocketbeans.tv'],
    'phoenix': ['phoenix.de'],
    'tagesschau': ['tagesschau.de'],
    'arte': ['arte.tv'],
}


class VideoDownloader:
    """Klasse für Video-Downloads von öffentlich-rechtlichen Sendern"""
    
    def __init__(self, download_path: str = "Downloads", quality: str = "best", output_format: str = "mp4", gui_instance: Optional[object] = None):
        """
        Initialisiert den Video-Downloader
        
        Args:
            download_path: Pfad zum Download-Verzeichnis
            quality: Video-Qualität ('best', 'worst', '720p', '1080p', etc.)
            output_format: Ausgabeformat ('mp4', 'mp3', 'webm', etc.)
            gui_instance: Optional GUI-Instanz für Zugriff auf Account-Daten
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.quality = quality
        self.output_format = output_format.lower()
        self.download_log: List[str] = []
        self.gui_instance = gui_instance
        
        # Log-Datei Setup
        self.log_file = None
        self._setup_logging()
        
        # Prüfe ob yt-dlp verfügbar ist
        self._check_ytdlp()
        
        # Prüfe ob ffmpeg für MP3-Konvertierung verfügbar ist
        if self.output_format == 'mp3':
            self._check_ffmpeg()
    
    def _setup_logging(self):
        """Richtet File-Logging ein"""
        try:
            # Erstelle Logs-Verzeichnis
            logs_dir = self.download_path.parent / "Logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Erstelle Log-Datei mit Timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = logs_dir / f"video_download_{timestamp}.log"
            self.log_file = open(log_filename, 'w', encoding='utf-8')
            self.log(f"Log-Datei erstellt: {log_filename}")
        except Exception as e:
            print(f"Warnung: Konnte Log-Datei nicht erstellen: {e}")
            self.log_file = None
    
    def __del__(self):
        """Schließt Log-Datei beim Beenden"""
        if self.log_file:
            try:
                self.log_file.close()
            except:
                pass
    
    def _check_ytdlp(self):
        """Prüft ob yt-dlp installiert ist"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.log(f"yt-dlp Version: {result.stdout.strip()}")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        self.log("WARNUNG: yt-dlp nicht gefunden! Bitte installieren Sie yt-dlp.", "ERROR")
        return False
    
    def _check_ffmpeg(self):
        """Prüft ob ffmpeg installiert ist (benötigt für MP3-Konvertierung)"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        self.log("WARNUNG: ffmpeg nicht gefunden! MP3-Konvertierung benötigt ffmpeg.", "ERROR")
        return False
    
    def log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Log hinzu"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.download_log.append(log_entry)
        
        # Schreibe in Log-Datei
        if self.log_file:
            try:
                self.log_file.write(log_entry + "\n")
                self.log_file.flush()  # Sofort schreiben
            except:
                pass
        
        # Nur wichtige Meldungen in Terminal ausgeben (reduziert)
        if level in ["ERROR", "WARNING"]:
            print(log_entry)
    
    def is_supported_url(self, url: str) -> bool:
        """
        Prüft ob die URL von einem unterstützten Sender stammt
        
        Args:
            url: Die zu prüfende URL
            
        Returns:
            True wenn unterstützt, sonst False
        """
        url_lower = url.lower()
        for sender, domains in SUPPORTED_SENDERS.items():
            for domain in domains:
                if domain in url_lower:
                    return True
        return False
    
    def _detect_service_from_url(self, url: str) -> Optional[str]:
        """
        Erkennt den Service aus der URL
        
        Args:
            url: Die Video-URL
            
        Returns:
            Service-Name (z.B. 'ARD Plus', 'Netflix', etc.) oder None
        """
        url_lower = url.lower()
        
        # ARD Plus
        if 'ardplus.de' in url_lower or 'ard-plus.de' in url_lower:
            return 'ARD Plus'
        
        # Netflix
        if 'netflix.com' in url_lower:
            return 'Netflix'
        
        # Amazon Prime Video
        if 'primevideo.com' in url_lower or 'amazon.de' in url_lower:
            return 'Amazon Prime Video'
        
        # Disney+
        if 'disneyplus.com' in url_lower or 'disney.de' in url_lower:
            return 'Disney+'
        
        # Maxdome
        if 'maxdome.de' in url_lower:
            return 'Maxdome'
        
        # Sky
        if 'sky.de' in url_lower or 'sky.com' in url_lower:
            return 'Sky'
        
        return None
    
    def _get_account_for_service(self, service: str) -> Optional[Dict]:
        """
        Holt den Account für einen Service aus den Einstellungen
        
        Args:
            service: Service-Name
            
        Returns:
            Account-Dictionary oder None
        """
        if not self.gui_instance or not hasattr(self.gui_instance, 'settings'):
            return None
        
        accounts = self.gui_instance.settings.get('video_accounts', [])
        for account in accounts:
            if account.get('service') == service:
                return account
        
        return None
    
    def _get_cookies_file(self, account: Dict) -> Optional[str]:
        """
        Erstellt eine temporäre Cookies-Datei für yt-dlp
        
        Args:
            account: Account-Dictionary mit Cookies
            
        Returns:
            Pfad zur temporären Cookies-Datei oder None
        """
        cookies_data = account.get('cookies', '').strip()
        if not cookies_data:
            return None
        
        try:
            import tempfile
            
            # Prüfe ob es Netscape-Format ist (beginnt mit # Netscape HTTP Cookie File)
            if cookies_data.startswith('# Netscape'):
                # Netscape-Format - bereinige ungültige Zeilen
                cookies_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                
                lines = cookies_data.split('\n')
                valid_lines = []
                
                for line in lines:
                    line = line.strip()
                    # Kommentarzeilen beibehalten
                    if line.startswith('#'):
                        valid_lines.append(line)
                        continue
                    # Leere Zeilen beibehalten
                    if not line:
                        valid_lines.append('')
                        continue
                    
                    # Prüfe ob die Zeile gültig ist (sollte 7 Felder haben, getrennt durch Tabs)
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        # Stelle sicher, dass alle Felder vorhanden sind
                        if parts[6]:  # Cookie-Wert sollte nicht leer sein
                            valid_lines.append(line)
                        else:
                            self.log(f"⚠ Überspringe Cookie-Zeile mit leerem Wert: {parts[5] if len(parts) > 5 else 'unbekannt'}", "WARNING")
                    elif len(parts) == 6:
                        # Manchmal fehlt der Cookie-Wert - füge leeren Wert hinzu
                        line_fixed = line + '\t'
                        valid_lines.append(line_fixed)
                        self.log(f"⚠ Cookie-Zeile korrigiert (fehlender Wert): {parts[5] if len(parts) > 5 else 'unbekannt'}", "WARNING")
                    else:
                        self.log(f"⚠ Überspringe ungültige Cookie-Zeile (nur {len(parts)} Felder): {line[:50]}...", "WARNING")
                
                cookies_file.write('\n'.join(valid_lines))
                cookies_file.close()
                self.log(f"✓ Cookies-Datei erstellt mit {len([l for l in valid_lines if l and not l.startswith('#')])} gültigen Cookies")
                return cookies_file.name
            else:
                # Versuche JSON-Format zu parsen
                try:
                    cookies_json = json.loads(cookies_data)
                    # Konvertiere JSON zu Netscape-Format
                    cookies_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                    cookies_file.write("# Netscape HTTP Cookie File\n")
                    cookies_file.write("# This is a generated file! Do not edit.\n\n")
                    
                    for cookie in cookies_json:
                        domain = cookie.get('domain', '')
                        domain_specified = 'TRUE' if domain.startswith('.') else 'FALSE'
                        path = cookie.get('path', '/')
                        secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                        expires = str(int(cookie.get('expirationDate', 0))) if cookie.get('expirationDate') else '0'
                        name = cookie.get('name', '')
                        value = cookie.get('value', '')
                        
                        cookies_file.write(f"{domain}\t{domain_specified}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
                    
                    cookies_file.close()
                    return cookies_file.name
                except json.JSONDecodeError:
                    # Kein JSON - versuche als Netscape-Format zu behandeln
                    cookies_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                    cookies_file.write(cookies_data)
                    cookies_file.close()
                    return cookies_file.name
        except Exception as e:
            self.log(f"Fehler beim Erstellen der Cookies-Datei: {e}", "ERROR")
            return None
    
    def get_video_info(self, url: str, check_series: bool = False) -> Optional[Dict]:
        """
        Ruft Informationen über das Video ab
        
        Args:
            url: Die Video-URL
            check_series: Wenn True, prüft auch ob es eine Serie/Staffel ist
            
        Returns:
            Dictionary mit Video-Informationen oder None bei Fehler
        """
        try:
            # Prüfe ob es ARD Plus ist und ob ein Account vorhanden ist
            service = self._detect_service_from_url(url)
            if service == 'ARD Plus':
                account = self._get_account_for_service(service)
                if not account or not account.get('cookies'):
                    self.log("⚠ WARNUNG: Für ARD Plus wird ein Account mit Cookies benötigt!", "WARNING")
                    self.log("⚠ Bitte fügen Sie einen ARD Plus Account in den Einstellungen hinzu.", "WARNING")
            
            self.log(f"Rufe Video-Informationen ab: {url}")
            
            # Füge Cookies hinzu falls vorhanden (auch für get_video_info)
            cookies_file = None
            if service:
                account = self._get_account_for_service(service)
                if account:
                    cookies_file = self._get_cookies_file(account)
            
            # Für Playlist-URLs: Nimm das erste Video oder verwende --flat-playlist
            if check_series:
                # Bei Serien/Playlists: Hole nur das erste Video für Info
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--yes-playlist',
                    '--playlist-end', '1',  # Nur erstes Video
                    '--no-warnings',
                ]
            else:
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--no-playlist',
                    '--no-warnings',
                ]
            
            # Füge Cookies hinzu falls vorhanden
            if cookies_file:
                cmd.extend(['--cookies', cookies_file])
                # Spezielle Optionen für ARD Plus
                if service == 'ARD Plus':
                    cmd.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                    cmd.extend(['--add-header', 'Referer:https://www.ardplus.de/'])
            
            # URL hinzufügen
            cmd.append(url)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Lösche temporäre Cookies-Datei falls vorhanden
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.unlink(cookies_file)
                except:
                    pass
            
            if result.returncode == 0:
                # Bei Playlists kann yt-dlp mehrere JSON-Objekte zurückgeben (eines pro Zeile)
                lines = result.stdout.strip().split('\n')
                if lines:
                    # Nimm das erste gültige JSON-Objekt
                    for line in lines:
                        if line.strip():
                            try:
                                info = json.loads(line)
                                self.log(f"✓ Video gefunden: {info.get('title', 'Unbekannt')}")
                                return info
                            except json.JSONDecodeError:
                                continue
                    self.log("✗ Keine gültigen JSON-Daten gefunden", "ERROR")
                    return None
                else:
                    self.log("✗ Keine Daten von yt-dlp erhalten", "ERROR")
                    return None
            else:
                error_output = result.stderr or result.stdout
                self.log(f"✗ Fehler beim Abrufen der Video-Info: {error_output}", "ERROR")
                
                # Spezielle Fehlermeldung für ARD Plus
                if service == 'ARD Plus' and 'Unsupported URL' in error_output:
                    self.log("⚠ ARD Plus wird von yt-dlp möglicherweise nicht unterstützt.", "WARNING")
                    self.log("⚠ ARD Plus verwendet DRM-geschützte Inhalte, die möglicherweise nicht heruntergeladen werden können.", "WARNING")
                    self.log("⚠ Bitte stellen Sie sicher, dass Sie die neueste Version von yt-dlp verwenden.", "WARNING")
                    self.log("⚠ Aktualisieren Sie yt-dlp mit: pip install --upgrade yt-dlp", "WARNING")
                
                return None
                
        except subprocess.TimeoutExpired:
            self.log("✗ Timeout beim Abrufen der Video-Informationen", "ERROR")
            return None
        except json.JSONDecodeError as e:
            self.log(f"✗ JSON-Fehler: {e}", "ERROR")
            return None
        except Exception as e:
            self.log(f"✗ Fehler: {e}", "ERROR")
            return None
    
    def is_series_or_season(self, url: str) -> bool:
        """
        Prüft ob die URL eine Serie oder Staffel ist
        
        Args:
            url: Die Video-URL
            
        Returns:
            True wenn es eine Serie/Staffel ist, sonst False
        """
        try:
            # Prüfe URL-Muster (z.B. /serie/, /staffel-, /season, /sammlung/, /sendung/)
            url_lower = url.lower()
            if '/serie/' in url_lower or '/staffel-' in url_lower or '/season' in url_lower:
                self.log(f"Serie/Staffel erkannt durch URL-Muster: {url}")
                return True
            
            # Prüfe auf ARD Mediathek Sammlungen/Sendungen (z.B. /maus, /sendung/, /sammlung/)
            if 'ardmediathek.de' in url_lower:
                # Prüfe ob es eine Sammlung/Sendung ist (kein einzelnes Video)
                # Einzelne Videos haben meist /video/ im Pfad
                parsed_path = url_lower.split('ardmediathek.de/')[-1].split('?')[0]
                if parsed_path and not parsed_path.startswith('video/') and not parsed_path.startswith('player/'):
                    # Prüfe mit yt-dlp ob es mehrere Videos enthält
                    try:
                        info = self.get_video_info(url, check_series=True)
                        if info:
                            # Prüfe auf Playlist-Merkmale
                            has_playlist = 'playlist' in info and info.get('playlist')
                            playlist_count = info.get('playlist_count')
                            if playlist_count is None:
                                playlist_count = 0
                            has_playlist_count = playlist_count > 1
                            
                            # Prüfe auch auf _type (collection, playlist, etc.)
                            entry_type = info.get('_type', '')
                            is_collection = entry_type in ['playlist', 'multi_video', 'collection']
                            
                            if has_playlist_count or is_collection or (has_playlist and playlist_count > 1):
                                self.log(f"Sammlung/Sendung erkannt: playlist_count={playlist_count}, _type={entry_type}")
                                return True
                    except Exception as e:
                        self.log(f"Fehler beim Prüfen der Sammlung: {e}", "WARNING")
                        # Bei Fehler: Wenn es keine /video/ URL ist, versuche es als Sammlung
                        if not parsed_path.startswith('video/'):
                            self.log(f"URL scheint eine Sammlung zu sein (kein /video/ Pfad): {url}")
                            return True
            
            # Prüfe mit yt-dlp
            info = self.get_video_info(url, check_series=True)
            if info:
                # Prüfe auf Serien-Merkmale
                has_series = 'series' in info and info.get('series')
                has_season = 'season_number' in info and info.get('season_number') is not None
                has_episode = 'episode_number' in info and info.get('episode_number') is not None
                has_playlist = 'playlist' in info and info.get('playlist')
                # Sicherstellen dass playlist_count nicht None ist
                playlist_count = info.get('playlist_count')
                if playlist_count is None:
                    playlist_count = 0
                has_playlist_count = playlist_count > 1
                
                # Prüfe auch auf _type
                entry_type = info.get('_type', '')
                is_collection = entry_type in ['playlist', 'multi_video', 'collection']
                
                result = has_series or (has_season and has_episode) or (has_playlist and has_playlist_count) or is_collection
                if result:
                    self.log(f"Serie/Staffel erkannt durch Metadaten: series={has_series}, season={has_season}, playlist={has_playlist_count}, _type={entry_type}")
                return result
            return False
        except Exception as e:
            self.log(f"Fehler bei Serien-Prüfung: {e}", "WARNING")
            return False
    
    def _extract_series_url(self, url: str) -> str:
        """
        Konvertiert eine Staffel-URL in eine Serien-URL, um alle Staffeln zu erhalten
        
        Args:
            url: Die URL (kann Staffel- oder Serien-URL sein)
            
        Returns:
            Die Serien-URL (ohne Staffel-Spezifikation)
        """
        # Für ARD-Mediathek: Entferne /staffel-X/ aus der URL
        if 'ardmediathek.de' in url and '/staffel-' in url:
            # Beispiel: https://www.ardmediathek.de/serie/die-pfefferkoerner/staffel-1/Y3JpZDovL2Rhc2Vyc3RlLm5kci5kZS80NzUz/1?isChildContent
            # Wird zu: https://www.ardmediathek.de/serie/die-pfefferkoerner/Y3JpZDovL2Rhc2Vyc3RlLm5kci5kZS80NzUz
            import re
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            
            # Parse die URL
            parsed = urlparse(url)
            
            # Entferne /staffel-X/ aus dem Pfad, aber behalte die ID
            # URL-Struktur: /serie/name/staffel-X/ID/nummer
            path_parts = [p for p in parsed.path.split('/') if p]  # Entferne leere Strings
            
            new_path_parts = []
            skip_staffel = False
            
            for i, part in enumerate(path_parts):
                # Überspringe /staffel-X/
                if part.startswith('staffel-') and part.replace('staffel-', '').isdigit():
                    skip_staffel = True
                    continue
                
                # Wenn wir gerade staffel-X übersprungen haben, überspringe auch die nächste Zahl (Staffel-Nummer)
                if skip_staffel:
                    skip_staffel = False
                    # Die nächste Komponente sollte die ID sein, nicht die Staffel-Nummer
                    # Die Staffel-Nummer kommt nach der ID
                    # Also: überspringe nichts hier, füge die ID hinzu
                
                # Entferne nur die abschließende Zahl (Staffel-Nummer), nicht die ID
                # Die ID ist ein Base64-ähnlicher String (enthält Buchstaben/Zahlen), keine einfache Zahl
                is_last = (i == len(path_parts) - 1)
                is_digit_only = part.isdigit() and len(part) <= 2
                
                # Wenn es die letzte Komponente ist UND eine einfache Zahl (nicht die ID), überspringe sie
                if is_last and is_digit_only:
                    # Prüfe ob die vorherige Komponente eine ID ist (enthält Buchstaben)
                    if i > 0 and any(c.isalpha() for c in path_parts[i-1]):
                        # Die vorherige Komponente ist die ID, diese Zahl ist die Staffel-Nummer -> überspringe
                        continue
                
                new_path_parts.append(part)
            
            # Baue neuen Pfad
            new_path = '/' + '/'.join(new_path_parts)
            
            # Entferne Query-Parameter, die auf eine spezifische Staffel hinweisen könnten
            query_params = parse_qs(parsed.query)
            # Entferne Parameter, die Staffel-spezifisch sein könnten
            if 'isChildContent' in query_params:
                del query_params['isChildContent']
            
            # Baue neue Query-String
            new_query = urlencode(query_params, doseq=True) if query_params else ''
            
            # Baue neue URL
            series_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                new_path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            
            self.log(f"Staffel-URL konvertiert zu Serien-URL: {series_url}")
            return series_url
        
        # Für andere Sender ähnlich behandeln
        if '/season' in url.lower():
            import re
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            new_path_parts = []
            skip_next = False
            for i, part in enumerate(path_parts):
                if skip_next:
                    skip_next = False
                    continue
                if part.lower().startswith('season-') and part.lower().replace('season-', '').isdigit():
                    skip_next = True
                    continue
                if i == len(path_parts) - 1 and part.isdigit():
                    continue
                new_path_parts.append(part)
            
            new_path_parts = [p for p in new_path_parts if p]
            new_path = '/' + '/'.join(new_path_parts)
            
            query_params = parse_qs(parsed.query)
            new_query = urlencode(query_params, doseq=True) if query_params else ''
            
            series_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                new_path,
                parsed.params,
                new_query,
                parsed.fragment
            ))
            
            if series_url != url:
                self.log(f"Staffel-URL konvertiert zu Serien-URL: {series_url}")
            return series_url
        
        # Falls keine Staffel-URL, gebe Original zurück
        return url
    
    def get_series_episodes(self, url: str) -> Optional[Dict]:
        """
        Ruft alle Folgen einer Serie/Staffel ab, gruppiert nach Staffeln
        
        Args:
            url: Die URL einer Serie oder Staffel
            
        Returns:
            Dictionary mit Staffeln als Keys und Listen von Episoden als Values
            Format: {
                'series_name': str,
                'seasons': {
                    1: [episode1, episode2, ...],
                    2: [episode1, episode2, ...],
                    ...
                }
            }
        """
        try:
            # Prüfe ob es eine YouTube-URL ist
            is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
            
            # Für YouTube-Playlists: Verwende URL direkt
            # Für andere Sender: Konvertiere Staffel-URL zu Serien-URL
            if is_youtube:
                series_url = url
                self.log(f"Rufe YouTube-Playlist-Informationen ab: {series_url}")
            else:
                # Spezielle Behandlung für ARD Mediathek Sammlungen/Sendungen
                if 'ardmediathek.de' in url.lower():
                    # Prüfe ob es eine einfache Sammlung/Sendung-URL ist (z.B. /maus)
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(url)
                    path_parts = [p for p in parsed.path.split('/') if p]
                    
                    # Wenn die URL nur einen Pfad-Teil hat (z.B. /maus), versuche sie als Sammlung zu behandeln
                    if len(path_parts) == 1 and path_parts[0] not in ['video', 'serie', 'sendung', 'sammlung', 'player']:
                        # Versuche die URL als Sammlung zu verwenden
                        # yt-dlp sollte ARDMediathekCollectionIE verwenden können
                        # Aber wir müssen möglicherweise die URL anpassen
                        collection_name = path_parts[0]
                        # Versuche verschiedene URL-Formate
                        # Format 1: /sammlung/name
                        # Format 2: /sendung/name
                        # Format 3: Original-URL (falls yt-dlp sie unterstützt)
                        series_url = url
                        self.log(f"ARD Mediathek Sammlung erkannt: {collection_name}, verwende URL: {series_url}")
                    else:
                        series_url = self._extract_series_url(url)
                        self.log(f"Rufe Serien-Informationen ab: {series_url}")
                else:
                    series_url = self._extract_series_url(url)
                    self.log(f"Rufe Serien-Informationen ab: {series_url}")
            
            # Für ARD Mediathek Sammlungen: Versuche URL-Normalisierung
            if 'ardmediathek.de' in series_url.lower():
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
                parsed = urlparse(series_url)
                path_parts = [p for p in parsed.path.split('/') if p]
                
                # Wenn die URL nur einen Pfad-Teil hat (z.B. /maus), versuche sie als Sammlung zu behandeln
                if len(path_parts) == 1 and path_parts[0] not in ['video', 'serie', 'sendung', 'sammlung', 'player']:
                    collection_name = path_parts[0]
                    # Versuche verschiedene URL-Formate, die yt-dlp versteht
                    # Format 1: /sammlung/name (wenn ID bekannt)
                    # Format 2: /sendung/name (wenn ID bekannt)
                    # Format 3: Versuche mit --extractor
                    # Für jetzt: Versuche die URL direkt, aber mit explizitem Extractor
                    self.log(f"Versuche ARD Mediathek Sammlung '{collection_name}' mit verschiedenen Formaten...")
                    
                    # Versuche zuerst mit explizitem Extractor
                    cmd = [
                        'yt-dlp',
                        '--dump-json',
                        '--flat-playlist',
                        '--yes-playlist',
                        '--playlist-end', '500',
                        '--extractor', 'ARDMediathekCollection',
                        series_url
                    ]
                else:
                    cmd = [
                        'yt-dlp',
                        '--dump-json',
                        '--flat-playlist',
                        '--yes-playlist',
                        '--playlist-end', '500',
                        series_url
                    ]
            else:
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--flat-playlist',
                    '--yes-playlist',
                    '--playlist-end', '500',
                    series_url
                ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # Wenn der erste Versuch fehlschlägt und es eine ARD Sammlung ist, versuche alternative Methoden
            if result.returncode != 0 and 'ardmediathek.de' in series_url.lower():
                error_output = result.stderr.lower()
                if 'unsupported url' in error_output or 'no video found' in error_output:
                    # Versuche ohne expliziten Extractor (lass yt-dlp automatisch erkennen)
                    self.log("Erster Versuch fehlgeschlagen, versuche ohne expliziten Extractor...")
                    cmd_alt = [
                        'yt-dlp',
                        '--dump-json',
                        '--flat-playlist',
                        '--yes-playlist',
                        '--playlist-end', '500',
                        series_url
                    ]
                    result = subprocess.run(
                        cmd_alt,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    # Wenn das auch fehlschlägt, versuche die Seite direkt zu parsen
                    if result.returncode != 0:
                        self.log("Versuche alternative Methode: Parse die Seite direkt...")
                        # Versuche die URL als normale Webseite zu behandeln und Video-Links zu extrahieren
                        try:
                            import requests
                            from bs4 import BeautifulSoup
                            
                            response = requests.get(series_url, timeout=30, headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            })
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                # Suche nach Video-Links auf der Seite
                                video_links = []
                                for link in soup.find_all('a', href=True):
                                    href = link.get('href')
                                    if href and ('/video/' in href or '/player/' in href):
                                        if not href.startswith('http'):
                                            href = f"https://www.ardmediathek.de{href}"
                                        if href not in video_links:
                                            video_links.append(href)
                                
                                if video_links:
                                    self.log(f"⚠️ Gefunden: {len(video_links)} Video-Links auf der Seite")
                                    self.log(f"⚠️ Die URL '{series_url}' ist eine Sammlungsseite, die yt-dlp nicht direkt unterstützt.")
                                    self.log(f"⚠️ Bitte verwenden Sie eine spezifische Video-URL oder eine Serien-URL (z.B. /serie/...).")
                                    self.log(f"⚠️ Beispiel-Video-URLs gefunden: {video_links[:3]}")
                                    return None
                        except Exception as e:
                            self.log(f"Fehler beim Parsen der Seite: {e}", "WARNING")
            
            if result.returncode == 0:
                episodes = []
                series_name = None
                
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            info = json.loads(line)
                            
                            # URL extrahieren - wichtig für spätere Downloads
                            # Bei --flat-playlist sind URLs oft nicht vollständig
                            episode_url = info.get('url') or info.get('webpage_url') or info.get('webpage_url_basename')
                            
                            # Falls keine vollständige URL, versuche sie zu konstruieren
                            if not episode_url or not episode_url.startswith('http'):
                                # Versuche URL aus ID zu konstruieren
                                episode_id = info.get('id')
                                if episode_id:
                                    # Für YouTube: Konstruiere URL aus Video-ID
                                    if is_youtube:
                                        episode_url = f"https://www.youtube.com/watch?v={episode_id}"
                                    # Für ARD: Konstruiere URL aus Original-URL
                                    elif 'ardmediathek.de' in series_url:
                                        # Versuche Episode-URL aus ID zu konstruieren
                                        # ARD Episode-URLs haben das Format: https://www.ardmediathek.de/video/.../ID
                                        # Oder verwende die vollständige URL aus webpage_url wenn verfügbar
                                        if info.get('webpage_url'):
                                            episode_url = info.get('webpage_url')
                                        else:
                                            # Fallback: Verwende Serien-URL, yt-dlp wird die richtige Episode finden
                                            episode_url = series_url
                                    else:
                                        episode_url = series_url  # Fallback: Serien-URL
                                else:
                                    episode_url = series_url  # Fallback: Serien-URL
                            
                            # Extrahiere Staffel- und Episodennummer aus Titel, falls nicht in Metadaten
                            title = info.get('title', info.get('id', 'Unbekannt'))
                            
                            if is_youtube:
                                # Für YouTube: Verwende Playlist-Index als Episode-Nummer
                                season_num = 1  # Immer Staffel 1 für YouTube-Playlists
                                episode_num = info.get('playlist_index') or info.get('playlist_autonumber') or info.get('episode_number')
                            else:
                                # Für andere Sender: Verwende normale Staffel/Episode-Nummern
                                season_num = info.get('season_number')
                                episode_num = info.get('episode_number')
                                
                                # Versuche Staffel/Episode aus Titel zu extrahieren (z.B. "Folge 7: Klassenfahrt (S03/E07)")
                                if not season_num or not episode_num:
                                    import re
                                    # Suche nach (SXX/EXX) im Titel - verschiedene Formate
                                    # Pattern 1: (S03/E07)
                                    season_episode_match = re.search(r'\(S(\d+)/E(\d+)\)', title)
                                    if not season_episode_match:
                                        # Pattern 2: S03/E07 (ohne Klammern)
                                        season_episode_match = re.search(r'S(\d+)/E(\d+)', title)
                                    if not season_episode_match:
                                        # Pattern 3: (S03 E07) mit Leerzeichen
                                        season_episode_match = re.search(r'\(S(\d+)\s+E(\d+)\)', title)
                                    
                                    if season_episode_match:
                                        if not season_num:
                                            season_num = int(season_episode_match.group(1))
                                        if not episode_num:
                                            episode_num = int(season_episode_match.group(2))
                            
                            # Setze Serienname/Playlist-Namen aus Metadaten
                            if is_youtube:
                                # Für YouTube: Verwende Playlist-Namen
                                series = info.get('playlist') or info.get('playlist_title') or info.get('series')
                                if not series_name:
                                    series_name = series
                            else:
                                # Für andere Sender: Verwende Serienname
                                series = info.get('series')
                                if not series and series_name:
                                    series = series_name
                            
                            episode_info = {
                                'title': title,
                                'url': episode_url,
                                'episode_number': episode_num,
                                'season_number': season_num if not is_youtube else 1,  # YouTube: Immer Staffel 1
                                'series': series,
                                'duration': info.get('duration', 0),
                                'duration_string': self._format_duration(info.get('duration') or 0),
                                'thumbnail': info.get('thumbnail'),
                                'id': info.get('id'),
                            }
                            
                            # Für YouTube: Füge Playlist-Index hinzu
                            if is_youtube:
                                episode_info['playlist_index'] = info.get('playlist_index') or info.get('playlist_autonumber')
                            
                            episodes.append(episode_info)
                            
                            # Setze Serienname/Playlist-Namen (falls noch nicht gesetzt)
                            if not series_name:
                                if is_youtube:
                                    # Für YouTube: Versuche Playlist-Namen zu extrahieren
                                    if episode_info.get('series'):
                                        series_name = episode_info.get('series')
                                    elif info.get('playlist'):
                                        series_name = info.get('playlist')
                                    elif info.get('playlist_title'):
                                        series_name = info.get('playlist_title')
                                else:
                                    # Für andere Sender: Versuche Serienname zu extrahieren
                                    if episode_info.get('series'):
                                        series_name = episode_info.get('series')
                                    else:
                                        # Versuche Serienname aus URL zu extrahieren (z.B. "almania" aus URL)
                                        if 'ardmediathek.de/serie/' in series_url:
                                            import re
                                            match = re.search(r'/serie/([^/]+)/', series_url)
                                            if match:
                                                # Konvertiere "almania" zu "Almania"
                                                series_name = match.group(1).replace('-', ' ').title()
                                                episode_info['series'] = series_name
                        except json.JSONDecodeError as e:
                            self.log(f"JSON-Fehler beim Parsen einer Episode: {e}", "WARNING")
                            continue
                        except Exception as e:
                            self.log(f"Fehler beim Verarbeiten einer Episode: {e}", "WARNING")
                            continue
                
                if episodes:
                    # Gruppiere nach Staffeln/Playlisten
                    seasons = {}
                    for episode in episodes:
                        # Für YouTube-Playlists: Alle Videos in "Playlist 1" (keine echten Staffeln)
                        if is_youtube:
                            season_num = 1  # Alle Videos in eine Playlist
                        else:
                            season_num = episode.get('season_number') or 1
                        if season_num not in seasons:
                            seasons[season_num] = []
                        seasons[season_num].append(episode)
                    
                    # Sortiere Episoden/Videos innerhalb jeder Staffel/Playlist
                    for season_num in seasons:
                        if is_youtube:
                            # Bei YouTube: Sortiere nach Index in Playlist (playlist_index)
                            seasons[season_num].sort(key=lambda x: x.get('playlist_index', x.get('episode_number', 0)) or 0)
                        else:
                            seasons[season_num].sort(key=lambda x: x.get('episode_number') or 0)
                    
                    # Sortiere Staffeln/Playlisten
                    sorted_seasons = dict(sorted(seasons.items()))
                    
                    # Für YouTube: Setze Playlist-Namen
                    if is_youtube:
                        playlist_name = series_name or info.get('playlist', 'Unbekannte Playlist') if episodes else 'Unbekannte Playlist'
                        if not series_name and episodes:
                            # Versuche Playlist-Namen aus erstem Video zu extrahieren
                            first_video = episodes[0]
                            playlist_name = first_video.get('playlist', first_video.get('series', 'Unbekannte Playlist'))
                        series_name = playlist_name
                    
                    result_dict = {
                        'series_name': series_name or ('Unbekannte Playlist' if is_youtube else 'Unbekannte Serie'),
                        'seasons': sorted_seasons,
                        'total_episodes': len(episodes)
                    }
                    
                    if is_youtube:
                        self.log(f"✓ {len(episodes)} Videos in {len(sorted_seasons)} Playlist(en) gefunden")
                    else:
                        self.log(f"✓ {len(episodes)} Folgen in {len(sorted_seasons)} Staffel(n) gefunden")
                    return result_dict
                else:
                    self.log("⚠ Keine Folgen gefunden", "WARNING")
                    return None
            else:
                self.log(f"✗ Fehler beim Abrufen der Serien-Info: {result.stderr}", "ERROR")
                return None
                
        except subprocess.TimeoutExpired:
            self.log("✗ Timeout beim Abrufen der Serien-Informationen", "ERROR")
            return None
        except Exception as e:
            self.log(f"✗ Fehler: {e}", "ERROR")
            return None
    
    def _format_duration(self, seconds: int) -> str:
        """Formatiert Dauer in MM:SS oder HH:MM:SS"""
        if not seconds:
            return "Unbekannt"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    def get_available_formats(self, url: str) -> List[Dict]:
        """
        Ruft verfügbare Formate/Qualitäten ab
        
        Args:
            url: Die Video-URL
            
        Returns:
            Liste mit verfügbaren Formaten
        """
        try:
            cmd = [
                'yt-dlp',
                '--list-formats',
                '--no-playlist',
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                formats = []
                lines = result.stdout.split('\n')
                for line in lines:
                    if re.match(r'^\d+', line.strip()):
                        # Format-Zeile parsen
                        parts = line.split()
                        if len(parts) >= 2:
                            format_id = parts[0]
                            format_info = ' '.join(parts[1:])
                            formats.append({
                                'id': format_id,
                                'info': format_info
                            })
                return formats
            else:
                return []
                
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Formate: {e}", "ERROR")
            return []
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Bereinigt einen Dateinamen von ungültigen Zeichen
        
        Args:
            filename: Der zu bereinigende Dateiname
            
        Returns:
            Bereinigter Dateiname
        """
        # Entferne ungültige Zeichen für Dateinamen
        invalid_chars = r'[<>:"/\\|?*]'
        filename = re.sub(invalid_chars, '_', filename)
        
        # Entferne führende/abschließende Punkte und Leerzeichen
        filename = filename.strip('. ')
        
        # Begrenze Länge
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def _get_output_path(self, video_info: Optional[Dict], output_dir: Path, 
                         is_series: bool = False, series_name: Optional[str] = None,
                         season_number: Optional[int] = None, url: str = '') -> Path:
        """
        Erstellt die richtige Ordnerstruktur basierend auf Video-Typ
        
        Args:
            video_info: Video-Informationen von yt-dlp
            output_dir: Basis-Download-Verzeichnis
            is_series: Ob es eine Serie ist
            series_name: Name der Serie (falls Serie)
            season_number: Staffelnummer (falls Serie)
            
        Returns:
            Pfad zum Ausgabe-Verzeichnis
        """
        # Basis: output_dir ist bereits "Downloads/Universal Downloader/Video"
        
        # Prüfe Sender aus URL oder video_info
        if not url and video_info:
            url = video_info.get('webpage_url', '') or video_info.get('original_url', '')
        
        sender = None
        for sender_key, domains in SUPPORTED_SENDERS.items():
            for domain in domains:
                if domain in url.lower():
                    sender = sender_key.upper()
                    break
            if sender:
                break
        
        # Prüfe ob es eine Serie ist (aus video_info)
        if video_info:
            has_series_info = video_info.get('series') or video_info.get('season_number') is not None
            if has_series_info and not series_name:
                series_name = video_info.get('series')
            if has_series_info and season_number is None:
                season_number = video_info.get('season_number')
            if has_series_info:
                is_series = True
        
        self.log(f"DEBUG: is_series={is_series}, series_name={series_name}, season_number={season_number}, sender={sender}")
        
        if is_series and series_name:
            # Serie: Video/ARD/Serienname/Staffel X/
            series_name_clean = self.sanitize_filename(series_name)
            if sender:
                series_path = output_dir / sender / series_name_clean
            else:
                series_path = output_dir / series_name_clean
            
            # Staffel-Ordner immer erstellen
            if season_number is not None:
                series_path = series_path / f"Staffel {season_number}"
            else:
                # Wenn keine Staffelnummer, aber es ist eine Serie, erstelle "Staffel 1" als Standard
                series_path = series_path / "Staffel 1"
            
            series_path.mkdir(parents=True, exist_ok=True)
            self.log(f"DEBUG: Serie-Pfad erstellt: {series_path}")
            return series_path
        elif video_info and (video_info.get('series') or video_info.get('season_number') is not None):
            # Einzelne Episode einer Serie (Fallback)
            series_name = video_info.get('series')
            season_num = video_info.get('season_number')
            
            if series_name:
                series_name_clean = self.sanitize_filename(series_name)
                if sender:
                    series_path = output_dir / sender / series_name_clean
                else:
                    series_path = output_dir / series_name_clean
                
                if season_num is not None:
                    series_path = series_path / f"Staffel {season_num}"
                else:
                    # Wenn keine Staffelnummer, aber es ist eine Serie, erstelle "Staffel 1" als Standard
                    series_path = series_path / "Staffel 1"
                
                series_path.mkdir(parents=True, exist_ok=True)
                self.log(f"DEBUG: Episode-Pfad erstellt: {series_path}")
                return series_path
        
        # Film oder einzelnes Video
        if sender:
            # Video/ARD/Filmname/
            film_title = None
            if video_info:
                # Versuche Filmtitel zu extrahieren
                film_title = video_info.get('title') or video_info.get('fulltitle')
                if film_title:
                    # Bereinige Filmtitel für Ordner
                    film_title = self.sanitize_filename(film_title)
            
            if film_title:
                film_path = output_dir / sender / film_title
            else:
                film_path = output_dir / sender
            film_path.mkdir(parents=True, exist_ok=True)
            self.log(f"DEBUG: Film-Pfad erstellt: {film_path}")
            return film_path
        else:
            # Video/ (Standard)
            self.log(f"DEBUG: Standard-Pfad verwendet: {output_dir}")
            return output_dir
    
    def download_video(self, url: str, output_dir: Optional[Path] = None, 
                      quality: Optional[str] = None, 
                      output_format: Optional[str] = None,
                      download_playlist: bool = False,
                      progress_callback: Optional[callable] = None,
                      video_info: Optional[Dict] = None,
                      is_series: bool = False,
                      series_name: Optional[str] = None,
                      season_number: Optional[int] = None,
                      download_subtitles: bool = False,
                      subtitle_language: str = "de",
                      download_description: bool = False,
                      download_thumbnail: bool = False,
                      resume_download: bool = True,
                      speed_limit: Optional[float] = None,
                      embed_metadata: bool = False,
                      gui_instance: Optional[object] = None) -> Tuple[bool, Optional[Path], str]:
        """
        Lädt ein Video herunter
        
        Args:
            url: Die Video-URL
            output_dir: Ausgabeverzeichnis (optional, verwendet self.download_path wenn None)
            quality: Video-Qualität (optional, verwendet self.quality wenn None)
            output_format: Ausgabeformat (optional, verwendet self.output_format wenn None)
            download_playlist: Wenn True, lade die gesamte Playlist herunter
            
        Returns:
            Tuple (success, file_path, error_message)
        """
        if output_dir is None:
            output_dir = self.download_path
        
        # Hole Video-Info falls nicht vorhanden
        if video_info is None:
            video_info = self.get_video_info(url, check_series=is_series)
        
        # Bestimme richtigen Ausgabe-Pfad basierend auf Video-Typ
        # Prüfe ob es eine Serie ist, falls nicht explizit gesetzt
        if not is_series and video_info:
            is_series = bool(video_info.get('series') or video_info.get('season_number'))
            if not series_name and is_series:
                series_name = video_info.get('series')
            if season_number is None and is_series:
                season_number = video_info.get('season_number')
        
        actual_output_dir = self._get_output_path(
            video_info, 
            output_dir,
            is_series=is_series,
            series_name=series_name,
            season_number=season_number,
            url=url
        )
        
        # Prüfe ob Ordner bereits existierte
        dir_existed_before = actual_output_dir.exists()
        
        self.log(f"Ordnerstruktur: {actual_output_dir}")
        
        quality = quality or self.quality
        output_format = (output_format or self.output_format).lower()
        
        try:
            # Wenn Format "none" (Keine) und nur zusätzliche Downloads gewünscht sind
            if output_format == 'none' and (download_description or download_thumbnail):
                self.log("Format 'Keine' ausgewählt - lade nur zusätzliche Dateien (Beschreibung/Thumbnail)...")
                
                # Hole Video-Info falls nicht vorhanden
                if video_info is None:
                    video_info = self.get_video_info(url, check_series=is_series)
                
                # Lade nur Beschreibung und/oder Thumbnail
                if download_description:
                    if video_info:
                        description_text = self._extract_description(video_info, url)
                        if description_text and description_text.strip():
                            description_path = actual_output_dir / "Info.txt"
                            try:
                                # Stelle sicher, dass das Verzeichnis existiert
                                actual_output_dir.mkdir(parents=True, exist_ok=True)
                                with open(description_path, 'w', encoding='utf-8') as f:
                                    f.write(description_text)
                                self.log(f"✓ Beschreibungstext gespeichert: {description_path}")
                            except Exception as e:
                                self.log(f"⚠ Konnte Beschreibungstext nicht speichern: {e}", "WARNING")
                                import traceback
                                self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
                        else:
                            self.log(f"⚠ Keine Beschreibungstext extrahiert (leer)", "WARNING")
                    else:
                        self.log(f"⚠ Keine Video-Info verfügbar für Beschreibung", "WARNING")
                
                # Für Thumbnail: Verwende yt-dlp nur für Thumbnail-Download
                if download_thumbnail:
                    # Baue yt-dlp Kommando nur für Thumbnail
                    from yt_dlp_helper import get_ytdlp_command
                    cmd = get_ytdlp_command()
                    if cmd is None:
                        self.log("yt-dlp Kommando konnte nicht erstellt werden", "ERROR")
                        return None
                    cmd.extend(['--write-thumbnail', '--convert-thumbnails', 'jpg', '--skip-download'])
                    cmd.append(url)
                    
                    self.log(f"Lade Thumbnail herunter...")
                    process = subprocess.run(
                        cmd,
                        cwd=str(actual_output_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    
                    if process.returncode == 0:
                        # Suche nach Thumbnail-Datei
                        thumbnail_files = list(actual_output_dir.glob('*.jpg')) + list(actual_output_dir.glob('*.webp'))
                        if thumbnail_files:
                            # Benenne um zu cover.jpg
                            thumbnail_file = thumbnail_files[0]
                            cover_path = actual_output_dir / "cover.jpg"
                            if thumbnail_file != cover_path:
                                try:
                                    thumbnail_file.rename(cover_path)
                                    self.log(f"✓ Thumbnail gespeichert: {cover_path.name}")
                                except Exception as e:
                                    self.log(f"⚠ Konnte Thumbnail nicht umbenennen: {e}", "WARNING")
                    else:
                        self.log(f"⚠ Konnte Thumbnail nicht herunterladen", "WARNING")
                
                self.log(f"✓ Zusätzliche Dateien erfolgreich heruntergeladen")
                return True, None, ""  # Keine Video-Datei, aber erfolgreich
            
            # Prüfe ob Video-Datei bereits existiert
            video_file_exists = False
            existing_video_file = None
            
            # Bestimme erwarteten Dateinamen basierend auf Video-Info
            if video_info:
                title = video_info.get('title', 'video')
                # Bereinige Titel für Dateinamen
                safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
                if output_format == 'mp3':
                    expected_file = actual_output_dir / f"{safe_title}.mp3"
                else:
                    expected_file = actual_output_dir / f"{safe_title}.{output_format}"
                
                # Prüfe ob Datei existiert (auch mit verschiedenen Varianten)
                if expected_file.exists():
                    video_file_exists = True
                    existing_video_file = expected_file
                else:
                    # Suche nach ähnlichen Dateien
                    if output_format == 'mp3':
                        files = list(actual_output_dir.glob('*.mp3'))
                    else:
                        files = list(actual_output_dir.glob(f'*.{output_format}'))
                    
                    # Prüfe ob eine Datei mit ähnlichem Namen existiert
                    for file in files:
                        if safe_title.lower() in file.stem.lower() or file.stem.lower() in safe_title.lower():
                            video_file_exists = True
                            existing_video_file = file
                            break
            
            # Wenn Datei existiert und nur zusätzliche Downloads gewünscht sind
            if video_file_exists and (download_description or download_thumbnail):
                self.log(f"Video-Datei bereits vorhanden: {existing_video_file.name}")
                self.log("Lade nur zusätzliche Dateien (Beschreibung/Thumbnail)...")
                
                # Hole Video-Info falls nicht vorhanden
                if video_info is None:
                    video_info = self.get_video_info(url, check_series=is_series)
                
                # Lade nur Beschreibung und/oder Thumbnail
                if download_description:
                    if video_info:
                        description_text = self._extract_description(video_info, url)
                        if description_text and description_text.strip():
                            description_path = actual_output_dir / "Info.txt"
                            try:
                                # Stelle sicher, dass das Verzeichnis existiert
                                actual_output_dir.mkdir(parents=True, exist_ok=True)
                                with open(description_path, 'w', encoding='utf-8') as f:
                                    f.write(description_text)
                                self.log(f"✓ Beschreibungstext gespeichert: {description_path}")
                            except Exception as e:
                                self.log(f"⚠ Konnte Beschreibungstext nicht speichern: {e}", "WARNING")
                                import traceback
                                self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
                        else:
                            self.log(f"⚠ Keine Beschreibungstext extrahiert (leer)", "WARNING")
                    else:
                        self.log(f"⚠ Keine Video-Info verfügbar für Beschreibung", "WARNING")
                
                # Für Thumbnail: Verwende yt-dlp nur für Thumbnail-Download
                if download_thumbnail:
                    # Baue yt-dlp Kommando nur für Thumbnail
                    from yt_dlp_helper import get_ytdlp_command
                    cmd = get_ytdlp_command()
                    if cmd is None:
                        self.log("yt-dlp Kommando konnte nicht erstellt werden", "ERROR")
                        return None
                    cmd.extend(['--write-thumbnail', '--convert-thumbnails', 'jpg', '--skip-download'])
                    cmd.append(url)
                    
                    self.log(f"Lade Thumbnail herunter...")
                    process = subprocess.run(
                        cmd,
                        cwd=str(actual_output_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    
                    if process.returncode == 0:
                        # Suche nach Thumbnail-Datei
                        thumbnail_files = list(actual_output_dir.glob('*.jpg')) + list(actual_output_dir.glob('*.webp'))
                        if thumbnail_files:
                            # Benenne um zu cover.jpg
                            thumbnail_file = thumbnail_files[0]
                            cover_path = actual_output_dir / "cover.jpg"
                            if thumbnail_file != cover_path:
                                try:
                                    thumbnail_file.rename(cover_path)
                                    self.log(f"✓ Thumbnail gespeichert: {cover_path.name}")
                                except Exception as e:
                                    self.log(f"⚠ Konnte Thumbnail nicht umbenennen: {e}", "WARNING")
                    else:
                        self.log(f"⚠ Konnte Thumbnail nicht herunterladen", "WARNING")
                
                self.log(f"✓ Zusätzliche Dateien erfolgreich heruntergeladen")
                return True, existing_video_file, ""
            
            # Normaler Download (Datei existiert nicht oder alle Downloads gewünscht)
            self.log(f"Starte Download: {url}")
            self.log(f"Qualität: {quality}")
            self.log(f"Format: {output_format}")
            self.log(f"Ausgabe-Verzeichnis: {actual_output_dir}")
            
            # Account-Integration: Prüfe ob ein Account für diesen Service vorhanden ist
            cookies_file = None
            service = self._detect_service_from_url(url)
            if service:
                account = self._get_account_for_service(service)
                if account:
                    self.log(f"Account gefunden für {service}: {account.get('name', 'Unbekannt')}")
                    cookies_file = self._get_cookies_file(account)
                    if cookies_file:
                        self.log(f"Cookies-Datei verwendet: {cookies_file}")
                    else:
                        self.log(f"⚠ Keine gültigen Cookies für {service} gefunden", "WARNING")
            
            # Baue yt-dlp Argumente (ohne Kommando selbst)
            from yt_dlp_helper import run_ytdlp
            yt_args = []
            
            # Füge Cookies hinzu falls vorhanden
            if cookies_file:
                yt_args.extend(['--cookies', cookies_file])
            
            # Spezielle Optionen für ARD Plus
            if service == 'ARD Plus':
                # User-Agent für ARD Plus
                cmd.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                # Referer setzen
                cmd.extend(['--add-header', 'Referer:https://www.ardplus.de/'])
                # Versuche generic extractor zu erzwingen
                cmd.extend(['--extractor-args', 'generic:no_check_certificate'])
                self.log("ARD Plus spezielle Optionen hinzugefügt")
            
            # Output-Template basierend auf Format - WICHTIG: verwende actual_output_dir!
            if output_format == 'mp3':
                # Für MP3: Konvertiere zu MP3
                output_template = str(actual_output_dir / '%(title)s.%(ext)s')
                yt_args.extend(['-o', output_template])
                yt_args.extend(['-x', '--audio-format', 'mp3', '--audio-quality', '0'])  # Beste Audio-Qualität
            else:
                # Für Video-Formate (MP4, etc.)
                output_template = str(actual_output_dir / f'%(title)s.{output_format}')
                yt_args.extend(['-o', output_template])
                yt_args.extend(['--recode-video', output_format])
            
            # Qualität/Format
            if output_format == 'mp3':
                # Für MP3: Beste Audio-Qualität
                yt_args.extend(['-f', 'bestaudio/best'])
            elif quality == "best":
                yt_args.extend(['-f', 'bestvideo+bestaudio/best'])
            elif quality == "worst":
                yt_args.extend(['-f', 'worstvideo+worstaudio/worst'])
            elif quality.endswith('p'):
                # Spezifische Auflösung (z.B. "720p", "1080p")
                resolution = quality[:-1]  # Entferne 'p'
                yt_args.extend(['-f', f'bestvideo[height<={resolution}]+bestaudio/best[height<={resolution}]'])
            else:
                # Fallback zu best
                yt_args.extend(['-f', 'bestvideo+bestaudio/best'])
            
            # Playlist-Option
            # WICHTIG: Bei Serien/Staffeln immer --yes-playlist verwenden, wenn download_playlist=True
            # Aber wenn wir einzelne Episoden aus einer Serie herunterladen, verwenden wir die spezifische Episode-URL
            if is_series and download_playlist:
                yt_args.append('--yes-playlist')  # Lade gesamte Playlist/Staffel
            elif is_series and not download_playlist:
                # Bei Serien, aber einzelne Episode: --no-playlist
                yt_args.append('--no-playlist')
            elif not download_playlist:
                yt_args.append('--no-playlist')  # Nur einzelnes Video, keine Playlist
            else:
                yt_args.append('--yes-playlist')  # Lade gesamte Playlist
            
            # Untertitel-Optionen
            if download_subtitles:
                if subtitle_language == "all":
                    yt_args.extend(['--write-subs', '--write-auto-subs', '--sub-langs', 'all'])
                else:
                    yt_args.extend(['--write-subs', '--write-auto-subs', '--sub-langs', subtitle_language])
                yt_args.extend(['--convert-subs', 'srt'])
            
            # Thumbnail-Download
            if download_thumbnail:
                yt_args.extend(['--write-thumbnail', '--convert-thumbnails', 'jpg'])
            
            # Download-Resume
            if resume_download:
                yt_args.append('--continue')
            else:
                yt_args.append('--no-continue')
            
            # Geschwindigkeits-Limit
            if speed_limit and speed_limit > 0:
                limit_bytes = int(speed_limit * 1024 * 1024)  # MB/s zu bytes/s
                yt_args.extend(['--limit-rate', str(limit_bytes)])
            
            # Metadaten-Embedding
            if embed_metadata:
                yt_args.extend(['--embed-metadata', '--embed-info-json'])
            
            # Weitere Optionen
            yt_args.extend([
                '--no-warnings',
                '--progress',
                '--newline',
            ])
            
            # URL hinzufügen
            yt_args.append(url)
            
            self.log(f"Führe yt-dlp aus mit {len(yt_args)} Argumenten...")
            
            # Verwende run_ytdlp() für den Download mit Popen für Prozessüberwachung
            try:
                # Für Prozessüberwachung und Abbruch-Funktionalität verwenden wir Popen
                process = run_ytdlp(
                    yt_args,
                    use_popen=True,  # Wichtig: Verwende Popen für Prozessüberwachung
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=str(actual_output_dir)
                )
                
                # Prüfe ob process ein Popen-Objekt ist (für Prozessüberwachung)
                if not hasattr(process, 'poll'):
                    # Fallback: Direkte API wurde verwendet (kein Prozessüberwachung möglich)
                    self.log("WARNING: Prozessüberwachung nicht verfügbar in .exe Build", "WARNING")
                    # Führe Download synchron aus
                    result = process
                    if hasattr(result, 'returncode') and result.returncode != 0:
                        error_msg = f"Download fehlgeschlagen: {result.stderr}"
                        self.log(error_msg, "ERROR")
                        return (False, None, error_msg)
                    # Erfolgreich
                    return (True, None, "")
            except Exception as e:
                error_msg = f"Fehler beim Starten von yt-dlp: {e}"
                self.log(error_msg, "ERROR")
                return (False, None, error_msg)
            
            # Verwende übergebene GUI-Instanz oder versuche sie aus dem Callback zu extrahieren
            if not gui_instance and progress_callback:
                # Versuche GUI-Instanz zu finden
                try:
                    # Methode 1: Über __self__ (wenn es eine gebundene Methode ist)
                    if hasattr(progress_callback, '__self__'):
                        gui_instance = progress_callback.__self__
                        self.log(f"[DEBUG] GUI-Instanz über __self__ gefunden: {type(gui_instance)}")
                    # Methode 2: Über __closure__ (wenn es eine Closure ist)
                    elif hasattr(progress_callback, '__closure__') and progress_callback.__closure__:
                        # Suche nach 'self' in den Closure-Variablen
                        for cell in progress_callback.__closure__:
                            try:
                                obj = cell.cell_contents
                                if hasattr(obj, 'video_download_cancelled'):
                                    gui_instance = obj
                                    self.log(f"[DEBUG] GUI-Instanz über Closure gefunden: {type(gui_instance)}")
                                    break
                            except:
                                pass
                except Exception as e:
                    self.log(f"[DEBUG] Fehler beim Finden der GUI-Instanz: {e}", "WARNING")
            
            # Speichere Prozess-Referenz
            if gui_instance and hasattr(gui_instance, 'video_download_process'):
                gui_instance.video_download_process = process
                self.log(f"[DEBUG] Prozess gespeichert: PID {process.pid}, GUI-Instanz: {type(gui_instance)}")
            else:
                if gui_instance:
                    self.log(f"[DEBUG] WARNUNG: GUI-Instanz gefunden, aber kein video_download_process Attribut!")
                else:
                    self.log(f"[DEBUG] WARNUNG: Keine GUI-Instanz gefunden! Abbruch-Funktion wird nicht funktionieren!")
            
            # Starte separaten Thread für Abbruch-Prüfung
            import threading
            cancelled = threading.Event()
            process_terminated = threading.Event()
            
            def terminate_process():
                """Beendet den Prozess sofort"""
                try:
                    self.log("[DEBUG] Versuche Prozess zu beenden...")
                    # Beende Prozessgruppe (alle Kindprozesse werden auch beendet)
                    if sys.platform != 'win32':
                        # Unix/macOS: Beende ganze Prozessgruppe
                        try:
                            pgid = os.getpgid(process.pid)
                            self.log(f"[DEBUG] Beende Prozessgruppe {pgid}")
                            os.killpg(pgid, signal.SIGTERM)
                            import time
                            time.sleep(0.3)
                            if process.poll() is None:
                                self.log("[DEBUG] Prozess läuft noch, sende SIGKILL...")
                                os.killpg(pgid, signal.SIGKILL)
                        except (ProcessLookupError, OSError) as e:
                            # Prozess bereits beendet oder Prozessgruppe nicht gefunden
                            self.log(f"[DEBUG] Prozessgruppe nicht gefunden, versuche direkt: {e}")
                            try:
                                process.terminate()
                                import time
                                time.sleep(0.3)
                                if process.poll() is None:
                                    process.kill()
                            except:
                                pass
                    else:
                        # Windows: Beende Prozessgruppe
                        process.terminate()
                        import time
                        time.sleep(0.3)
                        if process.poll() is None:
                            process.kill()
                    process_terminated.set()
                    self.log("[DEBUG] Prozess beendet")
                except Exception as e:
                    self.log(f"[DEBUG] Fehler beim Beenden des Prozesses: {e}", "WARNING")
                    process_terminated.set()
            
            def check_cancel():
                """Prüft regelmäßig auf Abbruch"""
                check_count = 0
                while process.poll() is None:  # Solange Prozess läuft
                    check_count += 1
                    if check_count % 10 == 0:  # Alle 2 Sekunden (10 * 0.2)
                        self.log(f"[DEBUG] Abbruch-Prüfung #{check_count}, Prozess läuft noch (PID: {process.pid})")
                        # Debug: Prüfe GUI-Instanz Status
                        if gui_instance:
                            has_flag = hasattr(gui_instance, 'video_download_cancelled')
                            flag_value = getattr(gui_instance, 'video_download_cancelled', None) if has_flag else None
                            self.log(f"[DEBUG] GUI-Instanz gefunden: {gui_instance}, has_flag={has_flag}, flag_value={flag_value}")
                        else:
                            self.log(f"[DEBUG] WARNUNG: Keine GUI-Instanz gefunden!")
                    
                    # Prüfe auf Abbruch - verwende getattr für Thread-Sicherheit
                    try:
                        if gui_instance:
                            # Direkter Zugriff auf das Attribut
                            cancelled_flag = getattr(gui_instance, 'video_download_cancelled', False)
                            if cancelled_flag:
                                cancelled.set()
                                self.log(f"[DEBUG] ABBRUCH ERKANNT! Prüfung #{check_count}, Prozess PID: {process.pid}")
                                self.log("Download wird abgebrochen...")
                                terminate_process()
                                break
                    except Exception as e:
                        self.log(f"[DEBUG] Fehler beim Prüfen des Abbruch-Flags: {e}", "WARNING")
                    
                    import time
                    time.sleep(0.2)  # Prüfe alle 0.2 Sekunden (sehr häufig)
                
                if process.poll() is not None:
                    self.log(f"[DEBUG] Abbruch-Thread beendet: Prozess ist nicht mehr aktiv (Returncode: {process.poll()})")
                else:
                    self.log(f"[DEBUG] Abbruch-Thread beendet: Prozess läuft noch!")
            
            cancel_thread = threading.Thread(target=check_cancel, daemon=True)
            cancel_thread.start()
            
            # Lese Output in Echtzeit
            output_lines = []
            try:
                # Verwende iter() für nicht-blockierendes Lesen mit Timeout
                import select
                import queue
                
                # Queue für Output-Zeilen
                output_queue = queue.Queue()
                read_done = threading.Event()
                
                def read_output():
                    """Liest Output in separatem Thread"""
                    try:
                        for line in process.stdout:
                            if cancelled.is_set() or process_terminated.is_set():
                                break
                            output_queue.put(line)
                    except:
                        pass
                    finally:
                        read_done.set()
                        output_queue.put(None)  # Signal für Ende
                
                read_thread = threading.Thread(target=read_output, daemon=True)
                read_thread.start()
                
                # Lese aus Queue mit Timeout
                line_count = 0
                while True:
                    line_count += 1
                    if line_count % 50 == 0:  # Alle 50 Zeilen
                        self.log(f"[DEBUG] Verarbeitet {line_count} Zeilen, Prozess Status: poll()={process.poll()}, cancelled={cancelled.is_set()}, terminated={process_terminated.is_set()}")
                    
                    # Prüfe zuerst auf Abbruch (wichtig!)
                    if cancelled.is_set() or process_terminated.is_set():
                        self.log(f"[DEBUG] Abbruch erkannt in Zeile {line_count}, beende sofort")
                        # Räume Dateien/Ordner auf
                        self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                        return (False, None, "Download abgebrochen")
                    
                    # Prüfe auch direkt auf GUI-Abbruch - verwende getattr für Thread-Sicherheit
                    try:
                        if gui_instance:
                            cancelled_flag = getattr(gui_instance, 'video_download_cancelled', False)
                            if cancelled_flag:
                                cancelled.set()
                                self.log(f"[DEBUG] GUI-Abbruch erkannt in Zeile {line_count}, beende sofort")
                                terminate_process()
                                self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                                return (False, None, "Download abgebrochen")
                    except Exception as e:
                        self.log(f"[DEBUG] Fehler beim Prüfen des GUI-Abbruch-Flags: {e}", "WARNING")
                    
                    try:
                        # Warte maximal 0.3 Sekunden auf neue Zeile
                        line = output_queue.get(timeout=0.3)
                        if line is None:  # Ende des Outputs
                            break
                        
                        line = line.strip()
                        if line:
                            output_lines.append(line)
                            # Parse Fortschritt
                            progress_percent = None
                            if '%' in line:
                                # Versuche Prozent zu extrahieren: z.B. "[download] 45.2% of 123.45MiB"
                                match = re.search(r'(\d+\.?\d*)%', line)
                                if match:
                                    try:
                                        progress_percent = float(match.group(1))
                                        if progress_callback:
                                            progress_callback(progress_percent, line)
                                    except ValueError:
                                        pass
                            
                            # Zeige Fortschritt
                            if '%' in line or 'ETA' in line or 'Downloading' in line or 'Merging' in line:
                                self.log(line)
                    except queue.Empty:
                        # Keine neue Zeile, prüfe weiter auf Abbruch
                        continue
                
                # Warte auf Read-Thread
                read_done.wait(timeout=1)
                        
            except Exception as e:
                # Falls Fehler beim Lesen (z.B. weil Prozess beendet wurde)
                if cancelled.is_set() or process_terminated.is_set():
                    self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                    return (False, None, "Download abgebrochen")
                self.log(f"[DEBUG] Fehler beim Lesen: {e}", "WARNING")
            
            # Warte auf Prozess-Ende (mit Timeout)
            self.log(f"[DEBUG] Warte auf Prozess-Ende, cancelled={cancelled.is_set()}, terminated={process_terminated.is_set()}")
            try:
                returncode = process.wait(timeout=1)
                self.log(f"[DEBUG] Prozess beendet mit Returncode: {returncode}")
            except subprocess.TimeoutExpired:
                # Prozess läuft noch, prüfe auf Abbruch
                self.log(f"[DEBUG] Timeout beim Warten, Prozess läuft noch, prüfe auf Abbruch")
                # Prüfe auf Abbruch mit getattr für Thread-Sicherheit
                cancelled_flag = False
                try:
                    if gui_instance:
                        cancelled_flag = getattr(gui_instance, 'video_download_cancelled', False)
                except:
                    pass
                
                if cancelled.is_set() or process_terminated.is_set() or cancelled_flag:
                    self.log(f"[DEBUG] Abbruch erkannt nach Timeout, räume auf")
                    self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                    return (False, None, "Download abgebrochen")
                self.log(f"[DEBUG] Warte weiter auf Prozess...")
                process.wait()  # Warte normal
            
            # Prüfe erneut auf Abbruch nach dem Warten - verwende getattr für Thread-Sicherheit
            cancelled_flag = False
            try:
                if gui_instance:
                    cancelled_flag = getattr(gui_instance, 'video_download_cancelled', False)
            except:
                pass
            
            if cancelled.is_set() or process_terminated.is_set() or cancelled_flag:
                self.log(f"[DEBUG] Abbruch erkannt nach process.wait(), räume auf")
                self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                return (False, None, "Download abgebrochen")
            
            if process.returncode == 0:
                # Suche nach heruntergeladener Datei
                # yt-dlp gibt normalerweise den Dateinamen aus
                downloaded_files = []
                for line in output_lines:
                    # Verschiedene Patterns für yt-dlp Output
                    patterns = [
                        r'\[download\]\s+Destination:\s+(.+?)$',
                        r'\[download\]\s+(.+?)\s+has already been downloaded',
                        r'\[ExtractAudio\]\s+Destination:\s+(.+?)$',
                        r'\[Merger\]\s+Merging formats into\s+"(.+?)"',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, line)
                        if match:
                            file_path = Path(match.group(1).strip().strip('"'))
                            if file_path.exists():
                                downloaded_files.append(file_path)
                
                # Falls nicht gefunden, suche im Output-Verzeichnis nach neuesten Dateien
                if not downloaded_files:
                    # Suche nach Dateien mit erwarteter Endung
                    if output_format == 'mp3':
                        files = list(actual_output_dir.glob('*.mp3'))
                    else:
                        files = list(actual_output_dir.glob(f'*.{output_format}'))
                        # Falls keine Dateien mit erwarteter Endung, suche alle
                        if not files:
                            files = list(actual_output_dir.glob('*'))
                    
                    if files:
                        # Sortiere nach Änderungszeit (neueste zuerst)
                        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                        downloaded_files = files[:1]  # Nimm die neueste
                
                if downloaded_files:
                    downloaded_file = downloaded_files[0]
                    
                    # Speichere Beschreibungstext, falls gewünscht
                    if download_description:
                        # Hole Video-Info falls nicht vorhanden
                        if video_info is None:
                            video_info = self.get_video_info(url, check_series=is_series)
                        
                        if video_info:
                            description_text = self._extract_description(video_info, url)
                            if description_text and description_text.strip():
                                description_path = actual_output_dir / "Info.txt"
                                try:
                                    # Stelle sicher, dass das Verzeichnis existiert
                                    actual_output_dir.mkdir(parents=True, exist_ok=True)
                                    with open(description_path, 'w', encoding='utf-8') as f:
                                        f.write(description_text)
                                    self.log(f"✓ Beschreibungstext gespeichert: {description_path}")
                                except Exception as e:
                                    self.log(f"⚠ Konnte Beschreibungstext nicht speichern: {e}", "WARNING")
                                    import traceback
                                    self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
                            else:
                                self.log(f"⚠ Keine Beschreibungstext extrahiert (leer)", "WARNING")
                        else:
                            self.log(f"⚠ Keine Video-Info verfügbar für Beschreibung", "WARNING")
                    
                    # Thumbnail wird automatisch von yt-dlp heruntergeladen, wenn --write-thumbnail gesetzt ist
                    # yt-dlp speichert es normalerweise als cover.jpg oder ähnlich
                    if download_thumbnail:
                        # Suche nach Thumbnail-Datei
                        thumbnail_files = list(actual_output_dir.glob('*.jpg')) + list(actual_output_dir.glob('*.webp'))
                        if thumbnail_files:
                            # Benenne um zu cover.jpg
                            thumbnail_file = thumbnail_files[0]
                            cover_path = actual_output_dir / "cover.jpg"
                            if thumbnail_file != cover_path:
                                try:
                                    thumbnail_file.rename(cover_path)
                                    self.log(f"✓ Thumbnail gespeichert: {cover_path.name}")
                                except Exception as e:
                                    self.log(f"⚠ Konnte Thumbnail nicht umbenennen: {e}", "WARNING")
                    
                    self.log(f"✓ Download erfolgreich: {downloaded_file.name}")
                    return True, downloaded_file, ""
                else:
                    self.log("⚠ Download scheint erfolgreich, aber Datei nicht gefunden", "WARNING")
                    return True, None, "Datei nicht gefunden"
            else:
                error_msg = '\n'.join(output_lines[-5:])  # Letzte 5 Zeilen
                self.log(f"✗ Download fehlgeschlagen: {error_msg}", "ERROR")
                # Prüfe auf Abbruch und räume auf
                if progress_callback and hasattr(progress_callback, '__self__'):
                    try:
                        gui_instance = progress_callback.__self__
                        if hasattr(gui_instance, 'video_download_cancelled') and gui_instance.video_download_cancelled:
                            self._cleanup_after_cancel(actual_output_dir, dir_existed_before, video_info, output_format)
                    except:
                        pass
                return False, None, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = "Timeout beim Download"
            self.log(f"✗ {error_msg}", "ERROR")
            return False, None, error_msg
        except Exception as e:
            error_msg = str(e)
            self.log(f"✗ Fehler: {error_msg}", "ERROR")
            return False, None, error_msg
        finally:
            # Lösche temporäre Cookies-Datei falls vorhanden
            if 'cookies_file' in locals() and cookies_file and os.path.exists(cookies_file):
                try:
                    os.unlink(cookies_file)
                    self.log(f"Temporäre Cookies-Datei gelöscht: {cookies_file}")
                except Exception as e:
                    self.log(f"⚠ Konnte Cookies-Datei nicht löschen: {e}", "WARNING")
    
    def _extract_description(self, video_info: Dict, url: str) -> str:
        """Extrahiert Beschreibungstext aus Video-Informationen"""
        try:
            description_parts = []
            
            # Titel
            title = video_info.get('title', 'Unbekannt')
            if not title or title == 'Unbekannt':
                # Versuche anderen Titel-Feld
                title = video_info.get('fulltitle') or video_info.get('display_id') or video_info.get('id', 'Unbekannt')
            description_parts.append(f"Titel: {title}\n")
            
            # URL
            description_parts.append(f"URL: {url}\n")
            
            # Beschreibung - prüfe mehrere mögliche Felder
            description = ''
            
            # Standard-Felder (in Reihenfolge der Wahrscheinlichkeit)
            possible_fields = [
                'description',
                'info',
                'summary', 
                'synopsis',
                'plot',
                'comment',
                'alt_title',
                'subtitle'
            ]
            
            for field in possible_fields:
                value = video_info.get(field, '')
                if value and isinstance(value, str) and len(value.strip()) > 10:
                    description = value
                    break
            
            # Für ARD-Mediathek: Prüfe auch verschachtelte Felder
            if not description:
                # ARD speichert manchmal die Beschreibung in 'availability' oder anderen Feldern
                availability = video_info.get('availability', '')
                if isinstance(availability, str) and len(availability.strip()) > 50:
                    description = availability
            
            # Prüfe auch in Metadaten
            if not description:
                metadata = video_info.get('metadata', {})
                if isinstance(metadata, dict):
                    for field in ['description', 'synopsis', 'info', 'plot']:
                        value = metadata.get(field, '')
                        if value and isinstance(value, str) and len(value.strip()) > 10:
                            description = value
                            break
            
            # Prüfe auch in 'subtitles' Metadaten (manchmal bei ARD)
            if not description:
                subtitles = video_info.get('subtitles', {})
                if isinstance(subtitles, dict):
                    # Prüfe erste verfügbare Sprache
                    for lang_code, subtitle_list in subtitles.items():
                        if subtitle_list and len(subtitle_list) > 0:
                            # Subtitles enthalten manchmal Metadaten
                            pass
            
            # Wenn keine Beschreibung gefunden, versuche sie von der Webseite zu extrahieren
            if not description:
                webpage_url = video_info.get('webpage_url') or video_info.get('original_url') or url
                # Prüfe ob es eine ARD-Mediathek URL ist
                if 'ardmediathek.de' in webpage_url or 'ard.de' in webpage_url:
                    self.log(f"[DEBUG] Versuche Beschreibung von Webseite zu extrahieren: {webpage_url}", "DEBUG")
                    description = self._extract_description_from_webpage(webpage_url)
                    if description:
                        self.log(f"[DEBUG] Beschreibung von Webseite extrahiert ({len(description)} Zeichen)", "DEBUG")
            
            # Debug: Logge verfügbare Felder wenn immer noch keine Beschreibung gefunden
            if not description:
                available_fields = [k for k in video_info.keys() if k not in ['formats', 'thumbnails', 'requested_formats', 'http_headers']]
                self.log(f"[DEBUG] Verfügbare Felder (ohne Beschreibung): {', '.join(available_fields[:20])}", "DEBUG")
                # Prüfe alle String-Felder die länger sind
                for key, value in video_info.items():
                    if isinstance(value, str) and len(value.strip()) > 50 and key not in ['url', 'webpage_url', 'thumbnail', 'format', 'format_id', 'original_url']:
                        # Prüfe ob es wie eine Beschreibung aussieht
                        if any(word in value.lower() for word in ['heute', 'mit', 'und', 'der', 'die', 'das', 'ein', 'eine']):
                            description = value
                            self.log(f"[DEBUG] Beschreibung in Feld '{key}' gefunden", "DEBUG")
                            break
            
            # Entferne HTML-Tags falls vorhanden
            if description:
                import re
                # Entferne einfache HTML-Tags
                description = re.sub(r'<[^>]+>', '', description)
                # Entferne mehrfache Leerzeichen und Zeilenumbrüche
                description = re.sub(r'\s+', ' ', description).strip()
                # Stelle Zeilenumbrüche wieder her bei Absätzen (nach Satzzeichen)
                description = re.sub(r'([.!?])\s+', r'\1\n\n', description)
                # Entferne zu viele Leerzeilen
                description = re.sub(r'\n{3,}', '\n\n', description)
                # Entferne führende/abschließende Leerzeilen
                description = description.strip()
            
            if description:
                description_parts.append(f"\nBeschreibung:\n{description}\n")
            
            # Uploader/Kanal
            uploader = video_info.get('uploader', '')
            if not uploader:
                uploader = video_info.get('channel') or video_info.get('uploader_id', '')
            if uploader:
                description_parts.append(f"\nKanal: {uploader}\n")
            
            # Dauer
            duration = video_info.get('duration')
            if duration:
                try:
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    description_parts.append(f"Dauer: {minutes}:{seconds:02d}\n")
                except:
                    pass
            
            # Upload-Datum
            upload_date = video_info.get('upload_date', '')
            if upload_date:
                # Format: YYYYMMDD
                if len(upload_date) == 8:
                    try:
                        year = upload_date[:4]
                        month = upload_date[4:6]
                        day = upload_date[6:8]
                        description_parts.append(f"Upload-Datum: {day}.{month}.{year}\n")
                    except:
                        pass
            
            # Views (falls vorhanden)
            view_count = video_info.get('view_count')
            if view_count:
                try:
                    description_parts.append(f"Aufrufe: {view_count:,}\n")
                except:
                    pass
            
            result = "\n".join(description_parts)
            # Stelle sicher, dass mindestens Titel und URL vorhanden sind
            if not result or len(result.strip()) < 10:
                result = f"Titel: {title}\nURL: {url}\n"
            
            return result
        except Exception as e:
            self.log(f"Fehler beim Extrahieren der Beschreibung: {e}", "WARNING")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}", "ERROR")
            # Fallback: Mindestens Titel und URL
            title = video_info.get('title', 'Unbekannt') if video_info else 'Unbekannt'
            if not title or title == 'Unbekannt':
                title = video_info.get('fulltitle', 'Unbekannt') if video_info else 'Unbekannt'
            return f"Titel: {title}\nURL: {url}\n"
    
    def _cleanup_after_cancel(self, output_dir: Path, dir_existed_before: bool, video_info: Optional[Dict], output_format: str):
        """Räumt Dateien/Ordner nach Abbruch auf"""
        try:
            if not output_dir.exists():
                return
            
            # Suche nach Dateien die während des Downloads erstellt wurden
            # yt-dlp erstellt oft temporäre Dateien mit Endungen wie .part, .ytdl, .tmp
            temp_patterns = ['*.part', '*.ytdl', '*.tmp', '*.temp', '*.f*.mp4', '*.f*.webm', '*.f*.mkv']
            video_extensions = ['.mp4', '.webm', '.mkv', '.avi', '.mp3', '.m4a', '.ogg']
            
            files_to_delete = []
            
            # Suche nach temporären Dateien
            for pattern in temp_patterns:
                files_to_delete.extend(list(output_dir.glob(pattern)))
            
            # Suche nach unvollständigen Video-Dateien (sehr klein oder kürzlich geändert)
            if output_format != 'none':
                for ext in video_extensions:
                    for file_path in output_dir.glob(f'*{ext}'):
                        try:
                            # Prüfe Dateigröße (unvollständige Downloads sind oft sehr klein)
                            file_size = file_path.stat().st_size
                            # Prüfe Änderungszeit (wenn sehr kürzlich geändert, könnte es unvollständig sein)
                            import time
                            mtime = file_path.stat().st_mtime
                            current_time = time.time()
                            
                            # Wenn Datei kleiner als 1MB oder in den letzten 10 Sekunden geändert wurde
                            if file_size < 1024 * 1024 or (current_time - mtime) < 10:
                                files_to_delete.append(file_path)
                        except:
                            pass
            
            # Lösche gefundene Dateien
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    self.log(f"Gelöscht: {file_path.name}")
                except Exception as e:
                    self.log(f"Konnte {file_path.name} nicht löschen: {e}", "WARNING")
            
            # Wenn Ordner vorher nicht existierte und jetzt leer ist, lösche ihn
            if not dir_existed_before:
                try:
                    # Prüfe ob Ordner leer ist (außer versteckten Dateien)
                    remaining_files = [f for f in output_dir.iterdir() if not f.name.startswith('.')]
                    if not remaining_files:
                        output_dir.rmdir()
                        self.log(f"Ordner gelöscht: {output_dir}")
                    else:
                        self.log(f"Ordner nicht gelöscht, da noch {len(remaining_files)} Dateien vorhanden")
                except Exception as e:
                    self.log(f"Konnte Ordner nicht löschen: {e}", "WARNING")
            else:
                # Ordner existierte bereits - lösche nur die spezifische Folge/Datei falls identifizierbar
                if video_info:
                    title = video_info.get('title', '')
                    if title:
                        # Suche nach Dateien die zum Titel passen
                        title_clean = re.sub(r'[^\w\s-]', '', title)[:50]  # Bereinige Titel
                        for file_path in output_dir.glob(f'*{title_clean}*'):
                            try:
                                # Prüfe ob es eine unvollständige Datei ist
                                file_size = file_path.stat().st_size
                                if file_size < 1024 * 1024:  # Kleiner als 1MB
                                    file_path.unlink()
                                    self.log(f"Unvollständige Datei gelöscht: {file_path.name}")
                            except:
                                pass
        except Exception as e:
            self.log(f"Fehler beim Aufräumen: {e}", "WARNING")
    
    def _extract_description_from_webpage(self, url: str) -> str:
        """Extrahiert Beschreibung direkt von der ARD-Mediathek Webseite"""
        try:
            import urllib.request
            
            # Lade die Webseite
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html_content = response.read().decode('utf-8')
            
            # Suche nach der Beschreibung in verschiedenen möglichen Stellen
            import re
            
            # ARD-Mediathek speichert die Beschreibung oft in einem <p> Tag mit bestimmten Klassen
            # Oder in einem <div> mit data-attribute oder bestimmten Klassen
            # Basierend auf der tatsächlichen ARD-Struktur
            patterns = [
                # Suche nach <p> Tags die nach dem Video-Titel kommen
                r'<h1[^>]*>.*?</h1>.*?<p[^>]*>(.*?)</p>',
                # Suche nach Beschreibung in bestimmten Divs
                r'<div[^>]*class="[^"]*description[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*class="[^"]*synopsis[^"]*"[^>]*>(.*?)</div>',
                r'<div[^>]*data-description="([^"]*)"',
                # Meta-Tags
                r'<meta[^>]*name="description"[^>]*content="([^"]*)"',
                # Suche nach Text der zwischen bestimmten Tags steht (nach Video-Info)
                r'<p[^>]*class="[^"]*text[^"]*"[^>]*>(.*?)</p>',
                r'<div[^>]*class="[^"]*text[^"]*"[^>]*>(.*?)</div>',
                # Suche nach langen Textblöcken die wie Beschreibungen aussehen
                r'<p[^>]*>(.{100,}?)</p>',  # Mindestens 100 Zeichen
            ]
            
            description = ''
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    # Entferne HTML-Tags
                    text = re.sub(r'<[^>]+>', '', match)
                    # Entferne HTML-Entities
                    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&apos;', "'")
                    # Entferne mehrfache Leerzeichen
                    text = re.sub(r'\s+', ' ', text).strip()
                    # Prüfe ob es wie eine Beschreibung aussieht (enthält deutsche Wörter)
                    if len(text) > 50 and any(word in text.lower() for word in ['heute', 'mit', 'und', 'der', 'die', 'das', 'ein', 'eine', 'sich', 'sind', 'wird']):
                        description = text
                        break
                if description:
                    break
            
            # Falls immer noch nichts gefunden, suche nach JSON-LD strukturierten Daten
            if not description:
                json_ld_pattern = r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>'
                json_ld_matches = re.findall(json_ld_pattern, html_content, re.DOTALL | re.IGNORECASE)
                for json_ld in json_ld_matches:
                    try:
                        data = json.loads(json_ld)
                        if isinstance(data, dict):
                            description = (data.get('description') or 
                                         data.get('about') or 
                                         data.get('text') or '')
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    desc = (item.get('description') or 
                                           item.get('about') or 
                                           item.get('text') or '')
                                    if desc and len(desc) > 50:
                                        description = desc
                                        break
                        if description:
                            break
                    except:
                        pass
            
            # Falls keine Beschreibung gefunden, versuche yt-dlp mit der Webseiten-URL
            if not description:
                try:
                    # Verwende yt-dlp um die Beschreibung von der Webseiten-URL zu extrahieren
                    cmd = [
                        'yt-dlp',
                        '--dump-json',
                        '--no-playlist',
                        '--no-warnings',
                        url
                    ]
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=15
                    )
                    if result.returncode == 0:
                        try:
                            info = json.loads(result.stdout.strip().split('\n')[0])
                            description = (info.get('description') or 
                                         info.get('info') or 
                                         info.get('summary') or 
                                         info.get('synopsis') or '')
                        except:
                            pass
                except:
                    pass
            
            return description.strip() if description else ''
        except Exception as e:
            self.log(f"[DEBUG] Fehler beim Extrahieren der Beschreibung von Webseite: {e}", "DEBUG")
            return ''
    
    def download_playlist(self, url: str, output_dir: Optional[Path] = None,
                          quality: Optional[str] = None) -> List[Tuple[bool, Optional[Path], str]]:
        """
        Lädt eine Playlist herunter
        
        Args:
            url: Die Playlist-URL
            output_dir: Ausgabeverzeichnis
            quality: Video-Qualität
            
        Returns:
            Liste von Tuples (success, file_path, error_message) für jedes Video
        """
        results = []
        
        try:
            self.log(f"Starte Playlist-Download: {url}")
            
            # Hole Playlist-Informationen
            cmd = [
                'yt-dlp',
                '--dump-json',
                '--flat-playlist',
                url
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Parse JSON-Lines
                video_urls = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            info = json.loads(line)
                            if 'url' in info:
                                video_urls.append(info['url'])
                            elif 'webpage_url' in info:
                                video_urls.append(info['webpage_url'])
                        except json.JSONDecodeError:
                            continue
                
                self.log(f"Gefunden: {len(video_urls)} Videos in Playlist")
                
                # Lade jedes Video herunter
                for i, video_url in enumerate(video_urls, 1):
                    self.log(f"\n[{i}/{len(video_urls)}] Lade Video herunter...")
                    success, file_path, error = self.download_video(
                        video_url, 
                        output_dir, 
                        quality
                    )
                    results.append((success, file_path, error))
                
            else:
                self.log(f"✗ Fehler beim Abrufen der Playlist: {result.stderr}", "ERROR")
                results.append((False, None, result.stderr))
                
        except Exception as e:
            self.log(f"✗ Fehler: {e}", "ERROR")
            results.append((False, None, str(e)))
        
        return results


def main():
    """Test-Funktion"""
    if len(sys.argv) < 2:
        print("Verwendung: python video_downloader.py <URL> [output_dir] [quality]")
        print("\nBeispiele:")
        print("  python video_downloader.py 'https://www.ardmediathek.de/video/...'")
        print("  python video_downloader.py 'https://www.zdf.de/...' Downloads/Video best")
        sys.exit(1)
    
    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "Downloads/Video"
    quality = sys.argv[3] if len(sys.argv) > 3 else "best"
    
    downloader = VideoDownloader(download_path=output_dir, quality=quality)
    
    if downloader.is_supported_url(url):
        print(f"✓ URL wird unterstützt")
    else:
        print(f"⚠ URL könnte nicht unterstützt werden, versuche trotzdem...")
    
    success, file_path, error = downloader.download_video(url)
    
    if success:
        print(f"\n✓ Download erfolgreich!")
        if file_path:
            print(f"  Datei: {file_path}")
    else:
        print(f"\n✗ Download fehlgeschlagen: {error}")


if __name__ == "__main__":
    main()
