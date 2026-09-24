# Universal Downloader

Ein Downloader für Videos, Hörfunk und Serien – für privaten Gebrauch.

Aktuelle Version: **2.1.57** (24. September 2026). Fertige Pakete liegen bei den [Releases](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.57). Neuere Versionen erscheinen auf der [Release-Übersicht](https://github.com/msebastian100/Universal-Downloader/releases). Die installierte App prüft dort selbst auf Updates.

## Wichtiger Hinweis

Dieser Downloader ist nur für privaten Gebrauch bestimmt. Bitte beachten Sie die Nutzungsbedingungen der jeweiligen Plattformen, Urheberrechte und die lokalen Gesetze zum Herunterladen geschützten Materials.

## Funktionen

- **Video:** YouTube und öffentlich-rechtliche Mediatheken (ARD, ZDF, ORF, SWR, BR, WDR, MDR, NDR, HR, RBB, SR, Phoenix, Arte, Tagesschau, RocketBeans TV). Format MP4, MKV oder MP3, Qualitätsauswahl, Playlists.
- **Hörfunk und Audiothek:** ARD Audiothek, ARD Sounds, die Audiotheken von BR, NDR, WDR, MDR, SWR, rbb, SR und HR, Deutschlandfunk, ORF-Radiothek, LibriVox. Ausgabe als MP3.
- **Serien-Wächter:** prüft Sendungen und Playlists, zeigt offene Folgen in der Leiste und startet den Download von dort. Pro Serie eigenes Format, ARD Sounds als MP3.
- Fortschritt mit Prozent und Geschwindigkeit, Protokoll, Update über die GitHub-Releases.

## Installation

### Windows

Den Installer von [Release v2.1.57](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.57) herunterladen und starten:

[UniversalDownloader_Setup_v2.1.57.exe](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.57/UniversalDownloader_Setup_v2.1.57.exe)

Zusätzlich liegt dort das ZIP `universal-downloader_v2.1.57.zip` (Programm ohne Setup).

### macOS

Ebenfalls unter [Release v2.1.57](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.57):

- [UniversalDownloader_2.1.57_arm64.dmg](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.57/UniversalDownloader_2.1.57_arm64.dmg) für Apple Silicon
- [UniversalDownloader_2.1.57.dmg](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.57/UniversalDownloader_2.1.57.dmg)

### Linux (APT, empfohlen)

Für Linux Mint, Ubuntu und Debian. Das Programm erscheint danach im Anwendungsmenü und aktualisiert sich wie andere Systempakete, auch in der Aktualisierungsverwaltung.

Die Datei liegt auf GitHub, nicht auf dem eigenen Rechner. Der Befehl lädt sie zuerst herunter und startet sie dann. Nichts vorher klonen oder speichern.

1. Terminal öffnen (unter Linux Mint und Ubuntu: Menü nach „Terminal“ suchen, oder `Strg+Alt+T`).
2. Diesen Block komplett markieren, kopieren, im Terminal einfügen und Enter drücken:

```bash
curl -fsSL -o /tmp/install_apt_linux.sh https://raw.githubusercontent.com/msebastian100/Universal-Downloader/main/install_apt_linux.sh && chmod +x /tmp/install_apt_linux.sh && sudo /tmp/install_apt_linux.sh
```

3. Das Passwort eingeben. Im Terminal bleibt das Feld leer, die Zeichen werden nicht angezeigt. Danach Enter.
4. Warten, bis das Skript fertig ist. **Universal Downloader** steht dann im Anwendungsmenü.

Das Skript holt den Schlüssel von `https://ppa.plertanix.de/apt`, trägt die Paketquelle ein und installiert `universal-downloader`. Schlägt der Schlüsselimport fehl, etwa wegen SSL, nutzt es die Quelle ohne Schlüsselprüfung. Fehler schreibt es nach `/var/log/` oder `/tmp/` (`universal-downloader-install_ERROR_*.log`).

Spätere Updates: in der Aktualisierungsverwaltung, oder im Terminal `sudo apt update && sudo apt install --only-upgrade universal-downloader`.

Entfernen: `sudo apt remove universal-downloader`. Die Quelle liegt in `/etc/apt/sources.list.d/universal-downloader.list`, der Schlüssel in `/etc/apt/trusted.gpg.d/universal-downloader.gpg`.

### Linux (.deb aus dem Release)

Wer das Paket einmalig von GitHub holen will, ohne die APT-Quelle: Terminal öffnen und diesen Befehl einfügen. Er lädt die Datei von [Release v2.1.57](https://github.com/msebastian100/Universal-Downloader/releases/tag/v2.1.57) nach `/tmp` und installiert sie.

```bash
curl -fL -o /tmp/universal-downloader_2.1.57_all.deb https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.57/universal-downloader_2.1.57_all.deb && sudo apt install /tmp/universal-downloader_2.1.57_all.deb
```

Direktlink, falls der Browser die Datei laden soll: [universal-downloader_2.1.57_all.deb](https://github.com/msebastian100/Universal-Downloader/releases/download/v2.1.57/universal-downloader_2.1.57_all.deb). Danach im Ordner der Datei `sudo apt install ./universal-downloader_2.1.57_all.deb`. Bei Updates über diesen Weg muss die neue `.deb` jedes Mal neu geladen werden. Mit der APT-Quelle oben kommt das von allein.

## Lizenz

MIT. Siehe [LICENSE](LICENSE).
