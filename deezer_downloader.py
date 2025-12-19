#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Deezer Downloader für privaten Gebrauch
Lädt Musik und Hörbücher von Deezer herunter
Mit DRM-Umgehung, Vollständigkeitsprüfung und detailliertem Logging
"""

import os
import re
import json
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC
from mutagen.mp3 import MP3
from PIL import Image
import io
from datetime import datetime

# Import Authentifizierung
try:
    from deezer_auth import DeezerAuth
except ImportError:
    DeezerAuth = None


class DownloadResult:
    """Klasse zur Speicherung von Download-Ergebnissen"""
    def __init__(self, track_id: str, track_name: str, success: bool, 
                 source: str, file_path: Optional[Path] = None, error: Optional[str] = None):
        self.track_id = track_id
        self.track_name = track_name
        self.success = success
        self.source = source  # "Deezer", "YouTube", "Fehlgeschlagen"
        self.file_path = file_path
        self.error = error
        self.timestamp = datetime.now()


class DeezerDownloader:
    """Hauptklasse für Deezer-Downloads"""
    
    def __init__(self, download_path: str = "Downloads", arl_token: Optional[str] = None, 
                 auth: Optional['DeezerAuth'] = None):
        """
        Initialisiert den Downloader
        
        Args:
            download_path: Pfad zum Download-Verzeichnis
            arl_token: Optionaler ARL-Token für Deezer-Authentifizierung (für DRM-Umgehung)
            auth: Optionales DeezerAuth-Objekt für erweiterte Authentifizierung
        """
        self.download_path = Path(download_path)
        self.download_path.mkdir(exist_ok=True)
        
        # Authentifizierung
        self.auth = auth
        if self.auth and self.auth.is_logged_in():
            self.arl_token = self.auth.arl_token
            self.quality = self.auth.get_quality()
        else:
            self.arl_token = arl_token
            self.quality = "MP3_320"  # Standard
        
        # Deezer API Base URL
        self.api_base = "https://api.deezer.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Setze ARL-Token in Session falls vorhanden
        if self.arl_token:
            self.session.cookies.set('arl', self.arl_token, domain='.deezer.com')
        
        # Download-Statistiken
        self.download_results: List[DownloadResult] = []
        self.download_log: List[str] = []
    
    def log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Log hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        self.download_log.append(log_entry)
        print(log_entry)
    
    def extract_id_from_url(self, url: str) -> Optional[str]:
        """
        Extrahiert die ID aus einem Deezer-Link
        
        Args:
            url: Deezer-URL (Track, Album, Playlist, etc.)
            
        Returns:
            ID des Elements oder None
        """
        # Prüfe ob es eine link.deezer.com URL ist - diese muss zuerst aufgelöst werden
        if 'link.deezer.com' in url.lower():
            try:
                # Folge Redirects um die echte URL zu bekommen
                response = self.session.get(url, allow_redirects=True, timeout=10)
                url = response.url
            except Exception as e:
                self.log(f"Fehler beim Auflösen der link.deezer.com URL: {e}", "WARNING")
                # Versuche trotzdem mit der ursprünglichen URL
        
        patterns = [
            r'deezer\.com/(?:[a-z]{2}/)?(?:track|album|playlist|artist)/(\d+)',
            r'/(track|album|playlist|artist)/(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1) if len(match.groups()) == 1 else match.group(2)
        return None
    
    def get_track_info(self, track_id: str) -> Optional[Dict]:
        """
        Ruft Track-Informationen von der Deezer API ab
        
        Args:
            track_id: Deezer Track-ID
            
        Returns:
            Dictionary mit Track-Informationen oder None
        """
        try:
            url = f"{self.api_base}/track/{track_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Track-Info: {e}", "ERROR")
            return None
    
    def get_album_info(self, album_id: str) -> Optional[Dict]:
        """
        Ruft Album-Informationen von der Deezer API ab
        
        Args:
            album_id: Deezer Album-ID
            
        Returns:
            Dictionary mit Album-Informationen oder None
        """
        try:
            url = f"{self.api_base}/album/{album_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Stelle sicher, dass alle Tracks geladen sind
            if 'tracks' in data and 'data' in data['tracks']:
                tracks = data['tracks']['data']
                # Prüfe auf weitere Seiten
                if 'next' in data.get('tracks', {}):
                    next_url = data['tracks']['next']
                    while next_url:
                        try:
                            next_response = self.session.get(next_url, timeout=10)
                            next_response.raise_for_status()
                            next_data = next_response.json()
                            tracks.extend(next_data.get('data', []))
                            next_url = next_data.get('next')
                        except:
                            break
                data['tracks']['data'] = tracks
            
            return data
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Album-Info: {e}", "ERROR")
            return None
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """
        Ruft alle Tracks einer Playlist ab
        
        Args:
            playlist_id: Deezer Playlist-ID
            
        Returns:
            Liste von Track-Dictionaries
        """
        tracks = []
        try:
            url = f"{self.api_base}/playlist/{playlist_id}/tracks"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            tracks.extend(data.get('data', []))
            
            # Pagination - lade alle Tracks
            while 'next' in data:
                try:
                    response = self.session.get(data['next'], timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    tracks.extend(data.get('data', []))
                except:
                    break
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Playlist: {e}", "ERROR")
        
        return tracks
    
    def download_cover_art(self, cover_url: str) -> Optional[bytes]:
        """
        Lädt das Cover-Art herunter
        
        Args:
            cover_url: URL zum Cover-Bild
            
        Returns:
            Bilddaten als Bytes oder None
        """
        try:
            response = self.session.get(cover_url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            self.log(f"Fehler beim Herunterladen des Covers: {e}", "WARNING")
            return None
    
    def sanitize_filename(self, filename: str) -> str:
        """
        Bereinigt Dateinamen von ungültigen Zeichen
        
        Args:
            filename: Original-Dateiname
            
        Returns:
            Bereinigter Dateiname
        """
        # Entferne ungültige Zeichen
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Entferne führende/abschließende Punkte und Leerzeichen
        filename = filename.strip('. ')
        
        # Begrenze Länge
        if len(filename) > 200:
            filename = filename[:200]
        
        return filename
    
    def add_metadata_to_mp3(self, file_path: Path, track_info: Dict, cover_art: Optional[bytes] = None):
        """
        Fügt Metadaten zu einer MP3-Datei hinzu
        
        Args:
            file_path: Pfad zur MP3-Datei
            track_info: Track-Informationen
            cover_art: Cover-Art als Bytes
        """
        try:
            audio = MP3(str(file_path), ID3=ID3)
            
            # Erstelle ID3-Tags falls nicht vorhanden
            try:
                audio.add_tags()
            except:
                pass
            
            # Titel
            if 'title' in track_info:
                audio['TIT2'] = TIT2(encoding=3, text=track_info['title'])
            
            # Künstler
            if 'artist' in track_info and 'name' in track_info['artist']:
                audio['TPE1'] = TPE1(encoding=3, text=track_info['artist']['name'])
            
            # Album
            if 'album' in track_info and 'title' in track_info['album']:
                audio['TALB'] = TALB(encoding=3, text=track_info['album']['title'])
            
            # Jahr
            if 'album' in track_info and 'release_date' in track_info['album']:
                year = track_info['album']['release_date'][:4]
                audio['TDRC'] = TDRC(encoding=3, text=year)
            
            # Cover-Art
            if cover_art:
                audio['APIC'] = APIC(
                    encoding=3,
                    mime='image/jpeg',
                    type=3,
                    desc='Cover',
                    data=cover_art
                )
            
            audio.save()
        except Exception as e:
            self.log(f"Fehler beim Hinzufügen der Metadaten: {e}", "WARNING")
    
    def get_audio_format_from_quality(self) -> Tuple[str, str]:
        """
        Konvertiert Qualitätsstring in yt-dlp Parameter
        
        Returns:
            (format, quality) - Format und Qualität für yt-dlp
        """
        quality_map = {
            "FLAC": ("flac", "best"),
            "MP3_320": ("mp3", "320"),
            "MP3_192": ("mp3", "192"),
            "MP3_128": ("mp3", "128")
        }
        
        return quality_map.get(self.quality, ("mp3", "320"))
    
    def download_track_deezer_direct(self, track_id: str, output_path: Path, track_info: Dict) -> Tuple[bool, str]:
        """
        Versucht direkten Deezer-Download (mit ARL-Token wenn verfügbar)
        
        Returns:
            (success, source) - source ist "Deezer" oder Fehlermeldung
        """
        try:
            import subprocess
            import sys
            
            deezer_url = f"https://www.deezer.com/track/{track_id}"
            
            # Bestimme Format und Qualität
            audio_format, quality = self.get_audio_format_from_quality()
            
            # Ändere Dateiendung basierend auf Format
            if audio_format == "flac":
                output_path = output_path.with_suffix('.flac')
            elif audio_format == "mp3":
                output_path = output_path.with_suffix('.mp3')
            
            # Versuche mit ARL-Token wenn verfügbar
            if self.arl_token:
                # Verwende Cookies-Datei für yt-dlp
                import tempfile
                cookies_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
                cookies_file.write(f".deezer.com\tTRUE\t/\tFALSE\t0\tarl\t{self.arl_token}\n")
                cookies_file.close()
                
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "--cookies", cookies_file.name,
                    "-x",
                    "--audio-format", audio_format,
                    "--audio-quality", quality if audio_format == "mp3" else "0",
                    "--no-warnings",
                    "-o", str(output_path),
                    deezer_url
                ]
            else:
                # Standard-Versuch ohne ARL
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "-x",
                    "--audio-format", audio_format,
                    "--audio-quality", quality if audio_format == "mp3" else "0",
                    "--no-warnings",
                    "-o", str(output_path),
                    deezer_url
                ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            # Lösche temporäre Cookies-Datei
            if self.arl_token and os.path.exists(cookies_file.name):
                try:
                    os.unlink(cookies_file.name)
                except:
                    pass
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return True, "Deezer"
            else:
                # Kombiniere stderr und stdout für vollständige Fehlermeldung
                error_msg = ""
                if result.stderr:
                    error_msg += result.stderr
                if result.stdout:
                    error_msg += " " + result.stdout
                error_msg = error_msg[:500] if error_msg else "Unbekannter Fehler"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)[:200]
    
    def download_track_youtube(self, track_info: Dict, output_path: Path) -> Tuple[bool, str]:
        """
        Lädt Track von YouTube herunter
        
        Returns:
            (success, source) - source ist "YouTube" oder Fehlermeldung
        """
        try:
            import subprocess
            import sys
            
            search_query = f"{track_info['artist']['name']} {track_info['title']}"
            search_url = f"ytsearch:{search_query}"
            
            cmd = [
                sys.executable, "-m", "yt_dlp",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "--no-warnings",
                "--quiet",
                "-f", "bestaudio/best",
                "-o", str(output_path),
                search_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return True, "YouTube"
            else:
                error_msg = result.stderr[:200] if result.stderr else "Unbekannter Fehler"
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)[:200]
    
    def download_track(self, track_id: str, output_dir: Optional[Path] = None, 
                       use_youtube_fallback: bool = True) -> DownloadResult:
        """
        Lädt einen einzelnen Track herunter mit vollständigem Logging
        
        Args:
            track_id: Deezer Track-ID
            output_dir: Ausgabeverzeichnis (optional)
            use_youtube_fallback: Falls True, versucht YouTube als Fallback zu nutzen
            
        Returns:
            DownloadResult mit allen Details
        """
        if output_dir is None:
            output_dir = self.download_path
        
        # Track-Info abrufen
        track_info = self.get_track_info(track_id)
        if not track_info or 'error' in track_info:
            error_msg = f"Track {track_id} nicht gefunden"
            self.log(error_msg, "ERROR")
            return DownloadResult(track_id, "Unbekannt", False, "Fehlgeschlagen", error=error_msg)
        
        track_name = f"{track_info['artist']['name']} - {track_info['title']}"
        self.log(f"Starte Download: {track_name}")
        
        # Zeige Qualität an
        if self.auth:
            self.log(f"  Qualität: {self.quality} (Abo: {self.auth.subscription_type or 'Unbekannt'})", "INFO")
        
        # Erstelle Dateiname
        filename = self.sanitize_filename(track_name)
        # Dateiendung wird basierend auf Qualität gesetzt
        
        # Methode 1: Versuche Deezer-Download
        self.log(f"  → Versuche Deezer-Download...", "INFO")
        
        # Erstelle Plattform-Ordnerstruktur: deezer/künstlername/...
        platform_output_dir = self._add_platform_folder(output_dir, "deezer")
        output_path = platform_output_dir / f"{filename}.mp3"
        
        success, source_or_error = self.download_track_deezer_direct(track_id, output_path, track_info)
        
        if success:
            # Cover-Art herunterladen
            cover_art = None
            if 'album' in track_info and 'cover_medium' in track_info['album']:
                cover_art = self.download_cover_art(track_info['album']['cover_medium'])
            
            # Metadaten hinzufügen
            self.add_metadata_to_mp3(output_path, track_info, cover_art)
            
            self.log(f"  ✓ Erfolgreich von Deezer heruntergeladen: {output_path}", "SUCCESS")
            result = DownloadResult(track_id, track_name, True, "Deezer", output_path)
            self.download_results.append(result)
            return result
        
        # Methode 2: Fallback zu YouTube
        # Prüfe auf DRM-Fehler (verschiedene Formate)
        drm_detected = (
            "[DRM]" in source_or_error or 
            "DRM" in source_or_error.upper() or
            "drm protection" in source_or_error.lower() or
            "drm-protected" in source_or_error.lower() or
            "not supported" in source_or_error.lower() and "drm" in source_or_error.lower()
        )
        
        if use_youtube_fallback and drm_detected:
            self.log(f"  ⚠ Deezer-Download fehlgeschlagen (DRM-Schutz): {source_or_error[:100]}", "WARNING")
            self.log(f"  → Versuche YouTube als Fallback...", "INFO")
            
            # Erstelle Plattform-Ordnerstruktur: youtube/künstlername/...
            platform_output_dir = self._add_platform_folder(output_dir, "youtube")
            output_path = platform_output_dir / f"{filename}.mp3"
            
            success, youtube_error = self.download_track_youtube(track_info, output_path)
            
            if success:
                # Cover-Art herunterladen
                cover_art = None
                if 'album' in track_info and 'cover_medium' in track_info['album']:
                    cover_art = self.download_cover_art(track_info['album']['cover_medium'])
                
                # Metadaten hinzufügen
                self.add_metadata_to_mp3(output_path, track_info, cover_art)
                
                self.log(f"  ✓ Erfolgreich von YouTube heruntergeladen: {output_path}", "SUCCESS")
                result = DownloadResult(track_id, track_name, True, "YouTube", output_path)
                self.download_results.append(result)
                return result
            else:
                error_msg = f"Deezer (DRM) und YouTube fehlgeschlagen: {youtube_error[:100]}"
                self.log(f"  ✗ {error_msg}", "ERROR")
                result = DownloadResult(track_id, track_name, False, "Fehlgeschlagen", error=error_msg)
                self.download_results.append(result)
                return result
        else:
            error_msg = f"Deezer-Download fehlgeschlagen: {source_or_error[:100]}"
            self.log(f"  ✗ {error_msg}", "ERROR")
            result = DownloadResult(track_id, track_name, False, "Fehlgeschlagen", error=error_msg)
            self.download_results.append(result)
            return result
    
    def _add_platform_folder(self, output_dir: Path, platform: str) -> Path:
        """
        Fügt Plattform-Ordner zur Ordnerstruktur hinzu
        
        Struktur: platform/künstlername/...
        
        Args:
            output_dir: Basis-Pfad (z.B. musik/künstlername/album-name)
            platform: Plattform-Name ('deezer' oder 'youtube')
            
        Returns:
            Pfad mit Plattform-Ordner (z.B. musik/deezer/künstlername/album-name)
        """
        # Extrahiere den relativen Pfad vom Basis-Download-Pfad
        base_path = self.download_path
        
        try:
            # Versuche relativen Pfad zu extrahieren
            relative_path = output_dir.relative_to(base_path)
            # Füge Plattform-Ordner vor dem relativen Pfad hinzu
            platform_path = base_path / platform / relative_path
        except ValueError:
            # Falls relativer Pfad nicht möglich (z.B. wenn output_dir außerhalb von base_path)
            # Erstelle neuen Pfad mit Plattform-Ordner
            # Extrahiere nur den letzten Teil des Pfads (Künstlername/Album-Name)
            parts = output_dir.parts
            # Finde den Index von base_path in parts
            try:
                base_index = parts.index(base_path.name) if base_path.name in parts else -1
                if base_index >= 0 and base_index < len(parts) - 1:
                    # Verwende alles nach base_path
                    relative_parts = parts[base_index + 1:]
                    platform_path = base_path / platform / Path(*relative_parts)
                else:
                    # Fallback: Verwende gesamten output_dir als relativen Pfad
                    platform_path = base_path / platform / output_dir.name
            except:
                # Fallback: Verwende gesamten output_dir als relativen Pfad
                platform_path = base_path / platform / output_dir.name
        
        platform_path.mkdir(parents=True, exist_ok=True)
        return platform_path
    
    def verify_completeness(self, expected_tracks: List[Dict], output_dir: Path) -> Dict:
        """
        Prüft die Vollständigkeit der Downloads
        
        Args:
            expected_tracks: Liste der erwarteten Tracks
            output_dir: Verzeichnis mit Downloads
            
        Returns:
            Dictionary mit Vollständigkeits-Informationen
        """
        expected_count = len(expected_tracks)
        downloaded_files = list(output_dir.glob("*.mp3"))
        downloaded_count = len(downloaded_files)
        
        # Erstelle Set der erwarteten Dateinamen
        expected_filenames = set()
        for track in expected_tracks:
            if 'artist' in track and 'name' in track['artist'] and 'title' in track:
                filename = self.sanitize_filename(f"{track['artist']['name']} - {track['title']}")
                expected_filenames.add(f"{filename}.mp3")
        
        # Finde fehlende Tracks
        downloaded_filenames = {f.name for f in downloaded_files}
        missing_tracks = expected_filenames - downloaded_filenames
        
        return {
            'expected': expected_count,
            'downloaded': downloaded_count,
            'missing': len(missing_tracks),
            'missing_tracks': list(missing_tracks),
            'completeness_percent': (downloaded_count / expected_count * 100) if expected_count > 0 else 0
        }
    
    def print_summary(self, expected_count: int = 0):
        """
        Druckt eine Zusammenfassung der Downloads
        
        Args:
            expected_count: Erwartete Anzahl Tracks (0 = automatisch aus Ergebnissen)
        """
        if not self.download_results:
            return
        
        total = len(self.download_results)
        successful = sum(1 for r in self.download_results if r.success)
        failed = total - successful
        
        deezer_count = sum(1 for r in self.download_results if r.source == "Deezer")
        youtube_count = sum(1 for r in self.download_results if r.source == "YouTube")
        
        print("\n" + "=" * 70)
        print("DOWNLOAD-ZUSAMMENFASSUNG")
        print("=" * 70)
        print(f"Gesamt: {total} Track(s)")
        print(f"Erfolgreich: {successful} Track(s)")
        print(f"Fehlgeschlagen: {failed} Track(s)")
        print()
        print("Download-Quellen:")
        print(f"  • Deezer: {deezer_count} Track(s)")
        print(f"  • YouTube (Fallback): {youtube_count} Track(s)")
        print()
        
        if expected_count > 0:
            completeness = (successful / expected_count * 100) if expected_count > 0 else 0
            print(f"Vollständigkeit: {successful}/{expected_count} ({completeness:.1f}%)")
            if successful < expected_count:
                print(f"⚠ WARNUNG: {expected_count - successful} Track(s) fehlen!")
                print("\nFehlgeschlagene Downloads:")
                for result in self.download_results:
                    if not result.success:
                        print(f"  • {result.track_name}")
                        if result.error:
                            print(f"    Fehler: {result.error[:100]}")
        
        print("\nErfolgreich heruntergeladene Tracks:")
        for result in self.download_results:
            if result.success:
                source_indicator = "🎵" if result.source == "Deezer" else "▶️"
                print(f"  {source_indicator} {result.track_name} ({result.source})")
                if result.file_path:
                    print(f"    → {result.file_path}")
        
        print("=" * 70)
    
    def download_album(self, album_id: str, output_dir: Optional[Path] = None) -> int:
        """
        Lädt ein komplettes Album herunter mit Vollständigkeitsprüfung
        
        Args:
            album_id: Deezer Album-ID
            output_dir: Ausgabeverzeichnis (optional)
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        album_info = self.get_album_info(album_id)
        if not album_info or 'error' in album_info:
            self.log(f"Album {album_id} nicht gefunden", "ERROR")
            return 0
        
        album_name = f"{album_info['artist']['name']} - {album_info['title']}"
        self.log(f"\n{'='*70}", "INFO")
        self.log(f"Album: {album_name}", "INFO")
        self.log(f"Anzahl Tracks: {album_info['nb_tracks']}", "INFO")
        self.log(f"{'='*70}\n", "INFO")
        
        if output_dir is None:
            album_dir_name = self.sanitize_filename(album_name)
            output_dir = self.download_path / album_dir_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Alle Tracks des Albums herunterladen
        tracks = album_info.get('tracks', {}).get('data', [])
        expected_count = len(tracks)
        
        for i, track in enumerate(tracks, 1):
            self.log(f"[{i}/{len(tracks)}] ", "INFO")
            self.download_track(str(track['id']), output_dir)
        
        # Vollständigkeitsprüfung
        completeness = self.verify_completeness(tracks, output_dir)
        
        self.log(f"\n{'='*70}", "INFO")
        self.log(f"Album-Download abgeschlossen", "INFO")
        self.log(f"Vollständigkeit: {completeness['downloaded']}/{completeness['expected']} ({completeness['completeness_percent']:.1f}%)", "INFO")
        
        if completeness['missing'] > 0:
            self.log(f"⚠ FEHLENDE TRACKS ({completeness['missing']}):", "WARNING")
            for missing in completeness['missing_tracks']:
                self.log(f"  • {missing}", "WARNING")
        
        # Zusammenfassung
        self.print_summary(expected_count)
        
        return completeness['downloaded']
    
    def get_playlist_info(self, playlist_id: str) -> Optional[Dict]:
        """
        Ruft Playlist-Informationen von der Deezer API ab
        
        Args:
            playlist_id: Deezer Playlist-ID
            
        Returns:
            Dictionary mit Playlist-Informationen oder None
        """
        try:
            url = f"{self.api_base}/playlist/{playlist_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Playlist-Info: {e}", "ERROR")
            return None
    
    def download_playlist(self, playlist_id: str, output_dir: Optional[Path] = None) -> int:
        """
        Lädt eine Playlist herunter mit Vollständigkeitsprüfung
        
        Args:
            playlist_id: Deezer Playlist-ID
            output_dir: Ausgabeverzeichnis (optional)
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        tracks = self.get_playlist_tracks(playlist_id)
        if not tracks:
            self.log(f"Playlist {playlist_id} nicht gefunden oder leer", "ERROR")
            return 0
        
        self.log(f"\n{'='*70}", "INFO")
        self.log(f"Playlist mit {len(tracks)} Tracks gefunden", "INFO")
        self.log(f"{'='*70}\n", "INFO")
        
        if output_dir is None:
            output_dir = self.download_path / "Playlist"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        expected_count = len(tracks)
        
        for i, track in enumerate(tracks, 1):
            self.log(f"[{i}/{len(tracks)}] ", "INFO")
            self.download_track(str(track['id']), output_dir)
        
        # Vollständigkeitsprüfung
        completeness = self.verify_completeness(tracks, output_dir)
        
        self.log(f"\n{'='*70}", "INFO")
        self.log(f"Playlist-Download abgeschlossen", "INFO")
        self.log(f"Vollständigkeit: {completeness['downloaded']}/{completeness['expected']} ({completeness['completeness_percent']:.1f}%)", "INFO")
        
        if completeness['missing'] > 0:
            self.log(f"⚠ FEHLENDE TRACKS ({completeness['missing']}):", "WARNING")
            for missing in completeness['missing_tracks']:
                self.log(f"  • {missing}", "WARNING")
        
        # Zusammenfassung
        self.print_summary(expected_count)
        
        return completeness['downloaded']
    
    def get_artist_info(self, artist_id: str) -> Optional[Dict]:
        """
        Ruft Artist-Informationen von der Deezer API ab
        
        Args:
            artist_id: Deezer Artist-ID
            
        Returns:
            Dictionary mit Artist-Informationen oder None
        """
        try:
            url = f"{self.api_base}/artist/{artist_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.log(f"Fehler beim Abrufen der Artist-Info: {e}", "ERROR")
            return None
    
    def download_artist(self, artist_id: str, output_dir: Optional[Path] = None, limit: int = 50) -> int:
        """
        Lädt Top-Tracks eines Artists herunter
        
        Args:
            artist_id: Deezer Artist-ID
            output_dir: Optionales Ausgabeverzeichnis
            limit: Maximale Anzahl Tracks (Standard: 50)
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        if output_dir is None:
            output_dir = self.download_path
        
        # Hole Artist-Info
        artist_info = self.get_artist_info(artist_id)
        if not artist_info:
            self.log(f"Konnte Artist-Informationen nicht abrufen", "ERROR")
            return 0
        
        artist_name = artist_info.get('name', f'Artist_{artist_id}')
        self.log(f"Lade Top-Tracks von {artist_name} herunter...", "INFO")
        
        # Hole Top-Tracks
        try:
            url = f"{self.api_base}/artist/{artist_id}/top?limit={limit}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            tracks = data.get('data', [])
            if not tracks:
                self.log(f"Keine Tracks für {artist_name} gefunden", "WARNING")
                return 0
            
            self.log(f"Gefunden: {len(tracks)} Track(s)", "INFO")
            
            # Lade jeden Track herunter
            downloaded = 0
            for i, track in enumerate(tracks, 1):
                track_id = str(track['id'])
                track_name = track.get('title', 'Unbekannt')
                self.log(f"[{i}/{len(tracks)}] Lade herunter: {track_name}", "INFO")
                
                result = self.download_track(track_id, output_dir=output_dir, use_youtube_fallback=True)
                if result.success:
                    downloaded += 1
            
            self.log(f"Artist-Download abgeschlossen: {downloaded}/{len(tracks)} Tracks erfolgreich", "INFO")
            return downloaded
            
        except Exception as e:
            self.log(f"Fehler beim Herunterladen der Artist-Tracks: {e}", "ERROR")
            return 0
    
    def download_from_url(self, url: str) -> int:
        """
        Lädt basierend auf einer Deezer-URL herunter
        
        Args:
            url: Deezer-URL (Track, Album, Playlist, Artist)
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        # Bestimme Typ und ID
        if '/track/' in url:
            track_id = self.extract_id_from_url(url)
            if track_id:
                result = self.download_track(track_id)
                self.print_summary(1)
                return 1 if result.success else 0
        elif '/album/' in url:
            album_id = self.extract_id_from_url(url)
            if album_id:
                return self.download_album(album_id)
        elif '/playlist/' in url:
            playlist_id = self.extract_id_from_url(url)
            if playlist_id:
                return self.download_playlist(playlist_id)
        elif '/artist/' in url:
            artist_id = self.extract_id_from_url(url)
            if artist_id:
                return self.download_artist(artist_id)
        
        self.log("Ungültige oder nicht unterstützte Deezer-URL", "ERROR")
        return 0


if __name__ == "__main__":
    # Beispiel-Verwendung
    downloader = DeezerDownloader()
    
    print("Deezer Downloader")
    print("=" * 50)
    
    # Optional: ARL-Token für DRM-Umgehung
    # arl_token = input("ARL-Token (optional, Enter zum Überspringen): ").strip()
    # if arl_token:
    #     downloader.arl_token = arl_token
    
    # Beispiel-URL (kann durch Benutzereingabe ersetzt werden)
    url = input("Deezer-URL eingeben (Track, Album oder Playlist): ").strip()
    
    if url:
        downloader.download_from_url(url)
    else:
        print("Keine URL eingegeben")
