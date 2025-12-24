#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio-Device-Detektor
Erkennt automatisch das richtige Audio-Input-Device für System-Audio-Aufnahme
"""

import subprocess
import sys
import re
from typing import Optional, List, Dict, Tuple


class AudioDeviceDetector:
    """Klasse zur automatischen Erkennung von Audio-Input-Devices"""
    
    @staticmethod
    def detect_audio_device() -> Tuple[Optional[str], str]:
        """
        Erkennt automatisch das richtige Audio-Input-Device
        
        Returns:
            (device_string, platform_info) - Device-String für ffmpeg und Info-Text
        """
        platform = sys.platform.lower()
        
        if platform == "win32":
            return AudioDeviceDetector._detect_windows_device()
        elif platform == "darwin":
            return AudioDeviceDetector._detect_macos_device()
        elif platform.startswith("linux"):
            return AudioDeviceDetector._detect_linux_device()
        else:
            return None, "Unbekanntes System"
    
    @staticmethod
    def _detect_windows_device() -> Tuple[Optional[str], str]:
        """Erkennt Windows Audio-Device (Stereo Mix oder Virtual Audio Capturer)"""
        try:
            # Liste alle verfügbaren Audio-Devices
            result = subprocess.run(
                ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            devices_text = result.stderr
            
            # Suche nach Stereo Mix (verschiedene Varianten)
            stereo_mix_patterns = [
                r'"Stereo Mix[^"]*"',
                r'"Stereo Mix \(([^)]+)\)"',
                r'audio="Stereo Mix[^"]*"'
            ]
            
            for pattern in stereo_mix_patterns:
                matches = re.findall(pattern, devices_text, re.IGNORECASE)
                if matches:
                    device_name = matches[0].strip('"')
                    return f"audio={device_name}", f"Stereo Mix gefunden: {device_name}"
            
            # Suche nach Virtual Audio Capturer
            if "virtual-audio-capturer" in devices_text.lower():
                return "audio=virtual-audio-capturer", "Virtual Audio Capturer gefunden"
            
            # Fallback: Versuche Standard-Namen
            if "Stereo Mix" in devices_text:
                # Extrahiere genauen Namen
                match = re.search(r'audio="([^"]*Stereo Mix[^"]*)"', devices_text, re.IGNORECASE)
                if match:
                    return f"audio={match.group(1)}", f"Stereo Mix gefunden: {match.group(1)}"
            
            return None, "Kein Stereo Mix oder Virtual Audio Capturer gefunden. Bitte aktivieren Sie Stereo Mix in Windows Sound-Einstellungen."
            
        except Exception as e:
            return None, f"Fehler bei Device-Erkennung: {e}"
    
    @staticmethod
    def _detect_macos_device() -> Tuple[Optional[str], str]:
        """Erkennt macOS Audio-Device (BlackHole oder System-Audio)"""
        try:
            # Liste alle verfügbaren Audio-Devices
            result = subprocess.run(
                ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            devices_text = result.stderr
            
            # Suche nach BlackHole (verschiedene Varianten)
            blackhole_patterns = [
                r'\[(\d+)\].*BlackHole',
                r'BlackHole.*\[(\d+)\]',
                r'BlackHole 2ch',
                r'BlackHole 16ch',
                r'BlackHole.*\((\d+)\)'
            ]
            
            # Durchsuche alle Zeilen nach BlackHole
            lines = devices_text.split('\n')
            for i, line in enumerate(lines):
                if 'blackhole' in line.lower():
                    # Suche nach Device-ID in dieser oder der nächsten Zeile
                    id_match = re.search(r'\[(\d+)\]', line)
                    if id_match:
                        device_id = id_match.group(1)
                        return f":{device_id}", f"BlackHole gefunden (Device ID: {device_id})"
                    
                    # Prüfe nächste Zeile
                    if i + 1 < len(lines):
                        id_match = re.search(r'\[(\d+)\]', lines[i + 1])
                        if id_match:
                            device_id = id_match.group(1)
                            return f":{device_id}", f"BlackHole gefunden (Device ID: {device_id})"
            
            # BlackHole nicht gefunden - prüfe ob es installiert sein sollte
            # (z.B. durch Prüfung ob BlackHole.app existiert oder durch Homebrew)
            blackhole_installed = False
            try:
                # Prüfe ob BlackHole über Homebrew installiert ist
                brew_result = subprocess.run(
                    ["brew", "list", "--cask", "blackhole-2ch"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if brew_result.returncode == 0:
                    blackhole_installed = True
            except:
                pass
            
            # Prüfe ob BlackHole-Driver existiert
            if not blackhole_installed:
                try:
                    driver_paths = [
                        "/Library/Audio/Plug-Ins/HAL/BlackHole.driver",
                        "/Library/Audio/Plug-Ins/HAL/BlackHole2ch.driver"
                    ]
                    for path in driver_paths:
                        import os
                        if os.path.exists(path):
                            blackhole_installed = True
                            break
                except:
                    pass
            
            if blackhole_installed:
                # BlackHole ist installiert, aber noch nicht verfügbar (Neustart erforderlich)
                return ":0", "BlackHole ist installiert, aber noch nicht verfügbar. Bitte Neustart durchführen! Verwende System-Audio (Device 0) als Fallback."
            else:
                # Fallback: System-Audio (Device 0)
                return ":0", "System-Audio (Device 0) - BlackHole wird empfohlen für bessere Qualität (brew install blackhole-2ch)"
            
        except Exception as e:
            return ":0", f"Fehler bei Device-Erkennung, verwende Standard: {e}"
    
    @staticmethod
    def _detect_linux_device() -> Tuple[Optional[str], str]:
        """Erkennt Linux Audio-Device (PulseAudio)"""
        try:
            # Prüfe ob PulseAudio läuft
            result = subprocess.run(
                ["pulseaudio", "--check"],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # PulseAudio ist verfügbar
                # Versuche Standard-Device zu finden
                try:
                    # Liste PulseAudio-Quellen
                    result = subprocess.run(
                        ["pactl", "list", "short", "sources"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        sources = result.stdout
                        # Suche nach Monitor-Quelle (für System-Audio)
                        for line in sources.split('\n'):
                            if 'monitor' in line.lower() or '.monitor' in line:
                                parts = line.split()
                                if parts:
                                    source_name = parts[1] if len(parts) > 1 else "default"
                                    return f"pulse:{source_name}", f"PulseAudio Monitor gefunden: {source_name}"
                    
                    # Fallback: Standard PulseAudio
                    return "pulse:default", "PulseAudio Standard-Device"
                    
                except:
                    return "pulse:default", "PulseAudio Standard-Device"
            else:
                return None, "PulseAudio nicht verfügbar. Bitte installieren Sie PulseAudio."
                
        except FileNotFoundError:
            return None, "PulseAudio nicht installiert. Bitte installieren Sie PulseAudio: sudo apt-get install pulseaudio"
        except Exception as e:
            return "pulse:default", f"Fehler bei Device-Erkennung, verwende Standard: {e}"
    
    @staticmethod
    def list_all_devices() -> List[Dict[str, str]]:
        """
        Listet alle verfügbaren Audio-Input-Devices auf
        
        Returns:
            Liste von Dictionaries mit device_info
        """
        devices = []
        platform = sys.platform.lower()
        
        try:
            if platform == "win32":
                result = subprocess.run(
                    ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # Parse Audio-Devices aus Output
                lines = result.stderr.split('\n')
                in_audio_section = False
                
                for line in lines:
                    if 'audio devices' in line.lower() or 'audio devices' in line:
                        in_audio_section = True
                        continue
                    
                    if in_audio_section:
                        match = re.search(r'"([^"]+)"', line)
                        if match:
                            device_name = match.group(1)
                            devices.append({
                                'name': device_name,
                                'type': 'dshow',
                                'device_string': f"audio={device_name}"
                            })
            
            elif platform == "darwin":
                result = subprocess.run(
                    ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                # Parse Audio-Devices aus Output
                lines = result.stderr.split('\n')
                in_audio_section = False
                
                for line in lines:
                    if 'audio devices' in line.lower():
                        in_audio_section = True
                        continue
                    
                    if in_audio_section:
                        match = re.search(r'\[(\d+)\]\s+(.+)', line)
                        if match:
                            device_id = match.group(1)
                            device_name = match.group(2).strip()
                            devices.append({
                                'name': device_name,
                                'type': 'avfoundation',
                                'device_string': f":{device_id}"
                            })
            
            elif platform.startswith("linux"):
                try:
                    result = subprocess.run(
                        ["pactl", "list", "short", "sources"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        for line in result.stdout.split('\n'):
                            if line.strip():
                                parts = line.split()
                                if len(parts) >= 2:
                                    device_name = parts[1]
                                    devices.append({
                                        'name': device_name,
                                        'type': 'pulse',
                                        'device_string': f"pulse:{device_name}"
                                    })
                except:
                    pass
        
        except Exception as e:
            pass
        
        return devices


if __name__ == "__main__":
    detector = AudioDeviceDetector()
    device, info = detector.detect_audio_device()
    print(f"Erkanntes Device: {device}")
    print(f"Info: {info}")
    print()
    print("Alle verfügbaren Devices:")
    for dev in detector.list_all_devices():
        print(f"  - {dev['name']} ({dev['type']}): {dev['device_string']}")
