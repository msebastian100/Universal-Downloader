#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stream-Automatisierung für Spotify und Deezer
Automatisiertes Abspielen mit Audio-Aufnahme (nur für privaten Gebrauch)

⚠️ WICHTIG: Nur für privaten Gebrauch!
"""

import time
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict

# Versuche Selenium zu importieren
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    webdriver = None
    Options = None
    By = None
    Keys = None
    ActionChains = None
    WebDriverWait = None
    EC = None

from audio_recorder import AudioRecorder


class StreamAutomation:
    """Klasse für automatisiertes Abspielen und Aufnehmen von Streams"""
    
    def __init__(self, output_path: Path, playback_speed: float = 4.0, arl_token: Optional[str] = None):
        """
        Initialisiert die Stream-Automatisierung
        
        Args:
            output_path: Pfad zur Ausgabedatei
            playback_speed: Wiedergabegeschwindigkeit (2.0 = doppelt so schnell)
            arl_token: Optionaler Deezer ARL-Token für automatische Anmeldung
        """
        self.output_path = Path(output_path)
        self.playback_speed = playback_speed
        self.arl_token = arl_token
        self.driver: Optional[webdriver.Chrome] = None
        self.recorder: Optional[AudioRecorder] = None
        self.is_playing = False
        
        # Lade ARL-Token automatisch falls nicht übergeben
        if not self.arl_token:
            self.arl_token = self._load_arl_token()
    
    def _load_arl_token(self) -> Optional[str]:
        """Lädt gespeicherten ARL-Token aus der Konfiguration"""
        try:
            from deezer_auth import DeezerAuth
            auth = DeezerAuth()
            if auth.is_logged_in():
                return auth.arl_token
        except Exception:
            pass
        
        # Fallback: Versuche direkt aus Config-Datei zu laden
        try:
            import json
            from pathlib import Path
            config_path = Path(".deezer_config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    arl = config.get('arl_token')
                    if arl:
                        return arl
        except Exception:
            pass
        
        return None
    
    def _set_deezer_cookie(self):
        """Setzt Deezer ARL-Cookie im Browser"""
        if not self.driver or not self.arl_token:
            return
        
        try:
            # Gehe zu Deezer-Hauptseite um Domain zu setzen
            self.driver.get("https://www.deezer.com")
            time.sleep(1)
            
            # Setze ARL-Cookie
            self.driver.add_cookie({
                'name': 'arl',
                'value': self.arl_token,
                'domain': '.deezer.com',
                'path': '/',
                'secure': True,
                'httpOnly': False
            })
            
            print("✓ Deezer ARL-Token als Cookie gesetzt (automatisch angemeldet)")
        except Exception as e:
            print(f"⚠️ Konnte ARL-Cookie nicht setzen: {e}")
        
    def setup_browser(self, headless: bool = False) -> bool:
        """Richtet Browser ein"""
        if not SELENIUM_AVAILABLE:
            print("❌ Selenium nicht verfügbar. Bitte installieren Sie es mit: pip install selenium")
            return False
        
        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument('--headless')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--mute-audio')  # Stumm schalten
            
            # Erstelle WebDriver
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.maximize_window()
            return True
        except Exception as e:
            print(f"❌ Fehler beim Einrichten des Browsers: {e}")
            return False
    
    def play_spotify_track(self, url: str, duration: Optional[float] = None) -> bool:
        """
        Spielt einen Spotify-Track automatisch ab
        
        Args:
            url: Spotify-URL
            duration: Erwartete Dauer in Sekunden (None = automatisch ermitteln)
            
        Returns:
            True bei Erfolg
        """
        if not self.driver:
            if not self.setup_browser():
                return False
        
        try:
            print(f"🌐 Öffne Spotify: {url}")
            self.driver.get(url)
            time.sleep(3)  # Warte auf Seitenladung
            
            # Warte auf Play-Button und klicke ihn
            try:
                # Spotify Play-Button finden (verschiedene Selektoren)
                play_selectors = [
                    "button[data-testid='play-button']",
                    "button[aria-label*='Play']",
                    "button[aria-label*='Wiedergabe']",
                    ".control-button[aria-label*='Play']",
                    "button[title*='Play']"
                ]
                
                play_button = None
                for selector in play_selectors:
                    try:
                        play_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        break
                    except:
                        continue
                
                if not play_button:
                    # Versuche mit JavaScript
                    self.driver.execute_script("document.querySelector('button[data-testid=\"play-button\"]')?.click()")
                    time.sleep(1)
                else:
                    play_button.click()
                
                print("▶️ Play-Button geklickt")
                time.sleep(2)  # Warte auf Start der Wiedergabe
                
            except Exception as e:
                print(f"⚠️ Konnte Play-Button nicht automatisch klicken: {e}")
                print("   Bitte klicken Sie manuell auf Play")
                time.sleep(5)  # Warte auf manuelles Klicken
            
            # Setze Geschwindigkeit auf 2x (falls verfügbar)
            try:
                # Öffne Geschwindigkeits-Menü (falls vorhanden)
                # Spotify hat normalerweise keine Geschwindigkeitskontrolle in der Web-App
                # Aber wir können versuchen, die Playback-Rate über JavaScript zu ändern
                self.driver.execute_script(f"""
                    const audio = document.querySelector('audio');
                    if (audio) {{
                        audio.playbackRate = {self.playback_speed};
                    }}
                """)
                print(f"⚡ Geschwindigkeit auf {self.playback_speed}x gesetzt")
            except Exception as e:
                print(f"⚠️ Konnte Geschwindigkeit nicht automatisch setzen: {e}")
                print(f"   Bitte stellen Sie die Geschwindigkeit manuell auf {self.playback_speed}x ein")
            
            # Stelle sicher, dass Audio stumm ist
            try:
                self.driver.execute_script("""
                    const audio = document.querySelector('audio');
                    if (audio) {
                        audio.volume = 0;
                    }
                """)
                print("🔇 Audio stumm geschaltet")
            except:
                pass
            
            # Prüfe ob Track läuft
            self.is_playing = True
            
            # Ermittle Track-Dauer (falls nicht angegeben)
            if not duration:
                try:
                    duration_text = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='duration']").text
                    # Parse Dauer (Format: "3:45")
                    parts = duration_text.split(':')
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    else:
                        duration = 180  # Fallback: 3 Minuten
                except:
                    duration = 180  # Fallback
            
            # Berücksichtige Geschwindigkeit für Aufnahmedauer
            recording_duration = duration / self.playback_speed if duration else None
            
            print(f"⏱️  Erwartete Dauer: {duration} Sekunden")
            print(f"⏱️  Aufnahmedauer (bei {self.playback_speed}x): {recording_duration:.1f} Sekunden")
            
            return True
            
        except Exception as e:
            print(f"❌ Fehler beim Abspielen: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def play_deezer_track(self, url: str, duration: Optional[float] = None) -> bool:
        """
        Spielt einen Deezer-Track automatisch ab
        
        Args:
            url: Deezer-URL
            duration: Erwartete Dauer in Sekunden (None = automatisch ermitteln)
            
        Returns:
            True bei Erfolg
        """
        if not self.driver:
            if not self.setup_browser():
                return False
        
        try:
            # Stelle sicher, dass wir angemeldet sind (falls ARL-Token vorhanden)
            if self.arl_token and '.deezer.com' in url:
                # Gehe zuerst zur Hauptseite um Cookie zu setzen (falls noch nicht gesetzt)
                try:
                    current_url = self.driver.current_url
                    if 'deezer.com' not in current_url:
                        self.driver.get("https://www.deezer.com")
                        time.sleep(1)
                        self._set_deezer_cookie()
                except:
                    pass
            
            print(f"🌐 Öffne Deezer: {url}")
            self.driver.get(url)
            time.sleep(3)  # Warte auf Seitenladung
            
            # Hole Track-Info VOR dem Start (Titel, Künstler, Dauer)
            track_info = {}
            try:
                # Titel
                try:
                    title_elem = self.driver.find_element(By.CSS_SELECTOR, 
                        "h1, .track-title, [data-testid='track-title'], .track-name")
                    track_info['title'] = title_elem.text.strip()
                    print(f"📝 Track-Titel erkannt: {track_info['title']}")
                except:
                    pass
                
                # Künstler
                try:
                    artist_elem = self.driver.find_element(By.CSS_SELECTOR,
                        ".track-artist, [data-testid='track-artist'], .artist-name, a[href*='/artist/']")
                    track_info['artist'] = artist_elem.text.strip()
                    print(f"👤 Künstler erkannt: {track_info['artist']}")
                except:
                    pass
                
                # Dauer
                try:
                    duration_elem = self.driver.find_element(By.CSS_SELECTOR,
                        ".track-duration, [data-testid='duration'], .duration")
                    duration_text = duration_elem.text.strip()
                    # Parse Dauer (Format: "MM:SS" oder "HH:MM:SS")
                    parts = duration_text.split(':')
                    if len(parts) == 2:
                        track_info['duration'] = int(parts[0]) * 60 + int(parts[1])
                    elif len(parts) == 3:
                        track_info['duration'] = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                    else:
                        track_info['duration'] = None
                    print(f"⏱️  Dauer erkannt: {duration_text} ({track_info.get('duration', 'unbekannt')} Sekunden)")
                except:
                    pass
                
                # Speichere für späteren Vergleich
                self.current_track_info = track_info
                
            except Exception as e:
                print(f"⚠️ Konnte Track-Info nicht vollständig abrufen: {e}")
                self.current_track_info = {}
            
            # Prüfe ob Anmeldung erfolgreich war (falls ARL-Token verwendet wurde)
            if self.arl_token:
                try:
                    # Prüfe ob Login-Button vorhanden ist (dann ist Anmeldung fehlgeschlagen)
                    login_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='login'], button[data-testid='login-button']")
                    if login_elements:
                        print("⚠️ Automatische Anmeldung fehlgeschlagen, verwende manuelle Anmeldung")
                        print("   Bitte melden Sie sich manuell an oder prüfen Sie den ARL-Token")
                    else:
                        print("✓ Automatisch bei Deezer angemeldet")
                except:
                    pass
            
            # Warte auf Play-Button und klicke ihn (mehrere Versuche)
            play_clicked = False
            
            # WICHTIG: Warte zuerst auf Seitenladung
            time.sleep(2)
            
            # Versuche zuerst direkt über Deezer Player API
            try:
                self.driver.execute_script("""
                    if (window.DZ && window.DZ.player) {
                        window.DZ.player.play();
                        return true;
                    }
                    return false;
                """)
                time.sleep(1)
                # Prüfe ob es funktioniert hat
                deezer_playing = self.driver.execute_script("""
                    var pauseButtons = document.querySelectorAll('button[data-testid="pause-button"]');
                    return pauseButtons.length > 0 && pauseButtons[0].offsetParent !== null;
                """)
                if deezer_playing:
                    print("✓ Track gestartet über Deezer Player API")
                    play_clicked = True
            except:
                pass
            
            if not play_clicked:
                for attempt in range(15):  # Maximal 15 Versuche (mehr Versuche für bessere Zuverlässigkeit)
                    try:
                        # Versuche verschiedene Selektoren (spezifisch für Track-Seite)
                        # WICHTIG: Vermeide Playlist-Erstellung-Button (+)
                        play_selectors = [
                            "button[data-testid='play-button']",
                            "button[aria-label*='Play']",
                            "button[aria-label*='Wiedergabe']",
                            ".control-play",
                            "button.play-button",
                            "[data-testid='play']",
                            "button[title*='Play']",
                            # Spezifische Deezer-Track-Seite Selektoren
                            ".track-actions button",
                            ".track-header button",
                            "button.button-play",
                            # Allgemeinere Selektoren
                            "button[class*='play']",
                            "button[class*='Play']",
                            # Vermeide explizit Playlist-Buttons
                            "button:not([aria-label*='Playlist']):not([aria-label*='Hinzufügen']):not([aria-label*='Add'])[data-testid='play-button']"
                        ]
                    
                        for selector in play_selectors:
                            try:
                                # Versuche zuerst mit kürzerer Wartezeit
                                play_button = WebDriverWait(self.driver, 1).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                                )
                                
                                # Prüfe ob Button sichtbar und klickbar ist
                                if not play_button.is_displayed():
                                    continue
                                
                                # Scroll zu Button falls nötig
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", play_button)
                                time.sleep(0.2)
                                
                                # WICHTIG: Verhindere versehentliche Klicks auf Next/Skip-Buttons
                                # Prüfe ob Button wirklich ein Play-Button ist (nicht Next/Skip)
                                button_aria = (play_button.get_attribute("aria-label") or "").lower()
                                button_text = (play_button.text or "").lower()
                                button_testid = play_button.get_attribute("data-testid") or ""
                                
                                # Überspringe Next/Skip-Buttons
                                if any(word in button_aria for word in ['next', 'skip', 'weiter', 'vorwärts', 'nächster', 'überspringen']):
                                    continue
                                if any(word in button_text for word in ['next', 'skip', 'weiter', 'vorwärts', 'nächster', 'überspringen']):
                                    continue
                                
                                # Überspringe Playlist-Buttons
                                if any(word in button_aria for word in ['playlist', 'hinzufügen', 'add', 'erstellen']):
                                    continue
                                if any(word in button_text for word in ['playlist', 'hinzufügen', 'add', 'erstellen']):
                                    continue
                                
                                # Prüfe ob es wirklich ein Play-Button ist
                                is_play_button = (
                                    'play' in button_aria or 
                                    'wiedergabe' in button_aria or
                                    'play' in button_text or
                                    button_testid == 'play-button' or
                                    'play' in selector.lower()
                                )
                                
                                if not is_play_button:
                                    continue
                                
                                # Klicke mit JavaScript (zuverlässiger) - MEHRFACH
                                try:
                                    self.driver.execute_script("arguments[0].click();", play_button)
                                    time.sleep(0.1)
                                    self.driver.execute_script("arguments[0].click();", play_button)  # Doppelklick für Sicherheit
                                except:
                                    play_button.click()  # Fallback: normaler Klick
                                
                                print(f"▶️ Play-Button geklickt (Versuch {attempt + 1}, Selektor: {selector})")
                                
                                # Prüfe ob es funktioniert hat (mehrere Versuche mit längeren Wartezeiten)
                                is_playing = False
                                for check_attempt in range(20):  # 20 Versuche über 10 Sekunden (mehr Zeit für Track-Start)
                                    time.sleep(0.5)  # Warte 0.5 Sekunden zwischen Prüfungen
                                    
                                    audio_state = self.driver.execute_script("""
                                        // Suche nach allen Audio-Elementen (auch versteckte)
                                        const audioElements = document.querySelectorAll('audio');
                                        let audio = null;
                                        
                                        // Finde das aktive Audio-Element
                                        for (const a of audioElements) {
                                            if (a.src || a.currentSrc) {
                                                audio = a;
                                                break;
                                            }
                                        }
                                        
                                        // Fallback: erstes Audio-Element
                                        if (!audio && audioElements.length > 0) {
                                            audio = audioElements[0];
                                        }
                                        
                                        // Alternative: Prüfe Deezer-spezifische Elemente
                                        let deezerPlaying = false;
                                        let deezerTime = 0;
                                        
                                        // Prüfe auf Play-Button-Status (wenn Pause-Button sichtbar, dann spielt es)
                                        const pauseButtons = document.querySelectorAll(
                                            'button[data-testid="pause-button"], ' +
                                            'button[aria-label*="Pause"], ' +
                                            'button[aria-label*="Pausieren"], ' +
                                            '.control-pause, ' +
                                            'button.pause-button'
                                        );
                                        
                                        for (const btn of pauseButtons) {
                                            if (btn.offsetParent !== null) { // Sichtbar
                                                deezerPlaying = true;
                                                break;
                                            }
                                        }
                                        
                                        // Prüfe auf Deezer Player-Status (verschiedene Methoden)
                                        // Methode 1: Prüfe ob Play-Button zu Pause-Button gewechselt ist
                                        const playButton = document.querySelector('button[data-testid="play-button"]');
                                        const isPauseButton = playButton && (
                                            (playButton.getAttribute('aria-label') || '').toLowerCase().includes('pause') ||
                                            (playButton.getAttribute('aria-label') || '').toLowerCase().includes('pausieren')
                                        );
                                        
                                        if (isPauseButton) {
                                            deezerPlaying = true;
                                        }
                                        
                                        // Methode 2: Prüfe auf aktive Player-Klasse
                                        const playerElements = document.querySelectorAll('.player, .player-controls, [class*="player"]');
                                        for (const el of playerElements) {
                                            if (el.classList.contains('playing') || 
                                                el.classList.contains('is-playing') ||
                                                el.getAttribute('data-state') === 'playing') {
                                                deezerPlaying = true;
                                                break;
                                            }
                                        }
                                        
                                        // Methode 3: Prüfe auf Web Audio API (falls verwendet)
                                        let webAudioPlaying = false;
                                        try {
                                            const audioContext = window.AudioContext || window.webkitAudioContext;
                                            if (audioContext) {
                                                // Prüfe ob AudioContext aktiv ist
                                                const contexts = [];
                                                // Versuche aktive AudioContexts zu finden
                                                // (Dies ist schwierig, da wir keinen direkten Zugriff haben)
                                            }
                                        } catch (e) {}
                                        
                                        if (!audio) {
                                            return {
                                                playing: deezerPlaying || webAudioPlaying, 
                                                paused: !deezerPlaying, 
                                                currentTime: deezerTime, 
                                                readyState: deezerPlaying ? 2 : 0,
                                                hasAudio: false,
                                                audioCount: audioElements.length,
                                                deezerPlaying: deezerPlaying,
                                                pauseButtonVisible: pauseButtons.length > 0
                                            };
                                        }
                                        
                                        return {
                                            playing: !audio.paused && (audio.readyState >= 2 || audio.currentTime > 0) || deezerPlaying,
                                            paused: audio.paused && !deezerPlaying,
                                            currentTime: audio.currentTime || deezerTime,
                                            duration: audio.duration,
                                            readyState: audio.readyState,
                                            hasAudio: true,
                                            audioCount: audioElements.length,
                                            src: audio.src || audio.currentSrc || 'no-src',
                                            deezerPlaying: deezerPlaying,
                                            pauseButtonVisible: pauseButtons.length > 0
                                        };
                                    """)
                                    
                                    # Debug-Ausgabe bei jedem Versuch (immer, nicht nur bei geraden Zahlen)
                                    print(f"  [DEBUG Track-Start Prüfung {check_attempt + 1}/20] "
                                          f"paused={audio_state.get('paused', True)}, "
                                          f"currentTime={audio_state.get('currentTime', 0):.2f}s, "
                                          f"readyState={audio_state.get('readyState', 0)}, "
                                          f"hasAudio={audio_state.get('hasAudio', False)}, "
                                          f"deezerPlaying={audio_state.get('deezerPlaying', False)}, "
                                          f"pauseButtonVisible={audio_state.get('pauseButtonVisible', False)}, "
                                          f"playButtonVisible={audio_state.get('playButtonVisible', False)}, "
                                          f"isPauseButton={audio_state.get('isPauseButton', False)}")
                                    
                                    # ZUSÄTZLICH: Prüfe ob Pause-Button sichtbar wird (stärkstes Signal dass Track spielt)
                                    if audio_state.get('pauseButtonVisible', False):
                                        print(f"  [DEBUG Track-Start] Pause-Button wurde sichtbar - Track spielt definitiv!")
                                        is_playing = True
                                        break
                                    
                                    # Sehr lockere Bedingungen: Track spielt wenn:
                                    # 1. Pause-Button sichtbar (stärkstes Signal)
                                    if audio_state.get('pauseButtonVisible', False):
                                        is_playing = True
                                        print(f"✓ Track spielt jetzt (Pause-Button sichtbar - stärkstes Signal)")
                                        break
                                    # 2. Deezer-spezifische Erkennung sagt es spielt
                                    elif audio_state.get('deezerPlaying', False):
                                        is_playing = True
                                        print(f"✓ Track spielt jetzt (Deezer-Erkennung: Pause-Button sichtbar)")
                                        break
                                    # 3. Audio-Element nicht pausiert
                                    elif not audio_state.get('paused', True):
                                        # Track ist nicht pausiert - das ist das wichtigste Kriterium
                                        if audio_state.get('currentTime', 0) > 0:
                                            is_playing = True
                                            print(f"✓ Track spielt jetzt (currentTime: {audio_state.get('currentTime', 0):.2f}s)")
                                            break
                                        elif audio_state.get('readyState', 0) >= 1:
                                            # Audio lädt oder läuft
                                            is_playing = True
                                            print(f"✓ Track spielt jetzt (readyState: {audio_state.get('readyState', 0)}, nicht pausiert)")
                                            break
                                        elif check_attempt >= 3:
                                            # Nach 1.5 Sekunden: Wenn nicht pausiert, dann spielt es wahrscheinlich
                                            is_playing = True
                                            print(f"✓ Track spielt jetzt (nicht pausiert nach {check_attempt * 0.5:.1f}s)")
                                            break
                                
                                    if is_playing:
                                        play_clicked = True
                                        break
                                
                                if is_playing:
                                    break
                            except:
                                continue
                    
                        if play_clicked:
                            break
                    except Exception as e:
                        print(f"⚠️ Fehler beim Klicken auf Play-Button (Versuch {attempt + 1}): {e}")
                        continue
                
                if play_clicked:
                    break
                    
                    # Fallback: Direktes JavaScript-Klicken (vermeide Playlist-Buttons)
                    if not play_clicked:
                        play_button_found = self.driver.execute_script("""
                            // Versuche verschiedene Methoden, vermeide Playlist-Buttons
                            var selectors = [
                                'button[data-testid="play-button"]',
                                'button[aria-label*="Play"]',
                                'button[aria-label*="Wiedergabe"]',
                                '.control-play',
                                'button.play-button'
                            ];
                            
                            for (var i = 0; i < selectors.length; i++) {
                                var selector = selectors[i];
                                var buttons = document.querySelectorAll(selector);
                                for (var j = 0; j < buttons.length; j++) {
                                    var btn = buttons[j];
                                    if (!btn.offsetParent) continue; // Nicht sichtbar
                                    
                                    var ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
                                    var title = (btn.getAttribute('title') || '').toLowerCase();
                                    var text = (btn.textContent || '').toLowerCase();
                                    
                                    // Überspringe Playlist-Buttons
                                    if (ariaLabel.indexOf('playlist') !== -1 || ariaLabel.indexOf('hinzufügen') !== -1 || 
                                        ariaLabel.indexOf('add') !== -1 || ariaLabel.indexOf('erstellen') !== -1 ||
                                        title.indexOf('playlist') !== -1 || title.indexOf('hinzufügen') !== -1 ||
                                        text.indexOf('playlist') !== -1 || text.indexOf('hinzufügen') !== -1) {
                                        continue;
                                    }
                                    
                                    // Prüfe ob es ein Play-Button ist
                                    if (ariaLabel.indexOf('play') !== -1 || ariaLabel.indexOf('wiedergabe') !== -1 || 
                                        title.indexOf('play') !== -1 || btn.getAttribute('data-testid') === 'play-button') {
                                        btn.click();
                                        return true;
                                    }
                                }
                            }
                            
                            // Versuche auch über Audio-Element direkt
                            var audio = document.querySelector('audio');
                            if (audio && audio.paused) {
                                audio.play();
                                return true;
                            }
                            
                            return false;
                        """)
                        
                        if play_button_found:
                            print(f"▶️ Play-Button per JavaScript geklickt (Versuch {attempt + 1})")
                            
                            # Prüfe ob es funktioniert hat (mehrere Versuche)
                            is_playing = False
                            for check_attempt in range(10):  # 10 Versuche über 5 Sekunden
                                time.sleep(0.5)  # Warte 0.5 Sekunden zwischen Prüfungen
                                
                                audio_state = self.driver.execute_script("""
                                    // Suche nach allen Audio-Elementen (auch versteckte)
                                    const audioElements = document.querySelectorAll('audio');
                                    let audio = null;
                                    
                                    // Finde das aktive Audio-Element
                                    for (const a of audioElements) {
                                        if (a.src || a.currentSrc) {
                                            audio = a;
                                            break;
                                        }
                                    }
                                    
                                    // Fallback: erstes Audio-Element
                                    if (!audio && audioElements.length > 0) {
                                        audio = audioElements[0];
                                    }
                                    
                                    if (!audio) {
                                        return {
                                            playing: false, 
                                            paused: true, 
                                            currentTime: 0, 
                                            readyState: 0,
                                            hasAudio: false,
                                            audioCount: audioElements.length
                                        };
                                    }
                                    
                                    return {
                                        playing: !audio.paused && (audio.readyState >= 2 || audio.currentTime > 0),
                                        paused: audio.paused,
                                        currentTime: audio.currentTime,
                                        duration: audio.duration,
                                        readyState: audio.readyState,
                                        hasAudio: true,
                                        audioCount: audioElements.length,
                                        src: audio.src || audio.currentSrc || 'no-src'
                                    };
                                """)
                                
                                # Sehr lockere Bedingungen: Track spielt wenn nicht pausiert
                                if not audio_state.get('paused', True):
                                    if audio_state.get('currentTime', 0) > 0:
                                        is_playing = True
                                        print(f"✓ Track spielt jetzt (JavaScript-Fallback, currentTime: {audio_state.get('currentTime', 0):.2f}s)")
                                        break
                                    elif audio_state.get('readyState', 0) >= 1:
                                        is_playing = True
                                        print(f"✓ Track spielt jetzt (JavaScript-Fallback, readyState: {audio_state.get('readyState', 0)})")
                                        break
                                    elif check_attempt >= 3:
                                        # Nach 1.5 Sekunden: Wenn nicht pausiert, dann spielt es wahrscheinlich
                                        is_playing = True
                                        print(f"✓ Track spielt jetzt (JavaScript-Fallback, nicht pausiert nach {check_attempt * 0.5:.1f}s)")
                                        break
                            
                            if is_playing:
                                play_clicked = True
                                break
                    
                    if not play_clicked:
                        print(f"⚠️ Versuch {attempt + 1} fehlgeschlagen, versuche erneut...")
                        time.sleep(1)
                
                except Exception as e:
                    print(f"⚠️ Fehler beim Klicken auf Play-Button (Versuch {attempt + 1}): {e}")
                    time.sleep(1)
            
            if not play_clicked:
                print("⚠️ Konnte Play-Button nicht automatisch klicken")
                print("   Versuche alternative Methoden...")
                
                # Alternative: Versuche direkt über JavaScript
                try:
                    self.driver.execute_script("""
                        // Versuche alle möglichen Play-Methoden
                        const methods = [
                            () => {
                                const btn = document.querySelector('button[data-testid="play-button"]');
                                if (btn) btn.click();
                            },
                            () => {
                                const audio = document.querySelector('audio');
                                if (audio) audio.play();
                            },
                            () => {
                                // Versuche über Deezer Player API
                                if (window.DZ && window.DZ.player) {
                                    window.DZ.player.play();
                                }
                            }
                        ];
                        
                        for (const method of methods) {
                            try {
                                method();
                                return true;
                            } catch(e) {}
                        }
                        return false;
                    """)
                    time.sleep(2)
                    # Prüfe ob es funktioniert hat
                    deezer_playing = self.driver.execute_script("""
                        const pauseButtons = document.querySelectorAll('button[data-testid="pause-button"]');
                        return pauseButtons.length > 0 && pauseButtons[0].offsetParent !== null;
                    """)
                    if deezer_playing:
                        print("✓ Track gestartet über JavaScript-Fallback")
                        play_clicked = True
                except:
                    pass
                
                if not play_clicked:
                    print("   Bitte klicken Sie manuell auf Play")
                    # Warte auf manuelles Klicken
                    max_wait_manual = 30  # 30 Sekunden
                waited_manual = 0
                while waited_manual < max_wait_manual:
                    time.sleep(1)
                    waited_manual += 1
                    audio_state = self.driver.execute_script("""
                        // Suche nach allen Audio-Elementen (auch versteckte)
                        const audioElements = document.querySelectorAll('audio');
                        let audio = null;
                        
                        // Finde das aktive Audio-Element
                        for (const a of audioElements) {
                            if (a.src || a.currentSrc) {
                                audio = a;
                                break;
                            }
                        }
                        
                        // Fallback: erstes Audio-Element
                        if (!audio && audioElements.length > 0) {
                            audio = audioElements[0];
                        }
                        
                        // Alternative: Prüfe Deezer-spezifische Elemente
                        let deezerPlaying = false;
                        
                        // Prüfe auf Pause-Button (wenn sichtbar, dann spielt es)
                        const pauseButtons = document.querySelectorAll(
                            'button[data-testid="pause-button"], ' +
                            'button[aria-label*="Pause"], ' +
                            'button[aria-label*="Pausieren"], ' +
                            '.control-pause, ' +
                            'button.pause-button'
                        );
                        
                        for (const btn of pauseButtons) {
                            if (btn.offsetParent !== null) { // Sichtbar
                                deezerPlaying = true;
                                break;
                            }
                        }
                        
                        // Prüfe ob Play-Button zu Pause-Button gewechselt ist
                        const playButton = document.querySelector('button[data-testid="play-button"]');
                        const isPauseButton = playButton && (
                            (playButton.getAttribute('aria-label') || '').toLowerCase().includes('pause') ||
                            (playButton.getAttribute('aria-label') || '').toLowerCase().includes('pausieren')
                        );
                        
                        if (isPauseButton) {
                            deezerPlaying = true;
                        }
                        
                        if (!audio) {
                            return {
                                playing: deezerPlaying, 
                                paused: !deezerPlaying, 
                                currentTime: 0, 
                                readyState: deezerPlaying ? 2 : 0,
                                hasAudio: false,
                                audioCount: audioElements.length,
                                deezerPlaying: deezerPlaying
                            };
                        }
                        
                        return {
                            playing: !audio.paused && (audio.readyState >= 2 || audio.currentTime > 0) || deezerPlaying,
                            paused: audio.paused && !deezerPlaying,
                            currentTime: audio.currentTime,
                            duration: audio.duration,
                            readyState: audio.readyState,
                            hasAudio: true,
                            audioCount: audioElements.length,
                            deezerPlaying: deezerPlaying
                        };
                    """)
                    
                    # Sehr lockere Bedingungen: Track spielt wenn Deezer-Erkennung sagt es spielt ODER nicht pausiert
                    is_playing = audio_state.get('deezerPlaying', False) or not audio_state.get('paused', True)
                    
                    if is_playing:
                        print(f"✓ Track spielt jetzt (manuell gestartet, currentTime: {audio_state.get('currentTime', 0):.2f}s, "
                              f"readyState: {audio_state.get('readyState', 0)}, "
                              f"deezerPlaying: {audio_state.get('deezerPlaying', False)})")
                        play_clicked = True
                        break
                else:
                    print("❌ Track wurde nicht gestartet")
                    return False
            
            time.sleep(2)  # Warte auf Start der Wiedergabe
            
            # Setze Geschwindigkeit (verschiedene Methoden, auch für höhere Geschwindigkeiten)
            try:
                # Methode 1: Direktes Setzen der playbackRate mit mehreren Versuchen
                # Für Geschwindigkeiten > 2x müssen wir möglicherweise mehrere atempo-Filter verwenden
                max_playback_rate = 4.0  # Browser-Limit ist normalerweise 4x
                target_speed = min(self.playback_speed, max_playback_rate)
                
                self.driver.execute_script(f"""
                    (function() {{
                        const audio = document.querySelector('audio');
                        if (!audio) return;
                        
                        // Setze Geschwindigkeit
                        audio.playbackRate = {target_speed};
                        
                        // Stelle sicher, dass es gesetzt bleibt - mehrere Event-Listener
                        function enforceSpeed() {{
                            if (audio.playbackRate !== {target_speed}) {{
                                audio.playbackRate = {target_speed};
                            }}
                        }}
                        
                        // Event-Listener für verschiedene Events
                        audio.addEventListener('ratechange', enforceSpeed);
                        audio.addEventListener('play', enforceSpeed);
                        audio.addEventListener('playing', enforceSpeed);
                        audio.addEventListener('timeupdate', enforceSpeed);
                        
                        // MutationObserver als Fallback
                        const observer = new MutationObserver(function() {{
                            enforceSpeed();
                        }});
                        
                        // Beobachte verschiedene Attribute
                        observer.observe(audio, {{ 
                            attributes: true, 
                            attributeFilter: ['playbackRate', 'src'] 
                        }});
                        
                        // Setze auch bei jedem timeupdate (häufigstes Event)
                        const timeUpdateInterval = setInterval(function() {{
                            if (audio.playbackRate !== {target_speed}) {{
                                audio.playbackRate = {target_speed};
                            }}
                        }}, 100); // Alle 100ms prüfen
                        
                        // Speichere Interval-ID für späteres Aufräumen
                        window._speedEnforcerInterval = timeUpdateInterval;
                    }})();
                """)
                
                # Prüfe ob es funktioniert hat
                time.sleep(1)
                actual_speed = self.driver.execute_script("""
                    const audio = document.querySelector('audio');
                    return audio ? audio.playbackRate : 1.0;
                """)
                
                if abs(actual_speed - target_speed) < 0.1:
                    print(f"⚡ Geschwindigkeit auf {target_speed}x gesetzt (tatsächlich: {actual_speed:.1f}x)")
                else:
                    print(f"⚠️ Geschwindigkeit konnte nicht auf {target_speed}x gesetzt werden (aktuell: {actual_speed:.1f}x)")
                    print(f"   Versuche alternative Methode...")
                    
                    # Alternative: Versuche über MediaSource API
                    self.driver.execute_script(f"""
                        const audio = document.querySelector('audio');
                        if (audio) {{
                            // Versuche über verschiedene Wege
                            Object.defineProperty(audio, 'playbackRate', {{
                                get: function() {{ return {target_speed}; }},
                                set: function(val) {{
                                    Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype, 'playbackRate').set.call(this, {target_speed});
                                }},
                                configurable: true
                            }});
                            audio.playbackRate = {target_speed};
                        }}
                    """)
            except Exception as e:
                print(f"⚠️ Konnte Geschwindigkeit nicht automatisch setzen: {e}")
            
            # Stelle sicher, dass Audio stumm ist
            try:
                self.driver.execute_script("""
                    const audio = document.querySelector('audio');
                    if (audio) {
                        audio.volume = 0;
                    }
                """)
                print("🔇 Audio stumm geschaltet")
            except:
                pass
            
            self.is_playing = True
            
            # Ermittle Track-Dauer
            if not duration:
                try:
                    duration_element = self.driver.find_element(By.CSS_SELECTOR, ".track-duration, [data-testid='duration']")
                    duration_text = duration_element.text
                    parts = duration_text.split(':')
                    if len(parts) == 2:
                        duration = int(parts[0]) * 60 + int(parts[1])
                    else:
                        duration = 180
                except:
                    duration = 180
            
            recording_duration = duration / self.playback_speed if duration else None
            print(f"⏱️  Erwartete Dauer: {duration} Sekunden")
            print(f"⏱️  Aufnahmedauer (bei {self.playback_speed}x): {recording_duration:.1f} Sekunden")
            
            return True
            
        except Exception as e:
            print(f"❌ Fehler beim Abspielen: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def record_with_automation(self, url: str, provider: str = "spotify", 
                               duration: Optional[float] = None, track_info: Optional[Dict] = None) -> bool:
        """
        Nimmt automatisch Audio auf während der Wiedergabe
        
        Args:
            url: URL des Tracks
            provider: "spotify" oder "deezer"
            duration: Erwartete Dauer (None = automatisch)
            track_info: Optional Track-Informationen für Metadaten
            
        Returns:
            True bei Erfolg
        """
        try:
            # Hole Track-Info falls nicht übergeben (für Metadaten)
            if not track_info and provider.lower() == "deezer":
                track_info = self._get_deezer_track_info(url)
            
            # Starte Audio-Aufnahme
            print(f"🎙️ Starte Audio-Aufnahme...")
            self.recorder = AudioRecorder(self.output_path)
            
            # Setze Progress-Callback falls vorhanden
            if hasattr(self, 'progress_callback'):
                self.recorder.progress_callback = self.progress_callback
            
            if not self.recorder.start_recording():
                print("❌ Konnte Audio-Aufnahme nicht starten")
                return False
            
            # Starte Browser und spiele Track ab
            playback_success = False
            try:
                if provider.lower() == "spotify":
                    playback_success = self.play_spotify_track(url, duration)
                elif provider.lower() == "deezer":
                    playback_success = self.play_deezer_track(url, duration)
                else:
                    print(f"❌ Unbekannter Provider: {provider}")
                    self.recorder.stop_recording()
                    return False
                
                if not playback_success:
                    print("⚠️ Track konnte nicht abgespielt werden, stoppe Aufnahme...")
                    self.recorder.stop_recording()
                    return False
                    
            except Exception as e:
                print(f"❌ Fehler beim Abspielen: {e}")
                import traceback
                traceback.print_exc()
                self.recorder.stop_recording()
                return False
            
            # Berechne Aufnahmedauer (bei 2x Geschwindigkeit)
            if duration:
                recording_duration = duration / self.playback_speed
                print(f"⏳ Warte {recording_duration:.1f} Sekunden (bei {self.playback_speed}x Geschwindigkeit)...")
                time.sleep(recording_duration + 2)  # +2 Sekunden Puffer
            else:
                # Warte auf Track-Ende (verbesserte Erkennung, auch bei Wiederholung)
                print("⏳ Warte auf Track-Ende...")
                
                # Berechne maximale Wartezeit basierend auf erwarteter Dauer
                if hasattr(self, 'current_track_info') and self.current_track_info.get('duration'):
                    expected_duration = self.current_track_info['duration']
                    # Wartezeit = erwartete Dauer + 30 Sekunden Puffer (bei aktueller Geschwindigkeit)
                    max_wait = (expected_duration / self.playback_speed) + 30
                    print(f"⏱️  Erwartete Aufnahmedauer: {expected_duration / self.playback_speed:.1f}s (bei {self.playback_speed}x)")
                    print(f"⏱️  Maximale Wartezeit: {max_wait:.1f}s (mit 30s Puffer)")
                else:
                    max_wait = 600  # Maximal 10 Minuten (Fallback)
                    print(f"⏱️  Maximale Wartezeit: {max_wait}s (Fallback, da Dauer unbekannt)")
                
                waited = 0
                track_ended = False
                last_position = 0
                position_unchanged_count = 0
                last_track_title = None
                last_url = self.driver.current_url
                last_recording_check = 0  # Für Aufnahme-Status-Prüfung
                
                # Speichere initialen Track-Titel (falls verfügbar)
                try:
                    track_title_elem = self.driver.find_element(By.CSS_SELECTOR, 
                        "h1, .track-title, [data-testid='track-title'], .track-name")
                    last_track_title = track_title_elem.text.strip()
                    print(f"📝 Initialer Track-Titel: {last_track_title}")
                except:
                    pass
                
                print(f"📝 Initiale URL: {last_url}")
                
                # JavaScript-Funktion für Track-Ende-Erkennung (auch bei Wiederholung und Deezer-spezifisch)
                # Setze auch erwartete Dauer für JavaScript (falls bekannt)
                expected_duration = None
                if hasattr(self, 'current_track_info') and self.current_track_info.get('duration'):
                    expected_duration = self.current_track_info['duration']
                
                # Verwende normale String-Formatierung statt f-string für JavaScript-Code
                js_code = """
                    window._expectedDuration = """ + (str(expected_duration) if expected_duration else "null") + """;
                    window._trackEndDetected = false;
                    window._lastTrackTime = 0;
                    window._lastTrackTitle = null;
                    window._trackEndCheck = function() {{
                        // Methode 1: Prüfe Audio-Element
                        const audio = document.querySelector('audio');
                        if (audio) {{
                            const currentTime = audio.currentTime;
                            const duration = audio.duration;
                            
                            // Prüfe ob Track beendet ist
                            if (audio.ended) {{
                                window._trackEndDetected = true;
                                return true;
                            }}
                            
                            // Prüfe ob wir am Ende sind (auch bei Wiederholung)
                            if (duration > 0 && currentTime >= duration - 0.5) {{
                                // Track ist am Ende - warte kurz ob er wiederholt wird
                                setTimeout(function() {{
                                    if (audio.currentTime < 0.5) {{
                                        // Track wurde wiederholt - ein Durchlauf ist beendet
                                        window._trackEndDetected = true;
                                    }} else if (audio.ended) {{
                                        // Track ist wirklich beendet
                                        window._trackEndDetected = true;
                                    }}
                                }}, 500);
                                return true;
                            }}
                        }}
                        
                        // Methode 2: Prüfe Deezer-spezifische Erkennung
                        // Wenn Play-Button wieder sichtbar wird (Pause-Button verschwindet), ist Track beendet
                        const pauseButtons = document.querySelectorAll(
                            'button[data-testid="pause-button"], ' +
                            'button[aria-label*="Pause"], ' +
                            'button[aria-label*="Pausieren"], ' +
                            '.control-pause'
                        );
                        
                        let pauseButtonVisible = false;
                        for (const btn of pauseButtons) {{
                            if (btn.offsetParent !== null) {{
                                pauseButtonVisible = true;
                                break;
                            }}
                        }}
                        
                        // Prüfe ob Play-Button sichtbar ist (und nicht Pause-Button)
                        const playButton = document.querySelector('button[data-testid="play-button"]');
                        if (playButton && playButton.offsetParent !== null) {{
                            const ariaLabel = (playButton.getAttribute('aria-label') || '').toLowerCase();
                            const isPauseButton = ariaLabel.includes('pause') || ariaLabel.includes('pausieren');
                            
                            // Wenn Play-Button sichtbar ist UND es kein Pause-Button ist UND kein Pause-Button sichtbar ist
                            if (!isPauseButton && !pauseButtonVisible) {{
                                // Track ist beendet (Play-Button ist wieder da, Pause-Button weg)
                                window._trackEndDetected = true;
                                return true;
                            }}
                        }}
                        
                        // Methode 3: Prüfe ob Track-Titel sich geändert hat (neuer Track gestartet)
                        try {{
                            const trackTitle = document.querySelector('h1, .track-title, [data-testid="track-title"], .track-name');
                            if (trackTitle) {{
                                const currentTitle = trackTitle.textContent.trim();
                                if (window._lastTrackTitle && window._lastTrackTitle !== '' && 
                                    currentTitle !== '' && currentTitle !== window._lastTrackTitle) {{
                                    // Track-Titel hat sich geändert - neuer Track gestartet
                                    window._trackEndDetected = true;
                                    return true;
                                }}
                                window._lastTrackTitle = currentTitle;
                            }}
                        }} catch (e) {{}}
                        
                        // Methode 4: Prüfe ob erwartete Dauer erreicht wurde
                        if (window._expectedDuration && audio) {{
                            const currentTime = audio.currentTime;
                            const duration = audio.duration;
                            
                            // Wenn wir nahe an der erwarteten Dauer sind
                            if (duration > 0 && currentTime >= window._expectedDuration - 1.0) {{
                                window._trackEndDetected = true;
                                return true;
                            }}
                        }}
                        
                        return false;
                    }};
                    
                    // Starte kontinuierliche Prüfung
                    const checkInterval = setInterval(function() {{
                        if (window._trackEndCheck()) {{
                            clearInterval(checkInterval);
                        }}
                    }}, 200); // Prüfe alle 200ms
                    
                    window._trackEndCheckInterval = checkInterval;
                """
                
                self.driver.execute_script(js_code)
                
                while waited < max_wait and not track_ended:
                    time.sleep(0.1)  # Prüfe alle 0.1 Sekunden für schnellere Reaktion (doppelt so schnell)
                    waited += 0.1
                    
                    # Debug: Zeige Fortschritt alle 2 Sekunden
                    if int(waited * 10) % 20 == 0 and waited > 0:
                        print(f"  [DEBUG Track-Ende] Wartezeit: {waited:.1f}s / {max_wait:.1f}s")
                    
                    # Prüfe ob Aufnahme noch läuft (alle 10 Sekunden)
                    if waited - last_recording_check >= 10:
                        last_recording_check = waited
                        if self.recorder and not self.recorder.is_active():
                            print("⚠️ Aufnahme-Prozess läuft nicht mehr!")
                            track_ended = True
                            break
                    
                    # Prüfe ob richtiger Track noch spielt (Titel-Vergleich)
                    if hasattr(self, 'current_track_info') and self.current_track_info.get('title'):
                        try:
                            current_title_elem = self.driver.find_element(By.CSS_SELECTOR,
                                "h1, .track-title, [data-testid='track-title'], .track-name")
                            current_title = current_title_elem.text.strip()
                            expected_title = self.current_track_info['title']
                            
                            if current_title != expected_title:
                                print(f"  [DEBUG Track-Ende] ⚠️ Track hat sich geändert!")
                                print(f"  [DEBUG Track-Ende] Erwartet: '{expected_title}'")
                                print(f"  [DEBUG Track-Ende] Aktuell: '{current_title}'")
                                print(f"✓ Track beendet (Track hat sich geändert - falscher Track erkannt)")
                                track_ended = True
                                break
                        except:
                            pass
                    
                    # Prüfe ob Dauer erreicht wurde (falls bekannt)
                    if hasattr(self, 'current_track_info') and self.current_track_info.get('duration'):
                        try:
                            audio_state = self.driver.execute_script("""
                                const audio = document.querySelector('audio');
                                if (!audio) return {currentTime: 0, duration: 0};
                                return {currentTime: audio.currentTime, duration: audio.duration};
                            """)
                            
                            expected_duration = self.current_track_info['duration']
                            current_time = audio_state.get('currentTime', 0)
                            
                            # Wenn wir über der erwarteten Dauer sind (mit Toleranz)
                            if current_time >= expected_duration - 1.0:
                                print(f"  [DEBUG Track-Ende] Erwartete Dauer erreicht: {current_time:.1f}s / {expected_duration}s")
                                print(f"✓ Track beendet (Erwartete Dauer erreicht)")
                                track_ended = True
                                break
                        except:
                            pass
                    
                    try:
                        # Methode 0: Prüfe URL-Änderung (neuer Track = URL hat sich geändert)
                        current_url = self.driver.current_url
                        if current_url != last_url and 'track' in current_url:
                            # URL hat sich geändert - neuer Track geladen
                            print(f"  [DEBUG Track-Ende] URL geändert erkannt!")
                            print(f"  [DEBUG Track-Ende] Alte URL: {last_url}")
                            print(f"  [DEBUG Track-Ende] Neue URL: {current_url}")
                            print(f"✓ Track beendet (URL geändert: '{last_url}' -> '{current_url}')")
                            track_ended = True
                            break
                        else:
                            # Debug: Zeige URL-Status alle 2 Sekunden
                            if int(waited * 5) % 10 == 0:
                                print(f"  [DEBUG Track-Ende] URL unverändert: {current_url[:80]}...")
                        
                        # Methode 1: Prüfe JavaScript-Flag (inkl. Deezer-Erkennung)
                        track_end_detected = self.driver.execute_script("return window._trackEndDetected || false;")
                        if track_end_detected:
                            print(f"  [DEBUG Track-Ende] JavaScript-Flag erkannt: {track_end_detected}")
                            print("✓ Track beendet (JavaScript-Erkennung)")
                            track_ended = True
                            break
                        else:
                            # Debug: Zeige Status alle 2 Sekunden
                            if int(waited * 5) % 10 == 0:
                                print(f"  [DEBUG Track-Ende] JavaScript-Flag: {track_end_detected}")
                        
                        # Methode 2: Prüfe Deezer-spezifische Erkennung (Play-Button wieder sichtbar, Pause-Button weg)
                        deezer_state = self.driver.execute_script("""
                            // Prüfe auf Pause-Button
                            const pauseButtons = document.querySelectorAll(
                                'button[data-testid="pause-button"], ' +
                                'button[aria-label*="Pause"], ' +
                                'button[aria-label*="Pausieren"], ' +
                                '.control-pause'
                            );
                            
                            let pauseButtonVisible = false;
                            for (const btn of pauseButtons) {
                                if (btn.offsetParent !== null) {
                                    pauseButtonVisible = true;
                                    break;
                                }
                            }
                            
                            // Prüfe Play-Button
                            const playButton = document.querySelector('button[data-testid="play-button"]');
                            let playButtonVisible = false;
                            let isPauseButton = false;
                            
                            if (playButton && playButton.offsetParent !== null) {
                                playButtonVisible = true;
                                const ariaLabel = (playButton.getAttribute('aria-label') || '').toLowerCase();
                                isPauseButton = ariaLabel.includes('pause') || ariaLabel.includes('pausieren');
                            }
                            
                            // Track ist beendet wenn: Play-Button sichtbar UND kein Pause-Button UND Play-Button ist kein Pause-Button
                            const trackEnded = playButtonVisible && !pauseButtonVisible && !isPauseButton;
                            
                            return {
                                trackEnded: trackEnded,
                                pauseButtonVisible: pauseButtonVisible,
                                playButtonVisible: playButtonVisible,
                                isPauseButton: isPauseButton
                            };
                        """)
                        
                        # Debug: Zeige Deezer-Status alle 1 Sekunde (häufiger)
                        if int(waited * 10) % 10 == 0:
                            print(f"  [DEBUG Track-Ende] Deezer-Status: "
                                  f"trackEnded={deezer_state.get('trackEnded', False)}, "
                                  f"pauseButtonVisible={deezer_state.get('pauseButtonVisible', False)}, "
                                  f"playButtonVisible={deezer_state.get('playButtonVisible', False)}, "
                                  f"isPauseButton={deezer_state.get('isPauseButton', False)}")
                        
                        # Prüfe auch ob Pause-Button verschwunden ist (Track beendet) - PRIORITÄT 1
                        if not deezer_state.get('pauseButtonVisible', True):
                            # Pause-Button weg = Track beendet (auch wenn Play-Button noch nicht sichtbar ist)
                            print(f"  [DEBUG Track-Ende] Pause-Button verschwunden erkannt!")
                            print(f"  [DEBUG Track-Ende] pauseButtonVisible: {deezer_state.get('pauseButtonVisible', False)}")
                            print(f"  [DEBUG Track-Ende] playButtonVisible: {deezer_state.get('playButtonVisible', False)}")
                            print("✓ Track beendet (Deezer-Erkennung: Pause-Button weg)")
                            # Stoppe Track sofort (verhindert automatischen Wechsel zum nächsten Track)
                            self.driver.execute_script("""
                                // Pausiere Audio falls vorhanden
                                const audio = document.querySelector('audio');
                                if (audio) {
                                    audio.pause();
                                    audio.currentTime = 0; // Zurück zum Anfang
                                }
                                
                                // Klicke auf Pause-Button falls noch sichtbar
                                const pauseButtons = document.querySelectorAll(
                                    'button[data-testid="pause-button"], ' +
                                    'button[aria-label*="Pause"], ' +
                                    'button[aria-label*="Pausieren"]'
                                );
                                for (const btn of pauseButtons) {
                                    if (btn.offsetParent !== null) {
                                        btn.click();
                                        break;
                                    }
                                }
                                
                                // Verhindere automatischen Wechsel zum nächsten Track
                                // Deaktiviere Auto-Play falls möglich
                                if (window.DZ && window.DZ.player) {
                                    try {
                                        window.DZ.player.pause();
                                        // Verhindere Auto-Play
                                        if (window.DZ.player.setAutoplay) {
                                            window.DZ.player.setAutoplay(false);
                                        }
                                    } catch(e) {}
                                }
                                
                                // Verhindere auch über Event-Listener
                                if (window.DZ && window.DZ.Events) {
                                    try {
                                        window.DZ.Events.subscribe('player:trackEnd', function() {
                                            window.DZ.player.pause();
                                        });
                                    } catch(e) {}
                                }
                            """)
                            track_ended = True
                            break
                        
                        if deezer_state.get('trackEnded', False):
                            print(f"  [DEBUG Track-Ende] trackEnded=True erkannt!")
                            print(f"  [DEBUG Track-Ende] Deezer-State: {deezer_state}")
                            print("✓ Track beendet (Deezer-Erkennung: Play-Button wieder sichtbar, Pause-Button weg)")
                            # Stoppe Track sofort (verhindert automatischen Wechsel zum nächsten Track)
                            self.driver.execute_script("""
                                // Pausiere Audio falls vorhanden
                                const audio = document.querySelector('audio');
                                if (audio) {
                                    audio.pause();
                                    audio.currentTime = 0; // Zurück zum Anfang
                                }
                                
                                // Klicke auf Pause-Button falls noch sichtbar
                                const pauseButtons = document.querySelectorAll(
                                    'button[data-testid="pause-button"], ' +
                                    'button[aria-label*="Pause"], ' +
                                    'button[aria-label*="Pausieren"]'
                                );
                                for (const btn of pauseButtons) {
                                    if (btn.offsetParent !== null) {
                                        btn.click();
                                        break;
                                    }
                                }
                                
                                // Verhindere automatischen Wechsel zum nächsten Track
                                // Deaktiviere Auto-Play falls möglich
                                if (window.DZ && window.DZ.player) {
                                    try {
                                        window.DZ.player.pause();
                                        // Verhindere Auto-Play
                                        if (window.DZ.player.setAutoplay) {
                                            window.DZ.player.setAutoplay(false);
                                        }
                                    } catch(e) {}
                                }
                                
                                // Verhindere auch über Event-Listener
                                if (window.DZ && window.DZ.Events) {
                                    try {
                                        window.DZ.Events.subscribe('player:trackEnd', function() {
                                            window.DZ.player.pause();
                                        });
                                    } catch(e) {}
                                }
                            """)
                            track_ended = True
                            break
                        
                        # Methode 3: Prüfe ob Track-Titel sich geändert hat (neuer Track gestartet)
                        try:
                            track_title_elem = self.driver.find_element(By.CSS_SELECTOR, 
                                "h1, .track-title, [data-testid='track-title'], .track-name")
                            current_track_title = track_title_elem.text.strip()
                            
                            if last_track_title and current_track_title and current_track_title != last_track_title:
                                print(f"  [DEBUG Track-Ende] Track-Titel geändert erkannt!")
                                print(f"  [DEBUG Track-Ende] Alter Titel: '{last_track_title}'")
                                print(f"  [DEBUG Track-Ende] Neuer Titel: '{current_track_title}'")
                                print(f"✓ Track beendet (Track-Titel geändert: '{last_track_title}' -> '{current_track_title}')")
                                # Stoppe sofort (verhindert dass neuer Track weiterläuft)
                                self.driver.execute_script("""
                                    // Pausiere Audio falls vorhanden
                                    const audio = document.querySelector('audio');
                                    if (audio) {
                                        audio.pause();
                                        audio.currentTime = 0; // Zurück zum Anfang
                                    }
                                    
                                    // Klicke auf Pause-Button falls noch sichtbar
                                    const pauseButtons = document.querySelectorAll(
                                        'button[data-testid="pause-button"], ' +
                                        'button[aria-label*="Pause"], ' +
                                        'button[aria-label*="Pausieren"]'
                                    );
                                    for (const btn of pauseButtons) {
                                        if (btn.offsetParent !== null) {
                                            btn.click();
                                            break;
                                        }
                                    }
                                    
                                    // Verhindere automatischen Wechsel zum nächsten Track
                                    if (window.DZ && window.DZ.player) {
                                        try {
                                            window.DZ.player.pause();
                                        } catch(e) {}
                                    }
                                """)
                                track_ended = True
                                break
                        except:
                            pass
                        
                        # Methode 3.5: Prüfe ob wir nahe am Ende sind (proaktives Stoppen)
                        if audio_state.get('duration', 0) > 0:
                            current_time = audio_state.get('currentTime', 0)
                            duration = audio_state.get('duration', 0)
                            
                            # Wenn wir in den letzten 2 Sekunden sind, prüfe häufiger
                            if duration > 0 and current_time >= duration - 2.0:
                                # Prüfe ob Pause-Button noch sichtbar ist
                                if not deezer_state.get('pauseButtonVisible', False):
                                    # Pause-Button weg = Track beendet
                                    print(f"✓ Track beendet (nahe am Ende, Pause-Button weg: {current_time:.1f}s / {duration:.1f}s)")
                                    track_ended = True
                                    break
                        
                        # Methode 4: Prüfe Audio-Element direkt
                        audio_state = self.driver.execute_script("""
                            const audio = document.querySelector('audio');
                            if (!audio) return {ended: false, currentTime: 0, duration: 0, paused: true};
                            
                            return {
                                ended: audio.ended,
                                currentTime: audio.currentTime,
                                duration: audio.duration,
                                paused: audio.paused
                            };
                        """)
                        
                        if audio_state['ended']:
                            print("✓ Track beendet (Audio-Element: ended=true)")
                            track_ended = True
                            break
                        
                        # Methode 3: Prüfe ob wir am Ende sind (auch bei Wiederholung)
                        if audio_state['duration'] > 0:
                            current_time = audio_state['currentTime']
                            duration = audio_state['duration']
                            
                            # Wenn wir sehr nah am Ende sind (letzte 0.5 Sekunden)
                            if current_time >= duration - 0.5:
                                # Warte kurz und prüfe ob Track wiederholt wurde oder beendet ist
                                time.sleep(0.6)
                                new_state = self.driver.execute_script("""
                                    const audio = document.querySelector('audio');
                                    if (!audio) return {ended: false, currentTime: 0};
                                    return {ended: audio.ended, currentTime: audio.currentTime};
                                """)
                                
                                if new_state['ended']:
                                    print("✓ Track beendet (am Ende erkannt)")
                                    track_ended = True
                                    # Stoppe Track automatisch
                                    self.driver.execute_script("""
                                        const audio = document.querySelector('audio');
                                        if (audio) audio.pause();
                                    """)
                                    break
                                elif new_state['currentTime'] < 1.0:
                                    # Track wurde wiederholt - ein Durchlauf ist beendet
                                    print("✓ Track-Durchlauf beendet (Wiederholung erkannt)")
                                    track_ended = True
                                    # Stoppe Track automatisch
                                    self.driver.execute_script("""
                                        const audio = document.querySelector('audio');
                                        if (audio) audio.pause();
                                    """)
                                    break
                            
                            # Prüfe ob Position sich nicht ändert (Track hängt)
                            if abs(current_time - last_position) < 0.1:
                                position_unchanged_count += 1
                                if position_unchanged_count > 10:  # 5 Sekunden keine Bewegung
                                    print("⚠️ Track scheint zu hängen, stoppe Aufnahme")
                                    track_ended = True
                                    # Stoppe Track automatisch
                                    self.driver.execute_script("""
                                        const audio = document.querySelector('audio');
                                        if (audio) audio.pause();
                                    """)
                                    break
                            else:
                                position_unchanged_count = 0
                                last_position = current_time
                        
                        # Methode 4: Prüfe Play-Button-Status (als Fallback)
                        try:
                            play_button = self.driver.find_element(By.CSS_SELECTOR, 
                                "button[data-testid='play-button'], button[aria-label*='Play'], button[aria-label*='Wiedergabe']")
                            aria_label = play_button.get_attribute("aria-label") or ""
                            
                            # Wenn Play-Button sichtbar ist und nicht "Pause" sagt
                            if play_button.is_displayed() and "play" in aria_label.lower() and "pause" not in aria_label.lower():
                                # Prüfe nochmal ob Audio wirklich beendet ist
                                audio_ended = self.driver.execute_script("""
                                    const audio = document.querySelector('audio');
                                    return audio ? audio.ended : false;
                                """)
                                
                                if audio_ended:
                                    print("✓ Track beendet (Play-Button)")
                                    track_ended = True
                                    # Stoppe Track automatisch
                                    self.driver.execute_script("""
                                        const audio = document.querySelector('audio');
                                        if (audio) audio.pause();
                                    """)
                                    break
                        except:
                            pass
                            
                    except Exception as e:
                        # Ignoriere Fehler und prüfe weiter
                        pass
                
                # Stoppe JavaScript-Interval
                try:
                    self.driver.execute_script("""
                        if (window._trackEndCheckInterval) {
                            clearInterval(window._trackEndCheckInterval);
                        }
                    """)
                except:
                    pass
                
                if not track_ended and waited >= max_wait:
                    print("⚠️ Maximale Wartezeit erreicht, stoppe Aufnahme")
            
            # Prüfe ob Browser noch reagiert
            try:
                self.driver.current_url  # Einfacher Test ob Browser noch reagiert
            except Exception as e:
                print(f"⚠️ Browser reagiert nicht mehr: {e}")
                # Versuche Browser neu zu starten falls nötig
                try:
                    self.cleanup()
                    if not self.setup_browser():
                        print("❌ Konnte Browser nicht neu starten")
                except:
                    pass
            
            # Stoppe Aufnahme
            print("🛑 Stoppe Aufnahme...")
            if not self.recorder.stop_recording():
                print("⚠️ Aufnahme-Stopp fehlgeschlagen, versuche erneut...")
                # Versuche erneut zu stoppen
                time.sleep(1)
                if not self.recorder.stop_recording():
                    print("❌ Aufnahme konnte nicht gestoppt werden")
                    # Versuche ffmpeg-Prozess direkt zu beenden
                    try:
                        if self.recorder.recording_process:
                            self.recorder.recording_process.terminate()
                            time.sleep(0.5)
                            if self.recorder.recording_process.poll() is None:
                                self.recorder.recording_process.kill()
                    except:
                        pass
                    return False
            
            # Prüfe ob Datei erstellt wurde und nicht leer ist
            if not self.output_path.exists():
                print("❌ Aufnahme-Datei wurde nicht erstellt")
                return False
            
            file_size = self.output_path.stat().st_size
            if file_size < 10 * 1024:  # Mindestens 10 KB
                print(f"⚠️ Aufnahme-Datei ist sehr klein ({file_size / 1024:.1f} KB) - möglicherweise unvollständig")
                # Versuche trotzdem weiter
            else:
                print(f"✓ Aufnahme-Datei erstellt: {file_size / 1024 / 1024:.2f} MB")
            
            # Normalisiere Geschwindigkeit (zurück auf 1x)
            print(f"🔄 Normalisiere Geschwindigkeit (zurück auf 1x)...")
            if not self.normalize_speed():
                print("⚠️ Normalisierung fehlgeschlagen, verwende Original-Datei")
            
            # Füge Metadaten hinzu
            if track_info and self.output_path.exists():
                print("📝 Füge Metadaten hinzu...")
                try:
                    self._add_metadata(track_info)
                except Exception as e:
                    print(f"⚠️ Metadaten konnten nicht hinzugefügt werden: {e}")
                    # Nicht kritisch, Datei ist trotzdem vorhanden
            
            # Finale Validierung
            if self.output_path.exists() and self.output_path.stat().st_size > 10 * 1024:
                print("✅ Aufnahme erfolgreich abgeschlossen!")
                return True
            else:
                print("❌ Aufnahme-Datei ist unvollständig oder fehlt")
                return False
            
        except Exception as e:
            print(f"❌ Fehler bei automatischer Aufnahme: {e}")
            import traceback
            traceback.print_exc()
            if self.recorder:
                self.recorder.stop_recording()
            return False
        finally:
            self.cleanup()
    
    def normalize_speed(self) -> bool:
        """
        Normalisiert die Geschwindigkeit der aufgenommenen Datei zurück auf 1x
        
        Returns:
            True bei Erfolg
        """
        try:
            if not self.output_path.exists():
                print("❌ Aufnahme-Datei existiert nicht")
                return False
            
            # Erstelle temporäre Datei
            temp_path = self.output_path.with_suffix('.temp.mp3')
            
            # Verwende ffmpeg um Geschwindigkeit zu normalisieren
            # Die Datei wurde bei 2x aufgenommen, also müssen wir sie auf 0.5x verlangsamen
            # um wieder normale Geschwindigkeit zu bekommen
            speed_factor = 1.0 / self.playback_speed
            
            cmd = [
                "ffmpeg",
                "-i", str(self.output_path),
                "-filter:a", f"atempo={speed_factor}",
                "-acodec", "libmp3lame",
                "-ab", "320k",
                "-y",
                str(temp_path)
            ]
            
            print(f"🔄 Normalisiere Geschwindigkeit mit ffmpeg...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0 and temp_path.exists():
                # Ersetze Original-Datei
                self.output_path.unlink()
                temp_path.rename(self.output_path)
                print(f"✓ Geschwindigkeit normalisiert: {self.output_path}")
                return True
            else:
                print(f"⚠️ Normalisierung fehlgeschlagen, verwende Original-Datei")
                if temp_path.exists():
                    temp_path.unlink()
                return True  # Verwende Original-Datei
            
        except Exception as e:
            print(f"⚠️ Fehler bei Normalisierung: {e}")
            return True  # Verwende Original-Datei trotzdem
    
    def _get_deezer_track_info(self, url: str) -> Optional[Dict]:
        """Ruft Track-Informationen von Deezer API ab"""
        try:
            import re
            import requests
            
            # Extrahiere Track-ID aus URL
            track_id_match = re.search(r'deezer\.com/(?:[a-z]{2}/)?track/(\d+)', url)
            if not track_id_match:
                return None
            
            track_id = track_id_match.group(1)
            
            # Rufe Deezer API auf
            api_url = f"https://api.deezer.com/track/{track_id}"
            response = requests.get(api_url, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"⚠️ Konnte Track-Info nicht abrufen: {e}")
        
        return None
    
    def _add_metadata(self, track_info: Dict):
        """Fügt Metadaten zur MP3-Datei hinzu"""
        try:
            from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, APIC
            from mutagen.mp3 import MP3
            import requests
            
            if not self.output_path.exists():
                print("⚠️ Aufnahme-Datei existiert nicht")
                return
            
            audio = MP3(str(self.output_path), ID3=ID3)
            
            # Erstelle ID3-Tags falls nicht vorhanden
            try:
                audio.add_tags()
            except:
                pass
            
            # Titel
            if 'title' in track_info:
                audio['TIT2'] = TIT2(encoding=3, text=track_info['title'])
                print(f"  ✓ Titel: {track_info['title']}")
            
            # Künstler
            if 'artist' in track_info and 'name' in track_info['artist']:
                audio['TPE1'] = TPE1(encoding=3, text=track_info['artist']['name'])
                print(f"  ✓ Künstler: {track_info['artist']['name']}")
            
            # Album
            if 'album' in track_info and 'title' in track_info['album']:
                audio['TALB'] = TALB(encoding=3, text=track_info['album']['title'])
                print(f"  ✓ Album: {track_info['album']['title']}")
            
            # Jahr
            if 'album' in track_info and 'release_date' in track_info['album']:
                year = track_info['album']['release_date'][:4]
                audio['TDRC'] = TDRC(encoding=3, text=year)
                print(f"  ✓ Jahr: {year}")
            
            # Cover-Art
            cover_art = None
            if 'album' in track_info and 'cover_medium' in track_info['album']:
                try:
                    cover_url = track_info['album']['cover_medium']
                    response = requests.get(cover_url, timeout=10)
                    if response.status_code == 200:
                        cover_art = response.content
                        audio['APIC'] = APIC(
                            encoding=3,
                            mime='image/jpeg',
                            type=3,
                            desc='Cover',
                            data=cover_art
                        )
                        print(f"  ✓ Cover-Art hinzugefügt")
                except Exception as e:
                    print(f"  ⚠️ Konnte Cover-Art nicht laden: {e}")
            
            # Benenne Datei um (mit Künstler und Titel)
            if 'title' in track_info and 'artist' in track_info and 'name' in track_info['artist']:
                import re
                def sanitize_filename(name: str) -> str:
                    invalid_chars = '<>:"/\\|?*'
                    for char in invalid_chars:
                        name = name.replace(char, '_')
                    return name.strip('. ')
                
                artist = sanitize_filename(track_info['artist']['name'])
                title = sanitize_filename(track_info['title'])
                new_filename = f"{artist} - {title}.mp3"
                new_path = self.output_path.parent / new_filename
                
                if new_path != self.output_path:
                    audio.save()  # Speichere Metadaten zuerst
                    self.output_path.rename(new_path)
                    self.output_path = new_path
                    print(f"  ✓ Datei umbenannt: {new_filename}")
                else:
                    audio.save()
            else:
                audio.save()
            
            print("✓ Metadaten erfolgreich hinzugefügt")
            
        except Exception as e:
            print(f"⚠️ Fehler beim Hinzufügen der Metadaten: {e}")
            import traceback
            traceback.print_exc()
    
    def cleanup(self):
        """Räumt auf"""
        if self.recorder:
            try:
                self.recorder.stop_recording()
            except:
                pass
        
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
