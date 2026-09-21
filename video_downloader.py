#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Video-Downloader für öffentlich-rechtliche Sender (ARD, ZDF, ORF, SWR, etc.)
Verwendet yt-dlp für Downloads
"""

import subprocess
import platform
import json
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Callable
from datetime import datetime
import sys
import logging
import os
import signal
import time

# Unterstützte Sender
# Nur Video-Sender; ARD Audiothek (ardaudiothek.de) und ARD Sounds (ardsounds.de) werden ausschließlich im Musik-Tab unterstützt
SUPPORTED_SENDERS = {
    'youtube': ['youtube.com', 'youtu.be', 'm.youtube.com'],
    'ard': ['ardmediathek.de', 'ard.de'],
    'ardplus': ['ardplus.de', 'ard-plus.de'],
    'zdf': ['zdf.de', 'zdfmediathek.de'],
    'orf': ['orf.at', 'tvthek.orf.at', 'on.orf.at'],
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
            quality: Video-Qualität ('best', 'niedrigste', '720p', '1080p', etc.)
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
            kwargs = {
                'capture_output': True,
                'text': True,
                'timeout': 5
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ['yt-dlp', '--version'],
                **kwargs
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
            kwargs = {
                'capture_output': True,
                'text': True,
                'timeout': 5
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ['ffmpeg', '-version'],
                **kwargs
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
        
        # YouTube Music (vor YouTube prüfen)
        if 'music.youtube.com' in url_lower:
            return 'YouTube Music'
        
        # YouTube (Video-Tab und Musik-Tab)
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'YouTube'
        
        # ARD Plus
        if 'ardplus.de' in url_lower or 'ard-plus.de' in url_lower:
            return 'ARD Plus'
        
        # ORF (tvthek, on.orf.at – Anmeldung für Altersverifikation)
        if 'orf.at' in url_lower or 'on.orf.at' in url_lower:
            return 'ORF'
        
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
            # Normalisiere ARD Sounds URLs zuerst (konvertiert zu ARD Audiothek-Format)
            original_url = url
            url = self._normalize_ard_sounds_url(url)
            if url != original_url:
                self.log(f"URL normalisiert in get_video_info: {original_url} → {url}")
            
            # Prüfe ob Account/Cookies für den Service benötigt werden
            service = self._detect_service_from_url(url)
            if service == 'ARD Plus':
                account = self._get_account_for_service(service)
                if not account or not account.get('cookies'):
                    self.log("⚠ WARNUNG: Für ARD Plus wird ein Account mit Cookies benötigt!", "WARNING")
                    self.log("⚠ Bitte fügen Sie einen ARD Plus Account in den Einstellungen hinzu.", "WARNING")
            if service == 'ORF':
                account = self._get_account_for_service(service)
                if not account or not account.get('cookies'):
                    self.log("⚠ HINWEIS: Für on.orf.at (Altersverifikation) können Sie sich in den Einstellungen anmelden.", "WARNING")
                    self.log("⚠ Einstellungen → Video-Accounts → ORF (on.orf.at) mit Cookies hinzufügen.", "WARNING")
            
            self.log(f"Rufe Video-Informationen ab: {url}")
            
            # Füge Cookies hinzu falls vorhanden (auch für get_video_info)
            cookies_file = None
            if service:
                account = self._get_account_for_service(service)
                if account:
                    cookies_file = self._get_cookies_file(account)
            
            # Verwende run_ytdlp (unter Windows-EXE: eingebettete API, keine weiteren Fenster)
            from yt_dlp_helper import run_ytdlp
            
            # Für Playlist-URLs: Nimm das erste Video oder verwende --flat-playlist
            if check_series:
                # Bei Serien/Playlists: Hole nur das erste Video für Info
                args = [
                    '--dump-json',
                    '--yes-playlist',
                    '--playlist-end', '1',  # Nur erstes Video
                    '--no-warnings',
                ]
            else:
                args = [
                    '--dump-json',
                    '--no-playlist',
                    '--no-warnings',
                ]
            
            # Füge Cookies hinzu falls vorhanden
            if cookies_file:
                args.extend(['--cookies', cookies_file])
                # Spezielle Optionen für ARD Plus
                if service == 'ARD Plus':
                    args.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                    args.extend(['--add-header', 'Referer:https://www.ardplus.de/'])
                # Optionen für ORF (on.orf.at – Altersverifikation mit Login)
                if service == 'ORF':
                    args.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                    args.extend(['--add-header', 'Referer:https://tvthek.orf.at/'])
            # ORF/on.orf.at: SSL "record layer failure" umgehen (z. B. TLS-Kompatibilität)
            if 'orf.at' in url.lower():
                args.append('--no-check-certificate')
            # ZDF: SSL WRONG_VERSION_NUMBER umgehen (z. B. zdf:channel, Serien)
            if service == 'zdf' or 'zdf.de' in url.lower() or 'zdfmediathek' in url.lower():
                args.append('--legacy-server-connect')
                args.append('--no-check-certificate')
            # ARD Audiothek / ARD Sounds: SSL "record layer failure" umgehen; --prefer-insecure nutzt HTTP wo möglich
            if 'ardaudiothek.de' in url.lower() or 'ardsounds.de' in url.lower():
                args.append('--legacy-server-connect')
                args.append('--no-check-certificate')
                args.append('--prefer-insecure')
            # YouTube: IPv4 erzwingen
            if service == 'youtube' or 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                args.append('-4')
            
            # URL hinzufügen
            args.append(url)
            
            kwargs = {
                'capture_output': True,
                'text': True,
                'encoding': 'utf-8',  # Explizit UTF-8 für Windows
                'errors': 'replace',  # Ersetze ungültige Zeichen statt Fehler
                'timeout': 30
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = run_ytdlp(args, **kwargs)
            
            # Lösche temporäre Cookies-Datei falls vorhanden
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.unlink(cookies_file)
                except:
                    pass
            
            if result.returncode == 0:
                # Bei Playlists kann yt-dlp mehrere JSON-Objekte zurückgeben (eines pro Zeile)
                # ZDF/Manche Extractor schreiben JSON auf stderr – beide Streams prüfen
                lines = []
                for stream in (result.stdout, result.stderr):
                    if stream and stream.strip():
                        for line in stream.strip().split('\n'):
                            if line.strip():
                                lines.append(line.strip())
                if lines:
                    for line in lines:
                        try:
                            info = json.loads(line)
                            self.log(f"✓ Video gefunden: {info.get('title', 'Unbekannt')}")
                            available_qualities = self._extract_available_qualities(info)
                            if available_qualities:
                                info['available_qualities'] = available_qualities
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
                
                # Fallback für ARD Sounds: Parse die Webseite direkt
                if ('ardsounds.de' in url.lower() or 'ardaudiothek.de' in url.lower()) and 'Unsupported URL' in error_output:
                    self.log("yt-dlp unterstützt diese ARD Sounds URL nicht, versuche Webseiten-Parsing...", "WARNING")
                    try:
                        fallback_info = self._get_video_info_from_html(url)
                        if fallback_info:
                            self.log(f"✓ Video-Info durch Webseiten-Parsing erhalten: {fallback_info.get('title', 'Unbekannt')}")
                            return fallback_info
                    except Exception as e:
                        self.log(f"Fehler beim Webseiten-Parsing: {e}", "WARNING")
                
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
    
    def _get_video_info_from_html(self, url: str) -> Optional[Dict]:
        """
        Fallback-Methode: Extrahiert Video-Informationen direkt aus der HTML-Seite
        (wird verwendet, wenn yt-dlp fehlschlägt, z.B. bei ardsounds.de)
        
        Args:
            url: Die Video-URL
            
        Returns:
            Dictionary mit Video-Informationen oder None bei Fehler
        """
        try:
            import ssl
            import urllib.request
            
            # Lade die Webseite
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            _ctx = None
            _ul = (url or '').lower()
            if 'ardsounds.de' in _ul or 'ardaudiothek.de' in _ul:
                _ctx = ssl.create_default_context()
                _ctx.check_hostname = False
                _ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(req, timeout=15, context=_ctx) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # Extrahiere Metadaten aus JSON im HTML
            info = {}

            def find_value(obj, keys):
                """Erste Treffer-Tiefe zuerst; Keys in angegebener Priorität."""
                if isinstance(obj, dict):
                    for key in keys:
                        if key in obj and obj[key] not in (None, ''):
                            return obj[key]
                    for value in obj.values():
                        if isinstance(value, (dict, list)):
                            result = find_value(value, keys)
                            if result not in (None, ''):
                                return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_value(item, keys)
                        if result not in (None, ''):
                            return result
                return None

            def find_media_urls(obj):
                urls = []
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if 'url' in key.lower() and isinstance(value, str) and ('http' in value or value.endswith(('.mp3', '.m4a', '.mp4'))):
                            if value not in urls:
                                urls.append(value)
                        elif isinstance(value, (dict, list)):
                            urls.extend(find_media_urls(value))
                elif isinstance(obj, list):
                    for item in obj:
                        urls.extend(find_media_urls(item))
                return urls

            # Alle JSON-Skripte durchsuchen (Next.js legt publishDate oft nicht im ersten Script)
            for json_match in re.finditer(
                r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
                html, re.IGNORECASE | re.DOTALL
            ):
                try:
                    json_data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    continue

                if 'title' not in info:
                    title = find_value(json_data, ['title', 'headline', 'name'])
                    if title and isinstance(title, str) and len(title.strip()) > 1:
                        info['title'] = title.strip()

                if 'description' not in info:
                    description = find_value(json_data, ['description', 'summary', 'teaser'])
                    if description and isinstance(description, str):
                        info['description'] = description

                if not info.get('broadcast_date'):
                    pub = find_value(json_data, [
                        'publicationStartDateAndTime', 'publishDate', 'publicationDate',
                        'publicationStartDate', 'firstPublicationDate', 'broadcastedOn',
                        'broadcastDate', 'datePublished', 'uploadDate',
                    ])
                    date_iso = self._normalize_broadcast_date(pub) if pub else ''
                    if date_iso:
                        info['broadcast_date'] = date_iso
                        info['upload_date'] = date_iso.replace('-', '')

                if 'thumbnail' not in info:
                    thumbnail = find_value(json_data, ['image', 'thumbnail', 'poster', 'cover'])
                    if thumbnail and isinstance(thumbnail, str):
                        info['thumbnail'] = thumbnail
                    elif isinstance(thumbnail, dict):
                        info['thumbnail'] = thumbnail.get('url') or thumbnail.get('src')

                if 'url' not in info:
                    media_urls = find_media_urls(json_data)
                    if media_urls:
                        audio_urls = [u for u in media_urls if u.endswith(('.mp3', '.m4a'))]
                        if audio_urls:
                            info['url'] = audio_urls[0]
                            info['format'] = 'audio'
                        else:
                            info['url'] = media_urls[0]
            
            # Fallback: Suche nach Media-URLs direkt im HTML (Regex)
            if 'url' not in info:
                media_pattern = r'https?://[^"\'<>\\s]+\.(?:mp3|m4a|mp4)'
                media_matches = re.findall(media_pattern, html, re.IGNORECASE)
                if media_matches:
                    audio_urls = [u for u in media_matches if u.endswith(('.mp3', '.m4a'))]
                    if audio_urls:
                        info['url'] = audio_urls[0]
                    else:
                        info['url'] = media_matches[0]
            
            # Fallback: Extrahiere Titel aus HTML-Tags
            if 'title' not in info:
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
                if title_match:
                    info['title'] = title_match.group(1).strip()
                else:
                    # Extrahiere URN für Fallback-Titel
                    urn_match = re.search(r'urn:ard:episode:([^/\s"\'<>]+)', url, re.IGNORECASE)
                    if urn_match:
                        info['title'] = f'ARD Sounds Episode {urn_match.group(1)[:8]}'
                    else:
                        info['title'] = 'ARD Sounds Episode'
            
            # Erscheinungsdatum wie auf der Sounds-Seite (bevorzugt gegenüber UTC)
            if not info.get('broadcast_date'):
                erschein = re.search(
                    r'Erscheinungsdatum</span>\s*</div>\s*<div[^>]*>\s*<span[^>]*>\s*(\d{1,2}\.\d{1,2}\.20\d{2})\s*</span>',
                    html, re.IGNORECASE
                )
                if not erschein:
                    erschein = re.search(
                        r'Erscheinungsdatum.{0,120}?(\d{1,2}\.\d{1,2}\.20\d{2})',
                        html, re.IGNORECASE | re.DOTALL
                    )
                if erschein:
                    date_iso = self._normalize_broadcast_date(erschein.group(1))
                    if date_iso:
                        info['broadcast_date'] = date_iso
                        info['upload_date'] = date_iso.replace('-', '')

            # Fallback: Datum aus <time datetime="…">
            if not info.get('broadcast_date'):
                time_m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if time_m:
                    date_iso = self._normalize_broadcast_date(time_m.group(1))
                    if date_iso:
                        info['broadcast_date'] = date_iso
                        info['upload_date'] = date_iso.replace('-', '')
            
            # Setze Standardwerte
            info['id'] = url
            info['webpage_url'] = url
            info['duration'] = 0
            info['extractor'] = 'html_parser'
            info['extractor_key'] = 'html_parser'
            
            # Für yt-dlp-Kompatibilität: Setze format_id
            if 'url' in info:
                info['format_id'] = 'html_parsed'
                info['format'] = info.get('format', 'audio')
            
            return info if info.get('url') or info.get('title') else None
            
        except Exception as e:
            self.log(f"Fehler beim HTML-Parsing: {e}", "WARNING")
            return None
    
    def _extract_available_qualities(self, video_info: Dict) -> List[str]:
        """
        Extrahiert verfügbare Qualitäten aus Video-Informationen
        
        Args:
            video_info: Dictionary mit Video-Informationen von yt-dlp
            
        Returns:
            Liste von verfügbaren Qualitäten (z.B. ['best', '1080p', '720p', 'niedrigste'])
        """
        qualities = set()
        
        try:
            formats = video_info.get('formats', [])
            if not formats:
                return ['best', 'niedrigste']
            
            for fmt in formats:
                # Prüfe Höhe (height) für Video-Formate
                height = fmt.get('height')
                if height and isinstance(height, (int, float)):
                    height_int = int(height)
                    if height_int >= 2160:
                        qualities.add('2160p')
                    elif height_int >= 1440:
                        qualities.add('1440p')
                    elif height_int >= 1080:
                        qualities.add('1080p')
                    elif height_int >= 720:
                        qualities.add('720p')
                    elif height_int >= 480:
                        qualities.add('480p')
                    elif height_int >= 360:
                        qualities.add('360p')
                    elif height_int >= 240:
                        qualities.add('240p')
                    elif height_int >= 144:
                        qualities.add('144p')
                
                # Prüfe auch format_note für zusätzliche Informationen
                format_note = fmt.get('format_note', '').lower()
                if format_note:
                    # Extrahiere Auflösung aus format_note (z.B. "1080p", "720p")
                    match = re.search(r'(\d+)p?', format_note)
                    if match:
                        res = int(match.group(1))
                        if res >= 2160:
                            qualities.add('2160p')
                        elif res >= 1440:
                            qualities.add('1440p')
                        elif res >= 1080:
                            qualities.add('1080p')
                        elif res >= 720:
                            qualities.add('720p')
                        elif res >= 480:
                            qualities.add('480p')
                        elif res >= 360:
                            qualities.add('360p')
                        elif res >= 240:
                            qualities.add('240p')
                        elif res >= 144:
                            qualities.add('144p')
            
            # Sortiere Qualitäten von hoch nach niedrig
            quality_order = ['2160p', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p']
            sorted_qualities = []
            for q in quality_order:
                if q in qualities:
                    sorted_qualities.append(q)
            
            # Füge "best" und "niedrigste" immer hinzu
            result = ['best']
            result.extend(sorted_qualities)
            result.append('niedrigste')
            
            return result
            
        except Exception as e:
            self.log(f"Fehler beim Extrahieren der Qualitäten: {e}", "WARNING")
            return ['best', 'niedrigste']  # Fallback
    
    def _get_actual_resolution(self, video_info: Dict, quality: str) -> Optional[str]:
        """
        Bestimmt die tatsächlich verwendete Auflösung basierend auf der ausgewählten Qualität
        
        Args:
            video_info: Dictionary mit Video-Informationen von yt-dlp
            quality: Ausgewählte Qualität ('best', 'niedrigste', '1080p', '720p', etc.)
            
        Returns:
            Tatsächlich verwendete Auflösung (z.B. '1080p', '720p') oder None
        """
        try:
            if quality == "best":
                # Finde die höchste verfügbare Auflösung
                formats = video_info.get('formats', [])
                if not formats:
                    return None
                
                max_height = 0
                for fmt in formats:
                    height = fmt.get('height')
                    if height and isinstance(height, (int, float)):
                        height_int = int(height)
                        if height_int > max_height:
                            max_height = height_int
                
                if max_height > 0:
                    # Konvertiere Höhe zu Auflösungs-String
                    if max_height >= 2160:
                        return '2160p'
                    elif max_height >= 1440:
                        return '1440p'
                    elif max_height >= 1080:
                        return '1080p'
                    elif max_height >= 720:
                        return '720p'
                    elif max_height >= 480:
                        return '480p'
                    elif max_height >= 360:
                        return '360p'
                    elif max_height >= 240:
                        return '240p'
                    elif max_height >= 144:
                        return '144p'
                    else:
                        return f'{max_height}p'
                return None
            elif quality == "niedrigste" or quality == "worst":
                # Finde die niedrigste verfügbare Auflösung
                formats = video_info.get('formats', [])
                if not formats:
                    return None
                
                min_height = float('inf')
                for fmt in formats:
                    height = fmt.get('height')
                    if height and isinstance(height, (int, float)):
                        height_int = int(height)
                        if height_int > 0 and height_int < min_height:
                            min_height = height_int
                
                if min_height != float('inf'):
                    # Konvertiere Höhe zu Auflösungs-String
                    if min_height >= 2160:
                        return '2160p'
                    elif min_height >= 1440:
                        return '1440p'
                    elif min_height >= 1080:
                        return '1080p'
                    elif min_height >= 720:
                        return '720p'
                    elif min_height >= 480:
                        return '480p'
                    elif min_height >= 360:
                        return '360p'
                    elif min_height >= 240:
                        return '240p'
                    elif min_height >= 144:
                        return '144p'
                    else:
                        return f'{int(min_height)}p'
                return None
            elif quality.endswith('p'):
                # Spezifische Auflösung wurde ausgewählt
                return quality
            else:
                return None
        except Exception as e:
            self.log(f"Fehler beim Bestimmen der Auflösung: {e}", "WARNING")
            return None
    
    def _normalize_ard_sounds_url(self, url: str) -> str:
        """Normalisiert ARD Sounds URLs für yt-dlp (entfernt /embed/, behält ardsounds.de bei)."""
        if not url or 'ardsounds.de' not in url.lower():
            return url
        
        url_lower = url.lower()
        
        # Extrahiere URN falls vorhanden (urn:ard:episode:... oder urn:ard:show:...)
        # Suche nach URN in der gesamten URL (auch nach /embed/)
        # URN kann am Ende ein trailing slash haben, den wir entfernen
        urn_match = re.search(r'urn:ard:(?:episode|show):[^/\s"\'<>]+/?', url, re.IGNORECASE)
        if urn_match:
            urn = urn_match.group(0).rstrip('/')
            # Entferne /embed/ und behalte ardsounds.de (nicht mehr zu ardaudiothek.de konvertieren)
            if 'urn:ard:episode:' in urn.lower():
                # Entferne /embed/ falls vorhanden, behalte ardsounds.de
                if '/embed/episode/' in url_lower:
                    normalized = f"https://www.ardsounds.de/episode/{urn}"
                else:
                    normalized = f"https://www.ardsounds.de/episode/{urn}"
                self.log(f"ARD Sounds URL normalisiert: {url} → {normalized}")
                return normalized
            elif 'urn:ard:show:' in urn.lower():
                # Entferne /embed/ falls vorhanden, behalte ardsounds.de
                if '/embed/sendung/' in url_lower or '/embed/podcast/' in url_lower:
                    normalized = f"https://www.ardsounds.de/sendung/{urn}"
                else:
                    normalized = f"https://www.ardsounds.de/sendung/{urn}"
                self.log(f"ARD Sounds URL normalisiert: {url} → {normalized}")
                return normalized
        
        # Falls keine URN direkt gefunden, aber /embed/episode/ oder /embed/podcast/ vorhanden: entferne /embed/ und extrahiere URN
        if '/embed/' in url_lower:
            # Entferne /embed/ und extrahiere dann die URN
            url_no_embed = url.replace('/embed/episode/', '/episode/')
            url_no_embed = url_no_embed.replace('/embed/podcast/', '/podcast/')
            url_no_embed = url_no_embed.replace('/embed/sendung/', '/sendung/')
            url_no_embed = url_no_embed.rstrip('/')
            
            # Versuche URN aus der bereinigten URL zu extrahieren
            urn_match = re.search(r'urn:ard:(?:episode|show):[^/\s"\'<>]+', url_no_embed, re.IGNORECASE)
            if urn_match:
                urn = urn_match.group(0)
                if 'urn:ard:episode:' in urn.lower():
                    normalized = f"https://www.ardsounds.de/episode/{urn}"
                    self.log(f"ARD Sounds URL normalisiert (nach /embed/ Entfernung): {url} → {normalized}")
                    return normalized
                elif 'urn:ard:show:' in urn.lower():
                    normalized = f"https://www.ardsounds.de/sendung/{urn}"
                    self.log(f"ARD Sounds URL normalisiert (nach /embed/ Entfernung): {url} → {normalized}")
                    return normalized
            
            # Fallback: Wenn keine URN gefunden, aber /episode/ oder /podcast/ vorhanden, versuche ID zu extrahieren
            episode_match = re.search(r'/episode/([^/\s"\'<>]+)', url_no_embed)
            if episode_match:
                episode_id = episode_match.group(1)
                if 'urn:ard:episode:' in episode_id.lower():
                    normalized = f"https://www.ardsounds.de/episode/{episode_id}"
                    self.log(f"ARD Sounds URL normalisiert (Episode-ID): {url} → {normalized}")
                    return normalized
            podcast_match = re.search(r'/podcast/([^/\s"\'<>]+)', url_no_embed)
            if podcast_match:
                podcast_id = podcast_match.group(1)
                if 'urn:ard:show:' in podcast_id.lower():
                    normalized = f"https://www.ardsounds.de/sendung/{podcast_id}"
                    self.log(f"ARD Sounds URL normalisiert (Podcast-ID): {url} → {normalized}")
                    return normalized
            
            # Letzter Fallback: Entferne nur /embed/, behalte ardsounds.de
            self.log(f"ARD Sounds URL: /embed/ entfernt, aber keine URN gefunden: {url_no_embed}")
            return url_no_embed
        
        return url
    
    def _parse_ardsounds_listing_episode_meta(self, html_content: str, urn_short: str) -> Tuple[Optional[str], int, str]:
        """
        Extrahiert Titel, Dauer (Sekunden) und Sendedatum aus der ARD-Sounds-Sendungsliste (SSR-HTML).
        Auf der Seite steht typischerweise zuerst der Link, danach <h3> mit dem Folgentitel,
        danach die Spieldauer als „45<!-- --> Min.“ in einem <span>, oft mit Datum.
        """
        import html as html_module
        if not html_content or not urn_short:
            return None, 0, ''
        try:
            needle = f'urn:ard:episode:{urn_short}'
            pos = html_content.find(needle)
            if pos < 0:
                return None, 0, ''
            # Fenster ab erstem Vorkommen der Episoden-URN (ein Listeneintrag)
            chunk = html_content[pos : pos + 9000]
            title = None
            h3_m = re.search(r'<h3[^>]*>([^<]+)</h3>', chunk, re.IGNORECASE)
            if h3_m:
                title = html_module.unescape(re.sub(r'\s+', ' ', h3_m.group(1).strip()))
                # Nur typische ARD-Suffixe mit echtem Worttrenner (nicht Bindestrich in „Krimi-Podcast“)
                title = re.sub(r'\s+[-–—]\s+Krimi-Podcast.*$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s+[-–—]\s+Podcast.*$', '', title, flags=re.IGNORECASE)
                title = title.strip() or None
            if not title:
                # Erstes Bild im Block: alt= oft „Serie Staffel X Folge Y“
                alt_m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
                if alt_m:
                    raw = html_module.unescape(alt_m.group(1).strip())
                    title = raw.split('・')[0].split('|')[0].strip() or None
            # Dauer: „45<!-- --> Min.“ oder „116 Min.“
            dur_m = re.search(r'(\d+)(?:<!--\s*-->)?\s*Min\.', chunk, re.IGNORECASE)
            seconds = int(dur_m.group(1)) * 60 if dur_m else 0
            date_iso = ''
            time_m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', chunk, re.IGNORECASE)
            if time_m:
                date_iso = self._normalize_broadcast_date(time_m.group(1))
            if not date_iso:
                de_m = re.search(r'\b(\d{1,2})\.(\d{1,2})\.(20\d{2})\b', chunk)
                if de_m:
                    date_iso = self._normalize_broadcast_date(de_m.group(0))
            if not date_iso:
                iso_m = re.search(r'\b(20\d{2}-\d{2}-\d{2})(?:T|\b)', chunk)
                if iso_m:
                    date_iso = self._normalize_broadcast_date(iso_m.group(1))
            return title, seconds, date_iso
        except Exception:
            return None, 0, ''
    
    def _fetch_ardsounds_show_episodes_via_api(self, series_url: str) -> Optional[Dict]:
        """
        Lädt alle Folgen einer Sendung über api.ardaudiothek.de/programsets/{urn:ard:show:…}
        mit offset/limit. Die Webseite listet in HTML oft nur die ersten ~12 Einträge.
        """
        import json as json_lib
        import ssl
        import urllib.request
        
        urn_m = re.search(r'urn:ard:show:[^/\s"\'<>]+', series_url or '', re.IGNORECASE)
        if not urn_m:
            return None
        show_urn = urn_m.group(0).rstrip('/')
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        all_nodes: List = []
        offset = 0
        limit = 100
        total: Optional[int] = None
        series_title: Optional[str] = None
        
        try:
            while True:
                api_url = f'https://api.ardaudiothek.de/programsets/{show_urn}?offset={offset}&limit={limit}'
                req = urllib.request.Request(
                    api_url,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'application/json',
                    },
                )
                with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                    data = json_lib.loads(resp.read().decode('utf-8', errors='replace'))
                ps = (data.get('data') or {}).get('programSet')
                if not ps:
                    break
                if series_title is None:
                    series_title = (ps.get('title') or '').strip() or None
                if total is None:
                    try:
                        total = int(ps.get('numberOfElements') or 0)
                    except (TypeError, ValueError):
                        total = 0
                nodes = (ps.get('items') or {}).get('nodes') or []
                if not nodes:
                    break
                all_nodes.extend(nodes)
                if total and len(all_nodes) >= total:
                    break
                # Weiter paginieren, auch wenn die Seite weniger als limit liefert
                # (API kann z. B. 40er-Seiten liefern, numberOfElements aber 200+)
                if not nodes:
                    break
                offset += len(nodes)
                if total and offset >= total:
                    break
                # Sicherheitsnetz gegen Endlosschleifen
                if offset > 5000 or len(all_nodes) > 5000:
                    break
                if len(nodes) < limit and (not total or len(all_nodes) >= total):
                    break
                if len(nodes) < limit and total and len(all_nodes) < total:
                    # Manche Antworten sind kürzer als limit – trotzdem weiter bis total
                    continue
                if len(nodes) < limit:
                    break
        except Exception as e:
            self.log(f"ARD programsets API: {e}", "WARNING")
            return None
        
        if not all_nodes:
            return None
        
        if series_title:
            self._series_name_for_fallback = series_title
        
        # Rohdaten sammeln, dann chronologisch nummerieren (älteste Folge = E01)
        # Nach Website-Umbau: assetId oft urn:ard:section:… (nicht nur urn:ard:episode:…)
        raw: List[Dict] = []
        for n in all_nodes:
            if not isinstance(n, dict):
                continue
            asset = (n.get('assetId') or n.get('publicationId') or '').strip()
            share = (n.get('sharingUrl') or '').strip()
            ep_url = ''
            if share and '/episode/' in share.lower():
                ep_url = share.rstrip('/')
                if not ep_url.startswith('http'):
                    ep_url = f"https://www.ardsounds.de{ep_url if ep_url.startswith('/') else '/' + ep_url}"
            elif asset and (
                'urn:ard:episode:' in asset.lower()
                or 'urn:ard:section:' in asset.lower()
                or 'urn:ard:publication:' in asset.lower()
                or 'urn:ard:extra:' in asset.lower()
            ):
                # section/publication/extra ebenfalls als Episode-URL nutzbar
                urn = asset
                if 'urn:ard:publication:' in urn.lower():
                    urn = 'urn:ard:section:' + urn.split(':')[-1]
                ep_url = f"https://www.ardsounds.de/episode/{urn}"
            if not ep_url:
                continue
            # Canonical ohne trailing slash
            ep_url = ep_url.rstrip('/')
            try:
                dur = int(n.get('duration') or 0)
            except (TypeError, ValueError):
                dur = 0
            title = (n.get('title') or '').strip() or 'Folge'
            thumb = None
            img = n.get('image')
            if isinstance(img, dict):
                thumb = img.get('url') or img.get('url1X1')
            date_iso = self._broadcast_date_from_info(n)
            season_num = 1
            episode_hint = None
            part_of = None  # z. B. 1 bei „(1/5)“
            # Staffel/Folge aus Titel, falls vorhanden (z. B. S02/E07, Staffel 3)
            m_se = re.search(r'\(S(\d+)\s*/\s*E(\d+)\)', title, re.IGNORECASE)
            if not m_se:
                m_se = re.search(r'\bS(\d+)\s*E(\d+)\b', title, re.IGNORECASE)
            if m_se:
                try:
                    season_num = int(m_se.group(1))
                    episode_hint = int(m_se.group(2))
                except ValueError:
                    pass
            else:
                m_st = re.search(r'\bStaffel\s*(\d+)\b', title, re.IGNORECASE)
                if m_st:
                    try:
                        season_num = int(m_st.group(1))
                    except ValueError:
                        pass
            # Mini-Serien: „Wo warst du? (1/5)“ – nur Sortierung bei gleichem Sendedatum
            # (Episodennummer wird danach fortlaufend vergeben)
            m_part = re.search(r'\((\d+)\s*/\s*(\d+)\)', title)
            if m_part:
                try:
                    part_of = int(m_part.group(1))
                except ValueError:
                    part_of = None
            raw.append({
                'title': title,
                'url': ep_url,
                'season_number': season_num,
                'episode_hint': episode_hint,
                'series': series_title or getattr(self, '_series_name_for_fallback', None) or 'Unbekannte Serie',
                'duration': dur,
                'duration_string': self._format_duration(dur) if dur else '0:00',
                'thumbnail': thumb,
                'id': asset or share or ep_url,
                'broadcast_date': date_iso,
                'upload_date': date_iso.replace('-', '') if date_iso else '',
                '_sort_date': date_iso or '',
                '_sort_part': part_of if part_of is not None else 10_000,
            })
        
        if not raw:
            return None
        
        # Duplikate nach URL entfernen (API kann section+episode mischen)
        seen_urls = set()
        deduped: List[Dict] = []
        for ep in raw:
            u = (ep.get('url') or '').lower()
            if u in seen_urls:
                continue
            seen_urls.add(u)
            deduped.append(ep)
        raw = deduped
        
        # Chronologisch; bei gleichem Datum nach (n/m) bzw. Titel
        raw.sort(key=lambda e: (
            e.get('_sort_date') or '9999',
            e.get('_sort_part') if e.get('_sort_part') is not None else 10_000,
            e.get('title') or '',
        ))
        
        seasons: Dict[int, List[Dict]] = {}
        counters: Dict[int, int] = {}
        for ep in raw:
            sn = int(ep.get('season_number') or 1)
            counters[sn] = counters.get(sn, 0) + 1
            # Fortlaufend nach Sortierung; SxxExx aus Titel hat Vorrang
            ep_num = ep.get('episode_hint') if ep.get('episode_hint') is not None else counters[sn]
            item = {k: v for k, v in ep.items() if not k.startswith('_') and k != 'episode_hint'}
            item['episode_number'] = ep_num
            item['season_number'] = sn
            seasons.setdefault(sn, []).append(item)
        
        for sn in seasons:
            seasons[sn].sort(key=lambda x: x.get('episode_number') or 0)
        sorted_seasons = dict(sorted(seasons.items()))
        total_eps = sum(len(v) for v in sorted_seasons.values())
        
        self.log(
            f"✓ {total_eps} Folgen über ARD programsets API "
            f"({len(sorted_seasons)} Staffel-Gruppe(n), Gesamt laut API: {total or total_eps})"
        )
        sn = series_title or getattr(self, '_series_name_for_fallback', None) or 'Unbekannte Serie'
        return {
            'series_name': sn,
            'seasons': sorted_seasons,
            'total_episodes': total_eps,
        }
    
    def is_series_or_season(self, url: str) -> bool:
        """
        Prüft ob die URL eine Serie oder Staffel ist
        
        Args:
            url: Die Video-URL
            
        Returns:
            True wenn es eine Serie/Staffel ist, sonst False
        """
        try:
            # Normalisiere ARD Sounds URLs zuerst
            original_url = url
            url = self._normalize_ard_sounds_url(url)
            if url != original_url:
                self.log(f"URL normalisiert in is_series_or_season: {original_url} → {url}")
            
            # Prüfe URL-Muster (z.B. /serie/, /staffel-, /season, /sammlung/, /sendung/)
            url_lower = url.lower()
            # ARD Audiothek / ARD Sounds: Nur echte Sendungs-/Serien-URLs, keine Einzelfolgen
            if 'ardaudiothek.de' in url_lower or 'ardsounds.de' in url_lower:
                # Einzelfolgen erkennen (auch nach Normalisierung)
                if '/episode/' in url_lower or 'urn:ard:episode:' in url_lower:
                    return False  # Einzelfolge – kein Serien-Dialog
                # Sendungen/Podcasts/Serien erkennen
                if '/sendung/' in url_lower or 'urn:ard:show:' in url_lower or '/podcast/' in url_lower:
                    self.log("ARD Audiothek/Sounds Sendung/Serie/Podcast erkannt")
                    return True
                # Auch Hauptseiten oder Sammlungen könnten Serien sein
                if url_lower.endswith('ardsounds.de') or url_lower.endswith('ardsounds.de/') or '/sammlung/' in url_lower:
                    # Prüfe ob es eine Sammlung/Serie sein könnte
                    return True
            # YouTube/YouTube Music: Kanal-, Playlist- und Album/Browse-URLs = Auswahldialog (welche Titel/Folgen)
            if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
                if '/channel/' in url_lower or '/@' in url_lower:
                    self.log("YouTube/YouTube Music Kanal erkannt (alle Uploads als Playlist)")
                    return True
                if 'list=' in url_lower or '/playlist' in url_lower or '/browse/' in url_lower:
                    self.log("YouTube/YouTube Music Playlist/Album erkannt – Auswahl der Titel anzeigen")
                    return True
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
            # Normalisiere ARD Sounds URLs zuerst (konvertiert zu ARD Audiothek-Format)
            original_url = url
            url = self._normalize_ard_sounds_url(url)
            if url != original_url:
                self.log(f"URL normalisiert in get_series_episodes: {original_url} → {url}")
            
            # Speichere die ursprüngliche URL für Fallback-Parsing
            original_series_url = original_url

            # ARD Sounds / Audiothek-Sendung: API zuerst (yt-dlp liefert oft nur einen Bruchteil der Folgen)
            url_l = (url or '').lower()
            orig_l = (original_url or '').lower()
            if (
                ('ardsounds.de' in url_l or 'ardaudiothek.de' in url_l or 'ardsounds.de' in orig_l or 'ardaudiothek.de' in orig_l)
                and ('/sendung/' in url_l or '/sendung/' in orig_l or 'urn:ard:show:' in url_l or 'urn:ard:show:' in orig_l)
                and '/episode/' not in url_l and 'urn:ard:episode:' not in url_l
            ):
                api_url = original_url if 'urn:ard:show:' in orig_l else url
                # Show-URN ggf. aus der Seite holen, wenn sie in der URL fehlt
                if 'urn:ard:show:' not in (api_url or '').lower():
                    try:
                        import ssl
                        import urllib.request
                        _ctx = ssl.create_default_context()
                        _ctx.check_hostname = False
                        _ctx.verify_mode = ssl.CERT_NONE
                        _req = urllib.request.Request(
                            api_url,
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                        )
                        with urllib.request.urlopen(_req, timeout=30, context=_ctx) as _resp:
                            _html = _resp.read().decode('utf-8', errors='replace')
                        _m = re.search(r'urn:ard:show:[^/\s"\'<>]+', _html, re.IGNORECASE)
                        if _m:
                            api_url = f"https://www.ardsounds.de/sendung/{_m.group(0)}"
                            self.log(f"ARD Sounds: Show-URN aus Seite: {_m.group(0)}")
                    except Exception as e:
                        self.log(f"ARD Sounds: Konnte Show-URN nicht aus Seite lesen: {e}", "WARNING")
                self.log(f"ARD Sounds/Audiothek: lade Folgenliste bevorzugt über API…")
                api_series = self._fetch_ardsounds_show_episodes_via_api(api_url)
                if api_series and api_series.get('seasons') and api_series.get('total_episodes', 0) > 0:
                    return api_series
                self.log("ARD API ohne Ergebnis – Fallback yt-dlp/HTML…", "WARNING")
            
            # Prüfe ob es eine YouTube-URL ist
            is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
            
            # Für YouTube-Playlists: Verwende URL direkt
            # Für YouTube-Kanal: Nur die Uploads-Playlist (UU...), nicht die ganze Kanal-Seite (Alben/Playlists/Mixes)
            if is_youtube:
                series_url = url
                url_lower = url.lower()
                if '/channel/' in url_lower:
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    path_parts = [p for p in parsed.path.split('/') if p]
                    # z.B. ['channel', 'UCI5yNfERjqXi1dKpom6o2CQ']
                    if len(path_parts) >= 2 and path_parts[0].lower() == 'channel':
                        channel_id = path_parts[1]
                        if channel_id.startswith('UC') and len(channel_id) >= 24:
                            # Uploads-Playlist = UU + Rest der Kanal-ID (nur die Uploads, nicht Alben/Playlists)
                            uploads_playlist_id = 'UU' + channel_id[2:]
                            series_url = f"{parsed.scheme}://{parsed.netloc}/playlist?list={uploads_playlist_id}"
                            self.log(f"YouTube-Kanal → nur Uploads-Playlist dieses Kanals: {series_url}")
                self.log(f"Rufe YouTube-Playlist-Informationen ab: {series_url}")
            else:
                # Spezielle Behandlung für ARD Mediathek / ARD Audiothek / ARD Sounds Sammlungen/Sendungen
                # Nach Normalisierung sollte url jetzt ardsounds.de sein (ohne /embed/)
                if 'ardaudiothek.de' in url.lower() or 'ardsounds.de' in url.lower():
                    series_url = url
                    service_name = "ARD Sounds" if 'ardsounds.de' in url.lower() else "ARD Audiothek"
                    self.log(f"Rufe {service_name} Sendungs-Informationen ab: {series_url}")
                    # Speichere die ursprüngliche URL für Fallback-Parsing (falls yt-dlp fehlschlägt)
                    # Verwende die ursprüngliche URL, falls sie ardsounds.de enthält, sonst die normalisierte
                    if 'ardsounds.de' in original_url.lower():
                        # Speichere als Instanzvariable, damit sie im Fallback verfügbar ist
                        self._original_series_url_for_parsing = original_url
                    else:
                        # Wenn die ursprüngliche URL bereits normalisiert war, verwende die normalisierte
                        self._original_series_url_for_parsing = url
                elif 'ardmediathek.de' in url.lower():
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
            
            # ARD Audiothek / ARD Sounds: ohne --flat-playlist, damit Titel und Serienname in den Metadaten stehen
            # --prefer-insecure kann SSL-Handshake-Probleme umgehen (nutzt HTTP wo möglich)
            if 'ardaudiothek.de' in series_url.lower() or 'ardsounds.de' in series_url.lower():
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--yes-playlist',
                    '--playlist-end', '500',
                    '--prefer-insecure',
                    '--legacy-server-connect',
                    '--no-check-certificate',
                    series_url
                ]
            elif 'ardmediathek.de' in series_url.lower():
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
            elif is_youtube and ('/channel/' in series_url or '/@' in series_url):
                # YouTube-Kanal: --flat-playlist für schnelle Abfrage (vermeidet Timeout), Kanalname aus erstem Eintrag
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--flat-playlist',
                    '--yes-playlist',
                    '--playlist-end', '500',
                    '--no-warnings',
                    '-4',
                    series_url
                ]
            elif is_youtube and ('list=' in series_url or '/playlist' in series_url):
                # YouTube-Playlist: ohne --flat-playlist, damit jedes Video playlist_title enthält (gemeinsamer Ordner)
                cmd = [
                    'yt-dlp',
                    '--dump-json',
                    '--yes-playlist',
                    '--playlist-end', '500',
                    '--no-warnings',
                    '-4',
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
            
            # run_ytdlp: unter Windows-EXE eingebettete API, keine weiteren Fenster
            from yt_dlp_helper import run_ytdlp
            
            # Konvertiere cmd zu args (ohne 'yt-dlp')
            args = cmd[1:] if cmd[0] == 'yt-dlp' else cmd
            # YouTube: Cookies aus Account-Verwaltung für Kanal/Playlist-Abruf (Serien-Dialog)
            if is_youtube and getattr(self, 'gui_instance', None):
                service = 'YouTube Music' if 'music.youtube.com' in series_url.lower() else 'YouTube'
                account = self._get_account_for_service(service)
                if account:
                    cookies_file = self._get_cookies_file(account)
                    if cookies_file:
                        args.extend(['--cookies', cookies_file])
            # ZDF / ARD Audiothek / ARD Sounds: SSL umgehen bei Serien/Playlist-Abruf
            if 'zdf.de' in series_url.lower() or 'zdfmediathek' in series_url.lower():
                args = ['--legacy-server-connect', '--no-check-certificate'] + args
            elif 'ardaudiothek.de' in series_url.lower() or 'ardsounds.de' in series_url.lower():
                args = ['--legacy-server-connect', '--no-check-certificate'] + args
            
            kwargs = {
                'capture_output': True,
                'text': True,
                'encoding': 'utf-8',  # Explizit UTF-8 für Windows
                'errors': 'replace',  # Ersetze ungültige Zeichen statt Fehler
                'timeout': 120
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            # Linux: ~/.local/bin im PATH (pipx/User-yt-dlp), damit gleiche Version wie beim Download
            if platform.system() != 'win32':
                run_env = os.environ.copy()
                home_bin = os.path.join(os.environ.get('HOME', ''), '.local', 'bin')
                if home_bin and os.path.isdir(home_bin):
                    run_env['PATH'] = home_bin + os.pathsep + run_env.get('PATH', '')
                kwargs['env'] = run_env
            
            # ARD Audiothek / ARD Sounds: Bei SSL-Fehler bis zu 3× wiederholen (Server reagiert oft erst beim 2./3. Versuch)
            import time
            max_attempts = 3 if ('ardaudiothek.de' in series_url.lower() or 'ardsounds.de' in series_url.lower()) else 1
            for attempt in range(max_attempts):
                result = run_ytdlp(args, **kwargs)
                if result.returncode == 0:
                    break
                if attempt < max_attempts - 1 and ('ardaudiothek.de' in series_url.lower() or 'ardsounds.de' in series_url.lower()):
                    err = (result.stderr or result.stdout or '').lower()
                    if 'ssl' in err or 'record layer failure' in err or 'unable to download' in err:
                        wait_sec = 5
                        service_name = "ARD Sounds" if 'ardsounds.de' in series_url.lower() else "ARD Audiothek"
                        self.log(f"{service_name}: SSL/Netzwerk-Fehler (Versuch {attempt + 1}/{max_attempts}) – wiederhole in {wait_sec} s…")
                        time.sleep(wait_sec)
                        continue
                break
            
            # Wenn der erste Versuch fehlschlägt und es eine ARD Sammlung ist, versuche alternative Methoden
            if result.returncode != 0 and 'ardmediathek.de' in series_url.lower():
                error_output = result.stderr.lower() if result.stderr else ''
                if 'unsupported url' in error_output or 'no video found' in error_output:
                    # Versuche ohne expliziten Extractor (lass yt-dlp automatisch erkennen)
                    self.log("Erster Versuch fehlgeschlagen, versuche ohne expliziten Extractor...")
                    args_alt = [
                        '--dump-json',
                        '--flat-playlist',
                        '--yes-playlist',
                        '--playlist-end', '500',
                        series_url
                    ]
                    kwargs_alt = {
                        'capture_output': True,
                        'text': True,
                        'encoding': 'utf-8',
                        'errors': 'replace',
                        'timeout': 120
                    }
                    if platform.system() == 'Windows':
                        kwargs_alt['creationflags'] = subprocess.CREATE_NO_WINDOW
                    elif platform.system() != 'win32':
                        run_env = os.environ.copy()
                        home_bin = os.path.join(os.environ.get('HOME', ''), '.local', 'bin')
                        if home_bin and os.path.isdir(home_bin):
                            run_env['PATH'] = home_bin + os.pathsep + run_env.get('PATH', '')
                        kwargs_alt['env'] = run_env
                    result = run_ytdlp(args_alt, **kwargs_alt)
                    
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
            
            # Prüfe ob returncode 0 ist ODER ob stderr nur Warnungen/Fehler über nicht-normalisierte URLs enthält
            # (yt-dlp kann Warnungen über ardsounds.de/embed/ URLs ausgeben, aber trotzdem gültige JSON zurückgeben)
            stderr_text = (result.stderr or '').strip()
            has_unsupported_url_error = 'unsupported url' in stderr_text.lower() and 'ardsounds.de/embed' in stderr_text.lower()
            
            # Wenn yt-dlp fehlschlägt wegen ARD Sounds URLs, versuche Webseiten-Parsing als Fallback
            # Prüfe auch, ob die ursprüngliche URL ardsounds.de war (auch wenn sie jetzt normalisiert ist)
            original_was_ardsounds = 'ardsounds.de' in series_url.lower() or 'ardaudiothek.de' in series_url.lower()
            if result.returncode != 0 and original_was_ardsounds:
                # Prüfe ob der Fehler mit ARD Sounds URLs zusammenhängt
                if has_unsupported_url_error or 'ardsounds.de' in stderr_text.lower() or not result.stdout or not result.stdout.strip():
                    self.log("yt-dlp fehlgeschlagen wegen nicht-normalisierter URLs, versuche Webseiten-Parsing...")
                    try:
                        import urllib.request
                        import re
                        
                        # Extrahiere Serienname aus URL (falls noch nicht vorhanden)
                        # ARD Sounds: /sendung/SLUG/urn:ard:show:... oder /sendung/urn:ard:show:...
                        fallback_series_name = None
                        if 'ardsounds.de' in series_url.lower():
                            # Versuche Serienname aus URL zu extrahieren
                            match = re.search(r'ardsounds\.de/sendung/([^/]+)/urn:ard:show:', series_url, re.IGNORECASE)
                            if match:
                                slug = match.group(1)
                                fallback_series_name = slug.replace('-', ' ').title()
                            # Fallback: Versuche aus HTML-Titel zu extrahieren (wird später gemacht)
                        elif 'ardaudiothek.de' in series_url.lower():
                            match = re.search(r'ardaudiothek\.de/sendung/([^/]+)/', series_url, re.IGNORECASE)
                            if match:
                                slug = match.group(1)
                                fallback_series_name = slug.replace('-', ' ').title()
                        
                        # Verwende fallback_series_name, wenn series_name noch nicht definiert ist
                        if not hasattr(self, '_series_name_for_fallback'):
                            self._series_name_for_fallback = fallback_series_name
                        
                        # Alle Folgen: api.ardaudiothek.de mit offset/limit (HTML „Alle Folgen“ ≈ nur erste ~12)
                        if 'urn:ard:show:' in series_url.lower():
                            api_series = self._fetch_ardsounds_show_episodes_via_api(series_url)
                            if api_series and api_series.get('seasons'):
                                return api_series
                        
                        # Lade die Webseite (verwende die ursprüngliche ardsounds.de URL, falls vorhanden)
                        # Versuche zuerst die ursprüngliche URL zu verwenden (falls gespeichert)
                        parse_url = series_url
                        # Prüfe ob wir die ursprüngliche URL haben (als Instanzvariable gespeichert)
                        if hasattr(self, '_original_series_url_for_parsing'):
                            parse_url = self._original_series_url_for_parsing
                            self.log(f"Verwende ursprüngliche URL für Parsing: {parse_url}")
                        elif 'ardsounds.de' in series_url.lower():
                            # URL ist bereits ardsounds.de, verwende sie direkt
                            parse_url = series_url
                        elif 'ardaudiothek.de' in series_url.lower() and 'urn:ard:show:' in series_url.lower():
                            # Versuche die ursprüngliche ardsounds.de URL zu rekonstruieren
                            # Extrahiere URN
                            urn_match = re.search(r'urn:ard:show:[^/\s"\'<>]+', series_url, re.IGNORECASE)
                            if urn_match:
                                urn = urn_match.group(0)
                                # Versuche die ursprüngliche URL zu rekonstruieren (mit Serienname)
                                # Da wir den Seriennamen nicht haben, versuchen wir es mit der normalisierten URL
                                # Die Webseite sollte auch unter ardsounds.de erreichbar sein
                                # Für jetzt: Versuche es mit der normalisierten URL
                                pass
                        
                        self.log(f"Lade Webseite für Parsing (Fallback): {parse_url}")
                        req = urllib.request.Request(parse_url, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        })
                        with urllib.request.urlopen(req, timeout=30) as response:
                            html_content = response.read().decode('utf-8', errors='ignore')
                        
                        # Extrahiere Serienname aus HTML-Titel, falls noch nicht vorhanden
                        if not fallback_series_name:
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
                            if title_match:
                                title_text = title_match.group(1).strip()
                                # Entferne " - ARD Sounds" oder ähnliche Suffixe
                                title_text = re.sub(r'\s*[-–—]\s*ARD\s+Sounds.*$', '', title_text, flags=re.IGNORECASE)
                                title_text = re.sub(r'\s*[-–—]\s*Jetzt.*$', '', title_text, flags=re.IGNORECASE)
                                if title_text:
                                    fallback_series_name = title_text.strip()
                                    self._series_name_for_fallback = fallback_series_name
                        
                        # Suche nach Episoden-URLs im HTML
                        # Format 1: https://www.ardsounds.de/episode/urn:ard:episode:... (vollständig, ohne /embed/)
                        # Format 2: https://www.ardsounds.de/embed/episode/urn:ard:episode:... (vollständig, mit /embed/)
                        # Format 3: /episode/urn:ard:episode:... (relativ, kann trailing slash haben)
                        # Format 4: /embed/episode/urn:ard:episode:... (relativ, mit /embed/)
                        episode_urls_full = re.findall(r'https://www\.ardsounds\.de/(?:embed/)?episode/urn:ard:episode:[^"\s<>]+/?', html_content)
                        episode_urls_rel = re.findall(r'/(?:embed/)?episode/urn:ard:episode:[^"\s<>/]+/?', html_content)
                        # Kombiniere beide Formate
                        episode_urls = list(episode_urls_full)
                        # Konvertiere relative URLs zu vollständigen URLs
                        for rel_url in episode_urls_rel:
                            # Entferne trailing slash und /embed/
                            rel_url = rel_url.rstrip('/')
                            if rel_url.startswith('/embed/'):
                                rel_url = rel_url.replace('/embed/', '/')
                            full_url = f"https://www.ardsounds.de{rel_url}"
                            if full_url not in episode_urls:
                                episode_urls.append(full_url)
                        
                        if episode_urls:
                            # Entferne Duplikate und normalisiere URLs
                            unique_urls = []
                            seen_urns = set()
                            for ep_url in episode_urls:
                                # Stelle sicher, dass es eine vollständige URL ist
                                if not ep_url.startswith('http'):
                                    ep_url = f"https://www.ardsounds.de{ep_url}"
                                # Entferne /embed/ falls vorhanden
                                ep_url = ep_url.replace('/embed/episode/', '/episode/')
                                # Extrahiere URN (kann am Ende ein trailing slash haben)
                                urn_match = re.search(r'urn:ard:episode:[^/\s"\'<>]+/?', ep_url, re.IGNORECASE)
                                if urn_match:
                                    urn = urn_match.group(0).rstrip('/')
                                    if urn not in seen_urns:
                                        seen_urns.add(urn)
                                        # Normalisiere zu ardsounds.de Format (ohne /embed/, ohne trailing slash)
                                        normalized_url = f"https://www.ardsounds.de/episode/{urn}"
                                        unique_urls.append(normalized_url)
                            
                            if unique_urls:
                                self.log(f"✓ {len(unique_urls)} Episoden durch Webseiten-Parsing gefunden")
                                # Versuche Titel aus dem HTML zu extrahieren
                                # Suche nach Titel-Informationen im HTML (oft in <h3>, <a>, oder data-Attributen)
                                # Erstelle Episode-Objekte aus den URLs
                                episodes = []
                                for i, ep_url in enumerate(unique_urls, 1):
                                    # Extrahiere URN für Titel-/Dauer-Suche
                                    ep_urn_match = re.search(r'urn:ard:episode:[^/\s"\'<>]+', ep_url, re.IGNORECASE)
                                    ep_urn = ep_urn_match.group(0) if ep_urn_match else None
                                    urn_short = ep_urn.split(':')[-1] if ep_urn else ''
                                    parsed_title, dur_seconds, parsed_date = (
                                        self._parse_ardsounds_listing_episode_meta(html_content, urn_short)
                                        if urn_short
                                        else (None, 0, '')
                                    )
                                    title = parsed_title if parsed_title else f'Folge {i}'
                                    duration_str = (
                                        self._format_duration(dur_seconds)
                                        if dur_seconds
                                        else '0:00'
                                    )
                                    
                                    # Erstelle Episode-Objekt ohne yt-dlp (da es nicht funktioniert)
                                    # Verwende fallback_series_name, wenn series_name noch nicht definiert ist
                                    ep_series_name = getattr(self, '_series_name_for_fallback', None) or 'Unbekannte Serie'
                                    episodes.append({
                                        'title': title,
                                        'url': ep_url,
                                        'episode_number': i,
                                        'season_number': 1,  # Standard: Staffel 1
                                        'series': ep_series_name,
                                        'duration': dur_seconds,
                                        'duration_string': duration_str,
                                        'thumbnail': None,
                                        'id': ep_urn,
                                        'broadcast_date': parsed_date or '',
                                        'upload_date': (parsed_date or '').replace('-', ''),
                                    })
                                
                                if episodes:
                                    # Gruppiere nach Staffeln
                                    seasons = {}
                                    for episode in episodes:
                                        season_num = episode.get('season_number') or 1
                                        if season_num not in seasons:
                                            seasons[season_num] = []
                                        seasons[season_num].append(episode)
                                    
                                    # Sortiere Episoden innerhalb jeder Staffel
                                    for season_num in seasons:
                                        seasons[season_num].sort(key=lambda x: x.get('episode_number') or 0)
                                    
                                    sorted_seasons = dict(sorted(seasons.items()))
                                    
                                    # Verwende fallback_series_name, wenn series_name noch nicht definiert ist
                                    final_series_name = getattr(self, '_series_name_for_fallback', None) or 'Unbekannte Serie'
                                    return {
                                        'series_name': final_series_name,
                                        'seasons': sorted_seasons,
                                        'total_episodes': len(episodes)
                                    }
                    except Exception as e:
                        self.log(f"Fehler beim Webseiten-Parsing: {e}", "WARNING")
                        import traceback
                        self.log(f"Traceback: {traceback.format_exc()}", "DEBUG")
            
            if result.returncode == 0 or (result.returncode != 0 and has_unsupported_url_error and result.stdout and result.stdout.strip()):
                episodes = []
                series_name = None
                # Unter Windows/EXE kann yt-dlp teils auf stderr ausgeben – beide Streams auswerten
                # Aber bei ARD Sounds: stderr kann Fehlermeldungen über embed-URLs enthalten, die wir ignorieren können
                out_lines = []
                for stream in (result.stdout, result.stderr):
                    if stream and stream.strip():
                        for line in stream.strip().split('\n'):
                            if line.strip():
                                # Ignoriere Fehlermeldungen über nicht-normalisierte URLs in stderr (werden später normalisiert)
                                if 'unsupported url' in line.lower() and 'ardsounds.de/embed' in line.lower():
                                    continue
                                out_lines.append(line.strip())
                for line in (out_lines if out_lines else (result.stdout or '').strip().split('\n')):
                    if line:
                        try:
                            # Normalisiere ARD Sounds URLs in der JSON-Ausgabe von yt-dlp (falls vorhanden)
                            # yt-dlp kann URLs im Format ardsounds.de/embed/episode/... oder ardsounds.de/sendung/... zurückgeben
                            if 'ardsounds.de' in line.lower():
                                import re
                                # Ersetze ardsounds.de URLs in der JSON-Ausgabe
                                def normalize_url_in_json(match):
                                    url = match.group(1)  # URL ohne Anführungszeichen
                                    # Extrahiere URN
                                    urn_match = re.search(r'urn:ard:(?:episode|show):[^/\s"\'<>]+/?', url, re.IGNORECASE)
                                    if urn_match:
                                        urn = urn_match.group(0).rstrip('/')
                                        if 'urn:ard:episode:' in urn.lower():
                                            return f'"https://www.ardsounds.de/episode/{urn}"'
                                        elif 'urn:ard:show:' in urn.lower():
                                            return f'"https://www.ardsounds.de/sendung/{urn}"'
                                    return match.group(0)  # Original-URL mit Anführungszeichen
                                # Suche nach URLs in Anführungszeichen (verschiedene Formate)
                                # Format 1: ardsounds.de/embed/episode/...
                                line = re.sub(r'"https://www\.ardsounds\.de/embed/episode/[^"]*"', normalize_url_in_json, line)
                                # Format 2: ardsounds.de/embed/sendung/...
                                line = re.sub(r'"https://www\.ardsounds\.de/embed/sendung/[^"]*"', normalize_url_in_json, line)
                                # Format 3: ardsounds.de/sendung/.../urn:ard:show:...
                                line = re.sub(r'"https://www\.ardsounds\.de/sendung/[^"]*urn:ard:show:[^"]*"', normalize_url_in_json, line)
                                # Format 4: ardsounds.de/episode/.../urn:ard:episode:...
                                line = re.sub(r'"https://www\.ardsounds\.de/episode/[^"]*urn:ard:episode:[^"]*"', normalize_url_in_json, line)
                            info = json.loads(line)
                            # Einzelne Zeile kann ein Playlist-Objekt sein (z. B. ARD Audiothek ohne --flat-playlist)
                            items_to_process = []
                            if info.get('_type') == 'playlist' and info.get('entries'):
                                if not series_name:
                                    series_name = info.get('title') or info.get('series')
                                items_to_process = [e for e in info['entries'] if isinstance(e, dict)]
                            else:
                                items_to_process = [info]
                                # YouTube-Kanal: Serienname aus erstem Video (channel/uploader/playlist_title)
                                if is_youtube and series_name is None and items_to_process:
                                    first = items_to_process[0]
                                    series_name = first.get('playlist_title') or first.get('channel') or first.get('uploader') or first.get('uploader_id') or ''
                            
                            for info in items_to_process:
                                if not info:
                                    continue
                                # URL extrahieren - wichtig für spätere Downloads und Ordnererkennung (z. B. Ardaudiothek)
                                # Bei Audiothek: webpage_url (Seiten-URL) bevorzugen, damit Ordner "Ardaudiothek" erkannt wird
                                if 'ardaudiothek.de' in series_url or 'ardsounds.de' in series_url:
                                    episode_url = info.get('webpage_url') or info.get('url') or info.get('webpage_url_basename')
                                    # Normalisiere ARD Sounds URLs (können von yt-dlp als ardsounds.de/embed/episode/... zurückkommen)
                                    if episode_url:
                                        episode_url = self._normalize_ard_sounds_url(episode_url)
                                elif is_youtube and info.get('id'):
                                    # YouTube: Immer kanonische Watch-URL verwenden (nicht googlevideo.com-Stream-URL),
                                    # sonst gleicher Dateiname "videoplayback" und Überschreiben mehrerer Videos
                                    episode_url = f"https://www.youtube.com/watch?v={info.get('id')}"
                                else:
                                    episode_url = info.get('url') or info.get('webpage_url') or info.get('webpage_url_basename')
                                    # Normalisiere ARD Sounds URLs auch für andere Sender (falls vorhanden)
                                    if episode_url and 'ardsounds.de' in episode_url.lower():
                                        episode_url = self._normalize_ard_sounds_url(episode_url)
                                
                                # Falls keine vollständige URL, versuche sie zu konstruieren
                                if not episode_url or not episode_url.startswith('http'):
                                    # Versuche URL aus ID zu konstruieren
                                    episode_id = info.get('id')
                                    if episode_id:
                                        # Für YouTube: Konstruiere URL aus Video-ID
                                        if is_youtube:
                                            episode_url = f"https://www.youtube.com/watch?v={episode_id}"
                                        # Für ARD Mediathek / Audiothek: Konstruiere URL aus Original-URL
                                    elif 'ardmediathek.de' in series_url or 'ardaudiothek.de' in series_url:
                                        # Versuche Episode-URL aus ID zu konstruieren
                                        # ARD Episode-URLs haben das Format: https://www.ardmediathek.de/video/.../ID
                                        # Oder verwende die vollständige URL aus webpage_url wenn verfügbar
                                        if info.get('webpage_url'):
                                            episode_url = info.get('webpage_url')
                                            # Normalisiere ARD Sounds URLs (können von yt-dlp als ardsounds.de/embed/episode/... zurückkommen)
                                            if episode_url and 'ardsounds.de' in episode_url.lower():
                                                episode_url = self._normalize_ard_sounds_url(episode_url)
                                        elif ('ardaudiothek.de' in series_url or 'ardsounds.de' in series_url) and episode_id:
                                            # ARD Sounds: Episode-URL aus ID/URN bauen (z. B. urn:ard:episode:xxx)
                                            u = (episode_id if isinstance(episode_id, str) else str(episode_id)).strip().lstrip('/')
                                            episode_url = f"https://www.ardsounds.de/episode/{u}"
                                        else:
                                            # Fallback: Verwende Serien-URL, yt-dlp wird die richtige Episode finden
                                            episode_url = series_url
                                        # ARD Sounds: URN/relative URL zu vollständiger URL machen
                                        if ('ardaudiothek.de' in series_url or 'ardsounds.de' in series_url) and episode_url and not episode_url.startswith('http'):
                                            u = episode_url.strip().lstrip('/')
                                            episode_url = f"https://www.ardsounds.de/episode/{u}"
                                        # Normalisiere ARD Sounds URLs auch hier (falls noch nicht normalisiert)
                                        if episode_url and ('ardsounds.de' in episode_url.lower() or 'ardaudiothek.de' in episode_url.lower()):
                                            episode_url = self._normalize_ard_sounds_url(episode_url)
                                        if not episode_url or not episode_url.startswith('http'):
                                            episode_url = series_url  # Fallback: Serien-URL
                                    else:
                                        episode_url = series_url  # Fallback: Serien-URL
                                
                                # Extrahiere Titel (bei Audiothek ohne flat-playlist sind Titel in den Metadaten)
                                title = info.get('title') or info.get('fulltitle') or ''
                                if not title or (isinstance(title, str) and title.startswith('urn:ard:episode:')):
                                    n = info.get('episode_number') or info.get('playlist_index')
                                    title = f"Folge {n}" if n is not None else (info.get('id') or 'Unbekannt')
                                
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
                                    # Für andere Sender / Audiothek: Serienname aus Metadaten oder Show
                                    series = info.get('series') or info.get('show') or info.get('playlist')
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
                                date_iso = self._broadcast_date_from_info(info)
                                if date_iso:
                                    episode_info['broadcast_date'] = date_iso
                                    episode_info['upload_date'] = date_iso.replace('-', '')
                                
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
                                        # ARD Audiothek: Serienname aus URL-Pfad /sendung/SLUG/ extrahieren
                                        if not series_name and 'ardaudiothek.de' in series_url:
                                            import re
                                            match = re.search(r'ardaudiothek\.de/sendung/([^/]+)/', series_url, re.IGNORECASE)
                                            if match:
                                                slug = match.group(1)
                                                series_name = slug.replace('-', ' ').title()
                                                if not episode_info.get('series'):
                                                    episode_info['series'] = series_name
                        except json.JSONDecodeError as e:
                            self.log(f"JSON-Fehler beim Parsen einer Episode: {e}", "WARNING")
                            continue
                        except Exception as e:
                            self.log(f"Fehler beim Verarbeiten einer Episode: {e}", "WARNING")
                            continue
                
                if episodes:
                    # ARD Audiothek: Serienname aus URL setzen, falls noch nicht aus Metadaten
                    if not series_name and 'ardaudiothek.de' in series_url:
                        import re
                        match = re.search(r'ardaudiothek\.de/sendung/([^/]+)/', series_url, re.IGNORECASE)
                        if match:
                            series_name = match.group(1).replace('-', ' ').title()
                            for ep in episodes:
                                if not ep.get('series'):
                                    ep['series'] = series_name
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
                    
                    # Für YouTube: Playlist-Namen setzen und in alle Episoden übernehmen (ein Ordner für die ganze Playlist)
                    if is_youtube:
                        playlist_name = series_name or info.get('playlist', 'Unbekannte Playlist') if episodes else 'Unbekannte Playlist'
                        if not series_name and episodes:
                            first_video = episodes[0]
                            playlist_name = first_video.get('series') or first_video.get('playlist', 'Unbekannte Playlist')
                        series_name = playlist_name
                        for ep in episodes:
                            if not ep.get('series'):
                                ep['series'] = series_name
                    
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
            
            kwargs = {
                'capture_output': True,
                'text': True,
                'timeout': 30
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **kwargs)
            
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

    @staticmethod
    def _is_audiothek_or_sounds_url(url: str) -> bool:
        u = (url or '').lower()
        return 'ardaudiothek.de' in u or 'ardsounds.de' in u

    def _normalize_broadcast_date(self, value) -> str:
        """
        Normalisiert Sende-/Veröffentlichungsdatum zu YYYY-MM-DD (Kalendertag Europe/Berlin).
        Wichtig: yt-dlp-upload_date/timestamp sind oft UTC und liegen einen Tag vor dem
        auf ARD Sounds angezeigten Erscheinungsdatum.
        """
        if value is None or value == '':
            return ''
        try:
            from zoneinfo import ZoneInfo
            berlin = ZoneInfo('Europe/Berlin')
        except Exception:
            berlin = None

        if isinstance(value, datetime):
            try:
                if value.tzinfo is not None and berlin is not None:
                    return value.astimezone(berlin).strftime('%Y-%m-%d')
                return value.strftime('%Y-%m-%d')
            except Exception:
                return value.strftime('%Y-%m-%d')

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                ts = float(value)
                if ts > 1e12:
                    ts /= 1000.0
                if ts > 1e9:
                    if berlin is not None:
                        return datetime.fromtimestamp(ts, tz=berlin).strftime('%Y-%m-%d')
                    return datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
            except (OSError, OverflowError, ValueError):
                return ''
            return ''

        s = str(value).strip()
        if not s:
            return ''

        # Deutsches Datum TT.MM.JJJJ (wie auf ARD Sounds „Erscheinungsdatum“)
        m = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(20\d{2})', s)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return f'{year:04d}-{month:02d}-{day:02d}'

        # ISO mit Zeitzone → Kalendertag in Europe/Berlin
        if 'T' in s or s.endswith('Z') or re.search(r'[+-]\d{2}:\d{2}$', s):
            try:
                iso = s.replace('Z', '+00:00')
                # Python <3.11: fromisoformat braucht ggf. Anpassungen bei Mikrosekunden
                if re.match(r'.*[+-]\d{4}$', iso) and iso[-5] != ':':
                    iso = iso[:-2] + ':' + iso[-2:]
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is not None and berlin is not None:
                    return dt.astimezone(berlin).strftime('%Y-%m-%d')
                if dt.tzinfo is not None:
                    # Fallback: Datum laut Offset der Quelle (nicht UTC-Mitternacht)
                    return dt.strftime('%Y-%m-%d')
                return dt.strftime('%Y-%m-%d')
            except Exception:
                m = re.match(r'(20\d{2})-(\d{2})-(\d{2})', s)
                if m:
                    return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

        # Reines ISO-Datum
        m = re.fullmatch(r'(20\d{2})-(\d{2})-(\d{2})', s)
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

        # yt-dlp YYYYMMDD – oft UTC; ohne bessere Quelle trotzdem übernehmen
        if re.fullmatch(r'\d{8}', s):
            return f'{s[:4]}-{s[4:6]}-{s[6:8]}'

        m = re.match(r'(20\d{2})-(\d{2})-(\d{2})', s)
        if m:
            return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
        return ''

    def _broadcast_date_from_info(self, info: Optional[Dict]) -> str:
        """Liest das Sendedatum aus API-, HTML- oder yt-dlp-Metadaten (Bevorzugt ARD-Lokaldatum)."""
        if not isinstance(info, dict):
            return ''
        # Reihenfolge: zuerst explizite/ lokale ARD-Felder, yt-dlp-UTC erst ganz am Ende
        keys = (
            'broadcast_date', 'sendedatum', 'datum', 'erscheinungsdatum',
            'publicationStartDateAndTime', 'publishDate', 'publicationDate',
            'publicationStartDate', 'firstPublicationDate', 'broadcastedOn',
            'broadcastDate', 'availableFrom', 'datePublished', 'uploadDate',
            'release_date',
            # yt-dlp: timestamp oft korrekt mit TZ umrechenbar, upload_date oft schon UTC-Tag
            'release_timestamp', 'timestamp',
            'upload_date',
        )
        for key in keys:
            if key not in info or info.get(key) in (None, ''):
                continue
            iso = self._normalize_broadcast_date(info.get(key))
            if iso:
                return iso
        return ''

    def _filename_date_context(self, video_info: Optional[Dict]) -> Dict[str, str]:
        iso = self._broadcast_date_from_info(video_info)
        de = ''
        if iso and len(iso) == 10:
            de = f'{iso[8:10]}.{iso[5:7]}.{iso[:4]}'
        return {
            'date': iso,
            'datum': iso,
            'sendedatum': iso,
            'date_de': de,
            'datum_de': de,
        }

    def _with_filename_aliases(self, context: Dict) -> Dict:
        ctx = dict(context)
        ctx.setdefault('staffel', ctx.get('season'))
        ctx.setdefault('staffel2', ctx.get('season2'))
        ctx.setdefault('folge', ctx.get('episode'))
        ctx.setdefault('folge2', ctx.get('episode2'))
        ctx.setdefault('name', ctx.get('title'))
        ctx.setdefault('date', '')
        ctx.setdefault('datum', ctx.get('date', ''))
        ctx.setdefault('sendedatum', ctx.get('date', ''))
        ctx.setdefault('date_de', '')
        ctx.setdefault('datum_de', ctx.get('date_de', ''))
        return ctx

    def _apply_filename_template(self, template: str, context: Dict) -> str:
        """Wendet das Dateinamen-Template an; leere Platzhalter (z. B. fehlendes Datum) werden sauber entfernt."""
        ctx = self._with_filename_aliases(context)
        try:
            name_raw = template.format(**ctx)
        except Exception:
            name_raw = str(ctx.get('title') or 'video')
        name_raw = re.sub(r'(\s*[-–—_]\s*){2,}', r'\1', name_raw)
        name_raw = re.sub(r'^[\s\-–—_]+', '', name_raw)
        name_raw = re.sub(r'[\s\-–—_]+$', '', name_raw)
        name_raw = re.sub(r'\s{2,}', ' ', name_raw).strip()
        return self.sanitize_filename(name_raw)
    
    def _get_description_basename(self, video_info: Optional[Dict], is_series: bool = False,
                                   series_name: Optional[str] = None, season_number: Optional[int] = None,
                                   url: str = '', playlist_index: Optional[int] = None) -> str:
        """Liefert den gleichen Basisnamen (ohne Endung) wie die Video-Datei für die Info.txt."""
        if not video_info:
            return "Info"
        title_val = video_info.get('title', 'video')
        if is_series and (video_info.get('series') or video_info.get('season_number') or series_name or season_number is not None or playlist_index is not None):
            season_num_val = season_number if season_number is not None else video_info.get('season_number') or 1
            series_name_val = series_name or video_info.get('series', '')
            episode_num_val = playlist_index if playlist_index is not None else video_info.get('playlist_index') or video_info.get('episode_number')
            if not episode_num_val:
                m = re.search(r'[Ee](\d{1,2})', title_val)
                if m:
                    try:
                        episode_num_val = int(m.group(1))
                    except Exception:
                        episode_num_val = None
            context = {
                'series': series_name_val or '',
                'season': season_num_val or 0,
                'season2': f"{int(season_num_val):02d}" if season_num_val else '',
                'episode': episode_num_val or 0,
                'episode2': f"{int(episode_num_val):02d}" if episode_num_val else '',
                'title': title_val,
            }
            context.update(self._filename_date_context(video_info))
            template = 'E{episode2} - {title}'
            if self.gui_instance and hasattr(self.gui_instance, 'settings'):
                s = getattr(self.gui_instance, 'settings', {})
                if self._is_audiothek_or_sounds_url(url):
                    template = s.get('audiothek_filename_template', template)
                elif playlist_index is not None and url and ('youtube.com' in url.lower() or 'youtu.be' in url.lower()):
                    template = '{episode2} - {title}'
                else:
                    template = s.get('series_filename_template', template)
        else:
            context = {
                'series': '', 'season': 0, 'season2': '', 'episode': 0, 'episode2': '',
                'title': title_val,
            }
            context.update(self._filename_date_context(video_info))
            template = '{title}'
            if self.gui_instance and hasattr(self.gui_instance, 'settings'):
                s = getattr(self.gui_instance, 'settings', {})
                if self._is_audiothek_or_sounds_url(url):
                    template = s.get('audiothek_filename_template', template)
                else:
                    template = s.get('movie_filename_template', template)
        try:
            name = self._apply_filename_template(template, context)
            return name if name else "Info"
        except Exception:
            return self.sanitize_filename(title_val) or "Info"
    
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
        # Audiothek: URL ggf. aus video_info (wichtig beim Aufruf aus Musik-Tab mit ep_url)
        _check_url = (url or '') + ((' ' + (video_info.get('webpage_url') or video_info.get('original_url') or '')) if video_info else '')
        
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
            # Audiothek: Serienname ggf. aus URL ableiten (z. B. /sendung/.../urn:ard:show:...)
            if not series_name and url and 'ardaudiothek.de' in url.lower() and (video_info.get('series') or video_info.get('season_number') is not None):
                match = re.search(r'ardaudiothek\.de/sendung/([^/]+)/', url, re.IGNORECASE)
                if match:
                    series_name = match.group(1).replace('-', ' ').title()
                    is_series = True
        
        # Oberordner: bei Audiothek/Sounds immer "Ardaudiothek", bei YouTube "YouTube", sonst Sender (z. B. ARD)
        top_folder = None
        if url and self._is_audiothek_or_sounds_url(url):
            top_folder = "Ardaudiothek"
        elif video_info and (
            self._is_audiothek_or_sounds_url(_check_url or '')
            or self._is_audiothek_or_sounds_url(video_info.get('webpage_url') or '')
        ):
            top_folder = "Ardaudiothek"
        elif sender:
            top_folder = "YouTube" if sender == "YOUTUBE" else sender
        # Fallback: Queue-Eintrag mit direkter googlevideo.com-URL (sollte nicht mehr vorkommen – wir speichern jetzt youtube.com/watch?v=ID)
        elif is_series and series_name and ('googlevideo.com' in (_check_url or '').lower() or 'source=youtube' in (_check_url or '').lower()):
            top_folder = "YouTube"
        
        # Audiothek-Serie: wenn is_series und Serien-Infos, aber top_folder noch nicht gesetzt (z. B. relative URL oder URN)
        if not top_folder and is_series and (series_name or (video_info and video_info.get('series'))):
            combined = (url or '') + ' ' + (video_info.get('webpage_url') or video_info.get('url') or '') if video_info else (url or '')
            combined_lower = combined.lower()
            if ('ardaudiothek.de' in combined_lower or 'ardsounds.de' in combined_lower
                    or 'urn:ard:episode' in combined or 'urn:ard:show' in combined or
                    ('/episode/' in (url or '') and 'urn:ard' in (url or ''))):
                top_folder = "Ardaudiothek"
        
        self.log(f"DEBUG: is_series={is_series}, series_name={series_name}, season_number={season_number}, sender={sender}, top_folder={top_folder}")
        
        # Audiothek: Serienname fehlt ggf. – aus URL oder video_info holen
        if is_series and top_folder == "Ardaudiothek" and not series_name and (url or video_info):
            series_name = (video_info or {}).get('series')
            if not series_name and url:
                match = re.search(r'ardaudiothek\.de/sendung/([^/]+)/', (url or ''), re.IGNORECASE)
                if match:
                    series_name = match.group(1).replace('-', ' ').title()
            if not series_name:
                series_name = "Audiothek-Serie"
        
        if is_series and series_name:
            # Serie: z. B. Ardaudiothek/Serienname/Staffel X/ oder ARD/Serienname/Staffel X/
            # YouTube-Playlists: nur YouTube/Playlistname/ (keine Staffel – Playlists haben keine Staffeln)
            series_name_clean = self.sanitize_filename(series_name)
            if top_folder:
                series_path = output_dir / top_folder / series_name_clean
            else:
                series_path = output_dir / series_name_clean

            is_youtube_playlist = ('youtube.com' in (_check_url or '').lower() or 'youtu.be' in (_check_url or '').lower() or
                                  (top_folder == "YouTube" and is_series))
            if not is_youtube_playlist:
                # Staffel-Ordner für echte Serien (ARD, ZDF, …), nicht für YouTube-Playlists
                if season_number is not None:
                    series_path = series_path / f"Staffel {season_number}"
                else:
                    series_path = series_path / "Staffel 1"
            # Bei YouTube: series_path bleibt YouTube/Playlistname/

            series_path.mkdir(parents=True, exist_ok=True)
            self.log(f"DEBUG: Serie-Pfad erstellt: {series_path}")
            return series_path
        elif video_info and (video_info.get('series') or video_info.get('season_number') is not None):
            # Einzelne Episode einer Serie (Fallback)
            series_name = video_info.get('series')
            season_num = video_info.get('season_number')
            is_youtube_playlist = ('youtube.com' in (_check_url or '').lower() or 'youtu.be' in (_check_url or '').lower() or
                                  (top_folder == "YouTube" and is_series))

            if series_name:
                series_name_clean = self.sanitize_filename(series_name)
                if top_folder:
                    series_path = output_dir / top_folder / series_name_clean
                else:
                    series_path = output_dir / series_name_clean

                if not is_youtube_playlist:
                    if season_num is not None:
                        series_path = series_path / f"Staffel {season_num}"
                    else:
                        series_path = series_path / "Staffel 1"

                series_path.mkdir(parents=True, exist_ok=True)
                self.log(f"DEBUG: Episode-Pfad erstellt: {series_path}")
                return series_path
        
        # Film oder einzelnes Video
        if top_folder:
            # z. B. Ardaudiothek/Filmname/ oder ARD/Filmname/
            film_title = None
            if video_info:
                # Versuche Filmtitel zu extrahieren
                film_title = video_info.get('title') or video_info.get('fulltitle')
                if film_title:
                    # Bereinige Filmtitel für Ordner
                    film_title = self.sanitize_filename(film_title)
            
            if film_title:
                film_path = output_dir / top_folder / film_title
            else:
                film_path = output_dir / top_folder
            film_path.mkdir(parents=True, exist_ok=True)
            self.log(f"DEBUG: Film-Pfad erstellt: {film_path}")
            return film_path
        else:
            # Video/ (Standard)
            self.log(f"DEBUG: Standard-Pfad verwendet: {output_dir}")
            return output_dir
    
    def check_existing_file(self, video_info: Optional[Dict], output_dir: Path,
                            output_format: str, is_series: bool = False,
                            series_name: Optional[str] = None, season_number: Optional[int] = None,
                            url: str = '') -> tuple:
        """
        Prüft ob bereits eine Datei zu diesem Video existiert.
        Returns: (exists: bool, existing_path: Optional[Path], same_format: bool)
        same_format = True wenn vorhandene Datei das gleiche Format (Extension) hat wie output_format.
        """
        output_dir = Path(output_dir).resolve()
        actual_output_dir = self._get_output_path(video_info, output_dir, is_series, series_name, season_number, url)
        existing_path = None
        if not video_info:
            return False, None, False
        title = video_info.get('title', 'video')
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        if output_format == 'mp3':
            expected = actual_output_dir / f"{safe_title}.mp3"
        else:
            expected = actual_output_dir / f"{safe_title}.{output_format}"
        if expected.exists():
            existing_path = expected
            same = (output_format == 'mp3' and existing_path.suffix.lower() == '.mp3') or (existing_path.suffix.lower() == f'.{output_format.lower()}')
            return True, existing_path, same
        # Suche nach Datei mit gleichem Stammnamen (anderes Format)
        for ext in ('.mp4', '.webm', '.mkv', '.avi', '.mp3', '.m4a'):
            candidate = actual_output_dir / f"{safe_title}{ext}"
            if candidate.exists():
                existing_path = candidate
                same = (output_format == 'mp3' and ext == '.mp3') or (ext == f'.{output_format}')
                return True, existing_path, same
        # Suche nach ähnlichem Namen
        for f in actual_output_dir.iterdir():
            if not f.is_file():
                continue
            if f.suffix.lower() in ('.mp4', '.webm', '.mkv', '.avi', '.mp3', '.m4a'):
                if safe_title.lower() in f.stem.lower() or f.stem.lower() in safe_title.lower():
                    existing_path = f
                    same = (output_format == 'mp3' and f.suffix.lower() == '.mp3') or (f.suffix.lower() == f'.{output_format}')
                    return True, existing_path, same
        return False, None, False
    
    def convert_existing_to_format(self, existing_path: Path, target_format: str,
                                   progress_callback: Optional[Callable[[float, str], None]] = None) -> Tuple[bool, Optional[Path], str]:
        """
        Konvertiert eine vorhandene Video/Audio-Datei ins Zielformat (z. B. mp4, mp3).
        Returns: (success, new_path, error_message)
        """
        existing_path = Path(existing_path).resolve()
        if not existing_path.is_file():
            return False, None, "Datei nicht gefunden"
        target_format = target_format.lower().strip()
        if target_format == 'mp3':
            out_path = existing_path.with_suffix('.mp3')
            # Audio-Extraktion
            try:
                import subprocess as sp
                ffmpeg_cmd = ['ffmpeg', '-y', '-i', str(existing_path), '-vn', '-acodec', 'libmp3lame', '-q:a', '0', str(out_path)]
                if platform.system() == 'Windows':
                    proc = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True, creationflags=getattr(sp, 'CREATE_NO_WINDOW', 0))
                else:
                    proc = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True)
                for line in proc.stdout:
                    if progress_callback and 'time=' in line:
                        m = re.search(r'time=(\d+):(\d+):(\d+)', line)
                        if m:
                            try:
                                t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                                progress_callback(min(100, t / 30), f"Konvertierung: {t}s")
                            except Exception:
                                pass
                proc.wait()
                if proc.returncode == 0 and out_path.exists():
                    return True, out_path, ""
                return False, None, "FFmpeg Fehler bei MP3-Konvertierung"
            except Exception as e:
                return False, None, str(e)
        # Video: umkodieren nach target_format (mp4, webm, etc.)
        out_path = existing_path.with_suffix(f'.{target_format}')
        try:
            import subprocess as sp
            ffmpeg_cmd = ['ffmpeg', '-y', '-i', str(existing_path), '-c:v', 'libx264', '-c:a', 'aac', str(out_path)]
            if platform.system() == 'Windows':
                proc = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True, creationflags=getattr(sp, 'CREATE_NO_WINDOW', 0))
            else:
                proc = sp.Popen(ffmpeg_cmd, stdout=sp.PIPE, stderr=sp.STDOUT, text=True)
            for line in proc.stdout:
                if progress_callback and 'time=' in line:
                    m = re.search(r'time=(\d+):(\d+):(\d+)', line)
                    if m:
                        try:
                            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
                            progress_callback(min(100, t / 30), f"Konvertierung: {t}s")
                        except Exception:
                            pass
            proc.wait()
            if proc.returncode == 0 and out_path.exists():
                return True, out_path, ""
            return False, None, "FFmpeg Fehler bei Video-Konvertierung"
        except Exception as e:
            return False, None, str(e)
    
    def download_video(self, url: str, output_dir: Optional[Path] = None, 
                      quality: Optional[str] = None, 
                      output_format: Optional[str] = None,
                      download_playlist: bool = False,
                      progress_callback: Optional[callable] = None,
                      video_info: Optional[Dict] = None,
                      is_series: bool = False,
                      series_name: Optional[str] = None,
                      season_number: Optional[int] = None,
                      playlist_index: Optional[int] = None,
                      download_subtitles: bool = False,
                      subtitle_language: str = "de",
                      download_description: bool = False,
                      download_thumbnail: bool = False,
                      resume_download: bool = True,
                      speed_limit: Optional[float] = None,
                      embed_metadata: bool = False,
                      gui_instance: Optional[object] = None,
                      gpu_enabled: bool = False,
                      gpu_vendor: str = 'auto',
                      force_redownload: bool = False,
                      cookies_from_browser: Optional[str] = None) -> Tuple[bool, Optional[Path], str]:
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
        # Normalisiere ARD Sounds URLs zuerst (konvertiert zu ARD Audiothek-Format für bessere yt-dlp-Unterstützung)
        original_url = url
        url = self._normalize_ard_sounds_url(url)
        if url != original_url:
            self.log(f"URL normalisiert in download_video: {original_url} → {url}")
        
        if output_dir is None:
            output_dir = self.download_path
        output_dir = Path(output_dir)
        try:
            output_dir = output_dir.resolve()  # absolut (wichtig bei Start z. B. über start_launcher.sh)
        except Exception:
            pass
        
        # Hole Video-Info falls nicht vorhanden (bei Audiothek/Sounds immer mit check_series für Serien-/Folgen-Metadaten)
        if video_info is None:
            check_series_audiothek = 'ardaudiothek.de' in url.lower() or 'ardsounds.de' in url.lower()
            video_info = self.get_video_info(url, check_series=(is_series or check_series_audiothek))
        
        # ARD Sounds (Einzelfolge): yt-dlp leitet oft auf /embed/episode/… und scheitert mit „Unsupported URL“.
        # Wenn Metadaten vom Serien-Dialog kommen, wurde get_video_info übersprungen – dann fehlt die direkte Media-URL.
        _u_low = (url or '').lower()
        if _u_low and ('ardsounds.de' in _u_low or 'ardaudiothek.de' in _u_low) and '/episode/' in _u_low and (
            'urn:ard:episode' in _u_low or 'urn:ard:section' in _u_low
        ):
            mu = (video_info or {}).get('url') or ''
            has_direct_media = (
                mu.startswith('http')
                and (mu.endswith('.mp3') or mu.endswith('.m4a') or '/clips/' in mu or 'akamaihd' in mu)
            )
            if not has_direct_media:
                try:
                    parsed = self._get_video_info_from_html(url)
                    if parsed and parsed.get('url') and str(parsed['url']).startswith('http'):
                        merged = {**(video_info or {}), **parsed}
                        # Metadaten aus GUI/Serien-Dialog haben Vorrage
                        if video_info:
                            for k in ('title', 'series', 'season_number', 'episode_number', 'thumbnail', 'broadcast_date', 'upload_date'):
                                if video_info.get(k) is not None:
                                    merged[k] = video_info[k]
                        video_info = merged
                        self.log("ARD Sounds: direkte Media-URL für Download aus HTML übernommen")
                except Exception as e:
                    self.log(f"ARD Sounds: Konnte Media-URL aus HTML nicht ermitteln: {e}", "WARNING")
        
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
        # Immer absoluten Pfad verwenden (wichtig bei Start über Verknüpfung/start_launcher.sh)
        try:
            actual_output_dir = actual_output_dir.resolve()
        except Exception:
            pass
        
        # Zielordner anlegen (wichtig bei Start über System-Verknüpfung – Ordner existiert sonst ggf. nicht)
        try:
            actual_output_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.log(f"⚠ Konnte Zielordner nicht anlegen: {actual_output_dir} – {e}", "WARNING")
        
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
                            desc_basename = self._get_description_basename(video_info, is_series, series_name, season_number, url, playlist_index=playlist_index)
                            description_path = actual_output_dir / f"{desc_basename}.txt"
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
                    _thumb_u = (url or '').lower()
                    if 'ardaudiothek.de' in _thumb_u or 'ardsounds.de' in _thumb_u:
                        cmd.extend(['--legacy-server-connect', '--no-check-certificate', '--prefer-insecure'])
                    cmd.append(url)
                    
                    self.log(f"Lade Thumbnail herunter...")
                    kwargs = {
                        'cwd': str(actual_output_dir),
                        'stdout': subprocess.PIPE,
                        'stderr': subprocess.STDOUT,
                        'text': True
                    }
                    if platform.system() == 'Windows':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    process = subprocess.run(cmd, **kwargs)
                    
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
            
            # Wenn Datei existiert und nur zusätzliche Downloads gewünscht sind (nicht bei explizitem "Erneut herunterladen")
            # Bei Kanal-/Playlist-URL nicht: Dann ist "einzelnes Video" nur Zufall (erstes Video), sonst würden nur Covers geladen.
            url_lower = (url or '').lower()
            is_channel_or_playlist_url = '/channel/' in url_lower or '/@' in url_lower or 'list=' in url_lower or '/playlist' in url_lower
            if video_file_exists and (download_description or download_thumbnail) and not force_redownload and not is_channel_or_playlist_url:
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
                            desc_basename = self._get_description_basename(video_info, is_series, series_name, season_number, url, playlist_index=playlist_index)
                            description_path = actual_output_dir / f"{desc_basename}.txt"
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
                    _thumb_u2 = (url or '').lower()
                    if 'ardaudiothek.de' in _thumb_u2 or 'ardsounds.de' in _thumb_u2:
                        cmd.extend(['--legacy-server-connect', '--no-check-certificate', '--prefer-insecure'])
                    cmd.append(url)
                    
                    self.log(f"Lade Thumbnail herunter...")
                    kwargs = {
                        'cwd': str(actual_output_dir),
                        'stdout': subprocess.PIPE,
                        'stderr': subprocess.STDOUT,
                        'text': True
                    }
                    if platform.system() == 'Windows':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    process = subprocess.run(cmd, **kwargs)
                    
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
            
            # Prüfe ffmpeg-Pfad und füge --ffmpeg-location hinzu falls nötig
            try:
                import subprocess as sp
                import platform as plat
                # Prüfe ob ffmpeg im PATH ist
                ffmpeg_in_path = False
                try:
                    result = sp.run(['ffmpeg', '-version'], capture_output=True, timeout=2, check=True)
                    ffmpeg_in_path = True
                except (sp.TimeoutExpired, sp.CalledProcessError, FileNotFoundError):
                    pass
                
                # Wenn ffmpeg nicht im PATH ist, prüfe lokale Installation
                if not ffmpeg_in_path:
                    try:
                        from auto_install_dependencies import get_app_dir
                        app_dir = get_app_dir()
                        if plat.system() == 'Windows':
                            ffmpeg_exe = app_dir / "ffmpeg" / "bin" / "ffmpeg.exe"
                            ffmpeg_bin = app_dir / "ffmpeg" / "bin"
                        else:
                            ffmpeg_exe = app_dir / "ffmpeg" / "bin" / "ffmpeg"
                            ffmpeg_bin = app_dir / "ffmpeg" / "bin"
                        
                        if ffmpeg_exe.exists() or ffmpeg_bin.exists():
                            # Verwende das bin-Verzeichnis als ffmpeg-location
                            yt_args.extend(['--ffmpeg-location', str(ffmpeg_bin)])
                            self.log(f"Verwende lokales ffmpeg: {ffmpeg_bin}")
                    except Exception as e:
                        self.log(f"Konnte ffmpeg-Pfad nicht ermitteln: {e}", "WARNING")
            except Exception as e:
                self.log(f"Fehler beim Prüfen von ffmpeg: {e}", "WARNING")
            
            # Füge Cookies hinzu falls vorhanden
            if cookies_file:
                yt_args.extend(['--cookies', cookies_file])
            # YouTube/YouTube Music: nur falls kein Account hinterlegt – Cookies aus Browser (z. B. Radio/Mix-Playlists)
            if cookies_from_browser and not cookies_file and ('music.youtube.com' in url.lower() or 'youtube.com' in url.lower()):
                yt_args.extend(['--cookies-from-browser', cookies_from_browser])
                self.log(f"YouTube: Cookies aus Browser „{cookies_from_browser}“ werden verwendet.")
            
            # Spezielle Optionen für ARD Plus
            if service == 'ARD Plus':
                # User-Agent für ARD Plus
                yt_args.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                # Referer setzen
                yt_args.extend(['--add-header', 'Referer:https://www.ardplus.de/'])
                # Versuche generic extractor zu erzwingen
                yt_args.extend(['--extractor-args', 'generic:no_check_certificate'])
                self.log("ARD Plus spezielle Optionen hinzugefügt")
            
            # Optionen für ORF (on.orf.at – Altersverifikation mit Login)
            if service == 'ORF':
                yt_args.extend(['--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'])
                yt_args.extend(['--add-header', 'Referer:https://tvthek.orf.at/'])
                self.log("ORF (on.orf.at) Account/Cookies verwendet")
            # ORF/on.orf.at: SSL "record layer failure" umgehen (z. B. TLS-Kompatibilität mit dem Server)
            url_lower = url.lower()
            if 'orf.at' in url_lower:
                yt_args.append('--no-check-certificate')
                self.log("ORF: SSL-Zertifikatsprüfung deaktiviert (Workaround für Verbindungsfehler)")
            # ZDF: SSL WRONG_VERSION_NUMBER umgehen (z. B. bei zdf:channel oder ZDF-Serien)
            if service == 'zdf' or 'zdf.de' in url_lower or 'zdfmediathek' in url_lower:
                yt_args.append('--legacy-server-connect')
                yt_args.append('--no-check-certificate')
                self.log("ZDF: SSL-Workaround aktiv (legacy-server-connect, no-check-certificate)")
            # ARD Audiothek / ARD Sounds: SSL "record layer failure" umgehen; --prefer-insecure nutzt HTTP wo möglich
            if 'ardaudiothek.de' in url_lower or 'ardsounds.de' in url_lower:
                yt_args.append('--legacy-server-connect')
                yt_args.append('--no-check-certificate')
                yt_args.append('--prefer-insecure')
                self.log("ARD Audiothek / ARD Sounds: SSL-Workaround aktiv (legacy-server-connect, no-check-certificate, prefer-insecure)")
            # YouTube: IPv4 erzwingen (oft stabiler; --impersonate chrome braucht Zusatz-Dependencies)
            if service == 'youtube' or 'youtube.com' in url_lower or 'youtu.be' in url_lower:
                yt_args.append('-4')
                self.log("YouTube: IPv4 erzwungen (-4)")
            
            # Ausgabeverzeichnis erzwingen (wichtig für ZDF/Linux: Ordner wird angelegt, Datei muss hier landen)
            # -P home:... setzt das Basis-Verzeichnis; -o dann relativ dazu → zuverlässiger als nur -o mit Pfad
            yt_args.extend(['-P', f'home:{actual_output_dir}'])
            self.log(f"yt-dlp Ausgabe-Verzeichnis (home): {actual_output_dir}")
            # Output-Template relativ zu "home"; bei Playlist/Serie mit Nummer: "E01 - Titel"
            use_index = is_series and playlist_index is not None
            if output_format == 'mp3':
                if use_index:
                    yt_args.extend(['-o', f'{playlist_index:02d} - %(title)s.%(ext)s'])
                else:
                    yt_args.extend(['-o', '%(title)s.%(ext)s'])
                yt_args.extend(['-x', '--audio-format', 'mp3', '--audio-quality', '0'])  # Beste Audio-Qualität
            else:
                if use_index:
                    yt_args.extend(['-o', f'{playlist_index:02d} - %(title)s.{output_format}'])
                else:
                    yt_args.extend(['-o', f'%(title)s.{output_format}'])
                yt_args.extend(['--recode-video', output_format])
                # GPU für Konvertierung (nur bei Video-Formaten)
                if gpu_enabled and gpu_vendor != 'none':
                    vendor = gpu_vendor if gpu_vendor != 'auto' else (
                        'apple' if sys.platform == 'darwin' else 'nvidia'  # auto: Apple auf Mac, sonst NVIDIA als häufigster Fall
                    )
                    pp_args = []
                    if vendor == 'nvidia':
                        pp_args = ['-c:v', 'h264_nvenc', '-c:a', 'copy']
                    elif vendor == 'amd':
                        pp_args = ['-c:v', 'h264_amf', '-c:a', 'copy'] if sys.platform == 'win32' else ['-c:v', 'h264_vaapi', '-c:a', 'copy']
                    elif vendor == 'apple':
                        # VideoToolbox (Apple Silicon / Mac GPU) – Qualitätsmodus statt nur Default-Bitrate
                        try:
                            from mac_platform import videotoolbox_encoder_args, find_ffmpeg, apple_chip_name
                            pp_args = videotoolbox_encoder_args(prefer_hevc=False)
                            ff = find_ffmpeg()
                            if ff:
                                yt_args.extend(['--ffmpeg-location', ff])
                            chip = apple_chip_name()
                            self.log(f"GPU-Konvertierung: VideoToolbox H.264 ({chip or 'Apple'})")
                        except Exception:
                            pp_args = ['-c:v', 'h264_videotoolbox', '-allow_sw', '1', '-b:v', '0', '-q:v', '65', '-c:a', 'copy']
                    if pp_args:
                        yt_args.extend(['--postprocessor-args', 'FFmpegVideoConvertor:' + ' '.join(pp_args)])
                        if vendor != 'apple':
                            self.log(f"GPU-Konvertierung aktiv: {vendor}")
                elif sys.platform == 'darwin':
                    # Auch ohne GPU: natives/ bevorzugtes ffmpeg setzen (Apple Silicon)
                    try:
                        from mac_platform import find_ffmpeg
                        ff = find_ffmpeg()
                        if ff:
                            yt_args.extend(['--ffmpeg-location', ff])
                    except Exception:
                        pass
            
            # Qualität/Format
            # Versuche, Audiodeskription (Audio Description) zu vermeiden, wenn möglich.
            # Wir filtern Formate, deren format_note typische AD-Begriffe enthält.
            # Falls dadurch keine Formate mehr übrig bleiben, fällt yt-dlp automatisch
            # auf den nachfolgenden Selector (ohne Filter) zurück.
            ad_filter = (
                '[format_note!*="audio description"]'
                '[format_note!*="Audio Description"]'
                '[format_note!*="Audiodeskription"]'
                '[format_note!*="audiodeskription"]'
            )
            if output_format == 'mp3':
                # Für MP3: Beste Audio-Qualität, bevorzugt ohne Audiodeskription
                yt_args.extend(['-f', f'bestaudio{ad_filter}/bestaudio/best'])
                self.log("Formatwahl: bevorzuge Audio ohne Audiodeskription (MP3)")
            elif quality == "best":
                # Beste Qualität, bevorzugt ohne Audiodeskription
                yt_args.extend(['-f', f'bestvideo{ad_filter}+bestaudio{ad_filter}/bestvideo+bestaudio/best'])
                self.log("Formatwahl: bevorzuge bestvideo+bestaudio ohne Audiodeskription")
            elif quality == "niedrigste" or quality == "worst":  # Unterstütze beide für Kompatibilität
                yt_args.extend(['-f', f'worstvideo{ad_filter}+worstaudio{ad_filter}/worstvideo+worstaudio/worst'])
                self.log("Formatwahl: niedrigste Qualität, möglichst ohne Audiodeskription")
            elif quality.endswith('p'):
                # Spezifische Auflösung (z.B. "720p", "1080p")
                resolution = quality[:-1]  # Entferne 'p'
                # Prüfe ob Auflösung gültig ist (1080, 720, etc.)
                try:
                    resolution_int = int(resolution)
                    if resolution_int > 0:
                        # Bevorzuge Audio ohne Audiodeskription bei gegebener Auflösung
                        yt_args.extend(['-f', f'bestvideo[height<={resolution_int}]{ad_filter}+bestaudio{ad_filter}/bestvideo[height<={resolution_int}]+bestaudio/best[height<={resolution_int}]'])
                        self.log(f"Formatwahl: max. {resolution_int}p, bevorzugt ohne Audiodeskription")
                    else:
                        # Fallback zu best bei ungültiger Auflösung
                        yt_args.extend(['-f', f'bestvideo{ad_filter}+bestaudio{ad_filter}/bestvideo+bestaudio/best'])
                        self.log("Formatwahl: ungültige Auflösung, Fallback bestvideo+bestaudio (ohne AD bevorzugt)")
                except ValueError:
                    # Fallback zu best bei ungültiger Auflösung
                    yt_args.extend(['-f', f'bestvideo{ad_filter}+bestaudio{ad_filter}/bestvideo+bestaudio/best'])
                    self.log("Formatwahl: ungültige Auflösung (ValueError), Fallback bestvideo+bestaudio (ohne AD bevorzugt)")
            else:
                # Fallback zu best, bevorzugt ohne Audiodeskription
                yt_args.extend(['-f', f'bestvideo{ad_filter}+bestaudio{ad_filter}/bestvideo+bestaudio/best'])
                self.log("Formatwahl: Fallback bestvideo+bestaudio (ohne AD bevorzugt)")
            
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
            
            # Bei "Erneut herunterladen": bestehende Datei überschreiben
            if force_redownload:
                yt_args.append('--force-overwrites')
            # Weitere Optionen: --print after_move gibt den endgültigen Dateipfad aus (zuverlässige Erkennung unter Linux/Mac)
            # Mehr Retries bei "Connection reset by peer" / Verbindungsabbrüchen (v. a. bei großen Dateien)
            yt_args.extend([
                '--retries', '20',
                '--fragment-retries', '20',
                '--no-warnings',
                '--progress',
                '--newline',
                '--print', 'after_move:filepath',
            ])
            # YouTube: Pause zwischen Anfragen, um Rate-Limit (403 / "rate-limited for up to an hour") zu vermeiden
            if url and ('youtube.com' in url.lower() or 'youtu.be' in url.lower()):
                yt_args.extend(['--sleep-interval', '2', '--max-sleep-interval', '5'])
            
            # Prüfe ob video_info eine direkte Media-URL enthält (z.B. von HTML-Parsing)
            # Wenn ja, verwende diese statt der Webseiten-URL (yt-dlp scheitert sonst an ardsounds.de/embed/…)
            download_url = url
            if video_info:
                media_url = video_info.get('url')
                if media_url and str(media_url).startswith('http'):
                    m = str(media_url).lower()
                    if media_url.endswith(('.mp3', '.m4a')) or '/clips/' in m or 'akamaihd' in m:
                        download_url = str(media_url)
                        self.log(f"Verwende direkte Media-URL: {download_url[:100]}...")
            
            # URL hinzufügen
            yt_args.append(download_url)
            
            self.log(f"Führe yt-dlp aus mit {len(yt_args)} Argumenten...")
            try:
                from yt_dlp_helper import get_ytdlp_command
                import shlex
                base = get_ytdlp_command() or ['yt-dlp']
                full_cmd = base + yt_args
                self.log(f"Befehl (zum Nachvollziehen): {' '.join(shlex.quote(str(a)) for a in full_cmd)}")
            except Exception:
                pass
            # Ungepufferte Ausgabe, damit --print after_move:filepath unter Linux ankommt
            run_env = os.environ.copy()
            run_env["PYTHONUNBUFFERED"] = "1"
            # Linux/macOS: pipx/User-yt-dlp finden, wenn App aus Desktop/Menü startet (dort oft kein ~/.local/bin im PATH)
            if sys.platform != 'win32':
                home_bin = os.path.join(os.environ.get('HOME', ''), '.local', 'bin')
                if home_bin and os.path.isdir(home_bin):
                    run_env["PATH"] = home_bin + os.pathsep + run_env.get("PATH", "")
            
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
                    cwd=str(actual_output_dir),
                    env=run_env
                )
                
                # Prüfe ob process ein Popen-Objekt ist (für Prozessüberwachung)
                if not hasattr(process, 'poll'):
                    # Fallback: Direkte API wurde verwendet (kein Prozessüberwachung möglich, z. B. Sandbox/kein Python)
                    self.log("WARNING: Prozessüberwachung nicht verfügbar in .exe Build", "WARNING")
                    result = process
                    if hasattr(result, 'returncode') and result.returncode != 0:
                        error_msg = f"Download fehlgeschlagen: {result.stderr}"
                        self.log(error_msg, "ERROR")
                        return (False, None, error_msg)
                    # Download war erfolgreich – Datei aus stdout oder Verzeichnis ermitteln
                    output_lines = (result.stdout or "").splitlines() + (result.stderr or "").splitlines()
                    downloaded_files = []
                    for line in output_lines:
                        line_stripped = line.strip().strip('"\'').split('\r')[-1].strip()
                        if line_stripped.endswith(('.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.avi')):
                            candidate = Path(line_stripped)
                            if not candidate.is_absolute():
                                candidate = (actual_output_dir / candidate).resolve()
                            if candidate.exists() and candidate.is_file():
                                downloaded_files.append(candidate)
                                break
                    if not downloaded_files and actual_output_dir.exists():
                        exts = [output_format] if output_format in ('mp4', 'mkv', 'webm', 'mp3', 'm4a', 'avi') else ['mp4', 'mkv', 'webm']
                        for ext in exts:
                            found = list(actual_output_dir.glob(f"*.{ext}")) + list(actual_output_dir.rglob(f"*.{ext}"))
                            found = [p for p in found if p.is_file() and not p.name.endswith('.part')]
                            if found:
                                found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                                downloaded_files = [found[0]]
                                break
                    if downloaded_files:
                        self.log(f"✓ Download erfolgreich: {downloaded_files[0].name}")
                        return (True, downloaded_files[0], "")
                    self.log("⚠ Download scheint erfolgreich, aber Datei nicht gefunden", "WARNING")
                    return (True, None, "Datei nicht gefunden")
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
                
                self._conversion_phase = False
                self._download_100_seen = False
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
                            # Konvertierungsphase erkennen
                            if not getattr(self, '_conversion_phase', False):
                                line_lower = line.lower()
                                is_merge_convert = (
                                    'merging' in line_lower or 'merger' in line_lower or
                                    'ffmpegvideoconvertor' in line_lower or 'extractaudio' in line_lower or
                                    'converting video' in line_lower or 'converting audio' in line_lower or
                                    ('destination:' in line_lower and ('webm' in line_lower or 'm4a' in line_lower))
                                )
                                # Fallback: Nach 100%-Download jede Zeile ohne Download-Fortschritt = Konvertierung
                                is_after_download = getattr(self, '_download_100_seen', False) and '[download]' not in line_lower and not re.search(r'\d+\.?\d*%\s+of\s+', line)
                                if is_merge_convert or is_after_download:
                                    self._conversion_phase = True
                                    if progress_callback:
                                        progress_callback(100, "Konvertierung läuft...")
                            # Merken, dass Download 100% erreicht hat (für Fallback-Erkennung Konvertierung)
                            if '%' in line and re.search(r'\[download\]\s+100\.?0?%', line, re.IGNORECASE):
                                self._download_100_seen = True
                            # FFmpeg-Fortschritt parsen (time=HH:MM:SS.xx)
                            if getattr(self, '_conversion_phase', False) and 'time=' in line and progress_callback and video_info:
                                time_match = re.search(r'time=(\d+):(\d+):(\d+)\.(\d+)', line)
                                if time_match:
                                    try:
                                        h, m, s, ms = int(time_match.group(1)), int(time_match.group(2)), int(time_match.group(3)), int(time_match.group(4))
                                        current_sec = h * 3600 + m * 60 + s + ms / 100.0
                                        duration_sec = float(video_info.get('duration') or 0)
                                        if duration_sec > 0 and current_sec <= duration_sec:
                                            pct = min(100.0, (current_sec / duration_sec) * 100.0)
                                            progress_callback(100, f"Konvertierung: {pct:.0f}%")
                                    except (ValueError, ZeroDivisionError):
                                        pass
                            # Parse Download-Fortschritt: yt-dlp-Prozent 1:1 anzeigen (0–100 %)
                            # Bei Video+Audio als zwei Streams kann der Balken kurz auf 0 % zurückspringen, läuft dann wieder durch.
                            if '%' in line and not getattr(self, '_conversion_phase', False):
                                match = re.search(r'(\d+\.?\d*)%', line)
                                if match and progress_callback:
                                    try:
                                        progress_percent = float(match.group(1))
                                        progress_callback(min(100.0, progress_percent), line)
                                    except ValueError:
                                        pass
                            
                            if '%' in line or 'ETA' in line or 'Downloading' in line or 'Merging' in line or 'time=' in line:
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
                # UI vor Abschluss auf 100 % setzen (damit Fortschritt nicht bei 50 % stehen bleibt)
                if progress_callback:
                    self.log("[DEBUG] Sende Progress 100 % an UI vor Dateisuche")
                    progress_callback(100, "Fertig")
                # Suche nach heruntergeladener Datei
                # 1) Zeile von --print after_move:filepath (zuverlässig unter Linux/Mac)
                downloaded_files = []
                for line in output_lines:
                    line_stripped = line.strip().strip('"\'')
                    # after_move:filepath gibt den Pfad oft allein oder mit Präfix aus (evtl. mit \r unter Linux)
                    line_stripped = line_stripped.split('\r')[-1].strip()
                    if line_stripped.endswith(('.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.avi')):
                        candidate = Path(line_stripped)
                        if not candidate.is_absolute():
                            candidate = (actual_output_dir / candidate).resolve()
                        if candidate.exists() and candidate.is_file():
                            downloaded_files.append(candidate)
                            break
                    # Zeile kann Pfad enthalten (z. B. "…/Datei.mp4") – letzten pfadähnlichen Teil prüfen
                    for ext in ('.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.avi'):
                        if ext in line_stripped:
                            idx = line_stripped.rfind(ext) + len(ext)
                            path_str = line_stripped[:idx].strip().strip('"\'')
                            if path_str:
                                try:
                                    p = Path(path_str)
                                    if not p.is_absolute():
                                        p = (actual_output_dir / p).resolve()
                                    if p.exists() and p.is_file():
                                        downloaded_files.append(p)
                                        break
                                except Exception:
                                    pass
                            if downloaded_files:
                                break
                    if downloaded_files:
                        break
                    # Verschiedene Patterns für yt-dlp Output
                    patterns = [
                        r'\[download\]\s+Destination:\s+(.+?)$',
                        r'\[download\]\s+(.+?)\s+has already been downloaded',
                        r'\[ExtractAudio\]\s+Destination:\s+(.+?)$',
                        r'\[Merger\]\s+Merging formats into\s+"(.+?)"',
                        r'^(.+\.(?:mp4|mkv|webm|mp3|m4a|avi))$',
                        r'[/\\]([^/\\]+\.(?:mp4|mkv|webm|mp3|m4a|avi))\s*$',  # Dateiname am Zeilenende
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, line.strip())
                        if match:
                            path_str = match.group(1).strip().strip('"\'')
                            file_path = Path(path_str)
                            if not file_path.is_absolute():
                                file_path = (actual_output_dir / file_path).resolve()
                            if file_path.exists() and file_path.is_file():
                                downloaded_files.append(file_path)
                                break
                    if downloaded_files:
                        break
                    # Irgendwo in der Zeile ein Pfad mit Video-Endung? (z. B. ZDF/Linux)
                    for ext in ('.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.avi'):
                        idx = line_stripped.find(ext)
                        if idx != -1:
                            path_str = line_stripped[:idx + len(ext)].strip()
                            # Von vorne kürzen bis zum Start eines Pfads
                            for sep in (' ', '\t', '\r', '\n'):
                                if sep in path_str:
                                    path_str = path_str.split(sep)[-1]
                            if path_str and path_str.endswith(ext):
                                try:
                                    p = Path(path_str)
                                    if not p.is_absolute():
                                        p = (actual_output_dir / p).resolve()
                                    if p.exists() and p.is_file():
                                        downloaded_files.append(p)
                                        break
                                except Exception:
                                    pass
                    if downloaded_files:
                        break
                
                # Falls nicht gefunden, suche im Output-Verzeichnis (inkl. Unterordner – ZDF/Serien legen oft Unterordner an)
                if not downloaded_files:
                    def _collect_video_files(base_dir):
                        try:
                            if not base_dir.exists():
                                return []
                        except Exception:
                            return []
                        out = []
                        if output_format == 'mp3':
                            out.extend(base_dir.glob('*.mp3'))
                            out.extend(base_dir.rglob('*.mp3'))
                        else:
                            out.extend(base_dir.glob(f'*.{output_format}'))
                            out.extend(base_dir.rglob(f'*.{output_format}'))
                            if not out:
                                out.extend(base_dir.glob('*.mkv'))
                                out.extend(base_dir.glob('*.webm'))
                                out.extend(base_dir.rglob('*.mkv'))
                                out.extend(base_dir.rglob('*.webm'))
                            if not out:
                                # Nur Video-/Audio-Endungen – nie glob('*'), sonst wird z. B. eine .zip im Home als „Download“ erkannt
                                out.extend(base_dir.glob('*.mp4'))
                                out.extend(base_dir.rglob('*.mp4'))
                                out.extend(base_dir.rglob('*.mkv'))
                                out.extend(base_dir.rglob('*.webm'))
                        return [p for p in out if p.is_file() and not p.name.endswith('.part')
                                and not p.name.startswith('.')]

                    dirs_to_search = [actual_output_dir]
                    try:
                        resolved = actual_output_dir.resolve()
                        if resolved != actual_output_dir and resolved.exists():
                            dirs_to_search.append(resolved)
                    except Exception:
                        pass
                    for search_dir in dirs_to_search:
                        files = _collect_video_files(search_dir)
                        if files:
                            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                            downloaded_files = [files[0]]
                            self.log(f"  Datei gefunden in: {downloaded_files[0].parent}")
                            break
                    
                    # Letzter Fallback: aktuelles Arbeitsverzeichnis (z. B. wenn yt-dlp bei start_launcher.sh dorthin schreibt)
                    if not downloaded_files:
                        try:
                            cwd = Path(os.getcwd())
                            if cwd != actual_output_dir and cwd.exists():
                                files = _collect_video_files(cwd)
                                if files:
                                    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                                    # Nur wenn Datei in den letzten 5 Min. geändert wurde (frischer Download)
                                    newest = files[0]
                                    if newest.stat().st_mtime >= (time.time() - 300):
                                        downloaded_files = [newest]
                                        self.log(f"  Datei im Arbeitsverzeichnis gefunden: {newest}")
                        except Exception:
                            pass
                
                if downloaded_files:
                    downloaded_file = downloaded_files[0]
                    # Normalisiere: wenn relativ, unter actual_output_dir auflösen
                    if not downloaded_file.is_absolute():
                        downloaded_file = (actual_output_dir / downloaded_file).resolve()
                    
                    # Serien-/Film-Dateinamen ggf. nach Template umbenennen
                    try:
                        template = None
                        context = {}
                        if is_series and video_info:
                            # Serien-Dateinamen
                            series_name_val = video_info.get('series') or series_name or ''
                            season_num_val = video_info.get('season_number') or season_number
                            episode_num_val = playlist_index if playlist_index is not None else video_info.get('playlist_index') or video_info.get('episode_number')
                            title_val = video_info.get('title') or downloaded_file.stem
                            # Audiothek: URN als Titel ersetzen (z. B. "urn:ard:episode:..." -> "Folge N")
                            if title_val and (title_val.startswith('urn:ard:') or 'urn:ard:' in title_val):
                                if episode_num_val is not None:
                                    title_val = f"Folge {episode_num_val}"
                                else:
                                    title_val = downloaded_file.stem if downloaded_file.stem and not downloaded_file.stem.startswith('urn:') else "Folge"
                            # Audiothek/Quelle: Präfix "STE04", "S04E04", "ST04 - " etc. entfernen, damit nur der reine Folgentitel im Template steht
                            if title_val and self._is_audiothek_or_sounds_url(url):
                                title_val = re.sub(r'^(?:ST\d*E\d+|S\d+E\d+)\s*[-–—]\s*', '', title_val, flags=re.IGNORECASE).strip() or title_val
                            
                            # Versuche, Episode aus Titel zu extrahieren falls nicht vorhanden (einfacher Fallback)
                            if not episode_num_val:
                                m = re.search(r'[Ee](\d{1,2})', title_val)
                                if m:
                                    try:
                                        episode_num_val = int(m.group(1))
                                    except Exception:
                                        episode_num_val = None
                            
                            context = {
                                'series': series_name_val or '',
                                'season': season_num_val or 0,
                                'season2': f"{int(season_num_val):02d}" if season_num_val else '',
                                'episode': episode_num_val or 0,
                                'episode2': f"{int(episode_num_val):02d}" if episode_num_val else '',
                                'title': title_val,
                            }
                            context.update(self._filename_date_context(video_info))
                            if self.gui_instance is not None and hasattr(self.gui_instance, 'settings'):
                                s = getattr(self.gui_instance, 'settings', {})
                                if self._is_audiothek_or_sounds_url(url):
                                    template = s.get('audiothek_filename_template', 'E{episode2} - {title}')
                                elif playlist_index is not None and url and ('youtube.com' in url.lower() or 'youtu.be' in url.lower()):
                                    # YouTube-Playlist: nur Nummer und Titel, kein "E" / "ST01E"
                                    template = '{episode2} - {title}'
                                else:
                                    template = s.get('series_filename_template', 'E{episode2} - {title}')
                            else:
                                template = 'E{episode2} - {title}' if (playlist_index is None or not url or ('youtube.com' not in url.lower() and 'youtu.be' not in url.lower())) else '{episode2} - {title}'
                        else:
                            # Film/Einzelvideo – optionales Template
                            if video_info:
                                title_val = video_info.get('title') or downloaded_file.stem
                                if title_val and (title_val.startswith('urn:ard:') or 'urn:ard:' in title_val):
                                    title_val = downloaded_file.stem if downloaded_file.stem and not downloaded_file.stem.startswith('urn:') else "Audiothek"
                            else:
                                title_val = downloaded_file.stem
                            context = {
                                'series': '',
                                'season': 0,
                                'season2': '',
                                'episode': 0,
                                'episode2': '',
                                'title': title_val,
                            }
                            context.update(self._filename_date_context(video_info if video_info else {'title': title_val}))
                            if self.gui_instance is not None and hasattr(self.gui_instance, 'settings'):
                                s = getattr(self.gui_instance, 'settings', {})
                                if self._is_audiothek_or_sounds_url(url):
                                    template = s.get('audiothek_filename_template', '{title}')
                                else:
                                    template = s.get('movie_filename_template', '{title}')
                            else:
                                template = '{title}'
                        
                        if template:
                            try:
                                new_name = self._apply_filename_template(template, context)
                                if not new_name:
                                    new_name = downloaded_file.stem
                                new_path = downloaded_file.with_name(f"{new_name}{downloaded_file.suffix}")
                                if new_path != downloaded_file:
                                    if not new_path.exists():
                                        downloaded_file.rename(new_path)
                                        self.log(f"DEBUG: Datei umbenannt in: {new_path.name}")
                                        downloaded_file = new_path
                            except Exception as e:
                                self.log(f"WARNING: Konnte Dateinamen-Template nicht anwenden: {e}", "WARNING")
                    except Exception:
                        pass
                    
                    # Speichere Beschreibungstext, falls gewünscht
                    if download_description:
                        # Hole Video-Info falls nicht vorhanden
                        if video_info is None:
                            video_info = self.get_video_info(url, check_series=is_series)
                        
                        if video_info:
                            description_text = self._extract_description(video_info, url)
                            if description_text and description_text.strip():
                                desc_basename = self._get_description_basename(video_info, is_series, series_name, season_number, url, playlist_index=playlist_index)
                                description_path = actual_output_dir / f"{desc_basename}.txt"
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
                    
                    # Fallback: Kein Cover vorhanden (z. B. ARD Audiothek) – von der Webseite holen (og:image)
                    has_cover = any((actual_output_dir / n).exists() for n in ('cover.jpg', 'cover.webp', 'cover.png'))
                    if not has_cover:
                        _u = (url or '')
                        page_url = _u if ('ardaudiothek.de' in _u or 'ardsounds.de' in _u) else ((video_info or {}).get('webpage_url') or _u or '')
                        if page_url and ('ardaudiothek.de' in page_url or 'ardsounds.de' in page_url):
                            self._fetch_cover_from_webpage(page_url, actual_output_dir)
                    
                    # MP3: Cover einbetten, falls in der Datei noch keins bzw. nur Platzhalter; danach Cover-Datei löschen
                    if downloaded_file.suffix.lower() == '.mp3':
                        try:
                            used_cover_path = self._embed_cover_into_mp3_if_missing(downloaded_file, actual_output_dir)
                            if used_cover_path is not None and used_cover_path.exists():
                                try:
                                    used_cover_path.unlink(missing_ok=True)
                                    self.log("✓ Cover-Datei nach Einbetten in MP3 entfernt")
                                except OSError as e:
                                    self.log(f"⚠ Cover-Datei konnte nicht entfernt werden: {e}", "WARNING")
                        except Exception as e:
                            self.log(f"⚠ Cover einbetten übersprungen: {e}", "WARNING")
                    
                    # Weitere Cover-Dateien im Ordner löschen, wenn kein Thumbnail gewünscht (Nutzer will nur eingebettetes Cover)
                    if not download_thumbnail:
                        removed_any = False
                        for name in ('cover.jpg', 'cover.jpeg', 'cover.webp', 'cover.png'):
                            cover_path = actual_output_dir / name
                            if cover_path.is_file():
                                if downloaded_file.suffix.lower() == '.mp3' and cover_path.resolve() == downloaded_file.resolve():
                                    continue
                                try:
                                    cover_path.unlink(missing_ok=True)
                                    removed_any = True
                                except OSError as e:
                                    self.log(f"⚠ Cover-Datei konnte nicht entfernt werden: {e}", "WARNING")
                        if removed_any:
                            self.log("✓ Cover-Datei(en) entfernt (nur in MP3)")
                    
                    self.log(f"✓ Download erfolgreich: {downloaded_file.name}")
                    return True, downloaded_file, ""
                else:
                    self.log("⚠ Download scheint erfolgreich, aber Datei nicht gefunden", "WARNING")
                    try:
                        if actual_output_dir.exists():
                            all_entries = list(actual_output_dir.rglob('*'))[:50]
                            files_in_dir = [p for p in all_entries if p.is_file()]
                            self.log(f"  Suchpfad: {actual_output_dir}", "WARNING")
                            self.log(f"  Gefundene Dateien (max. 20): {[p.name for p in files_in_dir[:20]]}", "WARNING")
                            if not files_in_dir:
                                self.log(f"  Oberverzeichnis-Inhalt: {[p.name for p in actual_output_dir.iterdir()]}", "WARNING")
                        else:
                            self.log(f"  Suchpfad existiert nicht: {actual_output_dir}", "WARNING")
                    except Exception as e:
                        self.log(f"  Fehler beim Auflisten: {e}", "WARNING")
                    # Debug: letzte yt-dlp-Zeilen (hilft unter Linux/ZDF)
                    if output_lines:
                        for ln in output_lines[-8:]:
                            if ln.strip():
                                self.log(f"  [yt-dlp] {ln.strip()[:120]}", "WARNING")
                    else:
                        self.log("  Keine yt-dlp-Ausgabe erfasst (stdout leer). Befehl im Terminal ausführen zur Fehlersuche.", "WARNING")
                        try:
                            from yt_dlp_helper import get_ytdlp_command
                            import shlex
                            base_cmd = get_ytdlp_command() or ['yt-dlp']
                            full_cmd = base_cmd + yt_args
                            self.log(f"  Befehl: {' '.join(shlex.quote(str(a)) for a in full_cmd)}", "WARNING")
                        except Exception:
                            pass
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
    
    def _fetch_cover_from_webpage(self, page_url: str, output_dir: Path) -> bool:
        """
        Lädt das Cover-Bild von einer Webseite (z. B. ARD Audiothek), falls og:image gesetzt ist.
        Speichert es als cover.jpg im output_dir.
        Returns True wenn ein Cover gespeichert wurde, sonst False.
        """
        if not page_url or not str(page_url).strip().startswith('http'):
            return False
        try:
            import ssl
            from urllib.request import Request, urlopen
            from urllib.error import URLError, HTTPError
            req = Request(
                str(page_url),
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            )
            # ARD Sounds / Audiothek: gleicher TLS-Workaround wie bei yt-dlp (record layer failure)
            _ssl_ctx = None
            _pu = str(page_url).lower()
            if 'ardsounds.de' in _pu or 'ardaudiothek.de' in _pu:
                _ssl_ctx = ssl.create_default_context()
                _ssl_ctx.check_hostname = False
                _ssl_ctx.verify_mode = ssl.CERT_NONE
            with urlopen(req, timeout=15, context=_ssl_ctx) as resp:
                html = resp.read().decode('utf-8', errors='replace')
            # og:image: <meta property="og:image" content="https://..."> oder content vor property
            m = re.search(
                r'<meta[^>]+\b(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+\bcontent=["\']([^"\']+)["\']',
                html, re.IGNORECASE
            )
            if not m:
                m = re.search(r'<meta[^>]+\bcontent=["\']([^"\']+)["\'][^>]+\b(?:property|name)=["\'](?:og:image|twitter:image)["\']', html, re.IGNORECASE)
            if not m:
                return False
            img_url = m.group(1).strip()
            if not img_url.startswith('http'):
                from urllib.parse import urljoin
                img_url = urljoin(page_url, img_url)
            req_img = Request(img_url, headers={'User-Agent': 'Mozilla/5.0 (compatible; UniversalDownloader/1.0)'})
            with urlopen(req_img, timeout=15) as img_resp:
                data = img_resp.read()
                content_type = (img_resp.headers.get('Content-Type') or '').lower()
            if not data or len(data) < 100:
                return False
            if 'webp' in content_type:
                cover_path = output_dir / "cover.webp"
            elif 'png' in content_type:
                cover_path = output_dir / "cover.png"
            else:
                cover_path = output_dir / "cover.jpg"
            with open(cover_path, 'wb') as f:
                f.write(data)
            self.log(f"✓ Cover von Webseite übernommen: {cover_path.name}")
            return True
        except (URLError, HTTPError, OSError, ValueError) as e:
            self.log(f"⚠ Cover von Webseite nicht verfügbar: {e}", "WARNING")
            return False
    
    def _embed_cover_into_mp3_if_missing(self, mp3_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Bettet das Cover (cover.jpg / cover.webp / cover.png) in die MP3 ein, falls die Datei
        noch kein brauchbares eingebettetes Bild hat (keins oder nur winziger Platzhalter).
        Returns den Pfad der verwendeten Cover-Datei, falls eingebettet wurde (kann danach gelöscht werden);
        sonst None.
        """
        if not mp3_path or not mp3_path.suffix.lower() == '.mp3' or not mp3_path.exists():
            return None
        try:
            from mutagen.mp3 import MP3
            from mutagen.id3 import ID3, APIC
            audio = MP3(str(mp3_path), ID3=ID3)
            # Nur überspringen, wenn bereits ein richtiges Cover eingebettet ist (> 500 Bytes)
            MIN_COVER_BYTES = 500
            has_real_cover = False
            if audio.tags:
                for frame in audio.tags.values():
                    if isinstance(frame, APIC) and getattr(frame, 'data', None) and len(frame.data) >= MIN_COVER_BYTES:
                        has_real_cover = True
                        break
            if has_real_cover:
                return None
            # Cover-Datei im Ordner suchen
            for name, mime in [('cover.jpg', 'image/jpeg'), ('cover.jpeg', 'image/jpeg'),
                               ('cover.webp', 'image/webp'), ('cover.png', 'image/png')]:
                cover_path = output_dir / name
                if not cover_path.exists():
                    continue
                try:
                    data = cover_path.read_bytes()
                    if not data or len(data) < 100:
                        continue
                except OSError:
                    continue
                try:
                    audio.add_tags()
                except Exception:
                    pass
                # Vorhandenes APIC entfernen, damit unser Cover verwendet wird (type 3 = Front Cover)
                if audio.tags:
                    to_del = [k for k, v in audio.tags.items() if isinstance(v, APIC)]
                    for k in to_del:
                        del audio.tags[k]
                audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc='Cover', data=data))
                audio.save()
                self.log(f"✓ Cover in MP3 eingebettet: {mp3_path.name}")
                return cover_path
        except Exception as e:
            self.log(f"⚠ Cover in MP3 einbetten fehlgeschlagen: {e}", "WARNING")
        return None
    
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
                    kwargs = {
                        'capture_output': True,
                        'text': True,
                        'timeout': 15
                    }
                    if platform.system() == 'Windows':
                        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
                    result = subprocess.run(cmd, **kwargs)
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
            
            kwargs = {
                'capture_output': True,
                'text': True,
                'timeout': 30
            }
            if platform.system() == 'Windows':
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(cmd, **kwargs)
            
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
