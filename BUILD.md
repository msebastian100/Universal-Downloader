# Build-Anleitung

Diese Anleitung erklärt, wie Sie ausführbare Dateien für Windows (.exe) und Linux (.deb) erstellen.

## Windows .exe Datei

### ⚠️ Wichtig: Build-Plattform

**Empfohlen:** Erstellen Sie die .exe auf einem Windows-System.

**Alternativen:**
- **WSL (Windows Subsystem for Linux)**: Kann verwendet werden, aber die .exe muss auf Windows getestet werden
- **Cross-Compilation**: Möglich, aber komplex und nicht empfohlen
- **VM/Remote**: Windows-VM oder Remote-Windows-System verwenden

### Voraussetzungen

1. **Windows-System** (empfohlen) oder Linux/Mac mit PyInstaller
2. Python 3.8 oder höher installiert
3. Alle Abhängigkeiten installiert:
   ```bash
   pip install -r requirements.txt
   pip install pyinstaller
   ```

### Build durchführen

**Option 1: Automatisches Build-Script**
```bash
python build_windows.py
```

**Option 2: Manuell mit PyInstaller**
```bash
pyinstaller UniversalDownloader.spec
```

Die .exe Datei befindet sich nach dem Build in `dist/UniversalDownloader.exe`.

**Hinweis:** Wenn Sie auf Linux/Mac bauen, wird die .exe erstellt, funktioniert aber nur auf Windows!

### Hinweise

- Die .exe Datei ist eigenständig und benötigt keine Python-Installation auf dem Zielsystem
- Die Datei kann groß sein (50-100 MB), da alle Abhängigkeiten eingebunden sind
- Für kleinere Dateien können Sie `--onedir` statt `--onefile` verwenden

## Linux .deb Paket

### ⚠️ Wichtig: Build-Plattform

**Erforderlich:** Sie müssen auf einem Linux-System bauen (Ubuntu, Debian, Linux Mint, etc.).

**Alternativen:**
- **WSL (Windows Subsystem for Linux)**: Funktioniert perfekt für .deb Builds
- **VM**: Linux-VM auf Windows/Mac verwenden
- **Docker**: Linux-Container für Builds verwenden
- **Remote**: Linux-Server für Builds verwenden

**Nicht möglich:** .deb Pakete können nicht auf Windows oder macOS nativ erstellt werden.

### Voraussetzungen

1. **Linux-System** (Ubuntu, Debian, Linux Mint, etc.)
2. dpkg-dev installiert:
   ```bash
   sudo apt-get install dpkg-dev
   ```

### Build durchführen

```bash
chmod +x build_linux.sh
./build_linux.sh
```

Das .deb Paket befindet sich nach dem Build in `deb_build/universal-downloader_1.0.0_all.deb`.

### Installation

```bash
sudo dpkg -i deb_build/universal-downloader_1.0.0_all.deb
sudo apt-get install -f  # Falls Abhängigkeiten fehlen
```

### Hinweise

- Das .deb Paket installiert die Anwendung systemweit
- Python-Abhängigkeiten werden automatisch installiert (falls möglich)
- Die Anwendung ist über das Anwendungsmenü verfügbar
- Start-Befehl: `universal-downloader`

## Troubleshooting

### Windows

**Problem: PyInstaller findet Module nicht**
- Lösung: Stellen Sie sicher, dass alle Abhängigkeiten im venv installiert sind
- Versuchen Sie: `pip install --upgrade pyinstaller`

**Problem: .exe startet nicht**
- Lösung: Erstellen Sie die .exe mit `--console` statt `--windowed` um Fehlermeldungen zu sehen
- Prüfen Sie die Logs in `dist/`

### Linux

**Problem: dpkg-deb nicht gefunden**
- Lösung: `sudo apt-get install dpkg-dev`

**Problem: Abhängigkeiten fehlen nach Installation**
- Lösung: `sudo apt-get install -f` oder manuell installieren:
  ```bash
  sudo apt-get install python3 python3-pip python3-tk ffmpeg
  pip3 install -r requirements.txt
  ```

**Problem: Berechtigungen**
- Lösung: Stellen Sie sicher, dass das Script ausführbar ist: `chmod +x build_linux.sh`

## Build auf verschiedenen Systemen

### Szenario 1: Nur Windows verfügbar
- ✅ Windows .exe: Direkt auf Windows erstellen
- ❌ Linux .deb: Nicht möglich → Verwenden Sie WSL oder VM

### Szenario 2: Nur Linux verfügbar
- ✅ Linux .deb: Direkt auf Linux erstellen
- ⚠️ Windows .exe: Möglich, aber .exe muss auf Windows getestet werden

### Szenario 3: macOS verfügbar
- ⚠️ Windows .exe: Möglich mit PyInstaller, aber .exe muss auf Windows getestet werden
- ❌ Linux .deb: Nicht möglich → Verwenden Sie Docker oder VM

### Empfohlene Lösung: WSL für Windows-Benutzer

Wenn Sie Windows haben und beide Builds erstellen möchten:

1. **Windows .exe**: Direkt auf Windows erstellen
2. **Linux .deb**: WSL installieren und dort bauen:
   ```bash
   # In WSL
   sudo apt-get update
   sudo apt-get install dpkg-dev
   ./build_linux.sh
   ```

## Verteilung

### Windows
- Verteilen Sie nur die .exe Datei
- Benutzer benötigen keine Python-Installation
- Optional: Erstellen Sie ein Installer mit Inno Setup oder NSIS

### Linux
- Verteilen Sie die .deb Datei
- Benutzer können sie mit `dpkg -i` installieren
- Optional: Erstellen Sie ein Repository für einfachere Updates

## Versionierung

Um die Version zu ändern:

**Windows:**
- Ändern Sie `--name=UniversalDownloader` in `build_windows.py`

**Linux:**
- Ändern Sie `VERSION="1.0.0"` in `build_linux.sh`
- Aktualisieren Sie auch die Version in `DEBIAN/control`
