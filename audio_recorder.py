#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Recorder für DRM-geschützte Streams
Nimmt Audio während der Wiedergabe auf (nur für privaten Gebrauch)

⚠️ WICHTIG: Nur für privaten Gebrauch!
Diese Funktion dient ausschließlich zur Aufnahme von gekauften/abonnierten Inhalten für persönliche Nutzung.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional, Callable
import threading
import time

# Import Audio-Device-Detektor
try:
    from audio_device_detector import AudioDeviceDetector
    DEVICE_DETECTOR_AVAILABLE = True
except ImportError:
    DEVICE_DETECTOR_AVAILABLE = False
    AudioDeviceDetector = None


class AudioRecorder:
    """Klasse für Audio-Aufnahme während der Wiedergabe"""
    
    def __init__(self, output_path: Path, sample_rate: int = 44100, channels: int = 2):
        """
        Initialisiert den Audio-Recorder
        
        Args:
            output_path: Pfad zur Ausgabedatei
            sample_rate: Sample-Rate (Standard: 44100 Hz)
            channels: Anzahl Kanäle (Standard: 2 = Stereo)
        """
        self.output_path = Path(output_path)
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.recording_process = None
        self.progress_callback: Optional[Callable[[float], None]] = None
        
    def start_recording(self, duration: Optional[float] = None, playback_speed: float = 1.0) -> bool:
        """
        Startet die Audio-Aufnahme
        
        Args:
            duration: Aufnahmedauer in Sekunden (None = unbegrenzt)
            playback_speed: Wiedergabegeschwindigkeit (1.0 = normal, 2.0 = doppelt so schnell)
                           HINWEIS: Die Geschwindigkeit muss in der Wiedergabe-App eingestellt werden!
            
        Returns:
            True wenn Aufnahme gestartet wurde
        """
        if self.is_recording:
            return False
        
        try:
            # Prüfe ob ffmpeg verfügbar ist
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5
            )
            if result.returncode != 0:
                print("❌ ffmpeg ist nicht verfügbar. Bitte installieren Sie ffmpeg.")
                return False
            
            # Erstelle Ausgabeverzeichnis
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Baue ffmpeg-Kommando für Audio-Aufnahme
            # Aufnahme vom Standard-Audio-Input (System-Audio)
            # HINWEIS: playback_speed wird hier nicht verwendet, da die Geschwindigkeit
            # in der Wiedergabe-App (Spotify/Deezer) eingestellt werden muss
            
            # Erkenne automatisch das richtige Audio-Device
            audio_device = None
            device_info = "Standard-Device"
            
            if DEVICE_DETECTOR_AVAILABLE:
                try:
                    audio_device, device_info = AudioDeviceDetector.detect_audio_device()
                    if audio_device:
                        print(f"🎤 Audio-Device erkannt: {device_info}")
                except Exception as e:
                    print(f"⚠️ Fehler bei Device-Erkennung: {e}, verwende Standard")
            
            # Für Linux: PulseAudio
            if sys.platform.startswith("linux"):
                if audio_device and audio_device.startswith("pulse:"):
                    device_input = audio_device
                else:
                    device_input = "pulse:default"
                
                cmd = [
                    "ffmpeg",
                    "-f", "pulse",
                    "-i", device_input,
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-acodec", "libmp3lame",
                    "-ab", "320k",
                    "-y",
                    str(self.output_path)
                ]
            
            # Für macOS: Verwende BlackHole oder ähnliches für System-Audio-Aufnahme
            elif sys.platform == "darwin":
                if audio_device and audio_device.startswith(":"):
                    device_input = audio_device
                else:
                    device_input = ":0"  # Fallback: System-Audio
                
                cmd = [
                    "ffmpeg",
                    "-f", "avfoundation",
                    "-i", device_input,
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-acodec", "libmp3lame",
                    "-ab", "320k",
                    "-y",
                    str(self.output_path)
                ]
            
            # Für Windows: Verwende virtual-audio-capturer oder Stereo Mix
            elif sys.platform == "win32":
                if audio_device and audio_device.startswith("audio="):
                    device_input = audio_device
                else:
                    # Fallback: Versuche Stereo Mix manuell zu finden
                    try:
                        result = subprocess.run(
                            ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if "Stereo Mix" in result.stderr:
                            # Extrahiere genauen Namen
                            import re
                            match = re.search(r'audio="([^"]*Stereo Mix[^"]*)"', result.stderr, re.IGNORECASE)
                            if match:
                                device_input = f"audio={match.group(1)}"
                            else:
                                device_input = "audio=virtual-audio-capturer"
                        else:
                            device_input = "audio=virtual-audio-capturer"
                    except:
                        device_input = "audio=virtual-audio-capturer"
                
                cmd = [
                    "ffmpeg",
                    "-f", "dshow",
                    "-i", device_input,
                    "-ar", str(self.sample_rate),
                    "-ac", str(self.channels),
                    "-acodec", "libmp3lame",
                    "-ab", "320k",
                    "-y",
                    str(self.output_path)
                ]
            else:
                raise RuntimeError(f"Unbekanntes System: {sys.platform}")
            
            # Debug: Zeige Kommando
            print(f"[DEBUG] ffmpeg-Kommando: {' '.join(cmd)}")
            
            # Starte Aufnahme-Prozess
            try:
                self.recording_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE
                )
                
                # Warte kurz und prüfe ob Prozess noch läuft
                time.sleep(0.5)
                if self.recording_process.poll() is not None:
                    # Prozess ist bereits beendet - Fehler!
                    stderr_output = self.recording_process.stderr.read().decode('utf-8', errors='ignore') if self.recording_process.stderr else ""
                    stdout_output = self.recording_process.stdout.read().decode('utf-8', errors='ignore') if self.recording_process.stdout else ""
                    
                    error_msg = stderr_output or stdout_output or "Unbekannter Fehler"
                    print(f"❌ Audio-Aufnahme-Prozess ist sofort beendet (Exit-Code: {self.recording_process.returncode})")
                    print(f"   Fehler: {error_msg[:500]}")
                    
                    # Zeige hilfreiche Fehlermeldung
                    if "device" in error_msg.lower() or "not found" in error_msg.lower():
                        print(f"   💡 Tipp: Audio-Device nicht gefunden. Bitte prüfen Sie:")
                        if sys.platform == "win32":
                            print(f"      - Ist 'Stereo Mix' in Windows aktiviert?")
                            print(f"      - Rechtsklick auf Lautsprecher → Sounds → Aufnahme → Stereo Mix aktivieren")
                        elif sys.platform == "darwin":
                            print(f"      - Ist BlackHole installiert? (brew install blackhole-2ch)")
                            print(f"      - Falls installiert: Neustart erforderlich!")
                            print(f"      - Oder verwenden Sie System-Audio (Device 0)")
                        elif sys.platform.startswith("linux"):
                            print(f"      - Ist PulseAudio installiert und läuft?")
                    
                    return False
                
                self.is_recording = True
                self.start_time = time.time()
                self.recorded_duration = 0.0
                
                # Starte Thread für Fortschrittsüberwachung (auch ohne duration)
                threading.Thread(
                    target=self._monitor_progress,
                    daemon=True
                ).start()
                
                print(f"🎙️ Audio-Aufnahme gestartet: {self.output_path}")
                print(f"   Dauer: {'Unbegrenzt' if not duration else f'{duration:.1f} Sekunden'}")
                print(f"   Sample-Rate: {self.sample_rate} Hz")
                print(f"   Kanäle: {self.channels}")
                print(f"   Device: {device_info}")
                if playback_speed != 1.0:
                    print(f"   💡 Tipp: Stellen Sie die Wiedergabegeschwindigkeit auf {playback_speed}x in der App ein")
                    print(f"      (z.B. Spotify: Einstellungen → Wiedergabe → Geschwindigkeit)")
                
                return True
                
            except Exception as e:
                print(f"❌ Fehler beim Starten des Aufnahme-Prozesses: {e}")
                import traceback
                traceback.print_exc()
                return False
            
        except Exception as e:
            print(f"❌ Fehler beim Starten der Aufnahme: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop_recording(self) -> bool:
        """Stoppt die Audio-Aufnahme"""
        if not self.is_recording:
            return False
        
        try:
            if self.recording_process:
                # Sende 'q' an ffmpeg um Aufnahme zu beenden
                self.recording_process.stdin.write(b'q\n')
                self.recording_process.stdin.flush()
                self.recording_process.wait(timeout=5)
            
            self.is_recording = False
            print(f"✓ Audio-Aufnahme beendet: {self.output_path}")
            
            # Prüfe ob Datei erstellt wurde
            if self.output_path.exists() and self.output_path.stat().st_size > 0:
                print(f"✓ Datei gespeichert: {self.output_path}")
                return True
            else:
                print("⚠️ Aufnahme-Datei ist leer oder wurde nicht erstellt")
                return False
                
        except Exception as e:
            print(f"❌ Fehler beim Beenden der Aufnahme: {e}")
            return False
    
    def _monitor_recording(self, duration: float):
        """Überwacht die Aufnahme und stoppt sie nach der angegebenen Dauer"""
        time.sleep(duration)
        if self.is_recording:
            self.stop_recording()
    
    def is_active(self) -> bool:
        """Prüft ob Aufnahme aktiv ist"""
        return self.is_recording and self.recording_process and self.recording_process.poll() is None


def record_audio_from_stream(url: str, output_path: Path, duration: Optional[float] = None, 
                             playback_speed: float = 2.0) -> bool:
    """
    Nimmt Audio von einem Stream auf während er abgespielt wird
    
    ⚠️ WICHTIG: Nur für privaten Gebrauch!
    
    Args:
        url: URL des Streams (Spotify/Deezer)
        output_path: Pfad zur Ausgabedatei
        duration: Aufnahmedauer in Sekunden (None = automatisch)
        playback_speed: Wiedergabegeschwindigkeit (2.0 = doppelt so schnell)
        
    Returns:
        True bei Erfolg
    """
    try:
        # Methode 1: Versuche Stream direkt mit ffmpeg aufzunehmen
        # (funktioniert nur wenn Stream unverschlüsselt ist)
        print(f"🎙️ Versuche Stream direkt aufzunehmen: {url}")
        
        cmd = [
            "ffmpeg",
            "-i", url,
            "-acodec", "libmp3lame",
            "-ab", "320k",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            print(f"✓ Stream erfolgreich aufgenommen: {output_path}")
            return True
        
        # Methode 2: Falls direkter Stream nicht funktioniert,
        # muss der Benutzer den Stream manuell abspielen
        # während die Aufnahme läuft
        print("⚠️ Direkter Stream-Download nicht möglich (DRM-geschützt)")
        print("   Verwende manuelle Aufnahme-Methode...")
        print("\n📋 Anleitung:")
        print("   1. Starten Sie die Aufnahme")
        print("   2. Spielen Sie den Track in Spotify/Deezer ab")
        print("   3. Die Aufnahme wird automatisch gestoppt wenn der Track endet")
        print("   4. Oder stoppen Sie die Aufnahme manuell")
        
        recorder = AudioRecorder(output_path)
        
        if recorder.start_recording(duration=duration):
            input("\n⏸️  Drücken Sie Enter wenn der Track abgespielt wurde und Sie die Aufnahme beenden möchten...\n")
            return recorder.stop_recording()
        
        return False
        
    except Exception as e:
        print(f"❌ Fehler bei Audio-Aufnahme: {e}")
        import traceback
        traceback.print_exc()
        return False
