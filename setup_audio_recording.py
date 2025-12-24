#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup-Skript für Audio-Aufnahme-Funktionalität
Automatisiert Installation und Konfiguration
"""

import subprocess
import sys
import os
import platform
from pathlib import Path
from typing import Tuple, List, Dict


class AudioRecordingSetup:
    """Klasse für automatisches Setup der Audio-Aufnahme"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.issues: List[str] = []
        self.fixes: List[str] = []
        
    def check_python_packages(self) -> Tuple[bool, List[str]]:
        """Prüft ob alle benötigten Python-Pakete installiert sind"""
        required_packages = {
            'selenium': 'selenium',
            'requests': 'requests'
        }
        
        missing = []
        for package, pip_name in required_packages.items():
            try:
                __import__(package)
            except ImportError:
                missing.append(pip_name)
        
        return len(missing) == 0, missing
    
    def install_python_packages(self, packages: List[str]) -> bool:
        """Installiert fehlende Python-Pakete"""
        if not packages:
            return True
        
        try:
            print(f"📦 Installiere fehlende Pakete: {', '.join(packages)}")
            cmd = [sys.executable, "-m", "pip", "install"] + packages
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✓ Pakete erfolgreich installiert")
                return True
            else:
                print(f"❌ Fehler bei Installation: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Fehler bei Installation: {e}")
            return False
    
    def check_chrome_driver(self) -> Tuple[bool, str]:
        """Prüft ob Chrome/Chromium und ChromeDriver verfügbar sind"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            
            # Prüfe ob Chrome installiert ist
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            try:
                driver = webdriver.Chrome(options=chrome_options)
                driver.quit()
                return True, "Chrome und ChromeDriver sind verfügbar"
            except Exception as e:
                error_msg = str(e)
                if "chromedriver" in error_msg.lower() or "executable" in error_msg.lower():
                    return False, "ChromeDriver nicht gefunden. Installiere automatisch..."
                else:
                    return False, f"Chrome nicht verfügbar: {error_msg}"
        except ImportError:
            return False, "Selenium nicht installiert"
    
    def install_chromedriver(self) -> bool:
        """Installiert ChromeDriver automatisch"""
        try:
            print("🔧 Installiere ChromeDriver...")
            # Verwende webdriver-manager falls verfügbar
            try:
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                
                # Teste Installation
                service = Service(ChromeDriverManager().install())
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Chrome(service=service, options=options)
                driver.quit()
                
                print("✓ ChromeDriver erfolgreich installiert")
                return True
            except ImportError:
                # Installiere webdriver-manager
                print("📦 Installiere webdriver-manager...")
                subprocess.run([sys.executable, "-m", "pip", "install", "webdriver-manager"], 
                             capture_output=True, timeout=60)
                
                # Versuche erneut
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                
                service = Service(ChromeDriverManager().install())
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                
                options = Options()
                options.add_argument('--headless')
                driver = webdriver.Chrome(service=service, options=options)
                driver.quit()
                
                print("✓ ChromeDriver erfolgreich installiert")
                return True
        except Exception as e:
            print(f"⚠️ Automatische ChromeDriver-Installation fehlgeschlagen: {e}")
            print("   Bitte installieren Sie ChromeDriver manuell:")
            print("   https://chromedriver.chromium.org/downloads")
            return False
    
    def check_ffmpeg(self) -> Tuple[bool, str]:
        """Prüft ob ffmpeg verfügbar ist"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True, "ffmpeg ist verfügbar"
            else:
                return False, "ffmpeg nicht gefunden"
        except FileNotFoundError:
            return False, "ffmpeg nicht installiert"
        except Exception as e:
            return False, f"Fehler bei ffmpeg-Prüfung: {e}"
    
    def check_audio_capture(self) -> Tuple[bool, str, List[str]]:
        """Prüft ob System-Audio-Aufnahme konfiguriert ist"""
        instructions = []
        
        if self.system == "windows":
            # Prüfe ob Stereo Mix verfügbar ist
            try:
                result = subprocess.run(
                    ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "Stereo Mix" in result.stderr:
                    return True, "Stereo Mix ist verfügbar", []
                else:
                    instructions = [
                        "1. Rechtsklick auf Lautsprecher-Symbol in der Taskleiste",
                        "2. Wähle 'Sounds' oder 'Ton-Einstellungen'",
                        "3. Gehe zu 'Aufnahme' Tab",
                        "4. Rechtsklick auf leeren Bereich → 'Deaktivierte Geräte anzeigen'",
                        "5. Rechtsklick auf 'Stereo Mix' → 'Aktivieren'",
                        "6. Setze 'Stereo Mix' als Standard-Aufnahmegerät"
                    ]
                    return False, "Stereo Mix ist nicht aktiviert", instructions
            except:
                instructions = [
                    "1. Aktivieren Sie 'Stereo Mix' in Windows Sound-Einstellungen",
                    "2. Rechtsklick auf Lautsprecher → Sounds → Aufnahme → Stereo Mix aktivieren"
                ]
                return False, "Konnte Stereo Mix nicht prüfen", instructions
        
        elif self.system == "darwin":  # macOS
            # Prüfe ob BlackHole installiert ist
            try:
                result = subprocess.run(
                    ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if "BlackHole" in result.stderr:
                    return True, "BlackHole ist verfügbar", []
                else:
                    instructions = [
                        "1. Installiere BlackHole: https://github.com/ExistentialAudio/BlackHole",
                        "2. Oder verwende: brew install blackhole-2ch",
                        "3. Erstelle Multi-Output Device in Audio MIDI Setup:",
                        "   - Öffne 'Audio MIDI Setup' (Spotlight: Cmd+Space → 'Audio MIDI Setup')",
                        "   - Klicke auf '+' → 'Multi-Output Device erstellen'",
                        "   - Aktiviere 'Built-in Output' und 'BlackHole 2ch'",
                        "   - Setze Multi-Output Device als Standard-Ausgabegerät"
                    ]
                    return False, "BlackHole ist nicht installiert", instructions
            except:
                instructions = [
                    "1. Installiere BlackHole für System-Audio-Aufnahme",
                    "2. https://github.com/ExistentialAudio/BlackHole"
                ]
                return False, "Konnte BlackHole nicht prüfen", instructions
        
        elif self.system == "linux":
            # Linux verwendet normalerweise PulseAudio
            try:
                result = subprocess.run(
                    ["pulseaudio", "--check"],
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    return True, "PulseAudio ist verfügbar", []
                else:
                    instructions = [
                        "1. Installiere PulseAudio: sudo apt-get install pulseaudio",
                        "2. Oder: sudo yum install pulseaudio"
                    ]
                    return False, "PulseAudio nicht gefunden", instructions
            except:
                instructions = [
                    "1. Installiere PulseAudio für System-Audio-Aufnahme",
                    "2. sudo apt-get install pulseaudio"
                ]
                return False, "Konnte PulseAudio nicht prüfen", instructions
        
        return False, "Unbekanntes System", []
    
    def run_full_setup(self) -> Dict[str, bool]:
        """Führt vollständiges Setup durch"""
        results = {
            'python_packages': False,
            'chrome_driver': False,
            'ffmpeg': False,
            'audio_capture': False
        }
        
        print("=" * 70)
        print("Audio-Aufnahme Setup")
        print("=" * 70)
        print()
        
        # 1. Python-Pakete prüfen und installieren
        print("1️⃣ Prüfe Python-Pakete...")
        packages_ok, missing = self.check_python_packages()
        if not packages_ok:
            print(f"   ⚠️ Fehlende Pakete: {', '.join(missing)}")
            if self.install_python_packages(missing):
                packages_ok = True
        results['python_packages'] = packages_ok
        print(f"   {'✓' if packages_ok else '✗'} Python-Pakete: {'OK' if packages_ok else 'FEHLER'}")
        print()
        
        # 2. Chrome/ChromeDriver prüfen
        print("2️⃣ Prüfe Chrome/ChromeDriver...")
        chrome_ok, chrome_msg = self.check_chrome_driver()
        if not chrome_ok:
            print(f"   ⚠️ {chrome_msg}")
            if "ChromeDriver" in chrome_msg:
                if self.install_chromedriver():
                    chrome_ok, _ = self.check_chrome_driver()
        results['chrome_driver'] = chrome_ok
        print(f"   {'✓' if chrome_ok else '✗'} Chrome/ChromeDriver: {'OK' if chrome_ok else 'FEHLER'}")
        print()
        
        # 3. ffmpeg prüfen
        print("3️⃣ Prüfe ffmpeg...")
        ffmpeg_ok, ffmpeg_msg = self.check_ffmpeg()
        if not ffmpeg_ok:
            print(f"   ⚠️ {ffmpeg_msg}")
            print("   Installations-Anleitung:")
            if self.system == "windows":
                print("   - Download: https://ffmpeg.org/download.html")
                print("   - Oder: choco install ffmpeg")
            elif self.system == "darwin":
                print("   - brew install ffmpeg")
            elif self.system == "linux":
                print("   - sudo apt-get install ffmpeg")
        results['ffmpeg'] = ffmpeg_ok
        print(f"   {'✓' if ffmpeg_ok else '✗'} ffmpeg: {'OK' if ffmpeg_ok else 'FEHLT'}")
        print()
        
        # 4. System-Audio-Aufnahme prüfen
        print("4️⃣ Prüfe System-Audio-Aufnahme...")
        audio_ok, audio_msg, instructions = self.check_audio_capture()
        if not audio_ok:
            print(f"   ⚠️ {audio_msg}")
            if instructions:
                print("   Konfigurations-Anleitung:")
                for instruction in instructions:
                    print(f"   {instruction}")
        results['audio_capture'] = audio_ok
        print(f"   {'✓' if audio_ok else '✗'} System-Audio: {'OK' if audio_ok else 'KONFIGURIEREN'}")
        print()
        
        # Zusammenfassung
        print("=" * 70)
        print("Setup-Zusammenfassung:")
        print("=" * 70)
        all_ok = all(results.values())
        
        for key, value in results.items():
            status = "✓ OK" if value else "✗ FEHLT"
            print(f"  {key.replace('_', ' ').title()}: {status}")
        
        print()
        if all_ok:
            print("🎉 Alle Komponenten sind bereit! Audio-Aufnahme kann verwendet werden.")
        else:
            print("⚠️ Einige Komponenten fehlen noch. Bitte folgen Sie den Anweisungen oben.")
        
        return results


def run_setup():
    """Hauptfunktion für Setup"""
    setup = AudioRecordingSetup()
    return setup.run_full_setup()


if __name__ == "__main__":
    run_setup()
