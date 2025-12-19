#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hilfsskript zum Installieren von ffmpeg auf verschiedenen Plattformen
"""

import sys
import subprocess
import platform
import os

def check_ffmpeg():
    """Prüft ob ffmpeg bereits installiert ist"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✓ ffmpeg bereits installiert: {version_line}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False

def install_ffmpeg_linux():
    """Installiert ffmpeg auf Linux"""
    # Prüfe verschiedene Paket-Manager
    if os.path.exists('/usr/bin/apt-get'):
        print("  Installiere ffmpeg über apt-get...")
        try:
            subprocess.run(['sudo', 'apt-get', 'update'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'ffmpeg'], check=True)
            print("✓ ffmpeg erfolgreich installiert")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler bei der Installation: {e}")
            return False
    elif os.path.exists('/usr/bin/dnf'):
        print("  Installiere ffmpeg über dnf...")
        try:
            subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True)
            print("✓ ffmpeg erfolgreich installiert")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler bei der Installation: {e}")
            return False
    elif os.path.exists('/usr/bin/pacman'):
        print("  Installiere ffmpeg über pacman...")
        try:
            subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'ffmpeg'], check=True)
            print("✓ ffmpeg erfolgreich installiert")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler bei der Installation: {e}")
            return False
    else:
        print("❌ Paket-Manager nicht erkannt")
        return False

def install_ffmpeg_macos():
    """Installiert ffmpeg auf macOS"""
    if os.path.exists('/usr/local/bin/brew') or os.path.exists('/opt/homebrew/bin/brew'):
        print("  Installiere ffmpeg über Homebrew...")
        brew_cmd = '/usr/local/bin/brew' if os.path.exists('/usr/local/bin/brew') else '/opt/homebrew/bin/brew'
        try:
            subprocess.run([brew_cmd, 'install', 'ffmpeg'], check=True)
            print("✓ ffmpeg erfolgreich installiert")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Fehler bei der Installation: {e}")
            return False
    else:
        print("❌ Homebrew nicht gefunden")
        print("  Installieren Sie Homebrew: https://brew.sh")
        return False

def install_ffmpeg_windows():
    """Installiert ffmpeg auf Windows (über pip oder gibt Hinweis)"""
    print("⚠ Windows: Automatische Installation über pip versuchen...")
    try:
        # Versuche ffmpeg-python zu installieren (Wrapper)
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'ffmpeg-python'], check=True)
        print("✓ ffmpeg-python installiert (Wrapper)")
        print("⚠ Sie müssen ffmpeg.exe noch manuell installieren:")
        print("  Download von: https://ffmpeg.org/download.html")
        print("  Fügen Sie ffmpeg.exe zu Ihrem PATH hinzu")
        return False  # Nicht vollständig installiert
    except subprocess.CalledProcessError:
        print("❌ Automatische Installation fehlgeschlagen")
        print("  Bitte installieren Sie ffmpeg manuell:")
        print("  Download von: https://ffmpeg.org/download.html")
        return False

def main():
    print("=" * 60)
    print("ffmpeg Installation")
    print("=" * 60)
    print()
    
    # Prüfe ob bereits installiert
    if check_ffmpeg():
        print("ffmpeg ist bereits installiert - keine Installation nötig.")
        return 0
    
    print("⚠ ffmpeg nicht gefunden - versuche Installation...")
    print()
    
    system = platform.system()
    success = False
    
    if system == 'Linux':
        success = install_ffmpeg_linux()
    elif system == 'Darwin':
        success = install_ffmpeg_macos()
    elif system == 'Windows':
        success = install_ffmpeg_windows()
    else:
        print(f"❌ Betriebssystem '{system}' nicht unterstützt")
        print("  Bitte installieren Sie ffmpeg manuell")
        return 1
    
    if success:
        # Prüfe nochmal
        if check_ffmpeg():
            print("\n✓ Installation erfolgreich abgeschlossen!")
            return 0
        else:
            print("\n⚠ Installation scheint fehlgeschlagen zu sein")
            return 1
    else:
        print("\n❌ Installation fehlgeschlagen")
        print("  Bitte installieren Sie ffmpeg manuell")
        return 1

if __name__ == "__main__":
    sys.exit(main())
