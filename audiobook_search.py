#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Anbieter-Suche für Hörbücher
Prüft Verfügbarkeit auf verschiedenen Plattformen: YouTube, Audible, Storytel, Nextory, BookBeat, Spotify
"""

import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
import time

# Importiere vorhandene Downloader
try:
    from deezer_downloader import DeezerDownloader
except ImportError:
    DeezerDownloader = None

try:
    from spotify_downloader import SpotifyDownloader
except ImportError:
    SpotifyDownloader = None

try:
    from audible_integration import AudibleLibrary
except ImportError:
    AudibleLibrary = None

try:
    from audiobook_providers import StorytelProvider, NextoryProvider, BookBeatProvider
except ImportError:
    StorytelProvider = None
    NextoryProvider = None
    BookBeatProvider = None


class AudiobookSearch:
    """Klasse für Multi-Anbieter-Suche von Hörbüchern"""
    
    def __init__(self):
        self.deezer_downloader = DeezerDownloader() if DeezerDownloader else None
        self.spotify_downloader = SpotifyDownloader() if SpotifyDownloader else None
        self.audible_library = AudibleLibrary() if AudibleLibrary else None
        
        # Initialisiere Provider (falls verfügbar)
        self.storytel = StorytelProvider() if StorytelProvider else None
        self.nextory = NextoryProvider() if NextoryProvider else None
        self.bookbeat = BookBeatProvider() if BookBeatProvider else None
    
    def search_all_providers(self, title: str, artist: Optional[str] = None) -> Dict[str, Dict]:
        """
        Sucht ein Hörbuch auf allen verfügbaren Plattformen
        
        Args:
            title: Titel des Hörbuchs
            artist: Optional: Künstler/Autor
            
        Returns:
            Dictionary mit Verfügbarkeits-Informationen pro Anbieter
            Format: {
                'youtube': {'available': bool, 'url': str, 'info': dict},
                'audible': {'available': bool, 'asin': str, 'info': dict},
                'spotify': {'available': bool, 'url': str, 'info': dict},
                'storytel': {'available': bool, 'book_id': str, 'info': dict},
                'nextory': {'available': bool, 'book_id': str, 'info': dict},
                'bookbeat': {'available': bool, 'book_id': str, 'info': dict},
            }
        """
        results = {
            'youtube': {'available': False, 'url': None, 'info': {}},
            'audible': {'available': False, 'asin': None, 'info': {}},
            'spotify': {'available': False, 'url': None, 'info': {}},
            'storytel': {'available': False, 'book_id': None, 'info': {}},
            'nextory': {'available': False, 'book_id': None, 'info': {}},
            'bookbeat': {'available': False, 'book_id': None, 'info': {}},
        }
        
        # Erstelle Suchanfrage
        search_query = f"{artist} {title}" if artist else title
        
        print(f"🔍 Suche nach: {search_query}")
        print("=" * 70)
        
        # 1. Prüfe YouTube
        print("📺 Prüfe YouTube...")
        youtube_result = self._search_youtube(search_query)
        results['youtube'] = youtube_result
        if youtube_result['available']:
            print(f"  ✅ Verfügbar auf YouTube")
        else:
            print(f"  ❌ Nicht verfügbar auf YouTube")
        
        # 2. Prüfe Spotify
        if self.spotify_downloader:
            print("🎵 Prüfe Spotify...")
            spotify_result = self._search_spotify(search_query)
            results['spotify'] = spotify_result
            if spotify_result['available']:
                print(f"  ✅ Verfügbar auf Spotify")
            else:
                print(f"  ❌ Nicht verfügbar auf Spotify")
        
        # 3. Prüfe Audible
        if self.audible_library:
            print("📚 Prüfe Audible...")
            audible_result = self._search_audible(search_query)
            results['audible'] = audible_result
            if audible_result['available']:
                print(f"  ✅ Verfügbar auf Audible")
            else:
                print(f"  ❌ Nicht verfügbar auf Audible")
        
        # 4. Prüfe Storytel
        if self.storytel:
            print("📖 Prüfe Storytel...")
            storytel_result = self._search_storytel(search_query)
            results['storytel'] = storytel_result
            if storytel_result['available']:
                print(f"  ✅ Verfügbar auf Storytel")
            else:
                print(f"  ❌ Nicht verfügbar auf Storytel")
        
        # 5. Prüfe Nextory
        if self.nextory:
            print("📕 Prüfe Nextory...")
            nextory_result = self._search_nextory(search_query)
            results['nextory'] = nextory_result
            if nextory_result['available']:
                print(f"  ✅ Verfügbar auf Nextory")
            else:
                print(f"  ❌ Nicht verfügbar auf Nextory")
        
        # 6. Prüfe BookBeat
        if self.bookbeat:
            print("📗 Prüfe BookBeat...")
            bookbeat_result = self._search_bookbeat(search_query)
            results['bookbeat'] = bookbeat_result
            if bookbeat_result['available']:
                print(f"  ✅ Verfügbar auf BookBeat")
            else:
                print(f"  ❌ Nicht verfügbar auf BookBeat")
        
        print("=" * 70)
        
        # Zusammenfassung
        available_providers = [provider for provider, data in results.items() if data.get('available', False)]
        if available_providers:
            print(f"✅ Verfügbar auf: {', '.join(available_providers)}")
        else:
            print("❌ Nicht auf den geprüften Plattformen verfügbar")
        
        return results
    
    def _search_youtube(self, query: str) -> Dict:
        """Sucht auf YouTube"""
        try:
            import tempfile
            from pathlib import Path
            
            # Optimiere Suchanfrage für Hörbücher
            search_query = f"{query} Hörbuch"
            search_url = f"ytsearch1:{search_query}"
            
            # Erstelle temporäre Datei
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
            
            try:
                cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "--dump-json",
                    "--no-warnings",
                    "--quiet",
                    search_url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 and result.stdout:
                    import json
                    video_info = json.loads(result.stdout)
                    
                    # Prüfe ob es ein Hörbuch sein könnte (Dauer > 30 Minuten)
                    duration = video_info.get('duration', 0)
                    title = video_info.get('title', '')
                    video_id = video_info.get('id', '')
                    
                    if duration > 1800 or 'hörbuch' in title.lower() or 'audiobook' in title.lower():
                        tmp_path.unlink(missing_ok=True)
                        return {
                            'available': True,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'info': {
                                'title': title,
                                'duration': duration,
                                'channel': video_info.get('uploader', ''),
                                'views': video_info.get('view_count', 0)
                            }
                        }
                
                tmp_path.unlink(missing_ok=True)
                return {'available': False, 'url': None, 'info': {}}
                
            except Exception:
                tmp_path.unlink(missing_ok=True)
                return {'available': False, 'url': None, 'info': {}}
                
        except Exception as e:
            return {'available': False, 'url': None, 'info': {'error': str(e)}}
    
    def _search_spotify(self, query: str) -> Dict:
        """Sucht auf Spotify"""
        try:
            if not self.spotify_downloader:
                return {'available': False, 'url': None, 'info': {}}
            
            # Verwende Spotify Web API für Suche
            search_url = "https://api.spotify.com/v1/search"
            params = {
                'q': query,
                'type': 'audiobook',
                'limit': 1
            }
            
            # Versuche ohne Token (öffentliche API)
            response = requests.get(search_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                audiobooks = data.get('audiobooks', {}).get('items', [])
                
                if audiobooks:
                    audiobook = audiobooks[0]
                    return {
                        'available': True,
                        'url': audiobook.get('external_urls', {}).get('spotify', ''),
                        'info': {
                            'name': audiobook.get('name', ''),
                            'publisher': audiobook.get('publisher', ''),
                            'total_chapters': audiobook.get('total_chapters', 0)
                        }
                    }
            
            return {'available': False, 'url': None, 'info': {}}
            
        except Exception as e:
            return {'available': False, 'url': None, 'info': {'error': str(e)}}
    
    def _search_audible(self, query: str) -> Dict:
        """Sucht auf Audible"""
        try:
            if not self.audible_library:
                return {'available': False, 'asin': None, 'info': {}}
            
            # Verwende Audible API für Suche
            # Hinweis: Audible API erfordert Authentifizierung
            # Für jetzt: Prüfe ob es in der Bibliothek ist
            if hasattr(self.audible_library, 'search_books'):
                results = self.audible_library.search_books(query)
                if results:
                    book = results[0]
                    return {
                        'available': True,
                        'asin': book.get('asin', ''),
                        'info': {
                            'title': book.get('title', ''),
                            'author': book.get('author', ''),
                            'runtime_length_ms': book.get('runtime_length_ms', 0)
                        }
                    }
            
            return {'available': False, 'asin': None, 'info': {}}
            
        except Exception as e:
            return {'available': False, 'asin': None, 'info': {'error': str(e)}}
    
    def _search_storytel(self, query: str) -> Dict:
        """Sucht auf Storytel"""
        try:
            if not self.storytel:
                return {'available': False, 'book_id': None, 'info': {}}
            
            # Storytel hat keine öffentliche API
            # Versuche über Web-Suche
            search_url = f"https://www.storytel.com/de/de/search?q={query}"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                # Prüfe ob Ergebnisse gefunden wurden (einfache Heuristik)
                if 'book' in response.text.lower() or 'hörbuch' in response.text.lower():
                    return {
                        'available': True,  # Möglicherweise verfügbar
                        'book_id': None,  # Erfordert Login für genaue ID
                        'info': {
                            'note': 'Erfordert Login für genaue Prüfung'
                        }
                    }
            
            return {'available': False, 'book_id': None, 'info': {}}
            
        except Exception as e:
            return {'available': False, 'book_id': None, 'info': {'error': str(e)}}
    
    def _search_nextory(self, query: str) -> Dict:
        """Sucht auf Nextory"""
        try:
            if not self.nextory:
                return {'available': False, 'book_id': None, 'info': {}}
            
            # Nextory hat keine öffentliche API
            search_url = f"https://www.nextory.de/suche/?q={query}"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                if 'book' in response.text.lower() or 'hörbuch' in response.text.lower():
                    return {
                        'available': True,  # Möglicherweise verfügbar
                        'book_id': None,  # Erfordert Login für genaue ID
                        'info': {
                            'note': 'Erfordert Login für genaue Prüfung'
                        }
                    }
            
            return {'available': False, 'book_id': None, 'info': {}}
            
        except Exception as e:
            return {'available': False, 'book_id': None, 'info': {'error': str(e)}}
    
    def _search_bookbeat(self, query: str) -> Dict:
        """Sucht auf BookBeat"""
        try:
            if not self.bookbeat:
                return {'available': False, 'book_id': None, 'info': {}}
            
            # BookBeat hat keine öffentliche API
            search_url = f"https://www.bookbeat.de/suche?q={query}"
            response = requests.get(search_url, timeout=10)
            
            if response.status_code == 200:
                if 'book' in response.text.lower() or 'hörbuch' in response.text.lower():
                    return {
                        'available': True,  # Möglicherweise verfügbar
                        'book_id': None,  # Erfordert Login für genaue ID
                        'info': {
                            'note': 'Erfordert Login für genaue Prüfung'
                        }
                    }
            
            return {'available': False, 'book_id': None, 'info': {}}
            
        except Exception as e:
            return {'available': False, 'book_id': None, 'info': {'error': str(e)}}
    
    def download_from_best_provider(self, title: str, artist: Optional[str] = None, 
                                   output_dir: Optional[Path] = None) -> bool:
        """
        Lädt Hörbuch vom besten verfügbaren Anbieter herunter
        
        Priorität:
        1. YouTube (kostenlos, schnell)
        2. Spotify (falls verfügbar)
        3. Audible (falls in Bibliothek)
        4. Andere Anbieter
        
        Args:
            title: Titel des Hörbuchs
            artist: Optional: Künstler/Autor
            output_dir: Ausgabeverzeichnis
            
        Returns:
            True bei Erfolg
        """
        # Suche auf allen Plattformen
        results = self.search_all_providers(title, artist)
        
        # Wähle besten Anbieter
        if results['youtube']['available']:
            print(f"\n📥 Lade von YouTube herunter...")
            return self._download_from_youtube(results['youtube']['url'], output_dir)
        elif results['spotify']['available']:
            print(f"\n📥 Lade von Spotify herunter...")
            return self._download_from_spotify(results['spotify']['url'], output_dir)
        elif results['audible']['available']:
            print(f"\n📥 Lade von Audible herunter...")
            return self._download_from_audible(results['audible']['asin'], output_dir)
        else:
            print("❌ Kein verfügbarer Anbieter gefunden")
            return False
    
    def _download_from_youtube(self, url: str, output_dir: Optional[Path] = None) -> bool:
        """Lädt von YouTube herunter"""
        try:
            from video_downloader import VideoDownloader
            
            if output_dir is None:
                output_dir = Path("Downloads")
            
            downloader = VideoDownloader(
                download_path=str(output_dir),
                quality="best",
                output_format="mp3"
            )
            
            return downloader.download_video(url)
            
        except Exception as e:
            print(f"❌ Fehler beim YouTube-Download: {e}")
            return False
    
    def _download_from_spotify(self, url: str, output_dir: Optional[Path] = None) -> bool:
        """Lädt von Spotify herunter"""
        try:
            if not self.spotify_downloader:
                return False
            
            # Spotify-Downloader verwendet bereits YouTube-Fallback
            return self.spotify_downloader.download_from_url(url)
            
        except Exception as e:
            print(f"❌ Fehler beim Spotify-Download: {e}")
            return False
    
    def _download_from_audible(self, asin: str, output_dir: Optional[Path] = None) -> bool:
        """Lädt von Audible herunter"""
        try:
            if not self.audible_library:
                return False
            
            if output_dir is None:
                output_dir = Path("Downloads")
            
            # Hole Buch-Info
            book_info = self.audible_library.get_book_info(asin)
            if not book_info:
                print(f"❌ Konnte Buch-Info nicht abrufen")
                return False
            
            title = book_info.get('title', asin)
            return self.audible_library.download_book(asin, title, output_dir)
            
        except Exception as e:
            print(f"❌ Fehler beim Audible-Download: {e}")
            return False


if __name__ == "__main__":
    # Test
    searcher = AudiobookSearch()
    results = searcher.search_all_providers("DICKE EIER IN UNTERFILZBACH", "Eva Adam")
    print("\nErgebnisse:")
    for provider, data in results.items():
        if data.get('available'):
            print(f"  {provider}: ✅ {data.get('info', {})}")
