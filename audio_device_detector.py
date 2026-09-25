#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio-Device-Detektor
Erkennt automatisch das richtige Audio-Input-Device für System-Audio-Aufnahme
"""

import subprocess
import sys
import re
from pathlib import Path
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
        """Getrennte Aufnahmespur, sonst die eingebaute WASAPI-Schleife."""
        cable = AudioDeviceDetector._detect_windows_virtual_cable()
        if cable[0]:
            return cable
        return "wasapi", "Windows-Systemton (WASAPI, alles was gerade ausgegeben wird)"

    @staticmethod
    def _detect_windows_virtual_cable() -> Tuple[Optional[str], str]:
        """Eigenes Aufnahmegerät, falls ein virtuelles Kabel installiert ist."""
        try:
            result = subprocess.run(
                ["ffmpeg", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for match in re.finditer(r'audio="([^"]+)"', result.stderr or "", re.IGNORECASE):
                name = match.group(1)
                if any(key in name.lower() for key in ("cable", "vb-audio", "voicemeeter", "blackhole")):
                    return f"audio={name}", f"Eigene Spur: {name}"
        except (OSError, subprocess.SubprocessError):
            pass
        return None, ""

    @staticmethod
    def _detect_windows_stereo_mix() -> Tuple[Optional[str], str]:
        """Stereo Mix, falls die WASAPI-Schleife auf diesem ffmpeg fehlt."""
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
            
            # Fallback: Versuche Standard-Namen
            if "Stereo Mix" in devices_text:
                # Extrahiere genauen Namen
                match = re.search(r'audio="([^"]*Stereo Mix[^"]*)"', devices_text, re.IGNORECASE)
                if match:
                    return f"audio={match.group(1)}", f"Stereo Mix gefunden: {match.group(1)}"
            
            return None, "Stereo Mix ist nicht aktiv. In den Windows-Klangeinstellungen unter Aufnahme einblenden und aktivieren."
            
        except Exception as e:
            return None, f"Fehler bei Device-Erkennung: {e}"
    
    @staticmethod
    def _ensure_macos_route() -> None:
        """Legt „UD Aufnahme“ an, falls BlackHole vorhanden ist."""
        helper = Path(__file__).resolve().parent / "tools" / "ud-aufnahme"
        if not helper.is_file():
            return
        try:
            subprocess.run([str(helper)], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.SubprocessError):
            pass

    @staticmethod
    def _detect_macos_device() -> Tuple[Optional[str], str]:
        """Nimmt nur BlackHole auf. Andere Programme wählen die Ausgabe „UD Aufnahme“."""
        AudioDeviceDetector._ensure_macos_route()
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
                        return f":{device_id}", "UD Aufnahme (im anderen Programm diese Ausgabe wählen)"
                    
                    # Prüfe nächste Zeile
                    if i + 1 < len(lines):
                        id_match = re.search(r'\[(\d+)\]', lines[i + 1])
                        if id_match:
                            device_id = id_match.group(1)
                            return f":{device_id}", "UD Aufnahme (im anderen Programm diese Ausgabe wählen)"
            
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
                return None, "BlackHole ist installiert, aber noch nicht in der Geräteliste. Einmal ab- und anmelden."
            return None, "macOS hat keine eingebaute Systemton-Schleife. BlackHole einrichten (brew install --cask blackhole-2ch) und als Ausgabe mitbenutzen."
            
        except Exception as e:
            return None, f"BlackHole konnte nicht gelesen werden: {e}"
    
    @staticmethod
    def _detect_linux_device() -> Tuple[Optional[str], str]:
        """Eigene Senke „UD Aufnahme“, damit nur der darauf gelegte Ton mitkommt."""
        monitor = "ud_aufnahme.monitor"
        try:
            listed = subprocess.run(
                ["pactl", "list", "short", "sources"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if listed.returncode == 0 and monitor not in listed.stdout:
                subprocess.run(
                    [
                        "pactl", "load-module", "module-null-sink",
                        "sink_name=ud_aufnahme",
                        "sink_properties=device.description=UD-Aufnahme",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            return f"pulse:{monitor}", "UD-Aufnahme (nur Ton, der auf dieses Gerät gelegt wird)"
        except (OSError, subprocess.SubprocessError):
            return None, "PulseAudio oder PipeWire (pactl) fehlt, die eigene Aufnahmespur konnte nicht angelegt werden."
    
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
