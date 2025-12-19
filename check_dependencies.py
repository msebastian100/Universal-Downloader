#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prüft ob alle benötigten Abhängigkeiten installiert sind
"""

import sys
import subprocess
from pathlib import Path

# Farben für Terminal-Ausgabe
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def check_python_package(package_name, import_name=None, min_version=None):
    """Prüft ob ein Python-Paket installiert ist"""
    if import_name is None:
        import_name = package_name
    
    try:
        module = __import__(import_name)
        version = getattr(module, '__version__', 'unbekannt')
        
        # Spezielle Behandlung für yt-dlp
        if import_name == 'yt_dlp':
            try:
                result = subprocess.run(
                    ['yt-dlp', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    version = result.stdout.strip()
            except:
                pass
        
        print(f"{Colors.GREEN}✓{Colors.END} {package_name:20s} installiert (Version: {version})")
        return True
    except ImportError:
        print(f"{Colors.RED}✗{Colors.END} {package_name:20s} NICHT installiert")
        return False
    except Exception as e:
        print(f"{Colors.YELLOW}⚠{Colors.END} {package_name:20s} Fehler beim Prüfen: {e}")
        return False

def check_system_command(command, name=None):
    """Prüft ob ein System-Befehl verfügbar ist"""
    if name is None:
        name = command
    
    try:
        result = subprocess.run(
            ['which', command],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Versuche Version zu bekommen
            try:
                version_result = subprocess.run(
                    [command, '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if version_result.returncode == 0:
                    version_line = version_result.stdout.split('\n')[0]
                    print(f"{Colors.GREEN}✓{Colors.END} {name:20s} installiert ({version_line[:50]})")
                else:
                    print(f"{Colors.GREEN}✓{Colors.END} {name:20s} installiert")
            except:
                print(f"{Colors.GREEN}✓{Colors.END} {name:20s} installiert")
            return True
        else:
            print(f"{Colors.RED}✗{Colors.END} {name:20s} NICHT installiert")
            return False
    except Exception as e:
        print(f"{Colors.YELLOW}⚠{Colors.END} {name:20s} Fehler beim Prüfen: {e}")
        return False

def main():
    print_header("Abhängigkeits-Prüfung für Universal Downloader")
    
    # Python-Pakete aus requirements.txt
    print(f"{Colors.BOLD}Python-Pakete:{Colors.END}")
    packages = [
        ('requests', 'requests'),
        ('mutagen', 'mutagen'),
        ('Pillow', 'PIL'),
        ('deezer-python', 'deezer'),
        ('yt-dlp', 'yt_dlp'),
        ('beautifulsoup4', 'bs4'),
        ('selenium', 'selenium'),
        ('audible', 'audible'),
        ('browser-cookie3', 'browser_cookie3'),
    ]
    
    python_ok = True
    for package_name, import_name in packages:
        if not check_python_package(package_name, import_name):
            python_ok = False
    
    # System-Befehle
    print(f"\n{Colors.BOLD}System-Befehle:{Colors.END}")
    system_commands = [
        ('yt-dlp', 'yt-dlp'),
        ('ffmpeg', 'ffmpeg'),
    ]
    
    system_ok = True
    for command, name in system_commands:
        if not check_system_command(command, name):
            system_ok = False
    
    # Zusammenfassung
    print_header("Zusammenfassung")
    
    if python_ok and system_ok:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ Alle Abhängigkeiten sind installiert!{Colors.END}")
        print(f"\nSie können die Anwendung jetzt starten:")
        print(f"  python start.py")
        return 0
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Einige Abhängigkeiten fehlen!{Colors.END}")
        print(f"\n{Colors.YELLOW}Installation fehlender Pakete:{Colors.END}")
        print(f"  cd /Users/basti/Documents/Projekte/Downloader")
        print(f"  source venv/bin/activate  # oder: . venv/bin/activate")
        print(f"  pip install -r requirements.txt")
        print(f"\n{Colors.YELLOW}Für ffmpeg (falls fehlend):{Colors.END}")
        print(f"  macOS: brew install ffmpeg")
        print(f"  Linux: sudo apt-get install ffmpeg  # oder entsprechendes Paket-Manager")
        print(f"  Windows: https://ffmpeg.org/download.html")
        return 1

if __name__ == "__main__":
    sys.exit(main())
