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
            for attempt in range(5):  # Maximal 5 Versuche
                try:
                    # Versuche verschiedene Selektoren
                    play_selectors = [
                        "button[data-testid='play-button']",
                        "button[aria-label*='Play']",
                        "button[aria-label*='Wiedergabe']",
                        ".control-play",
                        "button.play-button",
                        "[data-testid='play']",
                        "button[title*='Play']"
                    ]
                    
                    for selector in play_selectors:
                        try:
                            play_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )
                            if play_button.is_displayed():
                                # Scroll zu Button falls nötig
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", play_button)
                                time.sleep(0.3)
                                
                                # Klicke mit JavaScript (zuverlässiger)
                                self.driver.execute_script("arguments[0].click();", play_button)
                                print(f"▶️ Play-Button geklickt (Versuch {attempt + 1}, Selektor: {selector})")
                                time.sleep(1)
                                
                                # Prüfe ob es funktioniert hat
                                is_playing = self.driver.execute_script("""
                                    const audio = document.querySelector('audio');
                                    return audio ? (!audio.paused && audio.currentTime > 0) : false;
                                """)
                                
                                if is_playing:
                                    print("✓ Track spielt jetzt")
                                    play_clicked = True
                                    break
                        except:
                            continue
                    
                    if play_clicked:
                        break
                    
                    # Fallback: Direktes JavaScript-Klicken
                    if not play_clicked:
                        self.driver.execute_script("""
                            // Versuche verschiedene Methoden
                            const selectors = [
                                'button[data-testid="play-button"]',
                                'button[aria-label*="Play"]',
                                'button[aria-label*="Wiedergabe"]',
                                '.control-play',
                                'button.play-button'
                            ];
                            
                            for (const selector of selectors) {
                                const btn = document.querySelector(selector);
                                if (btn && btn.offsetParent !== null) {
                                    btn.click();
                                    break;
                                }
                            }
                            
                            // Versuche auch über Audio-Element
                            const audio = document.querySelector('audio');
                            if (audio && audio.paused) {
                                audio.play();
                            }
                        """)
                        time.sleep(1)
                        
                        # Prüfe nochmal
                        is_playing = self.driver.execute_script("""
                            const audio = document.querySelector('audio');
                            return audio ? (!audio.paused && audio.currentTime > 0) : false;
                        """)
                        
                        if is_playing:
                            print("✓ Track spielt jetzt (JavaScript-Fallback)")
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
                print("   Bitte klicken Sie manuell auf Play")
                # Warte auf manuelles Klicken
                max_wait_manual = 30  # 30 Sekunden
                waited_manual = 0
                while waited_manual < max_wait_manual:
                    time.sleep(1)
                    waited_manual += 1
                    is_playing = self.driver.execute_script("""
                        const audio = document.querySelector('audio');
                        return audio ? (!audio.paused && audio.currentTime > 0) : false;
                    """)
                    if is_playing:
                        print("✓ Track spielt jetzt (manuell gestartet)")
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
            
            if not self.recorder.start_recording():
                print("❌ Konnte Audio-Aufnahme nicht starten")
                return False
            
            # Starte Browser und spiele Track ab
            if provider.lower() == "spotify":
                if not self.play_spotify_track(url, duration):
                    self.recorder.stop_recording()
                    return False
            elif provider.lower() == "deezer":
                if not self.play_deezer_track(url, duration):
                    self.recorder.stop_recording()
                    return False
            else:
                print(f"❌ Unbekannter Provider: {provider}")
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
                max_wait = 600  # Maximal 10 Minuten
                waited = 0
                track_ended = False
                last_position = 0
                position_unchanged_count = 0
                
                # JavaScript-Funktion für Track-Ende-Erkennung (auch bei Wiederholung)
                self.driver.execute_script("""
                    window._trackEndDetected = false;
                    window._lastTrackTime = 0;
                    window._trackEndCheck = function() {
                        const audio = document.querySelector('audio');
                        if (!audio) return false;
                        
                        const currentTime = audio.currentTime;
                        const duration = audio.duration;
                        
                        // Prüfe ob Track beendet ist
                        if (audio.ended) {
                            window._trackEndDetected = true;
                            return true;
                        }
                        
                        // Prüfe ob wir am Ende sind (auch bei Wiederholung)
                        // Wenn currentTime nahe bei duration ist und dann zurück springt, ist ein Durchlauf beendet
                        if (duration > 0 && currentTime >= duration - 0.5) {
                            // Track ist am Ende - warte kurz ob er wiederholt wird
                            setTimeout(function() {
                                if (audio.currentTime < 0.5) {
                                    // Track wurde wiederholt - ein Durchlauf ist beendet
                                    window._trackEndDetected = true;
                                } else if (audio.ended) {
                                    // Track ist wirklich beendet
                                    window._trackEndDetected = true;
                                }
                            }, 500);
                            return true;
                        }
                        
                        return false;
                    };
                    
                    // Starte kontinuierliche Prüfung
                    const checkInterval = setInterval(function() {
                        if (window._trackEndCheck()) {
                            clearInterval(checkInterval);
                        }
                    }, 200); // Prüfe alle 200ms
                    
                    window._trackEndCheckInterval = checkInterval;
                """)
                
                while waited < max_wait and not track_ended:
                    time.sleep(0.5)  # Prüfe alle 0.5 Sekunden für schnellere Reaktion
                    waited += 0.5
                    
                    try:
                        # Methode 1: Prüfe JavaScript-Flag
                        track_end_detected = self.driver.execute_script("return window._trackEndDetected || false;")
                        if track_end_detected:
                            print("✓ Track beendet (JavaScript-Erkennung)")
                            track_ended = True
                            break
                        
                        # Methode 2: Prüfe Audio-Element direkt
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
            
            # Stoppe Aufnahme
            print("🛑 Stoppe Aufnahme...")
            if not self.recorder.stop_recording():
                return False
            
            # Normalisiere Geschwindigkeit (zurück auf 1x)
            print(f"🔄 Normalisiere Geschwindigkeit (zurück auf 1x)...")
            if not self.normalize_speed():
                print("⚠️ Normalisierung fehlgeschlagen, verwende Original-Datei")
            
            # Füge Metadaten hinzu
            if track_info and self.output_path.exists():
                print("📝 Füge Metadaten hinzu...")
                self._add_metadata(track_info)
            
            return True
            
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
