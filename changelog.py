#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Release Notes / Changelog für den Dialog „Was ist neu?“ nach einem Update.

Bei neuen Versionen hier einen Eintrag hinzufügen (neueste Version oben).
"""

from typing import List, Optional, Dict, Any

# Neueste Version zuerst – wird für „Erster Start“ und Upgrade-Anzeige genutzt
RELEASE_NOTES: List[Dict[str, Any]] = [
    {
        "version": "2.1.61",
        "date": "2026-09-25",
        "items": [
            "Suche: ae, oe und ue gelten wie ä, ö und ü, zum Beispiel „Pfefferkoerner“.",
            "URL-Zeile, Format, Qualität und die Suche sind größer und wachsen mit dem Fenster.",
        ],
    },
    {
        "version": "2.1.59",
        "date": "2026-09-24",
        "items": [
            "Linux: die Mediathek-Suche (ARD, ZDF, Audiothek) ist im Paket enthalten.",
        ],
    },
    {
        "version": "2.1.58",
        "date": "2026-09-24",
        "items": [
            "YouTube-Music-Mixe öffnen die Liederauswahl, mit dem hinterlegten Konto. Der Fortschritt läuft während des Downloads.",
        ],
    },
    {
        "version": "2.1.57",
        "date": "2026-09-24",
        "items": [
            "Suche für ARD und ZDF mit Bild, Beschreibung und Folgenauswahl. Serien und Hörspiele lassen sich in der App ansehen oder anhören.",
            "Audible für die eigene Bibliothek. Der Tab ist aus, bis er unter Einstellungen bei „Sichtbare Tabs“ eingeschaltet wird.",
            "Plugins können Knöpfe, Tabs und Prüfungen ergänzen. Die Beispieldatei liegt im Ordner plugins neben den Downloads.",
        ],
    },
    {
        "version": "2.1.55",
        "date": "2026-09-23",
        "items": [
            "Windows: „Queue abgeschlossen“ kommt als Systemmeldung, nicht als Extra-Fenster. Das Tray-Menü meldet „Hauptprogramm wird geöffnet“ nicht mehr, wenn das Fenster schon da ist.",
        ],
    },
    {
        "version": "2.1.54",
        "date": "2026-09-23",
        "items": [
            "Windows: der Serien-Wächter findet das Hauptprogramm auch unter „Programme (x86)“ und holt ein schon offenes Fenster nach vorn. Menü und Meldung zeigen die Versionsnummer.",
        ],
    },
    {
        "version": "2.1.53",
        "date": "2026-09-23",
        "items": [
            "Windows: das Update zeigt die installierte Version und den Download-Fortschritt. Ersetzt wird genau diese Installation, danach startet dieselbe Programmdatei. Liegt sie unter „Programme“, fragt Windows nach der Bestätigung; ohne Zustimmung bleibt die alte Version.",
        ],
    },
    {
        "version": "2.1.52",
        "date": "2026-09-23",
        "items": [
            "Windows: das Tray-Menü lässt sich wieder schließen. Der laufende Download zeigt darin Prozent und Balken, auch wenn das Menü schon offen war.",
        ],
    },
    {
        "version": "2.1.51",
        "date": "2026-09-23",
        "items": [
            "Windows: der Serien-Wächter zeigt die offenen Folgen im Tray-Menü, wie auf dem Mac und unter Linux. Ein Klick startet den Download.",
        ],
    },
    {
        "version": "2.1.50",
        "date": "2026-09-23",
        "items": [
            "Windows: das Update wartet, bis das Programm zu ist, und startet dann den Installer. Die laufende Programmdatei wird nicht mehr überschrieben.",
        ],
    },
    {
        "version": "2.1.49",
        "date": "2026-09-23",
        "items": [
            "Linux: das Menü in der Leiste zeigt den Download wie auf dem Mac, mit Balken, Prozent und „Download abbrechen“.",
        ],
    },
    {
        "version": "2.1.48",
        "date": "2026-09-23",
        "items": [
            "Download: die Statuszeile und der Balken zeigen den Prozentstand und die Geschwindigkeit, auch bei einer einzelnen Folge.",
        ],
    },
    {
        "version": "2.1.47",
        "date": "2026-09-23",
        "items": [
            "Linux: ein Klick auf eine Folge in der Leiste beendet das Icon nicht mehr. Der Download läuft im schon offenen Fenster weiter.",
        ],
    },
    {
        "version": "2.1.46",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: Ein Klick auf eine Folge oder „Hauptprogramm öffnen“ holt das schon offene Fenster nach vorn. Es öffnet sich kein zweites Programm.",
        ],
    },
    {
        "version": "2.1.45",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: „Jetzt prüfen“ öffnet die verfügbaren Folgen, auch wenn die Sendung schon einmal geprüft wurde und nichts als „habe ich“ markiert ist.",
            "Linux: das Menü in der Leiste zeigt die offenen Folgen und „Folgenliste öffnen…“, wie auf dem Mac.",
        ],
    },
    {
        "version": "2.1.44",
        "date": "2026-09-22",
        "items": [
            "ARD Sounds: in der MP3 steht der Folgentitel, nicht mehr der interne Clip-Name der Webseite.",
        ],
    },
    {
        "version": "2.1.43",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: weitere Folgen einer Serie bleiben beim gewählten Format. ARD Sounds landet als MP3 im Musik-Ordner, auch wenn mehrere Folgen gleichzeitig laden.",
            "Parallele Downloads überschreiben sich nicht mehr gegenseitig die temporäre Datei.",
        ],
    },
    {
        "version": "2.1.42",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: ARD-Sounds-Sendungen wie Kein Mucks werden erkannt. Ohne „habe ich“-Markierung gelten die Folgen als verfügbar.",
            "Das Menü zeigt nur acht Folgen. Über „Folgenliste öffnen…“ wählt man, was geladen oder ignoriert wird. Der Rest bleibt für später.",
        ],
    },
    {
        "version": "2.1.41",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: Format pro Serie. Video standardmäßig MP4 oder MKV, ARD Sounds als MP3, YouTube-Playlists als MP4, MKV oder MP3.",
        ],
    },
    {
        "version": "2.1.40",
        "date": "2026-09-22",
        "items": [
            "Menü: „Jetzt laden“ startet den Download wieder. Der Klick ist zuvor ohne Meldung abgebrochen.",
        ],
    },
    {
        "version": "2.1.39",
        "date": "2026-09-22",
        "items": [
            "Fehlende Folgen bleiben im Menü, auch wenn eine andere Serie dieselbe Kennung als vorhanden führt.",
        ],
    },
    {
        "version": "2.1.38",
        "date": "2026-09-22",
        "items": [
            "Menüleiste: eine fertige Folge bleibt nicht bei 100 % stehen. Heruntergeladene Folgen verschwinden aus den Hinweisen.",
        ],
    },
    {
        "version": "2.1.37",
        "date": "2026-09-22",
        "items": [
            "Fenster mit X schließen bricht einen laufenden Download nicht mehr ab. Er läuft in der Menüleiste weiter, das Programm lässt sich von dort wieder öffnen.",
        ],
    },
    {
        "version": "2.1.36",
        "date": "2026-09-22",
        "items": [
            "Download-Fortschritt läuft live mit. Die App startet yt-dlp als eigenen Prozess, statt die Ausgabe bis zum Ende zu puffern.",
        ],
    },
    {
        "version": "2.1.35",
        "date": "2026-09-22",
        "items": [
            "Menü und Programm zeigen den Download- und den Umwandlungsfortschritt live, nicht erst am Ende.",
        ],
    },
    {
        "version": "2.1.34",
        "date": "2026-09-22",
        "items": [
            "Menü: schon vorhandene Folgen bleiben nicht bei 0 % hängen. Sie gelten als bereits vorhanden und verschwinden aus der laufenden Liste.",
        ],
    },
    {
        "version": "2.1.33",
        "date": "2026-09-22",
        "items": [
            "Laufende Folgen zeigen im Menü und im Programm, ob sie noch laden oder schon konvertieren. Abbrechen bleibt im Menü.",
        ],
    },
    {
        "version": "2.1.32",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: „Jetzt laden“ nutzt „Max. gleichzeitige Video-Downloads“. Weitere Folgen warten in der Video-Queue. Bei GPU laden die Dateien parallel und werden danach nacheinander umgewandelt.",
        ],
    },
    {
        "version": "2.1.31",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: Fortschritt läuft mit, Abbruch stoppt den Download. Weitere Folgen landen in der Queue bzw. laufen parallel, je nach Einstellung.",
        ],
    },
    {
        "version": "2.1.30",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: gefundene Folgen in der Menüleiste direkt laden (einzeln oder alle). Laufenden Download abbrechen.",
        ],
    },
    {
        "version": "2.1.29",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: „Jetzt prüfen“ in der Menüleiste meldet nicht angehakte Folgen (z. B. Pfefferkörner S18).",
        ],
    },
    {
        "version": "2.1.28",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: „Jetzt prüfen“ zeigt nicht angehakte Folgen als fehlend, nicht als neue Serie. Das Auswahlfenster bleibt kompakt.",
        ],
    },
    {
        "version": "2.1.27",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: ungehakte Folgen gelten als fehlend; Trailer/Making-of lassen sich ignorieren.",
        ],
    },
    {
        "version": "2.1.26",
        "date": "2026-09-22",
        "items": [
            "macOS: Absturz nach „Jetzt prüfen“ im Serien-Wächter behoben (keine nativen System-Alerts mehr).",
        ],
    },
    {
        "version": "2.1.25",
        "date": "2026-09-22",
        "items": [
            "macOS: Fenster schließen lässt den Wächter in der Menüleiste; das Programm lässt sich wieder öffnen, ohne extra Dock-Icons.",
            "macOS: Einstellungsfenster und Dialoge passen sich der Bildschirmgröße an.",
            "GitHub: macOS-Installer als .dmg für Apple Silicon (arm64) und Intel (x86_64).",
        ],
    },
    {
        "version": "2.1.24",
        "date": "2026-09-22",
        "items": [
            "Windows: Tray-Menü beendet die App nicht mehr durch Fehlklick auf „Beenden“.",
            "Windows: kein CMD-/PowerShell-Fenster mehr beim Start oder „Jetzt prüfen“.",
            "Windows: schnellerer Start (Onedir statt Entpacken bei jedem Öffnen).",
        ],
    },
    {
        "version": "2.1.23",
        "date": "2026-09-22",
        "items": [
            "Windows: Klick auf das Serien-Wächter-Icon in der Taskleiste öffnet wieder das Menü (beendet die App nicht mehr).",
        ],
    },
    {
        "version": "2.1.22",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: in den Einstellungen komplett deaktivierbar (kein Tray, kein Autostart).",
        ],
    },
    {
        "version": "2.1.21",
        "date": "2026-09-22",
        "items": [
            "Linux Mint/Cinnamon: Serien-Wächter-Icon in der Infoleiste (XApp, eigener Prozess).",
            "Windows: Tray startet zuverlässig neben der GUI (PID-Datei blockiert den Wächter nicht mehr).",
        ],
    },
    {
        "version": "2.1.20",
        "date": "2026-09-22",
        "items": [
            "Windows: Absturz der GUI nach Tray-Start behoben (Tray läuft in eigenem Prozess, keine zweite Message-Loop).",
        ],
    },
    {
        "version": "2.1.19",
        "date": "2026-09-22",
        "items": [
            "Serien-Wächter: nach erfolgreichem Download Folgen automatisch als „habe ich“ markieren.",
            "Serien-Wächter: Option „Neue Folgen automatisch herunterladen“ (global und pro Serie).",
            "Serien-Wächter: Tray-Helper – Fortschritt, neue Folgen, Abbruch, Video- und Hörbuch-Ordner; Autostart nach Anmeldung (Windows/macOS/Linux).",
            "Serien-Wächter: Hörbücher/Audiothek (ARD Audiothek, ARD Sounds, LibriVox, …) prüfen und als MP3 in den Musik-Ordner laden.",
            "Windows: Tray-Icon über natives Notify-Icon (sichtbar in Windows 11); Setup-Installer zusätzlich zur portablen EXE.",
        ],
    },
    {
        "version": "2.1.18",
        "date": "2026-09-21",
        "items": [
            "Linux: GNOME/Ubuntu „Software“ zeigt das Paket mit Icon und Beschreibung (AppStream wie bei Ubuntu-Apps).",
        ],
    },
    {
        "version": "2.1.17",
        "date": "2026-09-21",
        "items": [
            "Linux: Paket erscheint in GNOME/Cinnamon „Software“ (AppStream/DEP-11, APT-Quelle „stable main“).",
        ],
    },
    {
        "version": "2.1.16",
        "date": "2026-09-21",
        "items": [
            "Linux: In-App-Update nutzt das APT-Repo statt einer GitHub-Windows-.exe (die fälschlich als .deb gespeichert wurde).",
            "Linux: Update-Installation über pkexec (Passwort-Dialog) statt sudo ohne Terminal.",
            "Linux: klare Fehlermeldung, falls die Installation scheitert.",
        ],
    },
    {
        "version": "2.1.15",
        "date": "2026-09-21",
        "items": [
            "ARD Sounds: nach Website-Umbau wieder komplette Sendungs-Folgenlisten (API zuerst, auch urn:ard:section:… / extra).",
            "ARD Sounds: Mini-Serien wie (1/5)–(5/5) korrekt sortiert bei gleichem Sendedatum.",
            "Dateinamen: optionale Platzhalter {date}/{sendedatum} und {date_de}; Sendedatum in Europe/Berlin (kein Tag Versatz).",
            "Linux: install_apt_linux.sh – APT-Repo inkl. Schlüssel-Import, Fallback und Fehler-Log.",
        ],
    },
    {
        "version": "2.1.14",
        "date": "2026-09-03",
        "items": [
            "Dateinamen: optionale Platzhalter {date}/{sendedatum} (YYYY-MM-DD) und {date_de} (TT.MM.JJJJ) für das Sendedatum.",
            "ARD Sounds/Audiothek: Sendedatum aus API/Webseite; Anzeige in der Folgenauswahl.",
        ],
    },
    {
        "version": "2.1.13",
        "date": "2026-03-21",
        "items": [
            "Linux (.deb): Release Notes / „Was ist neu?“ – fehlendes Modul changelog behoben (Datei wird mitinstalliert).",
            "Linux (.deb): postinst installiert Abhängigkeiten zuverlässig mit venv/bin/python3 -m pip und ensurepip (kein venv/bin/pip nötig).",
            "Windows/macOS (PyInstaller): hiddenimports für nachträglich geladene Module ergänzt (u. a. Hörbuch-Suche, Stream, ODT/DOCX-Import).",
            "macOS: build_mac.sh nutzt eigenes Build-venv (.venv_build_mac) für Homebrew-Python (PEP 668).",
        ],
    },
    {
        "version": "2.1.12",
        "date": "2026-03-21",
        "items": [
            "ARD Sounds (Musik): komplette Folgenliste pro Sendung über die ARD-API (nicht nur die ersten ~12 aus der Webseite).",
            "ARD Sounds: Titel und Spieldauer in der Staffel-/Folgenauswahl aus der API.",
            "ARD Sounds: zuverlässiger Download (direkte Audio-URL aus der Folgenseite, SSL-Workarounds für ardsounds.de wie bei der Audiothek).",
            "ARD Sounds: Staffel-Erkennung und Fallbacks (HTML/API) weiter stabilisiert.",
        ],
    },
    {
        "version": "2.1.11",
        "date": "2026-02-08",
        "items": [
            "Nach einem Update erscheint beim ersten Start automatisch ein Dialog mit den wichtigsten Änderungen.",
            "Changelog jederzeit unter Einstellungen → Allgemein → Button „Was ist neu?“ (neben der Versionsanzeige).",
        ],
    },
    {
        "version": "2.1.10",
        "date": "2026-02-08",
        "items": [
            "Video-Warteschlange: mehrere Downloads gleichzeitig (Einstellung „Max. gleichzeitige Video-Downloads“).",
            "Parallele YouTube-Downloads: stabilere MP4-Fertigstellung (GPU-Kodierung wird pro parallelem Job automatisch deaktiviert).",
            "Abbrechen beendet alle parallelen yt-dlp-Prozesse zuverlässig.",
            "Diverse Verbesserungen an Fortschritt, ETA, Qualität pro Sender, Historie und Theme.",
        ],
    },
]


def _compare(a: str, b: str) -> int:
    from version import compare_versions
    return compare_versions(a, b)


def _format_block(entry: Dict[str, Any]) -> str:
    lines = [f"Version {entry['version']} ({entry.get('date', '')})"]
    for it in entry.get("items") or []:
        lines.append(f"  • {it}")
    return "\n".join(lines)


def changelog_text_for_upgrade(from_version: str, to_version: str) -> Optional[str]:
    """
    Text für Nutzer, die von from_version auf to_version gewechselt haben.
    from_version leer oder 0.0.0 = erster Start → nur Hinweise zur Zielversion.
    """
    prev = (from_version or "").strip() or "0.0.0"
    if _compare(prev, to_version) >= 0:
        return None

    blocks: List[str] = []

    if prev == "0.0.0":
        # Erster Start / neues Feld in settings: letzte Releases bis zur aktuellen Version (max. 6)
        n = 0
        for entry in RELEASE_NOTES:
            if _compare(entry["version"], to_version) > 0:
                continue
            blocks.append(_format_block(entry))
            n += 1
            if n >= 6:
                break
        if not blocks:
            blocks.append(
                f"Version {to_version}\n\nWillkommen beim Universal Downloader!\n"
                "Nach jedem Update erscheint hier kurz, was sich geändert hat."
            )
        else:
            blocks.insert(0, "Willkommen – die letzten Änderungen im Überblick:\n")
    else:
        for entry in RELEASE_NOTES:
            v = entry["version"]
            if _compare(v, prev) <= 0:
                continue
            if _compare(v, to_version) > 0:
                continue
            blocks.append(_format_block(entry))

    if not blocks:
        return (
            f"Du nutzt jetzt Version {to_version}.\n\n"
            "Für diese Version liegen keine ausführlichen Release Notes vor."
        )
    if prev == "0.0.0":
        return "\n\n".join(blocks)
    return "Willkommen zurück – hier die Änderungen:\n\n" + "\n\n".join(blocks)


def changelog_full_reference() -> str:
    """Alle eingetragenen Versionen (für „Was ist neu?“ in den Einstellungen)."""
    if not RELEASE_NOTES:
        return "Noch keine Release Notes hinterlegt."
    parts = ["Release Notes – Universal Downloader\n" + "=" * 40 + "\n"]
    for entry in RELEASE_NOTES:
        parts.append(_format_block(entry))
        parts.append("")
    return "\n".join(parts).strip()
