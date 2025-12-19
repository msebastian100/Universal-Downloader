# Build und Upload zu GitHub - Anleitung

## ⚠️ Wichtiger Hinweis

**Builds müssen auf der jeweiligen Plattform erstellt werden:**
- **Windows .exe**: Nur auf Windows möglich
- **Linux .deb**: Nur auf Linux möglich (oder WSL)

Da Sie auf macOS sind, können die Builds hier nicht erstellt werden.

## Option 1: Builds auf den jeweiligen Systemen erstellen

### Windows .exe erstellen

1. **Auf einem Windows-Computer:**
   ```bash
   # Repository klonen
   git clone https://github.com/msebastian100/Universal-Downloader.git
   cd Universal-Downloader
   
   # Virtuelle Umgebung erstellen
   python -m venv venv
   venv\Scripts\activate
   
   # Abhängigkeiten installieren
   pip install -r requirements.txt
   pip install pyinstaller
   
   # Build erstellen
   python build_windows.py
   ```
   
2. **Die .exe Datei finden Sie in:** `dist/UniversalDownloader.exe`

### Linux .deb erstellen

1. **Auf einem Linux-Computer (oder WSL):**
   ```bash
   # Repository klonen
   git clone https://github.com/msebastian100/Universal-Downloader.git
   cd Universal-Downloader
   
   # dpkg-dev installieren
   sudo apt-get install dpkg-dev
   
   # Build erstellen
   chmod +x build_linux.sh
   ./build_linux.sh
   ```
   
2. **Die .deb Datei finden Sie in:** `deb_build/universal-downloader_2.0.0_all.deb`

## Option 2: GitHub Actions (Automatische Builds)

Ich kann GitHub Actions Workflows erstellen, die automatisch bei jedem Release die Builds erstellen. Das wäre die beste Lösung!

## Option 3: Manueller Upload (wenn Builds bereits existieren)

Falls Sie die Builds bereits haben:

1. **GitHub Release erstellen:**
   - Gehen Sie zu: https://github.com/msebastian100/Universal-Downloader/releases/new
   - Tag: `v2.0.0`
   - Titel: `Version 2.0.0 - Initial Release`
   - Beschreibung: Features auflisten

2. **Dateien hochladen:**
   - Ziehen Sie die `.exe` und `.deb` Dateien in den "Attach binaries" Bereich
   - Klicken Sie auf "Publish release"

## Empfehlung: GitHub Actions

Ich kann GitHub Actions Workflows erstellen, die:
- ✅ Automatisch bei jedem Release die Builds erstellen
- ✅ Auf Windows und Linux Build-Servern laufen
- ✅ Die Builds automatisch zum Release hinzufügen
- ✅ Keine manuelle Arbeit mehr nötig

Soll ich die GitHub Actions Workflows erstellen?
