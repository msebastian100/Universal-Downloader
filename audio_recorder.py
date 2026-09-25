#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio Recorder für DRM-geschützte Streams
Nimmt Audio während der Wiedergabe auf (nur für privaten Gebrauch)

⚠️ WICHTIG: Nur für privaten Gebrauch!
Diese Funktion dient ausschließlich zur Aufnahme von gekauften/abonnierten Inhalten für persönliche Nutzung.
"""

import re
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
        self.start_time: Optional[float] = None
        self.recorded_duration: float = 0.0
        self.live_parts: list = []
        self.on_track: Optional[Callable[[Path], None]] = None
        self.silence_stop_after: Optional[float] = None
        self._silence_token = 0
        self._app_pid: Optional[int] = None
        self._app_source = None
        
    def start_recording(self, duration: Optional[float] = None, playback_speed: float = 1.0, force_device: Optional[str] = None) -> bool:
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
            
            if force_device:
                audio_device, device_info = force_device, force_device
            elif DEVICE_DETECTOR_AVAILABLE:
                try:
                    audio_device, device_info = AudioDeviceDetector.detect_audio_device()
                    if audio_device:
                        print(f"🎤 Audio-Device erkannt: {device_info}")
                except Exception as e:
                    print(f"⚠️ Fehler bei Device-Erkennung: {e}, verwende Standard")
            
            # Für Linux: PulseAudio
            if self._app_pid and sys.platform == "darwin":
                cmd = ["ffmpeg", "-f", "f32le", "-i", "pipe:0", "-y", str(self.output_path)]
            elif sys.platform.startswith("linux"):
                if not audio_device or not str(audio_device).startswith("pulse:"):
                    print(f"❌ {device_info}")
                    return False
                device_input = audio_device
                
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
                if not audio_device or not str(audio_device).startswith(":"):
                    print(f"❌ {device_info}")
                    return False
                device_input = audio_device
                
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
            
            elif sys.platform == "win32":
                if audio_device == "wasapi" or not audio_device:
                    cmd = [
                        "ffmpeg",
                        "-f", "wasapi",
                        "-loopback", "1",
                        "-i", "default",
                        "-ar", str(self.sample_rate),
                        "-ac", str(self.channels),
                        "-acodec", "libmp3lame",
                        "-ab", "320k",
                        "-y",
                        str(self.output_path),
                    ]
                else:
                    device_input = audio_device if audio_device.startswith("audio=") else f"audio={audio_device}"
                    cmd = [
                        "ffmpeg",
                        "-f", "dshow",
                        "-i", device_input,
                        "-ar", str(self.sample_rate),
                        "-ac", str(self.channels),
                        "-acodec", "libmp3lame",
                        "-ab", "320k",
                        "-y",
                        str(self.output_path),
                    ]
            else:
                raise RuntimeError(f"Unbekanntes System: {sys.platform}")
            
            # Debug: Zeige Kommando
            print(f"[DEBUG] ffmpeg-Kommando: {' '.join(cmd)}")
            
            feed = None
            if self._app_pid and sys.platform == "darwin":
                helper = Path(__file__).resolve().parent / "tools" / "ud-app-audio"
                if not helper.is_file():
                    print("❌ App-Aufnahme fehlt")
                    return False
                self._app_source = subprocess.Popen(
                    [str(helper), "record", str(self._app_pid)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                )
                feed = self._app_source.stdout
                cmd = [
                    "ffmpeg", "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", "pipe:0",
                    "-af", "silencedetect=noise=-35dB:d=1.2",
                    "-acodec", "libmp3lame", "-ab", "320k", "-y", str(self.output_path),
                ]
            elif "-af" not in cmd:
                insert_at = cmd.index("-ar") if "-ar" in cmd else len(cmd) - 1
                cmd[insert_at:insert_at] = ["-af", "silencedetect=noise=-35dB:d=1.2"]
            self._track_start = 0.0
            self._part_index = 0
            self.live_parts = []

            # Starte Aufnahme-Prozess
            try:
                self.recording_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=feed if feed is not None else subprocess.PIPE,
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
                            print(f"      - Ist PulseAudio oder PipeWire installiert?")

                    if sys.platform == "win32" and audio_device == "wasapi" and DEVICE_DETECTOR_AVAILABLE and not force_device:
                        mix, mix_info = AudioDeviceDetector._detect_windows_stereo_mix()
                        if mix:
                            print(f"WASAPI nicht verfügbar, versuche {mix_info}")
                            return self.start_recording(duration, playback_speed, force_device=mix)
                    
                    return False
                
                self.is_recording = True
                self.start_time = time.time()
                self.recorded_duration = 0.0
                
                # Starte Thread für Fortschrittsüberwachung (auch ohne duration)
                threading.Thread(
                    target=self._monitor_progress,
                    daemon=True
                ).start()
                threading.Thread(
                    target=self._watch_track_edges,
                    daemon=True
                ).start()
                
                print(f"🎙️ Audio-Aufnahme gestartet: {self.output_path}")
                print(f"   Dauer: {'Unbegrenzt' if not duration else f'{duration:.1f} Sekunden'}")
                print(f"   Sample-Rate: {self.sample_rate} Hz")
                print(f"   Kanäle: {self.channels}")
                if not self._app_pid:
                    self.capture_label = device_info
                print(f"   Device: {device_info}")
                if sys.platform == "darwin" and ":0" in str(cmd):
                    print(f"   ℹ️  System-Audio (Device 0) wird verwendet - funktioniert sofort!")
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
    
    def _stop_if_still_silent(self, limit: float, token: int) -> None:
        time.sleep(limit)
        if token == self._silence_token and self.is_recording:
            self.stop_recording()

    def _cut_part(self, start: float, end: float) -> None:
        if end - start < 20:
            return
        time.sleep(0.4)
        self._part_index += 1
        target = self.output_path.with_name(
            f"{self.output_path.stem}_teil{self._part_index:02d}{self.output_path.suffix}"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(self.output_path),
                "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
                "-c", "copy", str(target),
            ],
            capture_output=True,
            timeout=60,
        )
        if target.is_file() and target.stat().st_size > 0:
            self.live_parts.append(target)
            if self.on_track:
                self.on_track(target)

    def _watch_track_edges(self) -> None:
        """Erkennt Anfang und Ende eines Stücks an der Stille, noch während der Aufnahme."""
        proc = self.recording_process
        if proc is None or proc.stderr is None:
            return
        start = 0.0
        for raw in proc.stderr:
            line = raw.decode("utf-8", errors="ignore")
            begun = re.search(r"silence_end: ([0-9.]+)", line)
            if begun:
                self._silence_token += 1
                start = float(begun.group(1))
                continue
            ended = re.search(r"silence_start: ([0-9.]+)", line)
            if ended:
                end = float(ended.group(1))
                self._cut_part(start, end)
                start = end
                limit = self.silence_stop_after
                if limit and self._part_index > 0:
                    self._silence_token += 1
                    token = self._silence_token
                    threading.Thread(target=self._stop_if_still_silent, args=(limit, token), daemon=True).start()
        if self.output_path.is_file():
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", str(self.output_path)],
                    capture_output=True, text=True, timeout=15,
                )
                total = float((probe.stdout or "0").strip() or 0)
            except (OSError, subprocess.SubprocessError, ValueError):
                total = 0.0
            if total > start:
                self._cut_part(start, total)

    def stop_recording(self) -> bool:
        """Stoppt die Audio-Aufnahme"""
        if not self.is_recording:
            return False
        
        try:
            if self._app_source is not None:
                self._app_source.terminate()
                self._app_source = None
            if self.recording_process:
                # Methode 1: Sende 'q' an ffmpeg um Aufnahme zu beenden
                try:
                    if self.recording_process.stdin:
                        self.recording_process.stdin.write(b'q\n')
                        self.recording_process.stdin.flush()
                except:
                    pass
                
                # Warte auf Beendigung (mit Timeout)
                try:
                    self.recording_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Methode 2: Terminiere Prozess falls er nicht reagiert
                    print("⚠️ ffmpeg reagiert nicht, terminiere Prozess...")
                    self.recording_process.terminate()
                    time.sleep(0.5)
                    if self.recording_process.poll() is None:
                        # Methode 3: Force-Kill falls Terminate nicht funktioniert
                        self.recording_process.kill()
                        time.sleep(0.5)
            
            self.is_recording = False
            print(f"✓ Audio-Aufnahme beendet: {self.output_path}")
            
            # Warte kurz damit Datei geschrieben wird
            time.sleep(0.5)
            
            # Prüfe ob Datei erstellt wurde
            if self.output_path.exists():
                file_size = self.output_path.stat().st_size
                if file_size > 0:
                    print(f"✓ Datei gespeichert: {self.output_path} ({file_size / 1024 / 1024:.2f} MB)")
                    return True
                else:
                    print("⚠️ Aufnahme-Datei ist leer")
                    return False
            else:
                print("⚠️ Aufnahme-Datei wurde nicht erstellt")
                return False
                
        except Exception as e:
            print(f"❌ Fehler beim Beenden der Aufnahme: {e}")
            # Versuche Prozess zu beenden falls noch aktiv
            try:
                if self.recording_process and self.recording_process.poll() is None:
                    self.recording_process.terminate()
                    time.sleep(0.5)
                    if self.recording_process.poll() is None:
                        self.recording_process.kill()
            except:
                pass
            return False
    
    def _monitor_progress(self):
        """Überwacht den Fortschritt der Aufnahme"""
        while self.is_recording and self.recording_process and self.recording_process.poll() is None:
            if self.start_time:
                elapsed = time.time() - self.start_time
                self.recorded_duration = elapsed
                
                # Rufe Progress-Callback auf falls vorhanden
                if self.progress_callback:
                    try:
                        self.progress_callback(elapsed)
                    except:
                        pass
            
            time.sleep(0.5)  # Update alle 0.5 Sekunden
    
    def _monitor_recording(self, duration: float):
        """Überwacht die Aufnahme und stoppt sie nach der angegebenen Dauer"""
        time.sleep(duration)
        if self.is_recording:
            self.stop_recording()
    
    def get_progress(self) -> Optional[float]:
        """
        Gibt den aktuellen Fortschritt zurück
        
        Returns:
            Verstrichene Zeit in Sekunden oder None
        """
        if self.is_recording and self.start_time:
            return time.time() - self.start_time
        return None
    
    def get_recorded_duration(self) -> float:
        """Gibt die aufgezeichnete Dauer zurück"""
        return self.recorded_duration
    
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
