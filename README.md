# Universal Downloader

[![Build Releases](https://github.com/msebastian100/Universal-Downloader/actions/workflows/build.yml/badge.svg)](https://github.com/msebastian100/Universal-Downloader/actions/workflows/build.yml)

Ein Universal-Downloader für Musik, Hörbücher und Videos - für privaten Gebrauch.

**Unterstützte Quellen:**
- 🎵 **Deezer**: Musik und Alben
- 📚 **Audible**: Hörbücher
- 🎬 **YouTube**: Videos und Playlists
- 📺 **Öffentlich-rechtliche Sender**: ARD, ZDF, ORF, SWR, BR, WDR, MDR, NDR, HR, RBB, SR, Phoenix, Arte, Tagesschau, RocketBeans TV

## ⚠️ Wichtiger Hinweis

Dieser Downloader ist **nur für privaten Gebrauch** bestimmt. Bitte beachten Sie:
- Die Nutzungsbedingungen von Deezer
- Urheberrechte und Lizenzbestimmungen
- Lokale Gesetze bezüglich des Herunterladens von geschütztem Material

## Features

### 🎵 Deezer
- ✅ Download von einzelnen Tracks
- ✅ Download von kompletten Alben
- ✅ Download von Playlists
- ✅ Automatische Metadaten-Extraktion (Titel, Künstler, Album, Cover)
- ✅ MP3-Tagging mit Cover-Art
- ✅ **YouTube-Fallback**: Da Deezer DRM-Schutz verwendet, wird automatisch YouTube als Alternative genutzt
- ✅ Metadaten werden weiterhin von Deezer abgerufen, auch bei YouTube-Downloads
- ✅ **ARL-Token Unterstützung**: Optional für DRM-Umgehung
- ✅ **Anmeldefunktion**: Login mit ARL-Token für höchste Qualität
- ✅ **Familien-Profile**: Unterstützung für mehrere Profile in Familien-Accounts
- ✅ **Automatische Qualitätsauswahl**: Basierend auf Abo-Status (Free/Premium/HiFi)

### 📚 Audible
- ✅ Download von Hörbüchern
- ✅ Konvertierung von AAX zu MP3/MP4
- ✅ Kapitelweise Downloads
- ✅ Qualitätsauswahl

### 🎬 Video-Downloader (YouTube & Öffentlich-rechtliche Sender)
- ✅ **YouTube**: Videos und Playlists
- ✅ **ARD, ZDF, ORF, SWR, BR, WDR, MDR, NDR, HR, RBB, SR, Phoenix, Arte, Tagesschau, RocketBeans TV**
- ✅ Format-Auswahl: **MP4 (Video)** oder **MP3 (Audio)**
- ✅ Qualitätsauswahl: Beste Qualität, 1080p, 720p, Niedrigste Qualität
- ✅ Playlist-Download: Gesamte Playlists herunterladen
- ✅ Automatische Metadaten-Extraktion

### 🖥️ Allgemein
- ✅ Moderne GUI (grafische Benutzeroberfläche)
- ✅ Detailliertes Logging
- ✅ Fortschrittsanzeige
- ✅ Fehlerbehandlung

## Installation

### Voraussetzungen
- **Python 3.8 oder höher** erforderlich
- **ffmpeg** (wird automatisch installiert, falls möglich)
- **tkinter** (GUI-Bibliothek - normalerweise mit Python installiert)

### Automatische Installation (empfohlen)

**Windows (einfachste Methode):**
1. Doppelklick auf `start_launcher.vbs` oder `start_launcher.bat`
2. Die Launcher installieren automatisch:
   - Python (falls nicht vorhanden, über Microsoft Store oder winget)
   - Virtuelle Umgebung (`venv`)
   - Alle Python-Abhängigkeiten (`requirements.txt`)
   - ffmpeg (über winget, falls möglich)
   - tkinter (normalerweise mit Python installiert)
   - Erstellen Desktop- und Startmenü-Verknüpfungen
3. Die Anwendung startet automatisch nach der Installation

**Linux/macOS:**
```bash
chmod +x install.sh
./install.sh
```

Das Installationsskript (`install.sh`):
- Erstellt eine virtuelle Umgebung (`venv`)
- Installiert alle Python-Abhängigkeiten
- Installiert ffmpeg (falls möglich)
- Installiert fehlende System-Pakete (z.B. `python3-tk` auf Linux)
- Erstellt Desktop-Verknüpfungen

**Hinweis für Windows:** Die Launcher (`start_launcher.vbs` und `start_launcher.bat`) führen automatisch alle Installationsschritte durch, auch auf einem "cleanen PC" ohne vorinstalliertes Python. Einfach die Datei doppelklicken!

### Manuelle Installation

**1. Virtuelle Umgebung erstellen:**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows
```

**2. Abhängigkeiten installieren:**
```bash
pip install -r requirements.txt
```

**3. System-Abhängigkeiten:**
   - **ffmpeg**: Download von https://ffmpeg.org/download.html und zu PATH hinzufügen
   - **python3-tk** (Linux): `sudo apt-get install python3-tk`

**4. Abhängigkeiten prüfen:**
```bash
python3 check_dependencies.py
```

## Verwendung

### Grafische Benutzeroberfläche (GUI)

**Empfohlene Methode - Plattform-spezifische Launcher:**

Die Anwendung kann über plattform-spezifische Launcher gestartet werden, die automatisch `start.py` ausführen:

**Linux/macOS (mit Shell-Launcher):**
```bash
chmod +x start_launcher.sh
./start_launcher.sh
```

**Windows (mit VBS-Launcher):**
```bash
# Doppelklick auf start_launcher.vbs
# Oder:
cscript start_launcher.vbs
```

**Windows (mit BAT-Launcher):**
```bash
# Doppelklick auf start_launcher.bat
# Oder in der Kommandozeile:
start_launcher.bat
```

**Hinweis:** Beide Windows-Launcher (`start_launcher.vbs` und `start_launcher.bat`) führen die gleichen Funktionen aus. Die VBS-Datei ist für Doppelklick optimiert (kein Konsolen-Fenster), die BAT-Datei zeigt die Ausgabe in einem Konsolen-Fenster.

**Was machen die Launcher?**
- **Windows (`start_launcher.vbs` / `start_launcher.bat`):**
  - Installiert Python automatisch (falls nicht vorhanden, über Microsoft Store oder winget)
  - Erstellt virtuelle Umgebung (`venv`)
  - Installiert alle Python-Abhängigkeiten (`requirements.txt`)
  - Installiert ffmpeg (über winget, falls möglich)
  - Prüft tkinter (normalerweise mit Python installiert)
  - Erstellt Desktop- und Startmenü-Verknüpfungen
  - Führt Update-Checks durch
  - Startet die GUI mit korrekter Konfiguration
  
- **Linux/macOS (`start_launcher.sh`):**
  - Prüft alle Abhängigkeiten
  - Installiert fehlende Pakete bei Bedarf (z.B. `python3-tk`, `python3-venv`)
  - Erstellt virtuelle Umgebung (`venv`)
  - Installiert alle Python-Abhängigkeiten
  - Erstellt Desktop-Verknüpfungen (`.desktop` Datei)
  - Startet die GUI mit korrekter Konfiguration

- **Alle Launcher führen automatisch `start.py` aus**, das die GUI startet

**Alternative Methoden:**

**Direkt mit Python:**
```bash
python3 start.py
```

**Oder direkt die GUI:**
```bash
python3 gui.py
```

#### 🎵 Deezer-Tab
1. Download-Pfad auswählen (optional)
2. Deezer-URL einfügen (Track, Album oder Playlist)
3. "Download starten" klicken

#### 📚 Audible-Tab
1. Bei Audible anmelden
2. Bibliothek laden
3. Hörbücher auswählen und herunterladen

#### 🎬 Video-Downloader-Tab
1. Download-Pfad auswählen
2. **Format wählen**: MP4 (Video) oder MP3 (Audio)
3. **Qualität wählen**: Beste Qualität, 1080p, 720p, Niedrigste Qualität
4. **Optional**: "Gesamte Playlist herunterladen" aktivieren
5. Video-URL einfügen (YouTube, ARD, ZDF, etc.)
6. "Download starten" klicken

### Kommandozeile

```bash
python3 deezer_downloader.py
```

Geben Sie die Deezer-URL ein, wenn Sie dazu aufgefordert werden.

### Programmgesteuert

```python
from deezer_downloader import DeezerDownloader

downloader = DeezerDownloader(download_path="Downloads")

# Einzelnen Track herunterladen
downloader.download_track("123456789")

# Album herunterladen
downloader.download_album("987654321")

# Playlist herunterladen
downloader.download_playlist("456789123")

# Aus URL herunterladen
downloader.download_from_url("https://www.deezer.com/track/123456789")
```

## Unterstützte URL-Formate

- Track: `https://www.deezer.com/track/123456789`
- Album: `https://www.deezer.com/album/987654321`
- Playlist: `https://www.deezer.com/playlist/456789123`

## Dateistruktur

```
Downloader/
├── deezer_downloader.py  # Haupt-Downloader-Modul
├── gui.py                # Grafische Benutzeroberfläche
├── requirements.txt       # Python-Abhängigkeiten
└── README.md             # Diese Datei
```

## Technische Details

- Verwendet die Deezer API für Metadaten
- Nutzt `yt-dlp` für den eigentlichen Download
- **Automatischer YouTube-Fallback**: Wenn Deezer-Downloads wegen DRM fehlschlagen, wird automatisch YouTube als Quelle verwendet
- **Vollständigkeitsprüfung**: Vergleicht erwartete mit tatsächlich heruntergeladenen Tracks
- **Detailliertes Logging**: Jeder Download wird mit Zeitstempel, Quelle (Deezer/YouTube) und Status protokolliert
- MP3-Tagging mit `mutagen`
- Cover-Art wird automatisch hinzugefügt
- Metadaten werden immer von Deezer abgerufen, auch bei YouTube-Downloads

## Anmeldung und Qualität

### Anmeldung für höchste Qualität

Für Premium/HiFi-Accounts können Sie sich anmelden, um die höchste Qualität zu nutzen:

#### In der GUI:
1. Klicken Sie auf "Anmelden"
2. Folgen Sie der Anleitung zum Extrahieren des ARL-Tokens
3. Geben Sie den ARL-Token ein
4. Die Qualität wird automatisch basierend auf Ihrem Abo gesetzt

#### In der Kommandozeile:
```python
from deezer_auth import interactive_login
from deezer_downloader import DeezerDownloader

# Anmeldung
auth = interactive_login()

# Downloader mit Authentifizierung
downloader = DeezerDownloader(download_path="Downloads", auth=auth)
```

#### Programmgesteuert:
```python
from deezer_auth import DeezerAuth
from deezer_downloader import DeezerDownloader

# Mit ARL-Token
auth = DeezerAuth()
auth.login_with_arl("IHR_ARL_TOKEN")

# Downloader mit Authentifizierung
downloader = DeezerDownloader(download_path="Downloads", auth=auth)
```

### ARL-Token extrahieren

1. Öffnen Sie Deezer in Ihrem Browser
2. Öffnen Sie die Entwicklertools (F12)
3. Gehen Sie zu: **Application** → **Cookies** → **deezer.com**
4. Kopieren Sie den Wert des Cookies **"arl"**

### Qualitätsauswahl

Die Qualität wird automatisch basierend auf Ihrem Abo gesetzt:
- **HiFi/Lossless**: FLAC (lossless)
- **Premium/Family**: MP3 320 kbps
- **Free**: MP3 128 kbps

### Familien-Profile

Wenn Sie ein Familien-Abo haben:
- Alle verfügbaren Profile werden automatisch erkannt
- Sie können zwischen Profilen wechseln
- Jedes Profil behält seine eigenen Einstellungen

**Hinweis**: Der ARL-Token ist persönlich und sollte nicht geteilt werden. Die Verwendung erfolgt auf eigene Verantwortung.

## Fehlerbehebung

### Download schlägt fehl
- Stellen Sie sicher, dass `yt-dlp` korrekt installiert ist
- Überprüfen Sie Ihre Internetverbindung
- Stellen Sie sicher, dass die Deezer-URL gültig ist

### Metadaten fehlen
- Die Deezer API könnte temporär nicht verfügbar sein
- Versuchen Sie es später erneut

## 📦 Ausführbare Dateien erstellen (optional)

Falls Sie eine ausführbare Datei erstellen möchten, siehe [BUILD.md](BUILD.md) für detaillierte Anleitungen.

**Hinweis:** Für normale Nutzung ist keine EXE-Erstellung erforderlich. Verwenden Sie einfach `python3 start.py`.

## 📜 Lizenz

Dieses Projekt ist unter der **MIT License** lizenziert. Siehe [LICENSE](LICENSE) für Details.

**Wichtiger Hinweis:** Dieser Downloader ist für privaten Gebrauch bestimmt. Bitte beachten Sie:
- Die Nutzungsbedingungen der jeweiligen Plattformen (Deezer, Spotify, etc.)
- Urheberrechte und Lizenzbestimmungen
- Lokale Gesetze bezüglich des Herunterladens von geschütztem Material

## 🔗 GitHub Repository

- Repository-URL: Siehe `version.py` (GITHUB_REPO_URL)
- Releases: Automatische Update-Prüfung über GitHub Releases
- Setup-Anleitung: Siehe [GITHUB_SETUP.md](GITHUB_SETUP.md)

## 🤝 Beitragen

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder öffnen Sie ein Issue.

