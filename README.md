# Universal Downloader

Ein Universal-Downloader für Musik, Hörbücher, Videos und Serien – für privaten Gebrauch.

Aktuelle Version: **2.1.55** (23. September 2026). Fertige Pakete liegen bei den [Releases](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.55). Neuere Versionen erscheinen auf der [Release-Übersicht](https://github.com/msebastian100/Universal-Downloader/releases). Die installierte App prüft dort selbst auf Updates.

## Wichtiger Hinweis

Dieser Downloader ist nur für privaten Gebrauch bestimmt. Bitte beachten Sie die Nutzungsbedingungen der jeweiligen Plattformen, Urheberrechte und die lokalen Gesetze zum Herunterladen geschützten Materials.

## Funktionen

- **Deezer:** Tracks, Alben und Playlists, Metadaten und Cover. Wenn Deezer wegen DRM nicht liefert, springt der Download auf YouTube um; Titeldaten kommen weiter von Deezer. Anmeldung per ARL-Token, Familienprofile und Qualität nach Abo (128 kbps, 320 kbps oder FLAC).
- **Spotify:** Titel über die hinterlegten Download-Wege.
- **Audible:** Hörbücher, Umwandlung von AAX nach MP3 oder MP4, kapitelweise.
- **Video:** YouTube und öffentlich-rechtliche Mediatheken (ARD, ZDF, ORF, SWR, BR, WDR, MDR, NDR, HR, RBB, SR, Phoenix, Arte, Tagesschau, RocketBeans TV). Format MP4, MKV oder MP3, Qualitätsauswahl, Playlists.
- **Serien-Wächter:** prüft Sendungen und Playlists, zeigt offene Folgen in der Leiste und startet den Download von dort. Pro Serie eigenes Format, ARD Sounds als MP3.
- Fortschritt mit Prozent und Geschwindigkeit, Protokoll, Update über die GitHub-Releases.

## Installation

### Windows

Den Installer von [Release v2.1.55](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.55) herunterladen und starten:

[UniversalDownloader_Setup_v2.1.55.exe](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.55/UniversalDownloader_Setup_v2.1.55.exe)

Zusätzlich liegt dort das ZIP `universal-downloader_v2.1.55.zip` (Programm ohne Setup).

### macOS

Ebenfalls unter [Release v2.1.55](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.55):

- [UniversalDownloader_2.1.55_arm64.dmg](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.55/UniversalDownloader_2.1.55_arm64.dmg) für Apple Silicon
- [UniversalDownloader_2.1.55.dmg](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.55/UniversalDownloader_2.1.55.dmg)

### Linux (APT, empfohlen)

Unter Linux Mint, Ubuntu und Debian installiert und aktualisiert das Paket wie andere Systempakete, auch in der Aktualisierungsverwaltung.

```bash
chmod +x install_apt_linux.sh
sudo ./install_apt_linux.sh
```

Das Skript `install_apt_linux.sh` importiert den Schlüssel von `https://ppa.plertanix.de/apt`, trägt die Quelle ein und installiert `universal-downloader`. Schlägt der Schlüsselimport fehl (zum Beispiel wegen SSL), trägt es die Quelle mit `[trusted=yes]` ein. Fehler landen unter `/var/log/` oder `/tmp/` (`universal-downloader-install_ERROR_*.log`).

Manuell:

```bash
curl -sS https://ppa.plertanix.de/apt/repo-key.asc -o /tmp/universal-downloader.asc
sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/universal-downloader.gpg /tmp/universal-downloader.asc
echo "deb [signed-by=/etc/apt/trusted.gpg.d/universal-downloader.gpg] https://ppa.plertanix.de/apt stable main" | sudo tee /etc/apt/sources.list.d/universal-downloader.list
sudo apt update
sudo apt install universal-downloader
```

Schlüssel und `sudo` nicht in eine Pipe legen: sonst liest `gpg` das Passwort statt des Schlüssels.

Ohne Schlüsselprüfung, nur wenn der Import scheitert:

```bash
echo "deb [trusted=yes] https://ppa.plertanix.de/apt stable main" | sudo tee /etc/apt/sources.list.d/universal-downloader.list
sudo apt update
sudo apt install universal-downloader
```

Updates: `sudo apt update && sudo apt install --only-upgrade universal-downloader`  
Entfernen: `sudo apt remove universal-downloader` und die Dateien `/etc/apt/sources.list.d/universal-downloader.list` sowie `/etc/apt/trusted.gpg.d/universal-downloader.gpg` löschen.

### Linux (.deb aus dem Release)

Das Paket von [Release v2.1.55](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.55):

[universal-downloader_2.1.55_all.deb](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.55/universal-downloader_2.1.55_all.deb)

```bash
sudo apt install ./universal-downloader_2.1.55_all.deb
```

Danach erscheint **Universal Downloader** im Anwendungsmenü. Das Paket legt eine eigene Umgebung unter `/usr/share/universal-downloader/venv` an.

## Start aus dem Quellcode

Python 3.8 oder neuer, ffmpeg und tkinter (`python3-tk` unter Linux).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 check_dependencies.py
python3 start.py
```

Unter Windows die Umgebung mit `venv\Scripts\activate` aktivieren. `install.sh` richtet Umgebung, Abhängigkeiten und eine Desktop-Verknüpfung ein.

## Deezer-Anmeldung

Für Premium- oder HiFi-Qualität in der Oberfläche auf **Anmelden** gehen und den ARL-Cookie eintragen:

1. Deezer im Browser öffnen
2. Entwicklertools (F12) → Application → Cookies → deezer.com
3. Wert des Cookies `arl` kopieren

Der Token ist persönlich und wird nicht geteilt. Die Qualität folgt dem Abo: FLAC bei HiFi, MP3 320 kbps bei Premium, MP3 128 kbps ohne Abo.

## Lizenz

MIT. Siehe [LICENSE](LICENSE).
