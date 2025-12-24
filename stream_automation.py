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
    
    def __init__(self, output_path: Path, playback_speed: float = 2.0):
        """
        Initialisiert die Stream-Automatisierung
        
        Args:
            output_path: Pfad zur Ausgabedatei
            playback_speed: Wiedergabegeschwindigkeit (2.0 = doppelt so schnell)
        """
        self.output_path = Path(output_path)
        self.playback_speed = playback_speed
        self.driver: Optional[webdriver.Chrome] = None
        self.recorder: Optional[AudioRecorder] = None
        self.is_playing = False
        
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
            print(f"🌐 Öffne Deezer: {url}")
            self.driver.get(url)
            time.sleep(3)  # Warte auf Seitenladung
            
            # Warte auf Play-Button und klicke ihn
            try:
                play_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='play-button'], .control-play, button.play-button"))
                )
                play_button.click()
                print("▶️ Play-Button geklickt")
                time.sleep(2)
            except:
                # Versuche mit JavaScript
                self.driver.execute_script("document.querySelector('button[data-testid=\"play-button\"]')?.click()")
                time.sleep(2)
            
            # Setze Geschwindigkeit auf 2x
            try:
                self.driver.execute_script(f"""
                    const audio = document.querySelector('audio');
                    if (audio) {{
                        audio.playbackRate = {self.playback_speed};
                    }}
                """)
                print(f"⚡ Geschwindigkeit auf {self.playback_speed}x gesetzt")
            except:
                print(f"⚠️ Konnte Geschwindigkeit nicht automatisch setzen")
            
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
                               duration: Optional[float] = None) -> bool:
        """
        Nimmt automatisch Audio auf während der Wiedergabe
        
        Args:
            url: URL des Tracks
            provider: "spotify" oder "deezer"
            duration: Erwartete Dauer (None = automatisch)
            
        Returns:
            True bei Erfolg
        """
        try:
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
                # Warte auf Track-Ende (prüfe ob noch läuft)
                print("⏳ Warte auf Track-Ende...")
                max_wait = 600  # Maximal 10 Minuten
                waited = 0
                while waited < max_wait:
                    time.sleep(5)
                    waited += 5
                    # Prüfe ob Track noch läuft (vereinfacht)
                    try:
                        # Versuche Play-Button-Status zu prüfen
                        play_button = self.driver.find_element(By.CSS_SELECTOR, "button[data-testid='play-button']")
                        if play_button.get_attribute("aria-label") and "play" in play_button.get_attribute("aria-label").lower():
                            # Track ist beendet (Play-Button ist wieder sichtbar)
                            print("✓ Track beendet")
                            break
                    except:
                        pass
                
                if waited >= max_wait:
                    print("⚠️ Maximale Wartezeit erreicht, stoppe Aufnahme")
            
            # Stoppe Aufnahme
            print("🛑 Stoppe Aufnahme...")
            if not self.recorder.stop_recording():
                return False
            
            # Normalisiere Geschwindigkeit (zurück auf 1x)
            print(f"🔄 Normalisiere Geschwindigkeit (zurück auf 1x)...")
            return self.normalize_speed()
            
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
