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
