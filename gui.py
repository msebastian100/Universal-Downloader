#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pyright: reportGeneralTypeIssues=false, reportArgumentType=false, reportOptionalMemberAccess=false, reportOptionalCall=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportAssignmentType=false, reportOperatorIssue=false, reportUnknownMemberType=false
"""
GUI für Deezer Downloader
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox as _tk_messagebox
from pathlib import Path
import threading
import queue
import time
import re
from typing import Optional, Dict, List
from datetime import datetime
import os
import sys
import json
import base64
import webbrowser
import platform
import shutil
import subprocess
import tempfile
from deezer_downloader import DeezerDownloader

# Import Authentifizierung
try: 
    from deezer_auth import DeezerAuth, interactive_login
except ImportError:
    DeezerAuth = None
    interactive_login = None

# Import Audible
try:
    from audible_integration import AudibleAuth, AudibleLibrary, interactive_audible_login
except ImportError:
    AudibleAuth = None
    AudibleLibrary = None
    interactive_audible_login = None

# Import Video Downloader
try:
    from video_downloader import VideoDownloader, SUPPORTED_SENDERS
except ImportError:
    VideoDownloader = None
    SUPPORTED_SENDERS = {}

try:
    import mediathek_search
except ImportError:
    mediathek_search = None

# Anzeigenamen für Video-Sender (Dialog "Unterstützte Sender")
VIDEO_SENDER_DISPLAY_NAMES = {
    "youtube": "YouTube",
    "ard": "ARD Mediathek",
    "ardplus": "ARD Plus",
    "zdf": "ZDF",
    "orf": "ORF",
    "swr": "SWR",
    "br": "BR",
    "wdr": "WDR",
    "mdr": "MDR",
    "ndr": "NDR",
    "hr": "HR",
    "rbb": "RBB",
    "sr": "SR",
    "rbtv": "RocketBeans TV",
    "phoenix": "Phoenix",
    "tagesschau": "Tagesschau",
    "arte": "Arte",
}

# Import Spotify Downloader
try:
    from spotify_downloader import SpotifyDownloader
except ImportError:
    SpotifyDownloader = None

# Import Updater
try:
    from updater import UpdateChecker, check_updates_simple
    from version import get_version_string, get_version
except ImportError:
    UpdateChecker = None
    check_updates_simple = None
    get_version_string = lambda: "Universal Downloader"
    get_version = lambda: "unknown"


# Im Musik-Tab unterstützte Mediatheken und kostenlose Hörbuch-/Hörspiel-Seiten (öffentlich-rechtlich oder kostenlos)
MUSIC_MEDIATHEK_DOMAINS = (
    'music.youtube.com',    # YouTube Music (Playlists, Alben, Singles)
    'ardaudiothek.de',      # ARD Audiothek (Hörspiele, Podcasts)
    'ardsounds.de',         # ARD Sounds (neue ARD-Plattform für Radio, Podcasts, Hörspiele & Hörbücher)
    'br.de',                # BR Audiothek
    'ndr.de',               # NDR Audiothek / NDR Hörspiele
    'wdr.de',               # WDR Audiothek
    'mdr.de',               # MDR Audiothek
    'swr.de',               # SWR Audiothek
    'rbb.de',               # rbb Audiothek
    'sr.de',                # SR (Saarländischer Rundfunk)
    'hr.de',                # HR Audiothek
    'deutschlandfunk.de',   # Deutschlandfunk
    'deutschlandradio.de',  # Deutschlandradio / Dlf
    'dradio.de',            # dradio (Deutschlandradio)
    'orf.at',               # ORF (österreichisch, Hörspiele/Podcasts)
    'librivox.org',         # LibriVox (kostenlose Hörbücher, Public Domain)
    'vorleser.net',         # Vorleser.net (kostenlose deutsche Hörbücher)
    'hoerspielprojekt.de',  # Hörspielprojekt (kostenlose Hörspiele)
)


def _mac_tk_dialog(title, message, buttons, parent=None):
    """Modales Tk-Fenster statt nativem NSAlert (stürzt unter macOS 26/27 mit SIGTRAP ab)."""
    result = {"value": buttons[-1][1] if buttons else None}
    root = parent
    if root is None:
        root = getattr(tk, "_default_root", None)
    win = tk.Toplevel(root) if root is not None else tk.Toplevel()
    try:
        win.title(str(title or ""))
    except tk.TclError:
        pass
    if parent is not None:
        try:
            win.transient(parent)
        except tk.TclError:
            pass
    try:
        win.resizable(True, True)
        bg = "#383838"
        try:
            if parent is not None:
                bg = parent.cget("bg") or bg
        except tk.TclError:
            pass
        win.configure(bg=bg)
        win.attributes("-topmost", True)
    except tk.TclError:
        bg = "#383838"

    frm = ttk.Frame(win, padding=16)
    frm.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frm, text=str(message or ""), wraplength=440, justify=tk.LEFT).pack(
        anchor=tk.W, pady=(0, 14)
    )
    row = ttk.Frame(frm)
    row.pack(anchor=tk.E)

    def choose(val):
        result["value"] = val
        try:
            win.destroy()
        except tk.TclError:
            pass

    for i, (label, val) in enumerate(buttons):
        b = ttk.Button(row, text=label, command=lambda v=val: choose(v))
        b.pack(side=tk.RIGHT, padx=4)
        if i == 0:
            try:
                b.focus_set()
                win.bind("<Return>", lambda _e, v=val: choose(v))
            except tk.TclError:
                pass
    win.bind("<Escape>", lambda _e: choose(buttons[-1][1]))
    win.protocol("WM_DELETE_WINDOW", lambda: choose(buttons[-1][1]))
    try:
        win.update_idletasks()
        w, h = max(win.winfo_reqwidth(), 360), max(win.winfo_reqheight(), 120)
        if parent is not None:
            px = parent.winfo_rootx() + max(20, (parent.winfo_width() - w) // 2)
            py = parent.winfo_rooty() + max(20, (parent.winfo_height() - h) // 3)
        else:
            px = max(40, (win.winfo_screenwidth() - w) // 2)
            py = max(40, (win.winfo_screenheight() - h) // 3)
        win.geometry(f"+{int(px)}+{int(py)}")
    except tk.TclError:
        pass
    try:
        win.grab_set()
    except tk.TclError:
        pass
    try:
        win.wait_window()
    except tk.TclError:
        pass
    return result["value"]


class _MacSafeMessageBox:
    """tkinter.messagebox auf macOS 26/27: natives NSAlert → GameController-SIGTRAP."""

    def showinfo(self, title=None, message=None, **kwargs):
        _mac_tk_dialog(title, message, [("OK", "ok")], kwargs.get("parent"))
        return "ok"

    def showwarning(self, title=None, message=None, **kwargs):
        _mac_tk_dialog(title, message, [("OK", "ok")], kwargs.get("parent"))
        return "ok"

    def showerror(self, title=None, message=None, **kwargs):
        _mac_tk_dialog(title, message, [("OK", "ok")], kwargs.get("parent"))
        return "ok"

    def askyesno(self, title=None, message=None, **kwargs):
        return bool(_mac_tk_dialog(title, message, [("Ja", True), ("Nein", False)], kwargs.get("parent")))

    def askokcancel(self, title=None, message=None, **kwargs):
        return bool(_mac_tk_dialog(title, message, [("OK", True), ("Abbrechen", False)], kwargs.get("parent")))

    def askretrycancel(self, title=None, message=None, **kwargs):
        return bool(_mac_tk_dialog(title, message, [("Erneut", True), ("Abbrechen", False)], kwargs.get("parent")))

    def askyesnocancel(self, title=None, message=None, **kwargs):
        return _mac_tk_dialog(
            title, message, [("Ja", True), ("Nein", False), ("Abbrechen", None)], kwargs.get("parent")
        )

    def askquestion(self, title=None, message=None, **kwargs):
        yes = _mac_tk_dialog(title, message, [("Ja", True), ("Nein", False)], kwargs.get("parent"))
        return "yes" if yes else "no"


if sys.platform == "darwin":
    messagebox = _MacSafeMessageBox()
else:
    messagebox = _tk_messagebox


def _store_edition() -> bool:
    """Microsoft-Store-Paket: ohne Deezer, Spotify und Audible."""
    try:
        from path_helper import is_microsoft_store
        return bool(is_microsoft_store())
    except Exception:
        return False


def _is_store_blocked_music_url(url: str) -> bool:
    if not _store_edition() or not url:
        return False
    ul = url.lower()
    return any(
        part in ul
        for part in ("spotify.com", "deezer.com", "deezer.page.link", "link.deezer.com", "audible.")
    )


def _music_sources_for_ui():
    sources = list(MUSIC_SOURCES_LIST)
    if _store_edition():
        sources = [item for item in sources if item[0] not in ("Deezer", "Spotify")]
    return sources


def _is_music_mediathek_url(url):
    """Prüft, ob die URL eine im Musik-Tab unterstützte Mediathek oder Hörbuch-/Hörspiel-Seite ist."""
    if not url or not isinstance(url, str):
        return False
    ul = url.lower()
    return any(domain in ul for domain in MUSIC_MEDIATHEK_DOMAINS)


def _normalize_ard_sounds_url(url: str) -> str:
    """Normalisiert ARD Sounds URLs für yt-dlp (entfernt /embed/, behält ardsounds.de bei)."""
    if not url or 'ardsounds.de' not in url.lower():
        return url
    
    url_lower = url.lower()
    import re
    
    # Extrahiere URN falls vorhanden (urn:ard:episode:... oder urn:ard:show:...)
    # URN kann am Ende ein trailing slash haben, den wir entfernen
    urn_match = re.search(r'urn:ard:(?:episode|show):[^/\s"\'<>]+/?', url, re.IGNORECASE)
    if urn_match:
        urn = urn_match.group(0).rstrip('/')
        # Entferne /embed/ und behalte ardsounds.de (nicht mehr zu ardaudiothek.de konvertieren)
        if 'urn:ard:episode:' in urn.lower():
            # Entferne /embed/ falls vorhanden
            if '/embed/episode/' in url_lower:
                return f"https://www.ardsounds.de/episode/{urn}"
            else:
                return f"https://www.ardsounds.de/episode/{urn}"
        elif 'urn:ard:show:' in urn.lower():
            # Entferne /embed/ falls vorhanden
            if '/embed/sendung/' in url_lower or '/embed/podcast/' in url_lower:
                return f"https://www.ardsounds.de/sendung/{urn}"
            else:
                return f"https://www.ardsounds.de/sendung/{urn}"
    
    # Falls keine URN direkt gefunden, aber /embed/episode/ oder /embed/podcast/ vorhanden: entferne /embed/ und extrahiere URN
    if '/embed/' in url_lower:
        url_no_embed = url.replace('/embed/episode/', '/episode/')
        url_no_embed = url_no_embed.replace('/embed/podcast/', '/podcast/')
        url_no_embed = url_no_embed.replace('/embed/sendung/', '/sendung/')
        url_no_embed = url_no_embed.rstrip('/')
        
        # Versuche URN aus der bereinigten URL zu extrahieren
        urn_match = re.search(r'urn:ard:(?:episode|show):[^/\s"\'<>]+/?', url_no_embed, re.IGNORECASE)
        if urn_match:
            urn = urn_match.group(0).rstrip('/')
            if 'urn:ard:episode:' in urn.lower():
                return f"https://www.ardaudiothek.de/episode/{urn}"
            elif 'urn:ard:show:' in urn.lower():
                return f"https://www.ardaudiothek.de/sendung/{urn}"
        
        # Fallback: Wenn keine URN gefunden, aber /episode/ oder /podcast/ vorhanden, versuche ID zu extrahieren
        episode_match = re.search(r'/episode/([^/\s"\'<>]+)', url_no_embed)
        if episode_match:
            episode_id = episode_match.group(1).rstrip('/')
            if 'urn:ard:episode:' in episode_id.lower():
                return f"https://www.ardsounds.de/episode/{episode_id}"
        podcast_match = re.search(r'/podcast/([^/\s"\'<>]+)', url_no_embed)
        if podcast_match:
            podcast_id = podcast_match.group(1).rstrip('/')
            if 'urn:ard:show:' in podcast_id.lower():
                return f"https://www.ardsounds.de/sendung/{podcast_id}"
        
        # Letzter Fallback: Entferne nur /embed/, behalte ardsounds.de
        return url_no_embed
    
    return url


# Für Dialog "Unterstützte Seiten" (Musik-Tab): Anzeigename : URL
MUSIC_SOURCES_LIST = (
    ("Deezer", "https://www.deezer.com/"),
    ("Spotify", "https://www.spotify.com/"),
    ("YouTube Musik", "https://music.youtube.com/"),
    ("ARD Audiothek", "https://www.ardaudiothek.de/"),
    ("ARD Sounds", "https://www.ardsounds.de/"),
    ("BR Audiothek", "https://www.br.de/mediathek/audiothek/"),
    ("NDR Audiothek", "https://www.ndr.de/mediathek/hoerspiel/"),
    ("WDR Audiothek", "https://www1.wdr.de/mediathek/audio/"),
    ("MDR Audiothek", "https://www.mdr.de/mediathek/audio/"),
    ("SWR Audiothek", "https://www.swr.de/audiothek/"),
    ("rbb Audiothek", "https://www.rbb-online.de/audiothek/"),
    ("SR Audiothek", "https://www.sr.de/audiothek/"),
    ("HR Audiothek", "https://www.hr.de/audiothek/"),
    ("Deutschlandfunk", "https://www.deutschlandfunk.de/"),
    ("Deutschlandradio", "https://www.deutschlandradio.de/"),
    ("ORF (Österreich)", "https://radiothek.orf.at/"),
    ("LibriVox", "https://librivox.org/"),
    ("Vorleser.net", "https://www.vorleser.net/"),
    ("Hörspielprojekt", "https://www.hoerspielprojekt.de/"),
)

try:
    import series_watch
except ImportError:
    series_watch = None  # type: ignore


class _ParallelDownloadGuiProxy:
    """Eigene yt-dlp-Prozess-Referenz pro parallelem Queue-Worker; Abbruch über Haupt-GUI."""
    __slots__ = ('_main', '_process')

    def __init__(self, main):
        self._main = main
        self._process = None

    @property
    def settings(self):
        return self._main.settings

    @property
    def video_download_cancelled(self):
        return self._main.video_download_cancelled

    @property
    def video_download_process(self):
        return self._process

    @video_download_process.setter
    def video_download_process(self, p):
        self._process = p
        if p is not None:
            lst = getattr(self._main, '_parallel_video_process_list', None)
            if lst is not None and p not in lst:
                lst.append(p)


class DeezerDownloaderGUI:
    """GUI-Klasse für den Deezer Downloader"""
    
    def __init__(self, root):
        self.root = root
        self.root.title(f"Universal Downloader {get_version()}")
        
        # Setze WM_CLASS für Linux erneut (falls es in main() nicht funktioniert hat)
        if sys.platform.startswith("linux"):
            try:
                # Versuche verschiedene Methoden
                self.root.wm_class("UniversalDownloader", "UniversalDownloader")
                self.root.tk.call('wm', 'class', self.root._w, 'UniversalDownloader')
                self.root.tk.call('wm', 'name', self.root._w, 'Universal Downloader')
            except Exception:
                try:
                    self.root.wm_class("UniversalDownloader")
                except:
                    pass
        
        # Setze Programm-Icon
        self._set_application_icon()
        
        # Basis-Download-Pfad (muss zuerst gesetzt werden, damit _load_window_geometry funktioniert)
        try:
            # Verwende path_helper um den echten Download-Ordner zu erkennen
            from path_helper import get_app_base_path
            self.base_download_path = get_app_base_path()
        except ImportError:
            # Fallback: Alte Methode
            try:
                self.base_download_path = Path.home() / "Downloads" / "Universal Downloader"
                self.base_download_path.mkdir(parents=True, exist_ok=True)
                if not self.base_download_path.exists():
                    # Fallback: Verwende AppData
                    if sys.platform == "win32":
                        appdata = os.getenv('APPDATA', Path.home() / "AppData" / "Roaming")
                        self.base_download_path = Path(appdata) / "Universal Downloader"
                    else:
                        self.base_download_path = Path.home() / ".universal-downloader"
                    self.base_download_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                # Fallback bei Fehler
                if sys.platform == "win32":
                    appdata = os.getenv('APPDATA', Path.home() / "AppData" / "Roaming")
                    self.base_download_path = Path(appdata) / "Universal Downloader"
                else:
                    self.base_download_path = Path.home() / ".universal-downloader"
                self.base_download_path.mkdir(parents=True, exist_ok=True)
                print(f"[WARNING] Konnte Standard-Download-Pfad nicht erstellen, verwende: {self.base_download_path}")
        
        # Lade gespeicherte Fenstergröße (wird nach create_widgets gesetzt)
        self._saved_geometry = self._load_window_geometry()
        
        # Setze Standard-Größe (wird später überschrieben, falls gespeicherte Größe existiert)
        if not self._saved_geometry:
            self.root.geometry("1280x820")
        
        self.root.resizable(True, True)
        # Standard-Mindestgröße (responsive gilt ab dieser Breite/Höhe)
        self._min_window_width = 1000
        self._min_window_height = 620
        self._ref_window_width = 1280  # Referenzbreite für „Standard“-Skalierung
        self.root.minsize(self._min_window_width, self._min_window_height)
        
        # Speichere Fenstergröße bei Änderungen
        self.root.bind('<Configure>', self._on_window_configure)
        
        # Initialisiere Timer-Variablen
        self._geometry_save_timer = None
        self._resize_panels_timer = None
        self._series_watch_last_run = 0.0
        self._series_watch_after_id = None
        
        # Einstellungen laden
        self.settings = self._load_settings()
        
        # Log-Datei Setup
        self.log_file = None
        self._setup_logging()
        
        # Führe Log-Aufräumen beim Start aus (wenn aktiviert)
        if self.settings.get('log_cleanup_enabled', False):
            self._cleanup_old_logs()
        
        # Prüfe und installiere Abhängigkeiten im Hintergrund (falls nötig)
        self.root.after(1000, self._ensure_dependencies_background)
        
        # Changelog nach Update / erstem Start mit neuer Version (kurz nach dem Laden)
        self.root.after(1500, self._maybe_show_changelog_after_update)
        # Prüfe auf Updates beim Start (wenn aktiviert)
        if self.settings.get('auto_check_updates', True):
            # Prüfe im Hintergrund nach 5 Sekunden (damit GUI vollständig geladen ist)
            self.root.after(5000, self._check_updates_on_start)
        
        # Downloader-Instanz
        self.downloader = None
        # Verwende gespeicherte Pfade aus Einstellungen
        # Gemeinsamer Pfad für Deezer und Spotify (USB/Volume kann fehlen → Fallback unter App-Basisordner)
        self.music_download_path = self._prepare_path_or_fallback(
            Path(self.settings.get('default_music_path', str(self.base_download_path / "Musik"))),
            self.base_download_path / "Musik",
            "Musik",
        )
        self.auth = None
        
        # Audible
        self.audible_auth = None
        self.audible_library = None
        self.audible_download_path = self._prepare_path_or_fallback(
            Path(self.settings.get('default_audible_path', str(self.base_download_path / "Audible"))),
            self.base_download_path / "Audible",
            "Audible",
        )
        
        # Video Downloader
        self.video_download_path = self._prepare_path_or_fallback(
            Path(self.settings.get('default_video_path', str(self.base_download_path / "Video"))),
            self.base_download_path / "Video",
            "Video",
        )
        
        # Download-Prozess-Referenz für Abbrechen
        self.video_download_process = None
        self._parallel_video_process_list = []
        self._video_active_urls = set()
        self._video_parallel_workers = 0
        self._video_parallel_lock = threading.Lock()
        self._video_convert_lock = threading.Lock()
        self._video_queue_hold = False
        self.video_download_cancelled = False
        self.video_download_cancel_current_only = False  # Nur aktuelle Folge abbrechen
        self.video_download_episodes_total = 0  # Gesamtanzahl Episoden beim Serien-Download
        
        # Spotify Downloader (für API-Funktionen)
        self.spotify_downloader = None
        
        # UI erstellen
        self.create_widgets()
        
        # Download-Pfad initialisieren
        self.update_download_path()
        
        # Jetzt die gespeicherte Fenstergröße setzen (nachdem alle Widgets erstellt sind)
        if self._saved_geometry:
            self.root.update_idletasks()  # Stelle sicher, dass alle Widgets gerendert sind
            self.root.geometry(self._saved_geometry)
            self.root.update_idletasks()  # Aktualisiere nach dem Setzen der Geometrie
            self._schedule_resize_download_panels()  # Responsive sofort auf gespeicherte Größe anwenden
        
        # Initialisiere letzte Geometrie nach dem Setzen
        self._last_geometry = self.root.geometry()
        try:
            self.root.deiconify()
        except Exception:
            pass
        # Nochmal nach kurzer Verzögerung: Layout ist dann stabil, Buttons/Inhalte passen sich an
        self.root.after(350, self._resize_download_panels)
        # Serien-Wächter: erster Timer-Tick nach 90 s, danach minütlich (Prüfintervall in Einstellungen)
        self.root.after(90000, self._series_watch_schedule_tick)
        # Tray-Icon (Windows-Infobereich / macOS-Menüleiste) mit der GUI starten
        self.root.after(1800, self._start_series_watch_tray)
        self.root.after(2500, self._series_watch_pull_gui_queue)
        
        # Prüfe ob bereits angemeldet (Deezer)
        if DeezerAuth:
            try:
                temp_auth = DeezerAuth()
                if temp_auth.is_logged_in():
                    self.auth = temp_auth
                    self.update_auth_status()
            except:
                pass
        
        # Prüfe ob bereits angemeldet (Audible)
        if AudibleAuth:
            try:
                from path_helper import get_app_base_path
                temp_audible_auth = AudibleAuth(str(get_app_base_path() / ".audible_config.json"))
                if temp_audible_auth.is_logged_in():
                    self.audible_auth = temp_audible_auth
                    self.audible_library = AudibleLibrary(temp_audible_auth)
                    # Aktualisiere Status
                    email = temp_audible_auth.email if temp_audible_auth.email else "Gespeicherte Anmeldung"
                    self.audible_status_var.set(f"✓ Angemeldet ({email})")
                    self.audible_load_button.config(state=tk.NORMAL)
            except Exception as e:
                print(f"Fehler beim Laden der gespeicherten Audible-Anmeldung: {e}")
    
    def _set_application_icon(self):
        """Setzt das Programm-Icon für das Hauptfenster und den Prozess"""
        try:
            # Suche nach Icon-Dateien im Projektverzeichnis
            # Priorität: .ico vor .png (Windows bevorzugt .ico)
            script_dir = Path(__file__).parent.absolute()
            icon_paths = [
                script_dir / "icon.ico",  # Windows bevorzugt .ico
                script_dir / "icon.png",
                script_dir / "app_icon.ico",
                script_dir / "app_icon.png",
            ]
            
            icon_set = False
            icon_path_found = None
            
            for icon_path in icon_paths:
                if icon_path.exists():
                    icon_path_found = icon_path
                    try:
                        # Für macOS: iconphoto verwenden
                        if sys.platform == "darwin":
                            try:
                                from PIL import Image, ImageTk
                                img = Image.open(icon_path)
                                # Resize auf Standard-Icon-Größe (macOS bevorzugt 512x512 oder 256x256)
                                img = img.resize((256, 256), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(img)
                                self.root.iconphoto(True, photo)
                                # Speichere Referenz, damit das Icon nicht gelöscht wird
                                self.root.icon_image = photo
                                icon_set = True
                                self._safe_log(f"[ICON] Icon geladen: {icon_path.name}")
                                break
                            except ImportError:
                                # PIL nicht verfügbar, versuche mit tkinter PhotoImage
                                try:
                                    if icon_path.suffix.lower() == '.png':
                                        photo = tk.PhotoImage(file=str(icon_path))
                                        self.root.iconphoto(True, photo)
                                        self.root.icon_image = photo
                                        icon_set = True
                                        self._safe_log(f"[ICON] Icon geladen (tkinter): {icon_path.name}")
                                        break
                                except Exception as e:
                                    self._safe_log(f"[ICON] Fehler beim Laden von {icon_path.name}: {e}")
                                    continue
                        elif sys.platform.startswith("linux"):
                            # Für Linux: iconphoto verwenden (PNG bevorzugt)
                            try:
                                from PIL import Image, ImageTk
                                img = Image.open(icon_path)
                                # Linux bevorzugt 48x48 oder 64x64 Icons
                                img = img.resize((64, 64), Image.Resampling.LANCZOS)
                                photo = ImageTk.PhotoImage(img)
                                self.root.iconphoto(True, photo)
                                # Speichere Referenz, damit das Icon nicht gelöscht wird
                                self.root.icon_image = photo
                                icon_set = True
                                self._safe_log(f"[ICON] Icon geladen (Linux): {icon_path.name}")
                                break
                            except ImportError:
                                # PIL nicht verfügbar, versuche mit tkinter PhotoImage
                                try:
                                    if icon_path.suffix.lower() == '.png':
                                        photo = tk.PhotoImage(file=str(icon_path))
                                        self.root.iconphoto(True, photo)
                                        self.root.icon_image = photo
                                        icon_set = True
                                        self._safe_log(f"[ICON] Icon geladen (tkinter Linux): {icon_path.name}")
                                        break
                                except Exception as e:
                                    self._safe_log(f"[ICON] Fehler beim Laden von {icon_path.name}: {e}")
                                    continue
                        else:
                            # Für Windows: Verwende iconphoto für PNG, iconbitmap für ICO
                            if icon_path.suffix.lower() == '.ico':
                                # ICO-Datei: Verwende iconbitmap
                                try:
                                    self.root.iconbitmap(str(icon_path))
                                    icon_set = True
                                    self._safe_log(f"[ICON] Icon geladen (ICO): {icon_path.name}")
                                    
                                    # Setze auch das Prozess-Icon (für Taskleiste und Task-Manager)
                                    try:
                                        import ctypes
                                        from ctypes import wintypes
                                        
                                        # Lade Icon aus Datei
                                        # LR_LOADFROMFILE = 0x00000010
                                        # IMAGE_ICON = 1
                                        LR_LOADFROMFILE = 0x00000010
                                        IMAGE_ICON = 1
                                        NULL = 0
                                        
                                        # LoadImageW für Unicode-Pfade
                                        user32 = ctypes.windll.user32
                                        hicon = user32.LoadImageW(
                                            NULL,
                                            str(icon_path),
                                            IMAGE_ICON,
                                            0, 0,
                                            LR_LOADFROMFILE
                                        )
                                        
                                        if hicon:
                                            # Setze Icon für große und kleine Icons
                                            # WM_SETICON: 0x0080 (ICON_BIG), 0x0081 (ICON_SMALL)
                                            # Warte kurz, damit das Fenster vollständig initialisiert ist
                                            try:
                                                hwnd = self.root.winfo_id()
                                                if hwnd:
                                                    user32.SendMessageW(hwnd, 0x0080, hicon, 0)  # ICON_BIG
                                                    user32.SendMessageW(hwnd, 0x0081, hicon, 0)  # ICON_SMALL
                                                    self._safe_log(f"[ICON] Prozess-Icon gesetzt: {icon_path.name}")
                                            except Exception as e2:
                                                # Versuche es später nochmal
                                                self.root.after(500, lambda p=icon_path: self._set_process_icon(p))
                                                self._safe_log(f"[ICON] Versuche Prozess-Icon später zu setzen: {e2}")
                                    except Exception as e:
                                        # Fehler beim Setzen des Prozess-Icons ist nicht kritisch
                                        self._safe_log(f"[ICON] Konnte Prozess-Icon nicht setzen: {e}")
                                    
                                    break
                                except Exception as e:
                                    self._safe_log(f"[ICON] Fehler beim Laden von ICO: {e}")
                                    continue
                            else:
                                # PNG-Datei: Konvertiere zu PhotoImage und verwende iconphoto
                                try:
                                    from PIL import Image, ImageTk
                                    img = Image.open(icon_path)
                                    # Windows bevorzugt 32x32 oder 16x16 Icons für die Taskleiste
                                    img = img.resize((32, 32), Image.Resampling.LANCZOS)
                                    photo = ImageTk.PhotoImage(img)
                                    self.root.iconphoto(True, photo)
                                    # Speichere Referenz, damit das Icon nicht gelöscht wird
                                    self.root.icon_image = photo
                                    icon_set = True
                                    self._safe_log(f"[ICON] Icon geladen (PNG->PhotoImage): {icon_path.name}")
                                    break
                                except ImportError:
                                    # PIL nicht verfügbar, versuche mit tkinter PhotoImage
                                    try:
                                        photo = tk.PhotoImage(file=str(icon_path))
                                        self.root.iconphoto(True, photo)
                                        self.root.icon_image = photo
                                        icon_set = True
                                        self._safe_log(f"[ICON] Icon geladen (tkinter PhotoImage): {icon_path.name}")
                                        break
                                    except Exception as e:
                                        self._safe_log(f"[ICON] Fehler beim Laden von PNG: {e}")
                                        continue
                                except Exception as e:
                                    self._safe_log(f"[ICON] Fehler beim Laden von PNG: {e}")
                                    continue
                    except Exception as e:
                        self._safe_log(f"[ICON] Fehler beim Laden von {icon_path.name}: {e}")
                        continue
            
            if not icon_set:
                self._safe_log("[ICON] Kein Icon gefunden. Bitte fügen Sie 'icon.png' oder 'icon.ico' ins Projektverzeichnis ein.")
            self._apply_app_icon(self.root)
        except Exception as e:
            self._safe_log(f"[ICON] Fehler beim Setzen des Icons: {e}")

    def _apply_app_icon(self, window):
        """Dieselbe Programm-Ikone für Dialoge. Sonst zeigt Windows ein leeres Fehler-Symbol."""
        try:
            if sys.platform == "win32" and getattr(sys, "frozen", False):
                window.iconbitmap(default=sys.executable)
                window.iconbitmap(sys.executable)
                return
        except Exception:
            pass
        try:
            photos = self.root.tk.splitlist(self.root.tk.call("wm", "iconphoto", self.root))
            if photos:
                window.iconphoto(True, *photos)
        except Exception:
            pass
    
    def _safe_log(self, message: str):
        """Sicherer Log-Aufruf, der auch funktioniert, wenn log_file noch nicht initialisiert ist"""
        try:
            if hasattr(self, 'log_file') and self.log_file is not None:
                self.log(message)
            else:
                # Fallback: einfach print, wenn Logging noch nicht initialisiert ist
                print(message)
        except:
            # Falls auch das fehlschlägt, einfach ignorieren
            pass

    def _prepare_path_or_fallback(self, preferred: Path, fallback: Path, label: str) -> Path:
        """Legt preferred an; bei OSError (Volume weg, keine Rechte) fallback, sonst Notfall unter ~/Downloads."""
        for p in (preferred, fallback):
            try:
                p.mkdir(parents=True, exist_ok=True)
                if p != preferred:
                    self._safe_log(f"[PFAD] {label}: nicht nutzbar ({preferred}), verwende {p}")
                return p.resolve()
            except OSError:
                continue
        emergency = Path.home() / "Downloads" / "Universal Downloader" / label.replace(" ", "_")
        try:
            emergency.mkdir(parents=True, exist_ok=True)
            self._safe_log(f"[PFAD] {label}: Notfall-Pfad {emergency}")
            return emergency.resolve()
        except OSError:
            return Path.home().resolve()
    
    def create_widgets(self):
        """Erstellt alle UI-Widgets"""
        
        # Theme und Stile (dark/light aus Einstellungen)
        try:
            ttk.Style().theme_use("clam")
        except tk.TclError:
            pass
        self._apply_theme(self.settings.get('theme', 'dark'))
        self._windows_round_window(self.root)
        
        # Hauptframe
        main_frame = ttk.Frame(self.root, padding="10", style="Download.TFrame")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Titel-Bar
        title_frame = ttk.Frame(main_frame, style="Download.TFrame")
        title_frame.grid(row=0, column=0, pady=(0, 10), sticky=(tk.W, tk.E))
        title_frame.columnconfigure(0, weight=1)
        self._title_label = ttk.Label(title_frame, text="🎵 Universal Downloader", font=("Arial", 12, "bold"), style="Download.TLabel")
        self._title_label.grid(row=0, column=0, sticky=tk.W)
        buttons_frame = ttk.Frame(title_frame, style="Download.TFrame")
        buttons_frame.grid(row=0, column=1, sticky=tk.E)
        self.header_buttons = buttons_frame
        self._register_plugin_area("kopf", buttons_frame)
        ttk.Button(buttons_frame, text="🔍 Suche", command=self.show_search_dialog, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        if series_watch is not None:
            ttk.Button(buttons_frame, text="📺 Serien-Wächter", command=self.show_series_watch_dialog, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="📝 Historie", command=self.show_download_history, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="⭐ Favoriten", command=self.show_favorites, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="📊 Statistiken", command=self.show_statistics, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="⚙️ Einstellungen", command=self.show_settings_dialog, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        
        # Notebook für Tabs (nimmt restliche Höhe/Breite ein); Hauptframe bei Größenänderung mit anpassen
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.notebook.bind("<Configure>", lambda e: self._schedule_resize_download_panels())
        main_frame.bind("<Configure>", lambda e: self._schedule_resize_download_panels())
        
        # Musik Tab (padding=0 damit Container bis zum Rand reicht, kein Hintergrund sichtbar)
        self.music_frame = ttk.Frame(self.notebook, padding="0", style="Download.TFrame")
        self.create_music_tab()
        
        if AudibleAuth and not _store_edition():
            self.audible_frame = ttk.Frame(self.notebook, padding="10", style="Download.TFrame")
            self.create_audible_tab()
        
        if VideoDownloader:
            self.video_frame = ttk.Frame(self.notebook, padding="0", style="Download.TFrame")
            self.create_video_tab()
        self._apply_enabled_tabs()
        
        # Zuletzt geöffneten Tab wiederherstellen und Tab-Wechsel speichern
        last_tab = self.settings.get('last_tab', '🎵 Musik')
        for tab_id in self.notebook.tabs():
            if self.notebook.tab(tab_id, "text") == last_tab:
                self.notebook.select(tab_id)
                break
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)
        try:
            from plugin_loader import activate_plugins
            activate_plugins(self)
        except Exception as exc:
            print(f"Plugins konnten nicht geladen werden: {exc}")
        self._ensure_audible_library()
        self.root.after(150, self._resize_download_panels)
    
    def account_status(self, service: str) -> dict:
        """Für Plugins: ob ein Dienst angemeldet ist und ob die Audible-Bücher schon da sind."""
        name = (service or "").strip().lower()
        if name == "audible":
            signed_in = bool(self.audible_auth and self.audible_auth.is_logged_in())
            books = getattr(self, "audible_books", {}) or {}
            return {
                "signed_in": signed_in,
                "books_loaded": bool(books),
                "book_count": len(books),
            }
        if name == "deezer":
            signed_in = bool(getattr(self, "auth", None) and self.auth.is_logged_in())
            return {"signed_in": signed_in, "books_loaded": False, "book_count": 0}
        for account in self.settings.get("video_accounts", []):
            service_name = str(account.get("service") or "")
            if name and name in service_name.lower():
                cookies = str(account.get("cookies") or "").strip()
                return {"signed_in": bool(cookies), "books_loaded": False, "book_count": 0}
        return {"signed_in": False, "books_loaded": False, "book_count": 0}

    def _builtin_tab_specs(self):
        """Feste Tabs in der Reihenfolge Musik, Audible, Video."""
        specs = [("music", getattr(self, "music_frame", None), "🎵 Musik")]
        specs.append(("audible", getattr(self, "audible_frame", None), "📚 Audible"))
        specs.append(("video", getattr(self, "video_frame", None), "🎬 Video Downloader"))
        return [(key, frame, title) for key, frame, title in specs if frame is not None]

    def _apply_enabled_tabs(self):
        """Zeigt nur die Tabs, die in den Einstellungen an sind. Audible ist standardmäßig aus."""
        enabled = self.settings.get("enabled_tabs")
        if not isinstance(enabled, dict):
            enabled = {}
        flags = {
            "music": bool(enabled.get("music", True)),
            "audible": bool(enabled.get("audible", False)) and not _store_edition(),
            "video": bool(enabled.get("video", True)),
        }
        specs = self._builtin_tab_specs()
        if specs and not any(flags.get(key, False) for key, _frame, _title in specs):
            flags["music"] = True
        builtin_ids = {str(frame) for _key, frame, _title in specs}
        plugin_tabs = []
        for tab_id in list(self.notebook.tabs()):
            if tab_id not in builtin_ids:
                plugin_tabs.append((tab_id, self.notebook.tab(tab_id, "text")))
            self.notebook.forget(tab_id)
        for key, frame, title in specs:
            if flags.get(key, False):
                self.notebook.add(frame, text=title)
        for tab_id, title in plugin_tabs:
            self.notebook.add(tab_id, text=title)

    def _ensure_audible_library(self):
        """Lädt die Hörbücher einmal, wenn der Audible-Tab offen ist."""
        try:
            tab_id = self.notebook.select()
            if "Audible" not in self.notebook.tab(tab_id, "text"):
                return
        except Exception:
            return
        if getattr(self, "_audible_library_loaded", False) or getattr(self, "_audible_library_loading", False):
            return
        self.load_audible_library(manual=False)

    def _register_plugin_area(self, name, frame):
        """Benannte Stelle, an der Plugins Knöpfe hinzufügen oder entfernen."""
        if not hasattr(self, "plugin_areas"):
            self.plugin_areas = {}
        self.plugin_areas[name] = frame

    def _schedule_resize_download_panels(self):
        """Plant Anpassung (entprellt), danach ggf. Nachlauf bis Größe stabil."""
        if getattr(self, '_resize_panels_timer', None) is not None:
            try:
                self.root.after_cancel(self._resize_panels_timer)
            except Exception:
                pass
        self._resize_panels_timer = self.root.after(40, self._do_resize_download_panels)
    
    def _on_notebook_tab_changed(self, event=None):
        """Speichert den aktuell gewählten Tab in den Einstellungen und passt Download-Bereiche an."""
        try:
            tab_id = self.notebook.select()
            if tab_id:
                self.settings['last_tab'] = self.notebook.tab(tab_id, "text")
                self._save_settings()
                if "Audible" in self.notebook.tab(tab_id, "text"):
                    self._ensure_audible_library()
            self._schedule_resize_download_panels()
        except Exception:
            pass
    
    def _update_download_pane_width(self, paned, force_width=None):
        """Setzt Sash-Position so, dass der Download-Bereich (roter Bereich) den Platz nutzt: min 400, max 800, sonst ~40 % der Breite."""
        try:
            pw = force_width if force_width is not None else paned.winfo_width()
            if pw <= 0:
                return
            # Größerer Anteil, damit der linke Bereich den dunklen Hintergrund „überdeckt“
            w = max(450, min(1000, int(pw * 0.55)))
            paned.sashpos(0, w)
            children = paned.winfo_children()
            if children:
                children[0].configure(width=w)
        except (tk.TclError, AttributeError, IndexError):
            pass
    
    def _apply_dark_toplevel(self, win):
        """Toplevel-Fenster (Queue, Einstellungen) an aktuelles Theme anpassen."""
        try:
            win.configure(bg=getattr(self, '_tk_bg_panel', '#383838'))
        except tk.TclError:
            pass
        self._windows_round_window(win)

    def _windows_round_window(self, win) -> None:
        """Windows-11-Rahmen mit runden Ecken.

        Ältere Windows-11-Versionen (auf der ARM-VM 25H2) runden Programmfenster von
        selbst. Neuere (auf dem AMD-Rechner 26H2) lassen sie eckig, bis das Programm
        die runde Ecke ausdrücklich anfordert.
        """
        if sys.platform != "win32":
            return

        def apply(_event=None):
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                dwmapi = ctypes.windll.dwmapi
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                dwmapi.DwmSetWindowAttribute.argtypes = [
                    wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                ]
                dwmapi.DwmSetWindowAttribute.restype = ctypes.c_long
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT,
                ]
                hwnd = user32.GetAncestor(win.winfo_id(), 2)  # GA_ROOT
                if not hwnd:
                    return
                pref = ctypes.c_int(2)  # DWMWCP_ROUND
                dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
                theme = (getattr(self, "settings", None) or {}).get("theme", "dark")
                dark = ctypes.c_int(0 if str(theme).lower() == "light" else 1)
                for attr in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
                    dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(dark), ctypes.sizeof(dark))
                user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
            except Exception:
                pass

        try:
            win.bind("<Map>", apply, add="+")
        except Exception:
            pass
        try:
            win.after(80, apply)
        except Exception:
            pass

    def _fit_dialog(self, win, width, height, min_width=None, min_height=None):
        """Dialoggröße setzen und auf den Bildschirm begrenzen (macOS/Windows/Linux)."""
        try:
            win.update_idletasks()
            sw = int(win.winfo_screenwidth() or 1280)
            sh = int(win.winfo_screenheight() or 800)
        except tk.TclError:
            sw, sh = 1280, 800
        w = max(320, min(int(width), sw - 40))
        h = max(220, min(int(height), sh - 80))
        win.geometry(f"{w}x{h}")
        if min_width is not None or min_height is not None:
            win.minsize(int(min_width or min(w, 400)), int(min_height or min(h, 280)))
        return w, h

    def _scroll_wheel_step(self, event):
        delta = getattr(event, "delta", 0) or 0
        if delta:
            if abs(delta) >= 120:
                step = int(-delta / 120)
            else:
                step = int(-delta)
            if step == 0:
                step = -1 if delta > 0 else 1
            return step
        if getattr(event, "num", None) == 4:
            return -1
        if getattr(event, "num", None) == 5:
            return 1
        return 0

    def _on_global_scroll_wheel(self, event):
        """Scrollt die Fläche unter dem Mauszeiger, auch wenn ein Eingabefeld den Fokus hat."""
        step = self._scroll_wheel_step(event)
        if not step:
            return
        try:
            px, py = self.root.winfo_pointerxy()
            target = self.root.winfo_containing(px, py)
        except tk.TclError:
            return
        if target is None:
            return
        try:
            if target.winfo_class() in ("Scrollbar", "TScrollbar"):
                return
        except tk.TclError:
            return
        canvases = []
        for canvas in getattr(self, "_scroll_canvases", []):
            try:
                if canvas.winfo_exists():
                    canvases.append(canvas)
            except tk.TclError:
                pass
        self._scroll_canvases = canvases
        widget = target
        while widget is not None:
            if widget in canvases:
                widget.yview_scroll(step, "units")
                return "break"
            widget = getattr(widget, "master", None)

    def _bind_scroll_wheel(self, canvas, inner=None):
        """Mausrad scrollt die Fläche, auch über den Einträgen und nicht nur an der Leiste."""
        if not hasattr(self, "_scroll_canvases"):
            self._scroll_canvases = []
        if canvas not in self._scroll_canvases:
            self._scroll_canvases.append(canvas)
        if not getattr(self, "_scroll_wheel_installed", False):
            self._scroll_wheel_installed = True
            self.root.bind_all("<MouseWheel>", self._on_global_scroll_wheel, add="+")
            self.root.bind_all("<Button-4>", self._on_global_scroll_wheel, add="+")
            self.root.bind_all("<Button-5>", self._on_global_scroll_wheel, add="+")

    def _entry_place_caret(self, entry):
        """Klick setzt die Schreibmarke an die Stelle, statt den ganzen Text zu markieren."""
        def _fix(event):
            widget = event.widget
            click_x = event.x

            def place():
                try:
                    text = widget.get()
                    if widget.selection_present() and widget.index("sel.first") == 0 and widget.index("sel.last") == len(text):
                        widget.icursor(f"@{click_x}")
                        widget.selection_clear()
                except tk.TclError:
                    pass

            widget.after_idle(place)

        entry.bind("<Button-1>", _fix, add="+")

    def _entry_edit_menu(self, entry):
        """Rechtsklick: Ausschneiden, Kopieren, Einfügen, Alles markieren."""
        menu = tk.Menu(entry, tearoff=0)

        def cut():
            copy()
            try:
                entry.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

        def copy():
            try:
                text = entry.selection_get()
            except tk.TclError:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        def paste():
            entry.focus_set()
            try:
                text = self.root.clipboard_get()
            except tk.TclError:
                return
            try:
                entry.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            entry.insert("insert", text)

        def select_all():
            entry.selection_range(0, tk.END)
            entry.icursor(tk.END)

        menu.add_command(label="Ausschneiden", command=cut)
        menu.add_command(label="Kopieren", command=copy)
        menu.add_command(label="Einfügen", command=paste)
        menu.add_separator()
        menu.add_command(label="Alles markieren", command=select_all)

        def popup(event):
            entry.focus_set()
            try:
                entry.icursor(f"@{event.x}")
            except tk.TclError:
                pass
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        entry.bind("<Button-2>", popup, add="+")
        entry.bind("<Button-3>", popup, add="+")

    def _style_log_scrolledtext(self, st_widget):
        """Log-Widget (Hintergrund/Scrollbar) ans aktuelle Theme anpassen."""
        try:
            log_bg = getattr(self, '_tk_log_bg', '#383838')
            trough = getattr(self, '_tk_bg_card', '#424242')
            sb_bg = getattr(self, '_tk_bg_panel', '#383838')
            sb_active = getattr(self, '_tk_btn_bg', '#4a4a4a')
            st_widget.configure(bg=log_bg, highlightthickness=0)
            for c in st_widget.winfo_children():
                try:
                    c.configure(highlightthickness=0, relief=tk.FLAT, bg=log_bg)
                except tk.TclError:
                    pass
                if c.winfo_class() == "Scrollbar":
                    try:
                        c.configure(bg=sb_bg, troughcolor=trough, activebackground=sb_active)
                    except tk.TclError:
                        pass
        except Exception:
            pass
    
    def _do_resize_download_panels(self):
        """Führt die Anpassung aus und plant Nachlauf, bis Größe stabil (Download-Bereich zieht mit)."""
        self._resize_panels_timer = None
        self._resize_download_panels()
        # Während des Ziehens weiter anpassen, bis Größe sich nicht mehr ändert
        self._resize_panels_timer = self.root.after(60, self._resize_download_panels_followup)
    
    def _resize_download_panels_followup(self):
        """Prüft ob sich Breite geändert hat und passt erneut an (flüssiges Mitziehen beim Ziehen)."""
        self._resize_panels_timer = None
        try:
            if not hasattr(self, 'notebook'):
                return
            self.root.update_idletasks()
            nw = self.notebook.winfo_width()
            if nw <= 0:
                nw = self.root.winfo_width() - 40
            last = getattr(self, '_last_resize_nw', -1)
            if last == nw:
                return
            self._last_resize_nw = nw
            self._resize_download_panels()
            self._resize_panels_timer = self.root.after(60, self._resize_download_panels_followup)
        except Exception:
            pass
    
    def _resize_download_panels(self):
        """Setzt Breite und Schriftgröße im Download-Bereich (responsive an Fensterbreite)."""
        try:
            if not hasattr(self, 'notebook'):
                return
            self.root.update_idletasks()
            nw = self.notebook.winfo_width()
            if nw <= 0:
                nw = self.root.winfo_width() - 40
            if nw <= 0:
                nw = getattr(self, '_ref_window_width', 1280)
            if nw <= 0:
                nw = 1280
            min_w = getattr(self, '_min_window_width', 1000)
            ref_w = getattr(self, '_ref_window_width', 1280)
            self._last_resize_nw = nw
            # Linke Spalte: Breite mit Fenster mitziehen (min 280, max 1100, ~50 %)
            w = max(280, min(1100, int(nw * 0.5)))
            if hasattr(self, '_music_options_wrapper') and self._music_options_wrapper.winfo_exists():
                self._music_options_wrapper.configure(width=w)
            if hasattr(self, '_video_options_wrapper') and self._video_options_wrapper.winfo_exists():
                self._video_options_wrapper.configure(width=w)
            if hasattr(self, '_music_container') and self._music_container.winfo_exists():
                self._music_container.columnconfigure(0, minsize=w)
            if hasattr(self, '_video_container') and self._video_container.winfo_exists():
                self._video_container.columnconfigure(0, minsize=w)
            # Canvas-Fensterbreite = aktuelle Breite des Optionsbereichs
            if hasattr(self, '_music_options_inner'):
                self._sync_options_scroll(self._music_options_canvas, self._music_options_inner, self._music_options_canvas_cw_id)
            if hasattr(self, '_video_options_inner'):
                self._sync_options_scroll(self._video_options_canvas, self._video_options_inner, self._video_options_canvas_cw_id)
            # Responsive: Skalierung zwischen Mindestbreite (min_w) und Referenzbreite (ref_w)
            # Vertikales Padding und Abstand für modernes Layout (pad_v / pad_v_large)
            nw_eff = max(nw, min_w)
            t = (nw_eff - min_w) / max(1, ref_w - min_w)  # 0 bei min_w, 1 bei ref_w
            t = max(0.0, min(1.2, t))  # leicht über 1 für große Fenster
            try:
                font_size = max(10, min(12, int(10 + t * 2)))
                pad_v = max(4, min(6, int(4 + t * 2)))
                pad_h = max(10, min(16, int(10 + t * 6)))
                pad_v_large = max(5, min(7, int(5 + t * 2)))
                pad_h_large = max(12, min(18, int(12 + t * 6)))
                _s = ttk.Style()
                _bg = getattr(self, '_tk_bg_panel', '#383838')
                _bg_card = getattr(self, '_tk_bg_card', '#424242')
                _fg = getattr(self, '_tk_fg_text', '#e8e8e8')
                _btn_bg = getattr(self, '_tk_btn_bg', '#4a4a4a')
                _btn_fg = getattr(self, '_tk_btn_fg', '#f0f0f0')
                _btn_hover = getattr(self, '_tk_btn_hover', '#565656')
                _btn_press = getattr(self, '_tk_btn_press', '#3a3a3a')
                _btn_light = getattr(self, '_tk_btn_light', '#5e5e5e')
                _btn_dark = getattr(self, '_tk_btn_dark', '#363636')
                _s.configure("Download.TLabelframe.Label", font=("Arial", font_size), background=_bg, foreground=_fg)
                _s.configure("Download.TButton", font=("Arial", font_size), padding=(pad_h, pad_v), anchor="center", background=_btn_bg, foreground=_btn_fg, relief="raised", borderwidth=2)
                try:
                    _s.configure("Download.TButton", lightcolor=_btn_light, darkcolor=_btn_dark)
                except tk.TclError:
                    pass
                _s.map("Download.TButton", background=[("active", _btn_hover), ("pressed", _btn_press)], relief=[("pressed", "sunken")], foreground=[("active", _btn_fg), ("pressed", _btn_fg)])
                _s.configure("Download.TButton.Large", font=("Arial", font_size), padding=(pad_h_large, pad_v_large), anchor="center", background=_btn_bg, foreground=_btn_fg, relief="raised", borderwidth=2)
                try:
                    _s.configure("Download.TButton.Large", lightcolor=_btn_light, darkcolor=_btn_dark)
                except tk.TclError:
                    pass
                _s.map("Download.TButton.Large", background=[("active", _btn_hover), ("pressed", _btn_press)], relief=[("pressed", "sunken")], foreground=[("active", _btn_fg), ("pressed", _btn_fg)])
                _s.configure("Download.TLabel", font=("Arial", font_size), background=_bg, foreground=_fg)
                choice_size = max(12, min(14, font_size + 2))
                _s.configure("Download.TRadiobutton", font=("Arial", choice_size), padding=(2, 1), background=_bg, foreground=_fg)
                _s.map("Download.TRadiobutton", background=[("active", _bg)], foreground=[("active", _fg)])
                _s.configure("Download.TCheckbutton", font=("Arial", choice_size), padding=(2, 1), background=_bg, foreground=_fg)
                _s.map("Download.TCheckbutton", background=[("active", _bg)], foreground=[("active", _fg)])
                url_size = max(12, min(14, font_size + 2))
                status_size = max(12, min(18, int(12 + t * 6)))
                bar_h = max(14, min(26, int(14 + t * 10)))
                for lab in (
                    getattr(self, 'music_status_label', None),
                    getattr(self, 'video_status_label', None),
                    getattr(self, 'music_jobs_label', None),
                    getattr(self, 'video_jobs_label', None),
                ):
                    try:
                        if lab is not None and lab.winfo_exists():
                            lab.configure(font=("Arial", status_size))
                    except (tk.TclError, AttributeError):
                        pass
                try:
                    _s.configure("Horizontal.TProgressbar", thickness=bar_h)
                except tk.TclError:
                    pass
                for ent in getattr(self, "_url_entries", ()):
                    try:
                        if ent.winfo_exists():
                            ent.configure(font=("Arial", url_size))
                    except (tk.TclError, AttributeError):
                        pass
                # Titel-Leiste und Tabs responsive skalieren
                title_size = max(10, min(15, int(10 + t * 5)))
                if hasattr(self, '_title_label') and self._title_label.winfo_exists():
                    try:
                        self._title_label.configure(font=("Arial", title_size, "bold"))
                    except (tk.TclError, AttributeError):
                        pass
                try:
                    tab_pad = max(6, min(12, int(6 + t * 6)))
                    _s.configure("TNotebook.Tab", font=("Arial", font_size), padding=(max(8, tab_pad), 5), background=_bg_card, foreground=_fg)
                    _s.map("TNotebook.Tab", background=[("selected", _bg)], expand=[("selected", [1, 1, 1, 0])])
                except tk.TclError:
                    pass
            except Exception:
                pass
        except (tk.TclError, AttributeError):
            pass
    
    def create_music_tab(self):
        """Erstellt den Musik-Tab (Layout: links Optionen, rechts Log; beide Bereiche grenzen direkt an)."""
        main_frame = self.music_frame
        
        container = ttk.Frame(main_frame, style="Download.TFrame")
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self._music_container = container
        container.columnconfigure(0, weight=0, minsize=280)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)
        container.bind("<Configure>", lambda e: self._schedule_resize_download_panels())
        
        # ===== LINKE SEITE: OPTIONEN (responsive, Grid sticky=nsew) =====
        options_wrapper = ttk.Frame(container, width=500, style="Download.TFrame")
        options_wrapper.pack_propagate(False)
        self._music_options_wrapper = options_wrapper
        options_wrapper.grid(row=0, column=0, sticky="nsew")
        
        options_container = ttk.Frame(options_wrapper, style="Download.TFrame")
        options_container.pack(fill=tk.BOTH, expand=True)
        
        info_row = ttk.Frame(options_container, style="Download.TFrame")
        info_row.pack(pady=(0, 2), padx=5, fill=tk.X)
        ttk.Label(info_row, text="Unterstützte Dienste und Mediatheken:", style="Download.TLabel").pack(side=tk.LEFT)
        ttk.Button(info_row, text="Unterstützte Seiten anzeigen", command=lambda: self._show_supported_sources_dialog("Unterstützte Seiten (Musik)", _music_sources_for_ui()), style="Download.TButton").pack(side=tk.LEFT, padx=(8, 0))
        
        _bp = getattr(self, '_tk_bg_panel', '#383838')
        options_canvas = tk.Canvas(options_container, highlightthickness=0, bg=_bp)
        options_scrollbar = ttk.Scrollbar(options_container, orient="vertical", command=options_canvas.yview)
        scrollable_options = ttk.Frame(options_canvas, style="Download.TFrame")
        
        cw_id = options_canvas.create_window((0, 0), window=scrollable_options, anchor="nw")
        self._music_options_canvas = options_canvas
        self._music_options_canvas_cw_id = cw_id
        self._music_options_inner = scrollable_options
        options_canvas.configure(yscrollcommand=options_scrollbar.set)
        self._bind_scroll_wheel(options_canvas, scrollable_options)
        scrollable_options.bind("<Configure>", lambda e: self._sync_options_scroll(options_canvas, scrollable_options, cw_id))
        options_canvas.bind("<Configure>", lambda e: self._sync_options_scroll(options_canvas, scrollable_options, cw_id))
        
        music_actions = ttk.Frame(options_container, style="Download.TFrame")
        music_actions.pack(side=tk.BOTTOM, fill=tk.X)
        options_canvas.pack(side="left", fill="both", expand=True)
        options_scrollbar.pack(side="right", fill="y")
        
        opt = scrollable_options
        
        # Download-Pfad
        path_frame = ttk.LabelFrame(opt, text="Download-Pfad", padding="3", style="Download.TLabelframe")
        path_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.music_path_var = tk.StringVar(value=str(self.music_download_path))
        path_entry = ttk.Entry(path_frame, textvariable=self.music_path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="...", width=3, command=self.browse_music_download_path, style="Download.TButton").pack(side=tk.RIGHT)
        
        # URL-Eingabe
        url_frame = ttk.LabelFrame(opt, text="Musik-URL", padding="3", style="Download.TLabelframe")
        url_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.music_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.music_url_var, font=("Arial", 13))
        url_entry.pack(fill=tk.X, padx=(0, 5), ipady=3)
        self._url_entries = getattr(self, "_url_entries", [])
        self._url_entries.append(url_entry)
        url_entry.bind('<Return>', lambda e: self.start_music_download())
        self._entry_place_caret(url_entry)
        self._entry_edit_menu(url_entry)
        url_entry.focus_set()
        
        ttk.Button(url_frame, text="📁 URLs aus Datei laden", command=self.load_music_urls_from_file, style="Download.TButton").pack(fill=tk.X, pady=(2, 0))
        
        # Account-Buttons (unsichtbar, nur für State – UI in Einstellungen)
        self._music_account_container = ttk.Frame(opt)
        self.auth_status_var = tk.StringVar(value="Deezer: Nicht angemeldet")
        ttk.Label(self._music_account_container, textvariable=self.auth_status_var, style="Download.TLabel").pack(anchor=tk.W)
        btn_row = ttk.Frame(self._music_account_container)
        btn_row.pack(fill=tk.X)
        self.login_button = ttk.Button(btn_row, text="Deezer anmelden", command=self.show_login_dialog, style="Download.TButton")
        self.login_button.pack(side=tk.LEFT, padx=(0, 5))
        self.logout_button = ttk.Button(btn_row, text="Abmelden", command=self.logout, state=tk.DISABLED, style="Download.TButton")
        self.logout_button.pack(side=tk.LEFT)
        # _music_account_container nicht packen → Buttons existieren für State, Anzeige in Einstellungen
        
        # Format (Musik: meist MP3)
        format_frame = ttk.LabelFrame(opt, text="Format", padding="4", style="Download.TLabelframe")
        format_frame.pack(fill=tk.X, padx=5, pady=2)
        default_music_format = self.settings.get('default_music_format', 'mp3')
        self.music_format_var = tk.StringVar(value=default_music_format)
        for index, (text, value) in enumerate([("MP3", "mp3"), ("MP4 (Audio)", "m4a"), ("Keine", "none")]):
            ttk.Radiobutton(format_frame, text=text, variable=self.music_format_var, value=value, style="Download.TRadiobutton").grid(row=0, column=index, sticky=tk.W, padx=(0, 8), pady=1)
        
        # Buttons: nebeneinander und untereinander, mit Abstand und Rand (Grid pady=2, Style mit Padding/Rand)
        button_frame = ttk.Frame(music_actions, style="Download.TFrame")
        button_frame.pack(fill=tk.X, padx=5, pady=0)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        for r in (0, 1, 2):
            button_frame.rowconfigure(r, pad=2)
        self.music_download_button = ttk.Button(button_frame, text="▶ Download starten", command=self.start_music_download, state=tk.NORMAL, style="Download.TButton.Large")
        self.music_download_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 1), pady=2, ipady=0, ipadx=0)
        self.music_cancel_button = ttk.Button(button_frame, text="⏹ Download abbrechen", command=self.cancel_music_download, state=tk.DISABLED, style="Download.TButton")
        self.music_cancel_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(1, 0), pady=2, ipady=0, ipadx=0)
        ttk.Button(button_frame, text="➕ Zur Queue", command=self.add_music_to_queue, style="Download.TButton.Large").grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2, ipady=0, ipadx=0)
        self.music_record_button = ttk.Button(button_frame, text="🎙️ Aufnahme (DRM)", command=self.start_audio_recording, state=tk.NORMAL, style="Download.TButton.Large")
        self.music_record_button.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2, ipady=0, ipadx=0)
        
        # Queue
        self.music_queue_status_label = ttk.Label(music_actions, text="📋 Queue: 0 Einträge", style="Download.TLabel")
        self.music_queue_status_label.pack(fill=tk.X, padx=5, pady=(0, 0))
        queue_btn_frame = ttk.Frame(music_actions, style="Download.TFrame")
        queue_btn_frame.pack(fill=tk.X, padx=5, pady=0)
        queue_btn_frame.columnconfigure(0, weight=1)
        queue_btn_frame.columnconfigure(1, weight=1)
        queue_btn_frame.rowconfigure(0, pad=2)
        ttk.Button(queue_btn_frame, text="📋 Queue anzeigen", command=self.show_music_queue, style="Download.TButton.Large").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 1), pady=2, ipady=0, ipadx=0)
        ttk.Button(queue_btn_frame, text="▶ Queue starten", command=self.start_music_queue_download, style="Download.TButton.Large").grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(1, 0), pady=2, ipady=0, ipadx=0)
        
        # Musik-Queue initialisieren
        if not hasattr(self, 'music_download_queue'):
            self.music_download_queue = []
        
        # ===== RECHTE SEITE: LOG (grenzt direkt an roten Bereich / Trennstrich) =====
        log_container = ttk.Frame(container, style="Download.TFrame")
        log_container.grid(row=0, column=1, sticky="nsew")
        
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        
        ttk.Label(log_container, text="Download-Log:", font=("Arial", 10, "bold"), style="Download.TLabel").pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        _log_bg = getattr(self, '_tk_log_bg', getattr(self, '_tk_bg_panel', '#383838'))
        _log_fg = getattr(self, '_tk_fg_text', '#e8e8e8')
        self.music_log_text = scrolledtext.ScrolledText(
            log_container, wrap=tk.WORD, state=tk.DISABLED, height=25,
            bg=_log_bg, fg=_log_fg, insertbackground=_log_fg,
            highlightthickness=0, relief=tk.FLAT
        )
        self.music_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._style_log_scrolledtext(self.music_log_text)
        
        status_frame = ttk.Frame(log_container, style="Download.TFrame")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.music_progress_var = tk.DoubleVar()
        self.music_progress_bar = ttk.Progressbar(status_frame, variable=self.music_progress_var, maximum=100, mode='determinate', style="Horizontal.TProgressbar")
        self.music_progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.music_status_var = tk.StringVar(value="Bereit")
        music_status_label = ttk.Label(status_frame, textvariable=self.music_status_var, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 12), style="Download.TLabel")
        music_status_label.pack(fill=tk.X)
        self.music_status_label = music_status_label
        self.music_jobs_var = tk.StringVar(value="")
        self.music_jobs_label = ttk.Label(
            status_frame, textvariable=self.music_jobs_var, anchor=tk.W, justify=tk.LEFT,
            font=("Arial", 9), style="Download.TLabel",
        )
        self.music_jobs_label.pack(fill=tk.X, pady=(4, 0))
    
    def create_audible_tab(self):
        """Erstellt den Audible-Tab"""
        main_frame = self.audible_frame
        
        # Konfiguriere Grid
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=0)
        main_frame.rowconfigure(2, weight=1)
        self.audible_books = {}
        
        # Authentifizierung
        auth_frame = ttk.Frame(main_frame)
        auth_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.audible_status_var = tk.StringVar(value="Nicht angemeldet")
        ttk.Label(auth_frame, textvariable=self.audible_status_var).pack(side=tk.LEFT, padx=5)
        
        button_container = ttk.Frame(auth_frame)
        button_container.pack(side=tk.RIGHT, padx=5)
        self._register_plugin_area("audible", button_container)
        
        ttk.Button(
            button_container,
            text="Audible anmelden",
            command=self.show_audible_login
        ).pack(side=tk.LEFT, padx=2)
        
        self.audible_load_button = ttk.Button(
            button_container,
            text="Bibliothek laden",
            command=self.load_audible_library,
            state=tk.DISABLED
        )
        self.audible_load_button.pack(side=tk.LEFT, padx=2)
        
        detail = ttk.LabelFrame(main_frame, text="Hörbuch", padding="10")
        detail.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        detail.columnconfigure(1, weight=1)
        self.audible_cover_image = tk.PhotoImage(width=180, height=180)
        self.audible_cover_label = tk.Label(detail, image=self.audible_cover_image, background="#e8e8e8")
        self.audible_cover_label.grid(row=0, column=0, rowspan=2, sticky=tk.N, padx=(0, 12))
        info = ttk.Frame(detail)
        info.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N))
        info.columnconfigure(1, weight=1)
        self.audible_detail_vars = {}
        for row, (key, label) in enumerate((
            ("title", "Titel"),
            ("author", "Autor"),
            ("narrators", "Gelesen von"),
            ("duration", "Dauer"),
            ("release_date", "Erscheinungsdatum"),
            ("purchase_date", "Kaufdatum"),
            ("genre", "Genre"),
        )):
            ttk.Label(info, text=label).grid(row=row, column=0, sticky=tk.W, padx=(0, 8))
            var = tk.StringVar(value="–")
            self.audible_detail_vars[key] = var
            ttk.Label(info, textvariable=var, wraplength=520).grid(row=row, column=1, sticky=tk.W)
        actions = ttk.Frame(detail)
        actions.grid(row=0, column=2, sticky=tk.NE, padx=(12, 0))
        self._register_plugin_area("audible_aktionen", actions)
        ttk.Button(actions, text="▶ Abspielen", command=self.play_selected_audible_book).pack(fill=tk.X, pady=(0, 6))
        ttk.Button(actions, text="Herunterladen", command=self.download_selected_audible_books).pack(fill=tk.X)
        summary_bg = ttk.Style().lookup("TFrame", "background") or self.root.cget("background")
        summary_fg = ttk.Style().lookup("TLabel", "foreground") or "#1d1d1f"
        self.audible_summary = tk.Text(
            detail, height=4, wrap=tk.WORD, state=tk.DISABLED,
            background=summary_bg, foreground=summary_fg,
            relief=tk.FLAT, borderwidth=0, highlightthickness=0,
        )
        self.audible_summary.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=(8, 0))

        library_frame = ttk.Frame(main_frame)
        library_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        library_frame.columnconfigure(0, weight=1)
        library_frame.rowconfigure(0, weight=1)

        columns = ('Titel', 'Autor', 'Gelesen von', 'Dauer', 'Kaufdatum')
        self.audible_tree = ttk.Treeview(library_frame, columns=columns, show='headings', height=12)
        widths = {'Titel': 280, 'Autor': 160, 'Gelesen von': 200, 'Dauer': 80, 'Kaufdatum': 110}
        for col in columns:
            self.audible_tree.heading(col, text=col)
            self.audible_tree.column(col, width=widths[col], stretch=col == 'Titel')
        scrollbar = ttk.Scrollbar(library_frame, orient=tk.VERTICAL, command=self.audible_tree.yview)
        self.audible_tree.configure(yscrollcommand=scrollbar.set)
        self.audible_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.audible_tree.bind("<<TreeviewSelect>>", self._audible_on_select)
        self.audible_tree.bind("<Double-1>", lambda _event: self.play_selected_audible_book())

        if self.audible_auth and self.audible_auth.is_logged_in():
            email = self.audible_auth.email or "Gespeicherte Anmeldung"
            self.audible_status_var.set(f"✓ Angemeldet ({email})")
            self.audible_load_button.config(state=tk.NORMAL)
    
    def create_video_tab(self):
        """Erstellt den Video-Downloader-Tab (Layout: links Optionen, rechts Log; roter Bereich bis Trennstrich)."""
        main_frame = self.video_frame
        
        container = ttk.Frame(main_frame, style="Download.TFrame")
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self._video_container = container
        container.columnconfigure(0, weight=0, minsize=280)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)
        container.bind("<Configure>", lambda e: self._schedule_resize_download_panels())
        
        # ===== LINKE SEITE: OPTIONEN (responsive, Grid sticky=nsew) =====
        options_wrapper = ttk.Frame(container, width=500, style="Download.TFrame")
        options_wrapper.pack_propagate(False)
        self._video_options_wrapper = options_wrapper
        options_wrapper.grid(row=0, column=0, sticky="nsew")
        
        options_container = ttk.Frame(options_wrapper, style="Download.TFrame")
        options_container.pack(fill=tk.BOTH, expand=True)
        
        # Info-Zeile mit Button für Sender-Liste
        info_row = ttk.Frame(options_container, style="Download.TFrame")
        info_row.pack(pady=(0, 2), padx=5, fill=tk.X)
        ttk.Label(info_row, text="Unterstützte Sender:", style="Download.TLabel").pack(side=tk.LEFT)
        ttk.Button(info_row, text="Unterstützte Sender anzeigen", command=self._show_video_supported_senders_dialog, style="Download.TButton").pack(side=tk.LEFT, padx=(8, 0))
        
        # Scrollbar für Optionen
        _bp = getattr(self, '_tk_bg_panel', '#383838')
        options_canvas = tk.Canvas(options_container, highlightthickness=0, bg=_bp)
        options_scrollbar = ttk.Scrollbar(options_container, orient="vertical", command=options_canvas.yview)
        scrollable_options = ttk.Frame(options_canvas, style="Download.TFrame")
        
        cw_id = options_canvas.create_window((0, 0), window=scrollable_options, anchor="nw")
        self._video_options_canvas = options_canvas
        self._video_options_canvas_cw_id = cw_id
        self._video_options_inner = scrollable_options
        options_canvas.configure(yscrollcommand=options_scrollbar.set)
        self._bind_scroll_wheel(options_canvas, scrollable_options)
        scrollable_options.bind("<Configure>", lambda e: self._sync_options_scroll(options_canvas, scrollable_options, cw_id))
        options_canvas.bind("<Configure>", lambda e: self._sync_options_scroll(options_canvas, scrollable_options, cw_id))
        
        video_actions = ttk.Frame(options_container, style="Download.TFrame")
        video_actions.pack(side=tk.BOTTOM, fill=tk.X)
        options_canvas.pack(side="left", fill="both", expand=True)
        options_scrollbar.pack(side="right", fill="y")
        
        # Verwende scrollable_options für alle Optionen
        opt = scrollable_options
        
        # Download-Pfad
        path_frame = ttk.LabelFrame(opt, text="Download-Pfad", padding="3", style="Download.TLabelframe")
        path_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.video_path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.video_path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="...", width=3, command=self.browse_video_download_path, style="Download.TButton").pack(side=tk.RIGHT)
        
        # URL-Eingabe
        url_frame = ttk.LabelFrame(opt, text="Video-URL", padding="3", style="Download.TLabelframe")
        url_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.video_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.video_url_var, font=("Arial", 13))
        url_entry.pack(fill=tk.X, padx=(0, 5), ipady=3)
        self._url_entries = getattr(self, "_url_entries", [])
        self._url_entries.append(url_entry)
        url_entry.bind('<Return>', lambda e: self.start_video_download())
        self._entry_place_caret(url_entry)
        self._entry_edit_menu(url_entry)
        url_entry.focus_set()
        
        # Batch-Download Button
        ttk.Button(url_frame, text="📁 URLs aus Datei laden", command=self.load_urls_from_file, style="Download.TButton").pack(fill=tk.X, pady=(2, 0))
        
        # Format-Auswahl
        format_frame = ttk.LabelFrame(opt, text="Format", padding="4", style="Download.TLabelframe")
        format_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Lade Format aus Einstellungen
        default_format = self.settings.get('default_video_format', 'mp4')
        self.video_format_var = tk.StringVar(value=default_format)
        formats = [("MP4", "mp4"), ("MP3", "mp3"), ("WebM", "webm"), ("MKV", "mkv"), ("AVI", "avi"), ("Keine", "none")]
        for index, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=text, variable=self.video_format_var, value=value, style="Download.TRadiobutton").grid(
                row=index // 3, column=index % 3, sticky=tk.W, padx=(0, 8), pady=1
            )
        
        # Qualität
        quality_frame = ttk.LabelFrame(opt, text="Qualität", padding="4", style="Download.TLabelframe")
        quality_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Lade Qualität aus Einstellungen
        default_quality = self.settings.get('default_video_quality', 'best')
        self.video_quality_var = tk.StringVar(value=default_quality)
        qualities = [("Beste", "best"), ("1080p", "1080p"), ("720p", "720p"), ("Niedrigste", "niedrigste")]
        for index, (text, value) in enumerate(qualities):
            ttk.Radiobutton(quality_frame, text=text, variable=self.video_quality_var, value=value, style="Download.TRadiobutton").grid(
                row=0, column=index, sticky=tk.W, padx=(0, 8), pady=1
            )
        
        # Erweiterte Optionen
        advanced_frame = ttk.LabelFrame(opt, text="Erweiterte Optionen", padding="3", style="Download.TLabelframe")
        advanced_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.video_resume_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text="Download fortsetzen (Resume)", variable=self.video_resume_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        
        self.video_description_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Beschreibungstext (Info.txt)", variable=self.video_description_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        
        self.video_thumbnail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Thumbnail/Cover (cover.jpg)", variable=self.video_thumbnail_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        
        self.video_shutdown_after_queue_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Herunterfahren nach Abschluss von Download(s)", variable=self.video_shutdown_after_queue_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        
        # Untertitel (nur anzeigen wenn in Einstellungen aktiviert)
        self.subtitle_frame = ttk.LabelFrame(opt, text="Untertitel", padding="3", style="Download.TLabelframe")
        self.subtitle_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.video_subtitle_var = tk.BooleanVar(value=self.settings.get('subtitle_enabled_by_default', False))
        subtitle_checkbox = ttk.Checkbutton(self.subtitle_frame, text="Untertitel herunterladen", variable=self.video_subtitle_var, command=lambda: self._update_subtitle_language_state())
        subtitle_checkbox.pack(anchor=tk.W, pady=2)
        
        subtitle_lang_frame = ttk.Frame(self.subtitle_frame, style="Download.TFrame")
        subtitle_lang_frame.pack(anchor=tk.W, padx=(20, 0))
        ttk.Label(subtitle_lang_frame, text="Sprache:").pack(side=tk.LEFT, padx=(0, 5))
        self.video_subtitle_lang_var = tk.StringVar(value=self.settings.get('subtitle_default_lang', 'de'))
        subtitle_lang_combo = ttk.Combobox(subtitle_lang_frame, textvariable=self.video_subtitle_lang_var, values=["de", "en", "all"], state="readonly", width=10)
        subtitle_lang_combo.pack(side=tk.LEFT)
        self.subtitle_lang_combo = subtitle_lang_combo
        
        # Geschwindigkeits-Limit Variablen (werden aus Einstellungen geladen)
        self.video_speed_limit_var = tk.BooleanVar(value=self.settings.get('speed_limit_enabled', False))
        self.video_speed_value_var = tk.StringVar(value=str(self.settings.get('speed_limit_value', '5')))
        
        # Buttons: nebeneinander und untereinander, mit Abstand und Rand (Grid pady=2, Style mit Padding/Rand)
        button_frame = ttk.Frame(video_actions, style="Download.TFrame")
        button_frame.pack(fill=tk.X, padx=5, pady=0)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.rowconfigure(0, pad=2)
        button_frame.rowconfigure(1, pad=2)
        self.video_download_button = ttk.Button(button_frame, text="▶ Download starten", command=self.start_video_download, state=tk.NORMAL, style="Download.TButton.Large")
        self.video_download_button.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 1), pady=2, ipady=0, ipadx=0)
        self.video_add_to_queue_button = ttk.Button(button_frame, text="➕ Zur Queue", command=self.add_video_to_queue, state=tk.NORMAL, style="Download.TButton.Large")
        self.video_add_to_queue_button.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(1, 0), pady=2, ipady=0, ipadx=0)
        self.video_cancel_button = ttk.Button(button_frame, text="⏹ Download abbrechen", command=self.cancel_video_download, state=tk.DISABLED, style="Download.TButton")
        self.video_cancel_button.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=2, ipady=0, ipadx=0)
        
        self.video_queue_status_label = ttk.Label(video_actions, text="📋 Queue: 0 Downloads", style="Download.TLabel")
        self.video_queue_status_label.pack(fill=tk.X, padx=5, pady=(0, 0))
        
        queue_button_frame = ttk.Frame(video_actions, style="Download.TFrame")
        queue_button_frame.pack(fill=tk.X, padx=5, pady=0)
        queue_button_frame.columnconfigure(0, weight=1)
        queue_button_frame.columnconfigure(1, weight=1)
        queue_button_frame.rowconfigure(0, pad=2)
        ttk.Button(queue_button_frame, text="📋 Queue anzeigen", command=self.show_download_queue, style="Download.TButton.Large").grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 1), pady=2, ipady=0, ipadx=0)
        ttk.Button(queue_button_frame, text="▶ Queue starten", command=self.start_queue_download, style="Download.TButton.Large").grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(1, 0), pady=2, ipady=0, ipadx=0)
        ttk.Button(video_actions, text="⏰ Geplante Downloads", command=self.show_scheduled_downloads, style="Download.TButton.Large").pack(fill=tk.X, padx=5, pady=2, ipady=0, ipadx=0)
        
        # Initialisiere States und Sichtbarkeit
        self._update_subtitle_language_state()
        self._update_video_tab_visibility()
        
        # Initialisiere Datenstrukturen
        self.video_scheduled_downloads = []  # Liste von geplanten Downloads
        self.video_download_history = []  # Liste von Download-Historien
        self.video_favorites = []  # Liste von Favoriten
        self.video_statistics = {
            'total_downloads': 0,
            'total_size': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'last_download': None
        }
        self.music_statistics = {
            'total_downloads': 0,
            'total_size': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'last_download': None
        }
        
        # Lade gespeicherte Daten
        self._load_video_data()
        
        # Starte Scheduler-Thread für geplante Downloads
        self.scheduler_running = True
        scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        scheduler_thread.start()
        
        # ===== RECHTE SEITE: LOG (grenzt direkt an roten Bereich / Trennstrich) =====
        log_container = ttk.Frame(container, style="Download.TFrame")
        log_container.grid(row=0, column=1, sticky="nsew")
        
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        
        # Log-Ausgabe (gleiches dunkles Design wie Musik-Log)
        ttk.Label(log_container, text="Download-Log:", font=("Arial", 10, "bold"), style="Download.TLabel").pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        _log_bg = getattr(self, '_tk_log_bg', getattr(self, '_tk_bg_panel', '#383838'))
        _log_fg = getattr(self, '_tk_fg_text', '#e8e8e8')
        self.video_log_text = scrolledtext.ScrolledText(
            log_container, wrap=tk.WORD, state=tk.DISABLED, height=25,
            bg=_log_bg, fg=_log_fg, insertbackground=_log_fg,
            highlightthickness=0, relief=tk.FLAT
        )
        self.video_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._style_log_scrolledtext(self.video_log_text)
        
        # Progress Bar und Status
        status_frame = ttk.Frame(log_container, style="Download.TFrame")
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_progress_var = tk.DoubleVar()
        self.video_progress_bar = ttk.Progressbar(status_frame, variable=self.video_progress_var, maximum=100, mode='determinate', style="Horizontal.TProgressbar")
        self.video_progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.video_status_var = tk.StringVar(value="Bereit")
        video_status_label = ttk.Label(status_frame, textvariable=self.video_status_var, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 12), style="Download.TLabel")
        video_status_label.pack(fill=tk.X)
        self.video_status_label = video_status_label
        self.video_jobs_var = tk.StringVar(value="")
        self.video_jobs_label = ttk.Label(
            status_frame, textvariable=self.video_jobs_var, anchor=tk.W, justify=tk.LEFT,
            font=("Arial", 9), style="Download.TLabel",
        )
        self.video_jobs_label.pack(fill=tk.X, pady=(4, 0))
        self._video_active_jobs = {}
        self._video_jobs_lock = threading.Lock()
        self._video_jobs_render_scheduled = False
        self._video_jobs_last_write = 0.0
        
        # Download-Queue initialisieren (erweiterte Struktur für Download-Optionen)
        self.video_download_queue = []
        self.video_download_queue_processing = False  # Flag ob Queue gerade abgearbeitet wird
        
        # Initialisiere Download-Pfad
        self.video_path_var.set(str(self.video_download_path))
    
    def create_spotify_tab(self):
        """Erstellt den Spotify-Tab"""
        main_frame = self.spotify_frame
        
        # Konfiguriere Grid
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Info-Label
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        
        info_text = (
            "Spotify-Downloads werden über YouTube/Deezer-Fallback durchgeführt.\n"
            "Geben Sie eine Spotify-URL ein (Track, Playlist oder Album).\n"
            "💡 Tipp: Für bessere Ergebnisse können Sie Spotify API Credentials konfigurieren."
        )
        ttk.Label(
            info_frame,
            text=info_text,
            foreground="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W)
        
        # Spotify API Credentials Button
        api_button_frame = ttk.Frame(main_frame)
        api_button_frame.grid(row=0, column=0, columnspan=3, pady=(5, 0), sticky=tk.E)
        
        ttk.Button(
            api_button_frame,
            text="⚙️ Spotify API konfigurieren",
            command=self.show_spotify_api_config
        ).pack(side=tk.RIGHT)
        
        # Download-Pfad
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="Download-Pfad:").grid(row=0, column=0, padx=(0, 5), sticky=tk.W)
        
        self.spotify_path_var = tk.StringVar(value=str(self.spotify_download_path))
        path_entry = ttk.Entry(path_frame, textvariable=self.spotify_path_var, state="readonly")
        path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        ttk.Button(
            path_frame,
            text="Durchsuchen",
            command=self.browse_spotify_download_path
        ).grid(row=0, column=2)
        
        # URL-Eingabe
        url_frame = ttk.Frame(main_frame)
        url_frame.grid(row=2, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        url_frame.columnconfigure(0, weight=1)
        
        ttk.Label(url_frame, text="Spotify-URL:").pack(anchor=tk.W)
        
        self.spotify_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.spotify_url_var)
        url_entry.pack(fill=tk.X, pady=(5, 0))
        url_entry.bind('<Return>', lambda e: self.start_spotify_download())
        # Unterstützung für Paste (Strg+V / Cmd+V) - verhindere doppelte Auslösung
        def handle_paste(event):
            # Erlaube Standard-Paste-Verhalten
            return None  # None erlaubt Standard-Verhalten
        url_entry.bind('<Control-v>', handle_paste)
        url_entry.bind('<Command-v>', handle_paste)
        # Stelle sicher, dass das Feld fokussierbar ist
        url_entry.focus_set()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=(0, 10))
        
        ttk.Button(
            button_frame,
            text="⬇️ Download starten",
            command=self.start_spotify_download
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="➕ Zur Queue",
            command=self.add_spotify_to_queue
        ).pack(side=tk.LEFT, padx=5)
        
        # Log-Bereich
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.spotify_log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.spotify_log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status-Bar
        self.spotify_status_var = tk.StringVar(value="Bereit")
        status_label = ttk.Label(
            main_frame,
            textvariable=self.spotify_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_label.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
    
    def browse_spotify_download_path(self):
        """Öffnet einen Dialog zur Auswahl des Spotify-Download-Pfads"""
        path = filedialog.askdirectory(initialdir=str(self.spotify_download_path))
        if path:
            self.spotify_download_path = Path(path)
            self.spotify_path_var.set(str(self.spotify_download_path))
            self.settings['default_spotify_path'] = str(self.spotify_download_path)
            self._save_settings()
    
    def spotify_log(self, message: str):
        """Fügt eine Nachricht zum Spotify-Log hinzu"""
        self.spotify_log_text.config(state=tk.NORMAL)
        self.spotify_log_text.insert(tk.END, message + "\n")
        self.spotify_log_text.see(tk.END)
        self.spotify_log_text.config(state=tk.DISABLED)
    
    def start_spotify_download(self):
        """Startet den Spotify-Download"""
        url = self.spotify_url_var.get().strip()
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine Spotify-URL ein.")
            return
        
        # Prüfe ob es eine Spotify-URL ist
        if 'spotify.com' not in url.lower():
            messagebox.showwarning("Ungültige URL", "Bitte geben Sie eine gültige Spotify-URL ein.")
            return
        
        # Starte Download in separatem Thread
        threading.Thread(
            target=self.spotify_download_thread,
            args=(url,),
            daemon=True
        ).start()
    
    def spotify_download_thread(self, url: str):
        """Download-Thread für Spotify"""
        try:
            # Verwende gemeinsamen Musik-Pfad
            download_path = self.music_download_path
            if hasattr(self, 'spotify_download_path'):
                download_path = self.spotify_download_path  # Legacy
            
            if not self.spotify_downloader:
                self.spotify_downloader = SpotifyDownloader(
                    download_path=str(download_path)
                )
            
            # Verwende entsprechenden Status-Var (falls vorhanden)
            status_var = self.spotify_status_var if hasattr(self, 'spotify_status_var') else self.music_status_var
            log_func = self.spotify_log if hasattr(self, 'spotify_log') else self.music_log
            
            self.root.after(0, lambda: status_var.set("Download läuft..."))
            log_func(f"Starte Download: {url}")
            
            # Redirect log output
            original_log = self.spotify_downloader.log
            def logged_log(message, level="INFO"):
                original_log(message, level)
                self.root.after(0, lambda: log_func(f"[{level}] {message}"))
            self.spotify_downloader.log = logged_log
            
            # Starte Download
            count = self.spotify_downloader.download_from_url(url, download_path)
            
            if count > 0:
                self.root.after(0, lambda: self.spotify_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                self.root.after(0, lambda: self.spotify_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
            else:
                self.root.after(0, lambda: self.spotify_status_var.set("✗ Download fehlgeschlagen"))
                self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
        
        except Exception as e:
            error_msg = f"Fehler beim Download: {e}"
            self.root.after(0, lambda: self.spotify_log(f"✗ {error_msg}"))
            self.root.after(0, lambda: self.spotify_status_var.set("✗ Fehler"))
            self.root.after(0, lambda: messagebox.showerror("Fehler", error_msg))
    
    def add_spotify_to_queue(self):
        """Fügt Spotify-URL zur Download-Queue hinzu"""
        url = self.spotify_url_var.get().strip()
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine Spotify-URL ein.")
            return
        
        if 'spotify.com' not in url.lower():
            messagebox.showwarning("Ungültige URL", "Bitte geben Sie eine gültige Spotify-URL ein.")
            return
        
        # Füge zur Video-Queue hinzu (kann später eigene Queue bekommen)
        if not hasattr(self, 'video_download_queue'):
            self.video_download_queue = []
        
        self.video_download_queue.append({
            'url': url,
            'type': 'spotify',
            'added': datetime.now()
        })
        
        messagebox.showinfo("Zur Queue hinzugefügt", f"Spotify-URL wurde zur Download-Queue hinzugefügt.\n\nURL: {url}")
        self.spotify_log(f"Zur Queue hinzugefügt: {url}")
    
    def show_spotify_api_config(self):
        """Zeigt Dialog zur Konfiguration der Spotify API Credentials"""
        config_window = tk.Toplevel(self.root)
        config_window.title("Spotify API Konfiguration")
        config_window.resizable(True, True)
        config_window.transient(self.root)
        config_window.grab_set()
        self._fit_dialog(config_window, 740, 640, 560, 420)
        
        main_frame = ttk.Frame(config_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        main_frame.columnconfigure(0, weight=1)
        
        # Info-Text
        info_frame = ttk.LabelFrame(main_frame, text="Anleitung", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        info_text = (
            "Für bessere Ergebnisse können Sie Spotify API Credentials konfigurieren.\n\n"
            "1. Gehen Sie zu https://developer.spotify.com/dashboard\n"
            "2. Erstellen Sie eine neue App\n"
            "3. Für 'Redirect URIs' verwenden Sie eine HTTPS-URL, z.B.:\n"
            "   https://example.com/callback\n"
            "   (Wird nicht verwendet, da wir Client Credentials Flow nutzen)\n"
            "4. Kopieren Sie die Client ID und Client Secret\n\n"
            "Hinweis: Für Client Credentials Flow wird keine echte Redirect URI benötigt.\n"
            "Falls Spotify eine verlangt, verwenden Sie einfach eine beliebige HTTPS-URL."
        )
        ttk.Label(
            info_frame,
            text=info_text,
            justify=tk.LEFT,
            wraplength=680,
            font=("Arial", 9)
        ).pack(anchor=tk.W)
        
        # Credentials Frame
        credentials_frame = ttk.LabelFrame(main_frame, text="API Credentials", padding="20")
        credentials_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        credentials_frame.columnconfigure(0, weight=1)
        
        # Client ID
        client_id_label = ttk.Label(credentials_frame, text="Client ID:", font=("Arial", 11, "bold"))
        client_id_label.pack(anchor=tk.W, pady=(0, 8))
        
        client_id_var = tk.StringVar()
        client_id_entry = ttk.Entry(
            credentials_frame, 
            textvariable=client_id_var, 
            width=80, 
            state="normal", 
            font=("Arial", 12)
        )
        client_id_entry.pack(fill=tk.X, pady=(0, 25), ipady=8)
        
        # Client Secret
        client_secret_label = ttk.Label(credentials_frame, text="Client Secret:", font=("Arial", 11, "bold"))
        client_secret_label.pack(anchor=tk.W, pady=(0, 8))
        
        client_secret_var = tk.StringVar()
        client_secret_entry = ttk.Entry(
            credentials_frame, 
            textvariable=client_secret_var, 
            width=80, 
            show="*", 
            state="normal", 
            font=("Arial", 12)
        )
        client_secret_entry.pack(fill=tk.X, pady=(0, 15), ipady=8)
        
        # Lade vorhandene Credentials
        if self.spotify_downloader and self.spotify_downloader.spotify_client_id:
            client_id_var.set(self.spotify_downloader.spotify_client_id)
            client_secret_var.set(self.spotify_downloader.spotify_client_secret or "")
        
        # Stelle sicher, dass die Felder editierbar sind
        client_id_entry.config(state="normal")
        client_secret_entry.config(state="normal")
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def save_credentials():
            client_id = client_id_var.get().strip()
            client_secret = client_secret_var.get().strip()
            
            if not client_id:
                messagebox.showwarning("Fehlende Daten", "Bitte geben Sie eine Client ID ein.")
                return
            
            if not client_secret:
                messagebox.showwarning("Fehlende Daten", "Bitte geben Sie ein Client Secret ein.")
                return
            
            # Speichere Credentials
            if not self.spotify_downloader:
                self.spotify_downloader = SpotifyDownloader(download_path=str(self.spotify_download_path))
            
            self.spotify_downloader.set_spotify_credentials(client_id, client_secret)
            
            messagebox.showinfo("Erfolg", "Spotify API Credentials gespeichert!")
            config_window.destroy()
        
        def clear_credentials():
            if messagebox.askyesno("Bestätigen", "Möchten Sie die gespeicherten Credentials wirklich löschen?"):
                if self.spotify_downloader:
                    self.spotify_downloader.set_spotify_credentials("", "")
                client_id_var.set("")
                client_secret_var.set("")
                messagebox.showinfo("Erfolg", "Credentials gelöscht!")
        
        ttk.Button(
            button_frame,
            text="💾 Speichern",
            command=save_credentials
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="🗑️ Löschen",
            command=clear_credentials
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="❌ Abbrechen",
            command=config_window.destroy
        ).pack(side=tk.RIGHT)
    
    def _show_supported_sources_dialog(self, title: str, sources_list: list):
        """Zeigt einen Dialog mit unterstützten Sendern/Seiten; jede Zeile 'Name : URL' ist anklickbar (öffnet URL im Browser)."""
        win = tk.Toplevel(self.root)
        win.title(title)
        win.transient(self.root)
        self._fit_dialog(win, 680, 540, 480, 320)
        f = ttk.Frame(win, padding=10)
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(f, text="Klicken Sie auf eine URL, um die Seite im Browser zu öffnen.", font=("Arial", 9)).pack(anchor=tk.W)
        text_frame = ttk.Frame(f)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 10))
        text = tk.Text(text_frame, wrap=tk.WORD, font=("TkDefaultFont", 10), cursor="hand2", height=18, width=62)
        scroll = ttk.Scrollbar(text_frame)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scroll.set)
        scroll.config(command=text.yview)
        for i, (name, url) in enumerate(sources_list):
            tag = f"link_{i}"
            text.insert(tk.END, f"{name} : ", "default")
            text.insert(tk.END, f"{url}\n", tag)
            text.tag_config(tag, foreground="#0066cc", underline=True)
            text.tag_bind(tag, "<Button-1>", lambda e, u=url: webbrowser.open(u))
        text.bind("<Key>", lambda e: "break")  # Nur lesen, Klicks auf URLs funktionieren
        ttk.Button(win, text="Schließen", command=win.destroy).pack(pady=(0, 10))

    def _show_video_supported_senders_dialog(self):
        """Baut die Liste der Video-Sender aus SUPPORTED_SENDERS und zeigt den Dialog."""
        sources = []
        for key, domains in (SUPPORTED_SENDERS or {}).items():
            name = VIDEO_SENDER_DISPLAY_NAMES.get(key, key.replace("_", " ").title())
            url = "https://www." + domains[0] if domains else "#"
            sources.append((name, url))
        self._show_supported_sources_dialog("Unterstützte Sender (Video)", sources)

    def _hoerspielprojekt_sanitize_folder(self, name: str) -> str:
        """Bereinigt einen Ordner-/Dateinamen für Hoerspielprojekt."""
        if not name or not name.strip():
            return "Unbekannt"
        name = re.sub(r'[<>:"/\\|?*]', '_', name.strip())
        name = name.strip('. ')
        return name[:200] if len(name) > 200 else name

    def _get_hoerspielprojekt_title_from_page(self, html: str) -> str:
        """Extrahiert den Titel aus der Hörspielprojekt-Seite (<h1> oder <title>)."""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html, re.IGNORECASE | re.DOTALL)
        if m:
            return self._hoerspielprojekt_sanitize_folder(re.sub(r'\s+', ' ', m.group(1).strip()))
        m = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if m:
            # Titel oft "Titel – Hoerspielprojekt.de", nur ersten Teil nutzen
            t = m.group(1).strip()
            if '–' in t:
                t = t.split('–', 1)[0].strip()
            elif '-' in t and 'Hoerspielprojekt' in t:
                t = t.split('-', 1)[0].strip()
            return self._hoerspielprojekt_sanitize_folder(t)
        return "Unbekannt"

    def _parse_hoerspielprojekt_series_page(self, page_url: str):
        """
        Parst eine Serien-/Artists-Seite (z. B. /artists/blut/) und liefert
        series_name sowie Liste von {url, title} für jede Folge.
        """
        import requests
        from urllib.parse import urljoin, urlparse
        import html as html_module
        resp = requests.get(page_url, timeout=20)
        resp.raise_for_status()
        html = resp.text
        series_name = self._get_hoerspielprojekt_title_from_page(html)
        # Serien-Slug aus URL (z. B. /artists/blut/ -> blut) für Filterung
        series_slug = ""
        url_path = page_url.rstrip("/").replace("https://", "").replace("http://", "")
        if "/artists/" in url_path:
            part = url_path.split("/artists/")[-1].split("/")[0]
            if part:
                series_slug = part.lower()
                if series_name == "Unbekannt" or not series_name:
                    series_name = self._hoerspielprojekt_sanitize_folder(part.replace("-", " ").title())
        elif "/serien/" in url_path:
            part = url_path.split("/serien/")[-1].split("/")[0]
            if part:
                series_slug = part.lower()
                if series_name == "Unbekannt" or not series_name:
                    series_name = self._hoerspielprojekt_sanitize_folder(part.replace("-", " ").title())
        episodes = []
        seen_norm_paths = set()
        # Links zu /music/... finden – nur solche, deren Pfad zum Serien-Slug gehört (keine Vorschläge/andere Serien)
        for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', html, re.IGNORECASE):
            href, link_text = m.group(1).strip(), m.group(2).strip()
            if "/music/" not in href:
                continue
            full_url = href if href.startswith("http") else urljoin(page_url, href)
            if "hoerspielprojekt.de" not in full_url:
                continue
            parsed_ep = urlparse(full_url)
            norm_path = parsed_ep.path.rstrip("/").lower()
            # Nur Folgen dieser Serie: Pfad muss den Serien-Slug enthalten (z. B. blut in /music/blut-folge-4/)
            if series_slug and series_slug not in norm_path:
                continue
            if norm_path in seen_norm_paths:
                continue
            seen_norm_paths.add(norm_path)
            title = self._hoerspielprojekt_sanitize_folder(html_module.unescape(link_text)) or "Folge"
            episodes.append({"url": full_url, "title": title})
        return {"series_name": series_name, "episodes": episodes}

    def _hoerspielprojekt_series_dialog_and_download(self, series_name: str, episodes: list):
        """Zeigt Folgen-Auswahl für Hörspielprojekt-Serie und startet Download der gewählten Folgen (Hauptthread)."""
        self._audiothek_series_dialog_pending = False
        self.root.after(0, lambda: self.music_progress_bar.stop())
        # Format für show_series_selection_dialog: eine "Staffel" mit allen Folgen
        series_data = {
            "series_name": f"Hörspielprojekt: {series_name}",
            "seasons": {1: [{"url": e["url"], "title": e["title"], "episode_number": i + 1} for i, e in enumerate(episodes)]},
            "total_episodes": len(episodes),
        }
        selected = self.show_series_selection_dialog(series_data, is_youtube_playlist=False)
        if not selected:
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
            self.music_log("Hörspielprojekt-Serie: Keine Folgen ausgewählt.")
            return
        self.music_log(f"Hörspielprojekt: {len(selected)} Folge(n) ausgewählt.")
        self.music_progress_bar.config(mode="determinate", maximum=100)
        self.music_audiothek_episodes_total = len(selected)
        threading.Thread(target=self._hoerspielprojekt_episodes_download_thread, args=(series_name, selected), daemon=True).start()

    def _hoerspielprojekt_episodes_download_thread(self, series_name: str, selected_episodes: list):
        """Lädt ausgewählte Hörspielprojekt-Folgen (ZIP entpacken nach Hoerspielprojekt/Serienname/Folge)."""
        total = len(selected_episodes)
        try:
            for i, ep in enumerate(selected_episodes, 1):
                if getattr(self, "music_download_cancelled", False):
                    break
                ep_url = ep.get("url")
                title = ep.get("title", f"Folge {i}")
                if not ep_url:
                    continue
                self.root.after(0, lambda t=title, cur=i, tot=total: self.music_status_var.set(f"Download läuft ({cur}/{tot}): {t[:45]}..."))
                output_subdir = f"{series_name}/{title}"
                ok, err = self._download_hoerspielprojekt(ep_url, output_subdir=output_subdir)
                if ok:
                    self.music_log(f"✓ {i}/{total}: {title}")
                else:
                    self.music_log(f"✗ {i}/{total}: {err}")
                if getattr(self, "music_download_cancel_current_only", False):
                    break
            self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {total} Folge(n)"))
            self.root.after(0, lambda: self.music_log(f"\n✓ Hörspielprojekt: {total} Folge(n) verarbeitet."))
            self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{total} Folge(n) verarbeitet. Details im Log."))
        except Exception as e:
            self.music_log(f"Fehler: {e}")
            self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))
        finally:
            self.music_audiothek_episodes_total = 0
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
            if hasattr(self, "music_cancel_button"):
                self.root.after(0, lambda: self.music_cancel_button.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.music_progress_bar.stop())

    def _download_hoerspielprojekt(self, page_url: str, output_subdir: Optional[str] = None):
        """
        Lädt eine Hörspielprojekt-Seite herunter: ZIP-Link suchen, ZIP in Ordner
        Hoerspielprojekt/<output_subdir oder Seitentitel> entpacken, ZIP löschen.
        output_subdir z. B. "Blut/Blut (1) – Blut-Virus" bei Serien.
        """
        try:
            import requests
            import zipfile
            from urllib.parse import urljoin, urlparse
            import html as html_module

            self.music_log(f"Hoerspielprojekt: Lade Seite: {page_url}")
            self.root.after(0, lambda: self.music_status_var.set("Lade Hörspielseite (Hörspielprojekt)..."))

            resp = requests.get(page_url, timeout=20)
            resp.raise_for_status()
            html = resp.text

            # Suche nach dem ZIP/Download-Link (zwei Systeme auf hoerspielprojekt.de)
            download_url = None
            # 1) Simple Download Monitor: ?smd_process_download=1&download_id=...
            m = re.search(r'href=[\"\']([^\"\']*smd_process_download=1[^\"\']*)[\"\']', html, re.IGNORECASE)
            if m:
                download_url = html_module.unescape(m.group(1))
            if not download_url:
                mid = re.search(r'download_id[\s=]+(\d+)', html, re.IGNORECASE)
                if mid:
                    parsed = urlparse(page_url)
                    base_site = f"{parsed.scheme}://{parsed.netloc}"
                    download_url = f"{base_site}/?smd_process_download=1&download_id={mid.group(1)}"
            # 2) Download-Monitor-Plugin: .../download-monitor/download.php?id=...
            if not download_url:
                m_dm = re.search(r'href=[\"\']([^\"\']*download-monitor/download\.php\?id=\d+[^\"\']*)[\"\']', html, re.IGNORECASE)
                if m_dm:
                    download_url = html_module.unescape(m_dm.group(1))
            if not download_url:
                dm_id = re.search(r'download-monitor/download\.php\?id=(\d+)', html, re.IGNORECASE)
                if dm_id:
                    parsed = urlparse(page_url)
                    base_site = f"{parsed.scheme}://{parsed.netloc}"
                    download_url = f"{base_site}/wp-content/plugins/download-monitor/download.php?id={dm_id.group(1)}"
            if not download_url:
                raise RuntimeError("Kein Download-Link (smd_process_download oder download-monitor) auf der Seite gefunden.")

            if download_url.startswith("/"):
                download_url = urljoin(page_url, download_url)
            elif not download_url.startswith("http"):
                download_url = urljoin(page_url, "/" + download_url.lstrip("/"))

            # Ausgabeordner erst anlegen, wenn Link gefunden (vermeidet leere Ordner bei Fehlern)
            base = Path(self.music_download_path) / "Hoerspielprojekt"
            if output_subdir:
                output_dir = base / output_subdir
            else:
                title = self._get_hoerspielprojekt_title_from_page(html)
                output_dir = base / title
            output_dir.mkdir(parents=True, exist_ok=True)

            self.music_log(f"Hoerspielprojekt: Download-URL gefunden: {download_url}")
            self.root.after(0, lambda: self.music_status_var.set("Lade ZIP (Hörspielprojekt)..."))

            with requests.get(download_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                total = int(r.headers.get("content-length", 0))
                filename = None
                cd = r.headers.get("content-disposition", "")
                m_name = re.search(r'filename=\"?([^\";]+)\"?', cd)
                if m_name:
                    filename = m_name.group(1).strip()
                if not filename:
                    parsed = urlparse(download_url)
                    filename = (parsed.path.rsplit("/", 1)[-1] or "hoerspielprojekt.zip")
                if not filename.lower().endswith(".zip"):
                    filename += ".zip"
                zip_path = output_dir / filename
                downloaded = 0
                chunk_size = 8192
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = min(100.0, downloaded * 100.0 / total)
                            self.root.after(0, lambda p=percent: self.music_progress_var.set(p))

            self.music_log(f"Hoerspielprojekt: ZIP gespeichert in {output_dir}")
            self.root.after(0, lambda: self.music_status_var.set("Entpacke ZIP (Hörspielprojekt)..."))
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(output_dir)
            try:
                zip_path.unlink()
            except OSError:
                pass
            self.music_log(f"✓ Hoerspielprojekt: ZIP entpackt nach {output_dir}")
            self.root.after(0, lambda: self.music_progress_var.set(100.0))
            return True, None
        except Exception as e:
            return False, str(e)

    def browse_music_download_path(self):
        """Öffnet einen Dialog zur Auswahl des Musik-Download-Pfads"""
        path = filedialog.askdirectory(initialdir=str(self.music_download_path))
        if path:
            self.music_download_path = Path(path)
            self.music_path_var.set(str(self.music_download_path))
            self.settings['default_music_path'] = str(self.music_download_path)
            self._save_settings()
    
    def update_music_download_path(self):
        """Aktualisiert den Musik-Download-Pfad in der UI"""
        if hasattr(self, 'music_path_var'):
            self.music_path_var.set(str(self.music_download_path))
        if self.downloader:
            self.downloader.download_path = self.music_download_path
        if self.spotify_downloader:
            self.spotify_downloader.download_path = str(self.music_download_path)
    
    def _get_deezer_arl_from_accounts(self) -> Optional[str]:
        """Liest ARL-Cookie aus einem Deezer-Account in der Account-Verwaltung (Netscape-Format)."""
        for acc in self.settings.get('video_accounts', []):
            if acc.get('service') != 'Deezer':
                continue
            raw = (acc.get('cookies') or '').strip()
            if not raw:
                continue
            for line in raw.split('\n'):
                line = line.strip()
                if line.startswith('#') or not line:
                    continue
                parts = line.split('\t')
                if len(parts) >= 7 and 'deezer' in (parts[0] or '').lower() and (parts[5] or '').strip() == 'arl':
                    return (parts[6] or '').strip()
        return None
    
    def music_log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Musik-Log hinzu"""
        # Bestimme Level basierend auf Nachricht
        if "[DEBUG]" in message:
            level = "DEBUG"
        elif "[WARNING]" in message or "⚠" in message:
            level = "WARNING"
        elif "[ERROR]" in message or "✗" in message:
            level = "ERROR"
        
        # Prüfe Log-Level-Einstellung
        log_level_setting = self.settings.get('log_level', 'debug')
        
        # In normalem Modus: Überspringe DEBUG-Logs in GUI
        show_in_gui = True
        if log_level_setting == 'normal' and level == 'DEBUG':
            show_in_gui = False
        
        if show_in_gui and hasattr(self, 'music_log_text'):
            self.music_log_text.config(state=tk.NORMAL)
            level_prefix = f"[{level}] " if level != "INFO" else ""
            self.music_log_text.insert(tk.END, f"{level_prefix}{message}\n")
            self.music_log_text.see(tk.END)
            self.music_log_text.config(state=tk.DISABLED)
        # Auch in Log-Datei schreiben (immer, aber mit Level-Filterung)
        self._write_to_log_file(f"[MUSIK] {message}", level)
    
    def _show_system_notification(self, title: str, message: str, *, require_global_notifications: bool = True):
        """Zeigt eine System-Benachrichtigung, unter Windows ohne Extra-Fenster."""
        if require_global_notifications and not self.settings.get('show_notifications', True):
            return
        try:
            if sys.platform == 'darwin':
                subprocess.run(
                    ['osascript', '-e', f'display notification "{message.replace(chr(34), chr(39))}" with title "{title.replace(chr(34), chr(39))}"'],
                    check=False, timeout=2, capture_output=True
                )
            elif sys.platform.startswith('linux'):
                subprocess.run(
                    ['notify-send', title, message],
                    check=False, timeout=2, capture_output=True
                )
            else:
                # Windows: Systemmeldung über den Serien-Wächter, kein Extra-Fenster.
                try:
                    import series_watch as _sw
                    import series_watch_tray as _swt
                    if _swt.tray_instance_running(self.base_download_path):
                        _sw.queue_user_notice(self.base_download_path, title, message)
                    else:
                        _sw.desktop_notify(title, message)
                except Exception:
                    pass
        except Exception:
            pass

    def _start_series_watch_tray(self):
        """Serien-Wächter-Icon in eigenem Prozess (im GUI-Prozess stürzt macOS/Windows ab)."""
        if os.environ.get("SERIES_WATCH_NO_TRAY"):
            return
        if not self.settings.get("series_watch_tray_enabled", True):
            try:
                import series_watch_tray as swt
                swt.remove_login_autostart()
                swt.steal_tray_instance(self.base_download_path)
            except Exception:
                pass
            return
        if getattr(self, "_series_watch_tray_app", None) is not None:
            return
        try:
            import series_watch_tray as swt
        except ImportError:
            try:
                self._write_to_log_file("[Serien-Wächter] Tray-Modul fehlt.", "INFO")
            except Exception:
                pass
            return
        if sys.platform != "win32" and not sys.platform.startswith("linux"):
            try:
                import pystray  # noqa: F401
            except ImportError:
                try:
                    self._write_to_log_file("[Serien-Wächter] Tray nicht gestartet (pystray fehlt).", "INFO")
                except Exception:
                    pass
                return
        try:
            if swt.tray_instance_running(self.base_download_path):
                self._series_watch_tray_app = True
                self._write_to_log_file("[Serien-Wächter] Tray-Prozess läuft bereits — Icon bleibt.", "INFO")
            else:
                swt.steal_tray_instance(self.base_download_path)
                argv = swt.get_tray_launch_argv()
                popen_kw = {
                    "close_fds": True,
                }
                try:
                    popen_kw["cwd"] = str(Path(argv[0]).resolve().parent)
                except Exception:
                    pass
                if sys.platform == "win32":
                    flags = 0
                    if hasattr(subprocess, "DETACHED_PROCESS"):
                        flags |= subprocess.DETACHED_PROCESS
                    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
                    if hasattr(subprocess, "CREATE_NO_WINDOW"):
                        flags |= subprocess.CREATE_NO_WINDOW
                    popen_kw["creationflags"] = flags
                else:
                    popen_kw["start_new_session"] = True
                    popen_kw["env"] = os.environ.copy()
                self._series_watch_tray_proc = subprocess.Popen(argv, **popen_kw)
                self._series_watch_tray_app = True
                self._write_to_log_file("[Serien-Wächter] Tray-Prozess gestartet.", "INFO")
            if self.settings.get("series_watch_tray_enabled", True) and self.settings.get("series_watch_tray_autostart", True):
                if swt.install_login_autostart():
                    self._write_to_log_file("[Serien-Wächter] Autostart nach Anmeldung eingerichtet.", "INFO")
        except Exception as e:
            try:
                self._write_to_log_file(f"[Serien-Wächter] Tray-Start fehlgeschlagen: {e}", "WARNING")
            except Exception:
                pass

    def _series_watch_ensure_tray(self):
        """Bringt das Leisten-Icon zurück, wenn der Tray-Prozess abgestürzt ist."""
        if os.environ.get("SERIES_WATCH_NO_TRAY"):
            return
        if not self.settings.get("series_watch_tray_enabled", True):
            return
        try:
            import series_watch_tray as swt
        except ImportError:
            return
        proc = getattr(self, "_series_watch_tray_proc", None)
        if proc is not None:
            try:
                proc.poll()
            except Exception:
                pass
        if swt.tray_instance_running(self.base_download_path):
            return
        now = time.time()
        if now - float(getattr(self, "_tray_restart_ts", 0) or 0) < 8:
            return
        self._tray_restart_ts = now
        self._series_watch_tray_app = None
        self._start_series_watch_tray()

    def _series_watch_pull_gui_queue(self):
        """Folgen aus der Menüleiste in die Video-Queue übernehmen und nach der Einstellung starten."""
        try:
            if series_watch is not None:
                show_flag = self.base_download_path / "series_watch_show_window"
                pick_flag = self.base_download_path / "series_watch_pick_episodes"
                if show_flag.exists() or pick_flag.exists():
                    pick_raw = ""
                    if pick_flag.exists():
                        try:
                            pick_raw = pick_flag.read_text(encoding="utf-8").strip()
                        except Exception:
                            pick_raw = "*"
                        try:
                            pick_flag.unlink()
                        except Exception:
                            pass
                    if show_flag.exists():
                        try:
                            show_flag.unlink()
                        except Exception:
                            pass
                    try:
                        self.root.deiconify()
                        self.root.lift()
                        self.root.focus_force()
                        if sys.platform.startswith("linux"):
                            self.root.attributes("-topmost", True)
                            self.root.after(400, lambda: self.root.attributes("-topmost", False))
                    except Exception:
                        pass
                    if pick_raw:
                        rows = self._series_watch_rows_for_picker(pick_raw)
                        self._series_watch_new_episodes_actions_dialog(
                            self.root, rows, "Verfügbare Folgen"
                        )
                if series_watch.is_download_cancel_requested(self.base_download_path):
                    self.video_download_cancelled = True
                    self._video_queue_hold = True
                    for proc in list(getattr(self, '_parallel_video_process_list', []) or []):
                        self._terminate_video_subprocess(proc)
                    if self.video_download_process is not None:
                        self._terminate_video_subprocess(self.video_download_process)
                    series_watch.write_runtime_status(self.base_download_path, cancel_requested=False)
                rows = series_watch.take_gui_video_queue(self.base_download_path)
                added = 0
                for row in rows:
                    url = (row.get("url") or "").strip()
                    if not url:
                        continue
                    self._add_to_download_queue(
                        url,
                        episode_info={
                            "title": row.get("title") or "",
                            "series_name": row.get("series_name") or row.get("series") or "",
                            "season_number": row.get("season_number"),
                            "episode_number": row.get("episode_number"),
                            "playlist_index": row.get("playlist_index") or row.get("episode_number"),
                            "url": url,
                            "id": row.get("id"),
                            "kind": row.get("kind") or "",
                            "output_format": (row.get("output_format") or "").lower(),
                        },
                        show_dialog=False,
                    )
                    added += 1
                if added:
                    self._video_queue_hold = False
                    self.video_download_cancelled = False
                    max_c = self._max_parallel_video_downloads()
                    self.video_log(
                        f"Serien-Wächter: {added} Folge(n) in der Queue, bis zu {max_c} gleichzeitig."
                    )
                    self._process_download_queue()
                    self._update_queue_status()
        except Exception:
            pass
        try:
            self._series_watch_ensure_tray()
        except Exception:
            pass
        try:
            self.root.after(1000, self._series_watch_pull_gui_queue)
        except Exception:
            pass

    def _series_watch_schedule_tick(self):
        """Ruft periodisch die Serien-Prüfung auf (minütlich; Abstand siehe Einstellungen)."""
        try:
            self._series_watch_maybe_run()
        except Exception:
            pass
        try:
            self._series_watch_after_id = self.root.after(60000, self._series_watch_schedule_tick)
        except Exception:
            pass

    def _series_watch_mark_downloaded(self, url: str = "", episode_id=None):
        """Nach erfolgreichem Video-Download: passendes have_ids im Serien-Wächter setzen."""
        if series_watch is None:
            return
        try:
            urls = [url] if (url or "").strip() else []
            ids = [str(episode_id)] if episode_id else []
            if not urls and not ids:
                return
            n = series_watch.mark_downloaded_episodes(
                self.base_download_path, urls=urls, episode_ids=ids
            )
            try:
                series_watch.prune_owned_alerts(self.base_download_path)
            except Exception:
                pass
            if n:
                self._write_to_log_file(
                    f"[Serien-Wächter] {n} Folge(n) als „habe ich“ markiert ({(url or '')[:80]})",
                    "INFO",
                )
        except Exception as e:
            try:
                self._write_to_log_file(f"[Serien-Wächter] Abhaken fehlgeschlagen: {e}", "WARNING")
            except Exception:
                pass

    def _series_watch_item_for_notification(self, n: Dict) -> Optional[Dict]:
        if series_watch is None or not isinstance(n, dict):
            return None
        data = series_watch.load_state(self.base_download_path)
        url = (n.get("series_url") or "").strip()
        name = (n.get("watch_name") or "").strip()
        for it in data.get("items") or []:
            if not isinstance(it, dict):
                continue
            if url and (it.get("url") or "").strip() == url:
                return it
            dn = (it.get("display_name") or "").strip()
            if name and (dn == name or (it.get("playlist_title") or "").strip() == name):
                return it
        return None

    def _series_watch_collect_auto_download_episodes(self, notifications: List[Dict]) -> List[Dict]:
        """Sammelt neue Folgen, die laut Einstellung/Serie automatisch geladen werden sollen."""
        if series_watch is None:
            return []
        out: List[Dict] = []
        seen_urls = set()
        for n in notifications or []:
            if not isinstance(n, dict):
                continue
            it = self._series_watch_item_for_notification(n)
            if it is None:
                it = {}
            if not series_watch.item_wants_auto_download(it, self.settings):
                continue
            series_name = (n.get("watch_name") or "").strip()
            series_url = (n.get("series_url") or (it.get("url") if isinstance(it, dict) else "") or "").strip()
            kind = series_watch.watch_item_kind(it if isinstance(it, dict) else None, series_url)
            for ep in series_watch.episodes_for_video_download(
                n.get("new_episodes") or [], series_name, kind=kind, series_url=series_url
            ):
                u = (ep.get("url") or "").strip()
                if not u or u in seen_urls:
                    continue
                seen_urls.add(u)
                out.append(ep)
        return out

    def _series_watch_start_auto_downloads(self, episodes: List[Dict]):
        """Startet Auto-Download: Video-Tab bzw. Musik-Tab (Hörbuch/Audiothek)."""
        if not episodes:
            return
        audio_eps = [
            e for e in episodes
            if (e.get("kind") == "audio") or (series_watch and series_watch.is_audio_watch_url(e.get("url") or e.get("series_url") or ""))
        ]
        video_eps = [e for e in episodes if e not in audio_eps]
        try:
            if series_watch is not None:
                series_watch.write_runtime_status(
                    self.base_download_path,
                    phase="downloading",
                    pending=[
                        {
                            "title": (e.get("title") or "")[:80],
                            "series": (e.get("series") or e.get("series_name") or "")[:60],
                        }
                        for e in episodes[1:]
                    ],
                    cancel_requested=False,
                )
                first = episodes[0]
                series_watch.set_download_progress(
                    self.base_download_path,
                    title=first.get("title") or "",
                    series=first.get("series") or first.get("series_name") or "",
                    percent=0.0,
                    index=1,
                    total=len(episodes),
                    pending=[
                        {
                            "title": (e.get("title") or "")[:80],
                            "series": (e.get("series") or e.get("series_name") or "")[:60],
                        }
                        for e in episodes[1:]
                    ],
                )
            if video_eps and VideoDownloader:
                self._series_watch_get_video_downloader()
                self.video_download_button.config(state=tk.DISABLED)
                if hasattr(self, "video_cancel_button"):
                    self.video_cancel_button.config(state=tk.NORMAL)
                self.video_log(f"\n[Serien-Wächter] Auto-Download Video: {len(video_eps)} Folge(n)")
                threading.Thread(target=self.video_download_episodes_thread, args=(video_eps,), daemon=True).start()
            if audio_eps:
                self._series_watch_get_video_downloader()
                if hasattr(self, "music_download_button"):
                    self.music_download_button.config(state=tk.DISABLED)
                self.music_log(f"\n[Serien-Wächter] Auto-Download Hörbuch/Audio: {len(audio_eps)} Folge(n)")
                threading.Thread(
                    target=self._audiothek_episodes_download_thread,
                    args=(audio_eps,),
                    kwargs={"silent": True},
                    daemon=True,
                ).start()
        except Exception as e:
            self._write_to_log_file(f"[Serien-Wächter] Auto-Download Start fehlgeschlagen: {e}", "ERROR")
            if series_watch is not None:
                try:
                    series_watch.clear_download_status(self.base_download_path)
                except Exception:
                    pass


    def _series_watch_notify_and_maybe_download(self, notifications: List[Dict], *, interactive: bool = False, parent=None):
        """Benachrichtigungen + optional Auto-Download. Interactive: Dialog bei manueller Prüfung."""
        if series_watch is None or not notifications:
            return
        auto_eps = self._series_watch_collect_auto_download_episodes(notifications)
        for n in notifications:
            title, body = series_watch.format_notification_text(n)
            if auto_eps:
                n_count = len(n.get("new_episodes") or [])
                title = f"Auto-Download: {n.get('watch_name') or title}"
                body = f"{n_count} neue Folge(n) – Download gestartet.\n\n" + body
            try:
                series_watch.send_external_notifications(self.settings, title, body)
            except Exception as e:
                self._write_to_log_file(f"[Serien-Wächter] Versand (E-Mail/Telegram/Discord): {e}", "WARNING")
            short = body[:500] + ("…" if len(body) > 500 else "")
            self.root.after(0, lambda t=title, m=short: self._series_watch_desktop_notify(t, m))

        if auto_eps:
            self.root.after(0, lambda eps=list(auto_eps): self._series_watch_start_auto_downloads(eps))
            return

        if interactive:
            all_new = []
            for n in notifications:
                wn = (n.get("watch_name") or "").strip()
                for ep in n.get("new_episodes") or []:
                    e = dict(ep)
                    if wn and not e.get("series"):
                        e["series"] = wn
                    if n.get("series_url") and not e.get("series_url"):
                        e["series_url"] = n.get("series_url")
                    all_new.append(e)
            parent_win = parent or self.root

            def ask():
                only_gaps = bool(notifications) and all(n.get("gap") for n in notifications)
                names = ", ".join((n.get("watch_name") or "Serie") for n in notifications[:3])
                n_eps = sum(len(n.get("new_episodes") or []) for n in notifications)
                if only_gaps:
                    self._series_watch_new_episodes_actions_dialog(
                        parent_win,
                        all_new,
                        f"Fehlende Folgen — {names}",
                    )
                    return
                if messagebox.askyesno(
                    "Neue Folgen",
                    f"{n_eps} neue Folge(n) bei {names}. Zur Queue hinzufügen oder herunterladen?",
                    parent=parent_win,
                ):
                    self._series_watch_new_episodes_actions_dialog(parent_win, all_new, "Neue Folgen — Aktion")

            self.root.after(0, ask)

    def _series_watch_maybe_run(self):
        if series_watch is None:
            return
        if not self.settings.get('series_watch_enabled', False):
            return
        st = series_watch.load_state(self.base_download_path)
        items = st.get('items') if isinstance(st, dict) else []
        if not items:
            return
        now = time.time()
        try:
            interval_h = float(self.settings.get('series_watch_interval_hours', 6) or 6)
        except (TypeError, ValueError):
            interval_h = 6.0
        if self._series_watch_last_run > 0 and (now - self._series_watch_last_run) < interval_h * 3600:
            return

        def work():
            lock = series_watch.try_acquire_check_lock(self.base_download_path, "gui")
            if lock is None:
                self._write_to_log_file("[Serien-Wächter] Prüfung übersprungen (Lock belegt, z. B. Tray aktiv).", "INFO")
                return
            try:
                try:
                    _, notifications = series_watch.check_all(
                        self.base_download_path,
                        on_item_error=lambda n, e: self._write_to_log_file(f"[Serien-Wächter] {n}: {e}", "WARNING"),
                    )
                except Exception as e:
                    self._write_to_log_file(f"[Serien-Wächter] Prüfung fehlgeschlagen: {e}", "ERROR")
                    return
                self._series_watch_last_run = time.time()
                if notifications:
                    self._series_watch_notify_and_maybe_download(notifications, interactive=False)
            finally:
                series_watch.release_check_lock(lock)

        threading.Thread(target=work, daemon=True).start()

    def _series_watch_desktop_notify(self, title: str, message: str):
        if not self.settings.get('series_notify_desktop', True):
            return
        self._show_system_notification(title[:120], message, require_global_notifications=False)

    def _series_watch_get_video_downloader(self):
        """VideoDownloader für Serien-Abruf / Downloads (gleiche Einstellungen wie Video-Tab)."""
        if not VideoDownloader:
            return None
        self.video_download_path = Path(self.video_path_var.get()) if hasattr(self, "video_path_var") else Path(
            self.settings.get("default_video_path", str(self.base_download_path / "Video"))
        )
        quality = self.video_quality_var.get() if hasattr(self, "video_quality_var") else self.settings.get("default_video_quality", "best")
        output_format = self.video_format_var.get() if hasattr(self, "video_format_var") else self.settings.get("default_video_format", "mp4")
        self.video_downloader = VideoDownloader(
            download_path=str(self.video_download_path),
            quality=quality,
            output_format=output_format,
            gui_instance=self,
        )
        return self.video_downloader

    def _series_watch_save_item_by_index(self, index: int, item: Dict) -> None:
        data = series_watch.load_state(self.base_download_path)
        items = data.get("items") or []
        if 0 <= index < len(items):
            items[index] = item
            series_watch.save_state(self.base_download_path, data)

    def _series_watch_quick_rules_dialog(self, parent, item_index: int):
        """Schnell: ganze Staffeln 1..n und/oder Staffel X Folgen 1..Y als „besitze ich“."""
        data = series_watch.load_state(self.base_download_path)
        items = data.get("items") or []
        if not (0 <= item_index < len(items)) or not isinstance(items[item_index], dict):
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=parent)
            return
        it = dict(items[item_index])
        d = tk.Toplevel(parent)
        d.title("Besitz-Regeln (Schnell)")
        d.transient(parent)
        d.grab_set()
        self._apply_dark_toplevel(d)
        self._fit_dialog(d, 580, 300, 480, 240)
        f = ttk.Frame(d, padding="12", style="Download.TFrame")
        f.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            f,
            text="Diese Regeln unterdrücken Hinweise für bereits „gehörte“ Folgen.\n"
            "Es werden die aktuell in der Mediathek gelisteten Folgen anhand S/E im Titel zugeordnet.",
            wraplength=520,
            style="Download.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))
        row1 = ttk.Frame(f, style="Download.TFrame")
        row1.pack(fill=tk.X, pady=4)
        ttk.Label(row1, text="Staffeln 1 bis … komplett:", style="Download.TLabel").pack(side=tk.LEFT)
        full_var = tk.StringVar(value=str(int(it.get("have_full_seasons_upto") or 0) or 0))
        ttk.Spinbox(row1, from_=0, to=99, textvariable=full_var, width=5, style="Download.TEntry").pack(side=tk.LEFT, padx=6)
        ttk.Label(row1, text="(0 = aus)", style="Download.TLabel").pack(side=tk.LEFT)
        row2 = ttk.Frame(f, style="Download.TFrame")
        row2.pack(fill=tk.X, pady=8)
        use_part = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Zusätzlich Teilmenge:", variable=use_part, style="Download.TCheckbutton").pack(side=tk.LEFT)
        ttk.Label(row2, text="Staffel", style="Download.TLabel").pack(side=tk.LEFT, padx=(8, 0))
        ps_var = tk.StringVar(value="22")
        ttk.Spinbox(row2, from_=1, to=99, textvariable=ps_var, width=4, style="Download.TEntry").pack(side=tk.LEFT, padx=4)
        ttk.Label(row2, text="Folgen 1 bis", style="Download.TLabel").pack(side=tk.LEFT, padx=(6, 0))
        pe_var = tk.StringVar(value="10")
        ttk.Spinbox(row2, from_=1, to=99, textvariable=pe_var, width=4, style="Download.TEntry").pack(side=tk.LEFT, padx=4)

        def apply_rules():
            try:
                fu = max(0, min(99, int(full_var.get() or 0)))
            except (TypeError, ValueError):
                fu = 0
            it["have_full_seasons_upto"] = fu
            if use_part.get():
                try:
                    ps = max(1, min(99, int(ps_var.get() or 1)))
                    pe = max(1, min(99, int(pe_var.get() or 1)))
                except (TypeError, ValueError):
                    messagebox.showwarning("Hinweis", "Ungültige Staffel/Folge.", parent=d)
                    return
                partial = [x for x in (it.get("have_partial_seasons") or []) if isinstance(x, dict) and int(x.get("season", -1)) != ps]
                partial.append({"season": ps, "episode_upto": pe})
                it["have_partial_seasons"] = partial
            try:
                _pid, _pt, cur = series_watch.fetch_playlist_episodes(it.get("url") or "")
                series_watch.merge_have_ids_from_current(it, cur)
            except Exception as ex:
                messagebox.showwarning("Serien-Wächter", f"Konnte Liste nicht laden: {ex}", parent=d)
                return
            self._series_watch_save_item_by_index(item_index, it)
            d.destroy()
            messagebox.showinfo("Serien-Wächter", "Besitz-Regeln gespeichert.", parent=parent)

        bf = ttk.Frame(f, style="Download.TFrame")
        bf.pack(fill=tk.X, pady=12)
        ttk.Button(bf, text="Übernehmen", command=apply_rules, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Abbrechen", command=d.destroy, style="Download.TButton").pack(side=tk.LEFT)

    def _series_watch_owned_episodes_dialog(self, parent, item_index: int):
        """Wie Serien-Download: Folgen anhaken, die Sie schon haben (inkl. Audiodeskription ausblenden)."""
        if not VideoDownloader:
            messagebox.showwarning("Serien-Wächter", "Video-Downloader nicht verfügbar.", parent=parent)
            return
        data = series_watch.load_state(self.base_download_path)
        items = data.get("items") or []
        if not (0 <= item_index < len(items)) or not isinstance(items[item_index], dict):
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=parent)
            return
        it = items[item_index]
        url = (it.get("url") or "").strip()
        if not url:
            return
        wait = tk.Toplevel(parent)
        wait.title("Lade Folgenliste…")
        wait.geometry("320x100")
        wait.transient(parent)
        ttk.Label(wait, text="Mediathek wird gelesen, bitte warten…", padding=20).pack()
        wait.update_idletasks()

        def work():
            try:
                vd = self._series_watch_get_video_downloader()
                series_data = vd.get_series_episodes(url)
            except Exception as e:
                self.root.after(0, wait.destroy)
                self.root.after(0, lambda: messagebox.showerror("Serien-Wächter", str(e), parent=parent))
                return
            if not series_data or not series_data.get("seasons"):
                self.root.after(0, wait.destroy)
                self.root.after(0, lambda: messagebox.showwarning("Serien-Wächter", "Keine Staffeln/Folgen gefunden.", parent=parent))
                return

            def filter_ad(sd: Dict) -> Dict:
                seasons = {}
                for sn, eps in (sd.get("seasons") or {}).items():
                    fe = [e for e in eps if "audiodeskription" not in (e.get("title") or "").lower()]
                    if fe:
                        seasons[sn] = fe
                total = sum(len(v) for v in seasons.values())
                return {"series_name": sd.get("series_name", "Serie"), "seasons": seasons, "total_episodes": total}

            filtered = filter_ad(series_data)
            self.root.after(0, wait.destroy)
            self.root.after(0, lambda: self._series_watch_owned_checkbox_ui(parent, item_index, dict(it), filtered))

        threading.Thread(target=work, daemon=True).start()

    def _series_watch_owned_checkbox_ui(self, parent, item_index: int, item_copy: Dict, series_data: Dict):
        """Checkbox-UI: angehakt = bereits vorhanden; Ignorieren = Trailer/Making-of o. Ä."""
        sel_win = tk.Toplevel(parent)
        sel_win.title("Bereits vorhandene Folgen markieren")
        sel_win.transient(parent)
        sel_win.grab_set()
        self._apply_dark_toplevel(sel_win)
        self._fit_dialog(sel_win, 960, 740, 720, 520)
        main_frame = ttk.Frame(sel_win, padding="12", style="Download.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        hid = set(str(x) for x in (item_copy.get("have_ids") or []))
        ign = set(str(x) for x in (item_copy.get("ignore_ids") or []))
        ttk.Label(
            main_frame,
            text=f"Serie: {series_data.get('series_name', '')} — Haken links = „habe ich schon“.\n"
            "Kreuz rechts = ignorieren (Trailer, Making-of, …): keine Hinweise, nicht als fehlend.\n"
            "Pro Staffel: „Gesamte Staffel markieren“ setzt alle Folgen dieser Staffel auf „habe ich“.",
            wraplength=900,
            style="Download.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))
        quick_fr = ttk.Frame(main_frame, style="Download.TFrame")
        quick_fr.pack(fill=tk.X, pady=(0, 6))
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        self._bind_scroll_wheel(canvas, scrollable)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        episode_vars = {}
        ignore_vars = {}
        season_vars = {}
        seasons = series_data.get("seasons") or {}

        def _exclusive(have_var, ign_var, which):
            if which == "have" and have_var.get():
                ign_var.set(False)
            elif which == "ign" and ign_var.get():
                have_var.set(False)

        def select_all_episodes():
            for var in episode_vars.values():
                var.set(True)
            for iv in ignore_vars.values():
                iv.set(False)
            for svar in season_vars.values():
                svar.set(True)

        def select_none_episodes():
            for var in episode_vars.values():
                var.set(False)
            for svar in season_vars.values():
                svar.set(False)

        def ignore_extras():
            for (sn, i), iv in ignore_vars.items():
                eps = seasons.get(sn) or []
                if i >= len(eps):
                    continue
                title = eps[i].get("title") or ""
                if series_watch.is_likely_extra_title(title):
                    iv.set(True)
                    k = (sn, i)
                    if k in episode_vars:
                        episode_vars[k].set(False)

        ttk.Button(quick_fr, text="Alle Folgen auswählen", command=select_all_episodes, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(quick_fr, text="Alle abwählen", command=select_none_episodes, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(quick_fr, text="Trailer/Making-of ignorieren", command=ignore_extras, style="Download.TButton").pack(side=tk.LEFT, padx=6)

        for season_num in sorted(seasons.keys()):
            eps = seasons[season_num]
            lf = ttk.LabelFrame(scrollable, text=f"Staffel {season_num} ({len(eps)} Folgen)", padding="8")
            lf.pack(fill=tk.X, padx=4, pady=6)
            all_in_season_have = bool(eps) and all(
                str(eps[j].get("id") or "") in hid for j in range(len(eps))
            )
            season_var = tk.BooleanVar(value=all_in_season_have)
            season_vars[season_num] = season_var

            def make_season_toggle(snum, svar):
                def toggle():
                    on = svar.get()
                    n_eps = seasons.get(snum) or []
                    for i in range(len(n_eps)):
                        k = (snum, i)
                        if k in episode_vars:
                            episode_vars[k].set(on)
                        if on and k in ignore_vars:
                            ignore_vars[k].set(False)
                return toggle

            ttk.Checkbutton(
                lf,
                text=f"Gesamte Staffel {season_num} markieren ({len(eps)} Folgen)",
                variable=season_var,
                command=make_season_toggle(season_num, season_var),
            ).pack(anchor=tk.W, pady=(0, 6), padx=4)
            for i, ep in enumerate(eps):
                eid = str(ep.get("id") or "")
                title = ep.get("title", "?")
                extra = series_watch.is_likely_extra_title(title)
                have_on = bool(eid and eid in hid)
                ign_on = bool(eid and eid in ign) or (extra and not have_on)
                if have_on:
                    ign_on = False
                var = tk.BooleanVar(value=have_on)
                ivar = tk.BooleanVar(value=ign_on)
                episode_vars[(season_num, i)] = var
                ignore_vars[(season_num, i)] = ivar
                if len(title) > 70:
                    title = title[:67] + "…"
                row = ttk.Frame(lf, style="Download.TFrame")
                row.pack(fill=tk.X, padx=8, pady=1)
                ttk.Checkbutton(
                    row,
                    text=title,
                    variable=var,
                    command=lambda h=var, g=ivar: _exclusive(h, g, "have"),
                ).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)
                ttk.Checkbutton(
                    row,
                    text="Ignorieren",
                    variable=ivar,
                    command=lambda h=var, g=ivar: _exclusive(h, g, "ign"),
                ).pack(side=tk.RIGHT)

        def do_save():
            shown_ids = set()
            new_hid = set()
            new_ign = set()
            for (sn, i), var in episode_vars.items():
                ep = seasons.get(sn, [])[i] if i < len(seasons.get(sn, [])) else None
                if not ep or not ep.get("id"):
                    continue
                eid = str(ep["id"])
                shown_ids.add(eid)
                if var.get():
                    new_hid.add(eid)
                elif ignore_vars.get((sn, i)) and ignore_vars[(sn, i)].get():
                    new_ign.add(eid)
            old_hid = set(str(x) for x in (item_copy.get("have_ids") or []) if x)
            old_ign = set(str(x) for x in (item_copy.get("ignore_ids") or []) if x)
            item_copy["have_ids"] = sorted((old_hid - shown_ids) | new_hid)
            item_copy["ignore_ids"] = sorted(((old_ign - shown_ids) | new_ign) - set(item_copy["have_ids"]))
            try:
                _pid, _pt, cur = series_watch.fetch_playlist_episodes(item_copy.get("url") or "")
                series_watch.merge_have_ids_from_current(item_copy, cur)
            except Exception:
                pass
            self._series_watch_save_item_by_index(item_index, item_copy)
            sel_win.destroy()
            messagebox.showinfo("Serien-Wächter", "Markierung gespeichert.", parent=parent)

        bf = ttk.Frame(main_frame, style="Download.TFrame")
        bf.pack(fill=tk.X, pady=8)
        ttk.Button(bf, text="Speichern", command=do_save, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Abbrechen", command=sel_win.destroy, style="Download.TButton").pack(side=tk.LEFT)

    def _series_watch_rows_for_picker(self, series_url: str = "") -> List[Dict]:
        """Offene Folgen einer Serie (oder aller Serien) für die Auswahlliste."""
        if series_watch is None:
            return []
        state = series_watch.load_state(self.base_download_path)
        want = (series_url or "").strip()
        if want == "*":
            want = ""
        rows: List[Dict] = []
        for group in series_watch.available_groups(state):
            surl = (group.get("series_url") or "").strip()
            if want and series_watch._normalize_url_key(surl) != series_watch._normalize_url_key(want):
                continue
            name = group.get("name") or ""
            kind = series_watch.watch_item_kind(None, surl)
            fmt = series_watch.download_format_for_series(state, surl, name)
            rows.extend(series_watch.episodes_for_video_download(
                group.get("episodes") or [],
                name,
                kind=kind,
                series_url=surl,
                output_format=fmt,
            ))
        return rows

    def _series_watch_cached_series_data(self, url: str) -> Optional[Dict]:
        """Folgen aus dem letzten Prüfstand, ohne die Mediathek noch einmal zu laden."""
        if series_watch is None:
            return None
        it = self._series_watch_watch_item_for_url(url)
        if not isinstance(it, dict):
            return None
        stored = it.get("episodes")
        if not isinstance(stored, dict) or not stored:
            return None
        name = (it.get("display_name") or it.get("playlist_title") or "").strip() or "Serie"
        kind = series_watch.watch_item_kind(it, url)
        fmt = series_watch.effective_download_format(it, url)
        raw: List[Dict] = []
        for eid, meta in stored.items():
            if not isinstance(meta, dict):
                meta = {}
            title = (meta.get("title") or "").strip()
            if not title or "audiodeskription" in title.lower():
                continue
            raw.append({
                "id": str(eid),
                "title": title,
                "url": (meta.get("url") or "").strip(),
                "series": name,
                "series_name": name,
                "series_url": url,
                "kind": kind,
                "output_format": fmt,
            })
        if not raw:
            return None
        # Die Sendungsseite liefert die neuesten Folgen zuerst.
        if series_watch.is_ard_audio_show_url(url):
            raw.reverse()
        seasons: Dict[Any, List[Dict]] = {}
        loose: List[Dict] = []
        counters: Dict[int, int] = {}
        any_season = False
        for ep in raw:
            s, e_num = series_watch.episode_s_e_from_title(ep.get("title") or "")
            if s is None:
                s = series_watch.season_from_title(ep.get("title") or "")
            if s is None:
                loose.append(ep)
                continue
            any_season = True
            if e_num is None:
                counters[s] = counters.get(s, 0) + 1
                e_num = counters[s]
            row = dict(ep)
            row["season_number"] = s
            row["episode_number"] = e_num
            seasons.setdefault(s, []).append(row)
        if not any_season:
            # Podcasts ohne S/E im Titel: eine Staffel, älteste Folge zuerst.
            # Video-Serien brauchen dafür die Mediathek, sonst landen alle in Staffel 1.
            if not series_watch.is_ard_audio_show_url(url):
                return None
            for i, ep in enumerate(raw, start=1):
                row = dict(ep)
                row["season_number"] = 1
                row["episode_number"] = i
                seasons.setdefault(1, []).append(row)
        else:
            for ep in loose:
                seasons.setdefault(None, []).append(ep)
        return {
            "series_name": name,
            "seasons": seasons,
            "total_episodes": sum(len(v) for v in seasons.values()),
        }

    def _series_watch_picker_urls(self, flat_eps: List[Dict]) -> List[str]:
        urls: List[str] = []
        for ep in flat_eps:
            u = (ep.get("series_url") or "").strip()
            if u and u not in urls:
                urls.append(u)
        if urls:
            return urls
        ids = {str(ep.get("id") or "") for ep in flat_eps if ep.get("id")}
        if not ids or series_watch is None:
            return []
        state = series_watch.load_state(self.base_download_path)
        for it in state.get("items") or []:
            if not isinstance(it, dict):
                continue
            known = {str(k) for k in (it.get("episodes") or {})}
            if ids.intersection(known):
                u = (it.get("url") or "").strip()
                if u and u not in urls:
                    urls.append(u)
        return urls

    def _series_watch_watch_item_for_url(self, url: str) -> Optional[Dict]:
        if series_watch is None:
            return None
        want = series_watch._normalize_url_key(url)
        if not want:
            return None
        state = series_watch.load_state(self.base_download_path)
        for it in state.get("items") or []:
            if not isinstance(it, dict):
                continue
            if series_watch._normalize_url_key(it.get("url") or "") == want:
                return it
        return None

    def _series_watch_picker_row(self, ep: Dict, *, have_ids: set, ignore_ids: set) -> Dict:
        """Eine Zeile: verfügbar, vorhanden oder ignoriert — gleiche IDs wie „Folgen habe ich“."""
        title = (ep.get("title") or ep.get("url") or "?").strip()
        eid = str(ep.get("id") or "")
        extra = bool(series_watch and series_watch.is_likely_extra_title(title))
        have_on = bool(eid and eid in have_ids)
        ign_on = bool(eid and eid in ignore_ids) or (extra and not have_on)
        if have_on:
            ign_on = False
        url = (ep.get("url") or "").strip()
        available = (not have_on) and (not ign_on) and bool(url)
        if have_on:
            status = "vorhanden"
        elif ign_on:
            status = "ignoriert"
        elif not url:
            status = "ohne Link"
        else:
            status = "verfügbar"
        s, e_num = (None, None)
        if series_watch is not None:
            s, e_num = series_watch.episode_s_e_from_title(title)
        season = ep.get("season_number")
        if season is None:
            season = s
        episode_number = ep.get("episode_number")
        if episode_number is None:
            episode_number = e_num
        row_ep = dict(ep)
        row_ep["title"] = title
        row_ep["id"] = eid
        row_ep["url"] = url
        if season is not None:
            row_ep["season_number"] = season
        if episode_number is not None:
            row_ep["episode_number"] = episode_number
        return {
            "ep": row_ep,
            "title": title,
            "available": available,
            "had": have_on,
            "ignored": ign_on,
            "status": status,
            "episode_number": episode_number if isinstance(episode_number, int) else 0,
        }

    def _series_watch_picker_sections(self, flat_eps: List[Dict], fetched: Dict[str, Optional[Dict]]) -> List[Dict]:
        """Staffeln wie im Dialog „Bereits vorhandene Folgen markieren“."""
        sections: List[Dict] = []
        used_ids: set = set()

        def rows_for_item(url: str, series_data: Optional[Dict], only_eps: List[Dict]) -> Dict:
            it = self._series_watch_watch_item_for_url(url) if url else None
            hid = set(str(x) for x in ((it or {}).get("have_ids") or []) if x)
            ign = set(str(x) for x in ((it or {}).get("ignore_ids") or []) if x)
            name = ""
            if isinstance(series_data, dict):
                name = (series_data.get("series_name") or "").strip()
            if not name and it:
                name = (it.get("display_name") or it.get("playlist_title") or "").strip()
            if not name and only_eps:
                name = (only_eps[0].get("series") or only_eps[0].get("series_name") or "").strip()
            kind = "video"
            fmt = ""
            if series_watch is not None and it is not None:
                kind = series_watch.watch_item_kind(it, url)
                fmt = series_watch.effective_download_format(it, url)
            elif series_watch is not None and url:
                kind = series_watch.watch_item_kind(None, url)
                fmt = series_watch.download_format_for_series(
                    series_watch.load_state(self.base_download_path), url, name
                )
            seasons: Dict[Any, List[Dict]] = {}

            def add_row(raw: Dict, season_hint) -> None:
                if "audiodeskription" in (raw.get("title") or "").lower():
                    return
                eid = str(raw.get("id") or "")
                eurl = (raw.get("url") or "").strip()
                if eid and eid in used_ids:
                    return
                if eurl and any(
                    (r.get("ep") or {}).get("url") == eurl
                    for bucket in seasons.values()
                    for r in bucket
                ):
                    return
                raw = dict(raw)
                raw.setdefault("series", name)
                raw.setdefault("series_name", name)
                raw.setdefault("series_url", url)
                raw.setdefault("kind", kind)
                raw.setdefault("output_format", fmt)
                if season_hint is not None:
                    raw["season_number"] = season_hint
                row = self._series_watch_picker_row(raw, have_ids=hid, ignore_ids=ign)
                sn = season_hint if season_hint is not None else raw.get("season_number")
                if sn is None and series_watch is not None:
                    sn = series_watch.season_from_title(row["title"])
                seasons.setdefault(sn, []).append(row)
                if eid:
                    used_ids.add(eid)

            def prepared_flat(ep: Dict) -> Dict:
                """Staffel nur aus dem Titel. Ein gesetztes season_number=1 ist oft nur der Download-Platzhalter."""
                raw = dict(ep)
                s, e_num = (None, None)
                if series_watch is not None:
                    s, e_num = series_watch.episode_s_e_from_title(raw.get("title") or "")
                    if s is None:
                        s = series_watch.season_from_title(raw.get("title") or "")
                if s is None:
                    raw.pop("season_number", None)
                    raw.pop("episode_number", None)
                else:
                    raw["season_number"] = s
                    if e_num is not None:
                        raw["episode_number"] = e_num
                return raw

            if isinstance(series_data, dict) and series_data.get("seasons"):
                for sn, eps in (series_data.get("seasons") or {}).items():
                    for ep in eps or []:
                        if isinstance(ep, dict):
                            add_row(ep, sn)
            else:
                for ep in only_eps:
                    if isinstance(ep, dict):
                        flat = prepared_flat(ep)
                        add_row(flat, flat.get("season_number"))

            known_titles = {
                (r.get("title") or "").strip().lower()
                for bucket in seasons.values()
                for r in bucket
            }
            for ep in only_eps:
                if not isinstance(ep, dict):
                    continue
                title_key = (ep.get("title") or "").strip().lower()
                if title_key and title_key in known_titles:
                    continue
                flat = prepared_flat(ep)
                add_row(flat, flat.get("season_number"))

            visible: Dict[Any, List[Dict]] = {}
            for sn, rows in seasons.items():
                rows.sort(key=lambda r: (r.get("episode_number") or 0, (r.get("title") or "").lower()))
                if rows:
                    visible[sn] = rows
            return {
                "series_name": name or "Serie",
                "series_url": url,
                "seasons": visible,
            }

        if fetched:
            for url, series_data in fetched.items():
                only = [ep for ep in flat_eps if (ep.get("series_url") or "").strip() == url]
                if not only and len(fetched) == 1:
                    only = list(flat_eps)
                sections.append(rows_for_item(url, series_data, only))
        else:
            by_name: Dict[str, List[Dict]] = {}
            for ep in flat_eps:
                key = (ep.get("series") or ep.get("series_name") or "").strip() or "Serie"
                by_name.setdefault(key, []).append(ep)
            for name, eps in by_name.items():
                section = rows_for_item("", None, eps)
                section["series_name"] = name
                sections.append(section)
        return [s for s in sections if s.get("seasons")]

    def _series_watch_new_episodes_actions_dialog(self, parent, flat_eps: List[Dict], heading: str = "Neue Folgen"):
        """Auswahl nach Staffeln, wie „Bereits vorhandene Folgen markieren“."""
        if not flat_eps:
            messagebox.showinfo("Serien-Wächter", "Keine Folgen in der Liste.", parent=parent)
            return
        urls = self._series_watch_picker_urls(flat_eps)
        fetched: Dict[str, Optional[Dict]] = {}
        missing_urls: List[str] = []
        for url in urls:
            cached = self._series_watch_cached_series_data(url)
            if cached and cached.get("seasons"):
                fetched[url] = cached
            else:
                missing_urls.append(url)
        sections: List[Dict] = []
        if fetched:
            sections.extend(self._series_watch_picker_sections(flat_eps, fetched))
        missing_set = set(missing_urls)
        leftover = [
            ep for ep in flat_eps
            if (ep.get("series_url") or "").strip() in missing_set or not fetched
        ]
        if leftover and (missing_urls or not fetched):
            sections.extend(self._series_watch_picker_sections(leftover, {}))
        if sections:
            self._series_watch_picker_checkbox_ui(parent, heading, sections)
            return
        if not urls or not VideoDownloader:
            self._series_watch_picker_checkbox_ui(parent, heading, sections)
            return

        wait = tk.Toplevel(parent)
        wait.title("Lade Folgenliste…")
        wait.geometry("360x110")
        wait.transient(parent)
        ttk.Label(wait, text="Mediathek wird nach Staffeln sortiert…", padding=20).pack()
        wait.update_idletasks()

        def work():
            for url in missing_urls:
                series_data = None
                try:
                    vd = self._series_watch_get_video_downloader()
                    if vd is not None:
                        series_data = vd.get_series_episodes(url)
                except Exception as e:
                    self._write_to_log_file(f"[Serien-Wächter] Folgenliste: {e}", "WARNING")
                    series_data = None
                fetched[url] = series_data if isinstance(series_data, dict) else None

            def show():
                try:
                    wait.destroy()
                except Exception:
                    pass
                try:
                    sections = self._series_watch_picker_sections(flat_eps, fetched)
                except Exception as e:
                    self._write_to_log_file(f"[Serien-Wächter] Folgenliste aufbauen: {e}", "ERROR")
                    sections = self._series_watch_picker_sections(flat_eps, {})
                if not sections:
                    messagebox.showinfo("Serien-Wächter", "Keine Folgen in der Liste.", parent=parent)
                    return
                self._series_watch_picker_checkbox_ui(parent, heading, sections)

            self.root.after(0, show)

        threading.Thread(target=work, daemon=True).start()

    def _series_watch_picker_checkbox_ui(self, parent, heading: str, sections: List[Dict]):
        """Checkbox-Liste nach Staffeln. Ignorieren schreibt in dieselben ignore_ids."""
        d = tk.Toplevel(parent)
        d.title(heading)
        d.transient(parent)
        d.grab_set()
        self._apply_dark_toplevel(d)
        self._fit_dialog(d, 960, 740, 720, 520)
        main_frame = ttk.Frame(d, padding="12", style="Download.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        names = [s.get("series_name") or "" for s in sections if s.get("series_name")]
        name_bit = names[0] if len(names) == 1 else ", ".join(n for n in names if n)
        ttk.Label(
            main_frame,
            text=(
                f"Serie: {name_bit} — Haken links = laden.\n"
                "Kreuz rechts = ignorieren (Trailer, Making-of, …): dieselbe Liste wie unter „Folgen habe ich“.\n"
                "Pro Staffel: „Gesamte Staffel markieren“ wählt alle Folgen dieser Staffel zum Laden."
            ),
            wraplength=900,
            style="Download.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))

        quick_fr = ttk.Frame(main_frame, style="Download.TFrame")
        quick_fr.pack(fill=tk.X, pady=(0, 6))
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _stretch(event):
            canvas.itemconfig(win_id, width=event.width)

        canvas.bind("<Configure>", _stretch)
        self._bind_scroll_wheel(canvas, scrollable)

        def _on_destroy(event=None):
            if event is not None and getattr(event, "widget", None) is not d:
                return
            self._series_watch_episode_picker_open = False

        d.bind("<Destroy>", _on_destroy)
        self._series_watch_episode_picker_open = True

        download_vars = {}
        ignore_vars = {}
        rows_by_key = {}
        season_vars = {}

        def _exclusive(have_var, ign_var, which):
            if which == "have" and have_var.get():
                ign_var.set(False)
            elif which == "ign" and ign_var.get():
                have_var.set(False)

        def select_all_episodes():
            for var in download_vars.values():
                var.set(True)
            for iv in ignore_vars.values():
                iv.set(False)
            for svar in season_vars.values():
                svar.set(True)

        def select_none_episodes():
            for var in download_vars.values():
                var.set(False)
            for svar in season_vars.values():
                svar.set(False)

        def ignore_extras():
            for key, iv in ignore_vars.items():
                row = rows_by_key.get(key) or {}
                title = row.get("title") or ""
                if series_watch is not None and series_watch.is_likely_extra_title(title):
                    iv.set(True)
                    if key in download_vars:
                        download_vars[key].set(False)

        ttk.Button(quick_fr, text="Alle Folgen auswählen", command=select_all_episodes, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(quick_fr, text="Alle abwählen", command=select_none_episodes, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(quick_fr, text="Trailer/Making-of ignorieren", command=ignore_extras, style="Download.TButton").pack(side=tk.LEFT, padx=6)

        multi = len([s for s in sections if s.get("seasons")]) > 1
        key_n = 0
        row_queue = []
        for section in sections:
            seasons = section.get("seasons") or {}
            series_name = (section.get("series_name") or "").strip()

            def season_key(sn):
                if sn is None:
                    return (1, 0)
                try:
                    return (0, int(sn))
                except (TypeError, ValueError):
                    return (0, 0)

            for sn in sorted(seasons.keys(), key=season_key):
                rows = seasons.get(sn) or []
                if not rows:
                    continue
                if sn is None:
                    frame_title = f"Weitere Folgen ({len(rows)})"
                    toggle_text = f"Gesamte Liste markieren ({len(rows)} Folgen)"
                else:
                    frame_title = f"Staffel {sn} ({len(rows)} Folgen)"
                    toggle_text = f"Gesamte Staffel {sn} markieren ({len(rows)} Folgen)"
                if multi and series_name:
                    frame_title = f"{series_name} — {frame_title}"
                lf = ttk.LabelFrame(scrollable, text=frame_title, padding="8")
                lf.pack(fill=tk.X, padx=4, pady=6)
                season_var = tk.BooleanVar(value=False)
                season_vars[key_n] = season_var
                season_index = key_n
                row_keys = []

                def make_season_toggle(keys, svar):
                    def toggle():
                        on = svar.get()
                        for k in keys:
                            if k in download_vars:
                                download_vars[k].set(on)
                            if on and k in ignore_vars:
                                ignore_vars[k].set(False)
                    return toggle

                toggle_btn = ttk.Checkbutton(lf, text=toggle_text, variable=season_var)
                toggle_btn.pack(anchor=tk.W, pady=(0, 6), padx=4)
                pending_rows = []
                for row in rows:
                    key_n += 1
                    key = key_n
                    rows_by_key[key] = row
                    row_keys.append(key)
                    title = row.get("title") or "?"
                    if len(title) > 70:
                        title = title[:67] + "…"
                    ign_on = bool(row.get("ignored"))
                    var = tk.BooleanVar(value=False)
                    ivar = tk.BooleanVar(value=ign_on)
                    download_vars[key] = var
                    ignore_vars[key] = ivar
                    pending_rows.append((lf, key, title, var, ivar, bool((row.get("ep") or {}).get("id"))))
                toggle_btn.configure(command=make_season_toggle(row_keys, season_var))
                season_vars[season_index] = season_var
                row_queue.extend(pending_rows)

        def _add_row_chunk(start: int = 0, size: int = 24) -> None:
            try:
                if not d.winfo_exists():
                    return
            except Exception:
                return
            end = min(start + size, len(row_queue))
            for lf, key, title, var, ivar, has_id in row_queue[start:end]:
                line = ttk.Frame(lf, style="Download.TFrame")
                line.pack(fill=tk.X, padx=8, pady=1)
                ttk.Checkbutton(
                    line,
                    text=title,
                    variable=var,
                    command=lambda h=var, g=ivar: _exclusive(h, g, "have"),
                ).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)
                if has_id:
                    ttk.Checkbutton(
                        line,
                        text="Ignorieren",
                        variable=ivar,
                        command=lambda h=var, g=ivar: _exclusive(h, g, "ign"),
                    ).pack(side=tk.RIGHT)
            if end < len(row_queue):
                d.after(1, lambda n=end: _add_row_chunk(n))
            else:
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                except Exception:
                    pass

        def persist_ignore() -> None:
            if series_watch is None:
                return
            by_url: Dict[str, Dict[str, List[str]]] = {}
            for key, iv in ignore_vars.items():
                row = rows_by_key.get(key) or {}
                ep = row.get("ep") or {}
                eid = str(ep.get("id") or "")
                if not eid:
                    continue
                surl = (ep.get("series_url") or "").strip()
                bucket = by_url.setdefault(surl, {"on": [], "off": []})
                if iv.get():
                    bucket["on"].append(eid)
                else:
                    bucket["off"].append(eid)
            for surl, bucket in by_url.items():
                series_watch.apply_ignore_selection(
                    self.base_download_path,
                    series_url=surl,
                    ignore_on=bucket["on"],
                    ignore_off=bucket["off"],
                )

        def collect_selected() -> List[Dict]:
            out = []
            for key, var in download_vars.items():
                if not var.get():
                    continue
                g = ignore_vars.get(key)
                if g is not None and g.get():
                    continue
                row = rows_by_key.get(key) or {}
                ep = dict(row.get("ep") or {})
                if not (ep.get("url") or "").strip():
                    continue
                if "audiodeskription" in (ep.get("title") or "").lower():
                    continue
                out.append(ep)
            return out

        def to_queue():
            persist_ignore()
            eps = collect_selected()
            if not eps:
                messagebox.showinfo("Hinweis", "Nichts zum Laden ausgewählt.", parent=d)
                return
            self._series_watch_add_episodes_to_video_queue(eps)
            d.destroy()
            audio_n = sum(1 for ep in eps if self._queue_item_is_audio(ep, ep.get("url") or ""))
            if audio_n and audio_n == len(eps):
                where = "Musik-Queue"
            elif audio_n:
                where = "Musik- und Video-Queue"
            else:
                where = "Video-Queue"
            messagebox.showinfo("Serien-Wächter", f"{len(eps)} Folge(n) zur {where} hinzugefügt.", parent=parent)

        def download_now():
            persist_ignore()
            eps = collect_selected()
            if not eps:
                messagebox.showinfo("Hinweis", "Nichts zum Laden ausgewählt.", parent=d)
                return
            norm_eps = []
            for ep in eps:
                ep2 = dict(ep)
                if not ep2.get("series"):
                    ep2["series"] = ep2.get("series_name") or ""
                if series_watch is not None:
                    s, e_num = series_watch.episode_s_e_from_title(ep2.get("title") or "")
                    if ep2.get("season_number") is None and s is not None:
                        ep2["season_number"] = s
                    if ep2.get("episode_number") is None and e_num is not None:
                        ep2["episode_number"] = e_num
                norm_eps.append(ep2)
            if not norm_eps:
                messagebox.showinfo("Serien-Wächter", "Keine gültigen Folgen.", parent=parent)
                return
            d.destroy()
            audio_n = sum(1 for ep in norm_eps if self._queue_item_is_audio(ep, ep.get("url") or ""))
            try:
                if audio_n:
                    self._select_music_tab()
                else:
                    self.notebook.select(self.notebook.index(self.video_frame))
            except Exception:
                pass
            self._series_watch_add_episodes_to_video_queue(norm_eps)
            self._video_queue_hold = False
            self.video_download_cancelled = False
            self._process_download_queue()
            self._update_queue_status()
            messagebox.showinfo(
                "Serien-Wächter",
                f"Download von {len(norm_eps)} Folge(n) gestartet.",
                parent=parent,
            )

        def save_ignore():
            persist_ignore()
            d.destroy()
            messagebox.showinfo(
                "Serien-Wächter",
                "Ignorieren ist gespeichert und steht auch unter „Folgen habe ich“.",
                parent=parent,
            )

        bf = ttk.Frame(main_frame, style="Download.TFrame")
        bf.pack(fill=tk.X, pady=8)
        ttk.Button(bf, text="Ausgewählte zur Queue", command=to_queue, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Ausgewählte herunterladen", command=download_now, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Ignorieren speichern", command=save_ignore, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Später", command=d.destroy, style="Download.TButton").pack(side=tk.RIGHT)
        try:
            d.update_idletasks()
        except Exception:
            pass
        d.after(1, _add_row_chunk)

    def _series_watch_add_episodes_to_video_queue(self, episodes: List[Dict]):
        """Fügt Episoden-Dicts (url, title, series, season_number, …) zur Video-Queue hinzu."""
        for ep in episodes:
            url = (ep.get("url") or "").strip()
            if not url:
                continue
            if "audiodeskription" in (ep.get("title") or "").lower():
                continue
            info = {
                "title": ep.get("title", ""),
                "series_name": ep.get("series") or ep.get("series_name") or "",
                "season_number": ep.get("season_number"),
                "episode_number": ep.get("episode_number"),
                "playlist_index": ep.get("playlist_index"),
                "url": url,
                "id": ep.get("id"),
                "kind": ep.get("kind") or "",
                "output_format": (ep.get("output_format") or "").lower(),
            }
            if info["season_number"] is None or info["episode_number"] is None:
                s, e = series_watch.episode_s_e_from_title(ep.get("title") or "")
                if info["season_number"] is None:
                    info["season_number"] = s
                if info["episode_number"] is None:
                    info["episode_number"] = e
            self._add_to_download_queue(url, episode_info=info, show_dialog=False)
        self._update_queue_status()

    def _series_watch_collect_missing_from_selection(self, parent, lb: tk.Listbox) -> List[Dict]:
        """Aktuelle Mediathek-Liste minus „habe ich schon“ für gewählten Serien-Eintrag."""
        sel = lb.curselection()
        if not sel:
            messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=parent)
            return []
        data = series_watch.load_state(self.base_download_path)
        items = data.get("items") or []
        idx = sel[0]
        if not (0 <= idx < len(items)) or not isinstance(items[idx], dict):
            return []
        it = items[idx]
        url = (it.get("url") or "").strip()
        if not url:
            return []
        stored = it.get("episodes") if isinstance(it.get("episodes"), dict) else {}
        cur: List[Dict] = []
        if stored:
            for eid, meta in stored.items():
                if not isinstance(meta, dict):
                    meta = {}
                cur.append({
                    "id": str(eid),
                    "title": (meta.get("title") or "").strip(),
                    "url": (meta.get("url") or "").strip(),
                })
        else:
            try:
                _pid, _pt, cur = series_watch.fetch_playlist_episodes(url)
            except Exception as e:
                messagebox.showerror("Serien-Wächter", str(e), parent=parent)
                return []
        missing = []
        for ep in cur:
            if series_watch.is_episode_had(ep, it):
                continue
            row = dict(ep)
            row["series_url"] = url
            row["series"] = (it.get("display_name") or it.get("playlist_title") or "").strip()
            row["output_format"] = series_watch.effective_download_format(it, url)
            row["kind"] = series_watch.watch_item_kind(it, url)
            missing.append(row)
        if not missing:
            messagebox.showinfo("Serien-Wächter", "Keine fehlenden Folgen laut Besitz-Regeln.", parent=parent)
        return missing

    def _series_watch_format_dialog(self, parent, item_index: int, refresh_list):
        """Ausgabeformat einer überwachten Serie: MP4/MKV, bei Audio MP3, bei YouTube auch MP3."""
        if series_watch is None:
            return
        data = series_watch.load_state(self.base_download_path)
        items = data.get("items") or []
        if not (0 <= item_index < len(items)) or not isinstance(items[item_index], dict):
            return
        it = items[item_index]
        choices = series_watch.format_choices_for_watch(it)
        current = series_watch.effective_download_format(it)
        name = (it.get("display_name") or it.get("playlist_title") or it.get("url") or "Serie").strip()
        d = tk.Toplevel(parent)
        d.title("Download-Format")
        d.transient(parent)
        d.grab_set()
        self._apply_dark_toplevel(d)
        self._fit_dialog(d, 460, 280, 400, 220)
        frm = ttk.Frame(d, padding=14, style="Download.TFrame")
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frm,
            text=f"{name}\nBeim Laden gefundener Folgen wird dieses Format verwendet.",
            style="Download.TLabel",
            wraplength=420,
        ).pack(anchor=tk.W, pady=(0, 10))
        var = tk.StringVar(value=current)
        labels = {
            "mp4": "MP4  (Video, Standard)",
            "mkv": "MKV  (Video)",
            "mp3": "MP3  (Audio, Musik-Ordner)",
        }
        for choice in choices:
            ttk.Radiobutton(
                frm, text=labels.get(choice, choice.upper()), variable=var, value=choice,
            ).pack(anchor=tk.W, pady=2)

        def save():
            it["download_format"] = var.get()
            series_watch.save_state(self.base_download_path, data)
            d.destroy()
            try:
                refresh_list()
            except Exception:
                pass

        bf = ttk.Frame(frm, style="Download.TFrame")
        bf.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(bf, text="Speichern", command=save, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bf, text="Abbrechen", command=d.destroy, style="Download.TButton").pack(side=tk.LEFT)

    def show_series_watch_dialog(self):
        """Dialog: Serien-URLs überwachen (Mediathek-Playlist), neue Folgen melden."""
        if series_watch is None:
            messagebox.showinfo("Serien-Wächter", "Modul series_watch.py nicht gefunden.")
            return
        win = tk.Toplevel(self.root)
        win.title("📺 Serien-Wächter")
        win.transient(self.root)
        self._apply_dark_toplevel(win)
        self._fit_dialog(win, 960, 720, 720, 520)
        main = ttk.Frame(win, padding="12", style="Download.TFrame")
        main.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            main,
            text="Video (z. B. ARD Mediathek, YouTube-Playlist) und Musik (YouTube Music, ARD Audiothek, ARD Sounds, LibriVox, …).\n"
            "Neue Lieder oder Folgen in der Playlist werden gemeldet und können automatisch geladen werden.\n"
            "ARD-Video: Auch bei „Staffel-x“-Links wird intern die Serien-URL genutzt.\n"
            "Audiodeskription wird ignoriert. Trailer/Making-of können Sie mit „Ignorieren“ ausblenden.\n"
            "Downloads werden als „habe ich“ abgehakt.\n"
            "Auto-Download: global in den Einstellungen oder pro Serie.\n"
            "Format pro Serie: Video standardmäßig MP4 (oder MKV). ARD Sounds als MP3. "
            "YouTube-Playlists als MP4, MKV oder MP3. Audio landet im Musik-Ordner, Video im Video-Ordner.",
            font=("Arial", 10),
            wraplength=900,
        ).pack(anchor=tk.W, pady=(0, 8))

        list_frame = ttk.LabelFrame(main, text="Überwachte Serien", padding="8", style="Download.TLabelframe")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        lb = tk.Listbox(
            list_frame, height=11, font=("Arial", 14), exportselection=False,
            bg=getattr(self, '_tk_bg_card', '#424242'), fg=getattr(self, '_tk_fg_text', '#e8e8e8'),
            selectbackground=getattr(self, '_tk_btn_bg', '#4a4a4a'), highlightthickness=0,
        )
        lb.pack(fill=tk.BOTH, expand=True)

        def refresh_list():
            lb.delete(0, tk.END)
            data = series_watch.load_state(self.base_download_path)
            for it in data.get("items") or []:
                if not isinstance(it, dict):
                    continue
                nm = (it.get("display_name") or "").strip() or (it.get("url") or "")[:50]
                u = (it.get("url") or "")[:72]
                kind = "🎧" if series_watch.watch_item_kind(it) == "audio" else "📺"
                n_ep = len(it.get("episodes") or {}) if isinstance(it.get("episodes"), dict) else 0
                n_have = len(it.get("have_ids") or []) if isinstance(it.get("have_ids"), list) else 0
                n_ign = len(it.get("ignore_ids") or []) if isinstance(it.get("ignore_ids"), list) else 0
                bl = "✓" if it.get("baseline_done") else "…"
                ad = ""
                if "auto_download" in it:
                    ad = "  |  Auto-DL an" if it.get("auto_download") else "  |  Auto-DL aus"
                elif self.settings.get("series_watch_auto_download", False):
                    ad = "  |  Auto-DL (global)"
                ign_s = f"  |  ignoriert {n_ign}" if n_ign else ""
                fmt = series_watch.effective_download_format(it).upper()
                lb.insert(tk.END, f"{bl} {kind} {nm}  |  {fmt}  |  Stand {n_ep} IDs  |  als „habe“ {n_have}{ign_s}{ad}  |  {u}")

        refresh_list()

        add_fr = ttk.Frame(main, style="Download.TFrame")
        add_fr.pack(fill=tk.X, pady=8)
        ttk.Label(add_fr, text="URL:", font=("Arial", 13)).pack(side=tk.LEFT, padx=(0, 4))
        url_var = tk.StringVar()
        ttk.Entry(add_fr, textvariable=url_var, width=48, font=("Arial", 14), style="Download.TEntry").pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True, ipady=4)
        ttk.Label(add_fr, text="Name (optional):", font=("Arial", 13)).pack(side=tk.LEFT, padx=(8, 4))
        name_var = tk.StringVar()
        ttk.Entry(add_fr, textvariable=name_var, width=16, font=("Arial", 14), style="Download.TEntry").pack(side=tk.LEFT, padx=2, ipady=4)

        btn_fr = ttk.Frame(main, style="Download.TFrame")
        btn_fr.pack(fill=tk.X, pady=4)

        def add_item():
            u = url_var.get().strip()
            if not u:
                messagebox.showwarning("Hinweis", "Bitte eine URL eingeben.", parent=win)
                return
            data = series_watch.load_state(self.base_download_path)
            items = data.setdefault("items", [])
            nu = series_watch.normalize_watch_url(u)
            items.append({
                "url": nu,
                "kind": series_watch.watch_item_kind(None, nu),
                "download_format": series_watch.effective_download_format(None, nu),
                "display_name": name_var.get().strip(),
                "episodes": {},
                "baseline_done": False,
                "max_season_seen": 0,
                "have_ids": [],
                "ignore_ids": [],
                "have_full_seasons_upto": 0,
                "have_partial_seasons": [],
            })
            series_watch.save_state(self.base_download_path, data)
            url_var.set("")
            name_var.set("")
            refresh_list()
            if nu != u:
                messagebox.showinfo(
                    "Serien-Wächter",
                    "ARD-Staffel-Link wurde zur Serien-URL normalisiert, damit alle Staffeln überwacht werden können.",
                    parent=win,
                )

        def remove_item():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=win)
                return
            data = series_watch.load_state(self.base_download_path)
            items = data.get("items") or []
            if 0 <= sel[0] < len(items):
                items.pop(sel[0])
                series_watch.save_state(self.base_download_path, data)
            refresh_list()

        def toggle_auto_download():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=win)
                return
            data = series_watch.load_state(self.base_download_path)
            items = data.get("items") or []
            idx = sel[0]
            if not (0 <= idx < len(items)) or not isinstance(items[idx], dict):
                return
            it = items[idx]
            # Zyklus: (global) → an → aus → (global)
            if "auto_download" not in it:
                it["auto_download"] = True
            elif it.get("auto_download"):
                it["auto_download"] = False
            else:
                it.pop("auto_download", None)
            series_watch.save_state(self.base_download_path, data)
            refresh_list()
            lb.selection_set(idx)

        def run_check_now():
            sel = lb.curselection()
            if not sel:
                messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=win)
                return
            data = series_watch.load_state(self.base_download_path)
            items = data.get("items") or []
            idx = sel[0]
            if not (0 <= idx < len(items)) or not isinstance(items[idx], dict):
                return
            only_url = (items[idx].get("url") or "").strip()
            only_name = (items[idx].get("display_name") or items[idx].get("playlist_title") or only_url).strip()
            if not only_url:
                return

            def work():
                lock = series_watch.try_acquire_check_lock(self.base_download_path, "gui-manual")
                if lock is None:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Serien-Wächter",
                        "Prüfung läuft bereits (Haupt-App oder Tray-Helper). Bitte kurz warten.",
                        parent=win,
                    ))
                    return
                try:
                    try:
                        _, notifications = series_watch.check_all(
                            self.base_download_path,
                            on_item_error=lambda n, e: self._write_to_log_file(f"[Serien-Wächter] {n}: {e}", "WARNING"),
                            report_unowned=True,
                            only_url=only_url,
                        )
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror("Serien-Wächter", str(e), parent=win))
                        self.root.after(0, refresh_list)
                        return
                    self._series_watch_last_run = time.time()
                    self.root.after(0, refresh_list)
                    notifications = [
                        n for n in (notifications or [])
                        if series_watch._normalize_url_key(n.get("series_url") or "")
                        == series_watch._normalize_url_key(only_url)
                    ]
                    if not notifications:
                        open_rows = self._series_watch_rows_for_picker(only_url)
                        if open_rows:
                            self.root.after(0, lambda rows=list(open_rows): self._series_watch_new_episodes_actions_dialog(
                                win,
                                rows,
                                f"Fehlende Folgen — {only_name}",
                            ))
                            return
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Serien-Wächter",
                            f"Keine fehlenden Folgen bei „{only_name}“.",
                            parent=win,
                        ))
                        return
                    self._series_watch_notify_and_maybe_download(notifications, interactive=True, parent=win)
                finally:
                    series_watch.release_check_lock(lock)

            threading.Thread(target=work, daemon=True).start()

        def sel_idx():
            s = lb.curselection()
            return s[0] if s else None

        ttk.Button(btn_fr, text="➕ Hinzufügen", command=add_item, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_fr, text="🗑️ Entfernen", command=remove_item, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_fr, text="🔄 Jetzt prüfen", command=run_check_now, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_fr, text="⬇ Auto-DL umschalten", command=toggle_auto_download, style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_fr, text="Schließen", command=win.destroy, style="Download.TButton").pack(side=tk.RIGHT, padx=6)
        btn_fr2 = ttk.Frame(main, style="Download.TFrame")
        btn_fr2.pack(fill=tk.X, pady=(0, 4))

        def _with_sel(fn):
            i = sel_idx()
            if i is None:
                messagebox.showinfo("Hinweis", "Bitte einen Eintrag wählen.", parent=win)
                return
            fn(i)

        ttk.Button(btn_fr2, text="☑ Folgen habe ich…", command=lambda: _with_sel(lambda i: self._series_watch_owned_episodes_dialog(win, i)), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(btn_fr2, text="📦 Download-Format…", command=lambda: _with_sel(lambda i: self._series_watch_format_dialog(win, i, refresh_list)), style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_fr2, text="⚡ Schnell Staffel 1…n", command=lambda: _with_sel(lambda i: self._series_watch_quick_rules_dialog(win, i)), style="Download.TButton").pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_fr2, text="⬇ Fehlende / neue wählen…", command=lambda: self._series_watch_new_episodes_actions_dialog(win, self._series_watch_collect_missing_from_selection(win, lb), "Folgen — Queue oder Download"), style="Download.TButton").pack(side=tk.LEFT, padx=6)

    def _get_download_archive_path(self) -> Path:
        """Pfad zur Download-Archiv-Datei (eine URL pro Zeile)."""
        p = self.settings.get('download_archive_path') or str(self.base_download_path / "download_archive.txt")
        return Path(p)

    def _is_in_download_archive(self, url: str) -> bool:
        """Prüft ob die URL bereits im Download-Archiv steht (bereits heruntergeladen)."""
        if not self.settings.get('download_archive_enabled', False):
            return False
        path = self._get_download_archive_path()
        if not path.exists():
            return False
        url_norm = (url or "").strip()
        if not url_norm:
            return False
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.strip() == url_norm:
                        return True
        except Exception:
            pass
        return False

    def _add_to_download_archive(self, url: str):
        """Fügt URL zum Download-Archiv hinzu (nach erfolgreichem Download)."""
        if not self.settings.get('download_archive_enabled', False):
            return
        url_norm = (url or "").strip()
        if not url_norm:
            return
        path = self._get_download_archive_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(url_norm + '\n')
        except Exception:
            pass

    def _open_folder(self, path: Path):
        """Öffnet den Ordner im System-Dateimanager."""
        try:
            folder = path if path.is_dir() else path.parent
            if sys.platform == 'darwin':
                subprocess.run(['open', str(folder)], check=False, timeout=5)
            elif sys.platform == 'win32':
                subprocess.run(['explorer', str(folder)], check=False, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            else:
                subprocess.run(['xdg-open', str(folder)], check=False, timeout=5)
        except Exception as e:
            self.video_log(f"Ordner konnte nicht geöffnet werden: {e}")

    def _open_file_with_default_app(self, path: Path):
        """Öffnet die Datei mit der Standard-Anwendung (z. B. Video/ Audio-Player)."""
        try:
            if sys.platform == 'darwin':
                subprocess.run(['open', str(path)], check=False, timeout=5)
            elif sys.platform == 'win32':
                os.startfile(str(path))
            else:
                subprocess.run(['xdg-open', str(path)], check=False, timeout=5)
        except Exception as e:
            self.video_log(f"Datei konnte nicht geöffnet werden: {e}")

    def _get_domain_from_url(self, url: str) -> str:
        """Extrahiert die Domain aus einer URL (z. B. youtube.com)."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            netloc = (parsed.netloc or "").lower()
            if netloc.startswith("www."):
                netloc = netloc[4:]
            return netloc or ""
        except Exception:
            return ""

    def _get_domain_preset(self, url: str):
        """Liefert (quality, format) für die URL aus domain_quality_format, sonst None."""
        domain = self._get_domain_from_url(url)
        if not domain:
            return None
        for entry in self.settings.get('domain_quality_format', []):
            if not isinstance(entry, dict):
                continue
            preset_domain = (entry.get('domain') or "").strip().lower()
            if preset_domain and (preset_domain in domain or domain in preset_domain):
                q = entry.get('quality', '').strip()
                f = entry.get('format', '').strip().lower()
                if q or f:
                    return (q or None, f or None)
        return None

    def _apply_domain_preset(self, url: str):
        """Setzt Qualität und Format in der UI gemäß Voreinstellung für die Domain der URL."""
        preset = self._get_domain_preset(url)
        if preset:
            quality, fmt = preset
            if quality and hasattr(self, 'video_quality_var'):
                self.video_quality_var.set(quality)
            if fmt and hasattr(self, 'video_format_var'):
                self.video_format_var.set(fmt)

    def _blit_photo(self, photo, pil_img):
        rows = []
        w, h = pil_img.size
        px = pil_img.load()
        for y in range(h):
            rows.append("{" + " ".join("#%02x%02x%02x" % px[x, y][:3] for x in range(w)) + "}")
        photo.put(" ".join(rows), to=(0, 0))

    def _smooth_disc(self, size, bg, fg, selected):
        """Kreis in hoher Auflösung, danach weich verkleinert. Sonst sind die Ränder Treppen."""
        from PIL import Image, ImageDraw
        scale = 8
        bg_rgb = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
        fg_rgb = tuple(int(fg[i:i + 2], 16) for i in (1, 3, 5))
        im = Image.new("RGB", (size * scale, size * scale), bg_rgb)
        draw = ImageDraw.Draw(im)
        pad = int(scale * 1.2)
        ring = max(2, int(scale * 1.7))
        box = (pad, pad, size * scale - pad - 1, size * scale - pad - 1)
        draw.ellipse(box, outline=fg_rgb, width=ring)
        if selected:
            inset = int((size * scale) * 0.30)
            draw.ellipse((inset, inset, size * scale - inset - 1, size * scale - inset - 1), fill=fg_rgb)
        one = im.resize((size, size), Image.Resampling.LANCZOS)
        two = im.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
        return one, two

    def _paint_mark(self, img, bg, fg, kind):
        """Zeichnet Kreis oder Kästchen in ein bestehendes PhotoImage."""
        size = int(img.width())
        if kind.startswith("radio"):
            one, two = self._smooth_disc(size, bg, fg, kind == "radio-on")
            self._blit_photo(img, one)
            images = getattr(self, "_choice_images", None) or {}
            key = "radio_on_2x" if kind == "radio-on" else "radio_off_2x"
            if images.get(key) is not None:
                self._blit_photo(images[key], two)
            return
        img.put(bg, to=(0, 0, size, size))
        for y in range(size):
            for x in range(size):
                edge = 1 <= x <= size - 2 and 1 <= y <= size - 2 and (
                    x <= 2 or y <= 2 or x >= size - 3 or y >= size - 3
                )
                if edge:
                    img.put(fg, to=(x, y))
        if kind == "check-on":
            m = size * 0.24
            self._stamp_line(img, m, m, size - m, size - m, fg, 1)
            self._stamp_line(img, size - m, m, m, size - m, fg, 1)

    def _stamp_line(self, img, x0, y0, x1, y1, color, thick):
        size = int(img.width())
        steps = int(max(abs(x1 - x0), abs(y1 - y0)) * 3) + 1
        for i in range(steps + 1):
            t = i / steps
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            for dx in range(-thick, thick + 1):
                for dy in range(-thick, thick + 1):
                    if dx * dx + dy * dy > thick * thick + 1:
                        continue
                    ix = int(round(x + dx))
                    iy = int(round(y + dy))
                    if 1 <= ix < size - 1 and 1 <= iy < size - 1:
                        img.put(color, to=(ix, iy))

    def _sync_options_scroll(self, canvas, inner, window_id):
        """Scrollbereich nur so hoch wie der Inhalt. Sonst rutscht das Feld ins Leere."""
        try:
            if not canvas.winfo_exists():
                return
            width = max(1, int(canvas.winfo_width()))
            height = max(1, int(canvas.winfo_height()))
            inner.update_idletasks()
            need = max(1, int(inner.winfo_reqheight()))
            canvas.itemconfig(window_id, width=width, height=need)
            if need <= height + 1:
                canvas.configure(scrollregion=(0, 0, width, height))
                canvas.yview_moveto(0)
            else:
                canvas.configure(scrollregion=(0, 0, width, need))
        except tk.TclError:
            pass

    def _install_choice_indicators(self, bg, fg):
        """Größere Kreise und Kästchen. clam zeichnet die Markierung sonst fest und klein."""
        try:
            radio_size, check_size = 22, 20
            images = getattr(self, "_choice_images", None)
            if not images or images["radio_off"].width() != radio_size:
                images = {
                    "radio_off": tk.PhotoImage(width=radio_size, height=radio_size),
                    "radio_on": tk.PhotoImage(width=radio_size, height=radio_size),
                    "radio_off_2x": tk.PhotoImage(width=radio_size * 2, height=radio_size * 2),
                    "radio_on_2x": tk.PhotoImage(width=radio_size * 2, height=radio_size * 2),
                    "check_off": tk.PhotoImage(width=check_size, height=check_size),
                    "check_on": tk.PhotoImage(width=check_size, height=check_size),
                }
                self._choice_images = images
                fresh = True
            else:
                fresh = False
            self._paint_mark(images["radio_off"], bg, fg, "radio-off")
            self._paint_mark(images["radio_on"], bg, fg, "radio-on")
            for key, twin in (("radio_off", "radio_off_2x"), ("radio_on", "radio_on_2x")):
                try:
                    images[key].tk.call(images[key], "configure", "-format", ("retina", images[twin]))
                except tk.TclError:
                    pass
            self._paint_mark(images["check_off"], bg, fg, "check-off")
            self._paint_mark(images["check_on"], bg, fg, "check-on")
            style = ttk.Style()
            if fresh:
                style.element_create(
                    "Download.Radio.ind", "image", images["radio_off"],
                    ("selected", images["radio_on"]),
                    ("active", images["radio_off"]),
                    ("active", "selected", images["radio_on"]),
                    sticky="w",
                )
                style.element_create(
                    "Download.Check.ind", "image", images["check_off"],
                    ("selected", images["check_on"]),
                    ("active", images["check_off"]),
                    ("active", "selected", images["check_on"]),
                    sticky="w",
                )
                style.layout("Download.TRadiobutton", [
                    ("Radiobutton.padding", {"sticky": "nswe", "children": [
                        ("Download.Radio.ind", {"side": "left", "sticky": "w"}),
                        ("Radiobutton.label", {"side": "left", "sticky": "w"}),
                    ]}),
                ])
                style.layout("Download.TCheckbutton", [
                    ("Checkbutton.padding", {"sticky": "nswe", "children": [
                        ("Download.Check.ind", {"side": "left", "sticky": "w"}),
                        ("Checkbutton.label", {"side": "left", "sticky": "w"}),
                    ]}),
                ])
        except tk.TclError:
            pass

    def _apply_theme(self, theme_name: str):
        """Wendet Dark- oder Light-Theme auf ttk-Styles an."""
        try:
            _s = ttk.Style()
            if (theme_name or '').lower() == 'light':
                _bg_panel = "#f0f0f0"
                _bg_card = "#ffffff"
                _fg_text = "#1a1a1a"
                _btn_bg = "#e0e0e0"
                _btn_fg = "#1a1a1a"
                _btn_hover = "#d0d0d0"
                _btn_press = "#c0c0c0"
                _btn_light = "#e8e8e8"
                _btn_dark = "#b0b0b0"
            else:
                _bg_panel = "#383838"
                _bg_card = "#424242"
                _fg_text = "#e8e8e8"
                _btn_bg = "#4a4a4a"
                _btn_fg = "#f0f0f0"
                _btn_hover = "#565656"
                _btn_press = "#3a3a3a"
                _btn_light = "#5e5e5e"
                _btn_dark = "#363636"
            self._tk_bg_panel = _bg_panel
            self._tk_bg_card = _bg_card
            self._tk_fg_text = _fg_text
            self._tk_btn_bg = _btn_bg
            self._tk_btn_fg = _btn_fg
            self._tk_btn_hover = _btn_hover
            self._tk_btn_press = _btn_press
            self._tk_btn_light = _btn_light
            self._tk_btn_dark = _btn_dark
            self._tk_log_bg = _bg_card if (theme_name or '').lower() == 'light' else _bg_panel
            _s.configure("Download.TFrame", background=_bg_panel)
            _s.configure("Download.TLabelframe", background=_bg_panel, borderwidth=0)
            _s.configure("Download.TLabelframe.Label", font=("Arial", 9), background=_bg_panel, foreground=_fg_text)
            _s.configure("Download.TRadiobutton", background=_bg_panel, foreground=_fg_text, font=("Arial", 9))
            _s.map("Download.TRadiobutton", background=[("active", _bg_panel)], foreground=[("active", _fg_text)])
            _s.configure("Download.TCheckbutton", background=_bg_panel, foreground=_fg_text, font=("Arial", 9))
            _s.map("Download.TCheckbutton", background=[("active", _bg_panel)], foreground=[("active", _fg_text)])
            self._install_choice_indicators(_bg_panel, _fg_text)
            _s.configure("Download.TButton", font=("Arial", 9), padding=(20, 4), anchor="center", background=_btn_bg, foreground=_btn_fg, relief="raised", borderwidth=2)
            try:
                _s.configure("Download.TButton", lightcolor=_btn_light, darkcolor=_btn_dark)
            except tk.TclError:
                pass
            _s.map("Download.TButton", background=[("active", _btn_hover), ("pressed", _btn_press)], relief=[("pressed", "sunken")])
            _s.map("Download.TButton", foreground=[("active", _btn_fg), ("pressed", _btn_fg)])
            try:
                _s.layout("Download.TButton.Large", _s.layout("TButton"))
            except tk.TclError:
                pass
            _s.configure("Download.TButton.Large", font=("Arial", 9), padding=(26, 5), anchor="center", background=_btn_bg, foreground=_btn_fg, relief="raised", borderwidth=2)
            try:
                _s.configure("Download.TButton.Large", lightcolor=_btn_light, darkcolor=_btn_dark)
            except tk.TclError:
                pass
            _s.map("Download.TButton.Large", background=[("active", _btn_hover), ("pressed", _btn_press)], relief=[("pressed", "sunken")])
            _s.map("Download.TButton.Large", foreground=[("active", _btn_fg), ("pressed", _btn_fg)])
            _s.configure("Download.TLabel", font=("Arial", 9), background=_bg_panel, foreground=_fg_text)
            # Standard-Widgets, damit Dialoge wie Statistik, Historie und Suche nicht hell bleiben.
            for style_name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label"):
                _s.configure(style_name, background=_bg_panel, foreground=_fg_text)
            _s.configure("TRadiobutton", background=_bg_panel, foreground=_fg_text)
            _s.map("TRadiobutton", background=[("active", _bg_panel)], foreground=[("active", _fg_text)])
            _s.configure("TCheckbutton", background=_bg_panel, foreground=_fg_text)
            _s.map("TCheckbutton", background=[("active", _bg_panel)], foreground=[("active", _fg_text)])
            _s.configure("TButton", background=_btn_bg, foreground=_btn_fg, padding=(12, 4))
            try:
                _s.configure("TButton", lightcolor=_btn_light, darkcolor=_btn_dark)
            except tk.TclError:
                pass
            _s.map("TButton", background=[("active", _btn_hover), ("pressed", _btn_press)], foreground=[("active", _btn_fg), ("pressed", _btn_fg)])
            _s.configure("Treeview", background=_bg_card, foreground=_fg_text, fieldbackground=_bg_card)
            _s.configure("Treeview.Heading", background=_btn_bg, foreground=_fg_text)
            _s.map("Treeview", background=[("selected", _btn_bg)], foreground=[("selected", _btn_fg)])
            _s.configure("TEntry", fieldbackground=_bg_card, foreground=_fg_text)
            for scroll_style in ("Vertical.TScrollbar", "Horizontal.TScrollbar"):
                _s.configure(scroll_style, background=_btn_bg, troughcolor=_bg_panel, arrowcolor=_fg_text)
            _s.configure("TNotebook", background=_bg_panel)
            _s.configure("TNotebook.Tab", background=_bg_card, foreground=_fg_text, padding=(10, 5), font=("Arial", 9))
            _s.map("TNotebook.Tab", background=[("selected", _bg_panel)], expand=[("selected", [1, 1, 1, 0])])
            _s.configure("Download.Treeview", background=_bg_card, foreground=_fg_text, fieldbackground=_bg_card)
            _s.configure("Download.Treeview.Heading", background=_btn_bg, foreground=_fg_text)
            _s.configure("Download.TEntry", fieldbackground=_bg_card, foreground=_fg_text, insertcolor=_fg_text)
            try:
                _s.configure("Download.TCombobox", fieldbackground=_bg_card, foreground=_fg_text, background=_bg_card)
            except tk.TclError:
                pass
            _bar = "#1565c0" if (theme_name or "").lower() == "light" else "#3b82f6"
            _trough = "#d6d6d6" if (theme_name or "").lower() == "light" else "#2a2a2a"
            _s.configure(
                "Horizontal.TProgressbar",
                background=_bar,
                troughcolor=_trough,
                bordercolor=_trough,
                lightcolor=_bar,
                darkcolor=_bar,
                thickness=14,
            )
            self._refresh_theme_tk_widgets()
        except Exception:
            pass

    def _refresh_theme_tk_widgets(self):
        """Tk-Widgets (Canvas, Log, Root), die nicht über ttk.Style laufen, ans Theme anpassen."""
        try:
            bp = getattr(self, '_tk_bg_panel', '#383838')
            bc = getattr(self, '_tk_bg_card', '#424242')
            fg = getattr(self, '_tk_fg_text', '#e8e8e8')
            log_bg = getattr(self, '_tk_log_bg', bp)
            self.root.configure(bg=bp)
            canvas = getattr(self, '_search_results_canvas', None)
            if canvas is not None:
                try:
                    if canvas.winfo_exists():
                        canvas.configure(bg=bp, highlightthickness=0)
                except tk.TclError:
                    pass
            for attr in ('_music_options_canvas', '_video_options_canvas'):
                c = getattr(self, attr, None)
                if c is not None:
                    try:
                        if c.winfo_exists():
                            c.configure(bg=bp)
                    except tk.TclError:
                        pass
            for attr in ('video_log_text', 'music_log_text'):
                st = getattr(self, attr, None)
                if st is not None:
                    try:
                        if st.winfo_exists():
                            st.configure(bg=log_bg, fg=fg, insertbackground=fg)
                            self._style_log_scrolledtext(st)
                    except tk.TclError:
                        pass
            st = getattr(self, 'spotify_log_text', None)
            if st is not None:
                try:
                    if st.winfo_exists():
                        st.configure(bg=log_bg, fg=fg, insertbackground=fg)
                        self._style_log_scrolledtext(st)
                except tk.TclError:
                    pass
        except Exception:
            pass

    def _clean_url(self, url: str) -> str:
        """Bereinigt eine URL von doppelten Einträgen und Whitespace"""
        url = url.strip()
        if not url:
            return url
        
        # Prüfe ob die URL doppelt vorkommt (z.B. "urlurl" oder "url url")
        # Finde die längste mögliche URL und prüfe ob sie sich wiederholt
        import re
        # Suche nach URLs im Text
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, url)
        
        if len(urls) > 1:
            # Wenn mehrere URLs gefunden wurden, nimm die erste
            url = urls[0]
        elif len(urls) == 1:
            url = urls[0]
        else:
            # Keine URL gefunden, prüfe ob die URL sich selbst wiederholt
            # Beispiel: "https://example.comhttps://example.com"
            # Finde die erste vollständige URL
            match = re.search(r'(https?://[^\s]+)', url)
            if match:
                first_url = match.group(1)
                # Prüfe ob die URL sich wiederholt
                if url.startswith(first_url + first_url):
                    url = first_url
                elif first_url in url and url.count(first_url) > 1:
                    # URL kommt mehrfach vor, nimm nur die erste
                    url = first_url
        
        return url.strip()
    
    def start_audio_recording(self):
        """Startet automatische Audio-Aufnahme mit Browser-Automatisierung"""
        url = self.music_url_var.get().strip()
        
        # Bereinige URL
        url = self._clean_url(url)
        self.music_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine URL ein.")
            return
        
        # Erkenne Provider
        is_spotify = 'spotify.com' in url.lower()
        is_deezer = 'deezer.com' in url.lower() or 'link.deezer.com' in url.lower()
        
        if not (is_spotify or is_deezer):
            messagebox.showwarning("Ungültige URL", "Audio-Aufnahme funktioniert nur mit Spotify oder Deezer URLs.")
            return
        
        # Bestätigungs-Dialog
        provider = "Spotify" if is_spotify else "Deezer"
        result = messagebox.askyesno(
            "Audio-Automatisierung",
            f"Automatische Audio-Aufnahme starten?\n\n"
            f"Provider: {provider}\n"
            f"URL: {url}\n\n"
            f"Der Browser wird automatisch geöffnet, der Track wird abgespielt\n"
            f"(stumm, 2x Geschwindigkeit) und die Aufnahme erfolgt automatisch.\n\n"
            f"⚠️ Nur für privaten Gebrauch!"
        )
        
        if not result:
            return
        
        # Starte in separatem Thread
        threading.Thread(
            target=self.audio_recording_thread,
            args=(url, provider.lower()),
            daemon=True
        ).start()
    
    def audio_recording_thread(self, url: str, provider: str):
        """Thread für automatische Audio-Aufnahme"""
        try:
            from stream_automation import StreamAutomation
            
            # Erstelle Ausgabepfad
            output_dir = Path(self.music_download_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Erstelle Dateiname aus URL
            import re
            if provider == "spotify":
                track_id_match = re.search(r'spotify\.com/track/([a-zA-Z0-9]+)', url)
                filename = f"spotify_{track_id_match.group(1) if track_id_match else 'track'}.mp3"
            else:
                track_id_match = re.search(r'deezer\.com/(?:[a-z]{2}/)?track/(\d+)', url)
                filename = f"deezer_{track_id_match.group(1) if track_id_match else 'track'}.mp3"
            
            output_path = output_dir / filename
            
            self.root.after(0, lambda: self.music_status_var.set("Audio-Aufnahme läuft..."))
            self.root.after(0, lambda: self.music_progress_bar.start())
            self.root.after(0, lambda: self.music_download_button.config(state=tk.DISABLED))
            self.root.after(0, lambda: self.music_record_button.config(state=tk.DISABLED))
            
            self.music_log(f"🎙️ Starte automatische Audio-Aufnahme...")
            self.music_log(f"Provider: {provider}")
            self.music_log(f"URL: {url}")
            self.music_log(f"Ausgabe: {output_path}")
            
            # Zeige Fortschritt während der Aufnahme
            def update_progress(elapsed: float):
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                self.root.after(0, lambda: self.music_status_var.set(
                    f"🎙️ Aufnahme läuft... ({minutes:02d}:{seconds:02d})"
                ))
            
            # Lade ARL-Token für automatische Anmeldung
            arl_token = None
            try:
                if hasattr(self, 'auth') and self.auth and self.auth.is_logged_in():
                    arl_token = self.auth.arl_token
            except:
                pass
            
            # Hole Track-Info für Metadaten (nur für Deezer)
            track_info = None
            if provider == "deezer":
                try:
                    import re
                    import requests
                    track_id_match = re.search(r'deezer\.com/(?:[a-z]{2}/)?track/(\d+)', url)
                    if track_id_match:
                        track_id = track_id_match.group(1)
                        api_url = f"https://api.deezer.com/track/{track_id}"
                        response = requests.get(api_url, timeout=10)
                        if response.status_code == 200:
                            track_info = response.json()
                except:
                    pass
            
            # Starte Automatisierung (4x Geschwindigkeit für schnellere Aufnahme)
            automation = StreamAutomation(output_path, playback_speed=4.0, arl_token=arl_token)
            
            # Setze Progress-Callback für Fortschrittsanzeige
            automation.progress_callback = update_progress
            
            if automation.record_with_automation(url, provider, track_info=track_info):
                self.root.after(0, lambda: self.music_status_var.set(f"✓ Audio-Aufnahme abgeschlossen: {filename}"))
                self.root.after(0, lambda: self.music_log(f"\n✓ Audio-Aufnahme erfolgreich: {output_path}"))
                self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Audio-Aufnahme abgeschlossen!\n\nDatei: {filename}"))
            else:
                self.root.after(0, lambda: self.music_status_var.set("✗ Audio-Aufnahme fehlgeschlagen"))
                self.root.after(0, lambda: messagebox.showerror("Fehler", "Audio-Aufnahme fehlgeschlagen"))
                
        except ImportError as e:
            self.music_log(f"❌ Fehler: {e}")
            error_msg = str(e)  # Erfasse Fehlermeldung vor Lambda
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Fehler", f"Automatisierung nicht verfügbar:\n{msg}"))
        except Exception as e:
            self.music_log(f"❌ Fehler: {e}")
            import traceback
            self.music_log(traceback.format_exc())
            error_msg = str(e)  # Erfasse Fehlermeldung vor Lambda
            self.root.after(0, lambda msg=error_msg: messagebox.showerror("Fehler", f"Fehler bei Audio-Aufnahme:\n{msg}"))
        finally:
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.music_record_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.music_progress_bar.stop())
    
    def show_audio_setup(self):
        """Zeigt Setup-Dialog für Audio-Aufnahme"""
        setup_window = tk.Toplevel(self.root)
        setup_window.title("Audio-Aufnahme Setup")
        setup_window.transient(self.root)
        setup_window.grab_set()
        self._fit_dialog(setup_window, 880, 680, 640, 480)
        
        main_frame = ttk.Frame(setup_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            main_frame,
            text="Audio-Aufnahme Setup",
            font=("Arial", 14, "bold")
        ).pack(pady=(0, 10))
        
        info_text = (
            "Dieses Setup prüft und installiert alle benötigten Komponenten\n"
            "für die automatische Audio-Aufnahme von DRM-geschützten Streams.\n\n"
            "⚠️ Nur für privaten Gebrauch!"
        )
        ttk.Label(
            main_frame,
            text=info_text,
            justify=tk.CENTER
        ).pack(pady=10)
        
        # Log-Bereich
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        log_text = scrolledtext.ScrolledText(
            log_frame,
            width=80,
            height=20,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        log_text.pack(fill=tk.BOTH, expand=True)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        def run_setup():
            log_text.config(state=tk.NORMAL)
            log_text.delete(1.0, tk.END)
            log_text.config(state=tk.DISABLED)
            
            # Führe Setup in separatem Thread aus
            def setup_thread():
                try:
                    from setup_audio_recording import AudioRecordingSetup
                    import io
                    import sys
                    
                    setup = AudioRecordingSetup()
                    
                    # Leite Output zu Text-Widget um
                    class TextRedirect:
                        def __init__(self, text_widget, root):
                            self.text_widget = text_widget
                            self.root = root
                            self.buffer = ""
                        
                        def write(self, s):
                            self.buffer += s
                            # Aktualisiere GUI im Hauptthread
                            self.root.after(0, lambda: self._append_log())
                        
                        def flush(self):
                            pass
                        
                        def _append_log(self):
                            if self.buffer:
                                self.text_widget.config(state=tk.NORMAL)
                                self.text_widget.insert(tk.END, self.buffer)
                                self.text_widget.see(tk.END)
                                self.text_widget.config(state=tk.DISABLED)
                                self.buffer = ""
                    
                    text_redirect = TextRedirect(log_text, self.root)
                    
                    from contextlib import redirect_stdout, redirect_stderr
                    
                    with redirect_stdout(text_redirect), redirect_stderr(text_redirect):
                        results = setup.run_full_setup()
                    
                    # Zeige Ergebnis
                    all_ok = all(results.values())
                    if all_ok:
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Setup erfolgreich",
                            "Alle Komponenten sind bereit!\n\nAudio-Aufnahme kann jetzt verwendet werden."
                        ))
                    else:
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Setup unvollständig",
                            "Einige Komponenten fehlen noch.\n\nBitte folgen Sie den Anweisungen im Log."
                        ))
                
                except Exception as e:
                    def show_error():
                        log_text.config(state=tk.NORMAL)
                        log_text.insert(tk.END, f"\n❌ Fehler beim Setup: {e}\n")
                        log_text.config(state=tk.DISABLED)
                        import traceback
                        messagebox.showerror(
                            "Setup-Fehler",
                            f"Fehler beim Setup:\n{e}"
                        )
                    self.root.after(0, show_error)
            
            threading.Thread(target=setup_thread, daemon=True).start()
        
        ttk.Button(
            button_frame,
            text="▶️ Setup starten",
            command=run_setup
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            button_frame,
            text="Schließen",
            command=setup_window.destroy
        ).pack(side=tk.LEFT, padx=5)
    
    def _start_plugin_download(self, url: str, output_dir: Path) -> bool:
        """Gibt den Download an ein Plugin ab, wenn eines die Adresse kennt."""
        try:
            from plugin_loader import plugin_for_url
            plugin = plugin_for_url(url)
        except Exception:
            return False
        if plugin is None:
            return False
        name = getattr(plugin, "name", "Plugin")

        def work():
            try:
                self.log(f"Plugin {name}: {url}")
                ok = bool(plugin.download(url, Path(output_dir)))
                if ok:
                    self.root.after(0, lambda: messagebox.showinfo("Plugin", f"{name} hat den Download abgeschlossen."))
                else:
                    self.root.after(0, lambda: messagebox.showerror("Plugin", f"{name} konnte die Adresse nicht laden."))
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: messagebox.showerror("Plugin", message))

        threading.Thread(target=work, daemon=True).start()
        return True

    def start_music_download(self):
        """Startet den Musik-Download (Deezer oder Spotify)"""
        url = self.music_url_var.get().strip()
        
        # Bereinige URL von doppelten Einträgen
        url = self._clean_url(url)
        
        # Normalisiere ARD Sounds URLs (entfernt /embed/, konvertiert zu Standard-Format)
        url = _normalize_ard_sounds_url(url)
        
        # Aktualisiere das Feld mit der bereinigten URL
        self.music_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine URL ein.")
            return

        self.music_download_path = Path(self.music_path_var.get())
        if self._start_plugin_download(url, self.music_download_path):
            return
        
        # Erkenne URL-Typ
        is_spotify = 'spotify.com' in url.lower()
        is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower() or 'link.deezer.com' in url.lower()
        is_mediathek_audio = _is_music_mediathek_url(url)
        if _is_store_blocked_music_url(url):
            messagebox.showinfo("Store-Version", "Deezer, Spotify und Audible sind in der Store-Version nicht enthalten.")
            return
        
        if not (is_spotify or is_deezer or is_mediathek_audio):
            hinweis = (
                "Bitte geben Sie eine YouTube-Musik- oder Mediatheken-/Hörbuch-URL ein (z. B. ARD Audiothek, BR, NDR, WDR, LibriVox)."
                if _store_edition()
                else "Bitte geben Sie eine gültige Deezer-, Spotify-, YouTube-Musik- oder Mediatheken-/Hörbuch-URL ein (z. B. ARD Audiothek, BR, NDR, WDR, LibriVox)."
            )
            messagebox.showwarning("Ungültige URL", hinweis)
            return
        
        # Pfad aus Eingabefeld übernehmen
        self.music_download_path = Path(self.music_path_var.get())
        
        # Starte Download in separatem Thread
        threading.Thread(
            target=self.music_download_thread,
            args=(url,),
            daemon=True
        ).start()
    
    def add_music_to_queue(self):
        """Fügt einen Musik-Download zur Queue hinzu"""
        url = self.music_url_var.get().strip()
        
        # Bereinige URL von doppelten Einträgen
        url = self._clean_url(url)
        
        # Normalisiere ARD Sounds URLs (entfernt /embed/, konvertiert zu Standard-Format)
        url = _normalize_ard_sounds_url(url)
        
        # Aktualisiere das Feld mit der bereinigten URL
        self.music_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine URL ein.")
            return
        
        # Erkenne URL-Typ
        is_spotify = 'spotify.com' in url.lower()
        is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower() or 'link.deezer.com' in url.lower()
        is_mediathek_audio = _is_music_mediathek_url(url)
        if _is_store_blocked_music_url(url):
            messagebox.showinfo("Store-Version", "Deezer, Spotify und Audible sind in der Store-Version nicht enthalten.")
            return
        
        if not (is_spotify or is_deezer or is_mediathek_audio):
            hinweis = (
                "Bitte geben Sie eine YouTube-Musik- oder Mediatheken-/Hörbuch-URL ein (z. B. ARD Audiothek, BR, NDR, WDR, LibriVox)."
                if _store_edition()
                else "Bitte geben Sie eine gültige Deezer-, Spotify-, YouTube-Musik- oder Mediatheken-/Hörbuch-URL ein (z. B. ARD Audiothek, BR, NDR, WDR, LibriVox)."
            )
            messagebox.showwarning("Ungültige URL", hinweis)
            return
        
        # Füge zur Queue hinzu (keine Duplikate)
        if not hasattr(self, 'music_download_queue'):
            self.music_download_queue = []
        if url in self.music_download_queue:
            messagebox.showinfo("Bereits in Queue", "Diese URL befindet sich bereits in der Queue.")
            return
        
        self.music_download_queue.append(url)
        self.music_log(f"Zur Queue hinzugefügt: {url}")
        self.music_status_var.set(f"Zur Queue hinzugefügt ({len(self.music_download_queue)} Einträge)")
        self._update_music_queue_status()
        messagebox.showinfo("Queue", f"URL zur Queue hinzugefügt.\nAktuelle Queue-Größe: {len(self.music_download_queue)}")
    
    def _update_music_queue_status(self):
        """Aktualisiert das Queue-Status-Label im Musik-Tab."""
        n = len(getattr(self, 'music_download_queue', []))
        if hasattr(self, 'music_queue_status_label'):
            self.music_queue_status_label.config(text=f"📋 Queue: {n} Einträge")
    
    def load_music_urls_from_file(self):
        """Lädt URLs aus einer Textdatei und fügt sie der Musik-Queue hinzu."""
        filename = filedialog.askopenfilename(
            title="URLs aus Datei laden",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if not filename:
            return
        try:
            with open(filename, 'rb') as f:
                raw = f.read()
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                text = raw.decode('latin-1')
            url_pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
            urls = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                # Inline-Kommentare (# ...) ignorieren
                if '#' in line:
                    line = line.split('#')[0].strip()
                    if not line:
                        continue
                for match in url_pattern.finditer(line):
                    url = match.group(0).rstrip('.,;:)')
                    if url not in urls:
                        urls.append(url)
            if urls:
                if not hasattr(self, 'music_download_queue'):
                    self.music_download_queue = []
                existing = set(self.music_download_queue)
                added = 0
                skipped_queue = 0
                skipped_archive = 0
                for u in urls:
                    if _is_store_blocked_music_url(u):
                        continue
                    if u in existing:
                        skipped_queue += 1
                    elif self.settings.get('download_archive_enabled', False) and self._is_in_download_archive(u):
                        skipped_archive += 1
                    else:
                        self.music_download_queue.append(u)
                        existing.add(u)
                        added += 1
                self._update_music_queue_status()
                self.music_log(f"✓ {added} URLs aus Datei zur Queue hinzugefügt." + (f" ({skipped_queue} bereits in Queue)" if skipped_queue else "") + (f", {skipped_archive} bereits im Archiv" if skipped_archive else ""))
                self.music_status_var.set(f"✓ {added} URLs zur Queue hinzugefügt" + (f", {skipped_queue + skipped_archive} übersprungen" if (skipped_queue or skipped_archive) else ""))
                msg = f"{added} URL(s) zur Musik-Queue hinzugefügt."
                if skipped_queue or skipped_archive:
                    msg += f"\n\n{skipped_queue} bereits in der Queue, {skipped_archive} bereits im Download-Archiv."
                messagebox.showinfo("Queue", msg)
            else:
                messagebox.showwarning("Warnung", "Keine URLs in der Datei gefunden.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Laden der Datei: {e}")
    
    def save_music_queue(self):
        """Speichert die aktuelle Musik-Queue in eine Textdatei (eine URL pro Zeile)."""
        queue = getattr(self, 'music_download_queue', [])
        if not queue:
            messagebox.showinfo("Queue speichern", "Die Queue ist leer. Nichts zu speichern.")
            return
        path = filedialog.asksaveasfilename(
            title="Musik-Queue speichern",
            defaultextension=".txt",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for url in queue:
                    f.write(url.strip() + "\n")
            self.music_log(f"✓ Queue mit {len(queue)} Einträgen gespeichert: {path}")
            messagebox.showinfo("Queue gespeichert", f"Queue mit {len(queue)} URL(s) gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Queue konnte nicht gespeichert werden:\n{e}")
    
    def load_music_queue(self):
        """Lädt URLs aus einer gespeicherten Queue-Datei und fügt sie der Musik-Queue hinzu (Duplikate werden übersprungen)."""
        path = filedialog.askopenfilename(
            title="Musik-Queue laden",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, 'rb') as f:
                raw = f.read()
            try:
                text = raw.decode('utf-8')
            except UnicodeDecodeError:
                text = raw.decode('latin-1')
            urls = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#')]
            # Nur gültige URLs (http/https)
            urls = [u for u in urls if u.startswith('http://') or u.startswith('https://')]
            if not urls:
                messagebox.showwarning("Queue laden", "In der Datei wurden keine gültigen URLs gefunden.")
                return
            if not hasattr(self, 'music_download_queue'):
                self.music_download_queue = []
            existing = set(self.music_download_queue)
            added = 0
            for u in urls:
                if u not in existing:
                    self.music_download_queue.append(u)
                    existing.add(u)
                    added += 1
            self._update_music_queue_status()
            skipped = len(urls) - added
            self.music_log(f"✓ Queue geladen: {added} URL(s) hinzugefügt." + (f" ({skipped} bereits in Queue)" if skipped else ""))
            msg = f"{added} URL(s) zur Queue hinzugefügt."
            if skipped:
                msg += f"\n\n{skipped} URL(s) übersprungen (bereits in der Queue)."
            messagebox.showinfo("Queue geladen", msg)
        except Exception as e:
            messagebox.showerror("Fehler", f"Queue konnte nicht geladen werden:\n{e}")
    
    def show_music_queue(self):
        """Zeigt die Musik-Download-Queue (gleiche Anordnung und Buttons wie Video-Queue-Fenster)."""
        if not hasattr(self, 'music_download_queue'):
            self.music_download_queue = []
        
        win = tk.Toplevel(self.root)
        win.title("Musik-Queue")
        win.transient(self.root)
        self._apply_dark_toplevel(win)
        self._fit_dialog(win, 900, 580, 640, 400)
        
        frame = ttk.Frame(win, padding="10", style="Download.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header-Zeile mit Label und Buttons (identisch zu Video-Queue)
        header_frame = ttk.Frame(frame, style="Download.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Musik-Queue:", font=("Arial", 10, "bold"), style="Download.TLabel").pack(side=tk.LEFT)
        
        # Zwei Zeilen Buttons rechts: oben Starten/↑/↓/Entfernen/Löschen/🔄, darunter Speichern/Laden
        right_buttons = ttk.Frame(header_frame, style="Download.TFrame")
        right_buttons.pack(side=tk.RIGHT)
        button_frame = ttk.Frame(right_buttons, style="Download.TFrame")
        button_frame.pack(fill=tk.X, pady=(0, 4))
        save_load_frame = ttk.Frame(right_buttons, style="Download.TFrame")
        save_load_frame.pack(fill=tk.X)
        
        # Treeview (wie Video-Queue)
        columns = ("Nr", "URL")
        queue_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15, style="Download.Treeview")
        queue_tree.heading("Nr", text="Nr.")
        queue_tree.heading("URL", text="URL")
        queue_tree.column("Nr", width=50)
        queue_tree.column("URL", width=580)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=queue_tree.yview)
        queue_tree.configure(yscrollcommand=scrollbar.set)
        
        queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        def refresh_list():
            queue_tree.delete(*queue_tree.get_children())
            q = getattr(self, 'music_download_queue', [])
            for i, u in enumerate(q):
                url_display = u[:100] + "…" if len(u) > 100 else u
                queue_tree.insert("", tk.END, values=(i + 1, url_display))
        
        def remove_selected():
            sel = queue_tree.selection()
            if not sel:
                return
            idx = queue_tree.index(sel[0])
            if 0 <= idx < len(self.music_download_queue):
                self.music_download_queue.pop(idx)
                refresh_list()
                self._update_music_queue_status()
        
        def clear_queue():
            if messagebox.askyesno("Bestätigen", "Queue wirklich löschen?"):
                self.music_download_queue.clear()
                refresh_list()
                self._update_music_queue_status()
        
        def move_up():
            sel = queue_tree.selection()
            if not sel:
                return
            idx = queue_tree.index(sel[0])
            if idx > 0:
                self.music_download_queue[idx], self.music_download_queue[idx - 1] = (
                    self.music_download_queue[idx - 1], self.music_download_queue[idx]
                )
                refresh_list()
                self._update_music_queue_status()
                children = queue_tree.get_children()
                if children:
                    queue_tree.selection_set(children[idx - 1])
        
        def move_down():
            sel = queue_tree.selection()
            if not sel:
                return
            idx = queue_tree.index(sel[0])
            if idx < len(self.music_download_queue) - 1:
                self.music_download_queue[idx], self.music_download_queue[idx + 1] = (
                    self.music_download_queue[idx + 1], self.music_download_queue[idx]
                )
                refresh_list()
                self._update_music_queue_status()
                children = queue_tree.get_children()
                if idx + 1 < len(children):
                    queue_tree.selection_set(children[idx + 1])
        
        def start_queue():
            if not self.music_download_queue:
                messagebox.showwarning("Warnung", "Queue ist leer!")
                return
            if getattr(self, 'music_queue_processing', False):
                messagebox.showwarning("Warnung", "Ein Download läuft bereits.")
                return
            win.destroy()
            self.start_music_queue_download()
        
        def do_load():
            self.load_music_queue()
            refresh_list()
        
        refresh_list()
        
        # Obere Zeile: Starten, ↑, ↓, Entfernen, Löschen, 🔄
        ttk.Button(button_frame, text="▶ Starten", command=start_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↑", command=move_up, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↓", command=move_down, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Entfernen", command=remove_selected, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Löschen", command=clear_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔄", command=refresh_list, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        # Untere Zeile: Speichern & Laden
        ttk.Button(save_load_frame, text="💾 Speichern", command=self.save_music_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(save_load_frame, text="📂 Laden", command=do_load, style="Download.TButton").pack(side=tk.LEFT, padx=2)
    
    def start_music_queue_download(self):
        """Startet den Abarbeitung der Musik-Queue (ein Eintrag nach dem anderen)."""
        queue = getattr(self, 'music_download_queue', [])
        if not queue:
            messagebox.showinfo("Queue", "Die Queue ist leer.")
            return
        self.music_queue_processing = True
        self.music_batch_total = len(queue)
        self.music_batch_success = 0
        self._music_queue_next()

    def _music_batch_record_success(self, count_stat=True):
        """Zählt einen erfolgreichen Musik-Download."""
        if count_stat:
            self._update_statistics(success=True, file_path=None, url="", kind="music")
        if getattr(self, 'music_queue_processing', False):
            self.music_batch_success = getattr(self, 'music_batch_success', 0) + 1

    def _music_queue_next(self):
        """Verarbeitet den nächsten Eintrag der Musik-Queue (auf Hauptthread aufrufen)."""
        if not getattr(self, 'music_queue_processing', False):
            if hasattr(self, 'music_download_button'):
                self.music_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'music_cancel_button'):
                self.music_cancel_button.config(state=tk.DISABLED)
            return
        queue = getattr(self, 'music_download_queue', [])
        if not queue:
            self.music_queue_processing = False
            self.music_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'music_cancel_button'):
                self.music_cancel_button.config(state=tk.DISABLED)
            self._update_music_queue_status()
            self.music_status_var.set("✓ Queue abgearbeitet")
            self.music_log("✓ Alle Queue-Downloads abgeschlossen.")
            total = getattr(self, 'music_batch_total', 0)
            success = getattr(self, 'music_batch_success', 0)
            failed = total - success
            if failed > 0:
                self._show_system_notification("Universal Downloader", f"{failed} Download(s) fehlgeschlagen.")
            else:
                self._show_system_notification("Universal Downloader", "Alle Downloads der Queue sind abgeschlossen.")
            return
        url = queue.pop(0)
        self._update_music_queue_status()
        self.music_download_path = Path(self.music_path_var.get())
        self.music_url_var.set(url)
        threading.Thread(target=self.music_download_thread, args=(url,), daemon=True).start()
    
    def cancel_music_download(self):
        """Bricht den laufenden Musik-Download ab – mit Dialog wie im Video-Downloader (optional Queue leeren)."""
        import time
        episodes_total = getattr(self, 'music_audiothek_episodes_total', 0)
        is_series_download = episodes_total > 1
        queue_count = len(getattr(self, 'music_download_queue', []))
        cancel_all_queued = False
        choice_ok = False

        if is_series_download:
            # Mehrere Audiothek-Folgen: Dialog wie bei Video „Aktuelle Folge“ / „Alle Folgen“ / „Abbrechen“
            cancel_dialog = tk.Toplevel(self.root)
            cancel_dialog.title("Download abbrechen")
            cancel_dialog.geometry("400x150")
            cancel_dialog.transient(self.root)
            cancel_dialog.grab_set()
            cancel_dialog.update_idletasks()
            x = (cancel_dialog.winfo_screenwidth() // 2) - (cancel_dialog.winfo_width() // 2)
            y = (cancel_dialog.winfo_screenheight() // 2) - (cancel_dialog.winfo_height() // 2)
            cancel_dialog.geometry(f"+{x}+{y}")
            choice = None

            def cancel_current():
                nonlocal choice
                choice = "current"
                cancel_dialog.destroy()

            def cancel_all():
                nonlocal choice
                choice = "all"
                cancel_dialog.destroy()

            def cancel_nothing():
                nonlocal choice
                choice = None
                cancel_dialog.destroy()

            ttk.Label(cancel_dialog, text="Was möchten Sie abbrechen?", font=("Arial", 11, "bold")).pack(pady=10)
            ttk.Label(cancel_dialog, text=f"Es werden {episodes_total} Folgen heruntergeladen.").pack(pady=5)
            btn_f = ttk.Frame(cancel_dialog)
            btn_f.pack(pady=15)
            ttk.Button(btn_f, text="Aktuelle Folge abbrechen", command=cancel_current, width=25).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_f, text="Alle Folgen abbrechen", command=cancel_all, width=25).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_f, text="Abbrechen", command=cancel_nothing).pack(side=tk.LEFT, padx=5)
            cancel_dialog.protocol("WM_DELETE_WINDOW", cancel_nothing)
            cancel_dialog.wait_window()

            if choice is None:
                return
            choice_ok = True
            if choice == "current":
                self.music_download_cancel_current_only = True
                self.music_download_cancelled = False
                self.music_log("⚠ Nur aktuelle Folge wird abgebrochen…")
                self.music_status_var.set("Aktuelle Folge wird abgebrochen…")
            else:
                self.music_download_cancelled = True
                self.music_download_cancel_current_only = False
                self.music_log("⚠ Alle Folgen werden abgebrochen…")
                self.music_status_var.set("Download wird abgebrochen…")
        elif queue_count > 0:
            # Einzeldownload mit Einträgen in der Queue: „Nein“ / „Ja“ / „Ja, alle“
            cancel_dialog = tk.Toplevel(self.root)
            cancel_dialog.title("Download abbrechen")
            cancel_dialog.geometry("420x140")
            cancel_dialog.transient(self.root)
            cancel_dialog.grab_set()
            choice = None

            def on_ja():
                nonlocal choice
                choice = "ja"
                cancel_dialog.destroy()

            def on_ja_alle():
                nonlocal choice, cancel_all_queued
                choice = "ja"
                cancel_all_queued = True
                cancel_dialog.destroy()

            def on_nein():
                nonlocal choice
                choice = "nein"
                cancel_dialog.destroy()

            ttk.Label(cancel_dialog, text="Möchten Sie den laufenden Download wirklich abbrechen?",
                      wraplength=380).pack(pady=(15, 8))
            ttk.Label(cancel_dialog, text=f"Noch {queue_count} Download(s) in der Warteschlange.",
                      font=("Arial", 9)).pack(pady=(0, 12))
            btn_f = ttk.Frame(cancel_dialog)
            btn_f.pack(pady=5)
            ttk.Button(btn_f, text="Nein", command=on_nein, width=10).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_f, text="Ja", command=on_ja, width=10).pack(side=tk.LEFT, padx=4)
            ttk.Button(btn_f, text="Ja, alle", command=on_ja_alle, width=10).pack(side=tk.LEFT, padx=4)
            cancel_dialog.protocol("WM_DELETE_WINDOW", on_nein)
            cancel_dialog.wait_window()

            if choice != "ja":
                return
            choice_ok = True
            self.music_download_cancelled = True
            self.music_download_cancel_current_only = False
            if cancel_all_queued and queue_count > 0:
                self.music_download_queue.clear()
                self.music_log(f"⚠ Warteschlange geleert ({queue_count} Einträge).")
                self._update_music_queue_status()
            self.music_log("⚠ Download wird abgebrochen…")
            self.music_status_var.set("Download wird abgebrochen…")
        else:
            # Einzeldownload ohne Queue: einfache Ja/Nein-Abfrage
            if not messagebox.askyesno("Download abbrechen", "Möchten Sie den laufenden Download wirklich abbrechen?"):
                return
            choice_ok = True
            self.music_download_cancelled = True
            self.music_download_cancel_current_only = False
            self.music_log("⚠ Download wird abgebrochen…")
            self.music_status_var.set("Download wird abgebrochen…")

        if not choice_ok:
            return

        # Prozess beenden (Audiothek nutzt video_downloader → video_download_process)
        if getattr(self, 'video_download_process', None):
            try:
                import os
                import signal
                import sys
                proc = self.video_download_process
                if sys.platform != 'win32':
                    try:
                        pgid = os.getpgid(proc.pid)
                        os.killpg(pgid, signal.SIGTERM)
                        time.sleep(0.3)
                        if proc.poll() is None:
                            os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        try:
                            proc.terminate()
                            time.sleep(0.3)
                            if proc.poll() is None:
                                proc.kill()
                        except Exception:
                            pass
                else:
                    proc.terminate()
                    time.sleep(0.3)
                    if proc.poll() is None:
                        proc.kill()
            except Exception as e:
                self.music_log(f"⚠ Fehler beim Abbrechen: {e}")
        self.music_download_button.config(state=tk.NORMAL)
        if hasattr(self, 'music_cancel_button'):
            self.music_cancel_button.config(state=tk.DISABLED)
        self.music_progress_bar.stop()
        self.music_status_var.set("Download abgebrochen")
        self.music_progress_var.set(0)
    
    def music_download_thread(self, url: str):
        """Download-Thread für Musik (Deezer, Spotify oder Mediatheken/Hörbücher wie ARD Audiothek, BR, NDR, LibriVox, Hörspielprojekt)"""
        try:
            if _is_store_blocked_music_url(url):
                self.music_log("Übersprungen: Deezer, Spotify und Audible sind in der Store-Version nicht enthalten.")
                self.root.after(0, self._music_queue_next)
                return
            # Download-Archiv: Bereits heruntergeladene überspringen
            if self._is_in_download_archive(url):
                self.music_log(f"Übersprungen (bereits im Download-Archiv): {url[:60]}…")
                self.root.after(0, lambda: self._music_batch_record_success(count_stat=False))
                self.root.after(0, self._music_queue_next)
                return
            
            # Erkenne URL-Typ
            is_spotify = 'spotify.com' in url.lower()
            is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower()
            is_mediathek_audio = _is_music_mediathek_url(url)
            
            self.root.after(0, lambda: self.music_status_var.set("Download läuft..."))
            self.root.after(0, lambda: self.music_download_button.config(state=tk.DISABLED))
            if hasattr(self, 'music_cancel_button'):
                self.root.after(0, lambda: self.music_cancel_button.config(state=tk.NORMAL))
            if not is_mediathek_audio:
                self.root.after(0, lambda: self.music_progress_bar.config(mode='indeterminate'))
                self.root.after(0, lambda: self.music_progress_bar.start())
            
            self.music_log(f"Starte Download: {url}")
            
            if is_mediathek_audio:
                # Normalisiere ARD Sounds URLs (entfernt /embed/, konvertiert zu Standard-Format)
                url = _normalize_ard_sounds_url(url)
                url_lower = url.lower()
                # YouTube Music: Cookies aus Browser verwenden (kann bei Radio/Mix-Playlists helfen, wenn eingeloggt)
                cookies_browser = None
                if "music.youtube.com" in url_lower:
                    import sys
                    cookies_browser = 'safari' if sys.platform == 'darwin' else 'chrome'
                # Spezieller Fall: hoerspielprojekt.de – ZIP-Download, Ordner Hoerspielprojekt/Serie/Folge
                if "hoerspielprojekt.de" in url_lower:
                    # Serien-Seite (/artists/ oder /serien/): Folgen-Liste parsen, Dialog, dann Downloads
                    if "/artists/" in url_lower or "/serien/" in url_lower:
                        try:
                            parsed = self._parse_hoerspielprojekt_series_page(url)
                            series_name = parsed.get("series_name", "Serie")
                            episodes = parsed.get("episodes", [])
                            if not episodes:
                                self.root.after(0, lambda: self.music_status_var.set("✗ Keine Folgen gefunden"))
                                self.root.after(0, lambda: self.music_log("\n✗ Auf der Serien-Seite wurden keine Folgen-Links gefunden."))
                                self.root.after(0, lambda: messagebox.showwarning("Hörspielprojekt", "Keine Folgen auf dieser Seite gefunden."))
                                return
                            self._audiothek_series_dialog_pending = True
                            self.root.after(0, lambda: self._hoerspielprojekt_series_dialog_and_download(series_name, episodes))
                        except Exception as e:
                            self.root.after(0, lambda: self.music_status_var.set("✗ Fehler"))
                            self.root.after(0, lambda: self.music_log(f"\n✗ Fehler beim Parsen der Serien-Seite: {e}"))
                            self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))
                        return
                    # Einzel-Hörspiel (/music/...): in Hoerspielprojekt/<Titel>/ entpacken
                    self.root.after(0, lambda: self.music_progress_bar.config(mode='determinate', maximum=100))
                    ok, err = self._download_hoerspielprojekt(url)
                    if ok:
                        self.root.after(0, lambda: self.music_status_var.set("✓ Download abgeschlossen (Hörspielprojekt)"))
                        self.root.after(0, lambda: self.music_log("\n✓ Download erfolgreich (Hörspielprojekt – ZIP entpackt)"))
                        self.root.after(0, lambda: messagebox.showinfo("Erfolg", "Download abgeschlossen!\nZIP entpackt (Hörspielprojekt)."))
                    else:
                        self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                        self.root.after(0, lambda: self.music_log(f"\n✗ Fehler (Hörspielprojekt): {err}"))
                        self.root.after(0, lambda: messagebox.showerror("Fehler", err or "Download fehlgeschlagen."))
                    return

                # Standard: Mediatheken / Hörbücher: Einzelfolge oder Serie (yt-dlp, MP3)
                if not hasattr(self, 'video_downloader') or self.video_downloader is None:
                    self.video_downloader = VideoDownloader(
                        download_path=str(self.music_download_path),
                        quality="best",
                        output_format="mp3",
                        gui_instance=self
                    )
                if self.video_downloader.is_series_or_season(url):
                    reading = "Mix wird gelesen…" if "list=rd" in url.lower() else "Playlist wird gelesen…"
                    self.root.after(0, lambda t=reading: self.music_status_var.set(t))
                    self.root.after(0, lambda: self.music_progress_bar.config(mode='indeterminate'))
                    self.root.after(0, lambda: self.music_progress_bar.start())
                    series_data = self.video_downloader.get_series_episodes(url)
                    if series_data and series_data.get('seasons'):
                        if "music.youtube.com" in url.lower():
                            series_data["playlist_kind"] = "music"
                        elif "youtube.com" in url.lower() or "youtu.be" in url.lower():
                            series_data["playlist_kind"] = "video"
                        self._audiothek_series_dialog_pending = True
                        self.root.after(0, lambda data=series_data: self._audiothek_series_dialog_and_download(data))
                        return
                # Einzelfolge oder keine Serien-Daten
                _music_log_last_p = [None]
                _music_log_last_t = [None]
                self.root.after(0, lambda: self.music_status_var.set("Verbindung wird aufgebaut…"))
                self.root.after(0, lambda: self.music_progress_bar.config(mode='indeterminate'))
                self.root.after(0, lambda: self.music_progress_bar.start())
                def progress_cb(percent, msg):
                    _p, _m = percent, (msg or "Download läuft...")
                    def _apply(p=_p, m=_m):
                        if p and p > 0:
                            self.music_progress_bar.stop()
                            self.music_progress_bar.config(mode='determinate', maximum=100)
                            self.music_progress_var.set(min(100.0, p))
                        if m:
                            self.music_status_var.set(m)
                    self.root.after(0, _apply)
                    if msg and ('at' in msg or 'ETA' in msg) and percent < 100:
                        import time
                        now = time.time()
                        if _music_log_last_p[0] is None or percent - _music_log_last_p[0] >= 10 or (_music_log_last_t[0] and now - _music_log_last_t[0] >= 5):
                            _music_log_last_p[0] = percent
                            _music_log_last_t[0] = now
                            speed_match = re.search(r'at\s+([\d.]+)\s*([KMGT]?i?B/s)', msg, re.IGNORECASE)
                            eta_match = re.search(r'ETA\s+(\d+:\d+)', msg)
                            part = f"  → {percent:.1f}%"
                            if speed_match:
                                part += f" - {speed_match.group(1)}{speed_match.group(2)}"
                            if eta_match:
                                part += f" - ETA: {eta_match.group(1)}"
                            self.root.after(0, lambda: self.music_log(part))
                success, file_path, error = self.video_downloader.download_video(
                    url,
                    output_dir=self.music_download_path,
                    output_format='mp3',
                    progress_callback=progress_cb,
                    download_description=False,
                    download_thumbnail=True,
                    cookies_from_browser=cookies_browser,
                )
                if success:
                    self.root.after(0, self._music_batch_record_success)
                    self.root.after(0, lambda: self._add_to_download_archive(url))
                    self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {file_path.name if file_path else 'Audio'}"))
                    self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich: {file_path.name if file_path else 'Audio'}"))
                    def _show_music_success():
                        fp = file_path
                        name = fp.name if fp else "Audio"
                        if fp and fp.exists():
                            if self.settings.get('auto_open_folder', False):
                                self._open_folder(fp)
                            if self.settings.get('play_after_download', False):
                                self._open_file_with_default_app(fp)
                            self._show_system_notification("Download abgeschlossen", f"{name} — {fp.parent}")
                        else:
                            self._show_system_notification("Download abgeschlossen", name)
                    self.root.after(0, _show_music_success)
                else:
                    self._update_statistics(success=False, file_path=None, url=url, kind="music", error=error)
                    self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                    self.root.after(0, lambda: self.music_log(f"\n✗ Fehler: {error}"))
                    err_lower = (error or "").lower()
                    if "music.youtube" in url_lower and "list=rd" in url_lower and ("playlist does not exist" in err_lower or "the playlist does not exist" in err_lower):
                        self.root.after(0, lambda: messagebox.showwarning(
                            "YouTube Music – Radio/Mix-Playlist",
                            "Diese URL ist eine YouTube-Music-Radio- oder Mix-Playlist („list=RD...“).\n\n"
                            "Solche dynamischen Playlists werden von YouTube nicht wie normale Playlists angeboten. Auch mit Browser-Cookies ist ein Download oft nicht möglich.\n\n"
                            "Bitte verwenden Sie eine normale Playlist oder laden Sie einzelne Titel über die jeweilige Video-URL."
                        ))
                    elif "music.youtube" in url_lower and ("failed to resolve album" in err_lower or "resolve album to playlist" in err_lower):
                        self.root.after(0, lambda: messagebox.showwarning(
                            "YouTube Music – Album-URL",
                            "Diese YouTube-Music-URL (Album/Browse) wird von yt-dlp derzeit nicht zuverlässig unterstützt.\n\n"
                            "• Bitte yt-dlp aktualisieren: pip install -U yt-dlp\n"
                            "• Alternativ: Album im Browser öffnen, Playlist-Link („Alle Titel“) kopieren und diese Playlist-URL hier einfügen.\n"
                            "• Oder einzelne Titel über die jeweilige youtube.com/watch?v=...-URL laden."
                        ))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Fehler", error or "Download fehlgeschlagen."))
                return
            
            if is_spotify:
                # Spotify-Download
                if not self.spotify_downloader:
                    self.spotify_downloader = SpotifyDownloader(
                        download_path=str(self.music_download_path)
                    )
                
                # Redirect log output
                original_log = self.spotify_downloader.log
                def logged_log(message, level="INFO"):
                    original_log(message, level)
                    self.root.after(0, lambda: self.music_log(f"[{level}] {message}"))
                self.spotify_downloader.log = logged_log
                
                # Starte Download
                count = self.spotify_downloader.download_from_url(url, str(self.music_download_path))
                
                if count > 0:
                    self.root.after(0, self._music_batch_record_success)
                    self.root.after(0, lambda u=url: self._add_to_download_archive(u))
                    self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                    self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                    self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                else:
                    self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                    self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
            
            elif is_deezer:
                # Deezer-Download (Auth aus Login-Dialog oder ARL aus Account-Verwaltung)
                if not self.downloader:
                    arl = (self.auth.arl_token if self.auth and self.auth.is_logged_in() else None) or self._get_deezer_arl_from_accounts()
                    self.downloader = DeezerDownloader(
                        download_path=self.music_download_path,
                        arl_token=arl,
                        auth=self.auth
                    )
                
                # Redirect log output
                original_log = self.downloader.log
                def logged_log(message, level="INFO"):
                    original_log(message, level)
                    self.root.after(0, lambda: self.music_log(f"[{level}] {message}"))
                self.downloader.log = logged_log
                
                # Prüfe ob es Artist oder Playlist ist - zeige Auswahl-Dialog
                # WICHTIG: Prüfe zuerst, ob es ein Share-Link ist und löse ihn auf
                resolved_url = url
                if 'link.deezer.com' in url.lower():
                    try:
                        response = self.downloader.session.get(url, allow_redirects=True, timeout=10)
                        resolved_url = response.url
                        self.music_log(f"Share-Link aufgelöst: {resolved_url}")
                    except Exception as e:
                        self.music_log(f"Fehler beim Auflösen des Share-Links: {e}")
                
                # Prüfe ob es ein Artist ist (nach Auflösung des Share-Links)
                if '/artist/' in resolved_url or 'artist-' in resolved_url:
                    artist_id = self.downloader.extract_id_from_url(resolved_url)
                    if artist_id:
                        # Hole Artist-Info und Alben
                        artist_info = self.downloader.get_artist_info(artist_id)
                        if artist_info:
                            artist_name = artist_info.get('name', 'Unbekannt')
                            
                            # Hole Alben
                            try:
                                self.root.after(0, lambda: self.music_status_var.set("Lade Alben..."))
                                albums = self.downloader.get_artist_albums(artist_id, limit=50)
                                
                                if albums:
                                    # Prüfe YouTube-Verfügbarkeit für jedes Album
                                    self.root.after(0, lambda: self.music_status_var.set("Prüfe YouTube-Verfügbarkeit..."))
                                    self.music_log(f"Prüfe YouTube-Verfügbarkeit für {len(albums)} Album(s)...")
                                    
                                    albums_with_availability = []
                                    for i, album in enumerate(albums, 1):
                                        self.music_log(f"[{i}/{len(albums)}] Prüfe: {album.get('title', 'Unbekannt')}...")
                                        youtube_available = self.downloader.check_album_youtube_availability(album)
                                        album['youtube_available'] = youtube_available
                                        albums_with_availability.append(album)
                                    
                                    # Zeige Album-Auswahl-Dialog
                                    selected_albums = self.show_album_selection_dialog(
                                        title=f"💿 Artist: {artist_name}",
                                        albums=albums_with_availability
                                    )
                                    
                                    if selected_albums:
                                        # Prüfe ob es Hörbücher sind (z.B. "Kapitel" im Titel)
                                        is_audiobook = any(
                                            'kapitel' in album.get('title', '').lower() or 
                                            'hörbuch' in album.get('title', '').lower() or
                                            album.get('nb_tracks', 0) > 20  # Viele Tracks = wahrscheinlich Hörbuch
                                            for album in selected_albums
                                        )
                                        
                                        if is_audiobook:
                                            # Zeige Option zur Multi-Anbieter-Suche
                                            self.root.after(0, lambda: self._show_audiobook_search_option(selected_albums, artist_name))
                                        
                                        # Lade ausgewählte Alben herunter
                                        total_count = 0
                                        for album in selected_albums:
                                            album_id = album.get('id')
                                            if album_id:
                                                self.music_log(f"\nLade Album: {album.get('title', 'Unbekannt')}")
                                                count = self.downloader.download_album(album_id)
                                                total_count += count
                                        
                                        if total_count > 0:
                                            self.root.after(0, self._music_batch_record_success)
                                            self.root.after(0, lambda u=url: self._add_to_download_archive(u))
                                            self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {total_count} Track(s)"))
                                            self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {total_count} Track(s) aus {len(selected_albums)} Album(s)"))
                                            self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{total_count} Track(s) aus {len(selected_albums)} Album(s) heruntergeladen."))
                                        else:
                                            self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                                            self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
                                    else:
                                        self.root.after(0, lambda: self.music_status_var.set("Download abgebrochen"))
                                else:
                                    # Fallback: Versuche Top-Tracks
                                    self.root.after(0, lambda: self.music_status_var.set("Keine Alben gefunden, versuche Top-Tracks..."))
                                    tracks_url = f"{self.downloader.api_base}/artist/{artist_id}/top?limit=100"
                                    response = self.downloader.session.get(tracks_url, timeout=10)
                                    response.raise_for_status()
                                    data = response.json()
                                    tracks = data.get('data', [])
                                    
                                    if tracks:
                                        # Zeige Auswahl-Dialog
                                        selected_tracks = self.show_track_selection_dialog(
                                            title=f"🎵 Artist: {artist_name}",
                                            tracks=tracks,
                                            is_artist=True
                                        )
                                        
                                        if selected_tracks:
                                            # Lade ausgewählte Tracks herunter
                                            count = self.download_selected_tracks(
                                                selected_tracks,
                                                context_type='artist',
                                                context_name=artist_name,
                                                artist_name=artist_name
                                            )
                                            if count > 0:
                                                self.root.after(0, self._music_batch_record_success)
                                                self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                                                self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                                                self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                                            else:
                                                self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                                                self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
                                        else:
                                            self.root.after(0, lambda: self.music_status_var.set("Download abgebrochen"))
                                    else:
                                        self.root.after(0, lambda: messagebox.showwarning("Warnung", "Keine Alben oder Tracks für diesen Artist gefunden."))
                            except Exception as e:
                                self.music_log(f"Fehler beim Abrufen der Artist-Alben: {e}")
                                self.root.after(0, lambda: messagebox.showerror("Fehler", f"Fehler beim Abrufen der Alben: {e}"))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("Fehler", "Konnte Artist-Informationen nicht abrufen."))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Ungültige Artist-URL."))
                
                elif '/playlist/' in url:
                    playlist_id = self.downloader.extract_id_from_url(url)
                    if playlist_id:
                        # Hole Playlist-Info und Tracks
                        playlist_info = self.downloader.get_playlist_info(playlist_id)
                        if playlist_info:
                            tracks = self.downloader.get_playlist_tracks(playlist_id)
                            
                            if tracks:
                                # Zeige Auswahl-Dialog
                                selected_tracks = self.show_track_selection_dialog(
                                    title=f"📋 Playlist: {playlist_info.get('title', 'Unbekannt')}",
                                    tracks=tracks,
                                    is_artist=False
                                )
                                
                                if selected_tracks:
                                    # Lade ausgewählte Tracks herunter
                                    playlist_name = playlist_info.get('title', 'Unbekannt')
                                    # Extrahiere Künstlername aus dem ersten Track oder Playlist-Creator
                                    first_track = tracks[0] if tracks else {}
                                    artist_name = first_track.get('artist', {}).get('name', 'Unbekannt') if isinstance(first_track.get('artist'), dict) else 'Unbekannt'
                                    count = self.download_selected_tracks(
                                        selected_tracks,
                                        context_type='playlist',
                                        context_name=playlist_name,
                                        artist_name=artist_name
                                    )
                                    if count > 0:
                                        self.root.after(0, self._music_batch_record_success)
                                        self.root.after(0, lambda u=url: self._add_to_download_archive(u))
                                        self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                                        self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                                        self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                                    else:
                                        self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
                                else:
                                    self.root.after(0, lambda: self.music_status_var.set("Download abgebrochen"))
                            else:
                                self.root.after(0, lambda: messagebox.showwarning("Warnung", "Keine Tracks in dieser Playlist gefunden."))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("Fehler", "Konnte Playlist-Informationen nicht abrufen."))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Ungültige Playlist-URL."))
                
                elif '/album/' in url:
                    album_id = self.downloader.extract_id_from_url(url)
                    if album_id:
                        # Hole Album-Info und Tracks
                        album_info = self.downloader.get_album_info(album_id)
                        if album_info:
                            # Hole Tracks aus Album-Info
                            tracks_data = album_info.get('tracks', {})
                            tracks = tracks_data.get('data', []) if isinstance(tracks_data, dict) else []
                            
                            if tracks:
                                # Zeige Auswahl-Dialog
                                selected_tracks = self.show_track_selection_dialog(
                                    title=f"💿 Album: {album_info.get('title', 'Unbekannt')} - {album_info.get('artist', {}).get('name', 'Unbekannt') if isinstance(album_info.get('artist'), dict) else 'Unbekannt'}",
                                    tracks=tracks,
                                    is_artist=False
                                )
                                
                                if selected_tracks:
                                    # Lade ausgewählte Tracks herunter
                                    album_name = album_info.get('title', 'Unbekannt')
                                    artist_name = album_info.get('artist', {}).get('name', 'Unbekannt') if isinstance(album_info.get('artist'), dict) else 'Unbekannt'
                                    count = self.download_selected_tracks(
                                        selected_tracks,
                                        context_type='album',
                                        context_name=album_name,
                                        artist_name=artist_name
                                    )
                                    if count > 0:
                                        self.root.after(0, self._music_batch_record_success)
                                        self.root.after(0, lambda u=url: self._add_to_download_archive(u))
                                        self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                                        self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                                        self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                                    else:
                                        self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
                                else:
                                    self.root.after(0, lambda: self.music_status_var.set("Download abgebrochen"))
                            else:
                                self.root.after(0, lambda: messagebox.showwarning("Warnung", "Keine Tracks in diesem Album gefunden."))
                        else:
                            self.root.after(0, lambda: messagebox.showerror("Fehler", "Konnte Album-Informationen nicht abrufen."))
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Ungültige Album-URL."))
                
                else:
                    # Normale Downloads (nur Track) ohne Auswahl
                    count = self.downloader.download_from_url(url)
                    
                    if count > 0:
                        self.root.after(0, self._music_batch_record_success)
                        self.root.after(0, lambda u=url: self._add_to_download_archive(u))
                        self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                        self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                        self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                    else:
                        self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                        self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
        
        except Exception as e:
            error_msg = f"Fehler beim Download: {e}"
            self.music_log(f"ERROR: {error_msg}")
            self.root.after(0, lambda: self.music_status_var.set("✗ Fehler"))
            self.root.after(0, lambda: messagebox.showerror("Fehler", error_msg))
        
        finally:
            if not getattr(self, '_audiothek_series_dialog_pending', False):
                self.root.after(0, lambda: self.music_progress_bar.stop())
                if getattr(self, 'music_queue_processing', False):
                    self.root.after(0, self._music_queue_next)
                else:
                    self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
                    if hasattr(self, 'music_cancel_button'):
                        self.root.after(0, lambda: self.music_cancel_button.config(state=tk.DISABLED))
    
    def _audiothek_series_dialog_and_download(self, series_data):
        """Zeigt Serien-Auswahl für ARD Audiothek und startet Download der gewählten Folgen (Hauptthread)."""
        self._audiothek_series_dialog_pending = False
        self.root.after(0, lambda: self.music_progress_bar.stop())
        try:
            kind = series_data.get("playlist_kind")
            selected = self.show_series_selection_dialog(
                series_data,
                is_youtube_playlist=kind in ("music", "video"),
            )
            if not selected:
                self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
                self.music_log("Keine Einträge ausgewählt.")
                return
            label = "Lieder" if kind == "music" else "Folgen"
            self.music_log(f"{len(selected)} {label} ausgewählt.")
            self.music_status_var.set("Verbindung wird aufgebaut…")
            self.music_progress_bar.config(mode='indeterminate')
            self.music_progress_bar.start()
            self.music_audiothek_episodes_total = len(selected)
            thread = threading.Thread(target=self._audiothek_episodes_download_thread, args=(selected,))
            thread.daemon = True
            thread.start()
        except Exception as e:
            self.music_log(f"Fehler bei Audiothek-Serien-Dialog: {e}")
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
    
    def _audiothek_episodes_download_thread(self, selected_episodes, silent=False):
        """Lädt ausgewählte ARD-Audiothek-Folgen als MP3 (Worker-Thread)."""
        import time
        try:
            total = len(selected_episodes)
            for i, ep in enumerate(selected_episodes, 1):
                if getattr(self, 'music_download_cancelled', False):
                    break
                ep_url = ep.get('url')
                if not ep_url:
                    continue
                # YouTube/YouTube Music: Pause zwischen Downloads, um Rate-Limit zu vermeiden
                if i > 1 and ('youtube.com' in ep_url or 'youtu.be' in ep_url):
                    self.music_log("  Pause 2 s (YouTube Rate-Limit-Schutz)…")
                    time.sleep(2)
                # Vollständige URL für Audiothek/Sounds: URN/relative URLs zu vollständiger URL machen
                if not (ep_url.startswith('http://') or ep_url.startswith('https://')):
                    ep_url = ep_url.strip().lstrip('/')
                    # Prüfe ob es eine ARD Sounds URL ist
                    if 'ardsounds.de' in (ep.get('series_url', '') or '').lower() or 'ardsounds.de' in (ep.get('url', '') or '').lower():
                        # ARD Sounds: URL-Format könnte anders sein, yt-dlp sollte es handhaben
                        ep_url = ep_url if ep_url.startswith('http') else f"https://www.ardsounds.de/{ep_url}"
                    else:
                        # ARD Audiothek: Standard-Format
                        ep_url = f"https://www.ardaudiothek.de/episode/{ep_url}" if not ep_url.startswith('http') else ep_url
                else:
                    # Normalisiere vollständige URLs (z.B. /embed/episode/ entfernen)
                    ep_url = _normalize_ard_sounds_url(ep_url)
                title = ep.get('title', f'Folge {i}')
                self.root.after(0, lambda t=title, cur=i, tot=total: self.music_status_var.set(f"Download läuft ({cur}/{tot}): {t[:40]}..."))
                self.root.after(0, lambda: self.music_progress_bar.config(mode='indeterminate'))
                self.root.after(0, lambda: self.music_progress_bar.start())
                def progress_cb(percent, msg):
                    _p, _m = percent, (msg or "Download läuft...")
                    def _apply(p=_p, m=_m, c=i, tot=total):
                        if p and p > 0:
                            self.music_progress_bar.stop()
                            self.music_progress_bar.config(mode='determinate', maximum=100)
                            self.music_progress_var.set(min(100.0, p))
                        self.music_status_var.set(f"({c}/{tot}) {m}")
                    self.root.after(0, _apply)
                # Metadaten aus Episoden-Auswahl für Serienordner und Dateinamen nutzen
                ep_video_info = {
                    'title': ep.get('title') or f"Folge {ep.get('episode_number') or i}",
                    'series': ep.get('series'),
                    'season_number': ep.get('season_number'),
                    'episode_number': ep.get('episode_number'),
                    'webpage_url': ep_url,  # damit Ardaudiothek-Ordner erkannt wird
                    'broadcast_date': ep.get('broadcast_date') or '',
                    'upload_date': ep.get('upload_date') or '',
                }
                max_attempts = 2
                success, file_path, error = False, None, ""
                for attempt in range(max_attempts):
                    success, file_path, error = self.video_downloader.download_video(
                        ep_url,
                        output_dir=self.music_download_path,
                        output_format='mp3',
                        progress_callback=progress_cb,
                        download_description=False,
                        download_thumbnail=True,
                        video_info=ep_video_info,
                        is_series=True,
                        series_name=ep.get('series'),
                        season_number=ep.get('season_number'),
                        playlist_index=ep.get('playlist_index') or ep.get('episode_number'),
                    )
                    if success:
                        break
                    # Bei HTTP 500 / Internal Server Error: einmal wiederholen nach kurzer Pause
                    if attempt < max_attempts - 1 and ("500" in (error or "") or "Internal Server Error" in (error or "")):
                        self.music_log(f"  → Wiederholung ({attempt + 2}/{max_attempts}) in 3 s…")
                        time.sleep(3)
                if success:
                    self.music_log(f"✓ {i}/{total}: {file_path.name if file_path else title}")
                    self._update_statistics(success=True, file_path=file_path, url=ep_url, kind="music")
                    self._series_watch_mark_downloaded(ep_url, episode_id=ep.get('id'))
                else:
                    self.music_log(f"✗ {i}/{total}: {error}")
                    self._update_statistics(success=False, file_path=None, url=ep_url, kind="music", error=error)
                if getattr(self, 'music_download_cancel_current_only', False):
                    self.music_log("⚠ Nur aktuelle Folge abgebrochen.")
                    break
            self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {total} Folge(n)"))
            self.root.after(0, lambda: self.music_log(f"\n✓ ARD Audiothek: {total} Folge(n) verarbeitet."))
            if not silent:
                self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{total} Folge(n) verarbeitet. Details im Log."))
        except Exception as e:
            self.music_log(f"Fehler: {e}")
            self.root.after(0, lambda: self.music_status_var.set("✗ Fehler"))
            if not silent:
                self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))
        finally:
            self.root.after(0, lambda: setattr(self, 'music_audiothek_episodes_total', 0))
            self.root.after(0, lambda: self.music_progress_bar.stop())
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
            if hasattr(self, 'music_cancel_button'):
                self.root.after(0, lambda: self.music_cancel_button.config(state=tk.DISABLED))
    
    def browse_download_path(self):
        """Öffnet einen Dialog zur Auswahl des Download-Pfads (Legacy für Deezer)"""
        path = filedialog.askdirectory(initialdir=str(self.music_download_path))
        if path:
            self.music_download_path = Path(path)
            if hasattr(self, 'path_var'):
                self.path_var.set(str(self.music_download_path))
            if hasattr(self, 'music_path_var'):
                self.music_path_var.set(str(self.music_download_path))
            self.settings['default_music_path'] = str(self.music_download_path)
            self._save_settings()
    
    def update_download_path(self):
        """Aktualisiert den Download-Pfad in der UI (Legacy)"""
        if hasattr(self, 'path_var'):
            self.path_var.set(str(self.music_download_path))
        if hasattr(self, 'music_path_var'):
            self.music_path_var.set(str(self.music_download_path))
        if self.downloader:
            self.downloader.download_path = self.music_download_path
    
    def update_auth_status(self):
        """Aktualisiert den Authentifizierungs-Status in der UI"""
        if self.auth and self.auth.is_logged_in():
            sub_info = self.auth.get_subscription_info()
            status_text = f"✓ Angemeldet | Abo: {sub_info['type']} | Qualität: {sub_info['quality']}"
            if sub_info['profiles'] > 0:
                current = sub_info['current_profile']
                if current:
                    status_text += f" | Profil: {current.get('name', 'Hauptprofil')}"
            
            self.auth_status_var.set(status_text)
            self.login_button.config(state=tk.DISABLED)
            self.logout_button.config(state=tk.NORMAL)
        else:
            self.auth_status_var.set("Nicht angemeldet")
            self.login_button.config(state=tk.NORMAL)
            self.logout_button.config(state=tk.DISABLED)
    
    def show_login_dialog(self):
        """Zeigt Anmelde-Dialog"""
        if not interactive_login:
            messagebox.showinfo(
                "Info",
                "Authentifizierungsmodul nicht verfügbar.\n"
                "Bitte verwenden Sie die Kommandozeile für die Anmeldung."
            )
            return
        
        # Öffne neues Fenster für Login
        login_window = tk.Toplevel(self.root)
        login_window.title("Deezer Anmeldung")
        login_window.transient(self.root)
        login_window.grab_set()
        self._fit_dialog(login_window, 580, 460, 480, 360)
        
        # Login-Frame
        login_frame = ttk.Frame(login_window, padding="20")
        login_frame.pack(fill=tk.BOTH, expand=True)
        
        info_text = (
            "ARL-Token Anleitung:\n\n"
            "1. Öffnen Sie Deezer in Ihrem Browser\n"
            "2. Öffnen Sie die Entwicklertools (F12)\n"
            "3. Gehen Sie zu: Application → Cookies → deezer.com\n"
            "4. Kopieren Sie den Wert des Cookies 'arl'\n"
        )
        
        ttk.Label(login_frame, text=info_text, justify=tk.LEFT).pack(pady=10)
        
        ttk.Label(login_frame, text="ARL-Token:").pack(anchor=tk.W, pady=5)
        arl_entry = ttk.Entry(login_frame, width=50, show="*")
        arl_entry.pack(pady=5, fill=tk.X)
        arl_entry.focus()
        
        def do_login():
            arl = arl_entry.get().strip()
            if not arl:
                messagebox.showwarning("Warnung", "Bitte geben Sie einen ARL-Token ein.")
                return
            
            try:
                auth = DeezerAuth()
                if auth.login_with_arl(arl):
                    self.auth = auth
                    self.update_auth_status()
                    login_window.destroy()
                    messagebox.showinfo("Erfolg", "Erfolgreich angemeldet!")
                else:
                    messagebox.showerror("Fehler", "Anmeldung fehlgeschlagen. Bitte ARL-Token überprüfen.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler bei der Anmeldung: {e}")
        
        login_button = ttk.Button(login_frame, text="Anmelden", command=do_login)
        login_button.pack(pady=10)
        
        cancel_button = ttk.Button(login_frame, text="Abbrechen", command=login_window.destroy)
        cancel_button.pack()
        
        # Enter-Taste für Login
        arl_entry.bind('<Return>', lambda e: do_login())
    
    def logout(self):
        """Meldet den Benutzer ab"""
        if self.auth:
            self.auth.logout()
            self.auth = None
            self.update_auth_status()
            messagebox.showinfo("Info", "Erfolgreich abgemeldet.")
    
    def show_audible_login(self):
        """Zeigt Audible-Anmelde-Dialog"""
        if not AudibleAuth:
            messagebox.showinfo("Info", "Audible-Integration nicht verfügbar.")
            return
        
        login_window = tk.Toplevel(self.root)
        login_window.title("Audible Anmeldung")
        login_window.transient(self.root)
        login_window.grab_set()
        self._fit_dialog(login_window, 580, 500, 480, 380)
        
        login_frame = ttk.Frame(login_window, padding="20")
        login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info-Text
        info_text = (
            "Wählen Sie eine Anmeldemethode:\n\n"
            "🌐 Browser-Anmeldung (empfohlen):\n"
            "   Öffnet Audible im Browser. Nach dem Login\n"
            "   die Adresse der Fehlerseite hier einfügen.\n\n"
            "🍪 Cookie-Anmeldung (manuell):\n"
            "   Manuelle Cookie-Extraktion aus Browser\n"
            "   (falls Browser-Anmeldung nicht funktioniert)"
        )
        ttk.Label(login_frame, text=info_text, justify=tk.LEFT).pack(pady=10)
        
        ttk.Separator(login_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Browser-Anmeldung Button
        browser_button = ttk.Button(
            login_frame,
            text="🌐 Browser-Anmeldung (empfohlen)",
            command=lambda: self.do_browser_login(login_window)
        )
        browser_button.pack(pady=10, fill=tk.X)
        
        ttk.Label(login_frame, text="oder", foreground="gray").pack(pady=5)
        
        # Cookie-Anmeldung Button
        ttk.Button(
            login_frame,
            text="🍪 Cookie-Anmeldung (manuell)",
            command=lambda: self.show_cookie_login(login_window)
        ).pack(pady=5, fill=tk.X)
        
        ttk.Button(login_frame, text="Abbrechen", command=login_window.destroy).pack(pady=10)
    
    def do_browser_login(self, login_window):
        """Schließt die Auswahl und zeigt danach sofort das Anmeldungsfenster."""
        try:
            login_window.grab_release()
        except tk.TclError:
            pass
        try:
            login_window.destroy()
        except tk.TclError:
            pass
        self.root.after(30, self._open_audible_browser_login)

    def _open_audible_browser_login(self):
        """Fenster zuerst, Browser danach. Sonst bleibt der Klick auf dem Mac ohne Dialog."""
        result = {"url": "", "done": False}
        win = tk.Toplevel(self.root)
        win.title("Audible Anmeldung")
        try:
            win.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._fit_dialog(win, 680, 420, 560, 340)
        frame = ttk.Frame(win, padding="16")
        frame.pack(fill=tk.BOTH, expand=True)
        status = ttk.Label(frame, text="Fenster ist da. Der Browser öffnet sich gleich.", wraplength=620, justify=tk.LEFT)
        status.pack(anchor=tk.W, pady=(0, 8))
        ttk.Label(
            frame,
            text=(
                "Im Browser anmelden, auch die zweite Abfrage und ein Captcha.\n"
                "Danach kommt eine Fehlerseite. Die komplette Adresse daraus hier einfügen."
            ),
            justify=tk.LEFT,
            wraplength=620,
        ).pack(anchor=tk.W, pady=(0, 8))
        link = tk.Text(frame, height=3, wrap=tk.WORD)
        link.pack(fill=tk.X, pady=(0, 8))
        link.insert("1.0", "Anmeldelink wird vorbereitet…")
        ttk.Label(frame, text="Adresse nach dem Login:").pack(anchor=tk.W)
        entry = tk.Text(frame, height=4, wrap=tk.WORD)
        entry.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        def open_link():
            import webbrowser
            url = link.get("1.0", "end").strip()
            if url.startswith("http"):
                webbrowser.open(url)

        def pasted_text():
            return "\n".join((
                entry.get("1.0", "end"),
                link.get("1.0", "end"),
            ))

        def paste_into(_event=None):
            try:
                entry.insert("insert", self.root.clipboard_get())
            except tk.TclError:
                pass
            return "break"

        entry.bind("<Command-v>", paste_into)
        entry.bind("<Control-v>", paste_into)

        pending = {}

        def close_window():
            result["done"] = True
            try:
                win.destroy()
            except tk.TclError:
                pass

        def logged_in(account):
            self.audible_auth = account
            self.audible_library = AudibleLibrary(account)
            self.audible_status_var.set("✓ Angemeldet")
            self.audible_load_button.config(state=tk.NORMAL)
            try:
                self.notebook.select(self.audible_frame)
            except Exception:
                pass
            close_window()
            try:
                self.log("✓ Audible-Anmeldung erfolgreich")
            except Exception:
                pass
            messagebox.showinfo("Audible", "Angemeldet. Die Bibliothek kann jetzt geladen werden.", parent=self.root)

        def login_failed(exc):
            self.log(f"✗ Audible-Anmeldung fehlgeschlagen: {exc}")
            status.config(text=str(exc))
            for child in buttons.winfo_children():
                try:
                    child.config(state=tk.NORMAL)
                except tk.TclError:
                    pass

        def finish(ok):
            if not ok:
                result["url"] = ""
                close_window()
                return
            text = pasted_text()
            if not AudibleAuth.authorization_code_from_text(text):
                status.config(text="In dem Text ist kein Anmeldecode. Die komplette Adresse der Fehlerseite ins untere Feld einfügen.")
                return
            result["url"] = text
            status.config(text="Anmeldung läuft…")
            for child in buttons.winfo_children():
                try:
                    child.config(state=tk.DISABLED)
                except tk.TclError:
                    pass

            def work():
                try:
                    from path_helper import get_app_base_path
                    account = AudibleAuth(str(get_app_base_path() / ".audible_config.json"))
                    account.finish_browser_login(result["url"], pending)
                    self.root.after(0, lambda account=account: logged_in(account))
                except Exception as exc:
                    message = str(exc)
                    self.root.after(0, lambda message=message: login_failed(message))

            threading.Thread(target=work, daemon=True).start()

        buttons = ttk.Frame(frame)
        buttons.pack(anchor=tk.E)
        ttk.Button(buttons, text="Browser erneut öffnen", command=open_link).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Anmelden", command=lambda: finish(True)).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text="Abbrechen", command=lambda: finish(False)).pack(side=tk.RIGHT)
        win.protocol("WM_DELETE_WINDOW", lambda: finish(False))
        win.update_idletasks()
        try:
            win.lift()
            win.focus_force()
        except tk.TclError:
            pass

        try:
            pending.update(AudibleAuth.prepare_browser_login())
        except Exception as exc:
            status.config(text=f"Anmeldelink fehlgeschlagen: {exc}")
            win.wait_window()
            return
        link.delete("1.0", "end")
        link.insert("1.0", pending["url"])
        status.config(text="Adresse der Fehlerseite ins untere Feld einfügen und auf Anmelden klicken.")
        open_link()
        win.wait_window()
    
    def show_cookie_login(self, parent_window):
        """Zeigt Dialog für Cookie-Anmeldung"""
        cookie_window = tk.Toplevel(self.root)
        cookie_window.title("Cookie-Anmeldung")
        cookie_window.transient(self.root)
        cookie_window.grab_set()
        self._fit_dialog(cookie_window, 740, 660, 560, 440)
        
        cookie_frame = ttk.Frame(cookie_window, padding="20")
        cookie_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbarer Bereich für Anleitung
        info_frame = ttk.Frame(cookie_frame)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        info_text = (
            "📋 So finden Sie die Cookies:\n\n"
            "⚠️ WICHTIG: Stellen Sie sicher, dass Sie wirklich eingeloggt sind!\n"
            "   Öffnen Sie https://www.audible.de/library im Browser\n"
            "   und vergewissern Sie sich, dass Ihre Bibliothek angezeigt wird.\n\n"
            "1. Öffnen Sie Audible.de in Ihrem Browser (EINGELOGGT!)\n"
            "   Gehen Sie zu: https://www.audible.de/library\n\n"
            "2. Öffnen Sie die Entwicklertools:\n"
            "   • Chrome/Edge: F12 oder Rechtsklick → Untersuchen\n"
            "   • Firefox: F12 oder Rechtsklick → Element untersuchen\n"
            "   • Safari: Cmd+Option+I\n\n"
            "3. Gehen Sie zu:\n"
            "   Application (Chrome) / Storage (Firefox) →\n"
            "   Cookies → https://www.audible.de\n\n"
            "4. Kopieren Sie ALLE Cookies auf einmal:\n"
            "   • Markieren Sie alle Cookie-Zeilen (Strg+A / Cmd+A)\n"
            "   • Kopieren Sie sie (Strg+C / Cmd+C)\n"
            "   • Fügen Sie sie unten ein (Strg+V / Cmd+V)\n\n"
            "💡 Unterstützte Formate:\n"
            "   • Name=Wert (pro Zeile)\n"
            "   • Name: Wert\n"
            "   • Oder einfach die Cookie-Tabelle kopieren\n\n"
            "Wichtige Cookies (werden automatisch erkannt):\n"
            "• session-id, session-id-time\n"
            "• ubid-main (oder ubid-acbde, ubid-*)\n"
            "• at-main (oder at-acbde, at-*)\n"
            "• sess-at-main (oder sess-at-acbde, sess-at-*)\n"
            "• session-token, x-acbde (werden auch verwendet)"
        )
        
        info_scroll = scrolledtext.ScrolledText(
            info_frame,
            height=12,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("TkDefaultFont", 9)
        )
        info_scroll.pack(fill=tk.BOTH, expand=True)
        info_scroll.config(state=tk.NORMAL)
        info_scroll.insert(tk.END, info_text)
        info_scroll.config(state=tk.DISABLED)
        
        ttk.Separator(cookie_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Einzelnes großes Textfeld für alle Cookies
        ttk.Label(cookie_frame, text="Fügen Sie hier alle Cookies ein (können Sie direkt aus der Tabelle kopieren):", 
                 font=("TkDefaultFont", 9, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        cookie_text = scrolledtext.ScrolledText(
            cookie_frame,
            height=8,
            wrap=tk.WORD,
            font=("Courier", 9)
        )
        cookie_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        def parse_cookies(text: str) -> Dict[str, str]:
            """Parst Cookies aus verschiedenen Formaten"""
            cookies = {}
            lines = text.strip().split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Überschriften überspringen
                if line.lower().startswith(('name', 'cookie', 'domain', 'path', 'expires')):
                    continue
                
                # Format 1: Tab-getrennt (aus Browser-Tabelle kopiert)
                if '\t' in line:
                    parts = [p.strip() for p in line.split('\t')]
                    # Erste Spalte = Name, zweite Spalte = Wert
                    if len(parts) >= 2:
                        name = parts[0]
                        value = parts[1]
                        # Überspringe leere Werte, Domain-Spalten, etc.
                        if name and value and name.lower() not in ['name', 'wert', 'value', 'domain', 'path', 'expires', 'größe', 'size', 'secure', 'httponly', 'samesite']:
                            # Entferne Anführungszeichen am Anfang/Ende
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            cookies[name] = value
                
                # Format 2: Name=Wert
                elif '=' in line and not line.startswith('http'):
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                        if name and value:
                            # Entferne Anführungszeichen
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            cookies[name] = value
                
                # Format 3: Name: Wert
                elif ':' in line and not line.startswith('http'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        name = parts[0].strip()
                        value = parts[1].strip()
                        if name and value:
                            # Entferne Anführungszeichen
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            cookies[name] = value
            
            return cookies
        
        def normalize_cookie_name(name: str) -> str:
            """Normalisiert Cookie-Namen (z.B. ubid-acbde -> ubid-main)"""
            name_lower = name.lower()
            # Erkenne Cookie-Typen auch mit verschiedenen Suffixen
            if name_lower == 'session-id' or name_lower.startswith('session-id'):
                if 'time' in name_lower:
                    return 'session-id-time'
                return 'session-id'
            elif name_lower.startswith('ubid-'):
                # ubid-main, ubid-acbde, etc. -> ubid-main
                return 'ubid-main'
            elif name_lower.startswith('sess-at-'):
                # sess-at-main, sess-at-acbde, etc. -> sess-at-main
                return 'sess-at-main'
            elif name_lower.startswith('at-'):
                # at-main, at-acbde, etc. -> at-main
                return 'at-main'
            # Unbekannter Cookie, behalte Original-Name
            return name
        
        def do_cookie_login():
            text = cookie_text.get("1.0", tk.END).strip()
            if not text:
                messagebox.showwarning("Warnung", "Bitte fügen Sie Cookies ein.")
                return
            
            # Parse Cookies
            parsed_cookies = parse_cookies(text)
            
            if not parsed_cookies:
                messagebox.showwarning("Warnung", "Keine Cookies gefunden. Bitte überprüfen Sie das Format.")
                return
            
            # Normalisiere Cookie-Namen für wichtige Cookies
            # WICHTIG: Behalte ALLE Cookies, auch die nicht normalisierten!
            normalized_cookies = {}
            for name, value in parsed_cookies.items():
                normalized_name = normalize_cookie_name(name)
                
                # Wenn der Name normalisiert wurde (z.B. ubid-acbde -> ubid-main)
                if normalized_name != name:
                    # Verwende normalisierten Namen
                    if normalized_name not in normalized_cookies:
                        normalized_cookies[normalized_name] = value
                else:
                    # Name wurde nicht normalisiert, behalte Original-Name
                    # (z.B. session-token, x-acbde, TAsessionID, etc.)
                    normalized_cookies[name] = value
            
            # Debug: Zeige gefundene Cookies
            found_cookies = list(normalized_cookies.keys())
            self.log(f"\nGefundene Cookies ({len(found_cookies)}): {', '.join(found_cookies)}")
            
            # Wichtige Cookies prüfen
            important = ['session-id', 'session-id-time']
            missing = [c for c in important if c not in normalized_cookies]
            
            if missing:
                self.log(f"⚠ Fehlende wichtige Cookies: {', '.join(missing)}")
                if not messagebox.askyesno(
                    "Warnung",
                    f"Einige wichtige Cookies fehlen: {', '.join(missing)}\n\n"
                    "Möchten Sie trotzdem fortfahren?"
                ):
                    return
            
            try:
                from path_helper import get_app_base_path
                auth = AudibleAuth(str(get_app_base_path() / ".audible_config.json"))
                if auth.login_with_cookies(normalized_cookies):
                    self.audible_auth = auth
                    self.audible_library = AudibleLibrary(auth)
                    self.audible_status_var.set("✓ Angemeldet (Cookies)")
                    self.audible_load_button.config(state=tk.NORMAL)
                    cookie_window.destroy()
                    parent_window.destroy()
                    messagebox.showinfo("Erfolg", "Erfolgreich angemeldet mit Cookies!")
                else:
                    messagebox.showerror("Fehler", "Anmeldung mit Cookies fehlgeschlagen.\nCookies könnten ungültig oder abgelaufen sein.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler bei der Cookie-Anmeldung: {e}")
        
        button_frame = ttk.Frame(cookie_frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Anmelden", command=do_cookie_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=cookie_window.destroy).pack(side=tk.LEFT, padx=5)
    
    def load_audible_library(self, manual=True):
        """Lädt die Audible-Bibliothek. Beim Start ohne Tab-Wechsel und ohne Erfolgsfenster."""
        if not self.audible_auth or not self.audible_auth.is_logged_in():
            if manual:
                messagebox.showwarning("Warnung", "Bitte zuerst anmelden.")
            return
        if not self.audible_library:
            self.audible_library = AudibleLibrary(self.audible_auth)
        if not manual:
            self._audible_library_loading = True
        try:
            from plugin_loader import ask_plugins
            answers = ask_plugins(self.plugin_host, "can_load_books")
        except Exception:
            answers = []
        if any(answer is False for answer in answers):
            self._audible_library_loading = False
            if manual:
                messagebox.showwarning("Audible", "Ein Plugin hat das Laden der Bücher abgelehnt.")
            return
        
        def show_books(books):
            if manual:
                try:
                    self.notebook.select(self.audible_frame)
                except Exception:
                    pass
            for item in self.audible_tree.get_children():
                self.audible_tree.delete(item)
            self.audible_books = {}
            for book in books:
                asin = book.get('asin') or ''
                if asin:
                    self.audible_books[asin] = book
                self.audible_tree.insert(
                    '',
                    tk.END,
                    **({"iid": asin} if asin else {}),
                    values=(
                        book.get('title') or 'Unbekannt',
                        book.get('author') or 'Unbekannt',
                        book.get('narrators') or '–',
                        book.get('duration') or '–',
                        book.get('purchase_date') or '–',
                    ),
                    tags=(asin,),
                )
            children = self.audible_tree.get_children()
            if children:
                self.audible_tree.selection_set(children[0])
                self.audible_tree.focus(children[0])
                self._audible_show_book(self.audible_books.get(children[0]))
            try:
                self.log(f"✓ Bibliothek geladen: {len(books)} Hörbücher")
            except Exception:
                pass
            if manual:
                messagebox.showinfo("Erfolg", f"Bibliothek geladen: {len(books)} Hörbücher")
            else:
                self.audible_status_var.set(f"✓ Angemeldet, {len(books)} Hörbücher")
            self._audible_library_loaded = True
            self._audible_library_loading = False

        def load_failed(message):
            self._audible_library_loading = False
            if manual:
                messagebox.showerror("Fehler", f"Fehler beim Laden der Bibliothek: {message}")
            else:
                self.audible_status_var.set("Bibliothek konnte nicht geladen werden")

        def load_thread():
            try:
                books = self.audible_library.fetch_library()
                self.root.after(0, lambda books=books: show_books(books))
            except Exception as exc:
                message = str(exc)
                self.root.after(0, lambda message=message: load_failed(message))
        
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()

    def _audible_selected_book(self):
        selected = self.audible_tree.selection()
        if not selected:
            return None
        return self.audible_books.get(selected[0])

    def _audible_on_select(self, _event=None):
        self._audible_show_book(self._audible_selected_book())

    def _audible_show_book(self, book):
        book = book or {}
        for key, var in self.audible_detail_vars.items():
            var.set(book.get(key) or "–")
        self.audible_summary.config(state=tk.NORMAL)
        self.audible_summary.delete("1.0", tk.END)
        self.audible_summary.insert("1.0", book.get("summary") or "")
        self.audible_summary.config(state=tk.DISABLED)
        cover_url = book.get("cover_url") or ""
        if not cover_url:
            return

        def load_cover():
            try:
                import io
                import subprocess
                from PIL import Image
                raw = subprocess.check_output(["/usr/bin/curl", "-fsS", "-A", "Mozilla/5.0", cover_url], timeout=20)
                image = Image.open(io.BytesIO(raw))
                image.thumbnail((180, 180))
                buffer = io.BytesIO()
                image.convert("RGB").save(buffer, format="PNG")
                png = buffer.getvalue()
            except Exception:
                return

            def apply():
                if self._audible_selected_book() and self._audible_selected_book().get("cover_url") != cover_url:
                    return
                photo = tk.PhotoImage(data=png)
                self.audible_cover_image = photo
                self.audible_cover_label.config(image=photo)

            self.root.after(0, apply)

        threading.Thread(target=load_cover, daemon=True).start()

    def _audible_local_files(self, book):
        title = (book or {}).get("title") or ""
        if not title or not self.audible_library:
            return []
        folder = Path(self.audible_download_path) / self.audible_library._sanitize_filename(title)
        if not folder.is_dir():
            return []
        files = []
        for pattern in ("*.mp3", "*.m4a", "*.m4b"):
            files.extend(folder.glob(pattern))
        return sorted(files)

    def play_selected_audible_book(self):
        book = self._audible_selected_book()
        if not book:
            messagebox.showwarning("Audible", "Bitte zuerst ein Hörbuch auswählen.")
            return
        files = self._audible_local_files(book)
        if not files:
            messagebox.showinfo(
                "Audible",
                "Dieses Hörbuch liegt noch nicht als Datei vor.\nZuerst herunterladen, danach kann der Player es abspielen.",
            )
            return
        if len(files) == 1:
            self._preview_video(files[0].as_uri(), book.get("title") or "Hörbuch", image=book.get("cover_url") or "", stream_url=str(files[0]))
            return
        try:
            import preview_player
        except ImportError:
            messagebox.showerror("Wiedergabe", "Der eingebaute Player ist nicht verfügbar.")
            return
        entries = [
            {"title": path.stem, "url": path.as_uri(), "image": book.get("cover_url") or "", "stream_url": str(path)}
            for path in files
        ]
        preview_player.open_preview_list(entries, self.root.after, lambda msg: messagebox.showerror("Wiedergabe", msg), self._ask_resume_playback)

    def show_activation_bytes_placeholder(self):
        """Der Knopf bleibt. Die alte Funktion ist noch nicht brauchbar, Plugins können sie füllen."""
        try:
            from plugin_loader import ask_plugins
            answers = ask_plugins(getattr(self, "plugin_host", None), "activation_bytes")
        except Exception:
            answers = []
        text = next((answer for answer in answers if isinstance(answer, str) and answer.strip()), "")
        messagebox.showinfo(
            "Activation Bytes",
            text or "Platzhalter. Diese Funktion ist noch nicht brauchbar.",
        )

    def show_activation_bytes_dialog(self):
        """Zeigt Dialog zur manuellen Eingabe von Activation Bytes"""
        if not self.audible_auth:
            messagebox.showwarning("Warnung", "Bitte melden Sie sich zuerst bei Audible an.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Activation Bytes")
        dialog.transient(self.root)
        dialog.grab_set()
        self._fit_dialog(dialog, 660, 540, 520, 400)
        
        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Status-Anzeige
        status_frame = ttk.LabelFrame(frame, text="Status", padding="10")
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        status_label = ttk.Label(status_frame, text="", font=("Arial", 10))
        status_label.pack(anchor=tk.W)
        
        activation_display_frame = ttk.Frame(status_frame)
        activation_display_frame.pack(fill=tk.X, pady=(5, 0))
        
        activation_display_label = ttk.Label(
            activation_display_frame, 
            text="", 
            font=("Courier", 11, "bold"),
            foreground="green"
        )
        activation_display_label.pack(anchor=tk.W)
        
        def update_status():
            """Aktualisiert die Status-Anzeige"""
            if self.audible_auth.activation_bytes:
                status_label.config(
                    text="✓ Activation Bytes gefunden und gespeichert",
                    foreground="green"
                )
                activation_display_label.config(
                    text=f"Key: {self.audible_auth.activation_bytes}",
                    foreground="green"
                )
            else:
                status_label.config(
                    text="✗ Activation Bytes nicht gefunden",
                    foreground="red"
                )
                activation_display_label.config(
                    text="Keine Activation Bytes vorhanden",
                    foreground="gray"
                )
        
        # Initialisiere Status
        update_status()
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Automatische Ermittlung
        auto_frame = ttk.LabelFrame(frame, text="Automatische Ermittlung", padding="10")
        auto_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_text = (
            "Versucht automatisch die Activation Bytes aus Ihrer Audible-Session zu extrahieren.\n"
            "Dies funktioniert nur, wenn Sie mit der audible-Bibliothek angemeldet sind."
        )
        ttk.Label(auto_frame, text=info_text, justify=tk.LEFT, wraplength=600).pack(pady=5)
        
        def auto_extract():
            """Extrahiert Activation Bytes automatisch"""
            status_label.config(text="⏳ Extrahiere Activation Bytes...", foreground="blue")
            activation_display_label.config(text="", foreground="")
            dialog.update()
            
            try:
                self.log("\nVersuche Activation Bytes automatisch zu extrahieren...")
                activation_bytes = self.audible_auth.get_activation_bytes(force_refresh=True)
                if activation_bytes:
                    self.log(f"\n✓ Activation Bytes erfolgreich extrahiert: {activation_bytes}")
                    self.log(f"  Key: {activation_bytes}")
                    update_status()
                    messagebox.showinfo(
                        "Erfolg", 
                        f"Activation Bytes erfolgreich extrahiert!\n\nKey: {activation_bytes}"
                    )
                else:
                    self.log("\n✗ Konnte Activation Bytes nicht automatisch extrahieren")
                    self.log("\nℹ Alternative: Verwenden Sie audible-activator manuell")
                    self.log("  1. Öffnen Sie ein Terminal")
                    self.log("  2. Führen Sie aus:")
                    self.log(f"     cd {Path(__file__).parent / 'audible-activator'}")
                    self.log("     python3 audible-activator.py -l de -d")
                    self.log("     (Mit -d für Debug-Modus, damit Sie manuell einloggen können)")
                    self.log("  3. Ein Browser-Fenster öffnet sich")
                    self.log("  4. Melden Sie sich manuell an (inkl. 2FA falls aktiviert)")
                    self.log("  5. Warten Sie 32 Sekunden oder drücken Sie Enter im Terminal")
                    self.log("  6. Die Activation Bytes werden angezeigt")
                    self.log("  7. Kopieren Sie die angezeigten Activation Bytes")
                    self.log("  8. Fügen Sie sie hier manuell ein")
                    
                    status_label.config(
                        text="✗ Konnte Activation Bytes nicht automatisch extrahieren",
                        foreground="red"
                    )
                    activation_display_label.config(
                        text="Bitte verwenden Sie die manuelle Eingabe oder audible-activator",
                        foreground="orange"
                    )
                    messagebox.showwarning(
                        "Nicht gefunden",
                        "Activation Bytes konnten nicht automatisch extrahiert werden.\n\n"
                        "Alternative Methoden:\n"
                        "1. Manuelle Eingabe (unten)\n"
                        "2. audible-activator (Terminal):\n"
                        f"   cd audible-activator\n"
                        f"   python3 audible-activator.py -l de -d\n"
                        f"   (Mit -d für Debug-Modus)\n\n"
                        "Im Debug-Modus können Sie manuell einloggen.\n"
                        "Die Activation Bytes werden dann angezeigt."
                    )
            except Exception as e:
                self.log(f"\n✗ Fehler bei automatischer Extraktion: {e}")
                import traceback
                self.log(traceback.format_exc())
                status_label.config(
                    text=f"✗ Fehler: {str(e)[:50]}...",
                    foreground="red"
                )
                activation_display_label.config(
                    text="Bitte verwenden Sie die manuelle Eingabe",
                    foreground="orange"
                )
                messagebox.showerror("Fehler", f"Fehler bei automatischer Extraktion:\n{e}")
        
        ttk.Button(
            auto_frame,
            text="🔍 Automatisch ermitteln",
            command=auto_extract
        ).pack(pady=10)
        
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Manuelle Eingabe
        manual_frame = ttk.LabelFrame(frame, text="Manuelle Eingabe", padding="10")
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        info_text2 = (
            "Geben Sie die Activation Bytes manuell ein.\n"
            "Format: Hex-String (z.B. '12345678' oder '12-34-56-78')\n\n"
            "So erhalten Sie die Activation Bytes:\n"
            "1. Öffnen Sie ein Terminal\n"
            "2. Führen Sie aus:\n"
            f"   cd {Path(__file__).parent / 'audible-activator'}\n"
            "   python3 audible-activator.py -l de\n"
            "3. Geben Sie Username und Password ein\n"
            "4. Ein Browser öffnet sich - melden Sie sich an\n"
            "5. Warten Sie, bis die Activation Bytes angezeigt werden\n"
            "6. Kopieren Sie die Activation Bytes (z.B. 'a1b2c3d4')\n"
            "7. Fügen Sie sie hier ein und klicken Sie auf 'Speichern'"
        )
        ttk.Label(manual_frame, text=info_text2, justify=tk.LEFT, wraplength=500).pack(pady=5)
        
        activation_entry = ttk.Entry(manual_frame, width=40, font=("Courier", 10))
        activation_entry.pack(pady=5, fill=tk.X)
        
        def save_activation_bytes():
            value = activation_entry.get().strip()
            if not value:
                messagebox.showwarning("Warnung", "Bitte geben Sie Activation Bytes ein.")
                return
            
            if self.audible_auth.set_activation_bytes(value):
                self.log(f"\n✓ Activation Bytes manuell gespeichert: {value}")
                update_status()
                messagebox.showinfo("Erfolg", f"Activation Bytes wurden gespeichert!\n\nKey: {value}")
                activation_entry.delete(0, tk.END)
            else:
                messagebox.showerror("Fehler", "Ungültiges Format für Activation Bytes.")
        
        ttk.Button(
            manual_frame,
            text="💾 Speichern",
            command=save_activation_bytes
        ).pack(pady=5)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Schließen", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def show_audible_download_options(self) -> Optional[Dict]:
        """
        Zeigt Dialog für Download-Optionen (Kapitel oder Gesamt-MP3)
        
        Returns:
            Dictionary mit Optionen oder None bei Abbruch
        """
        options_window = tk.Toplevel(self.root)
        options_window.title("Download-Optionen")
        options_window.transient(self.root)
        options_window.grab_set()
        self._fit_dialog(options_window, 560, 500, 460, 400)
        
        options_frame = ttk.Frame(options_window, padding="20")
        options_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            options_frame,
            text="Wie möchten Sie das Hörbuch herunterladen?",
            font=("Arial", 10, "bold")
        ).pack(pady=10)
        
        download_mode = tk.StringVar(value="complete")
        
        # Option 1: Gesamt-MP3
        mode_frame1 = ttk.Frame(options_frame)
        mode_frame1.pack(fill=tk.X, pady=10)
        
        ttk.Radiobutton(
            mode_frame1,
            text="Als komplette MP3-Datei",
            variable=download_mode,
            value="complete"
        ).pack(anchor=tk.W)
        
        ttk.Label(
            mode_frame1,
            text="  → Eine einzige Datei für das gesamte Hörbuch",
            foreground="gray",
            font=("Arial", 8)
        ).pack(anchor=tk.W, padx=20)
        
        # Option 2: Kapitel
        mode_frame2 = ttk.Frame(options_frame)
        mode_frame2.pack(fill=tk.X, pady=10)
        
        ttk.Radiobutton(
            mode_frame2,
            text="Als einzelne Kapitel",
            variable=download_mode,
            value="chapters"
        ).pack(anchor=tk.W)
        
        ttk.Label(
            mode_frame2,
            text="  → Jedes Kapitel als separate Datei",
            foreground="gray",
            font=("Arial", 8)
        ).pack(anchor=tk.W, padx=20)
        
        # Qualitätsauswahl (nur für Konvertierung, nicht für AAX-Download)
        ttk.Separator(options_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        
        ttk.Label(
            options_frame,
            text="Zielformat (nach Konvertierung):",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, pady=5)
        
        info_label = ttk.Label(
            options_frame,
            text="ℹ Die beste verfügbare AAX-Qualität wird automatisch heruntergeladen\n   und dann in das gewählte Format konvertiert.",
            font=("Arial", 9),
            foreground="gray"
        )
        info_label.pack(anchor=tk.W, pady=5)
        
        quality_var = tk.StringVar(value="MP3_320")
        
        qualities = [
            ("FLAC (Lossless, beste Qualität)", "FLAC"),
            ("MP3 320 kbps (hohe Qualität)", "MP3_320"),
            ("MP3 192 kbps (mittlere Qualität)", "MP3_192"),
            ("MP3 128 kbps (niedrige Qualität)", "MP3_128"),
        ]
        
        for text, value in qualities:
            ttk.Radiobutton(
                options_frame,
                text=text,
                variable=quality_var,
                value=value
            ).pack(anchor=tk.W, pady=2)
        
        result = [None]
        
        def confirm():
            result[0] = {
                'as_chapters': download_mode.get() == "chapters",
                'quality': quality_var.get()
            }
            options_window.destroy()
        
        def cancel():
            options_window.destroy()
        
        button_frame = ttk.Frame(options_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Bestätigen", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        options_window.wait_window()
        return result[0]
    
    def download_selected_audible_books(self):
        """Lädt ausgewählte Hörbücher herunter"""
        selected = self.audible_tree.selection()
        if not selected:
            messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens ein Hörbuch aus.")
            return
        
        if not self.audible_library:
            messagebox.showwarning("Warnung", "Bitte zuerst anmelden und Bibliothek laden.")
            return
        
        # Download-Optionen (Kapitel oder Gesamt-MP3 + Qualität)
        options = self.show_audible_download_options()
        if not options:
            return  # Benutzer hat abgebrochen
        
        # Download-Pfad
        download_path = Path(self.path_var.get()) if hasattr(self, 'path_var') else self.download_path
        audible_path = self.audible_download_path
        
        def download_thread():
            try:
                # Wechsle zum Deezer-Tab für Logs
                self.notebook.select(0)
                self.log(f"Starte Download von {len(selected)} Hörbuch(en)...")
                self.log(f"Modus: {'Kapitel einzeln' if options['as_chapters'] else 'Komplette MP3'}")
                self.log(f"Qualität: {options['quality']}")
                self.log("=" * 60)
                
                success_count = 0
                
                for item in selected:
                    values = self.audible_tree.item(item, 'values')
                    asin = self.audible_tree.item(item, 'tags')[0] if self.audible_tree.item(item, 'tags') else None
                    title = values[0] if values else "Unbekannt"
                    
                    if not asin:
                        self.log(f"✗ Keine ASIN für {title} gefunden")
                        continue
                    
                    self.log(f"Lade herunter: {title}")
                    
                    # Download durchführen
                    success = self.audible_library.download_book(
                        asin=asin,
                        title=title,
                        output_dir=audible_path,
                        as_chapters=options['as_chapters'],
                        quality=options['quality']
                    )
                    
                    if success:
                        self.log(f"  ✓ Erfolgreich: {title}")
                        success_count += 1
                    else:
                        self.log(f"  ✗ Fehlgeschlagen: {title}")
                
                self.log("=" * 60)
                self.log(f"✓ Download abgeschlossen: {success_count}/{len(selected)} Hörbücher")
                
                # Wechsle zurück zum Audible-Tab
                self.notebook.select(1)
                
                messagebox.showinfo(
                    "Erfolg",
                    f"Download abgeschlossen!\n{success_count}/{len(selected)} Hörbücher erfolgreich heruntergeladen."
                )
            except Exception as e:
                self.log(f"✗ Fehler beim Download: {e}")
                messagebox.showerror("Fehler", f"Fehler beim Download: {e}")
        
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
    
    def browse_video_download_path(self):
        """Öffnet einen Dialog zur Auswahl des Video-Download-Pfads"""
        path = filedialog.askdirectory(initialdir=str(self.video_download_path))
        if path:
            self.video_download_path = Path(path)
            self.video_path_var.set(str(self.video_download_path))
    
    def start_video_download(self):
        """Startet den Video-Download in einem separaten Thread"""
        url = self.video_url_var.get().strip()
        
        if not url:
            messagebox.showwarning("Warnung", "Bitte geben Sie eine Video-URL ein.")
            return

        self.video_download_path = Path(self.video_path_var.get())
        if self._start_plugin_download(url, self.video_download_path):
            return
        
        # Voreinstellung Qualität/Format pro Sender anwenden
        self._apply_domain_preset(url)

        # Mediatheken/Hörbücher nur im Musik-Tab
        if _is_music_mediathek_url(url):
            messagebox.showinfo(
                "Mediathek / Hörspiel – Musik-Tab",
                "Diese URL ist eine Audio-Mediathek oder Hörbuch-/Hörspiel-Seite und wird im Tab „Musik“ unterstützt.\n\n"
                "Bitte wechseln Sie zum Tab „🎵 Musik“ und starten Sie den Download dort."
            )
            try:
                for tab_id in self.notebook.tabs():
                    if "Musik" in self.notebook.tab(tab_id, "text"):
                        self.notebook.select(tab_id)
                        break
            except Exception:
                pass
            return
        
        # Downloader initialisieren
        self.video_download_path = Path(self.video_path_var.get())
        quality = self.video_quality_var.get()
        output_format = self.video_format_var.get()
        self.video_downloader = VideoDownloader(
            download_path=str(self.video_download_path),
            quality=quality,
            output_format=output_format,
            gui_instance=self
        )
        
        # Prüfe ob es ARD Plus ist (DRM-geschützt)
        url_lower = url.lower()
        is_ard_plus = 'ardplus.de' in url_lower or 'ard-plus.de' in url_lower
        
        if is_ard_plus:
            # Zeige Info-Dialog mit Optionen
            info_window = tk.Toplevel(self.root)
            info_window.title("ARD Plus - DRM-geschützte Inhalte")
            info_window.transient(self.root)
            info_window.grab_set()
            self._fit_dialog(info_window, 720, 460, 560, 360)
            
            # Variable um zu verfolgen, ob weitergemacht werden soll
            continue_download = tk.BooleanVar(value=False)
            
            main_frame = ttk.Frame(info_window, padding="20")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(
                main_frame,
                text="ARD Plus verwendet DRM-geschützte Inhalte",
                font=("Arial", 12, "bold")
            ).pack(pady=(0, 10))
            
            info_text = (
                "yt-dlp kann DRM-geschützte Inhalte nicht herunterladen.\n\n"
                "Für private Zwecke können Sie folgende Tools verwenden:\n"
                "• StreamFab (bereits vorhanden) - speziell für DRM-geschützte Inhalte\n"
                "• PlayOn - Aufnahme während der Wiedergabe\n"
                "• Browser-Erweiterungen wie Video DownloadHelper\n\n"
                "Die URL wird automatisch in die Zwischenablage kopiert,\n"
                "damit Sie sie einfach in StreamFab einfügen können."
            )
            
            ttk.Label(
                main_frame,
                text=info_text,
                justify=tk.LEFT,
                wraplength=660
            ).pack(pady=10, padx=10)
            
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)
            
            def copy_url_and_close():
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                self.root.update()
                messagebox.showinfo("URL kopiert", f"Die URL wurde in die Zwischenablage kopiert:\n\n{url}\n\nSie können sie jetzt in StreamFab einfügen.")
                continue_download.set(False)
                info_window.destroy()
            
            def try_anyway():
                continue_download.set(True)
                info_window.destroy()
            
            def cancel():
                continue_download.set(False)
                info_window.destroy()
            
            ttk.Button(
                button_frame,
                text="📋 URL kopieren & Schließen",
                command=copy_url_and_close
            ).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(
                button_frame,
                text="🔄 Trotzdem versuchen",
                command=try_anyway
            ).pack(side=tk.LEFT, padx=5)
            
            ttk.Button(
                button_frame,
                text="❌ Abbrechen",
                command=cancel
            ).pack(side=tk.LEFT, padx=5)
            
            # Kopiere URL automatisch in Zwischenablage
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.root.update()
            
            # Warte auf Schließen des Dialogs
            info_window.wait_window()
            
            # Prüfe ob der Download fortgesetzt werden soll
            if not continue_download.get():
                return
        
        # Stelle sicher, dass video_downloader initialisiert ist
        if not hasattr(self, 'video_downloader') or self.video_downloader is None:
            if VideoDownloader:
                self.video_downloader = VideoDownloader(
                    str(self.video_download_path),
                    quality=self.video_quality_var.get(),
                    output_format=self.video_format_var.get(),
                    gui_instance=self,
                )
            else:
                messagebox.showerror("Fehler", "VideoDownloader konnte nicht initialisiert werden.")
                return
        
        # Prüfe ob URL unterstützt wird
        if not self.video_downloader.is_supported_url(url):
            response = messagebox.askyesno(
                "URL möglicherweise nicht unterstützt",
                f"Die URL scheint nicht von einem bekannten Sender zu stammen.\n\n"
                f"Trotzdem versuchen? (yt-dlp unterstützt viele weitere Quellen)"
            )
            if not response:
                return
        
        # Prüfe ob es eine Serie/Staffel ist – aber nur, wenn wir nicht explizit für eine einzelne Episode
        # aus der Queue starten (dort gibt es bereits episode_info, kein neuer Auswahl-Dialog nötig).
        skip_series_detection = getattr(self, '_skip_series_detection_for_episode', False)
        if skip_series_detection:
            # Flag sofort zurücksetzen, gilt nur für diesen Start
            try:
                del self._skip_series_detection_for_episode
            except AttributeError:
                pass
        else:
            self.video_log("Prüfe ob es eine Serie/Staffel ist...")
            
            # Prüfe ob es eine YouTube-URL ist
            is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
            is_youtube_playlist = is_youtube and ('list=' in url.lower() or '/playlist' in url.lower())
            
            # Prüfe ob es eine Serie/Staffel oder YouTube-Playlist ist
            is_series_or_playlist = False
            if is_youtube_playlist:
                # YouTube-Playlist: immer Auswahl anbieten
                is_series_or_playlist = True
                self.video_log("✓ YouTube-Playlist erkannt!")
            elif not is_youtube and self.video_downloader.is_series_or_season(url):
                # Andere Sender: Prüfe ob Serie/Staffel
                is_series_or_playlist = True
                self.video_log("✓ Serie/Staffel erkannt!")
            
            if is_series_or_playlist:
                # Zeige Dialog zur Auswahl
                self.video_log("Rufe Episoden/Playlist-Daten ab...")
                series_data = self.video_downloader.get_series_episodes(url)
                
                if series_data:
                    if is_youtube_playlist:
                        self.video_log(f"✓ Playlist-Daten erhalten: {series_data.get('series_name', 'Unbekannt')}")
                        self.video_log(f"  Playlisten: {len(series_data.get('seasons', {}))}")
                    else:
                        self.video_log(f"✓ Serien-Daten erhalten: {series_data.get('series_name', 'Unbekannt')}")
                        self.video_log(f"  Staffeln: {len(series_data.get('seasons', {}))}")
                    self.video_log(f"  Gesamt-Folgen: {series_data.get('total_episodes', 0)}")
                    
                    if series_data.get('seasons'):
                        # Öffne Dialog
                        self.video_log("Öffne Dialog zur Auswahl...")
                        try:
                            selected_episodes = self.show_series_selection_dialog(series_data, is_youtube_playlist=is_youtube_playlist)
                            if not selected_episodes:
                                self.video_log("Benutzer hat abgebrochen")
                                return  # Benutzer hat abgebrochen
                            
                            self.video_log(f"✓ {len(selected_episodes)} Folgen ausgewählt")
                            
                            # Starte Download für ausgewählte Folgen
                            self.video_download_button.config(state=tk.DISABLED)
                            if hasattr(self, 'video_cancel_button'):
                                self.video_cancel_button.config(state=tk.NORMAL)
                            self.video_progress_var.set(0)
                            self.video_progress_bar.config(mode='determinate', maximum=100)
                            self.video_status_var.set("Download läuft...")
                            self.video_download_cancelled = False
                            self.video_download_cancel_current_only = False
                            # Setze episodes_total VOR dem Start des Threads, damit cancel_video_download es sehen kann
                            self.video_download_episodes_total = len(selected_episodes)
                            
                            thread = threading.Thread(target=self.video_download_episodes_thread, args=(selected_episodes,))
                            thread.daemon = True
                            thread.start()
                            return
                        except Exception as e:
                            self.video_log(f"✗ Fehler beim Öffnen des Dialogs: {e}")
                            import traceback
                            self.video_log(traceback.format_exc())
                    else:
                        if is_youtube_playlist:
                            self.video_log("⚠ Keine Playlisten in Daten gefunden")
                        else:
                            self.video_log("⚠ Keine Staffeln in Serien-Daten gefunden")
                else:
                    if is_youtube_playlist:
                        self.video_log("⚠ Keine Playlist-Daten erhalten")
                    else:
                        self.video_log("⚠ Keine Serien-Daten erhalten")
        
        # Normales einzelnes Video
        # UI deaktivieren
        self.video_download_button.config(state=tk.DISABLED)
        if hasattr(self, 'video_cancel_button'):
            self.video_cancel_button.config(state=tk.NORMAL)
        self.video_progress_var.set(0)
        self.video_progress_bar.config(mode='determinate', maximum=100)
        # Bei Serien-Queue: "Download läuft (2/2)" etc. anzeigen
        ep_total = getattr(self, '_video_batch_episode_total', 0)
        ep_current = getattr(self, '_video_batch_episode_current', 0)
        if ep_total and ep_current:
            self.video_status_var.set(f"Download läuft ({ep_current}/{ep_total})...")
        else:
            self.video_status_var.set("Download läuft...")
        self.video_download_cancelled = False
        
        # Download in separatem Thread starten
        thread = threading.Thread(target=self.video_download_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def video_download_thread(self, url: str, queue_item=None, parallel_gui=None, _from_queue_worker=False):
        """Video-Download-Thread. queue_item/parallel_gui bei paralleler Queue-Verarbeitung."""
        qi = queue_item if isinstance(queue_item, dict) else {}
        gui_inst = parallel_gui if parallel_gui is not None else self
        parallel_mode = parallel_gui is not None

        def Qo(key, default_fn):
            if key in qi:
                return qi[key]
            return default_fn()

        job_tag = f"[{url[:40]}…] " if parallel_mode and url else ""

        try:
            # Wechsle zum Video-Tab für Logs
            audio_ui = self._queue_item_is_audio(queue_item, url)
            if not hasattr(self, "_download_surface_for_url"):
                self._download_surface_for_url = {}
            self._download_surface_for_url[url] = "music" if audio_ui else "video"
            if audio_ui:
                self._select_music_tab()
                self.music_log(f"Starte Hörbuch-/Audio-Download: {(url or '')[:80]}")
            else:
                self.notebook.select(self.notebook.index(self.video_frame))
            
            # Download-Archiv: Bereits heruntergeladene überspringen
            if self._is_in_download_archive(url):
                self.video_log(f"{job_tag}Übersprungen (bereits im Download-Archiv): {url[:60]}…")
                qitem = qi if qi else getattr(self, '_current_queue_item_for_batch', None)
                if qitem:
                    if qitem.get('from_file_batch'):
                        self.video_download_batch_file_success = getattr(self, 'video_download_batch_file_success', 0) + 1
                    if qitem.get('episode_info'):
                        self.video_download_batch_series_success = getattr(self, 'video_download_batch_series_success', 0) + 1
                if not _from_queue_worker:
                    self.root.after(0, self._process_download_queue)
                return
            
            # Prüfe ob es eine YouTube-URL ist
            is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
            is_youtube_playlist = 'list=' in url.lower() or '/playlist' in url.lower()
            
            self.video_log("=" * 60)
            self.video_log(f"{job_tag}Starte Video-Download")
            self.video_log(f"URL: {url}")
            fmt_v = Qo('format', self.video_format_var.get)
            format_display = (fmt_v or '').upper() if fmt_v != "none" else "Keine"
            self.video_log(f"Format: {format_display}")
            self.video_log(f"Qualität: {Qo('quality', self.video_quality_var.get)}")
            if is_youtube and is_youtube_playlist:
                self.video_log(f"YouTube-Playlist erkannt: Gesamte Playlist wird heruntergeladen")
            self.video_log(f"Ziel: {qi.get('output_dir') or self.video_download_path}")
            self.video_log("=" * 60)
            
            # Pro parallelem Job eigener Downloader + keine GPU-Kodierung (sonst oft fehlgeschlagene
            # FFmpeg/VideoToolbox-Merges: leere MP4, große .webm liegen bleiben).
            # Stelle sicher, dass video_downloader initialisiert ist
            if not hasattr(self, 'video_downloader') or self.video_downloader is None:
                if VideoDownloader:
                    self.video_downloader = VideoDownloader(
                        str(self.video_download_path),
                        quality=Qo('quality', self.video_quality_var.get),
                        output_format=(Qo('format', self.video_format_var.get) or 'mp4').lower(),
                        gui_instance=self,
                    )
                else:
                    messagebox.showerror("Fehler", "VideoDownloader konnte nicht initialisiert werden.")
                    return
            vd = self.video_downloader
            if parallel_mode and VideoDownloader:
                try:
                    vd = VideoDownloader(
                        str(self.video_download_path),
                        quality=Qo('quality', self.video_quality_var.get),
                        output_format=(Qo('format', self.video_format_var.get) or 'mp4').lower(),
                        gui_instance=gui_inst,
                    )
                    fmt_now = (Qo('format', self.video_format_var.get) or 'mp4').lower()
                    if self.settings.get('gpu_enabled', False) and fmt_now not in ('mp3', 'none', ''):
                        self.video_log(
                            f"{job_tag}Parallele Downloads: die Dateien laden gleichzeitig, "
                            f"die GPU wandelt sie danach nacheinander nach {fmt_now.upper()} um."
                        )
                except Exception as _e:
                    self.video_log(f"{job_tag}Hinweis: Eigener Downloader fehlgeschlagen, nutze Standard: {_e}")
                    vd = self.video_downloader
            
            # Hole Video-Informationen
            self.video_log("\nRufe Video-Informationen ab...")
            video_info = vd.get_video_info(url)
            
            if video_info:
                title = video_info.get('title', 'Unbekannt')
                duration = video_info.get('duration', 0)
                if duration:
                    minutes = int(duration // 60)
                    seconds = int(duration % 60)
                    duration_str = f"{minutes}:{seconds:02d}"
                else:
                    duration_str = "Unbekannt"
                
                self.video_log(f"\n✓ Video gefunden:")
                self.video_log(f"  Titel: {title}")
                self._video_job_update(url, title=title)
                self.video_log(f"  Dauer: {duration_str}")
                self.video_log(f"  Uploader: {video_info.get('uploader', 'Unbekannt')}")
                
                # Zeige tatsächlich verwendete Auflösung basierend auf ausgewählter Qualität
                selected_quality = Qo('quality', self.video_quality_var.get)
                actual_resolution = vd._get_actual_resolution(video_info, selected_quality)
                if actual_resolution:
                    quality_display = selected_quality
                    if selected_quality == "best":
                        quality_display = "Beste"
                    elif selected_quality == "niedrigste":
                        quality_display = "Niedrigste"
                    self.video_log(f"  Qualität: {quality_display} → {actual_resolution}")
            
            # Starte Download mit Fortschritts-Callback
            self.video_log("\nStarte Download...")
            _job_title = self._queue_item_label(qi, url)
            self._video_job_update(url, title=_job_title, phase="download", percent=0, create=True)

            def progress_callback(percent, status_line):
                """Fortschritt direkt merken. Die Anzeige zieht das alle 250 ms, ohne die Oberfläche zu fluten."""
                phase_now = "download"
                pct = percent
                if status_line and "Konvertierung" in status_line:
                    phase_now = "convert"
                    m = re.search(r"(\d+\.?\d*)\s*%", status_line)
                    if m:
                        try:
                            pct = float(m.group(1))
                        except ValueError:
                            pass
                self._video_job_update(url, phase=phase_now, percent=pct, status_line=status_line)
            
            # Prüfe ob es eine Serie ist (nur für nicht-YouTube URLs)
            # Oder: Einzelvideo aus Queue mit episode_info (z. B. Playlist-Folge) → gleicher Ordner wie Playlist
            is_series = False
            series_name = None
            season_number = None
            
            queue_item = qi if qi else getattr(self, '_current_queue_item_for_batch', None)
            playlist_index_from_queue = None
            if isinstance(queue_item, dict) and queue_item.get('episode_info'):
                ep_info = queue_item['episode_info']
                is_series = True
                series_name = ep_info.get('series_name') or ep_info.get('series') or ''
                season_number = ep_info.get('season_number')
                playlist_index_from_queue = ep_info.get('playlist_index') or ep_info.get('episode_number')
                if video_info is None:
                    video_info = {}
                for k in ('title', 'series', 'season_number', 'episode_number', 'broadcast_date', 'upload_date'):
                    if ep_info.get(k) not in (None, ''):
                        video_info[k] = ep_info[k]
                if series_name and not video_info.get('series'):
                    video_info['series'] = series_name
            elif not is_youtube and video_info:
                is_series = bool(video_info.get('series') or video_info.get('season_number'))
                series_name = video_info.get('series')
                season_number = video_info.get('season_number')
            
            # Für YouTube: Playlist automatisch erkennen
            download_playlist = is_youtube and is_youtube_playlist
            target_fmt = (Qo('format', self.video_format_var.get) or 'mp4').lower()
            out_dir = qi.get('output_dir') or self.video_download_path
            if target_fmt == 'mp3':
                out_dir = self.music_download_path
            
            # Prüfung: Datei existiert bereits? (nur bei Einzelvideo, nicht bei Playlist)
            file_exists_choice = None  # "redownload" | "skip" | "convert" | "cancel"
            if not download_playlist and video_info:
                exists, existing_path, same_format = vd.check_existing_file(
                    video_info, out_dir, target_fmt,
                    is_series, series_name, season_number, url
                )
                if exists and existing_path and same_format and _from_queue_worker:
                    file_exists_choice = "skip"
                elif exists and existing_path:
                    result_queue = queue.Queue()
                    def _show_exists_dialog():
                        choice = [None]  # use list to allow assign in nested
                        tw = tk.Toplevel(self.root)
                        tw.transient(self.root)
                        tw.title("Datei existiert bereits")
                        if same_format:
                            msg = f"Eine Datei existiert bereits:\n{existing_path.name}\n\nErneut herunterladen?"
                            frm = ttk.Frame(tw, padding=15)
                            frm.pack(fill=tk.BOTH, expand=True)
                            ttk.Label(frm, text=msg, wraplength=400).pack(pady=(0, 15))
                            def on_ja(): choice[0] = "redownload"; tw.destroy()
                            def on_nein(): choice[0] = "skip"; tw.destroy()
                            def on_abbrechen(): choice[0] = "cancel"; tw.destroy()
                            ttk.Button(frm, text="Ja", command=on_ja).pack(side=tk.LEFT, padx=5)
                            ttk.Button(frm, text="Nein", command=on_nein).pack(side=tk.LEFT, padx=5)
                            ttk.Button(frm, text="Abbrechen", command=on_abbrechen).pack(side=tk.LEFT, padx=5)
                        else:
                            msg = f"Eine Datei existiert bereits in anderem Format:\n{existing_path.name}\n\nErneut herunterladen oder vorhandene Datei konvertieren?"
                            frm = ttk.Frame(tw, padding=15)
                            frm.pack(fill=tk.BOTH, expand=True)
                            ttk.Label(frm, text=msg, wraplength=400).pack(pady=(0, 15))
                            def on_redownload(): choice[0] = "redownload"; tw.destroy()
                            def on_convert(): choice[0] = "convert"; tw.destroy()
                            def on_abbrechen(): choice[0] = "cancel"; tw.destroy()
                            ttk.Button(frm, text="Erneut herunterladen", command=on_redownload).pack(side=tk.LEFT, padx=5)
                            ttk.Button(frm, text="Konvertieren", command=on_convert).pack(side=tk.LEFT, padx=5)
                            ttk.Button(frm, text="Abbrechen", command=on_abbrechen).pack(side=tk.LEFT, padx=5)
                        tw.protocol("WM_DELETE_WINDOW", lambda: (choice.__setitem__(0, "cancel") or tw.destroy()))
                        tw.grab_set()
                        tw.wait_window()
                        result_queue.put(choice[0])
                    self.root.after(0, _show_exists_dialog)
                    file_exists_choice = result_queue.get()
            
            success, file_path, error = False, None, ""
            if file_exists_choice == "cancel":
                self.video_log("\nDownload abgebrochen (Datei existiert bereits).")
                self.video_status_var.set("Abgebrochen")
                success, file_path, error = False, None, "Abgebrochen"
            elif file_exists_choice == "skip":
                self.video_log("\nBereits vorhanden – nicht erneut geladen.")
                self.video_status_var.set("Bereits vorhanden")
                self._video_job_update(url, phase="exists", percent=100)
                success, file_path, error = True, existing_path, ""
            elif file_exists_choice == "convert":
                self.video_log("\nKonvertiere vorhandene Datei...")
                success, file_path, error = vd.convert_existing_to_format(
                    existing_path, Qo('format', self.video_format_var.get), progress_callback
                )
                if not success:
                    self.video_log(f"\nKonvertierung fehlgeschlagen: {error}")
            else:
                # redownload or no existing file: normal download
                # Geschwindigkeits-Limit (aus Einstellungen)
                speed_limit = None
                if self.settings.get('speed_limit_enabled', False):
                    try:
                        speed_limit = float(self.settings.get('speed_limit_value', '5'))
                    except ValueError:
                        speed_limit = None
                gpu_on = bool(self.settings.get('gpu_enabled', False))
                # Mehrere Downloads parallel, GPU-Umwandlung danach nacheinander.
                defer_recode = bool(parallel_mode and gpu_on and target_fmt not in ('mp3', 'none', ''))
                use_gpu = gpu_on and not parallel_mode
                success, file_path, error = vd.download_video(
                url,
                output_dir=out_dir,
                quality=Qo('quality', self.video_quality_var.get),
                output_format=target_fmt,
                download_playlist=download_playlist,
                progress_callback=progress_callback,
                video_info=video_info,
                is_series=is_series,
                series_name=series_name,
                season_number=season_number,
                playlist_index=playlist_index_from_queue,
                download_subtitles=Qo('subtitle', self.video_subtitle_var.get),
                subtitle_language=Qo('subtitle_lang', self.video_subtitle_lang_var.get),
                download_description=Qo('description', self.video_description_var.get),
                download_thumbnail=Qo('thumbnail', self.video_thumbnail_var.get),
                resume_download=Qo('resume', self.video_resume_var.get),
                speed_limit=speed_limit,
                embed_metadata=True,
                gui_instance=gui_inst,
                gpu_enabled=use_gpu,
                gpu_vendor=self.settings.get('gpu_vendor', 'auto'),
                force_redownload=(file_exists_choice == "redownload"),
                defer_recode=defer_recode,
            )
                if success and defer_recode and file_path and Path(file_path).suffix.lower() != f'.{target_fmt}':
                    self.video_log(f"{job_tag}Download fertig. Konvertierung nach {target_fmt.upper()} wartet, bis die GPU frei ist.")
                    self._video_job_update(url, phase="convert_wait", percent=100)
                    with self._video_convert_lock:
                        if self.video_download_cancelled:
                            success, file_path, error = False, None, "Abgebrochen"
                        else:
                            self._video_job_update(url, phase="convert", percent=100)
                            progress_callback(100, "Konvertierung läuft...")
                            ok_c, fp_c, err_c = vd.convert_existing_to_format(
                                file_path,
                                target_fmt,
                                progress_callback,
                                gpu_enabled=True,
                                gpu_vendor=self.settings.get('gpu_vendor', 'auto'),
                            )
                            if ok_c and fp_c:
                                try:
                                    if Path(fp_c).resolve() != Path(file_path).resolve():
                                        Path(file_path).unlink()
                                except Exception:
                                    pass
                                file_path = fp_c
                            else:
                                success, error = False, err_c or "Konvertierung fehlgeschlagen"
            
            stat_kind = "music" if self._queue_item_is_audio(qi if isinstance(qi, dict) else None, url) else "video"
            if success:
                if file_path:
                    self.video_log(f"\n✓ Download erfolgreich!")
                    self.video_log(f"  Datei: {file_path.name}")
                    self.video_log(f"  Pfad: {file_path}")
                    self.video_status_var.set(f"✓ Download erfolgreich: {file_path.name}")
                    
                    # Aktualisiere Statistiken
                    self._update_statistics(success=True, file_path=file_path, url=url, kind=stat_kind)
                    
                    # Füge zur Historie hinzu
                    self._add_to_history(url, file_path.name, "Erfolgreich")
                    # Download-Archiv: URL als heruntergeladen markieren
                    self._add_to_download_archive(url)
                    # Serien-Wächter: Folge als „habe ich“ markieren
                    ep_id = None
                    q_mark = qi if qi else getattr(self, '_current_queue_item_for_batch', None)
                    if isinstance(q_mark, dict):
                        epi = q_mark.get('episode_info') or {}
                        if isinstance(epi, dict):
                            ep_id = epi.get('id')
                    self._series_watch_mark_downloaded(url, episode_id=ep_id)
                    
                    # Batch-Zähler (URL-Liste aus Datei oder Serien-Folgen aus Queue)
                    qitem = qi if qi else getattr(self, '_current_queue_item_for_batch', None)
                    if qitem:
                        if qitem.get('from_file_batch'):
                            self.video_download_batch_file_success = getattr(self, 'video_download_batch_file_success', 0) + 1
                        if qitem.get('episode_info'):
                            self.video_download_batch_series_success = getattr(self, 'video_download_batch_series_success', 0) + 1
                        try:
                            del self._current_queue_item_for_batch
                        except AttributeError:
                            pass
                    
                    # Einzel-Erfolgs-Dialog nur wenn keine Batch-Meldung am Ende kommt
                    queue_count = len(getattr(self, 'video_download_queue', []))
                    workers_left = getattr(self, '_video_parallel_workers', 0)
                    batch_file = getattr(self, 'video_download_batch_from_file', False)
                    batch_series = getattr(self, 'video_download_batch_series_total', 0)
                    if queue_count == 0 and not parallel_mode and not batch_file and not batch_series:
                        def _show_success_autoclose():
                            fp = file_path
                            if fp and getattr(fp, "exists", lambda: False)():
                                if self.settings.get('auto_open_folder', False):
                                    self._open_folder(fp)
                                if self.settings.get('play_after_download', False):
                                    self._open_file_with_default_app(fp)
                                self._show_system_notification("Download abgeschlossen", f"{fp.name} — {fp.parent}")
                            else:
                                self._show_system_notification("Download abgeschlossen", "Die Datei wurde gespeichert.")
                        self.root.after(0, _show_success_autoclose)
                else:
                    self.video_log(f"\n⚠ Download scheint erfolgreich, aber Datei nicht gefunden")
                    self.video_status_var.set("⚠ Download abgeschlossen (Datei nicht gefunden)")
                    
                    # Aktualisiere Statistiken
                    self._update_statistics(success=True, file_path=None, url=url, kind=stat_kind)
                    
                    # Füge zur Historie hinzu
                    self._add_to_history(url, "N/A", "Datei nicht gefunden")
                    
                    queue_count = len(getattr(self, 'video_download_queue', []))
                    if queue_count == 0:
                        messagebox.showwarning(
                            "Warnung",
                            "Download abgeschlossen, aber Datei nicht gefunden.\nBitte prüfen Sie das Download-Verzeichnis."
                        )
            else:
                failed_title = self._queue_item_label(qi, url)
                self.video_log(f"\n✗ Download fehlgeschlagen ({failed_title}): {error}")
                self.video_status_var.set(f"✗ {failed_title}: fehlgeschlagen")
                
                # Aktualisiere Statistiken
                self._update_statistics(success=False, file_path=None, url=url, kind=stat_kind, error=error)
                
                # Füge zur Historie hinzu
                self._add_to_history(url, "N/A", f"Fehlgeschlagen: {error}")
                
                if error != "Abgebrochen":
                    if "404" in (error or "") or "Unable to download JSON metadata" in (error or ""):
                        err_msg = (
                            f"„{failed_title}“ ist in der Mediathek gerade nicht abrufbar.\n\n"
                            "Die Seite dazu wurde nicht gefunden. Ein fehlendes Cover "
                            "bricht den Download nicht ab."
                        )
                    else:
                        err_msg = f"„{failed_title}“\n\nDownload fehlgeschlagen:\n\n{error}"
                    self.root.after(0, lambda m=err_msg: messagebox.showerror("Fehler", m))
            
        except Exception as e:
            self.video_log(f"\n✗ Fehler: {e}")
            import traceback
            self.video_log(traceback.format_exc())
            self.video_status_var.set(f"✗ Fehler: {e}")
            err_msg = f"Fehler beim Download: {e}"
            self.root.after(0, lambda: messagebox.showerror("Fehler", err_msg))
        finally:
            self._video_job_update(url, remove=True)
            if not _from_queue_worker:
                self.video_download_button.config(state=tk.NORMAL)
                if hasattr(self, 'video_cancel_button'):
                    self.video_cancel_button.config(state=tk.DISABLED)
                self.video_download_process = None
                if self.video_download_cancelled:
                    self.video_status_var.set("Download abgebrochen")
                    self.video_progress_var.set(0)
                else:
                    self.video_progress_var.set(100)
                    if self.video_status_var.get().startswith("Download läuft"):
                        self.video_status_var.set("Bereit")
                last_url = getattr(self, '_last_video_download_url', '') or ''
                delay_ms = 2000 if last_url and ('youtube.com' in last_url.lower() or 'youtu.be' in last_url.lower()) else 0
                if delay_ms:
                    self.video_log("  Pause 2 s (YouTube Rate-Limit-Schutz)…")
                self.root.after(delay_ms, self._process_download_queue)
            else:
                if parallel_gui is None:
                    self.video_download_process = None
    
    def _terminate_video_subprocess(self, proc):
        """Beendet einen yt-dlp-Unterprozess (Unix: Prozessgruppe, Windows: terminate/kill)."""
        if proc is None:
            return
        try:
            if proc.poll() is not None:
                return
        except Exception:
            return
        try:
            import os
            import signal
            import time
            if sys.platform != 'win32':
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGTERM)
                    time.sleep(0.25)
                    if proc.poll() is None:
                        os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, OSError):
                    try:
                        proc.terminate()
                        time.sleep(0.25)
                        if proc.poll() is None:
                            proc.kill()
                    except Exception:
                        pass
            else:
                proc.terminate()
                time.sleep(0.25)
                if proc.poll() is None:
                    proc.kill()
        except Exception as e:
            self.video_log(f"⚠ Fehler beim Beenden eines Prozesses: {e}")

    def _terminate_all_active_video_download_processes(self):
        """Alle laufenden Video-Download-Prozesse (parallel + Haupt-Referenz)."""
        for p in list(getattr(self, '_parallel_video_process_list', []) or []):
            self._terminate_video_subprocess(p)
        self._terminate_video_subprocess(self.video_download_process)

    def cancel_video_download(self):
        """Bricht den laufenden Download ab"""
        # Prüfe ob ein Serien-Download läuft (mehrere Episoden)
        episodes_total = getattr(self, 'video_download_episodes_total', 0)
        is_series_download = episodes_total > 1
        
        # Debug-Logging auch in die Hauptlog-Datei schreiben
        print(f"[DEBUG] cancel_video_download: episodes_total={episodes_total}, is_series_download={is_series_download}")
        self.video_log(f"[DEBUG] Abbrechen: episodes_total={episodes_total}, is_series_download={is_series_download}")
        
        if is_series_download:
            print(f"[DEBUG] Zeige Dialog für Serien-Download mit {episodes_total} Folgen")
            self.video_log(f"[DEBUG] Zeige Dialog für Serien-Download mit {episodes_total} Folgen")
            # Zeige Dialog mit zwei Optionen
            cancel_dialog = tk.Toplevel(self.root)
            cancel_dialog.title("Download abbrechen")
            cancel_dialog.geometry("400x150")
            cancel_dialog.transient(self.root)
            cancel_dialog.grab_set()
            
            # Zentriere das Fenster
            cancel_dialog.update_idletasks()
            x = (cancel_dialog.winfo_screenwidth() // 2) - (cancel_dialog.winfo_width() // 2)
            y = (cancel_dialog.winfo_screenheight() // 2) - (cancel_dialog.winfo_height() // 2)
            cancel_dialog.geometry(f"+{x}+{y}")
            
            choice = None
            
            def cancel_current():
                nonlocal choice
                choice = "current"
                cancel_dialog.destroy()
            
            def cancel_all():
                nonlocal choice
                choice = "all"
                cancel_dialog.destroy()
            
            def cancel_nothing():
                nonlocal choice
                choice = None
                cancel_dialog.destroy()
            
            ttk.Label(cancel_dialog, text="Was möchten Sie abbrechen?", font=("Arial", 11, "bold")).pack(pady=10)
            ttk.Label(cancel_dialog, text=f"Es werden {episodes_total} Folgen heruntergeladen.").pack(pady=5)
            
            button_frame = ttk.Frame(cancel_dialog)
            button_frame.pack(pady=15)
            
            ttk.Button(button_frame, text="Aktuelle Folge abbrechen", command=cancel_current, width=25).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Ganze Staffel abbrechen", command=cancel_all, width=25).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Abbrechen", command=cancel_nothing).pack(side=tk.LEFT, padx=5)
            
            cancel_dialog.wait_window()
            
            if choice is None:
                return  # Benutzer hat abgebrochen
            
            import time
            self.video_log("\n" + "="*60)
            
            if choice == "current":
                # Nur aktuelle Folge abbrechen
                self.video_log("⚠ ABBRUCH ANGEORDNET: Nur aktuelle Folge")
                self.video_log(f"[DEBUG] Abbrechen-Button geklickt um {time.strftime('%H:%M:%S')}")
                self.video_log(f"[DEBUG] Nur aktuelle Folge wird abgebrochen")
                self.video_download_cancel_current_only = True
                self.video_log("⚠ Aktuelle Folge wird abgebrochen...")
                self.video_status_var.set("Aktuelle Folge wird abgebrochen...")
            else:
                # Ganze Staffel abbrechen
                self.video_log("⚠ ABBRUCH ANGEORDNET: Ganze Staffel")
                self.video_log(f"[DEBUG] Abbrechen-Button geklickt um {time.strftime('%H:%M:%S')}")
                self.video_log(f"[DEBUG] video_download_cancelled wird auf True gesetzt")
                self.video_download_cancelled = True
                self.video_download_cancel_current_only = False
                self.video_log(f"[DEBUG] video_download_cancelled ist jetzt: {self.video_download_cancelled}")
                self.video_log("⚠ Download wird abgebrochen...")
                self.video_status_var.set("Download wird abgebrochen...")
            
            self.video_log("[DEBUG] Beende alle laufenden Video-Prozesse…")
            self._terminate_all_active_video_download_processes()
            
            # UI aktualisieren
            self.video_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.DISABLED)
            self.video_status_var.set("Download abgebrochen")
            self.video_progress_var.set(0)
        else:
            # Einzelner Download – Abfrage mit optionalem "Ja alle" (Queue leeren), wenn noch Einträge in der Warteschlange sind
            queue_count = len(getattr(self, 'video_download_queue', []))
            cancel_all_queued = False
            
            if queue_count > 0:
                cancel_dialog = tk.Toplevel(self.root)
                cancel_dialog.title("Download abbrechen")
                cancel_dialog.geometry("420x140")
                cancel_dialog.transient(self.root)
                cancel_dialog.grab_set()
                choice = None
                def on_ja():
                    nonlocal choice
                    choice = "ja"
                    cancel_dialog.destroy()
                def on_ja_alle():
                    nonlocal choice, cancel_all_queued
                    choice = "ja"
                    cancel_all_queued = True
                    cancel_dialog.destroy()
                def on_nein():
                    nonlocal choice
                    choice = "nein"
                    cancel_dialog.destroy()
                ttk.Label(cancel_dialog, text="Möchten Sie den laufenden Download wirklich abbrechen?",
                          wraplength=380).pack(pady=(15, 8))
                ttk.Label(cancel_dialog, text=f"Noch {queue_count} Download(s) in der Warteschlange.",
                          font=("Arial", 9)).pack(pady=(0, 12))
                btn_frame = ttk.Frame(cancel_dialog)
                btn_frame.pack(pady=5)
                ttk.Button(btn_frame, text="Nein", command=on_nein, width=10).pack(side=tk.LEFT, padx=4)
                ttk.Button(btn_frame, text="Ja", command=on_ja, width=10).pack(side=tk.LEFT, padx=4)
                ttk.Button(btn_frame, text="Ja, alle", command=on_ja_alle, width=10).pack(side=tk.LEFT, padx=4)
                cancel_dialog.protocol("WM_DELETE_WINDOW", on_nein)
                cancel_dialog.wait_window()
                if choice != "ja":
                    return
            else:
                if not messagebox.askyesno("Download abbrechen", "Möchten Sie den laufenden Download wirklich abbrechen?"):
                    return
            
            if cancel_all_queued and queue_count > 0:
                self.video_download_queue.clear()
                self.video_log(f"⚠ Warteschlange geleert ({queue_count} Einträge verworfen).")
                self._update_queue_status()
            
            import time
            self.video_log("\n" + "="*60)
            self.video_log("⚠ ABBRUCH ANGEORDNET")
            self.video_log(f"[DEBUG] Abbrechen-Button geklickt um {time.strftime('%H:%M:%S')}")
            self.video_log(f"[DEBUG] video_download_cancelled wird auf True gesetzt")
            self.video_download_cancelled = True
            self.video_download_cancel_current_only = False
            self.video_log(f"[DEBUG] video_download_cancelled ist jetzt: {self.video_download_cancelled}")
            self.video_log("⚠ Download wird abgebrochen...")
            self.video_status_var.set("Download wird abgebrochen…")
            self.video_log("[DEBUG] Beende alle laufenden Video-Prozesse (inkl. parallele Queue)…")
            self._terminate_all_active_video_download_processes()
            
            # UI aktualisieren
            self.video_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.DISABLED)
            self.video_status_var.set("Download abgebrochen")
            self.video_progress_var.set(0)
    
    def show_series_selection_dialog(self, series_data: Dict, is_youtube_playlist: bool = False) -> Optional[List[Dict]]:
        """
        Zeigt Dialog zur Auswahl von Staffeln/Playlisten und Folgen
        
        Args:
            series_data: Dictionary mit Serien/Playlist-Informationen (von get_series_episodes)
                Format: {
                    'series_name': str,
                    'seasons': {
                        1: [episode1, episode2, ...],
                        2: [episode1, episode2, ...],
                    },
                    'total_episodes': int
                }
            is_youtube_playlist: True wenn es eine YouTube-Playlist ist, sonst False
            
        Returns:
            Liste mit ausgewählten Episoden oder None bei Abbruch
        """
        selection_window = tk.Toplevel(self.root)
        if is_youtube_playlist:
            selection_window.title("Playlisten und Videos auswählen")
        else:
            selection_window.title("Staffeln und Folgen auswählen")
        selection_window.transient(self.root)
        selection_window.grab_set()
        self._fit_dialog(selection_window, 980, 760, 720, 520)
        
        # Hauptcontainer mit einheitlichem Design
        main_frame = ttk.Frame(selection_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titel-Bereich mit Hintergrund
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        series_name = series_data.get('series_name', 'Unbekannte Serie/Playlist')
        total_episodes = series_data.get('total_episodes', 0)
        seasons = series_data.get('seasons', {})
        
        playlist_kind = series_data.get("playlist_kind")
        if playlist_kind == "music":
            title_text = f"Playlist: {series_name}"
            info_text = f"{total_episodes} Lieder. Einzelne anhaken oder oben alle auswählen."
        elif is_youtube_playlist:
            title_text = f"📺 Playlist: {series_name}"
            info_text = f"{len(seasons)} Playlist(en) mit insgesamt {total_episodes} Video(s) gefunden."
        else:
            title_text = f"📺 Serie: {series_name}"
            info_text = f"{len(seasons)} Staffel(n) mit insgesamt {total_episodes} Folgen gefunden."
        
        title_label = ttk.Label(
            title_frame,
            text=title_text,
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 5))
        
        info_label = ttk.Label(
            title_frame,
            text=info_text,
            font=("Arial", 10),
            foreground="gray"
        )
        info_label.pack(anchor=tk.W)
        
        # Frame für Staffeln/Playlisten und Folgen/Videos mit Scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Canvas mit einheitlichem Hintergrund (system default, kein weiß)
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self._bind_scroll_wheel(canvas, scrollable_frame)
        
        # Variablen für Checkboxen
        season_vars = {}  # {season_num: BooleanVar}
        episode_vars = {}  # {(season_num, episode_idx): BooleanVar}
        
        # Erstelle UI für jede Staffel/Playlist
        for season_num in sorted(seasons.keys()):
            season_episodes = seasons[season_num]
            
            # Staffel/Playlist-Frame mit verbessertem Design
            if playlist_kind == "music":
                frame_text = f"Playlist ({len(season_episodes)} Lieder)"
                checkbox_text = "Alle Lieder auswählen"
            elif is_youtube_playlist:
                frame_text = f"📋 Playlist {season_num} ({len(season_episodes)} Videos)"
                checkbox_text = f"Alle Videos aus Playlist {season_num} auswählen"
            else:
                frame_text = f"📺 Staffel {season_num} ({len(season_episodes)} Folgen)"
                checkbox_text = f"Alle Folgen aus Staffel {season_num} auswählen"
            
            season_frame = ttk.LabelFrame(
                scrollable_frame,
                text=frame_text,
                padding="12"
            )
            season_frame.pack(fill=tk.X, padx=8, pady=8)
            
            # Staffel/Playlist-Checkbox (alle Folgen/Videos dieser Staffel/Playlist)
            season_var = tk.BooleanVar(value=False)
            season_vars[season_num] = season_var
            
            def make_season_toggle(season_num, var):
                def toggle():
                    # Alle Episoden/Videos dieser Staffel/Playlist ein/ausschalten
                    for i in range(len(seasons[season_num])):
                        key = (season_num, i)
                        if key in episode_vars:
                            episode_vars[key].set(var.get())
                return toggle
            
            season_checkbox = ttk.Checkbutton(
                season_frame,
                text=checkbox_text,
                variable=season_var,
                command=make_season_toggle(season_num, season_var)
            )
            season_checkbox.pack(anchor=tk.W, pady=(0, 5))
            
            # Episoden/Videos-Frame (mit Grid für bessere Darstellung)
            episodes_frame = ttk.Frame(season_frame)
            episodes_frame.pack(fill=tk.BOTH, expand=True, padx=(25, 0), pady=(5, 0))
            
            # Episoden/Videos in Spalten anzeigen (2 Spalten)
            for i, episode in enumerate(season_episodes):
                var = tk.BooleanVar(value=False)
                episode_vars[(season_num, i)] = var
                
                # Episode/Video-Info
                ep_num = episode.get('episode_number')
                title = episode.get('title', 'Unbekannt')
                duration = episode.get('duration_string', '')
                date_iso = episode.get('broadcast_date') or ''
                date_disp = ''
                if date_iso and len(str(date_iso)) == 10 and str(date_iso)[4] == '-':
                    date_disp = f"{date_iso[8:10]}.{date_iso[5:7]}.{date_iso[:4]}"
                elif date_iso:
                    date_disp = str(date_iso)
                
                if ep_num is not None:
                    if is_youtube_playlist:
                        label_text = f"▶ {ep_num:02d}. {title}"
                    else:
                        label_text = f"▶ E{ep_num:02d}: {title}"
                else:
                    label_text = f"▶ {title}"
                
                extras = []
                if duration:
                    extras.append(duration)
                if date_disp:
                    extras.append(date_disp)
                if extras:
                    label_text += f" ({', '.join(extras)})"
                
                # Kürze Titel falls zu lang
                if len(label_text) > 70:
                    label_text = label_text[:67] + "..."
                
                # Checkbox direkt ohne zusätzlichen Frame (für einheitliches Design)
                checkbox = ttk.Checkbutton(
                    episodes_frame,
                    text=label_text,
                    variable=var
                )
                
                # 2 Spalten Layout mit besserem Abstand
                row = i // 2
                col = i % 2
                checkbox.grid(row=row, column=col, sticky=tk.W, padx=8, pady=4)
            
            # Konfiguriere Spalten-Gewichtung für gleichmäßige Verteilung
            episodes_frame.columnconfigure(0, weight=1)
            episodes_frame.columnconfigure(1, weight=1)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons-Bereich mit besserem Design
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Linke Seite: Auswahl-Buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        def select_all():
            for var in season_vars.values():
                var.set(True)
            for var in episode_vars.values():
                var.set(True)
            update_button_text()
        
        def select_none():
            for var in season_vars.values():
                var.set(False)
            for var in episode_vars.values():
                var.set(False)
            update_button_text()
        
        ttk.Button(left_buttons, text="✓ Alle auswählen", command=select_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(left_buttons, text="✗ Alle abwählen", command=select_none).pack(side=tk.LEFT, padx=3)
        
        # Rechte Seite: Download und Abbrechen-Buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        selected_episodes = []
        
        def confirm():
            nonlocal selected_episodes
            # Sammle alle ausgewählten Episoden
            for season_num in sorted(seasons.keys()):
                season_episodes = seasons[season_num]
                for i, episode in enumerate(season_episodes):
                    key = (season_num, i)
                    if key in episode_vars and episode_vars[key].get():
                        selected_episodes.append(episode)
            
            if not selected_episodes:
                if playlist_kind == "music":
                    messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens ein Lied aus.")
                elif is_youtube_playlist:
                    messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens ein Video aus.")
                else:
                    messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens eine Folge aus.")
                return
            selection_window.destroy()
        
        def cancel():
            nonlocal selected_episodes
            selected_episodes = None
            selection_window.destroy()
        
        # Zähle ausgewählte Episoden/Videos für Button-Text
        def update_button_text():
            count = sum(1 for var in episode_vars.values() if var.get())
            if playlist_kind == "music":
                confirm_button.config(text=f"▶ Download ({count} Lieder)")
            elif is_youtube_playlist:
                confirm_button.config(text=f"▶ Download ({count} Video(s))")
            else:
                confirm_button.config(text=f"▶ Download ({count} Folge(n))")
        
        # Initialisiere Button-Text
        if playlist_kind == "music":
            confirm_button = ttk.Button(right_buttons, text="▶ Download (0 Lieder)", command=confirm)
        elif is_youtube_playlist:
            confirm_button = ttk.Button(right_buttons, text="▶ Download (0 Video(s))", command=confirm)
        else:
            confirm_button = ttk.Button(right_buttons, text="▶ Download (0 Folge(n))", command=confirm)
        confirm_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="❌ Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # Aktualisiere Button-Text bei Änderungen
        for var in list(season_vars.values()) + list(episode_vars.values()):
            var.trace_add("write", lambda *args: update_button_text())
        
        selection_window.wait_window()
        return selected_episodes
    
    def show_track_selection_dialog(self, title: str, tracks: List[Dict], is_artist: bool = False) -> Optional[List[Dict]]:
        """
        Zeigt Dialog zur Auswahl von Tracks (für Artists oder Playlists)
        
        Args:
            title: Titel des Dialogs
            tracks: Liste von Track-Dictionaries
            is_artist: True wenn es ein Artist ist, False wenn Playlist
            
        Returns:
            Liste mit ausgewählten Tracks oder None bei Abbruch
        """
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Tracks auswählen")
        selection_window.transient(self.root)
        selection_window.grab_set()
        self._fit_dialog(selection_window, 880, 720, 640, 500)
        
        # Hauptcontainer
        main_frame = ttk.Frame(selection_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titel-Bereich
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame,
            text=title,
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 5))
        
        info_label = ttk.Label(
            title_frame,
            text=f"{len(tracks)} Track(s) gefunden.",
            font=("Arial", 10),
            foreground="gray"
        )
        info_label.pack(anchor=tk.W)
        
        # Frame für Tracks mit Scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self._bind_scroll_wheel(canvas, scrollable_frame)
        
        # Variablen für Checkboxen
        track_vars = {}  # {track_index: BooleanVar}
        
        # Erstelle UI für jeden Track
        for i, track in enumerate(tracks):
            var = tk.BooleanVar(value=False)
            track_vars[i] = var
            
            # Track-Info
            track_title = track.get('title', 'Unbekannt')
            artist_name = track.get('artist', {}).get('name', 'Unbekannt') if isinstance(track.get('artist'), dict) else 'Unbekannt'
            duration = track.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration > 0 else ""
            
            label_text = f"🎵 {track_title} - {artist_name}"
            if duration_str:
                label_text += f" ({duration_str})"
            
            # Kürze Titel falls zu lang
            if len(label_text) > 80:
                label_text = label_text[:77] + "..."
            
            # Checkbox
            checkbox = ttk.Checkbutton(
                scrollable_frame,
                text=label_text,
                variable=var
            )
            checkbox.pack(anchor=tk.W, padx=8, pady=4)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons-Bereich
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Linke Seite: Auswahl-Buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        def select_all():
            for var in track_vars.values():
                var.set(True)
            update_button_text()
        
        def select_none():
            for var in track_vars.values():
                var.set(False)
            update_button_text()
        
        ttk.Button(left_buttons, text="✓ Alle auswählen", command=select_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(left_buttons, text="✗ Alle abwählen", command=select_none).pack(side=tk.LEFT, padx=3)
        
        # Rechte Seite: Download und Abbrechen-Buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        selected_tracks = []
        
        def confirm():
            nonlocal selected_tracks
            # Sammle alle ausgewählten Tracks
            for i, track in enumerate(tracks):
                if i in track_vars and track_vars[i].get():
                    selected_tracks.append(track)
            
            if not selected_tracks:
                messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens einen Track aus.")
                return
            selection_window.destroy()
        
        def cancel():
            nonlocal selected_tracks
            selected_tracks = None
            selection_window.destroy()
        
        # Zähle ausgewählte Tracks für Button-Text
        def update_button_text():
            count = sum(1 for var in track_vars.values() if var.get())
            confirm_button.config(text=f"▶ Download ({count} Track(s))")
        
        confirm_button = ttk.Button(right_buttons, text="▶ Download (0 Track(s))", command=confirm)
        confirm_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="❌ Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # Aktualisiere Button-Text bei Änderungen
        for var in track_vars.values():
            var.trace_add("write", lambda *args: update_button_text())
        
        selection_window.wait_window()
        return selected_tracks
    
    def show_album_selection_dialog(self, title: str, albums: List[Dict]) -> Optional[List[Dict]]:
        """
        Zeigt Dialog zur Auswahl von Alben mit YouTube-Verfügbarkeitsanzeige
        
        Args:
            title: Titel des Dialogs
            albums: Liste von Album-Dictionaries (mit 'youtube_available' Feld)
            
        Returns:
            Liste mit ausgewählten Alben oder None bei Abbruch
        """
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Alben auswählen")
        selection_window.transient(self.root)
        selection_window.grab_set()
        self._fit_dialog(selection_window, 960, 720, 700, 500)
        
        # Hauptcontainer
        main_frame = ttk.Frame(selection_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titel-Bereich
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame,
            text=title,
            font=("Arial", 16, "bold")
        )
        title_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Zähle YouTube-verfügbare Alben
        youtube_count = sum(1 for album in albums if album.get('youtube_available', False))
        info_label = ttk.Label(
            title_frame,
            text=f"{len(albums)} Album(s) gefunden. {youtube_count} auf YouTube verfügbar.",
            font=("Arial", 10),
            foreground="gray"
        )
        info_label.pack(anchor=tk.W)
        
        # Frame für Alben mit Scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self._bind_scroll_wheel(canvas, scrollable_frame)
        
        # Variablen für Checkboxen
        album_vars = {}  # {album_index: BooleanVar}
        
        # Erstelle UI für jedes Album
        for i, album in enumerate(albums):
            var = tk.BooleanVar(value=False)
            album_vars[i] = var
            
            # Album-Info
            album_title = album.get('title', 'Unbekannt')
            artist_name = album.get('artist', {}).get('name', 'Unbekannt') if isinstance(album.get('artist'), dict) else 'Unbekannt'
            nb_tracks = album.get('nb_tracks', 0)
            release_date = album.get('release_date', '')
            
            # YouTube-Verfügbarkeit
            youtube_available = album.get('youtube_available', False)
            youtube_icon = "✅" if youtube_available else "❌"
            youtube_text = "YouTube verfügbar" if youtube_available else "Nur auf Deezer"
            
            # Erstelle Frame für jedes Album
            album_frame = ttk.Frame(scrollable_frame)
            album_frame.pack(fill=tk.X, padx=8, pady=4)
            
            # Checkbox
            checkbox = ttk.Checkbutton(
                album_frame,
                variable=var
            )
            checkbox.pack(side=tk.LEFT, padx=(0, 10))
            
            # Album-Info Frame
            info_frame = ttk.Frame(album_frame)
            info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Album-Titel
            title_label = ttk.Label(
                info_frame,
                text=f"💿 {album_title}",
                font=("Arial", 11, "bold")
            )
            title_label.pack(anchor=tk.W)
            
            # Zusätzliche Info
            info_text = f"👤 {artist_name}"
            if nb_tracks > 0:
                info_text += f" • {nb_tracks} Track(s)"
            if release_date:
                info_text += f" • {release_date[:4]}"
            
            info_label = ttk.Label(
                info_frame,
                text=info_text,
                font=("Arial", 9),
                foreground="gray"
            )
            info_label.pack(anchor=tk.W)
            
            # YouTube-Status
            youtube_label = ttk.Label(
                info_frame,
                text=f"{youtube_icon} {youtube_text}",
                font=("Arial", 9),
                foreground="green" if youtube_available else "orange"
            )
            youtube_label.pack(anchor=tk.W, pady=(2, 0))
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Buttons-Bereich
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Linke Seite: Auswahl-Buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)
        
        def select_all():
            for var in album_vars.values():
                var.set(True)
            update_button_text()
        
        def select_none():
            for var in album_vars.values():
                var.set(False)
            update_button_text()
        
        def select_youtube_only():
            for i, album in enumerate(albums):
                if i in album_vars:
                    album_vars[i].set(album.get('youtube_available', False))
            update_button_text()
        
        ttk.Button(left_buttons, text="✓ Alle auswählen", command=select_all).pack(side=tk.LEFT, padx=3)
        ttk.Button(left_buttons, text="✓ Nur YouTube", command=select_youtube_only).pack(side=tk.LEFT, padx=3)
        ttk.Button(left_buttons, text="✗ Alle abwählen", command=select_none).pack(side=tk.LEFT, padx=3)
        
        # Rechte Seite: Download und Abbrechen-Buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)
        
        selected_albums = []
        
        def confirm():
            nonlocal selected_albums
            # Sammle alle ausgewählten Alben
            for i, album in enumerate(albums):
                if i in album_vars and album_vars[i].get():
                    selected_albums.append(album)
            
            if not selected_albums:
                messagebox.showwarning("Warnung", "Bitte wählen Sie mindestens ein Album aus.")
                return
            selection_window.destroy()
        
        def cancel():
            nonlocal selected_albums
            selected_albums = None
            selection_window.destroy()
        
        # Zähle ausgewählte Alben für Button-Text
        def update_button_text():
            count = sum(1 for var in album_vars.values() if var.get())
            confirm_button.config(text=f"▶ Download ({count} Album(s))")
        
        confirm_button = ttk.Button(right_buttons, text="▶ Download (0 Album(s))", command=confirm)
        confirm_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(right_buttons, text="❌ Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # Aktualisiere Button-Text bei Änderungen
        for var in album_vars.values():
            var.trace_add("write", lambda *args: update_button_text())
        
        selection_window.wait_window()
        return selected_albums
    
    def _show_audiobook_search_option(self, albums: List[Dict], artist_name: str):
        """Zeigt Option zur Multi-Anbieter-Suche für Hörbücher"""
        try:
            from audiobook_search import AudiobookSearch
            from tkinter import messagebox
            
            # Frage ob nach alternativen Anbietern gesucht werden soll
            album_titles = [album.get('title', 'Unbekannt') for album in albums[:3]]  # Erste 3 Alben
            titles_text = '\n'.join(f"  • {title}" for title in album_titles)
            if len(albums) > 3:
                titles_text += f"\n  ... und {len(albums) - 3} weitere"
            
            response = messagebox.askyesno(
                "Hörbuch erkannt",
                f"Es wurden Hörbücher erkannt:\n{titles_text}\n\n"
                f"Möchten Sie prüfen, ob diese Hörbücher auf anderen Plattformen verfügbar sind?\n"
                f"(YouTube, Audible, Spotify, Storytel, Nextory, BookBeat)\n\n"
                f"Dies kann einige Minuten dauern.",
                icon='question'
            )
            
            if response:
                # Starte Suche in separatem Thread
                import threading
                search_thread = threading.Thread(
                    target=self._search_audiobooks_thread,
                    args=(albums, artist_name),
                    daemon=True
                )
                search_thread.start()
        
        except ImportError:
            pass  # audiobook_search nicht verfügbar
        except Exception as e:
            print(f"Fehler bei Hörbuch-Suche: {e}")
    
    def _search_audiobooks_thread(self, albums: List[Dict], artist_name: str):
        """Thread für Multi-Anbieter-Suche"""
        try:
            from audiobook_search import AudiobookSearch
            
            searcher = AudiobookSearch()
            
            for album in albums:
                album_title = album.get('title', 'Unbekannt')
                self.music_log(f"\n🔍 Suche nach alternativen Anbietern für: {album_title}")
                
                # Entferne "Kapitel" und ähnliche Präfixe
                import re
                cleaned_title = re.sub(r'^.*? - ', '', album_title, count=1)  # Entferne alles vor " - "
                cleaned_title = re.sub(r'\(.*?\)', '', cleaned_title).strip()  # Entferne Klammern
                
                # Suche auf allen Plattformen
                results = searcher.search_all_providers(cleaned_title, artist_name)
                
                # Zeige Ergebnisse - nur herunterladbare Anbieter
                downloadable_providers = [p for p, d in results.items() 
                                         if d.get('available', False) and d.get('downloadable', False)]
                no_drm_providers = [p for p in downloadable_providers if not results[p].get('drm', False)]
                drm_providers = [p for p in downloadable_providers if results[p].get('drm', False)]
                
                if downloadable_providers:
                    # Zeige detaillierte Informationen
                    provider_info = []
                    for provider in downloadable_providers:
                        info = results[provider]
                        method = info.get('method', 'unknown')
                        has_drm = info.get('drm', False)
                        status = "✅ Kein DRM" if not has_drm else "🔓 DRM (Umgehung möglich)"
                        provider_info.append(f"{provider} ({status})")
                    
                    self.music_log(f"  ✅ Verfügbar und herunterladbar auf:")
                    for info in provider_info:
                        self.music_log(f"     • {info}")
                    
                    if no_drm_providers:
                        self.music_log(f"  📥 Empfohlen (kein DRM): {', '.join(no_drm_providers)}")
                    
                    # Frage ob von alternativem Anbieter heruntergeladen werden soll
                    self.root.after(0, lambda p=downloadable_providers, t=cleaned_title, a=artist_name, s=searcher, r=results: 
                        self._ask_download_from_alternative(p, t, a, s, r))
                else:
                    self.music_log(f"  ❌ Nicht auf anderen Plattformen verfügbar (oder nicht herunterladbar)")
        
        except ImportError:
            self.music_log("⚠️ Multi-Anbieter-Suche nicht verfügbar (audiobook_search.py fehlt)")
        except Exception as e:
            self.music_log(f"❌ Fehler bei Multi-Anbieter-Suche: {e}")
    
    def _ask_download_from_alternative(self, providers: List[str], title: str, artist: str, searcher, results: Dict):
        """Fragt ob von alternativem Anbieter heruntergeladen werden soll"""
        try:
            from tkinter import messagebox
            
            # Erstelle detaillierte Anbieter-Liste
            provider_details = []
            no_drm_list = []
            drm_list = []
            
            for provider in providers:
                info = results.get(provider, {})
                has_drm = info.get('drm', False)
                method = info.get('method', 'unknown')
                
                if not has_drm:
                    no_drm_list.append(provider)
                    provider_details.append(f"  ✅ {provider} (kein DRM, direkter Download)")
                else:
                    drm_list.append(provider)
                    method_text = {
                        'aax-decrypt': 'AAX-Entschlüsselung',
                        'audio-recording': 'Audio-Aufnahme',
                        'yt-dlp': 'yt-dlp',
                        'direct': 'Direkter Download'
                    }.get(method, method)
                    provider_details.append(f"  🔓 {provider} (DRM, {method_text})")
            
            details_text = '\n'.join(provider_details)
            recommendation = f"Empfohlen: {', '.join(no_drm_list)}" if no_drm_list else f"Verfügbar: {', '.join(providers)}"
            
            response = messagebox.askyesno(
                "Alternativer Anbieter gefunden",
                f"'{title}' ist verfügbar auf:\n{details_text}\n\n"
                f"{recommendation}\n\n"
                f"Möchten Sie von einem dieser Anbieter herunterladen?",
                icon='question'
            )
            
            if response:
                # Lade vom besten Anbieter herunter (Priorität: kein DRM > DRM)
                import threading
                download_thread = threading.Thread(
                    target=lambda: searcher.download_from_best_provider(title, artist, Path(self.music_download_path)),
                    daemon=True
                )
                download_thread.start()
        
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Starten des Downloads: {e}")
    
    def download_selected_tracks(self, tracks: List[Dict], context_type: str = 'track', 
                                 context_name: str = '', artist_name: str = '') -> int:
        """
        Lädt ausgewählte Tracks herunter mit strukturierter Ordnerstruktur
        
        Args:
            tracks: Liste von Track-Dictionaries
            context_type: Typ des Kontexts ('artist', 'album', 'playlist', 'track')
            context_name: Name des Kontexts (Album-Name, Playlist-Name, etc.)
            artist_name: Name des Künstlers
            
        Returns:
            Anzahl erfolgreich heruntergeladener Tracks
        """
        downloaded = 0
        total = len(tracks)
        
        # Erstelle Ordnerstruktur basierend auf Kontext
        # Struktur: platform/künstlername/album-name oder platform/künstlername/playlist-name
        base_path = self.music_download_path
        
        for i, track in enumerate(tracks, 1):
            track_id = str(track.get('id', ''))
            track_name = track.get('title', 'Unbekannt')
            
            if not track_id:
                continue
            
            # Bestimme Künstlername für diesen Track (falls nicht übergeben)
            track_artist = track.get('artist', {}).get('name', artist_name) if isinstance(track.get('artist'), dict) else artist_name
            if not track_artist:
                track_artist = 'Unbekannt'
            
            # Erstelle Ordnerstruktur
            output_dir = self._create_music_folder_structure(
                base_path=base_path,
                context_type=context_type,
                context_name=context_name,
                artist_name=track_artist
            )
            
            self.music_log(f"[{i}/{total}] Lade herunter: {track_name}")
            
            result = self.downloader.download_track(
                track_id,
                output_dir=output_dir,
                use_youtube_fallback=True
            )
            
            if result.success:
                downloaded += 1
        
        return downloaded
    
    def _create_music_folder_structure(self, base_path: Path, context_type: str, 
                                      context_name: str, artist_name: str) -> Path:
        """
        Erstellt die Ordnerstruktur für Musik-Downloads
        
        Struktur:
        - Artist: platform/künstlername/
        - Album: platform/künstlername/album-name/
        - Playlist: platform/künstlername/playlist-name/
        - Track: platform/künstlername/
        
        Args:
            base_path: Basis-Pfad für Downloads
            context_type: Typ des Kontexts ('artist', 'album', 'playlist', 'track')
            context_name: Name des Kontexts (Album-Name, Playlist-Name, etc.)
            artist_name: Name des Künstlers
            
        Returns:
            Path zum Download-Verzeichnis (ohne Plattform-Ordner, wird in download_track hinzugefügt)
        """
        # Bereinige Namen für Dateisystem
        def sanitize(name: str) -> str:
            # Entferne ungültige Zeichen für Dateinamen
            import re
            name = re.sub(r'[<>:"/\\|?*]', '', name)
            name = name.strip()
            return name or 'Unbekannt'
        
        artist_clean = sanitize(artist_name)
        
        # Erstelle Pfad ohne Plattform-Ordner (wird in download_track basierend auf Quelle hinzugefügt)
        if context_type == 'album' and context_name:
            # Album: künstlername/album-name (Plattform wird später hinzugefügt)
            folder_path = base_path / artist_clean / sanitize(context_name)
        elif context_type == 'playlist' and context_name:
            # Playlist: künstlername/playlist-name (Plattform wird später hinzugefügt)
            folder_path = base_path / artist_clean / sanitize(context_name)
        else:
            # Artist oder Track: künstlername (Plattform wird später hinzugefügt)
            folder_path = base_path / artist_clean
        
        folder_path.mkdir(parents=True, exist_ok=True)
        return folder_path
    
    def video_download_episodes_thread(self, episodes: List[Dict]):
        """Download-Thread für mehrere Episoden"""
        try:
            # Setze Gesamtanzahl Episoden für Abbruch-Dialog (sollte bereits gesetzt sein, aber zur Sicherheit nochmal)
            episodes_count = len(episodes)
            self.video_download_episodes_total = episodes_count
            self.video_download_cancel_current_only = False
            print(f"[DEBUG] video_download_episodes_thread: Setze episodes_total={episodes_count}")
            self.video_log(f"[DEBUG] Thread gestartet: episodes_total={episodes_count}")
            
            # Wechsle zum Video-Tab für Logs
            self.notebook.select(self.notebook.index(self.video_frame))
            
            self.video_log("=" * 60)
            self.video_log(f"Starte Download von {len(episodes)} Folgen")
            format_display = self.video_format_var.get().upper() if self.video_format_var.get() != "none" else "Keine"
            self.video_log(f"Format: {format_display}")
            self.video_log(f"Qualität: {self.video_quality_var.get()}")
            self.video_log(f"Ziel: {self.video_download_path}")
            self.video_log("=" * 60)
            
            success_count = 0
            failed_count = 0
            
            for i, episode in enumerate(episodes, 1):
                url = episode.get('url')
                if not url:
                    self.video_log(f"\n[{i}/{len(episodes)}] ⚠ Keine URL für Episode: {episode.get('title', 'Unbekannt')}")
                    failed_count += 1
                    continue
                
                title = episode.get('title', 'Unbekannt')
                series_name = episode.get('series')
                season_number = episode.get('season_number')
                
                # Wenn erste Episode startet, füge restliche Episoden zur Queue hinzu
                if i == 1 and len(episodes) > 1:
                    remaining_episodes = episodes[1:]  # Alle außer der ersten
                    self.video_log(f"\n📋 Füge {len(remaining_episodes)} weitere Folgen zur Queue hinzu...")
                    # Batch-Serie: am Ende eine gemeinsame Erfolgsmeldung für alle Folgen
                    self.video_download_batch_series_total = len(episodes)
                    self.video_download_batch_series_success = 1  # erste gerade am Laden
                    for remaining_episode in remaining_episodes:
                        remaining_url = remaining_episode.get('url')
                        if remaining_url:
                            # Erstelle Episode-Info für Queue-Eintrag
                            remaining_episode_info = {
                                'title': remaining_episode.get('title', 'Unbekannt'),
                                'series_name': remaining_episode.get('series', series_name),
                                'series': remaining_episode.get('series', series_name),
                                'season_number': remaining_episode.get('season_number', season_number),
                                'episode_number': remaining_episode.get('episode_number'),
                                'playlist_index': remaining_episode.get('playlist_index'),
                                'broadcast_date': remaining_episode.get('broadcast_date') or '',
                                'upload_date': remaining_episode.get('upload_date') or '',
                                'url': remaining_url,
                                'id': remaining_episode.get('id'),
                                'kind': remaining_episode.get('kind') or '',
                                'output_format': (remaining_episode.get('output_format') or '').lower(),
                            }
                            # Füge zur Queue hinzu ohne Dialog
                            self._add_to_download_queue(remaining_url, episode_info=remaining_episode_info, show_dialog=False)
                    self.video_log(f"✓ {len(remaining_episodes)} Folgen zur Queue hinzugefügt")
                    self._update_queue_status()
                    
                    # WICHTIG: Setze episodes_total auf 1, damit nur die erste Episode in dieser Schleife heruntergeladen wird
                    # Die restlichen werden über die Queue verarbeitet
                    original_episodes_total = self.video_download_episodes_total
                    self.video_download_episodes_total = 1  # Nur noch eine Episode in dieser Schleife
                
                self.video_log(f"\n[{i}/{len(episodes)}] Lade herunter: {title}")
                if series_name:
                    self.video_log(f"  Serie: {series_name}, Staffel: {season_number or 1}")
                
                # Fortschritt für diese Episode (0–100%), Anzeige mit Episoden-Zähler
                def progress_callback(percent, status_line):
                    """Callback für Fortschritts-Updates (Download und Konvertierung) – Main-Thread"""
                    if series_watch is not None:
                        try:
                            pending_rest = [
                                {
                                    "title": (x.get("title") or "")[:80],
                                    "series": (x.get("series") or x.get("series_name") or series_name or "")[:60],
                                }
                                for x in episodes[i:]
                            ]
                            series_watch.set_download_progress(
                                self.base_download_path,
                                title=title,
                                series=series_name or "",
                                percent=percent,
                                index=i,
                                total=len(episodes),
                                pending=pending_rest,
                            )
                            if series_watch.is_download_cancel_requested(self.base_download_path):
                                self.video_download_cancelled = True
                        except Exception:
                            pass
                    def _update():
                        try:
                            # Fortschrittsbalken zeigt immer den Fortschritt der aktuellen Episode (0–100%)
                            self.video_progress_var.set(percent)
                            if status_line and "Konvertierung" in status_line:
                                self.video_status_var.set(f"{status_line} ({i}/{len(episodes)})")
                            else:
                                speed_str = ""
                                eta_str = ""
                                if status_line:
                                    speed_match = re.search(r'at\s+([\d.]+)\s*([KMGT]?i?B/s)', status_line, re.IGNORECASE)
                                    if speed_match:
                                        speed_str = f" - {speed_match.group(1)}{speed_match.group(2)}"
                                    eta_match = re.search(r'ETA\s+(\d+:\d+)', status_line)
                                    if eta_match:
                                        eta_str = f" - ETA: {eta_match.group(1)}"
                                status_text = f"Download läuft... {percent:.1f}% ({i}/{len(episodes)}){speed_str}{eta_str}"
                                self.video_status_var.set(status_text)
                            self.root.update_idletasks()
                        except Exception:
                            pass
                    self.root.after(0, _update)
                
                # Hole Video-Info für diese Episode
                episode_info = self.video_downloader.get_video_info(url) or {}
                if episode.get('title'):
                    episode_info['title'] = episode.get('title')
                if episode.get('series') or series_name:
                    episode_info['series'] = episode.get('series') or series_name
                if episode.get('season_number') is not None or season_number is not None:
                    episode_info['season_number'] = episode.get('season_number') if episode.get('season_number') is not None else season_number
                if episode.get('episode_number') is not None:
                    episode_info['episode_number'] = episode.get('episode_number')
                if episode.get('broadcast_date') or episode.get('upload_date'):
                    episode_info['broadcast_date'] = episode.get('broadcast_date') or episode_info.get('broadcast_date') or ''
                    episode_info['upload_date'] = episode.get('upload_date') or episode_info.get('upload_date') or ''
                
                # Geschwindigkeits-Limit (aus Einstellungen)
                speed_limit = None
                if self.settings.get('speed_limit_enabled', False):
                    try:
                        speed_limit = float(self.settings.get('speed_limit_value', '5'))
                    except ValueError:
                        speed_limit = None
                
                # Prüfe erneut auf Abbruch vor dem Download
                if self.video_download_cancelled:
                    self.video_log(f"\n⚠ Download wurde abgebrochen")
                    break
                
                # Prüfe ob nur aktuelle Folge abgebrochen werden soll
                if self.video_download_cancel_current_only:
                    self.video_log(f"\n⚠ Aktuelle Folge wird übersprungen")
                    self.video_download_cancel_current_only = False
                    continue  # Überspringe aktuelle Folge, aber lade nächste
                
                success, file_path, error = self.video_downloader.download_video(
                        url,
                        output_dir=self.music_download_path if str(episode.get('output_format') or '').lower() == 'mp3' else self.video_download_path,
                        quality=self.video_quality_var.get(),
                        output_format=(episode.get('output_format') or self.video_format_var.get() or 'mp4'),
                        download_playlist=False,
                        progress_callback=progress_callback,
                        video_info=episode_info,
                        is_series=True,
                        series_name=series_name,
                        season_number=season_number,
                        playlist_index=episode.get('playlist_index') or episode.get('episode_number'),
                        download_subtitles=self.video_subtitle_var.get(),
                        subtitle_language=self.video_subtitle_lang_var.get(),
                        download_description=self.video_description_var.get(),
                        download_thumbnail=self.video_thumbnail_var.get(),
                        resume_download=self.video_resume_var.get(),
                        speed_limit=speed_limit,
                        embed_metadata=True,  # Immer aktiviert
                        gui_instance=self,
                        gpu_enabled=self.settings.get('gpu_enabled', False),
                        gpu_vendor=self.settings.get('gpu_vendor', 'auto')
                    )
                
                # Prüfe auf Abbruch nach dem Download
                if self.video_download_cancelled:
                    self.video_log(f"\n⚠ Download wurde abgebrochen")
                    # Räume auf: Lösche unvollständige Dateien der aktuellen Episode
                    if not success and episode_info:
                        try:
                            # Versuche Output-Verzeichnis zu finden und aufzuräumen
                            from pathlib import Path
                            output_dir = self.video_download_path
                            if series_name:
                                series_dir = output_dir / series_name
                                if season_number:
                                    season_dir = series_dir / f"Staffel {season_number}"
                                    if season_dir.exists():
                                        # Lösche temporäre/unvollständige Dateien
                                        for temp_file in season_dir.glob('*.part'):
                                            try:
                                                temp_file.unlink()
                                            except:
                                                pass
                                        for temp_file in season_dir.glob('*.ytdl'):
                                            try:
                                                temp_file.unlink()
                                            except:
                                                pass
                        except:
                            pass
                    break
                
                # Prüfe ob nur aktuelle Folge abgebrochen werden soll
                if self.video_download_cancel_current_only:
                    self.video_log(f"\n⚠ Aktuelle Folge wurde abgebrochen, überspringe restliche Folgen")
                    # Setze Flag zurück, damit nächste Folge normal läuft
                    self.video_download_cancel_current_only = False
                    # Räume auf: Lösche unvollständige Dateien der aktuellen Episode
                    if not success and episode_info:
                        try:
                            from pathlib import Path
                            output_dir = self.video_download_path
                            if series_name:
                                series_dir = output_dir / series_name
                                if season_number:
                                    season_dir = series_dir / f"Staffel {season_number}"
                                    if season_dir.exists():
                                        for temp_file in season_dir.glob('*.part'):
                                            try:
                                                temp_file.unlink()
                                            except:
                                                pass
                                        for temp_file in season_dir.glob('*.ytdl'):
                                            try:
                                                temp_file.unlink()
                                            except:
                                                pass
                        except:
                            pass
                    continue  # Überspringe aktuelle Folge, aber lade nächste
                
                ep_kind = "music" if self._queue_item_is_audio(episode, url) else "video"
                if success:
                    if file_path:
                        self.video_log(f"  ✓ Erfolgreich: {file_path.name}")
                        success_count += 1
                    else:
                        self.video_log(f"  ⚠ Download scheint erfolgreich, aber Datei nicht gefunden")
                        success_count += 1
                    self._update_statistics(success=True, file_path=file_path, url=url, kind=ep_kind)
                    self._series_watch_mark_downloaded(url, episode_id=episode.get('id'))
                else:
                    self.video_log(f"  ✗ Fehlgeschlagen: {error}")
                    failed_count += 1
                    if error != "Abgebrochen":
                        self._update_statistics(success=False, file_path=None, url=url, kind=ep_kind, error=error)
                
                # Wenn erste Episode heruntergeladen wurde und restliche zur Queue hinzugefügt wurden,
                # beende die Schleife hier, damit die restlichen Episoden über die Queue verarbeitet werden
                if i == 1 and len(episodes) > 1:
                    self.video_log(f"\n📋 Erste Episode heruntergeladen. Restliche {len(episodes) - 1} Folgen werden über Queue verarbeitet.")
                    # Setze episodes_total zurück, damit Queue starten kann
                    self.video_download_episodes_total = 0
                    break  # Beende Schleife, restliche Episoden werden über Queue verarbeitet
            
            # Zusammenfassung
            self.video_log("\n" + "=" * 60)
            
            # Prüfe ob Download abgebrochen wurde
            if self.video_download_cancelled:
                self.video_log(f"⚠ Download wurde abgebrochen")
                self.video_log(f"Heruntergeladen: {success_count}/{len(episodes)} Folgen")
                self.video_log("=" * 60)
                
                self.video_status_var.set("⚠ Download abgebrochen")
                
                # Zeige Popup-Fenster für Abbruch
                messagebox.showwarning(
                    "Download abgebrochen",
                    f"Der Download wurde abgebrochen.\n\n"
                    f"Heruntergeladen: {success_count}/{len(episodes)} Folgen"
                )
            else:
                self.video_log(f"Download abgeschlossen: {success_count}/{len(episodes)} Folgen erfolgreich")
                if failed_count > 0:
                    self.video_log(f"Fehlgeschlagen: {failed_count} Folgen")
                self.video_log("=" * 60)
                
                self.video_status_var.set(f"✓ Download abgeschlossen: {success_count}/{len(episodes)} Folgen")
                
                # Erfolgs-Dialog nur wenn alle Folgen in dieser Schleife liefen (nicht bei Rest in Queue)
                # Sonst kommt die Meldung am Ende der Queue (_show_batch_series_success)
                queue_count = len(getattr(self, 'video_download_queue', []))
                all_done_in_loop = (success_count + failed_count) == len(episodes)
                if queue_count == 0 and all_done_in_loop:
                    def _show_series_success_autoclose():
                        self._show_system_notification(
                            "Download abgeschlossen",
                            f"Erfolgreich: {success_count}/{len(episodes)} Folgen. Fehlgeschlagen: {failed_count}.",
                        )
                    self.root.after(0, _show_series_success_autoclose)
            
        except Exception as e:
            self.video_log(f"\n✗ Fehler: {e}")
            import traceback
            self.video_log(traceback.format_exc())
            self.video_status_var.set(f"✗ Fehler: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Download: {e}")
        finally:
            # Reset Variablen NUR wenn Download komplett beendet ist
            # NICHT zurücksetzen während des Downloads, sonst funktioniert der Dialog nicht!
            # self.video_download_episodes_total = 0  # Wird später zurückgesetzt
            # self.video_download_cancel_current_only = False  # Wird später zurückgesetzt
            if series_watch is not None:
                try:
                    series_watch.clear_download_status(self.base_download_path)
                except Exception:
                    pass
            
            # UI wieder aktivieren
            self.video_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.DISABLED)
            self.video_download_process = None
            
            if self.video_download_cancelled:
                self.video_status_var.set("Download abgebrochen")
                self.video_progress_var.set(0)
            else:
                self.video_progress_var.set(100)
                if self.video_status_var.get().startswith("Download läuft"):
                    self.video_status_var.set("Bereit")
            
            # Reset Variablen ZUERST, damit _process_download_queue erkennt, dass Download beendet ist
            self.video_download_episodes_total = 0
            self.video_download_cancel_current_only = False
            
            # Queue-Verarbeitung: bei YouTube 2 s Pause, um Rate-Limit zu vermeiden
            last_url = getattr(self, '_last_video_download_url', '') or ''
            delay_ms = 2000 if last_url and ('youtube.com' in last_url.lower() or 'youtu.be' in last_url.lower()) else 0
            if delay_ms:
                self.video_log("  Pause 2 s (YouTube Rate-Limit-Schutz)…")
            self.root.after(delay_ms, self._process_download_queue)
    
    def _setup_logging(self):
        """Richtet File-Logging ein"""
        try:
            # Erstelle Logs-Verzeichnis
            logs_dir = self.base_download_path / "Logs"
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                # Fallback: Verwende AppData oder Temp
                if sys.platform == "win32":
                    appdata = os.getenv('APPDATA', Path.home() / "AppData" / "Roaming")
                    logs_dir = Path(appdata) / "Universal Downloader" / "Logs"
                else:
                    logs_dir = Path.home() / ".universal-downloader" / "Logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                print(f"[WARNING] Konnte Log-Ordner nicht im Standard-Pfad erstellen, verwende: {logs_dir}")
            
            # Prüfe ob Ordner wirklich existiert
            if not logs_dir.exists():
                raise Exception(f"Log-Ordner konnte nicht erstellt werden: {logs_dir}")
            
            # Erstelle Log-Datei mit Timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            log_filename = logs_dir / f"universal_downloader_{timestamp}.log"
            self.log_file = open(log_filename, 'w', encoding='utf-8')
            self._write_to_log_file(f"=== Universal Downloader gestartet ===", "INFO")
            self._write_to_log_file(f"Log-Datei: {log_filename}", "INFO")
            self._write_to_log_file(f"Download-Pfad: {self.base_download_path}", "INFO")
        except Exception as e:
            print(f"[ERROR] Konnte Log-Datei nicht erstellen: {e}")
            import traceback
            print(f"[ERROR] Traceback: {traceback.format_exc()}")
            self.log_file = None
    
    def _write_to_log_file(self, message: str, level: str = "INFO"):
        """
        Schreibt eine Nachricht in die Log-Datei
        
        Args:
            message: Die Log-Nachricht
            level: Log-Level ('INFO', 'DEBUG', 'WARNING', 'ERROR')
        """
        if self.log_file:
            try:
                # Prüfe Log-Level-Einstellung
                log_level_setting = self.settings.get('log_level', 'debug')
                
                # In normalem Modus: Überspringe DEBUG-Logs
                if log_level_setting == 'normal' and level == 'DEBUG':
                    return
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_entry = f"[{timestamp}] [{level}] {message}\n"
                self.log_file.write(log_entry)
                self.log_file.flush()  # Sofort schreiben
            except:
                pass
    
    def _cleanup_old_logs(self):
        """Löscht alte Log-Dateien basierend auf Einstellungen"""
        try:
            if not self.settings.get('log_cleanup_enabled', False):
                return
            
            log_cleanup_days = self.settings.get('log_cleanup_days', 30)
            logs_dir = self.base_download_path / "Logs"
            
            if not logs_dir.exists():
                return
            
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=log_cleanup_days)
            
            deleted_count = 0
            for log_file in logs_dir.glob("*.log"):
                try:
                    # Prüfe Änderungsdatum der Datei
                    mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        log_file.unlink()
                        deleted_count += 1
                except Exception as e:
                    if hasattr(self, '_write_to_log_file'):
                        self._write_to_log_file(f"Fehler beim Löschen von {log_file.name}: {e}")
            
            if deleted_count > 0 and hasattr(self, '_write_to_log_file'):
                self._write_to_log_file(f"✓ {deleted_count} alte Log-Datei(en) gelöscht (älter als {log_cleanup_days} Tage)")
        except Exception as e:
            if hasattr(self, '_write_to_log_file'):
                self._write_to_log_file(f"Fehler beim Aufräumen der Logs: {e}")
    
    def _cleanup_logs_on_exit(self):
        """Löscht alle Logs beim Beenden (wenn aktiviert)"""
        try:
            if not self.settings.get('log_cleanup_on_exit', False):
                return
            
            logs_dir = self.base_download_path / "Logs"
            if not logs_dir.exists():
                return
            
            deleted_count = 0
            for log_file in logs_dir.glob("*.log"):
                try:
                    log_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    pass
            
            if deleted_count > 0:
                print(f"✓ {deleted_count} Log-Datei(en) beim Beenden gelöscht")
        except Exception as e:
            pass
    
    def _close_log_file(self):
        """Schließt die Log-Datei"""
        if hasattr(self, 'log_file') and self.log_file:
            try:
                self._write_to_log_file("=== Universal Downloader beendet ===")
                self.log_file.close()
                self.log_file = None
            except:
                pass
        
        # Führe Log-Aufräumen beim Beenden aus
        self._cleanup_logs_on_exit()
    
    def _update_subtitle_language_state(self):
        """Aktiviert/Deaktiviert die Untertitel-Sprache-Auswahl"""
        if hasattr(self, 'subtitle_lang_combo'):
            enabled = self.video_subtitle_var.get()
            self.subtitle_lang_combo.config(state="readonly" if enabled else "disabled")
    
    def _update_speed_limit_state(self):
        """Aktiviert/Deaktiviert die Geschwindigkeits-Limit-Eingabe"""
        if hasattr(self, 'speed_entry'):
            enabled = self.video_speed_limit_var.get()
            self.speed_entry.config(state="normal" if enabled else "disabled")
    
    def _update_video_tab_visibility(self):
        """Aktualisiert die Sichtbarkeit von Optionen basierend auf Einstellungen"""
        # Untertitel-Frame anzeigen/verstecken
        if hasattr(self, 'subtitle_frame'):
            if self.settings.get('subtitle_enabled_by_default', False):
                self.subtitle_frame.pack(fill=tk.X, padx=5, pady=5)
            else:
                self.subtitle_frame.pack_forget()
        
    
    def _extract_text_from_document(self, filepath: str) -> Optional[str]:
        """Extrahiert Text aus verschiedenen Dokumentformaten (RTF, DOCX, DOC, ODT, XML, CSV)."""
        path = Path(filepath)
        ext = path.suffix.lower()
        
        # CSV
        if ext == '.csv':
            try:
                import csv
                text_lines = []
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        text_lines.append(' '.join(row))
                return '\n'.join(text_lines)
            except Exception as e:
                print(f"[WARN] CSV-Parsing fehlgeschlagen: {e}")
                return None
        
        # RTF
        if ext == '.rtf':
            try:
                from striprtf import striprtf
                with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                    rtf_content = f.read()
                    return striprtf(rtf_content)
            except ImportError:
                try:
                    # Fallback: einfaches RTF-Parsing (entfernt RTF-Steuerzeichen grob)
                    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                    import re
                    # Entferne RTF-Steuerwörter und -Gruppen grob
                    content = re.sub(r'\\[a-z]+\d*\s?', '', content)
                    content = re.sub(r'\{[^}]*\}', '', content)
                    return content
                except Exception as e:
                    print(f"[WARN] RTF-Parsing fehlgeschlagen: {e}")
                    return None
            except Exception as e:
                print(f"[WARN] RTF-Parsing fehlgeschlagen: {e}")
                return None
        
        # DOCX (Word 2007+)
        if ext == '.docx':
            try:
                from docx import Document
                doc = Document(filepath)
                paragraphs = [p.text for p in doc.paragraphs]
                tables_text = []
                for table in doc.tables:
                    for row in table.rows:
                        cells = [cell.text for cell in row.cells]
                        tables_text.append(' '.join(cells))
                all_text = '\n'.join(paragraphs + tables_text)
                return all_text
            except ImportError:
                messagebox.showwarning(
                    "Bibliothek fehlt",
                    "Für DOCX-Dateien wird 'python-docx' benötigt.\n\n"
                    "Installation: pip install python-docx"
                )
                return None
            except Exception as e:
                print(f"[WARN] DOCX-Parsing fehlgeschlagen: {e}")
                return None
        
        # DOC (Word 97-2003) - benötigt textract oder antiword
        if ext == '.doc':
            try:
                import textract
                text = textract.process(filepath).decode('utf-8', errors='replace')
                return text
            except ImportError:
                try:
                    # Fallback: python-docx2txt
                    import docx2txt
                    text = docx2txt.process(filepath)
                    return text
                except ImportError:
                    messagebox.showwarning(
                        "Bibliothek fehlt",
                        "Für DOC-Dateien wird 'textract' oder 'docx2txt' benötigt.\n\n"
                        "Installation: pip install textract\n"
                        "oder: pip install docx2txt"
                    )
                    return None
            except Exception as e:
                print(f"[WARN] DOC-Parsing fehlgeschlagen: {e}")
                return None
        
        # ODT (OpenDocument Text)
        if ext == '.odt':
            try:
                from odf.opendocument import load
                from odf.text import P
                from odf.teletype import extractText
                doc = load(filepath)
                paragraphs = []
                for para in doc.getElementsByType(P):
                    paragraphs.append(extractText(para))
                return '\n'.join(paragraphs)
            except ImportError:
                messagebox.showwarning(
                    "Bibliothek fehlt",
                    "Für ODT-Dateien wird 'odfpy' benötigt.\n\n"
                    "Installation: pip install odfpy"
                )
                return None
            except Exception as e:
                print(f"[WARN] ODT-Parsing fehlgeschlagen: {e}")
                return None
        
        # XML (Word 2003 XML)
        if ext == '.xml':
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(filepath)
                root = tree.getroot()
                # Einfache Text-Extraktion aus XML
                text_parts = []
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        text_parts.append(elem.text.strip())
                return '\n'.join(text_parts)
            except Exception as e:
                print(f"[WARN] XML-Parsing fehlgeschlagen: {e}")
                return None
        
        return None
    
    def load_urls_from_file(self):
        """Lädt URLs aus einer Textdatei oder Dokument (RTF, DOCX, DOC, ODT, XML, CSV).
        Es werden alle vorkommenden http(s)://-URLs extrahiert.
        Film-/Seriennamen, Trennzeichen (z.B. -------------) und Kommentare (#) werden ignoriert."""
        filename = filedialog.askopenfilename(
            title="URLs aus Datei laden",
            filetypes=[
                ("Textdateien", "*.txt"),
                ("CSV-Dateien", "*.csv"),
                ("RTF-Dokumente", "*.rtf"),
                ("Word 2007+ (.docx)", "*.docx"),
                ("Word 97-2003 (.doc)", "*.doc"),
                ("Word 2003 XML (.xml)", "*.xml"),
                ("OpenDocument Text (.odt)", "*.odt"),
                ("Alle unterstützten Formate", "*.txt;*.csv;*.rtf;*.docx;*.doc;*.xml;*.odt"),
                ("Alle Dateien", "*.*")
            ]
        )
        if filename:
            try:
                path = Path(filename)
                ext = path.suffix.lower()
                
                # Spezielle Formate über Hilfsfunktion
                if ext in ('.csv', '.rtf', '.docx', '.doc', '.odt', '.xml'):
                    text = self._extract_text_from_document(filename)
                    if text is None:
                        messagebox.showerror("Fehler", f"Konnte Text aus {ext}-Datei nicht extrahieren.")
                        return
                else:
                    # Normale Textdatei
                    with open(filename, 'rb') as f:
                        raw = f.read()
                    try:
                        text = raw.decode('utf-8')
                    except UnicodeDecodeError:
                        text = raw.decode('latin-1')
                # Alle http:// und https:// URLs aus dem Text extrahieren; Zeilen mit # (Kommentar) bzw. Inline-# ignorieren
                url_pattern = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
                all_urls = []
                for line in text.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    # Inline-Kommentare (# ...) ignorieren
                    if '#' in line:
                        line = line.split('#')[0].strip()
                        if not line:
                            continue
                    for match in url_pattern.finditer(line):
                        url = match.group(0).rstrip('.,;:)')
                        if url not in all_urls:
                            all_urls.append(url)
                # Im Video-Tab: Audio-Mediatheken/Hörbuch-URLs ausfiltern (nur im Musik-Tab unterstützt)
                urls = [u for u in all_urls if not _is_music_mediathek_url(u)]
                skipped_mediathek = len(all_urls) - len(urls)
                if urls:
                    msg = f"{len(urls)} Video-URL(s) gefunden."
                    if skipped_mediathek:
                        msg += f"\n\n{skipped_mediathek} Mediatheken-/Hörbuch-URL(s) übersprungen (bitte im Tab „Musik“ verwenden)."
                    msg += "\n\nSoll die Queue mit diesen URLs gefüllt werden?"
                    if messagebox.askyesno("URLs geladen", msg):
                        from datetime import datetime
                        existing = set(
                            item.get('url', item) if isinstance(item, dict) else item
                            for item in getattr(self, 'video_download_queue', [])
                        )
                        added = 0
                        skipped_queue = 0
                        skipped_archive = 0
                        for u in urls:
                            if u in existing:
                                skipped_queue += 1
                            elif self.settings.get('download_archive_enabled', False) and self._is_in_download_archive(u):
                                skipped_archive += 1
                            else:
                                preset = self._get_domain_preset(u)
                                if preset:
                                    q, f = preset
                                    quality = q or self.video_quality_var.get()
                                    fmt = f or self.video_format_var.get()
                                else:
                                    quality = self.video_quality_var.get()
                                    fmt = self.video_format_var.get()
                                self.video_download_queue.append({
                                    'url': u,
                                    'from_file_batch': True,
                                    'quality': quality,
                                    'format': fmt,
                                    'added': datetime.now(),
                                    'status': 'Wartend'
                                })
                                existing.add(u)
                                added += 1
                        self.video_download_batch_from_file = True
                        self.video_download_batch_file_total = added
                        self.video_download_batch_file_success = 0
                        self.video_log(f"✓ {added} URLs zur Queue hinzugefügt." + (f" ({skipped_queue} bereits in Queue)" if skipped_queue else "") + (f", {skipped_archive} bereits im Archiv" if skipped_archive else ""))
                        msg_ok = f"{added} URL(s) zur Download-Queue hinzugefügt."
                        if skipped_queue or skipped_archive:
                            msg_ok += f"\n\n{skipped_queue} bereits in der Queue, {skipped_archive} bereits im Download-Archiv."
                        messagebox.showinfo("Erfolg", msg_ok)
                        self._update_queue_status()
                else:
                    messagebox.showwarning("Warnung", "Keine URLs in der Datei gefunden.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Laden der Datei: {e}")
    
    def save_video_queue(self):
        """Speichert die aktuelle Video-Download-Queue in eine JSON-Datei (inkl. Qualität, Format etc.)."""
        queue = getattr(self, 'video_download_queue', [])
        if not queue:
            messagebox.showinfo("Queue speichern", "Die Queue ist leer. Nichts zu speichern.")
            return
        path = filedialog.asksaveasfilename(
            title="Video-Queue speichern",
            defaultextension=".json",
            filetypes=[("JSON-Dateien", "*.json"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return
        try:
            out = []
            for item in queue:
                if isinstance(item, dict):
                    row = {k: v for k, v in item.items() if k != 'added'}
                    if 'added' in item:
                        row['added'] = item['added'].isoformat() if hasattr(item['added'], 'isoformat') else str(item['added'])
                    out.append(row)
                else:
                    out.append({'url': str(item)})
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            self.video_log(f"✓ Queue mit {len(out)} Einträgen gespeichert: {path}")
            messagebox.showinfo("Queue gespeichert", f"Queue mit {len(out)} Download(s) gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Queue konnte nicht gespeichert werden:\n{e}")
    
    def load_video_queue(self):
        """Lädt eine gespeicherte Video-Queue aus JSON und fügt Einträge hinzu (Duplikate werden übersprungen)."""
        path = filedialog.askopenfilename(
            title="Video-Queue laden",
            filetypes=[("JSON-Dateien", "*.json"), ("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if not path:
            return
        try:
            existing_urls = set(
                item.get('url', item) if isinstance(item, dict) else item
                for item in getattr(self, 'video_download_queue', [])
            )
            added = 0
            if path.lower().endswith('.json'):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    data = [data]
                for row in data:
                    url = row.get('url') if isinstance(row, dict) else str(row)
                    if not url or not (url.startswith('http://') or url.startswith('https://')):
                        continue
                    if url in existing_urls:
                        continue
                    item = {
                        'url': url,
                        'quality': row.get('quality', self.video_quality_var.get()) if isinstance(row, dict) else self.video_quality_var.get(),
                        'format': row.get('format', self.video_format_var.get()) if isinstance(row, dict) else self.video_format_var.get(),
                        'subtitle': row.get('subtitle', self.video_subtitle_var.get()) if isinstance(row, dict) else self.video_subtitle_var.get(),
                        'subtitle_lang': row.get('subtitle_lang', self.video_subtitle_lang_var.get()) if isinstance(row, dict) else self.video_subtitle_lang_var.get(),
                        'description': row.get('description', self.video_description_var.get()) if isinstance(row, dict) else self.video_description_var.get(),
                        'thumbnail': row.get('thumbnail', self.video_thumbnail_var.get()) if isinstance(row, dict) else self.video_thumbnail_var.get(),
                        'resume': row.get('resume', self.video_resume_var.get()) if isinstance(row, dict) else self.video_resume_var.get(),
                        'added': datetime.now(),
                        'status': 'Wartend'
                    }
                    if isinstance(row, dict):
                        for key in ('from_file_batch', 'episode_info', 'is_series', 'series_name', 'season_number', 'episode_number', 'episode_title'):
                            if key in row:
                                item[key] = row[key]
                    self.video_download_queue.append(item)
                    existing_urls.add(url)
                    added += 1
                total_in_file = len(data)
            else:
                # TXT: eine URL pro Zeile (wie Musik-Queue)
                with open(path, 'rb') as f:
                    raw = f.read()
                text = raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else str(raw)
                urls_in_file = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith('#') and (line.strip().startswith('http://') or line.strip().startswith('https://'))]
                total_in_file = len(urls_in_file)
                for u in urls_in_file:
                    if u in existing_urls:
                        continue
                    self.video_download_queue.append({
                        'url': u,
                        'quality': self.video_quality_var.get(),
                        'format': self.video_format_var.get(),
                        'subtitle': self.video_subtitle_var.get(),
                        'subtitle_lang': self.video_subtitle_lang_var.get(),
                        'description': self.video_description_var.get(),
                        'thumbnail': self.video_thumbnail_var.get(),
                        'resume': self.video_resume_var.get(),
                        'added': datetime.now(),
                        'status': 'Wartend'
                    })
                    existing_urls.add(u)
                    added += 1
            self._update_queue_status()
            skipped = total_in_file - added
            self.video_log(f"✓ Queue geladen: {added} Einträge hinzugefügt." + (f" ({skipped} bereits in Queue)" if skipped > 0 else ""))
            msg = f"{added} Eintrag/Einträge zur Queue hinzugefügt." if added else "Keine neuen Einträge (alle URLs waren bereits in der Queue oder ungültig)."
            if added and skipped > 0:
                msg += f"\n\n{skipped} übersprungen (bereits in der Queue)."
            messagebox.showinfo("Queue geladen", msg)
        except Exception as e:
            messagebox.showerror("Fehler", f"Queue konnte nicht geladen werden:\n{e}")
    
    def _queue_item_label(self, queue_item, url: str = "") -> str:
        """Anzeigename eines Queue-Eintrags, sonst ein kurzes Stück der Adresse."""
        if isinstance(queue_item, dict):
            title = (queue_item.get("display_title") or "").strip()
            if not title:
                epi = queue_item.get("episode_info") if isinstance(queue_item.get("episode_info"), dict) else {}
                title = (epi.get("title") or queue_item.get("episode_title") or "").strip()
            if title:
                return title
        text = (url or "").strip()
        return text[:70] if text else "Download"

    def _add_to_download_queue(self, url: str, episode_info: Optional[Dict] = None, show_dialog: bool = True, display_title: str = ""):
        """Fügt einen Download zur Queue hinzu
        
        Args:
            url: Die Video-URL
            episode_info: Optional: Episode-Informationen für Serien
            show_dialog: Wenn True, wird ein Dialog-Fenster angezeigt (Standard: True)
        """
        from datetime import datetime
        
        # Duplikat prüfen: URL bereits in Queue oder gerade am Laden?
        existing_urls = []
        for item in getattr(self, 'video_download_queue', []):
            u = item.get('url', item) if isinstance(item, dict) else item
            existing_urls.append(u)
        if url in existing_urls or url in getattr(self, '_video_active_urls', set()):
            self.video_log(f"⚠ URL bereits in der Queue, nicht erneut hinzugefügt: {url[:60]}…")
            if show_dialog:
                messagebox.showinfo("Bereits in Queue", "Diese URL befindet sich bereits in der Warteschlange.")
            return
        
        # Erstelle Queue-Eintrag mit allen notwendigen Informationen
        queue_item = {
            'url': url,
            'quality': self.video_quality_var.get(),
            'format': self.video_format_var.get(),
            'subtitle': self.video_subtitle_var.get(),
            'subtitle_lang': self.video_subtitle_lang_var.get(),
            'description': self.video_description_var.get(),
            'thumbnail': self.video_thumbnail_var.get(),
            'resume': self.video_resume_var.get(),
            'added': datetime.now(),
            'status': 'Wartend',
            'display_title': (display_title or "").strip(),
        }
        
        # Füge Episode-Informationen hinzu falls vorhanden
        if episode_info:
            queue_item['episode_info'] = episode_info
            queue_item['is_series'] = True
            queue_item['series_name'] = episode_info.get('series_name', '')
            queue_item['season_number'] = episode_info.get('season_number')
            queue_item['episode_number'] = episode_info.get('episode_number')
            queue_item['episode_title'] = episode_info.get('title', '')
            fmt = str(episode_info.get('output_format') or '').lower().strip()
            if fmt in ('mp3', 'mp4', 'mkv'):
                queue_item['format'] = fmt
            if fmt == 'mp3' or episode_info.get('kind') == 'audio':
                queue_item['output_dir'] = str(self.music_download_path)
                queue_item['format'] = 'mp3'
        
        self.video_download_queue.append(queue_item)
        
        # Zeige Episode-Titel oder URL im Log
        if episode_info:
            episode_title = episode_info.get('title', '')
            series_name = episode_info.get('series_name', '')
            if series_name and episode_title:
                log_text = f"📋 Zur Queue hinzugefügt: {series_name} - {episode_title[:50]}..."
            elif episode_title:
                log_text = f"📋 Zur Queue hinzugefügt: {episode_title[:60]}..."
            else:
                log_text = f"📋 Zur Queue hinzugefügt: {url[:60]}..."
        else:
            shown = (display_title or "").strip() or url[:60]
            log_text = f"📋 Zur Queue hinzugefügt: {shown}..."
        
        if self._queue_item_is_audio(queue_item, url):
            self.music_log(log_text)
            self._select_music_tab()
        else:
            self.video_log(log_text)
        
        # Zeige Dialog nur wenn gewünscht (nicht bei Batch-Hinzufügung von Episoden)
        if show_dialog:
            messagebox.showinfo("Zur Queue hinzugefügt", 
                              f"Download wurde zur Warteschlange hinzugefügt.\n\n"
                              f"URL: {url[:80]}{'...' if len(url) > 80 else ''}\n\n"
                              f"Downloads in Queue: {len(self.video_download_queue)}")
        
        self._update_queue_status()
    
    def add_video_to_queue(self):
        """Fügt aktuelles Video zur Queue hinzu (mit Serien/Playlist-Erkennung)"""
        url = self.video_url_var.get().strip()
        
        # Bereinige URL von doppelten Einträgen
        url = self._clean_url(url)
        
        # Aktualisiere das Feld mit der bereinigten URL
        self.video_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Warnung", "Bitte geben Sie eine Video-URL ein.")
            return
        
        # Mediatheken/Hörbücher (ARD Audiothek, BR, NDR, …) nur im Musik-Tab
        if _is_music_mediathek_url(url):
            messagebox.showinfo(
                "Mediathek / Hörspiel – Musik-Tab",
                "Diese URL ist eine Audio-Mediathek oder Hörbuch-/Hörspiel-Seite und wird im Tab „Musik“ unterstützt.\n\nBitte wechseln Sie zum Tab „🎵 Musik“ und starten Sie den Download dort."
            )
            try:
                for tab_id in self.notebook.tabs():
                    if "Musik" in self.notebook.tab(tab_id, "text"):
                        self.notebook.select(tab_id)
                        break
            except Exception:
                pass
            return
        
        # Downloader initialisieren falls noch nicht geschehen
        if not hasattr(self, 'video_downloader') or self.video_downloader is None:
            self.video_download_path = Path(self.video_path_var.get())
            quality = self.video_quality_var.get()
            output_format = self.video_format_var.get()
            self.video_downloader = VideoDownloader(
                download_path=str(self.video_download_path),
                quality=quality,
                output_format=output_format,
                gui_instance=self
            )
        
        # Prüfe ob es eine YouTube-URL ist
        is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
        is_youtube_playlist = is_youtube and ('list=' in url.lower() or '/playlist' in url.lower())
        
        # Prüfe ob es eine Serie/Staffel oder YouTube-Playlist ist
        is_series_or_playlist = False
        if is_youtube_playlist:
            is_series_or_playlist = True
        elif not is_youtube and self.video_downloader.is_series_or_season(url):
            is_series_or_playlist = True
        
        if is_series_or_playlist:
            # Zeige Dialog zur Auswahl
            self.video_log("Prüfe ob es eine Serie/Playlist ist...")
            series_data = self.video_downloader.get_series_episodes(url)
            
            if series_data and series_data.get('seasons'):
                try:
                    selected_episodes = self.show_series_selection_dialog(series_data, is_youtube_playlist=is_youtube_playlist)
                    if not selected_episodes:
                        self.video_log("Benutzer hat abgebrochen")
                        return  # Benutzer hat abgebrochen
                    
                    # Füge alle ausgewählten Episoden zur Queue hinzu (ohne Dialog für jede Episode)
                    self.video_log(f"✓ {len(selected_episodes)} Folgen zur Queue hinzufügen...")
                    for episode in selected_episodes:
                        episode_url = episode.get('url', url)
                        # Erstelle Queue-Eintrag für jede Episode (ohne Dialog)
                        self._add_to_download_queue(episode_url, episode_info=episode, show_dialog=False)
                    
                    # Zeige nur einmal eine Zusammenfassung
                    messagebox.showinfo("Zur Queue hinzugefügt", 
                                      f"{len(selected_episodes)} Folgen wurden zur Warteschlange hinzugefügt.")
                    self._update_queue_status()
                    return
                except Exception as e:
                    self.video_log(f"✗ Fehler beim Öffnen des Dialogs: {e}")
                    import traceback
                    self.video_log(traceback.format_exc())
        
        # Normales einzelnes Video
        self._add_to_download_queue(url)
    
    def _select_music_tab(self):
        try:
            self.notebook.select(self.notebook.index(self.music_frame))
        except Exception:
            pass

    def _queue_item_is_audio(self, qi, url: str = "") -> bool:
        """Hörbuch/Audiothek gehört in den Musik-Tab, nicht in die Video-Anzeige."""
        epi = {}
        if isinstance(qi, dict):
            raw = qi.get("episode_info")
            epi = raw if isinstance(raw, dict) else {}
            if epi.get("kind") == "audio" or qi.get("kind") == "audio":
                return True
        check = " ".join([
            url or "",
            (epi.get("url") or "") if isinstance(epi, dict) else "",
            (epi.get("series_url") or "") if isinstance(epi, dict) else "",
            (qi.get("series_url") or "") if isinstance(qi, dict) else "",
            (qi.get("url") or "") if isinstance(qi, dict) else "",
        ])
        if series_watch is not None and series_watch.is_audio_watch_url(check):
            return True
        try:
            return bool(_is_music_mediathek_url(url or (epi.get("url") if isinstance(epi, dict) else "") or ""))
        except Exception:
            return False

    def _update_queue_status(self):
        """Aktualisiert die Queue-Status-Anzeige. Audio zählt im Musik-Tab."""
        items = list(getattr(self, "video_download_queue", []) or [])
        audio_n = 0
        video_n = 0
        for item in items:
            u = item.get("url") if isinstance(item, dict) else str(item)
            if self._queue_item_is_audio(item if isinstance(item, dict) else None, u):
                audio_n += 1
            else:
                video_n += 1
        if hasattr(self, 'video_queue_status_label'):
            if video_n > 0:
                self.video_queue_status_label.config(text=f"📋 Queue: {video_n} Download{'s' if video_n != 1 else ''} wartend")
            else:
                self.video_queue_status_label.config(text="📋 Queue: 0 Downloads")
        music_n = len(getattr(self, "music_download_queue", []) or []) + audio_n
        if hasattr(self, "music_queue_status_label"):
            self.music_queue_status_label.config(text=f"📋 Queue: {music_n} Einträge")
    
    def _video_job_update(self, job_id, title=None, phase=None, percent=None, status_line=None, remove=False, create=False):
        """Merkt den Zustand einer laufenden Folge für Programm und Menü.

        create=False ändert nur einen laufenden Eintrag. Ein später Fortschritt
        nach dem Ende legt den Eintrag nicht wieder an (sonst bleibt 0 % stehen).
        """
        key = str(job_id or "")
        if not key:
            return
        surface = (getattr(self, "_download_surface_for_url", {}) or {}).get(key, "video")
        with self._video_jobs_lock:
            if remove:
                self._video_active_jobs.pop(key, None)
                getattr(self, "_download_surface_for_url", {}).pop(key, None)
            elif key not in self._video_active_jobs:
                if not create:
                    return
                self._video_active_jobs[key] = {
                    "title": "Folge", "phase": "download", "percent": 0.0, "surface": surface,
                }
            if not remove and key in self._video_active_jobs:
                slot = self._video_active_jobs[key]
                slot["surface"] = surface
                if title:
                    slot["title"] = str(title)[:80]
                if phase:
                    slot["phase"] = phase
                if status_line:
                    speed_match = re.search(
                        r"at\s+([\d.]+\s*[KMGT]?i?B/s)", str(status_line), re.IGNORECASE
                    )
                    if speed_match:
                        slot["speed"] = re.sub(r"\s+", "", speed_match.group(1))
                if percent is not None:
                    try:
                        slot["percent"] = max(0.0, min(100.0, float(percent)))
                    except (TypeError, ValueError):
                        pass
            snapshot_empty = not self._video_active_jobs
            removed_last = bool(remove and snapshot_empty)
        self._video_jobs_arm_tick()
        if removed_last:
            self._video_jobs_publish([], [])

    def _video_downloads_running(self) -> bool:
        """True, solange ein Video-Download oder eine Umwandlung läuft."""
        try:
            with self._video_jobs_lock:
                if self._video_active_jobs:
                    return True
        except Exception:
            pass
        if getattr(self, "_video_parallel_workers", 0) > 0:
            return True
        proc = getattr(self, "video_download_process", None)
        if proc is not None:
            try:
                return proc.poll() is None
            except Exception:
                return True
        return False

    def _video_jobs_arm_tick(self):
        with self._video_jobs_lock:
            if getattr(self, "_video_jobs_tick_on", False):
                return
            self._video_jobs_tick_on = True
        try:
            self.root.after(0, self._video_jobs_tick)
        except Exception:
            self._video_jobs_tick_on = False

    def _video_jobs_tick(self):
        try:
            self._video_jobs_render()
        except Exception:
            pass
        with self._video_jobs_lock:
            alive = bool(self._video_active_jobs)
        if not alive:
            # Der erste Stand kann noch die Folge enthalten, die gerade fertig wurde.
            try:
                self._video_jobs_render()
            except Exception:
                pass
            with self._video_jobs_lock:
                alive = bool(self._video_active_jobs)
        if alive:
            try:
                self.root.after(250, self._video_jobs_tick)
                return
            except Exception:
                pass
        with self._video_jobs_lock:
            if self._video_active_jobs:
                try:
                    self.root.after(250, self._video_jobs_tick)
                except Exception:
                    self._video_jobs_tick_on = False
                return
            self._video_jobs_tick_on = False

    def _job_lines(self, slots, waiting):
        lines = []
        for slot in slots:
            title = (slot.get("title") or "Folge").strip()
            phase = slot.get("phase") or "download"
            pct = float(slot.get("percent") or 0)
            speed = (slot.get("speed") or "").strip()
            speed_bit = f" · {speed}" if speed and phase == "download" else ""
            if phase == "convert":
                lines.append(f"⟳ {title} — konvertiert {pct:.0f}%")
            elif phase == "convert_wait":
                lines.append(f"⏳ {title} — Download fertig, wartet auf Konvertierung")
            elif phase == "exists":
                lines.append(f"✓ {title} — bereits vorhanden")
            else:
                lines.append(f"⬇ {title} — lädt {pct:.0f}%{speed_bit}")
        for title in waiting:
            if len(lines) >= 8:
                break
            lines.append(f"· {str(title)[:70]} — wartet in der Queue")
        return lines

    def _paint_job_surface(self, slots, waiting, jobs_var, status_var, progress_var, progress_bar):
        lines = self._job_lines(slots, waiting)
        if jobs_var is not None:
            jobs_var.set("\n".join(lines) if (slots or waiting) else "")
        if not slots or status_var is None or progress_var is None:
            return
        bits = []
        for slot in slots[:3]:
            title = (slot.get("title") or "Folge").strip()[:36]
            pct = float(slot.get("percent") or 0)
            phase = slot.get("phase") or "download"
            speed = (slot.get("speed") or "").strip()
            speed_bit = f" · {speed}" if speed and phase == "download" else ""
            if phase == "convert":
                bits.append(f"{title} — konvertiert {pct:.0f}%")
            elif phase == "convert_wait":
                bits.append(f"{title} — wartet auf Konvertierung")
            elif phase == "exists":
                bits.append(f"{title} — bereits vorhanden")
            else:
                bits.append(f"{title} — {pct:.0f}%{speed_bit}")
        if waiting:
            bits.append(f"{len(waiting)} in der Queue")
        status_var.set(" · ".join(bits))
        show = None
        for slot in slots:
            if (slot.get("phase") or "download") == "download":
                show = float(slot.get("percent") or 0)
                break
        if show is None:
            show = float(slots[0].get("percent") or 0)
        progress_var.set(show)
        if progress_bar is not None:
            try:
                progress_bar.update_idletasks()
            except Exception:
                pass

    def _video_jobs_render(self):
        with self._video_jobs_lock:
            snapshot = [dict(v) for v in self._video_active_jobs.values()]
        video_slots = [s for s in snapshot if s.get("surface") != "music"]
        music_slots = [s for s in snapshot if s.get("surface") == "music"]
        video_wait = []
        music_wait = []
        pending = []
        for item in list(getattr(self, "video_download_queue", []) or []):
            if isinstance(item, dict):
                epi = item.get("episode_info") if isinstance(item.get("episode_info"), dict) else {}
                t = (item.get("display_title") or epi.get("title") or item.get("episode_title") or item.get("url") or "Folge")
                u = item.get("url") or ""
            else:
                t = str(item)
                u = t
            pending.append({"title": str(t)[:80]})
            if self._queue_item_is_audio(item if isinstance(item, dict) else None, u):
                music_wait.append(t)
            else:
                video_wait.append(t)
        self._paint_job_surface(
            video_slots, video_wait[:8],
            getattr(self, "video_jobs_var", None),
            getattr(self, "video_status_var", None),
            getattr(self, "video_progress_var", None),
            getattr(self, "video_progress_bar", None),
        )
        self._paint_job_surface(
            music_slots, music_wait[:8],
            getattr(self, "music_jobs_var", None),
            getattr(self, "music_status_var", None),
            getattr(self, "music_progress_var", None),
            getattr(self, "music_progress_bar", None),
        )
        self._video_jobs_publish(snapshot, pending)

    def _video_jobs_publish(self, snapshot, pending):
        if series_watch is None:
            return
        import time as _time
        now = _time.monotonic()
        force = (not snapshot) or any((s.get("phase") or "download") != "download" for s in snapshot)
        if snapshot and not force and (now - getattr(self, "_video_jobs_last_write", 0.0)) < 0.25:
            return
        self._video_jobs_last_write = now
        try:
            if not snapshot:
                series_watch.clear_download_status(self.base_download_path, phase="idle")
                return
            first = snapshot[0]
            series_watch.write_runtime_status(
                self.base_download_path,
                phase="downloading",
                downloads=[
                    {
                        "title": s.get("title") or "",
                        "percent": float(s.get("percent") or 0),
                        "phase": s.get("phase") or "download",
                        "speed": s.get("speed") or "",
                    }
                    for s in snapshot[:6]
                ],
                download={
                    "title": first.get("title") or "",
                    "percent": float(first.get("percent") or 0),
                    "phase": first.get("phase") or "download",
                    "speed": first.get("speed") or "",
                    "index": 1,
                    "total": len(snapshot) + len(pending),
                },
                pending=pending,
            )
        except Exception:
            pass

    def _max_parallel_video_downloads(self) -> int:
        """Gleichzeitige Video-Queue-Downloads (1–8), aus Einstellungen."""
        try:
            n = int(self.settings.get('max_concurrent_downloads', 1))
        except (TypeError, ValueError):
            n = 1
        return max(1, min(8, n))

    def _video_queue_worker_entry(self, url: str, queue_item: dict):
        """Worker-Thread: ein Queue-Download; bei Parallelität eigener GUI-Proxy für yt-dlp."""
        max_c = self._max_parallel_video_downloads()
        parallel_gui = _ParallelDownloadGuiProxy(self) if max_c > 1 else None
        try:
            self.video_download_thread(
                url, queue_item=queue_item, parallel_gui=parallel_gui, _from_queue_worker=True
            )
        finally:
            try:
                self._video_active_urls.discard(url)
            except Exception:
                pass
            def _worker_finished():
                if parallel_gui and parallel_gui._process:
                    try:
                        if parallel_gui._process in self._parallel_video_process_list:
                            self._parallel_video_process_list.remove(parallel_gui._process)
                    except (ValueError, AttributeError):
                        pass
                with self._video_parallel_lock:
                    self._video_parallel_workers = max(0, self._video_parallel_workers - 1)
                    remaining = self._video_parallel_workers
                if remaining <= 0:
                    self.video_download_process = None
                last_url = url or ''
                delay_ms = 500 if max_c > 1 and last_url and ('youtube.com' in last_url.lower() or 'youtu.be' in last_url.lower()) else 0
                if delay_ms:
                    self.video_log("  Kurze Pause (YouTube, parallele Queue)…")
                self.root.after(delay_ms, self._process_download_queue)
            self.root.after(0, _worker_finished)

    def _process_download_queue(self):
        """Startet automatisch nächste Download(s) aus der Queue (1 oder mehr parallel)."""
        if getattr(self, 'video_download_episodes_total', 0) > 0:
            return
        with self._video_parallel_lock:
            workers = self._video_parallel_workers
        max_c = self._max_parallel_video_downloads()
        if workers == 0 and self.video_download_process is not None:
            return

        if not self.video_download_queue:
            if workers > 0:
                return
            if hasattr(self, 'video_download_queue_processing'):
                self.video_download_queue_processing = False
            self.video_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.DISABLED)
            self._show_system_notification("Universal Downloader", "Alle Downloads der Queue sind abgeschlossen.")
            batch_file_total = getattr(self, 'video_download_batch_file_total', 0)
            batch_file_success = getattr(self, 'video_download_batch_file_success', 0)
            batch_series_total = getattr(self, 'video_download_batch_series_total', 0)
            batch_series_success = getattr(self, 'video_download_batch_series_success', 0)
            if batch_file_total and batch_file_total > 0:
                self.root.after(0, lambda: self._show_batch_file_success(batch_file_success, batch_file_total))
                failed = batch_file_total - batch_file_success
                if failed > 0:
                    self.root.after(0, lambda: self._show_system_notification("Universal Downloader", f"{failed} Download(s) fehlgeschlagen."))
                self.video_download_batch_from_file = False
                self.video_download_batch_file_total = 0
                self.video_download_batch_file_success = 0
            if batch_series_total and batch_series_total > 0:
                self.root.after(0, lambda: self._show_batch_series_success(batch_series_success, batch_series_total))
                failed_s = batch_series_total - batch_series_success
                if failed_s > 0:
                    self.root.after(0, lambda: self._show_system_notification("Universal Downloader", f"{failed_s} Folge(n) fehlgeschlagen."))
                self.video_download_batch_series_total = 0
                self.video_download_batch_series_success = 0
            if getattr(self, '_video_batch_episode_total', 0):
                self._video_batch_episode_total = 0
                self._video_batch_episode_current = 0
            if getattr(self, 'video_shutdown_after_queue_var', None) and self.video_shutdown_after_queue_var.get():
                self.root.after(100, self._show_shutdown_after_downloads_dialog)
            return

        if getattr(self, '_video_queue_hold', False):
            return

        while True:
            with self._video_parallel_lock:
                if self._video_parallel_workers >= max_c:
                    break
            if not self.video_download_queue:
                break
            queue_item = self.video_download_queue.pop(0)
            url = queue_item.get('url', queue_item) if isinstance(queue_item, dict) else queue_item
            if not isinstance(queue_item, dict):
                queue_item = {'url': url}
            if url in self._video_active_urls:
                self.video_log(f"⚠ Läuft schon, nicht doppelt gestartet: {url[:70]}")
                continue
            self._video_active_urls.add(url)
            self._last_video_download_url = url
            with self._video_parallel_lock:
                self._video_parallel_workers += 1
                workers = self._video_parallel_workers
            qleft = len(self.video_download_queue)
            self.video_log(f"\n{'='*60}")
            self.video_log(f"📋 Queue: Starte Download [{workers}/{max_c} aktiv, {qleft} in Warteschlange]")
            self.video_log(f"URL: {url}")
            self.video_log(f"{'='*60}\n")
            self.video_download_button.config(state=tk.DISABLED)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.NORMAL)
            self.video_download_cancelled = False
            threading.Thread(
                target=self._video_queue_worker_entry, args=(url, queue_item), daemon=True
            ).start()
    
    def _start_video_download_direct(self, url: str):
        """Startet Download direkt ohne Queue-Prüfung (intern verwendet)"""
        # Setze URL
        self.video_url_var.set(url)
        
        # Rufe die ursprüngliche start_video_download Logik auf, aber überspringe Queue-Prüfung
        # Wir verwenden einen Flag um die Queue-Prüfung zu überspringen
        self._skip_queue_check = True
        try:
            # Rufe die ursprüngliche Methode auf (sie prüft jetzt den Flag)
            self.start_video_download()
        finally:
            self._skip_queue_check = False
    
    def _show_batch_file_success(self, success_count: int, total: int):
        """Zeigt eine gemeinsame Erfolgsmeldung für alle Downloads aus einer URL-Liste (Datei)."""
        self._show_system_notification(
            "Downloads abgeschlossen",
            f"Aus der URL-Liste erfolgreich: {success_count}/{total}.",
        )
    
    def _show_batch_series_success(self, success_count: int, total: int):
        """Zeigt eine gemeinsame Erfolgsmeldung für alle Folgen einer Serie."""
        self._show_system_notification(
            "Download abgeschlossen",
            f"Serie erfolgreich: {success_count}/{total} Folgen.",
        )
    
    def _trigger_system_shutdown(self) -> bool:
        """Führt Herunterfahren des Systems aus (Windows, Linux, macOS). Gibt True bei Erfolg zurück."""
        try:
            if sys.platform == 'win32':
                subprocess.Popen(['shutdown', '/s', '/t', '0'], creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                return True
            if sys.platform == 'darwin':
                subprocess.Popen(['osascript', '-e', 'tell application "System Events" to shut down'])
                return True
            # Linux: zuerst D-Bus (funktioniert oft ohne Root), dann ggf. pkexec (Passwort-Dialog)
            if sys.platform.startswith('linux'):
                # 1. logind über D-Bus – auf Mint/Ubuntu meist ohne Passwort für aktive Session
                try:
                    r = subprocess.run(
                        ['dbus-send', '--system', '--print-reply', '--dest=org.freedesktop.login1',
                         '/org/freedesktop/login1', 'org.freedesktop.login1.Manager.PowerOff', 'boolean:true'],
                        capture_output=True, timeout=5
                    )
                    if r.returncode == 0:
                        return True
                except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                    pass
                # 2. pkexec + shutdown (öffnet Passwort-Dialog)
                try:
                    subprocess.Popen(
                        ['pkexec', 'shutdown', '-h', 'now'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                    )
                    return True
                except (FileNotFoundError, PermissionError, Exception):
                    pass
                # 3. Ohne pkexec: Befehle ausführen und Rückgabecode prüfen (ohne Root schlagen sie fehl)
                for cmd in [['loginctl', 'poweroff'], ['systemctl', 'poweroff'], ['poweroff'], ['shutdown', '-h', 'now']]:
                    try:
                        r = subprocess.run(cmd, capture_output=True, timeout=3)
                        if r.returncode == 0:
                            return True
                    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, Exception):
                        continue
            return False
        except Exception:
            return False
    
    def _show_shutdown_after_downloads_dialog(self):
        """Zeigt Popup: Alle Queue-Downloads fertig, Countdown 30 s, dann Herunterfahren (mit Jetzt/Abbrechen)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Downloads abgeschlossen – Herunterfahren")
        dialog.geometry("420x200")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (420 // 2)
        y = (dialog.winfo_screenheight() // 2) - (200 // 2)
        dialog.geometry(f"420x200+{x}+{y}")
        
        countdown_sec = [30]
        countdown_label = ttk.Label(dialog, text="", font=("Arial", 14, "bold"))
        countdown_label.pack(pady=(20, 5))
        ttk.Label(dialog, text="Alle Downloads sind abgeschlossen.", font=("Arial", 10)).pack(pady=(0, 5))
        ttk.Label(dialog, text="Der Rechner wird heruntergefahren – oder Sie brechen ab.", font=("Arial", 9)).pack(pady=(0, 15))
        
        def update_countdown():
            countdown_label.config(text=f"Herunterfahren in {countdown_sec[0]} Sekunden…")
        
        shutdown_after_id = [None]
        countdown_after_id = [None]
        
        def do_shutdown():
            for aid in (shutdown_after_id[0], countdown_after_id[0]):
                if aid is not None:
                    try:
                        self.root.after_cancel(aid)
                    except Exception:
                        pass
            dialog.destroy()
            if self._trigger_system_shutdown():
                self.video_log("System wird heruntergefahren.")
            else:
                self.video_log("Herunterfahren fehlgeschlagen (evtl. fehlen Rechte).", "WARNING")
                messagebox.showwarning("Herunterfahren", "Herunterfahren konnte nicht ausgeführt werden (evtl. fehlen Rechte).")
        
        def schedule_shutdown():
            shutdown_after_id[0] = self.root.after(30000, do_shutdown)
        
        def tick():
            countdown_sec[0] -= 1
            if countdown_sec[0] <= 0:
                do_shutdown()
                return
            update_countdown()
            countdown_after_id[0] = self.root.after(1000, tick)
        
        def cancel():
            for aid in (shutdown_after_id[0], countdown_after_id[0]):
                if aid is not None:
                    try:
                        self.root.after_cancel(aid)
                    except Exception:
                        pass
            dialog.destroy()
            self.video_log("Herunterfahren abgebrochen.")
        
        update_countdown()
        schedule_shutdown()
        countdown_after_id[0] = self.root.after(1000, tick)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Jetzt herunterfahren", command=do_shutdown).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
    
    def show_download_queue(self):
        """Zeigt die Download-Queue an"""
        queue_window = tk.Toplevel(self.root)
        queue_window.title("Download-Queue")
        queue_window.transient(self.root)
        self._apply_dark_toplevel(queue_window)
        self._fit_dialog(queue_window, 940, 580, 700, 400)
        
        frame = ttk.Frame(queue_window, padding="10", style="Download.TFrame")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header-Zeile mit Label und Buttons
        header_frame = ttk.Frame(frame, style="Download.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Download-Queue:", font=("Arial", 10, "bold"), style="Download.TLabel").pack(side=tk.LEFT)
        
        # Zwei Zeilen Buttons rechts: oben Starten/↑/↓/…, darunter Speichern/Laden
        right_buttons = ttk.Frame(header_frame, style="Download.TFrame")
        right_buttons.pack(side=tk.RIGHT)
        button_frame = ttk.Frame(right_buttons, style="Download.TFrame")
        button_frame.pack(fill=tk.X, pady=(0, 4))
        save_load_frame = ttk.Frame(right_buttons, style="Download.TFrame")
        save_load_frame.pack(fill=tk.X)
        
        # Treeview für bessere Anzeige
        columns = ("Status", "URL", "Qualität", "Format", "Hinzugefügt")
        queue_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15, style="Download.Treeview")
        queue_tree.heading("Status", text="Status")
        queue_tree.heading("URL", text="URL")
        queue_tree.heading("Qualität", text="Qualität")
        queue_tree.heading("Format", text="Format")
        queue_tree.heading("Hinzugefügt", text="Hinzugefügt")
        queue_tree.column("Status", width=80)
        queue_tree.column("URL", width=300)
        queue_tree.column("Qualität", width=80)
        queue_tree.column("Format", width=80)
        queue_tree.column("Hinzugefügt", width=120)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=queue_tree.yview)
        queue_tree.configure(yscrollcommand=scrollbar.set)
        
        queue_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 10))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 10))
        
        def refresh_queue():
            queue_tree.delete(*queue_tree.get_children())
            for i, item in enumerate(self.video_download_queue):
                if isinstance(item, dict):
                    url = item.get('url', '')
                    status = item.get('status', 'Wartend')
                    quality = item.get('quality', 'best')
                    format_val = item.get('format', 'mp4')
                    added = item.get('added', datetime.now())
                    if isinstance(added, datetime):
                        added_str = added.strftime("%H:%M:%S")
                    else:
                        added_str = str(added)
                    
                    # Zeige Episode-Informationen falls vorhanden
                    episode_info = item.get('episode_info')
                    if episode_info:
                        episode_title = episode_info.get('title', '')
                        series_name = episode_info.get('series_name', item.get('series_name', ''))
                        season_num = episode_info.get('season_number', item.get('season_number'))
                        episode_num = episode_info.get('episode_number', item.get('episode_number'))
                        
                        if series_name:
                            display_text = f"{series_name}"
                            if season_num:
                                display_text += f" S{season_num:02d}"
                            if episode_num:
                                display_text += f"E{episode_num:02d}"
                            if episode_title:
                                display_text += f": {episode_title}"
                            url_display = display_text[:60] + "..." if len(display_text) > 60 else display_text
                        else:
                            url_display = episode_title[:60] + "..." if episode_title and len(episode_title) > 60 else (episode_title or url[:60] + "..." if len(url) > 60 else url)
                    else:
                        url_display = url[:60] + "..." if len(url) > 60 else url
                else:
                    url = item
                    status = 'Wartend'
                    quality = self.video_quality_var.get()
                    format_val = self.video_format_var.get()
                    added_str = "Jetzt"
                    url_display = url[:60] + "..." if len(url) > 60 else url
                
                queue_tree.insert("", tk.END, values=(
                    status,
                    url_display,
                    quality,
                    format_val,
                    added_str
                ), tags=(url,))
        
        refresh_queue()
        
        def remove_selected():
            selection = queue_tree.selection()
            if selection:
                item_id = selection[0]
                item_values = queue_tree.item(item_id, 'values')
                url = item_values[1] if len(item_values) > 1 else None
                
                # Finde und entferne aus Queue
                for i, queue_item in enumerate(self.video_download_queue):
                    item_url = queue_item.get('url', queue_item) if isinstance(queue_item, dict) else queue_item
                    if item_url == url or (isinstance(url, str) and url in str(item_url)):
                        self.video_download_queue.pop(i)
                        break
                refresh_queue()
                self._update_queue_status()
        
        def clear_queue():
            if messagebox.askyesno("Bestätigen", "Queue wirklich löschen?"):
                self.video_download_queue.clear()
                refresh_queue()
                self._update_queue_status()
        
        def move_up():
            selection = queue_tree.selection()
            if selection:
                item_id = selection[0]
                index = queue_tree.index(item_id)
                if index > 0:
                    # Tausche Positionen
                    self.video_download_queue[index], self.video_download_queue[index-1] = \
                        self.video_download_queue[index-1], self.video_download_queue[index]
                    refresh_queue()
                    queue_tree.selection_set(queue_tree.get_children()[index-1])
                    self._update_queue_status()
        
        def move_down():
            selection = queue_tree.selection()
            if selection:
                item_id = selection[0]
                index = queue_tree.index(item_id)
                if index < len(self.video_download_queue) - 1:
                    # Tausche Positionen
                    self.video_download_queue[index], self.video_download_queue[index+1] = \
                        self.video_download_queue[index+1], self.video_download_queue[index]
                    refresh_queue()
                    queue_tree.selection_set(queue_tree.get_children()[index+1])
                    self._update_queue_status()
        
        def start_queue():
            """Startet die Queue manuell"""
            if not self.video_download_queue:
                messagebox.showwarning("Warnung", "Queue ist leer!")
                return
            
            # Prüfe ob bereits ein Download läuft
            is_download_running = (
                self.video_download_process is not None or 
                (hasattr(self, 'video_download_episodes_total') and self.video_download_episodes_total > 0)
            )
            
            if is_download_running:
                messagebox.showwarning("Warnung", "Ein Download läuft bereits. Die Queue wird automatisch fortgesetzt, sobald der aktuelle Download fertig ist.")
                return
            
            if messagebox.askyesno("Queue starten", f"{len(self.video_download_queue)} Downloads in der Queue.\n\nDownloads nacheinander starten?"):
                queue_window.destroy()
                self.start_queue_download()
        
        def do_load_queue():
            self.load_video_queue()
            refresh_queue()
        
        # Obere Zeile: Starten, Reihenfolge, Entfernen, Löschen, Aktualisieren
        ttk.Button(button_frame, text="▶ Starten", command=start_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↑", command=move_up, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↓", command=move_down, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Entfernen", command=remove_selected, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Löschen", command=clear_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔄", command=refresh_queue, width=3, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        # Untere Zeile: Speichern & Laden
        ttk.Button(save_load_frame, text="💾 Speichern", command=self.save_video_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
        ttk.Button(save_load_frame, text="📂 Laden", command=do_load_queue, style="Download.TButton").pack(side=tk.LEFT, padx=2)
    
    def start_queue_download(self):
        """Startet Downloads aus der Queue (manuell)"""
        if not self.video_download_queue:
            messagebox.showwarning("Warnung", "Queue ist leer!")
            return
        
        # Prüfe ob bereits ein Download läuft
        is_download_running = (
            self.video_download_process is not None or 
            (hasattr(self, 'video_download_episodes_total') and self.video_download_episodes_total > 0)
        )
        
        if is_download_running:
            messagebox.showwarning("Warnung", "Ein Download läuft bereits. Die Queue wird automatisch fortgesetzt, sobald der aktuelle Download fertig ist.")
            return
        
        # Optionen aus der GUI auf alle Einträge aus URL-Liste (from_file_batch) anwenden – so gilt beim Start das aktuell eingestellte (Beschreibung, Thumbnail, etc.) für alle
        current_opts = {
            'quality': self.video_quality_var.get(),
            'format': self.video_format_var.get(),
            'subtitle': self.video_subtitle_var.get(),
            'subtitle_lang': self.video_subtitle_lang_var.get(),
            'description': self.video_description_var.get(),
            'thumbnail': self.video_thumbnail_var.get(),
            'resume': self.video_resume_var.get(),
        }
        for item in self.video_download_queue:
            if isinstance(item, dict) and item.get('from_file_batch'):
                item.update(current_opts)
        
        # Starte Queue-Verarbeitung
        self._video_queue_hold = False
        self.video_download_cancelled = False
        self.video_download_queue_processing = True
        self.video_log(f"\n{'='*60}")
        self.video_log(f"📋 Starte Queue-Download: {len(self.video_download_queue)} Downloads")
        self.video_log(f"{'='*60}\n")
        self._process_download_queue()
    
    def show_scheduled_downloads(self):
        """Zeigt Dialog für geplante Downloads"""
        schedule_window = tk.Toplevel(self.root)
        schedule_window.title("Geplante Downloads")
        self._apply_dark_toplevel(schedule_window)
        schedule_window.transient(self.root)
        self._fit_dialog(schedule_window, 860, 580, 640, 400)
        
        frame = ttk.Frame(schedule_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Überschrift
        ttk.Label(frame, text="Geplante Downloads", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Liste der geplanten Downloads
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview für geplante Downloads
        columns = ("URL", "Zeitpunkt", "Status")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        tree.heading("URL", text="URL")
        tree.heading("Zeitpunkt", text="Geplant für")
        tree.heading("Status", text="Status")
        tree.column("URL", width=400)
        tree.column("Zeitpunkt", width=150)
        tree.column("Status", width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Aktualisiere Liste
        def refresh_list():
            tree.delete(*tree.get_children())
            for item in self.video_scheduled_downloads:
                status = "Wartend" if item['scheduled_time'] > datetime.now() else "Bereit"
                tree.insert("", tk.END, values=(
                    item['url'][:60] + "..." if len(item['url']) > 60 else item['url'],
                    item['scheduled_time'].strftime("%Y-%m-%d %H:%M"),
                    status
                ), tags=(item['url'],))
        
        refresh_list()
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        def add_scheduled():
            add_window = tk.Toplevel(schedule_window)
            add_window.title("Download vormerken")
            add_window.transient(schedule_window)
            self._fit_dialog(add_window, 560, 360, 440, 280)
            
            add_frame = ttk.Frame(add_window, padding="20")
            add_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(add_frame, text="URL:").pack(anchor=tk.W, pady=(0, 5))
            url_entry = ttk.Entry(add_frame, width=60)
            url_entry.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(add_frame, text="Geplant für (YYYY-MM-DD HH:MM):").pack(anchor=tk.W, pady=(0, 5))
            time_entry = ttk.Entry(add_frame, width=20)
            time_entry.pack(anchor=tk.W, pady=(0, 15))
            # Vorschlag: Heute 20:15
            default_time = datetime.now().replace(hour=20, minute=15, second=0, microsecond=0)
            if default_time < datetime.now():
                default_time = default_time.replace(day=default_time.day + 1)
            time_entry.insert(0, default_time.strftime("%Y-%m-%d %H:%M"))
            
            def save_scheduled():
                url = url_entry.get().strip()
                time_str = time_entry.get().strip()
                
                if not url:
                    messagebox.showerror("Fehler", "Bitte URL eingeben!")
                    return
                
                try:
                    scheduled_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
                    if scheduled_time < datetime.now():
                        messagebox.showerror("Fehler", "Zeitpunkt muss in der Zukunft liegen!")
                        return
                    
                    self.video_scheduled_downloads.append({
                        'url': url,
                        'scheduled_time': scheduled_time,
                        'settings': {
                            'quality': self.video_quality_var.get(),
                            'format': self.video_format_var.get(),
                            'subtitle': self.video_subtitle_var.get(),
                            'subtitle_lang': self.video_subtitle_lang_var.get(),
                            'description': self.video_description_var.get(),
                            'thumbnail': self.video_thumbnail_var.get(),
                            'resume': self.video_resume_var.get(),
                            'metadata': True,  # Immer aktiviert
                            'speed_limit': self.settings.get('speed_limit_value', '5') if self.settings.get('speed_limit_enabled', False) else None
                        }
                    })
                    
                    self._save_video_data()
                    refresh_list()
                    add_window.destroy()
                    messagebox.showinfo("Erfolg", f"Download für {scheduled_time.strftime('%Y-%m-%d %H:%M')} vorgemerkt!")
                except ValueError:
                    messagebox.showerror("Fehler", "Ungültiges Datum/Zeit-Format! Verwenden Sie: YYYY-MM-DD HH:MM")
            
            ttk.Button(add_frame, text="Vormerken", command=save_scheduled).pack(pady=10)
            ttk.Button(add_frame, text="Abbrechen", command=add_window.destroy).pack()
        
        def remove_selected():
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                url = item['tags'][0] if item['tags'] else None
                if url:
                    self.video_scheduled_downloads = [s for s in self.video_scheduled_downloads if s['url'] != url]
                    self._save_video_data()
                    refresh_list()
        
        def clear_all():
            if messagebox.askyesno("Bestätigen", "Alle geplanten Downloads löschen?"):
                self.video_scheduled_downloads.clear()
                self._save_video_data()
                refresh_list()
        
        ttk.Button(button_frame, text="➕ Download vormerken", command=add_scheduled).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Ausgewähltes entfernen", command=remove_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Alle löschen", command=clear_all).pack(side=tk.LEFT, padx=5)
    
    def _scheduler_loop(self):
        """Prüft regelmäßig auf geplante Downloads"""
        while self.scheduler_running:
            try:
                now = datetime.now()
                ready_downloads = []
                
                for scheduled in self.video_scheduled_downloads[:]:
                    if scheduled['scheduled_time'] <= now:
                        ready_downloads.append(scheduled)
                        self.video_scheduled_downloads.remove(scheduled)
                
                if ready_downloads:
                    self._save_video_data()
                    for scheduled in ready_downloads:
                        # Starte Download im Hintergrund
                        self.root.after(0, lambda s=scheduled: self._start_scheduled_download(s))
                
                time.sleep(30)  # Prüfe alle 30 Sekunden
            except Exception as e:
                self.video_log(f"⚠ Fehler im Scheduler: {e}")
                time.sleep(60)
    
    def _start_scheduled_download(self, scheduled):
        """Startet einen geplanten Download"""
        try:
            self.video_log(f"\n{'='*60}")
            self.video_log(f"⏰ Starte geplanten Download: {scheduled['url']}")
            self.video_log(f"{'='*60}")
            
            # Setze Einstellungen temporär
            old_quality = self.video_quality_var.get()
            old_format = self.video_format_var.get()
            old_subtitle = self.video_subtitle_var.get()
            old_subtitle_lang = self.video_subtitle_lang_var.get()
            old_description = self.video_description_var.get()
            old_thumbnail = self.video_thumbnail_var.get()
            old_resume = self.video_resume_var.get()
            settings = scheduled['settings']
            # Unterstütze sowohl 'quality' (Legacy) als auch 'default_video_quality'
            quality = settings.get('quality') or settings.get('default_video_quality', 'best')
            # Konvertiere 'worst' zu 'niedrigste' für Kompatibilität
            if quality == 'worst':
                quality = 'niedrigste'
            self.video_quality_var.set(quality)
            self.video_format_var.set(settings.get('format', 'mp4'))
            self.video_subtitle_var.set(settings.get('subtitle', False))
            self.video_subtitle_lang_var.set(settings.get('subtitle_lang', 'de'))
            self.video_description_var.set(settings.get('description', False))
            self.video_thumbnail_var.set(settings.get('thumbnail', False))
            self.video_resume_var.set(settings.get('resume', True))
            
            # Starte Download
            self.video_url_var.set(scheduled['url'])
            self.start_video_download()
            
            # Stelle alte Einstellungen wieder her (nach kurzer Verzögerung)
            self.root.after(5000, lambda: self._restore_settings(
                old_quality, old_format, old_subtitle, old_subtitle_lang,
                old_description, old_thumbnail, old_resume
            ))
            
        except Exception as e:
            self.video_log(f"✗ Fehler beim Starten des geplanten Downloads: {e}")
    
    def _restore_settings(self, quality, format_val, subtitle, subtitle_lang, description, thumbnail, resume):
        """Stellt die ursprünglichen Einstellungen wieder her"""
        self.video_quality_var.set(quality)
        self.video_format_var.set(format_val)
        self.video_subtitle_var.set(subtitle)
        self.video_subtitle_lang_var.set(subtitle_lang)
        self.video_description_var.set(description)
        self.video_thumbnail_var.set(thumbnail)
        self.video_resume_var.set(resume)
    
    def show_download_history(self):
        """Zeigt Download-Historie; Doppelklick auf einen Eintrag kopiert die URL in die Zwischenablage."""
        history_window = tk.Toplevel(self.root)
        history_window.title("Download-Historie")
        history_window.transient(self.root)
        self._apply_dark_toplevel(history_window)
        self._fit_dialog(history_window, 1100, 680, 860, 480)
        
        frame = ttk.Frame(history_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Download-Historie", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 5))
        hint = ttk.Label(frame, text="Doppelklick kopiert die URL. Rechtsklick: URL, Fehler oder Datum kopieren.", font=("Arial", 9))
        hint.pack(anchor=tk.W, pady=(0, 5))
        # Suche/Filter (URL, Datei, Datum)
        filter_frame = ttk.Frame(frame)
        filter_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(filter_frame, text="Suchen (URL, Datei, Datum):", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        filter_var = tk.StringVar()
        filter_entry = ttk.Entry(filter_frame, textvariable=filter_var, width=40, style="Download.TEntry")
        filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self._entry_place_caret(filter_entry)
        self._entry_edit_menu(filter_entry)

        button_frame = ttk.Frame(frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Treeview
        columns = ("Zeitpunkt", "URL", "Status", "Datei")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=20)
        tree.heading("Zeitpunkt", text="Zeitpunkt")
        tree.heading("URL", text="URL")
        tree.heading("Status", text="Status")
        tree.heading("Datei", text="Datei")
        tree.column("Zeitpunkt", width=160, minwidth=120, stretch=False)
        tree.column("URL", width=420, minwidth=160, stretch=True)
        tree.column("Status", width=140, minwidth=90, stretch=False)
        tree.column("Datei", width=280, minwidth=120, stretch=True)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Reihenfolge für Klick → URL (Eintrag in gleicher Order wie Tree); alle Einträge für Filter
        all_entries_ordered = []
        for entry in sorted(self.video_download_history, key=lambda x: x.get('timestamp', ''), reverse=True):
            all_entries_ordered.append(entry)

        visible_entries_for_copy = []  # Liste der aktuell angezeigten Einträge (für URL-Kopieren)

        def refresh_tree(entries_to_show=None):
            nonlocal visible_entries_for_copy
            entries_to_show = entries_to_show if entries_to_show is not None else all_entries_ordered
            visible_entries_for_copy = list(entries_to_show)
            tree.delete(*tree.get_children())
            for entry in entries_to_show:
                tree.insert("", tk.END, values=(
                    entry.get('timestamp', 'Unbekannt'),
                    entry.get('url', '') or '',
                    entry.get('status', 'Unbekannt'),
                    entry.get('filename', 'N/A') or 'N/A',
                ))

        def apply_filter(*_):
            q = (filter_var.get() or "").strip().lower()
            if not q:
                refresh_tree(all_entries_ordered)
                return
            filtered = [
                e for e in all_entries_ordered
                if q in (e.get('timestamp', '') or '').lower()
                or q in (e.get('url', '') or '').lower()
                or q in (e.get('status', '') or '').lower()
                or q in (e.get('filename', '') or '').lower()
            ]
            refresh_tree(filtered)

        refresh_tree()
        filter_var.trace_add("write", apply_filter)

        def _selected_entry():
            sel = tree.selection()
            if not sel:
                return None
            try:
                idx = tree.index(sel[0])
            except tk.TclError:
                return None
            if 0 <= idx < len(visible_entries_for_copy):
                return visible_entries_for_copy[idx]
            return None

        def _copy_field(key):
            entry = _selected_entry()
            if not entry:
                return
            text = str(entry.get(key, '') or '')
            if not text:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)

        def copy_url_from_selection(*_):
            _copy_field('url')

        context = tk.Menu(history_window, tearoff=0)
        context.add_command(label="URL kopieren", command=lambda: _copy_field('url'))
        context.add_command(label="Fehler kopieren", command=lambda: _copy_field('status'))
        context.add_command(label="Datum kopieren", command=lambda: _copy_field('timestamp'))

        def popup_history(event):
            row = tree.identify_row(event.y)
            if row:
                tree.selection_set(row)
                tree.focus(row)
            try:
                context.tk_popup(event.x_root, event.y_root)
            finally:
                context.grab_release()

        tree.bind("<Double-1>", copy_url_from_selection)
        tree.bind("<Button-2>", popup_history)
        tree.bind("<Button-3>", popup_history)
        
        def clear_history():
            if messagebox.askyesno("Bestätigen", "Historie wirklich löschen?"):
                self.video_download_history.clear()
                self._save_video_data()
                all_entries_ordered.clear()
                refresh_tree()
        
        ttk.Button(button_frame, text="Historie löschen", command=clear_history).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="URL kopieren", command=copy_url_from_selection).pack(side=tk.LEFT, padx=5)
    
    def show_favorites(self):
        """Zeigt Favoriten-Verwaltung"""
        fav_window = tk.Toplevel(self.root)
        fav_window.title("Favoriten")
        fav_window.transient(self.root)
        self._apply_dark_toplevel(fav_window)
        self._fit_dialog(fav_window, 720, 500, 520, 360)
        
        frame = ttk.Frame(fav_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Favoriten", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        listbox = tk.Listbox(
            frame, height=15,
            bg=getattr(self, '_tk_bg_card', '#424242'), fg=getattr(self, '_tk_fg_text', '#e8e8e8'),
            selectbackground=getattr(self, '_tk_btn_bg', '#4a4a4a'),
            selectforeground=getattr(self, '_tk_fg_text', '#e8e8e8'),
            highlightthickness=0,
        )
        listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        for fav in self.video_favorites:
            listbox.insert(tk.END, fav.get('name', fav.get('url', 'Unbekannt')))
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        def add_favorite():
            add_window = tk.Toplevel(fav_window)
            add_window.title("Favorit hinzufügen")
            add_window.transient(fav_window)
            self._apply_dark_toplevel(add_window)
            self._fit_dialog(add_window, 500, 260, 400, 220)
            
            add_frame = ttk.Frame(add_window, padding="20")
            add_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(add_frame, text="Name:").pack(anchor=tk.W, pady=(0, 5))
            name_entry = ttk.Entry(add_frame, width=40)
            name_entry.pack(fill=tk.X, pady=(0, 15))
            
            ttk.Label(add_frame, text="URL:").pack(anchor=tk.W, pady=(0, 5))
            url_entry = ttk.Entry(add_frame, width=40)
            url_entry.pack(fill=tk.X, pady=(0, 15))
            
            def save_favorite():
                name = name_entry.get().strip()
                url = url_entry.get().strip()
                if name and url:
                    self.video_favorites.append({'name': name, 'url': url})
                    self._save_video_data()
                    listbox.insert(tk.END, name)
                    add_window.destroy()
                else:
                    messagebox.showerror("Fehler", "Bitte Name und URL eingeben!")
            
            ttk.Button(add_frame, text="Hinzufügen", command=save_favorite).pack(pady=10)
        
        def remove_favorite():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                self.video_favorites.pop(index)
                self._save_video_data()
                listbox.delete(index)
        
        def load_favorite():
            selection = listbox.curselection()
            if selection:
                fav = self.video_favorites[selection[0]]
                self.video_url_var.set(fav['url'])
                fav_window.destroy()
                self.notebook.select(self.notebook.index(self.video_frame))
        
        ttk.Button(button_frame, text="➕ Hinzufügen", command=add_favorite).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🗑️ Entfernen", command=remove_favorite).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📥 Laden", command=load_favorite).pack(side=tk.RIGHT, padx=5)
    
    def show_search_dialog(self):
        """Zeigt Such-Dialog für Filme und Serien"""
        search_window = tk.Toplevel(self.root)
        search_window.title("🔍 Suche nach Filmen und Serien")
        search_window.transient(self.root)
        self._fit_dialog(search_window, 1100, 860, 860, 620)
        
        main_frame = ttk.Frame(search_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Suchfeld
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Suche:", font=("Arial", 16, "bold")).pack(side=tk.LEFT, padx=(0, 8))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, font=("Arial", 14))
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True, ipady=6)
        self._entry_place_caret(search_entry)
        self._entry_edit_menu(search_entry)
        
        search_button = ttk.Button(search_frame, text="🔍 Suchen", command=lambda: self._perform_search(search_var.get(), results_frame, status_label, scope_var.get()), style="Download.TButton.Large")
        search_button.pack(side=tk.LEFT, padx=5, ipady=4)

        scope_var = tk.StringVar(value="video")
        scope_row = ttk.Frame(main_frame)
        scope_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(scope_row, text="Bereich:", font=("Arial", 13)).pack(side=tk.LEFT, padx=(0, 8))
        for label, value in (("Video", "video"), ("Musik", "music"), ("Beides", "both")):
            ttk.Radiobutton(scope_row, text=label, variable=scope_var, value=value, style="Download.TRadiobutton").pack(side=tk.LEFT, padx=(0, 14))
        
        # Enter-Taste für Suche
        search_entry.bind('<Return>', lambda e: self._perform_search(search_var.get(), results_frame, status_label, scope_var.get()))
        
        # Status-Label
        status_label = ttk.Label(main_frame, text="Geben Sie einen Suchbegriff ein und klicken Sie auf 'Suchen'", foreground='gray')
        status_label.pack(pady=5)
        
        # Ergebnisse-Frame mit Scrollbar
        results_container = ttk.Frame(main_frame)
        results_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(
            results_container,
            bg=getattr(self, '_tk_bg_panel', '#383838'),
            highlightthickness=0,
        )
        self._search_results_canvas = canvas
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=canvas.yview)
        results_frame = ttk.Frame(canvas)
        
        results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        results_window = canvas.create_window((0, 0), window=results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _stretch_search_results(event):
            canvas.itemconfig(results_window, width=max(400, event.width))
        canvas.bind("<Configure>", _stretch_search_results)
        self._bind_scroll_wheel(canvas, results_frame)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Fokus auf Suchfeld
        search_entry.focus()
    
    def _get_sender_logo(self, sender: str) -> str:
        """Gibt das Senderlogo/Emoji für einen Sender zurück"""
        sender_logos = {
            'youtube': '📺',
            'ard': '🔴',
            'zdf': '🔵',
            'orf': '🟠',
            'swr': '🟡',
            'br': '🟢',
            'wdr': '🟣',
            'mdr': '🔵',
            'ndr': '🟢',
            'hr': '🟠',
            'rbb': '🔴',
            'sr': '🟡',
            'arte': '🎨',
            'phoenix': '📡',
            'tagesschau': '📰',
            'rbtv': '🚀'
        }
        return sender_logos.get(sender.lower(), '📺')
    
    def _detect_sender_from_url(self, url: str) -> str:
        """Erkennt den Sender aus der URL"""
        if not SUPPORTED_SENDERS:
            return 'unknown'
        url_lower = url.lower()
        for sender, domains in SUPPORTED_SENDERS.items():
            for domain in domains:
                if domain in url_lower:
                    return sender
        return 'unknown'
    
    def _perform_search(self, query: str, results_frame: ttk.Frame, status_label: ttk.Label, scope: str = "video"):
        """Video: Mediathek und YouTube. Musik: ARD Audiothek. Beides: alle drei."""
        if not query.strip():
            messagebox.showwarning("Warnung", "Bitte geben Sie einen Suchbegriff ein.")
            return
        scope = scope if scope in ("video", "music", "both") else "video"
        for widget in results_frame.winfo_children():
            widget.destroy()
        where = {"video": "der ARD-Mediathek, beim ZDF und auf YouTube", "music": "der ARD Audiothek", "both": "Video und Musik"}[scope]
        status_label.config(text=f"Suche nach „{query.strip()}“ in {where}…", foreground="blue")

        def search_thread():
            ard_results = []
            zdf_results = []
            audio_results = []
            ard_error = ""
            zdf_error = ""
            youtube_results = []
            if scope in ("video", "both"):
                try:
                    if mediathek_search is not None:
                        ard_results = mediathek_search.search_ard(query.strip())
                except Exception as exc:
                    ard_error = str(exc)
                try:
                    if mediathek_search is not None:
                        zdf_results = mediathek_search.search_zdf(query.strip())
                except Exception as exc:
                    zdf_error = str(exc)
                try:
                    youtube_results = self._search_youtube_results(query.strip())
                except Exception:
                    youtube_results = []
            if scope in ("music", "both") and mediathek_search is not None:
                try:
                    audio_results = mediathek_search.search_audiothek(query.strip())
                except Exception as exc:
                    if not ard_error:
                        ard_error = str(exc)
            shown = list(ard_results or [])
            zdf = list(zdf_results or [])
            videos = list(youtube_results or [])
            audio = list(audio_results or [])
            err = ard_error
            zerr = zdf_error
            self.root.after(0, lambda a=shown, y=videos, u=audio, e=err, z=zdf, ze=zerr: self._display_search_results_list(
                a, y, results_frame, status_label, query.strip(), e, u, z, ze
            ))

        threading.Thread(target=search_thread, daemon=True).start()

    def _search_youtube_results(self, query: str) -> List[Dict]:
        from yt_dlp_helper import get_ytdlp_command
        cmd = get_ytdlp_command() + [
            "--dump-json", "--flat-playlist", "--no-warnings", f"ytsearch8:{query.casefold()}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        found = []
        for line in (result.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                info = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = info.get("url") or info.get("webpage_url") or ""
            if url and not str(url).startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"
            if not url:
                continue
            uploader = info.get("uploader") or info.get("channel") or "YouTube"
            video_id = (info.get("id") or "").strip()
            image = ""
            thumbs = [t for t in (info.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
            if thumbs:
                thumbs.sort(key=lambda t: int(t.get("width") or 0))
                image = thumbs[-1]["url"]
            elif video_id:
                image = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            found.append({
                "kind": "video",
                "source": "youtube",
                "title": info.get("title") or video_id or "Unbekannt",
                "url": url,
                "duration": info.get("duration") or 0,
                "uploader": uploader,
                "publisher": f"YouTube ({uploader})",
                "view_count": info.get("view_count") or 0,
                "image": image,
                "seasons": [],
            })
        return found

    def _search_drop_episode_dupes(self, ard_results, youtube_results) -> List[Dict]:
        """YouTube-Einzelfolgen ausblenden, wenn dieselbe Serie schon in der Mediathek liegt."""
        series_titles = []
        for item in ard_results or []:
            if item.get("kind") != "series":
                continue
            title = " ".join((item.get("title") or "").casefold().split())
            if len(title) >= 4:
                series_titles.append(title)
        if not series_titles:
            return list(youtube_results or [])
        kept = []
        for item in youtube_results or []:
            title = " ".join((item.get("title") or "").casefold().split())
            if any(series in title for series in series_titles):
                continue
            kept.append(item)
        return kept

    def _search_season_label(self, seasons) -> str:
        nums = sorted({int(n) for n in (seasons or [])})
        if not nums:
            return ""
        ranges = []
        start = prev = nums[0]
        for num in nums[1:]:
            if num == prev + 1:
                prev = num
                continue
            ranges.append(f"{start}–{prev}" if start != prev else str(start))
            start = prev = num
        ranges.append(f"{start}–{prev}" if start != prev else str(start))
        word = "Staffel" if len(nums) == 1 else "Staffeln"
        return f"{word} {', '.join(ranges)}"
    
    def _display_search_results_list(self, ard_results, youtube_results, results_frame, status_label, query, ard_error="", audio_results=None, zdf_results=None, zdf_error=""):
        """Serien und Filme oben, ZDF und Hörspiele danach, YouTube darunter."""
        for widget in results_frame.winfo_children():
            widget.destroy()
        results_frame._photos = []
        ard_results = list(ard_results or [])
        zdf_results = list(zdf_results or [])
        audio_results = list(audio_results or [])
        youtube_results = self._search_drop_episode_dupes(ard_results + zdf_results, youtube_results)
        if not ard_results and not youtube_results and not audio_results and not zdf_results:
            extra = f" ({ard_error or zdf_error})" if (ard_error or zdf_error) else ""
            status_label.config(text=f"Keine Ergebnisse für „{query}“{extra}", foreground="orange")
            return
        bits = []
        if ard_results:
            bits.append(f"{len(ard_results)} in der ARD-Mediathek")
        if zdf_results:
            bits.append(f"{len(zdf_results)} beim ZDF")
        if audio_results:
            bits.append(f"{len(audio_results)} in der Audiothek")
        if youtube_results:
            bits.append(f"{len(youtube_results)} auf YouTube")
        notes = []
        if ard_error and not ard_results:
            notes.append(f"ARD: {ard_error}")
        if zdf_error and not zdf_results:
            notes.append(f"ZDF: {zdf_error}")
        note = (" — " + " · ".join(notes)) if notes else ""
        status_label.config(text="Gefunden: " + ", ".join(bits) + note, foreground="green")
        if ard_error and not ard_results:
            ttk.Label(
                results_frame,
                text=f"ARD-Mediathek gerade nicht erreichbar: {ard_error}",
                foreground="red",
                wraplength=640,
            ).pack(anchor=tk.W, padx=6, pady=(4, 2))
        if zdf_error and not zdf_results:
            ttk.Label(
                results_frame,
                text=f"ZDF-Mediathek gerade nicht erreichbar: {zdf_error}",
                foreground="red",
                wraplength=640,
            ).pack(anchor=tk.W, padx=6, pady=(4, 2))
        if ard_results:
            ttk.Label(results_frame, text="Serien und Filme", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=6, pady=(4, 2))
            for item in ard_results:
                self._search_result_card(results_frame, item)
        if zdf_results:
            ttk.Label(results_frame, text="ZDF-Mediathek", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=6, pady=(12, 2))
            for item in zdf_results:
                self._search_result_card(results_frame, item)
        if audio_results:
            ttk.Label(results_frame, text="Hörspiele und Podcasts", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=6, pady=(12, 2))
            for item in audio_results:
                self._search_result_card(results_frame, item)
        if youtube_results:
            ttk.Label(results_frame, text="YouTube", font=("Arial", 12, "bold")).pack(anchor=tk.W, padx=6, pady=(12, 2))
            for item in youtube_results:
                self._search_result_card(results_frame, item)
        results_frame.update_idletasks()
        canvas = results_frame.master
        if isinstance(canvas, tk.Canvas):
            canvas.configure(scrollregion=canvas.bbox("all"))

    def _search_result_card(self, parent, item: Dict):
        card = ttk.LabelFrame(parent, padding="8")
        card.pack(fill=tk.X, padx=6, pady=4)
        row = ttk.Frame(card)
        row.pack(fill=tk.X)
        image_url = (item.get("image") or "").strip()
        if image_url:
            holder = ttk.Label(row, text="")
            holder.pack(side=tk.LEFT, padx=(0, 10))
            self._search_load_thumb(holder, image_url, parent)
        text = ttk.Frame(row)
        text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        wrap = 640
        canvas = getattr(self, "_search_results_canvas", None)
        if canvas is not None:
            try:
                cw = canvas.winfo_width()
                if cw > 240:
                    wrap = max(420, cw - 200)
            except tk.TclError:
                pass
        ttk.Label(text, text=item.get("title") or "Unbekannt", font=("Arial", 14, "bold"), wraplength=wrap).pack(anchor=tk.W)
        meta = []
        series_name = (item.get("series_name") or "").strip()
        if series_name and item.get("kind") != "series" and series_name.casefold() != (item.get("title") or "").casefold():
            meta.append(f"Folge von {series_name}")
        if item.get("publisher"):
            meta.append(item["publisher"])
        season_label = self._search_season_label(item.get("seasons"))
        if season_label:
            meta.append(season_label + " verfügbar")
        if item.get("episode_count"):
            meta.append(f"{int(item['episode_count'])} Folgen")
        if item.get("year"):
            meta.append(str(item["year"]))
        duration = int(item.get("duration") or 0)
        if duration:
            meta.append(f"{duration // 60}:{duration % 60:02d}")
        if item.get("view_count"):
            meta.append(f"{int(item['view_count']):,} Aufrufe".replace(",", "."))
        if item.get("kind") == "series":
            kind_name = "Serie"
        elif item.get("kind") == "movie":
            kind_name = "Film"
        elif item.get("kind") == "audio":
            kind_name = "Hörspiel"
        else:
            kind_name = "Video"
        meta.insert(0, kind_name)
        if meta:
            ttk.Label(text, text=" · ".join(meta), foreground="gray").pack(anchor=tk.W, pady=(2, 0))
        blurb = (item.get("description") or "").strip()
        if blurb:
            ttk.Label(text, text=blurb, wraplength=wrap, justify=tk.LEFT, font=("Arial", 12)).pack(anchor=tk.W, pady=(4, 0))
        buttons = ttk.Frame(card)
        buttons.pack(fill=tk.X, pady=(8, 0))
        title = item.get("title") or ""
        url = item.get("url") or ""
        if item.get("kind") == "series":
            ttk.Button(buttons, text="Herunterladen", command=lambda it=item: self._search_open_series(it), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
            ttk.Button(buttons, text="▶ Ansehen", command=lambda it=item: self._search_open_series(it), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        elif item.get("kind") == "audio" and int(item.get("episode_count") or 0) > 1:
            ttk.Button(buttons, text="Herunterladen", command=lambda it=item: self._search_open_series(it), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
            ttk.Button(buttons, text="▶ Anhören", command=lambda it=item: self._search_open_series(it), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        elif item.get("kind") == "audio":
            ttk.Button(buttons, text="Herunterladen", command=lambda u=url, t=title: self._download_from_search(u, t, direct=True), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
            ttk.Button(buttons, text="Zur Queue", command=lambda u=url, t=title: self._download_from_search(u, t, direct=False), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
            if url:
                ttk.Button(buttons, text="▶ Anhören", command=lambda u=url, t=title: self._preview_video(u, t), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        else:
            ttk.Button(buttons, text="Herunterladen", command=lambda u=url, t=title: self._download_from_search(u, t, direct=True), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
            ttk.Button(buttons, text="Zur Queue", command=lambda u=url, t=title: self._download_from_search(u, t, direct=False), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)
        if url and item.get("kind") not in ("series", "audio"):
            ttk.Button(buttons, text="▶ Ansehen", command=lambda u=url, t=title: self._preview_video(u, t), style="Download.TButton").pack(side=tk.LEFT, padx=(0, 8), ipady=2)

    def _search_load_thumb(self, holder, image_url: str, store_on):
        def work():
            try:
                if mediathek_search is None:
                    return
                raw = mediathek_search._get_json  # noqa: keep import path
                import io
                import urllib.request
                req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
                data = None
                for ctx in mediathek_search._contexts():
                    try:
                        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                            data = resp.read()
                        break
                    except Exception:
                        data = None
                if not data:
                    return
                from PIL import Image, ImageTk
                img = Image.open(io.BytesIO(data))
                img.thumbnail((168, 94))
                def apply():
                    try:
                        if not holder.winfo_exists():
                            return
                        photo = ImageTk.PhotoImage(img)
                        holder.configure(image=photo)
                        photos = getattr(store_on, "_photos", None)
                        if photos is None:
                            store_on._photos = []
                            photos = store_on._photos
                        photos.append(photo)
                    except Exception:
                        pass
                self.root.after(0, apply)
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _download_from_search(self, url: str, title: str, direct: bool = True):
        """Film oder YouTube-Video sofort laden oder in die Video-Queue legen."""
        if not (url or "").strip():
            messagebox.showinfo("Hinweis", "Für diesen Treffer gibt es noch keinen Download-Link.")
            return
        self._add_to_download_queue(url, show_dialog=False, display_title=title)
        audio = _is_music_mediathek_url(url)
        try:
            target = self.music_frame if audio else self.video_frame
            self.notebook.select(self.notebook.index(target))
        except Exception:
            pass
        if direct:
            self._video_queue_hold = False
            self.video_download_cancelled = False
            self._process_download_queue()
            messagebox.showinfo("Download", f"„{title}“ wird heruntergeladen.")
        else:
            self._update_queue_status()
            where = "Musik-Queue" if audio else "Video-Queue"
            messagebox.showinfo("Queue", f"„{title}“ liegt in der {where}.")

    def _search_open_series(self, item: Dict):
        """Staffelansicht wie bei „Folgen habe ich“, ohne Ignorieren, mit Ansehen pro Folge."""
        if mediathek_search is None:
            messagebox.showerror("Suche", "Die Mediathek-Suche ist nicht verfügbar.")
            return
        parent = self.root
        win = tk.Toplevel(parent)
        win.title(item.get("title") or "Serie")
        win.transient(parent)
        self._apply_dark_toplevel(win)
        self._fit_dialog(win, 960, 740, 720, 520)
        main = ttk.Frame(win, padding="12", style="Download.TFrame")
        main.pack(fill=tk.BOTH, expand=True)
        season_label = self._search_season_label(item.get("seasons"))
        audio = item.get("kind") == "audio"
        ttk.Label(
            main,
            text=(
                f"{item.get('title') or 'Serie'}"
                + (f" · {item.get('publisher')}" if item.get("publisher") else "")
                + (f" · {season_label}" if season_label else "")
                + (
                    "\nHaken links = laden oder mehrere Folgen nacheinander anhören. Anhören an einer Folge spielt nur diese."
                    if audio else
                    "\nHaken links = laden oder mehrere Folgen nacheinander ansehen. Ansehen an einer Folge spielt nur diese."
                )
            ),
            wraplength=900,
            justify=tk.LEFT,
            style="Download.TLabel",
        ).pack(anchor=tk.W, pady=(0, 8))
        status = ttk.Label(main, text="Folgen werden geladen…", foreground="blue")
        status.pack(anchor=tk.W, pady=(0, 6))
        host = ttk.Frame(main)
        host.pack(fill=tk.BOTH, expand=True)

        def loaded(seasons, error):
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return
            if error:
                status.config(text=f"Folgen konnten nicht geladen werden: {error}", foreground="red")
                return
            if not seasons:
                status.config(text="Aktuell sind keine Folgen verfügbar.", foreground="orange")
                return
            total = sum(len(v) for v in seasons.values())
            status.config(text=f"{total} Folgen in {len(seasons)} Staffel(n).", foreground="green")
            self._search_fill_season_list(win, host, seasons, item, status)

        def work():
            try:
                seasons = mediathek_search.load_series_seasons(item)
                err = ""
            except Exception as exc:
                seasons, err = {}, str(exc)
            self.root.after(0, lambda: loaded(seasons, err))

        threading.Thread(target=work, daemon=True).start()

    def _ask_resume_playback(self, title: str, seconds: float) -> bool:
        whole = max(0, int(seconds))
        minutes, secs = divmod(whole, 60)
        hours, minutes = divmod(minutes, 60)
        stamp = f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"
        text = f"„{title}“ war bei {stamp}.\n\nDort weitermachen oder von vorn starten?"
        if sys.platform == "darwin":
            return bool(_mac_tk_dialog("Weitermachen", text, [("Weitermachen", True), ("Von vorn", False)], None))
        return bool(messagebox.askyesno("Weitermachen", text))

    def _preview_video(self, url: str, title: str, parent=None, status=None, image: str = "", stream_url: str = ""):
        """Spielt die Folge in einem eigenen Fenster, nicht im Browser."""
        try:
            import preview_player
        except ImportError:
            messagebox.showerror("Wiedergabe", "Der eingebaute Player ist nicht verfügbar.", parent=parent)
            return
        if status is not None:
            status.config(text="Wiedergabe wird vorbereitet…", foreground="blue")

        def report(msg):
            if status is not None:
                try:
                    status.config(text=str(msg).replace("\n", " "), foreground="red")
                except Exception:
                    pass
            messagebox.showerror("Wiedergabe", msg, parent=parent)

        def started():
            if status is not None:
                try:
                    status.config(text="Wiedergabe läuft im Player-Fenster.", foreground="green")
                except Exception:
                    pass

        preview_player.open_preview(
            url,
            title,
            self.root.after,
            report,
            self._ask_resume_playback,
            started,
            image,
            stream_url,
        )

    def _search_claim_owned(self, item: Dict, episodes: List[Dict]):
        if series_watch is None:
            return
        try:
            series_watch.claim_episodes_as_owned(
                self.base_download_path,
                series_title=item.get("title") or "",
                asset_id=item.get("asset_id") or "",
                episodes=episodes,
            )
        except Exception:
            pass

    def _search_fill_season_list(self, win, host, seasons: Dict, item: Dict, status=None):
        for widget in host.winfo_children():
            widget.destroy()
        list_frame = ttk.Frame(host)
        list_frame.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(list_frame, highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        self._bind_scroll_wheel(canvas, scrollable)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win_id, width=e.width))

        def season_key(sn):
            try:
                return (0, int(sn))
            except (TypeError, ValueError):
                return (1, 0)

        download_vars = {}
        rows = {}
        quick = ttk.Frame(host)
        quick.pack(fill=tk.X, pady=(0, 6), before=list_frame)

        def select_all(on: bool):
            for var in download_vars.values():
                var.set(on)

        ttk.Button(quick, text="Alle Folgen auswählen", command=lambda: select_all(True)).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(quick, text="Alle abwählen", command=lambda: select_all(False)).pack(side=tk.LEFT)

        pending = []
        for sn in sorted(seasons.keys(), key=season_key):
            eps = seasons.get(sn) or []
            if not eps:
                continue
            title = f"Staffel {sn} ({len(eps)} Folgen)" if sn is not None else f"Weitere Folgen ({len(eps)})"
            lf = ttk.LabelFrame(scrollable, text=title, padding="8")
            lf.pack(fill=tk.X, padx=4, pady=6)
            season_var = tk.BooleanVar(value=False)
            keys = []
            for ep in eps:
                key = len(rows) + 1
                rows[key] = ep
                keys.append(key)
                var = tk.BooleanVar(value=False)
                download_vars[key] = var
                label = ep.get("title") or "?"
                if len(label) > 78:
                    label = label[:75] + "…"
                pending.append((
                    lf, key, label, var, ep.get("url") or "",
                    ep.get("image") or "",
                    ep.get("stream_url") or "",
                ))

            def make_toggle(bound_keys, svar):
                def toggle():
                    for key in bound_keys:
                        if key in download_vars:
                            download_vars[key].set(svar.get())
                return toggle

            toggle_text = f"Gesamte Staffel {sn} markieren" if sn is not None else "Gesamte Liste markieren"
            ttk.Checkbutton(lf, text=toggle_text, variable=season_var, command=make_toggle(keys, season_var)).pack(anchor=tk.W, pady=(0, 4))

        def add_chunk(start=0, size=24):
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return
            end = min(start + size, len(pending))
            for lf, key, label, var, url, image, stream_url in pending[start:end]:
                line = ttk.Frame(lf)
                line.pack(fill=tk.X, padx=4, pady=1)
                ttk.Checkbutton(line, text=label, variable=var).pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W)
                if url or stream_url:
                    row_listen = "Anhören" if item.get("kind") == "audio" else "Ansehen"
                    ttk.Button(
                        line,
                        text=row_listen,
                        command=lambda u=url, t=label, img=image, s=stream_url, st=status: self._preview_video(
                            u, t, parent=win, status=st, image=img, stream_url=s,
                        ),
                    ).pack(side=tk.RIGHT)
            if end < len(pending):
                win.after(1, lambda n=end: add_chunk(n))
            else:
                try:
                    canvas.configure(scrollregion=canvas.bbox("all"))
                except Exception:
                    pass

        def collect():
            out = []
            for key, var in download_vars.items():
                if var.get():
                    ep = rows.get(key)
                    if ep and (ep.get("url") or "").strip():
                        out.append(ep)
            return out

        def watch_selected():
            eps = collect()
            if not eps:
                word = "Anhören" if item.get("kind") == "audio" else "Ansehen"
                messagebox.showinfo("Hinweis", f"Keine Folge zum {word} ausgewählt.", parent=win)
                return
            try:
                import preview_player
            except ImportError:
                messagebox.showerror("Anhören" if item.get("kind") == "audio" else "Ansehen", "Der eingebaute Player ist nicht verfügbar.", parent=win)
                return
            try:
                status.config(text="Wiedergabe wird vorbereitet…", foreground="blue")
            except Exception:
                pass
            preview_player.open_preview_list(
                [{
                    "url": ep.get("url") or "",
                    "title": ep.get("title") or "",
                    "image": ep.get("image") or "",
                    "stream_url": ep.get("stream_url") or "",
                } for ep in eps],
                self.root.after,
                lambda msg: messagebox.showerror("Wiedergabe", msg, parent=win),
                self._ask_resume_playback,
                lambda: status.config(text="Wiedergabe läuft im Player-Fenster.", foreground="green") if status is not None else None,
            )

        def to_queue():
            eps = collect()
            if not eps:
                messagebox.showinfo("Hinweis", "Nichts zum Laden ausgewählt.", parent=win)
                return
            if item.get("kind") != "audio":
                self._search_claim_owned(item, eps)
            self._series_watch_add_episodes_to_video_queue(eps)
            where = "Musik-Queue" if item.get("kind") == "audio" else "Video-Queue"
            extra = "" if item.get("kind") == "audio" else " und gelten für den Serien-Wächter als vorhanden"
            messagebox.showinfo("Queue", f"{len(eps)} Folge(n) liegen in der {where}{extra}.", parent=win)

        def download_now():
            eps = collect()
            if not eps:
                messagebox.showinfo("Hinweis", "Nichts zum Laden ausgewählt.", parent=win)
                return
            if item.get("kind") != "audio":
                self._search_claim_owned(item, eps)
            self._series_watch_add_episodes_to_video_queue(eps)
            try:
                target = self.music_frame if item.get("kind") == "audio" else self.video_frame
                self.notebook.select(self.notebook.index(target))
            except Exception:
                pass
            self._video_queue_hold = False
            self.video_download_cancelled = False
            self._process_download_queue()
            messagebox.showinfo("Download", f"Download von {len(eps)} Folge(n) gestartet.", parent=win)

        bar = ttk.Frame(win)
        bar.pack(fill=tk.X, padx=12, pady=(0, 10))
        listen_all = "Ausgewählte anhören" if item.get("kind") == "audio" else "Ausgewählte ansehen"
        ttk.Button(bar, text=listen_all, command=watch_selected).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="Ausgewählte zur Queue", command=to_queue).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="Ausgewählte herunterladen", command=download_now).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(bar, text="Schließen", command=win.destroy).pack(side=tk.RIGHT)
        win.after(1, add_chunk)

    def show_statistics(self):
        """Zeigt Download-Statistiken"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Download-Statistiken")
        stats_window.transient(self.root)
        self._apply_dark_toplevel(stats_window)
        self._fit_dialog(stats_window, 720, 640, 480, 420)
        
        frame = ttk.Frame(stats_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Download-Statistiken", font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 12))

        def _block(title, stats):
            last = stats.get('last_download') or 'Nie'
            return (
                f"{title}\n"
                f"Downloads: {stats.get('total_downloads', 0)}\n"
                f"Erfolgreich: {stats.get('successful_downloads', 0)}\n"
                f"Fehlgeschlagen: {stats.get('failed_downloads', 0)}\n"
                f"Gesamt-Größe: {self._format_size(stats.get('total_size', 0))}\n"
                f"Letzter Download: {last}"
            )

        video_stats = getattr(self, 'video_statistics', {}) or {}
        music_stats = getattr(self, 'music_statistics', {}) or {}
        combined = {
            'total_downloads': int(video_stats.get('total_downloads') or 0) + int(music_stats.get('total_downloads') or 0),
            'successful_downloads': int(video_stats.get('successful_downloads') or 0) + int(music_stats.get('successful_downloads') or 0),
            'failed_downloads': int(video_stats.get('failed_downloads') or 0) + int(music_stats.get('failed_downloads') or 0),
            'total_size': int(video_stats.get('total_size') or 0) + int(music_stats.get('total_size') or 0),
            'last_download': max(
                [t for t in (video_stats.get('last_download'), music_stats.get('last_download')) if t and t != 'Nie'],
                default=None,
            ),
        }
        fail_path = self._failed_downloads_path()
        blocks = ttk.Frame(frame)
        blocks.pack(anchor=tk.NW, fill=tk.X)
        block_labels = []
        for title, data in (("Zusammen", combined), ("Video", video_stats), ("Musik", music_stats)):
            lab = ttk.Label(blocks, text=_block(title, data), justify=tk.LEFT, anchor=tk.NW, font=("Arial", 15))
            block_labels.append(lab)
        footer = ttk.Label(
            blocks,
            text=(
                f"Geplante Downloads: {len(self.video_scheduled_downloads)}\n"
                f"Favoriten: {len(self.video_favorites)}\n"
                f"Historie-Einträge: {len(self.video_download_history)}\n\n"
                f"Fehlgeschlagene Links (zum Nachreichen):\n{fail_path}"
            ),
            justify=tk.LEFT,
            anchor=tk.NW,
            font=("Arial", 15),
        )
        stats_layout = {"wide": None, "size": None}

        def _place_stats(width):
            wide = width >= 860
            size = 18 if width >= 1200 else 16 if width >= 860 else 14
            if stats_layout["wide"] == wide and stats_layout["size"] == size:
                return
            stats_layout["wide"] = wide
            stats_layout["size"] = size
            for lab in block_labels:
                lab.grid_forget()
            footer.grid_forget()
            for lab in block_labels + [footer]:
                lab.configure(font=("Arial", size))
            if wide:
                for i, lab in enumerate(block_labels):
                    lab.grid(row=0, column=i, sticky=tk.NW, padx=(0, 36), pady=(0, 8))
                footer.grid(row=1, column=0, columnspan=3, sticky=tk.NW, pady=(12, 0))
            else:
                for i, lab in enumerate(block_labels):
                    lab.grid(row=i, column=0, sticky=tk.NW, pady=(0, 12))
                footer.grid(row=len(block_labels), column=0, sticky=tk.NW, pady=(4, 0))

        def _grow_stats(event):
            if event.widget is frame:
                _place_stats(event.width)

        frame.bind("<Configure>", _grow_stats)
        frame.after(50, lambda: _place_stats(max(640, frame.winfo_width())))
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def reset_stats():
            if messagebox.askyesno("Bestätigen", "Statistiken wirklich zurücksetzen?"):
                empty = {
                    'total_downloads': 0,
                    'total_size': 0,
                    'successful_downloads': 0,
                    'failed_downloads': 0,
                    'last_download': None
                }
                self.video_statistics = dict(empty)
                self.music_statistics = dict(empty)
                self._save_video_data()
                stats_window.destroy()
                self.show_statistics()
        
        def open_failed_list():
            path = self._failed_downloads_path()
            if not path.exists() or not path.read_text(encoding="utf-8").strip():
                messagebox.showinfo("Hinweis", "Noch keine fehlgeschlagenen Downloads.", parent=stats_window)
                return
            self._open_file_with_default_app(path)

        def copy_failed_list():
            path = self._failed_downloads_path()
            text = path.read_text(encoding="utf-8").strip() if path.exists() else ""
            if not text:
                messagebox.showinfo("Hinweis", "Noch keine fehlgeschlagenen Downloads.", parent=stats_window)
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Kopiert", "Die Liste liegt in der Zwischenablage und kann in GitHub oder eine E-Mail eingefügt werden.", parent=stats_window)

        ttk.Button(button_frame, text="Liste öffnen", command=open_failed_list).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Liste kopieren", command=copy_failed_list).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(button_frame, text="Statistiken zurücksetzen", command=reset_stats).pack(side=tk.LEFT)
    
    def _ensure_dependencies_background(self):
        """Prüft und installiert Abhängigkeiten im Hintergrund - DEAKTIVIERT.
        
        Abhängigkeiten werden manuell installiert (z.B. in .deb/.exe Builds).
        Diese Funktion wird nicht mehr ausgeführt.
        """
        # Komplett deaktiviert - Abhängigkeiten werden manuell installiert
        try:
            self._write_to_log_file("[DEBUG] Abhängigkeits-Installation deaktiviert (manuelle Installation)", "DEBUG")
        except Exception:
            pass  # Falls Log noch nicht verfügbar ist
        return
    
    def _show_dependency_installation_dialog(self):
        """Zeigt Dialog während der Abhängigkeits-Installation"""
        if hasattr(self, '_dep_dialog') and self._dep_dialog.winfo_exists():
            return  # Dialog bereits vorhanden
        
        self._dep_dialog = tk.Toplevel(self.root)
        self._dep_dialog.title("Abhängigkeiten installieren")
        self._dep_dialog.geometry("500x300")
        self._dep_dialog.transient(self.root)
        # NICHT grab_set() verwenden, damit die Hauptanwendung weiterhin schließbar ist
        # self._dep_dialog.grab_set()
        
        # Erlaube Schließen des Dialogs (aber warne wenn Installation läuft)
        self._dep_installation_running = True
        def on_dialog_close():
            if self._dep_installation_running:
                if messagebox.askyesno(
                    "Installation läuft",
                    "Die Installation läuft noch. Möchten Sie den Dialog wirklich schließen?\n\n"
                    "Die Installation wird im Hintergrund fortgesetzt."
                ):
                    self._dep_dialog.destroy()
            else:
                self._dep_dialog.destroy()
        self._dep_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)
        
        frame = ttk.Frame(self._dep_dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            frame,
            text="Installiere fehlende Abhängigkeiten...",
            font=("Arial", 12, "bold")
        ).pack(pady=10)
        
        ttk.Label(
            frame,
            text="Bitte warten Sie, während die benötigten Komponenten installiert werden.",
            wraplength=450
        ).pack(pady=5)
        
        # Status-Text
        self._dep_status_text = scrolledtext.ScrolledText(
            frame,
            height=10,
            width=60,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self._dep_status_text.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # Progress Bar
        self._dep_progress = ttk.Progressbar(
            frame,
            mode='indeterminate'
        )
        self._dep_progress.pack(fill=tk.X, pady=5)
        self._dep_progress.start()
        
        # Schließen-Button (zunächst deaktiviert)
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=10)
        
        self._dep_close_button = ttk.Button(
            button_frame,
            text="Schließen",
            command=self._dep_dialog.destroy,
            state=tk.DISABLED
        )
        self._dep_close_button.pack()
        
        # Starte Status-Updates
        self._dep_status_text.config(state=tk.NORMAL)
        self._dep_status_text.insert(tk.END, "[INFO] Prüfe Abhängigkeiten...\n")
        self._dep_status_text.config(state=tk.DISABLED)
        self._dep_status_text.see(tk.END)
    
    def _add_status_message(self, message):
        """Fügt eine Status-Nachricht zum Installations-Dialog hinzu"""
        if hasattr(self, '_dep_status_text') and self._dep_status_text.winfo_exists():
            self._dep_status_text.config(state=tk.NORMAL)
            self._dep_status_text.insert(tk.END, message + "\n")
            self._dep_status_text.config(state=tk.DISABLED)
            self._dep_status_text.see(tk.END)
    
    def _update_dependency_dialog(self, ytdlp_ok, ffmpeg_ok, messages, has_updates=False):
        """Aktualisiert den Installations-Dialog mit Ergebnissen
        Zeigt Installation von requirements.txt und ffmpeg
        """
        if not hasattr(self, '_dep_dialog') or not self._dep_dialog.winfo_exists():
            return
        
        # Markiere Installation als beendet
        self._dep_installation_running = False
        
        # Stoppe Progress Bar
        self._dep_progress.stop()
        
        # Zeige alle Meldungen (requirements.txt und ffmpeg)
        self._dep_status_text.config(state=tk.NORMAL)
        for msg in messages:
            self._dep_status_text.insert(tk.END, msg + "\n")
        self._dep_status_text.config(state=tk.DISABLED)
        self._dep_status_text.see(tk.END)
        
        # Aktiviere Schließen-Button
        self._dep_close_button.config(state=tk.NORMAL)
        
        # Erlaube Schließen ohne Warnung
        self._dep_dialog.protocol("WM_DELETE_WINDOW", self._dep_dialog.destroy)
        
        # Zeige Erfolgsmeldung und frage nach Neustart
        # Frage nach Neustart wenn Updates durchgeführt wurden oder Installation nötig war
        if has_updates or not ffmpeg_ok:
            self._dep_status_text.config(state=tk.NORMAL)
            if ffmpeg_ok:
                self._dep_status_text.insert(tk.END, "\n[OK] Alle Abhängigkeiten wurden erfolgreich installiert!\n")
                self._dep_status_text.insert(tk.END, "\nDie Anwendung wird automatisch neu gestartet...\n")
            else:
                self._dep_status_text.insert(tk.END, "\n[WARNING] ffmpeg konnte nicht installiert werden.\n")
                self._dep_status_text.insert(tk.END, "Die Anwendung kann möglicherweise nicht vollständig funktionieren.\n")
            self._dep_status_text.config(state=tk.DISABLED)
            self._dep_status_text.see(tk.END)
            
            # Frage nach Neustart nur wenn ffmpeg installiert wurde
            if ffmpeg_ok:
                # Warte 2 Sekunden, dann automatisch Neustart fragen
                self.root.after(2000, lambda: self._ask_restart_after_dependency_install())
        else:
            self._dep_status_text.config(state=tk.NORMAL)
            self._dep_status_text.insert(tk.END, "\n[OK] Alle Abhängigkeiten sind vorhanden.\n")
            self._dep_status_text.config(state=tk.DISABLED)
            self._dep_status_text.see(tk.END)
            # Schließe Dialog automatisch nach 2 Sekunden wenn alles OK ist
            self.root.after(2000, self._dep_dialog.destroy)
    
    def _ask_restart_after_dependency_install(self):
        """Fragt ob die Anwendung nach Abhängigkeits-Installation neu gestartet werden soll"""
        if not hasattr(self, '_dep_dialog') or not self._dep_dialog.winfo_exists():
            return
        
        # Prüfe ob wir gerade nach einem Neustart sind (verhindere Endlosschleife)
        restart_flag_file = Path(tempfile.gettempdir()) / "universal_downloader_restarting.flag"
        if restart_flag_file.exists():
            # Wir wurden gerade neu gestartet - frage nicht nach Neustart
            self._dep_dialog.destroy()
            return
        
        result = messagebox.askyesno(
            "Abhängigkeiten installiert",
            "Die Abhängigkeiten wurden erfolgreich installiert.\n\n"
            "Möchten Sie die Anwendung jetzt neu starten, um sicherzustellen, "
            "dass alle Komponenten korrekt geladen werden?",
            parent=self._dep_dialog
        )
        
        if result:
            self._dep_dialog.destroy()
            # Warte kurz, damit der Dialog geschlossen wird
            self.root.after(100, lambda: self._restart_application(Path()))
    
    def _maybe_show_changelog_after_update(self):
        """Zeigt nach einem Versionswechsel (oder erstem Start) den Changelog-Dialog."""
        try:
            from version import get_version, compare_versions
            from changelog import changelog_text_for_upgrade
        except Exception:
            return
        curr = get_version()
        prev = str(self.settings.get("last_seen_changelog_version", "") or "").strip()
        if prev == curr:
            return
        if prev:
            try:
                if compare_versions(prev, curr) > 0:
                    self.settings["last_seen_changelog_version"] = curr
                    self._save_settings()
                    return
            except Exception:
                pass
        body = changelog_text_for_upgrade(prev if prev else "0.0.0", curr)
        if not body:
            self.settings["last_seen_changelog_version"] = curr
            self._save_settings()
            return
        self._show_changelog_dialog(body, mark_seen_on_close=True)

    def show_changelog_window(self, full_history: bool = False):
        """Öffentlich: Changelog anzeigen (Einstellungen „Was ist neu?“)."""
        try:
            from version import get_version
            from changelog import changelog_full_reference, changelog_text_for_upgrade
        except Exception as e:
            messagebox.showinfo("Changelog", f"Release Notes konnten nicht geladen werden:\n{e}", parent=self.root)
            return
        if full_history:
            body = changelog_full_reference()
        else:
            body = changelog_text_for_upgrade("0.0.0", get_version()) or changelog_full_reference()
        self._show_changelog_dialog(body, mark_seen_on_close=False)

    def _show_changelog_dialog(self, body: str, mark_seen_on_close: bool = False, parent=None):
        """Scrollbarer Dialog mit Release-Text."""
        parent = parent or self.root
        win = tk.Toplevel(parent)
        win.title("Was ist neu?")
        win.transient(parent)
        self._fit_dialog(win, 860, 680, 560, 420)
        try:
            win.update_idletasks()
            x = (win.winfo_screenwidth() // 2) - (win.winfo_width() // 2)
            y = (win.winfo_screenheight() // 2) - (win.winfo_height() // 2)
            win.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frm, text="Änderungen & Hinweise", font=("Arial", 16, "bold")).pack(anchor=tk.W, pady=(0, 8))
        _bg = getattr(self, "_tk_bg_card", "#424242")
        _fg = getattr(self, "_tk_fg_text", "#e8e8e8")
        txt = scrolledtext.ScrolledText(
            frm, wrap=tk.WORD, height=18, width=72, font=("Arial", 14),
            bg=_bg, fg=_fg, insertbackground=_fg, highlightthickness=0, relief=tk.FLAT,
        )
        txt.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        txt.insert("1.0", body)
        txt.config(state=tk.DISABLED)

        btn_row = ttk.Frame(frm)
        btn_row.pack(fill=tk.X)

        def on_ok():
            win.destroy()
            if mark_seen_on_close:
                try:
                    from version import get_version
                    self.settings["last_seen_changelog_version"] = get_version()
                    self._save_settings()
                except Exception:
                    pass

        ttk.Button(btn_row, text="OK", command=on_ok).pack(side=tk.RIGHT)
        win.protocol("WM_DELETE_WINDOW", on_ok)
        win.grab_set()

    def _check_updates_on_start(self):
        """Prüft im Hintergrund auf Updates beim Start"""
        if not UpdateChecker:
            return
        
        # Prüfe ob wir gerade nach einem Update neu gestartet wurden
        # Verhindere Endlosschleife: Prüfe nicht sofort nach Neustart
        import time
        restart_flag_file = Path(tempfile.gettempdir()) / "universal_downloader_restarting.flag"
        if restart_flag_file.exists():
            # Wir wurden gerade neu gestartet - lösche Flag und überspringe Update-Check
            restart_flag_file.unlink(missing_ok=True)
            return
        
        def check_thread():
            try:
                checker = UpdateChecker()
                available, info = checker.check_for_updates()
                if available and info:
                    # Zeige Benachrichtigung im Hauptthread
                    self.root.after(0, lambda: self._show_update_notification(info))
            except Exception:
                pass  # Stille Fehlerbehandlung beim Start
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def check_for_updates_dialog(self):
        """Zeigt Dialog zum manuellen Prüfen auf Updates"""
        if not UpdateChecker:
            messagebox.showinfo("Info", "Update-Funktion nicht verfügbar.")
            return
        
        # Erstelle Dialog
        update_window = tk.Toplevel(self.root)
        update_window.title("🔄 Updates prüfen")
        update_window.transient(self.root)
        update_window.grab_set()
        self._fit_dialog(update_window, 580, 420, 460, 300)
        
        frame = ttk.Frame(update_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        status_label = ttk.Label(frame, text="Prüfe auf Updates...", font=("Arial", 10))
        status_label.pack(pady=20)
        
        progress = ttk.Progressbar(frame, mode='indeterminate')
        progress.pack(fill=tk.X, pady=10)
        progress.start()
        
        result_text = tk.Text(frame, height=10, wrap=tk.WORD, state=tk.DISABLED)
        result_text.pack(fill=tk.BOTH, expand=True, pady=10)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        close_button = ttk.Button(button_frame, text="Schließen", command=update_window.destroy)
        close_button.pack(side=tk.RIGHT)
        
        def check_thread():
            try:
                checker = UpdateChecker()
                available, info = checker.check_for_updates()
                
                def update_ui():
                    progress.stop()
                    if available and info:
                        status_label.config(text=f"✓ Update verfügbar: Version {info['version']}")
                        result_text.config(state=tk.NORMAL)
                        result_text.delete(1.0, tk.END)
                        result_text.insert(tk.END, f"Neue Version verfügbar: {info['version']}\n\n")
                        if info.get('changelog'):
                            result_text.insert(tk.END, f"Änderungen:\n{info['changelog']}\n\n")
                        if info.get('release_date'):
                            result_text.insert(tk.END, f"Veröffentlicht: {info['release_date']}\n")
                        
                        # Zeige Download-URL Status
                        if info.get('download_url'):
                            result_text.insert(tk.END, f"\n✓ Download-URL verfügbar\n")
                        else:
                            result_text.insert(tk.END, f"\n⚠ Download-URL nicht verfügbar\n")
                            if 'assets' in info and info['assets']:
                                result_text.insert(tk.END, f"\nVerfügbare Assets:\n")
                                for asset in info['assets']:
                                    result_text.insert(tk.END, f"  - {asset['name']}\n")
                            result_text.insert(tk.END, f"\nBitte laden Sie das Update manuell von der Release-Seite herunter:\n")
                            result_text.insert(tk.END, f"{info.get('release_url', 'GitHub Releases')}\n")
                        
                        result_text.config(state=tk.DISABLED)
                        
                        # Download-Button hinzufügen (nur wenn URL verfügbar)
                        if info.get('download_url'):
                            download_btn = ttk.Button(
                                button_frame,
                                text="📥 Update herunterladen",
                                command=lambda: self._download_update(info, update_window)
                            )
                            download_btn.pack(side=tk.LEFT, padx=5)
                        else:
                            # Link zu Release-Seite
                            release_btn = ttk.Button(
                                button_frame,
                                text="🔗 Zur Release-Seite",
                                command=lambda: webbrowser.open(info.get('release_url', ''))
                            )
                            release_btn.pack(side=tk.LEFT, padx=5)
                    else:
                        status_label.config(text="✓ Sie verwenden die neueste Version")
                        result_text.config(state=tk.NORMAL)
                        result_text.delete(1.0, tk.END)
                        result_text.insert(tk.END, f"Aktuelle Version: {get_version()}\n\nKeine Updates verfügbar.")
                        result_text.config(state=tk.DISABLED)
                
                self.root.after(0, update_ui)
            except Exception as e:
                def show_error():
                    progress.stop()
                    status_label.config(text="✗ Fehler beim Prüfen")
                    result_text.config(state=tk.NORMAL)
                    result_text.delete(1.0, tk.END)
                    result_text.insert(tk.END, f"Fehler beim Prüfen auf Updates:\n{str(e)}")
                    result_text.config(state=tk.DISABLED)
                self.root.after(0, show_error)
        
        threading.Thread(target=check_thread, daemon=True).start()
    
    def _show_update_notification(self, update_info):
        """Zeigt Benachrichtigung über verfügbares Update"""
        running = get_version()
        install_dir = ""
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            install_dir = str(Path(sys.executable).resolve().parent)
        where = f"\nOrdner: {install_dir}\n" if install_dir else "\n"
        response = messagebox.askyesno(
            "Update verfügbar",
            f"Installiert ist Version {running}.{where}\n"
            f"Eine neue Version ({update_info['version']}) ist verfügbar.\n"
            f"Möchten Sie das Update jetzt herunterladen?",
            icon='question'
        )
        if response:
            self._download_update(update_info)
    
    def _download_update(self, update_info, parent_window=None):
        """Lädt ein Update herunter und installiert es automatisch"""
        if not update_info.get('download_url'):
            if platform.system().lower() == 'linux':
                messagebox.showinfo(
                    "Update",
                    "Die neue Version kommt für Linux über das APT-Repo "
                    "(ppa.plertanix.de), nicht als GitHub-Download.\n\n"
                    "Sobald sie dort liegt: Einstellungen → Updates prüfen, "
                    "oder im Terminal:\n"
                    "sudo apt update && sudo apt install --only-upgrade universal-downloader",
                )
                return
            # Zeige detaillierte Fehlermeldung
            assets_info = ""
            if 'assets' in update_info and update_info['assets']:
                available_assets = [a['name'] for a in update_info['assets']]
                assets_info = f"\n\nVerfügbare Assets im Release:\n" + "\n".join(f"  - {name}" for name in available_assets)
            
            messagebox.showwarning(
                "Warnung", 
                f"Download-URL nicht verfügbar für Ihr Betriebssystem ({platform.system()}).\n"
                f"Bitte laden Sie das Update manuell von der Release-Seite herunter:\n"
                f"{update_info.get('release_url', 'GitHub Releases')}"
                + assets_info
            )
            return
        
        # Automatischer Speicherort (Temp-Ordner)
        temp_dir = Path(tempfile.gettempdir())
        extension = ".exe" if sys.platform == "win32" else ".deb"
        save_path = temp_dir / f"UniversalDownloader_Update_{update_info['version']}{extension}"
        
        # Download-Dialog
        download_window = tk.Toplevel(parent_window or self.root)
        download_window.title(f"Update auf {update_info['version']}")
        download_window.geometry("560x260")
        download_window.transient(parent_window or self.root)
        self._apply_app_icon(download_window)
        
        frame = ttk.Frame(download_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        headline = ttk.Label(
            frame,
            text=f"Lade Version {update_info['version']} …\nInstalliert ist {get_version()}.",
            wraplength=520,
            justify=tk.LEFT,
        )
        headline.pack(pady=(0, 10), anchor=tk.W)
        
        progress = ttk.Progressbar(frame, mode='determinate', maximum=100)
        progress.pack(fill=tk.X, pady=10)
        
        status_label = ttk.Label(frame, text="Verbindung …", wraplength=520, justify=tk.LEFT)
        status_label.pack(anchor=tk.W)
        
        def on_download_progress(done: int, total: int):
            def apply():
                if total > 0:
                    pct = min(100, int(done * 100 / total))
                    progress.configure(value=pct)
                    status_label.config(
                        text=f"{done / 1048576:.0f} von {total / 1048576:.0f} MB ({pct} %)"
                    )
                else:
                    status_label.config(text=f"{done / 1048576:.0f} MB geladen")
            try:
                self.root.after(0, apply)
            except Exception:
                pass
        
        def download_thread():
            try:
                checker = UpdateChecker()
                use_apt = str(update_info.get('download_url') or '').startswith('apt:')
                if use_apt:
                    success = True
                else:
                    success = checker.download_update(
                        update_info['download_url'],
                        Path(save_path),
                        progress_callback=on_download_progress,
                    )
                
                def update_ui():
                    if success:
                        status_label.config(text="Installiere Update …")
                        self.root.update()
                        
                        install_success, install_msg = self._install_update(
                            None if use_apt else Path(save_path),
                            update_info['version'],
                        )
                        
                        if install_success and install_msg == "handoff":
                            install_dir = str(Path(sys.executable).resolve().parent)
                            needs_admin = "\\program files" in install_dir.lower()
                            note = (
                                f"Version {update_info['version']} ersetzt die Installation in:\n{install_dir}\n\n"
                                "Das Programm schließt sich jetzt. "
                            )
                            if needs_admin:
                                note += (
                                    "Windows fragt nach der Administrator-Bestätigung. "
                                    "Ohne Zustimmung bleibt die bisherige Version, und es erscheint ein Hinweis."
                                )
                            else:
                                note += "Danach startet dieselbe Programmdatei in der neuen Version."
                            headline.config(text=note)
                            status_label.config(text="")
                            self.root.update()
                            self.root.after(2500, self._exit_for_windows_update)
                        elif install_success:
                            status_label.config(text="✓ Update installiert! Starte Programm neu...")
                            self.root.update()
                            
                            # Starte Programm neu
                            self._restart_application(Path(save_path) if not use_apt else None)
                        else:
                            status_label.config(text="⚠ Installation fehlgeschlagen")
                            hint = (
                                "sudo apt update && sudo apt install --only-upgrade universal-downloader"
                                if use_apt else str(save_path)
                            )
                            detail = f"\n\n{install_msg}" if install_msg else ""
                            messagebox.showwarning(
                                "Warnung",
                                "Update-Installation fehlgeschlagen."
                                f"{detail}\n\nBitte manuell:\n{hint}"
                            )
                            download_window.destroy()
                            if parent_window:
                                parent_window.destroy()
                    else:
                        status_label.config(text="✗ Download fehlgeschlagen")
                        messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte versuchen Sie es erneut.")
                
                self.root.after(0, update_ui)
            except Exception as e:
                def show_error():
                    status_label.config(text="✗ Fehler")
                    messagebox.showerror("Fehler", f"Fehler beim Download: {str(e)}")
                self.root.after(0, show_error)
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def _install_update(self, update_file: Optional[Path], new_version: str):
        """
        Installiert das Update (Windows: .exe ersetzen, Linux: APT/pkexec).
        Returns:
            (True/False, Fehler- oder Logtext)
        """
        try:
            if sys.platform == "win32":
                if not getattr(sys, 'frozen', False):
                    return False, "Kein Windows-.exe-Build – automatische Installation nicht möglich."
                if update_file is None or not Path(update_file).is_file():
                    return False, "Die Update-Datei fehlt."
                # Die laufende .exe ist gesperrt. Ein Helfer wartet, bis das Programm zu ist,
                # und startet dann den Installer.
                return self._windows_handoff_update(Path(update_file))
            elif sys.platform == "linux":
                if not UpdateChecker:
                    return False, "Updater nicht verfügbar."
                ok, msg = UpdateChecker().install_linux_update(update_file)
                return ok, msg
            else:
                # macOS: Kann nicht automatisch installieren
                return False, "macOS: bitte manuell neu installieren."
                
        except Exception as e:
            print(f"[ERROR] Fehler bei Update-Installation: {e}")
            return False, str(e)
    
    def _is_inno_setup(self, path: Path) -> bool:
        if "setup" in path.name.lower():
            return True
        try:
            size = path.stat().st_size
            # Die Kennung liegt hinter dem Archiv, oft mehr als 1 MB vor dem Dateiende.
            with open(path, "rb") as fh:
                fh.seek(max(0, size - 8_000_000))
                tail = fh.read()
            return b"Inno Setup" in tail
        except Exception:
            return False

    def _windows_handoff_update(self, update_file: Path):
        """Installer erst starten, wenn dieses Programm beendet ist.

        Ersetzt genau den Ordner der laufenden Programmdatei und startet
        danach dieselbe Datei. Eine andere, ältere Kopie wird nicht geöffnet.
        """
        pid = os.getpid()
        setup = str(Path(update_file).resolve())
        install_dir = str(Path(sys.executable).resolve().parent)
        app_exe = str(Path(install_dir) / "UniversalDownloader.exe")
        elevate = "\\program files" in install_dir.lower()
        is_setup = self._is_inno_setup(update_file)
        ps1 = Path(tempfile.gettempdir()) / "ud_apply_update.ps1"

        def ps_quote(value: str) -> str:
            return value.replace("'", "''")

        script = (
            "$ErrorActionPreference = 'Continue'\n"
            "$log = Join-Path $env:TEMP 'ud_apply_update.log'\n"
            "function Log([string]$m) {\n"
            "  Add-Content -LiteralPath $log -Value ((Get-Date -Format 'HH:mm:ss') + ' ' + $m)\n"
            "}\n"
            f"$pidWait = {int(pid)}\n"
            f"$setup = '{ps_quote(setup)}'\n"
            f"$dir = '{ps_quote(install_dir)}'\n"
            f"$app = '{ps_quote(app_exe)}'\n"
            f"$elevate = ${'true' if elevate else 'false'}\n"
            f"$isSetup = ${'true' if is_setup else 'false'}\n"
            "Log ('start dir=' + $dir + ' elevate=' + $elevate)\n"
            "while (Get-Process -Id $pidWait -ErrorAction SilentlyContinue) { Start-Sleep -Seconds 1 }\n"
            "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {\n"
            "  $_.Name -match '^(UniversalDownloader|UniversalDownloaderTray)(\\.exe)?$' -or\n"
            "  ($_.CommandLine -and $_.CommandLine -match 'series-watch-tray')\n"
            "} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }\n"
            "$unlocked = $false\n"
            "for ($i = 0; $i -lt 20; $i++) {\n"
            "  try {\n"
            "    $fs = [System.IO.File]::Open($app, 'Open', 'Read', 'None')\n"
            "    $fs.Close()\n"
            "    $unlocked = $true\n"
            "    break\n"
            "  } catch { Start-Sleep -Milliseconds 500 }\n"
            "}\n"
            "Log ('unlocked=' + $unlocked)\n"
            "$code = 1\n"
            "try {\n"
            "  if ($isSetup) {\n"
            "    $setupLog = Join-Path $env:TEMP 'ud_setup.log'\n"
            "    $mode = if ($elevate) { '/ALLUSERS' } else { '/CURRENTUSER' }\n"
            "    $arg = '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS ' + $mode + ' /LOG=\"' + $setupLog + '\" /DIR=\"' + $dir + '\"'\n"
            "    if ($elevate) {\n"
            "      $p = Start-Process -FilePath $setup -ArgumentList $arg -Verb RunAs -PassThru -Wait\n"
            "    } else {\n"
            "      $p = Start-Process -FilePath $setup -ArgumentList $arg -PassThru -Wait\n"
            "    }\n"
            "    if ($null -ne $p -and $null -ne $p.ExitCode) { $code = [int]$p.ExitCode }\n"
            "  } else {\n"
            "    Copy-Item -LiteralPath $setup -Destination $app -Force\n"
            "    $code = 0\n"
            "  }\n"
            "} catch {\n"
            "  Log $_.Exception.Message\n"
            "  $code = 1\n"
            "}\n"
            "Log ('exit ' + $code)\n"
            "if ($code -ne 0) {\n"
            "  Add-Type -AssemblyName System.Windows.Forms\n"
            "  [void][System.Windows.Forms.MessageBox]::Show(\n"
            "    (\"Das Update wurde nicht installiert (Code $code). Es bleibt die bisherige Version.`n`nOrdner: $dir\"),\n"
            "    'Universal Downloader')\n"
            "}\n"
            "if (Test-Path -LiteralPath $app) { Start-Process -FilePath $app }\n"
            "if ($code -eq 0) { Remove-Item -LiteralPath $setup -Force -ErrorAction SilentlyContinue }\n"
            "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue\n"
        )
        ps1.write_text(script, encoding="utf-8-sig")
        self._stop_windows_watchers()
        system_root = os.environ.get("SystemRoot") or r"C:\Windows"
        powershell = str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
        if not Path(powershell).is_file():
            powershell = "powershell"
        flags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            flags |= subprocess.CREATE_NEW_PROCESS_GROUP
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags |= subprocess.CREATE_NO_WINDOW
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        # Ohne DETACHED_PROCESS: die Kombination mit CREATE_NO_WINDOW beendet den
        # Helfer sofort wieder, dann passiert nach dem Download nichts.
        subprocess.Popen(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(ps1),
            ],
            creationflags=flags,
            startupinfo=startup,
            close_fds=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, "handoff"

    def _stop_windows_watchers(self) -> None:
        """Serien-Wächter beenden. Er ist dieselbe EXE und blockiert sonst das Update."""
        if sys.platform != "win32":
            return
        me = os.getpid()
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    (
                        "Get-CimInstance Win32_Process | Where-Object { "
                        f"$_.ProcessId -ne {int(me)} -and ("
                        "$_.Name -match '^(UniversalDownloader|UniversalDownloaderTray)(\\.exe)?$' -or "
                        "($_.CommandLine -and $_.CommandLine -match 'series-watch-tray')"
                        ") } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
                    ),
                ],
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        except Exception:
            pass

    def _exit_for_windows_update(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        os._exit(0)

    def _restart_application(self, update_file: Path = None):
        """
        Startet die Anwendung neu nach einem Update oder nach Abhängigkeits-Installation
        
        Args:
            update_file: Pfad zur neuen .exe (optional, wird nicht mehr benötigt, da bereits installiert)
        """
        try:
            self._write_to_log_file("[DEBUG] Neustart wird vorbereitet...", "DEBUG")
            
            # Setze Flag, um zu verhindern, dass nach Neustart sofort wieder geprüft wird
            restart_flag_file = Path(tempfile.gettempdir()) / "universal_downloader_restarting.flag"
            restart_flag_file.touch()
            self._write_to_log_file(f"[DEBUG] Restart-Flag gesetzt: {restart_flag_file}", "DEBUG")
            
            # Prüfe ob wir als .exe (frozen) oder als Python-Skript laufen
            is_frozen = getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS')
            
            if sys.platform == "win32":
                # Windows: Starte die neue Instanz
                import time
                time.sleep(2)  # Warte kurz, damit die Installation abgeschlossen ist
                
                if is_frozen:
                    # Als .exe: Starte die .exe direkt
                    current_exe = Path(sys.executable)
                    self._write_to_log_file(f"[DEBUG] Starte neue Instanz (.exe): {current_exe}", "DEBUG")
                    try:
                        # Verwende CREATE_NEW_CONSOLE um sicherzustellen, dass es ein separater Prozess ist
                        subprocess.Popen(
                            [str(current_exe)],
                            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                            | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            close_fds=True
                        )
                        self._write_to_log_file("[DEBUG] Neue Instanz gestartet", "DEBUG")
                    except Exception as e:
                        self._write_to_log_file(f"[ERROR] Fehler beim Starten der neuen Instanz: {e}", "ERROR")
                        # Fallback: Versuche mit shell=True
                        subprocess.Popen([str(current_exe)], shell=True)
                else:
                    # Als Python-Skript: Starte start.py mit Python
                    script_dir = Path(__file__).parent.absolute()
                    start_script = script_dir / "start.py"
                    python_exe = sys.executable
                    self._write_to_log_file(f"[DEBUG] Starte neue Instanz (Python-Skript): {python_exe} {start_script}", "DEBUG")
                    try:
                        # Verwende CREATE_NEW_CONSOLE für Windows
                        subprocess.Popen(
                            [str(python_exe), str(start_script)],
                            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
                            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                            | getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            close_fds=True,
                            cwd=str(script_dir)
                        )
                        self._write_to_log_file("[DEBUG] Neue Instanz gestartet", "DEBUG")
                    except Exception as e:
                        self._write_to_log_file(f"[ERROR] Fehler beim Starten der neuen Instanz: {e}", "ERROR")
                        # Fallback: Versuche mit shell=True
                        subprocess.Popen([str(python_exe), str(start_script)], shell=True, cwd=str(script_dir))
                
                # Warte länger, damit die neue Instanz sicher starten kann
                time.sleep(3)
                
                self._write_to_log_file("[DEBUG] Schließe aktuelle Instanz...", "DEBUG")
                # Schließe aktuelle Instanz
                self.root.quit()
                self.root.destroy()
                sys.exit(0)
            elif sys.platform == "linux":
                # Linux: Starte die Anwendung neu
                if is_frozen:
                    # Als .deb installiert: Verwende den System-Befehl
                    subprocess.Popen(['universal-downloader'], shell=True)
                else:
                    # Als Python-Skript: Starte start.py
                    script_dir = Path(__file__).parent.absolute()
                    start_script = script_dir / "start.py"
                    python_exe = sys.executable
                    subprocess.Popen([str(python_exe), str(start_script)], cwd=str(script_dir))
                self.root.quit()
                self.root.destroy()
                sys.exit(0)
            else:
                # macOS: Zeige Hinweis
                messagebox.showinfo(
                    "Update installiert",
                    "Das Update wurde installiert. Bitte starten Sie die Anwendung manuell neu."
                )
                self.root.quit()
                self.root.destroy()
                sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Fehler beim Neustart: {e}")
            import traceback
            self._write_to_log_file(f"[ERROR] Traceback: {traceback.format_exc()}", "ERROR")
            messagebox.showinfo(
                "Update installiert",
                "Das Update wurde installiert. Bitte starten Sie die Anwendung manuell neu."
            )
            self.root.quit()
            self.root.destroy()
            sys.exit(0)
    
    def show_about_dialog(self):
        """Zeigt Info-Dialog über die Anwendung"""
        about_window = tk.Toplevel(self.root)
        about_window.title("ℹ️ Über Universal Downloader")
        about_window.transient(self.root)
        self._fit_dialog(about_window, 580, 480, 440, 340)
        
        frame = ttk.Frame(about_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            frame,
            text="Universal Downloader",
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 10))
        
        version_text = get_version_string() if get_version_string else f"Version {get_version()}"
        ttk.Label(frame, text=version_text, font=("Arial", 10)).pack(pady=5)
        
        info_text = """
Ein Universal-Downloader für Musik, Hörbücher und Videos.

Unterstützte Plattformen:
• Deezer (mit API und YouTube-Fallback)
• Spotify (mit YouTube-Fallback)
• Audible
• Öffentlich-rechtliche Sender (ARD, ZDF, etc.)
• YouTube

Features:
• Automatische Metadaten-Tagging
• DRM-Umgehung mit Fallback
• Serien-Download mit Auswahl
• Download-Warteschlange
• Statistiken und Historie

Lizenz: MIT License
Copyright (c) 2025 Universal Downloader Contributors
        """
        
        text_widget = tk.Text(frame, height=15, wrap=tk.WORD, state=tk.DISABLED, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True, pady=10)
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, info_text.strip())
        text_widget.config(state=tk.DISABLED)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=10)
        
        # GitHub-Link Button (falls Repository vorhanden)
        try:
            from version import GITHUB_REPO_URL
            if GITHUB_REPO_URL:
                def open_github():
                    import webbrowser
                    webbrowser.open(GITHUB_REPO_URL)
                ttk.Button(button_frame, text="🔗 GitHub", command=open_github).pack(side=tk.LEFT, padx=5)
        except:
            pass
        
        ttk.Button(button_frame, text="Schließen", command=about_window.destroy).pack(side=tk.RIGHT)
    
    def _format_size(self, size_bytes):
        """Formatiert Bytes in lesbare Größe"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def _failed_downloads_path(self):
        """Textdatei mit echten Fehlschlägen (Link und Grund), zum Kopieren in GitHub oder E-Mail."""
        return self.base_download_path / "fehlgeschlagene_downloads.txt"

    def _append_failed_download(self, kind, url, error):
        url = (url or "").strip()
        if not url:
            return
        reason = " ".join((error or "").split()) or "Unbekannter Fehler"
        if len(reason) > 600:
            reason = reason[:600] + "…"
        label = "Musik" if kind == "music" else "Video"
        path = self._failed_downloads_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.stat().st_size == 0:
                path.write_text(
                    "Fehlgeschlagene Downloads\n"
                    "Jeder Block ist ein Versuch, der nicht geklappt hat "
                    "(zum Beispiel Seite oder yt-dlp nicht unterstützt).\n"
                    "Die Liste kann in eine GitHub-Meldung oder E-Mail kopiert werden.\n\n",
                    encoding="utf-8",
                )
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(
                    f"Zeit: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Bereich: {label}\n"
                    f"URL: {url}\n"
                    f"Grund: {reason}\n"
                    "---\n"
                )
        except Exception:
            pass

    def _update_statistics(self, success, file_path, url, kind="video", error=""):
        """Zählt einen abgeschlossenen Download, getrennt nach Video und Musik."""
        if not success:
            err = (error or "").strip()
            if err == "Abgebrochen" or err.lower().startswith("abgebrochen"):
                return
        if not hasattr(self, 'music_statistics'):
            self.music_statistics = {
                'total_downloads': 0, 'total_size': 0,
                'successful_downloads': 0, 'failed_downloads': 0, 'last_download': None,
            }
        bucket = self.music_statistics if kind == "music" else self.video_statistics
        bucket['total_downloads'] = int(bucket.get('total_downloads') or 0) + 1
        if success:
            bucket['successful_downloads'] = int(bucket.get('successful_downloads') or 0) + 1
            path = Path(file_path) if file_path else None
            if path is not None and path.exists():
                try:
                    bucket['total_size'] = int(bucket.get('total_size') or 0) + path.stat().st_size
                except Exception:
                    pass
        else:
            bucket['failed_downloads'] = int(bucket.get('failed_downloads') or 0) + 1
            self._append_failed_download(kind, url, error)
        bucket['last_download'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save_video_data()
    
    def _add_to_history(self, url, filename, status):
        """Fügt Eintrag zur Download-Historie hinzu"""
        self.video_download_history.append({
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'url': url,
            'filename': filename,
            'status': status
        })
        # Behalte nur die letzten 1000 Einträge
        if len(self.video_download_history) > 1000:
            self.video_download_history = self.video_download_history[-1000:]
        self._save_video_data()
    
    def _load_settings(self):
        """Lädt gespeicherte Einstellungen"""
        default_settings = {
            'default_music_path': str(self.base_download_path / "Musik"),  # Gemeinsamer Pfad für Deezer & Spotify
            'default_deezer_path': str(self.base_download_path / "Deezer"),  # Legacy
            'default_audible_path': str(self.base_download_path / "Audible"),
            'default_video_path': str(self.base_download_path / "Video"),
            'default_spotify_path': str(self.base_download_path / "Spotify"),  # Legacy
            'default_video_quality': 'best',
            'default_video_format': 'mp4',
            # Dateinamen-Templates
            # Platzhalter (werden bereinigt zu gültigen Dateinamen):
            # {series}  = Serienname
            # {season}  = Staffelnummer (z. B. 1)
            # {season2} = Staffelnummer zweistellig (z. B. 01)
            # {episode}  = Episodennummer
            # {episode2} = Episodennummer zweistellig (z. B. 01)
            # {title}   = Episoden- bzw. Filmtitel
            # {date}/{datum}/{sendedatum} = Sendedatum YYYY-MM-DD (optional, z. B. ARD Sounds)
            # {date_de}/{datum_de} = Sendedatum TT.MM.JJJJ
            'series_filename_template': 'E{episode2} - {title}',
            'movie_filename_template': '{title}',
            'audiothek_filename_template': 'E{episode2} - {title}',
            'gpu_enabled': False,
            'gpu_vendor': 'auto',
            'auto_open_folder': False,
            'max_concurrent_downloads': 3,
            'show_notifications': True,
            'language': 'de',
            'log_cleanup_enabled': False,
            'log_cleanup_days': 30,
            'log_cleanup_on_exit': False,
            'auto_check_updates': True,  # Automatische Update-Prüfung beim Start
            'log_level': 'debug',  # Log-Level: 'normal' oder 'debug'
            'video_accounts': [],  # Liste von Account-Dictionaries
            'last_tab': '🎵 Musik',  # Zuletzt gewählter Tab (z. B. "🎬 Video Downloader")
            'enabled_tabs': {'music': True, 'audible': False, 'video': True},
            'download_archive_enabled': False,  # Bereits heruntergeladene URLs überspringen (Archiv-Datei)
            'download_archive_path': '',  # Leer = base_download_path / "download_archive.txt"
            'play_after_download': False,  # Nach Download mit Standard-Player abspielen
            'domain_quality_format': [],  # [{"domain": "youtube.com", "quality": "1080p", "format": "mp4"}, ...]
            'theme': 'dark',  # 'dark' | 'light'
            # Serien-Wächter (Mediathek-Playlist, yt-dlp)
            'series_watch_enabled': False,
            'series_watch_interval_hours': 6,
            'series_watch_auto_download': False,
            'series_watch_tray_enabled': True,
            'series_watch_tray_autostart': True,
            'series_notify_desktop': True,
            'series_notify_email_enabled': False,
            'series_smtp_host': '',
            'series_smtp_port': 587,
            'series_smtp_user': '',
            'series_smtp_password_enc': '',
            'series_smtp_tls': True,
            'series_email_from': '',
            'series_email_to': '',
            'series_notify_telegram_enabled': False,
            'series_telegram_bot_token': '',
            'series_telegram_chat_id': '',
            'series_notify_discord_enabled': False,
            'series_discord_webhook_url': '',
        }
        
        try:
            config_file = self.base_download_path / "settings.json"
            saved_settings = {}
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    if not isinstance(saved_settings, dict):
                        saved_settings = {}
            had_gpu_key = 'gpu_enabled' in saved_settings
            # Merge mit Defaults (falls neue Einstellungen hinzugefügt wurden)
            default_settings.update(saved_settings)
            raw_tabs = saved_settings.get('enabled_tabs')
            if not isinstance(raw_tabs, dict):
                raw_tabs = {}
            default_settings['enabled_tabs'] = {
                'music': bool(raw_tabs.get('music', True)),
                'audible': bool(raw_tabs.get('audible', False)),
                'video': bool(raw_tabs.get('video', True)),
            }
            # Apple Silicon / macOS: VideoToolbox-GPU standardmäßig an, wenn noch nie gesetzt
            if not had_gpu_key and sys.platform == 'darwin':
                try:
                    from mac_platform import has_videotoolbox
                    default_settings['gpu_enabled'] = bool(has_videotoolbox())
                except Exception:
                    default_settings['gpu_enabled'] = True
                if default_settings.get('gpu_vendor') in (None, '', 'none', 'auto'):
                    default_settings['gpu_vendor'] = 'apple'
            # Stelle sicher, dass video_accounts existiert und gültige Einträge hat
            if 'video_accounts' not in default_settings:
                default_settings['video_accounts'] = []
            accounts = default_settings['video_accounts']
            if not isinstance(accounts, list):
                default_settings['video_accounts'] = []
            else:
                # Nur gültige Einträge (mit service und cookies) behalten
                default_settings['video_accounts'] = [
                    a for a in accounts
                    if isinstance(a, dict) and a.get('service') and a.get('cookies')
                ]
            return default_settings
        except Exception as e:
            pass
        # Keine settings.json: auf macOS VideoToolbox bevorzugen
        if sys.platform == 'darwin':
            try:
                from mac_platform import has_videotoolbox
                default_settings['gpu_enabled'] = bool(has_videotoolbox())
            except Exception:
                default_settings['gpu_enabled'] = True
            default_settings['gpu_vendor'] = 'apple'
        return default_settings
    
    def _save_settings(self):
        """Speichert Einstellungen"""
        try:
            config_file = self.base_download_path / "settings.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            pass
    
    def _encrypt_password(self, password: str) -> str:
        """Verschlüsselt ein Passwort mit Base64 (einfache Kodierung)"""
        if not password:
            return ""
        return base64.b64encode(password.encode('utf-8')).decode('utf-8')
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Entschlüsselt ein Base64-kodiertes Passwort"""
        if not encrypted_password:
            return ""
        try:
            return base64.b64decode(encrypted_password.encode('utf-8')).decode('utf-8')
        except:
            return ""
    
    def _get_available_gpu_vendors(self):
        """Ermittelt verbaut/verfügbare Grafikhersteller (nvidia, amd, apple). Rückgabe: Liste von Strings."""
        available = []
        try:
            if sys.platform == 'darwin':
                # Apple Silicon / VideoToolbox: nur anbieten wenn ffmpeg den Encoder hat
                try:
                    from mac_platform import has_videotoolbox, is_macos
                    if is_macos() and has_videotoolbox():
                        available.append('apple')
                    elif is_macos():
                        # ffmpeg fehlt oder ohne VT — trotzdem apple anbieten (Fallback allow_sw)
                        available.append('apple')
                except Exception:
                    available.append('apple')
            # NVIDIA: nvidia-smi vorhanden und ausführbar
            try:
                r = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                    capture_output=True, timeout=3, text=True
                )
                if r.returncode == 0 and r.stdout.strip():
                    available.append('nvidia')
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            # AMD: unter Linux lspci, unter Windows wmic (oder nur Linux für Einfachheit)
            if sys.platform != 'darwin':
                try:
                    if sys.platform == 'win32':
                        r = subprocess.run(
                            ['wmic', 'path', 'win32_VideoController', 'get', 'Name'],
                            capture_output=True, timeout=5, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                        )
                        out = (r.stdout or '').lower()
                        if 'amd' in out or 'radeon' in out:
                            available.append('amd')
                    else:
                        r = subprocess.run(
                            ['lspci', '-nn'],
                            capture_output=True, timeout=3, text=True
                        )
                        if r.returncode == 0 and r.stdout:
                            for line in r.stdout.splitlines():
                                line_lower = line.lower()
                                if 'vga' in line_lower or '3d' in line_lower or 'display' in line_lower:
                                    if 'nvidia' in line_lower and 'nvidia' not in available:
                                        available.append('nvidia')
                                    if 'amd' in line_lower or 'ati' in line_lower:
                                        if 'amd' not in available:
                                            available.append('amd')
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
        except Exception:
            pass
        return sorted(set(available))
    
    def show_settings_dialog(self):
        """Zeigt das Einstellungsfenster"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("⚙️ Einstellungen")
        settings_window.transient(self.root)
        settings_window.grab_set()
        self._apply_dark_toplevel(settings_window)
        self._fit_dialog(settings_window, 980, 900, 760, 580)
        
        # Hauptframe mit Scrollbar (dunkles Design)
        main_frame = ttk.Frame(settings_window, padding="15", style="Download.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        canvas = tk.Canvas(main_frame, bg=getattr(self, '_tk_bg_panel', '#383838'), highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, style="Download.TFrame")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_win_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        self._bind_scroll_wheel(canvas, scrollable_frame)
        settings_wrap_labels = []

        def _sync_settings_canvas(event):
            if event.widget is not canvas:
                return
            inner_w = max(1, event.width)
            canvas.itemconfigure(canvas_win_id, width=inner_w)
            wrap = max(480, inner_w - 48)
            for lbl in settings_wrap_labels:
                try:
                    lbl.configure(wraplength=wrap)
                except tk.TclError:
                    pass

        canvas.bind("<Configure>", _sync_settings_canvas)
        
        # Standard-Download-Pfade
        paths_frame = ttk.LabelFrame(scrollable_frame, text="📁 Standard-Download-Pfade", padding="10", style="Download.TLabelframe")
        paths_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Deezer-Pfad
        ttk.Label(paths_frame, text="Deezer:", style="Download.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        deezer_path_var = tk.StringVar(value=self.settings.get('default_deezer_path', ''))
        deezer_entry = ttk.Entry(paths_frame, textvariable=deezer_path_var, width=50, style="Download.TEntry")
        deezer_entry.grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(deezer_path_var), style="Download.TButton").grid(row=0, column=2, padx=5)
        
        # Audible-Pfad
        ttk.Label(paths_frame, text="Audible:", style="Download.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        audible_path_var = tk.StringVar(value=self.settings.get('default_audible_path', ''))
        audible_entry = ttk.Entry(paths_frame, textvariable=audible_path_var, width=50, style="Download.TEntry")
        audible_entry.grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(audible_path_var), style="Download.TButton").grid(row=1, column=2, padx=5)
        
        # Video-Pfad
        ttk.Label(paths_frame, text="Video:", style="Download.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        video_path_var = tk.StringVar(value=self.settings.get('default_video_path', ''))
        video_entry = ttk.Entry(paths_frame, textvariable=video_path_var, width=50, style="Download.TEntry")
        video_entry.grid(row=2, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(video_path_var), style="Download.TButton").grid(row=2, column=2, padx=5)
        
        paths_frame.columnconfigure(1, weight=1)

        tabs_frame = ttk.LabelFrame(scrollable_frame, text="🗂️ Sichtbare Tabs", padding="10", style="Download.TLabelframe")
        tabs_frame.pack(fill=tk.X, pady=5, padx=5)
        tabs_hint = "Die Auswahl bleibt auf diesem Rechner gespeichert."
        if not _store_edition():
            tabs_hint = "Audible ist aus, bis du es hier einschaltest. " + tabs_hint
        ttk.Label(
            tabs_frame,
            text=tabs_hint,
            style="Download.TLabel",
        ).pack(anchor=tk.W, pady=(0, 6))
        enabled_tabs = self.settings.get("enabled_tabs") if isinstance(self.settings.get("enabled_tabs"), dict) else {}
        tab_music_var = tk.BooleanVar(value=bool(enabled_tabs.get("music", True)))
        tab_audible_var = tk.BooleanVar(value=bool(enabled_tabs.get("audible", False)) and not _store_edition())
        tab_video_var = tk.BooleanVar(value=bool(enabled_tabs.get("video", True)))
        ttk.Checkbutton(tabs_frame, text="Musik", variable=tab_music_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        if not _store_edition():
            ttk.Checkbutton(tabs_frame, text="Audible", variable=tab_audible_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        ttk.Checkbutton(tabs_frame, text="Video", variable=tab_video_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        
        # Musik – Account & Tools (Deezer, Spotify, Audio-Aufnahme)
        music_tools_frame = ttk.LabelFrame(scrollable_frame, text="🎵 Musik – Account & Tools", padding="10", style="Download.TLabelframe")
        music_tools_frame.pack(fill=tk.X, pady=5, padx=5)
        if not _store_edition():
            ttk.Label(music_tools_frame, textvariable=self.auth_status_var, style="Download.TLabel").pack(anchor=tk.W)
        music_btn_row = ttk.Frame(music_tools_frame, style="Download.TFrame")
        music_btn_row.pack(fill=tk.X, pady=(5, 0))
        if not _store_edition():
            ttk.Button(music_btn_row, text="Deezer anmelden", command=self.show_login_dialog, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 5))
            ttk.Button(music_btn_row, text="Abmelden", command=self.logout, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 5))
            if SpotifyDownloader:
                ttk.Button(music_btn_row, text="⚙️ Spotify API", command=self.show_spotify_api_config, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(music_btn_row, text="🔧 Audio-Aufnahme Setup", command=self.show_audio_setup, style="Download.TButton").pack(side=tk.LEFT)
        
        # Video-Einstellungen
        video_frame = ttk.LabelFrame(scrollable_frame, text="🎬 Video-Einstellungen", padding="10", style="Download.TLabelframe")
        video_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Standard-Qualität
        ttk.Label(video_frame, text="Standard-Qualität:", style="Download.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
        quality_var = tk.StringVar(value=self.settings.get('default_video_quality', 'best'))
        quality_combo = ttk.Combobox(video_frame, textvariable=quality_var, values=['best', '1080p', '720p', 'niedrigste'], state='readonly', width=15, style="Download.TEntry")
        quality_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Standard-Format
        ttk.Label(video_frame, text="Standard-Format:", style="Download.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        format_var = tk.StringVar(value=self.settings.get('default_video_format', 'mp4'))
        format_combo = ttk.Combobox(video_frame, textvariable=format_var, values=['mp4', 'mp3', 'webm', 'mkv', 'avi'], state='readonly', width=15, style="Download.TEntry")
        format_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Geschwindigkeits-Limit
        ttk.Label(video_frame, text="Geschwindigkeits-Limit:", style="Download.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        speed_limit_frame = ttk.Frame(video_frame, style="Download.TFrame")
        speed_limit_frame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        speed_limit_enabled_var = tk.BooleanVar(value=self.settings.get('speed_limit_enabled', False))
        speed_limit_check = ttk.Checkbutton(speed_limit_frame, text="Aktivieren", variable=speed_limit_enabled_var, style="Download.TCheckbutton")
        speed_limit_check.pack(side=tk.LEFT, padx=(0, 5))
        
        speed_limit_value_var = tk.StringVar(value=str(self.settings.get('speed_limit_value', '5')))
        speed_limit_entry = ttk.Entry(speed_limit_frame, textvariable=speed_limit_value_var, width=8, style="Download.TEntry")
        speed_limit_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(speed_limit_frame, text="MB/s", style="Download.TLabel").pack(side=tk.LEFT)

        # Qualität/Format pro Sender (Domain-Voreinstellungen)
        domain_presets_frame = ttk.LabelFrame(scrollable_frame, text="🎬 Qualität/Format pro Sender", padding="10", style="Download.TLabelframe")
        domain_presets_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Label(domain_presets_frame, text="Für diese Domains werden beim Download automatisch Qualität und Format gesetzt.", style="Download.TLabel").pack(anchor=tk.W, pady=(0, 5))
        domain_presets_working = list(self.settings.get('domain_quality_format', []))
        domain_presets_listbox = tk.Listbox(
            domain_presets_frame, height=4, width=60, font=("Arial", 9),
            bg=getattr(self, '_tk_bg_card', '#424242'), fg=getattr(self, '_tk_fg_text', '#e8e8e8'),
            selectbackground=getattr(self, '_tk_btn_bg', '#4a4a4a'),
            selectforeground=getattr(self, '_tk_fg_text', '#e8e8e8'),
            highlightthickness=0,
        )
        domain_presets_listbox.pack(fill=tk.X, pady=5)
        def refresh_domain_presets():
            domain_presets_listbox.delete(0, tk.END)
            for e in domain_presets_working:
                if isinstance(e, dict):
                    d = e.get('domain', '')
                    q = e.get('quality', '')
                    f = e.get('format', '')
                    domain_presets_listbox.insert(tk.END, f"{d} → Qualität: {q}, Format: {f}")
        def domain_preset_dialog(edit_index=None):
            d = tk.Toplevel(settings_window)
            d.title("Sender-Voreinstellung")
            d.transient(settings_window)
            d.grab_set()
            self._fit_dialog(d, 520, 280, 440, 220)
            f = ttk.Frame(d, padding="10")
            f.pack(fill=tk.BOTH, expand=True)
            ttk.Label(f, text="Domain (z. B. youtube.com):", style="Download.TLabel").grid(row=0, column=0, sticky=tk.W, pady=5)
            domain_var = tk.StringVar()
            ttk.Entry(f, textvariable=domain_var, width=35, style="Download.TEntry").grid(row=0, column=1, padx=5, pady=5)
            ttk.Label(f, text="Qualität:", style="Download.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
            q_var = tk.StringVar(value="best")
            ttk.Combobox(f, textvariable=q_var, values=['best', '1080p', '720p', 'niedrigste'], state='readonly', width=15, style="Download.TEntry").grid(row=1, column=1, padx=5, pady=5)
            ttk.Label(f, text="Format:", style="Download.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
            fmt_var = tk.StringVar(value="mp4")
            ttk.Combobox(f, textvariable=fmt_var, values=['mp4', 'mkv', 'webm', 'avi'], state='readonly', width=15, style="Download.TEntry").grid(row=2, column=1, padx=5, pady=5)
            if edit_index is not None and 0 <= edit_index < len(domain_presets_working):
                ent = domain_presets_working[edit_index]
                if isinstance(ent, dict):
                    domain_var.set(ent.get('domain', ''))
                    q_var.set(ent.get('quality', 'best'))
                    fmt_var.set(ent.get('format', 'mp4'))
            result = [None]
            def on_ok():
                dom = domain_var.get().strip().lower()
                if not dom:
                    messagebox.showwarning("Warnung", "Bitte Domain eingeben (z. B. youtube.com).", parent=d)
                    return
                result[0] = {'domain': dom, 'quality': q_var.get().strip() or 'best', 'format': fmt_var.get().strip().lower() or 'mp4'}
                d.destroy()
            ttk.Button(f, text="OK", command=on_ok).grid(row=3, column=0, columnspan=2, pady=10)
            d.wait_window()
            return result[0]
        def add_domain_preset():
            data = domain_preset_dialog()
            if data:
                domain_presets_working.append(data)
                refresh_domain_presets()
        def remove_domain_preset():
            sel = domain_presets_listbox.curselection()
            if sel:
                idx = sel[0]
                if 0 <= idx < len(domain_presets_working):
                    domain_presets_working.pop(idx)
                    refresh_domain_presets()
        def edit_domain_preset():
            sel = domain_presets_listbox.curselection()
            if not sel:
                messagebox.showinfo("Info", "Bitte zuerst einen Eintrag auswählen.", parent=settings_window)
                return
            idx = sel[0]
            data = domain_preset_dialog(edit_index=idx)
            if data:
                domain_presets_working[idx] = data
                refresh_domain_presets()
        refresh_domain_presets()
        dp_btn_f = ttk.Frame(domain_presets_frame, style="Download.TFrame")
        dp_btn_f.pack(fill=tk.X)
        ttk.Button(dp_btn_f, text="Hinzufügen", command=add_domain_preset, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(dp_btn_f, text="Bearbeiten", command=edit_domain_preset, style="Download.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(dp_btn_f, text="Entfernen", command=remove_domain_preset, style="Download.TButton").pack(side=tk.LEFT, padx=5)
        
        # Dateinamen für Filme/Serien
        ttk.Label(video_frame, text="Dateiname Serie (Template):", style="Download.TLabel").grid(row=3, column=0, sticky=tk.W, pady=5)
        series_template_var = tk.StringVar(value=self.settings.get('series_filename_template', 'E{episode2} - {title}'))
        series_template_entry = ttk.Entry(video_frame, textvariable=series_template_var, width=40, style="Download.TEntry")
        series_template_entry.grid(row=3, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        series_help = ttk.Label(
            video_frame,
            text="Platzhalter: {series}/{staffel}, {season2}/{staffel2}, {episode}/{folge}, {episode2}/{folge2}, {title}/{name}, optional {date}/{sendedatum} (YYYY-MM-DD) oder {date_de}",
            font=("Arial", 8),
            wraplength=840,
            style="Download.TLabel"
        )
        series_help.grid(row=4, column=0, columnspan=2, sticky=tk.W, padx=5)
        settings_wrap_labels.append(series_help)
        
        ttk.Label(video_frame, text="Dateiname Film (Template):", style="Download.TLabel").grid(row=5, column=0, sticky=tk.W, pady=(5, 5))
        movie_template_var = tk.StringVar(value=self.settings.get('movie_filename_template', '{title}'))
        movie_template_entry = ttk.Entry(video_frame, textvariable=movie_template_var, width=40, style="Download.TEntry")
        movie_template_entry.grid(row=5, column=1, padx=5, pady=(5, 5), sticky=(tk.W, tk.E))
        
        ttk.Label(video_frame, text="Dateiname Audiothek/Podcast:", style="Download.TLabel").grid(row=6, column=0, sticky=tk.W, pady=(5, 5))
        audiothek_template_var = tk.StringVar(value=self.settings.get('audiothek_filename_template', 'E{episode2} - {title}'))
        audiothek_template_entry = ttk.Entry(video_frame, textvariable=audiothek_template_var, width=40, style="Download.TEntry")
        audiothek_template_entry.grid(row=6, column=1, padx=5, pady=(5, 5), sticky=(tk.W, tk.E))
        audiothek_help_lbl = ttk.Label(
            video_frame,
            text="Gilt für ARD Audiothek und ARD Sounds. Optional z. B. {date} - E{episode2} - {title} (Sendedatum zuerst).",
            font=("Arial", 8),
            wraplength=840,
            style="Download.TLabel",
        )
        audiothek_help_lbl.grid(row=7, column=0, columnspan=2, sticky=tk.W, padx=5)
        settings_wrap_labels.append(audiothek_help_lbl)
        
        # Grafikarte (GPU) für Konvertierung – nur verbaut/verfügbare anzeigen
        ttk.Label(video_frame, text="Grafikkarte (GPU):", style="Download.TLabel").grid(row=8, column=0, sticky=tk.W, pady=5)
        gpu_frame = ttk.Frame(video_frame, style="Download.TFrame")
        gpu_frame.grid(row=8, column=1, padx=5, pady=5, sticky=tk.W)
        gpu_enabled_var = tk.BooleanVar(value=self.settings.get('gpu_enabled', False))
        gpu_check_text = "GPU für Konvertierung verwenden"
        if sys.platform == 'darwin':
            gpu_check_text = "Apple GPU (VideoToolbox) für Konvertierung"
        ttk.Checkbutton(gpu_frame, text=gpu_check_text, variable=gpu_enabled_var, style="Download.TCheckbutton").pack(side=tk.LEFT, padx=(0, 10))
        available_gpus = self._get_available_gpu_vendors()
        gpu_values = ['none', 'auto'] + available_gpus
        saved_gpu = self.settings.get('gpu_vendor', 'auto')
        if saved_gpu not in gpu_values:
            saved_gpu = 'auto'
        gpu_vendor_var = tk.StringVar(value=saved_gpu)
        ttk.Label(gpu_frame, text="Karte:", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        gpu_combo = ttk.Combobox(gpu_frame, textvariable=gpu_vendor_var, values=gpu_values, state='readonly', width=12, style="Download.TEntry")
        gpu_combo.pack(side=tk.LEFT)
        gpu_hint = "(nur verbaut: " + (", ".join(available_gpus) if available_gpus else "keine erkannt") + ")"
        if sys.platform == 'darwin':
            try:
                from mac_platform import gpu_status_summary
                _ok, _sum = gpu_status_summary()
                if _sum:
                    gpu_hint = _sum
            except Exception:
                pass
        gpu_hint_lbl = ttk.Label(video_frame, text=gpu_hint, font=("Arial", 8), style="Download.TLabel")
        gpu_hint_lbl.grid(row=9, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(0, 5))
        settings_wrap_labels.append(gpu_hint_lbl)
        video_frame.columnconfigure(1, weight=1)
        
        # Anmeldung / Account-Verwaltung (Video + Musik: ORF, ARD Plus, YouTube, Deezer)
        video_accounts_frame = ttk.LabelFrame(scrollable_frame, text="🔐 Anmeldung / Account-Verwaltung", padding="10", style="Download.TLabelframe")
        video_accounts_frame.pack(fill=tk.X, pady=5, padx=5)
        ttk.Label(
            video_accounts_frame,
            text="Accounts für Video- und Musik-Dienste. Cookies im Netscape-Format (z. B. Browser-Erweiterung „Get cookies.txt LOCALLY“).",
            font=("Arial", 9),
            style="Download.TLabel"
        ).pack(anchor=tk.W, pady=(0, 4))
        deezer_cookie = "" if _store_edition() else "Deezer: .deezer.com (Cookie „arl“). "
        cookie_hint = (
            "Welche Cookies? ORF: .orf.at (Altersverifikation). ARD Plus: .ardplus.de. "
            "YouTube / YouTube Music: .youtube.com (für Playlists/Radio). "
            + deezer_cookie
            + "Für YouTube/YouTube Music: Get cookies.txt LOCALLY auf youtube.com oder music.youtube.com ausführen (eingeloggt), „Nur diese Seite“ exportieren."
        )
        cookie_hint_lbl = ttk.Label(
            video_accounts_frame,
            text=cookie_hint,
            font=("Arial", 8),
            style="Download.TLabel",
            foreground="gray",
            wraplength=840
        )
        cookie_hint_lbl.pack(anchor=tk.W, pady=(0, 8))
        settings_wrap_labels.append(cookie_hint_lbl)
        video_accounts_working = list(self.settings.get('video_accounts', []))
        video_accounts_listbox = tk.Listbox(
            video_accounts_frame, height=3, selectmode=tk.SINGLE,
            bg=getattr(self, '_tk_bg_card', '#424242'), fg=getattr(self, '_tk_fg_text', '#e8e8e8'),
            selectbackground=getattr(self, '_tk_btn_bg', '#4a4a4a'), highlightthickness=0
        )
        video_accounts_listbox.pack(fill=tk.X, pady=(0, 5))
        def refresh_video_accounts_list():
            video_accounts_listbox.delete(0, tk.END)
            for acc in video_accounts_working:
                name = acc.get('name', '').strip() or acc.get('service', '')
                video_accounts_listbox.insert(tk.END, f"{acc.get('service', '')}: {name}")
        refresh_video_accounts_list()
        def video_account_dialog(edit_index=None):
            """Öffnet Dialog zum Hinzufügen/Bearbeiten eines Video-Accounts. Returns (service, name, cookies) or None."""
            d = tk.Toplevel(settings_window)
            d.title("Account hinzufügen" if edit_index is None else "Account bearbeiten")
            d.transient(settings_window)
            d.grab_set()
            self._fit_dialog(d, 640, 520, 500, 400)
            f = ttk.Frame(d, padding="10")
            f.pack(fill=tk.BOTH, expand=True)
            ttk.Label(f, text="Dienst:").grid(row=0, column=0, sticky=tk.W, pady=5)
            service_var = tk.StringVar(value="YouTube")
            service_combo = ttk.Combobox(f, textvariable=service_var, values=["YouTube", "YouTube Music", "ORF", "ARD Plus", "Deezer"], state="readonly", width=25)
            service_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            ttk.Label(f, text="Name (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
            name_var = tk.StringVar()
            ttk.Entry(f, textvariable=name_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
            ttk.Label(f, text="Cookies (Netscape-Format aus dem Browser):").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=5)
            cookies_text = scrolledtext.ScrolledText(f, width=55, height=12, wrap=tk.WORD)
            cookies_text.grid(row=2, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
            f.columnconfigure(1, weight=1)
            f.rowconfigure(2, weight=1)
            if edit_index is not None and 0 <= edit_index < len(video_accounts_working):
                acc = video_accounts_working[edit_index]
                service_var.set(acc.get('service', 'ORF'))
                name_var.set(acc.get('name', ''))
                cookies_text.insert(tk.END, acc.get('cookies', ''))
            result = [None]
            def on_ok():
                service = service_var.get().strip()
                cookies = cookies_text.get("1.0", tk.END).strip()
                if not service:
                    messagebox.showwarning("Warnung", "Bitte Sender auswählen.", parent=d)
                    return
                if not cookies:
                    messagebox.showwarning("Warnung", "Bitte Cookies einfügen (z. B. mit Browser-Erweiterung exportieren).", parent=d)
                    return
                result[0] = {'service': service, 'name': name_var.get().strip(), 'cookies': cookies}
                d.destroy()
            def on_cancel():
                d.destroy()
            btn_f = ttk.Frame(f)
            btn_f.grid(row=3, column=0, columnspan=2, pady=15)
            ttk.Button(btn_f, text="OK", command=on_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(btn_f, text="Abbrechen", command=on_cancel).pack(side=tk.LEFT, padx=5)
            d.wait_window()
            return result[0]
        def add_video_account():
            data = video_account_dialog()
            if data:
                video_accounts_working.append(data)
                refresh_video_accounts_list()
        def edit_video_account():
            sel = video_accounts_listbox.curselection()
            if not sel:
                messagebox.showinfo("Info", "Bitte zuerst einen Account in der Liste auswählen.", parent=settings_window)
                return
            data = video_account_dialog(edit_index=sel[0])
            if data:
                video_accounts_working[sel[0]] = data
                refresh_video_accounts_list()
        def remove_video_account():
            sel = video_accounts_listbox.curselection()
            if not sel:
                messagebox.showinfo("Info", "Bitte zuerst einen Account in der Liste auswählen.", parent=settings_window)
                return
            video_accounts_working.pop(sel[0])
            refresh_video_accounts_list()
        acc_btn_f = ttk.Frame(video_accounts_frame, style="Download.TFrame")
        acc_btn_f.pack(fill=tk.X)
        ttk.Button(acc_btn_f, text="Hinzufügen", command=add_video_account, style="Download.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(acc_btn_f, text="Bearbeiten", command=edit_video_account, style="Download.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(acc_btn_f, text="Entfernen", command=remove_video_account, style="Download.TButton").pack(side=tk.LEFT, padx=5)
        
        # Untertitel-Einstellungen
        subtitle_settings_frame = ttk.LabelFrame(scrollable_frame, text="📝 Untertitel-Einstellungen", padding="10", style="Download.TLabelframe")
        subtitle_settings_frame.pack(fill=tk.X, pady=5, padx=5)
        
        subtitle_enabled_by_default_var = tk.BooleanVar(value=self.settings.get('subtitle_enabled_by_default', False))
        ttk.Checkbutton(subtitle_settings_frame, text="Untertitel standardmäßig aktivieren", variable=subtitle_enabled_by_default_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        ttk.Label(subtitle_settings_frame, text="Standard-Untertitel-Sprache:", style="Download.TLabel").pack(anchor=tk.W, pady=(10, 5))
        subtitle_default_lang_var = tk.StringVar(value=self.settings.get('subtitle_default_lang', 'de'))
        subtitle_default_lang_combo = ttk.Combobox(subtitle_settings_frame, textvariable=subtitle_default_lang_var, values=['de', 'en', 'all'], state='readonly', width=15, style="Download.TEntry")
        subtitle_default_lang_combo.pack(anchor=tk.W, pady=5)
        
        # Serien-Wächter (Benachrichtigungen bei neuen Mediathek-Folgen)
        sw_frame = ttk.LabelFrame(scrollable_frame, text="📺 Serien-Wächter (neue Folgen / Staffel)", padding="10", style="Download.TLabelframe")
        sw_frame.pack(fill=tk.X, pady=5, padx=5)
        sw_help_lbl = ttk.Label(
            sw_frame,
            text="URLs im Dialog „Serien-Wächter“ (Button in der Titelleiste). Unterstützt Playlists, die yt-dlp ausliest (z. B. ARD-Staffel-Seite).\n"
            "E-Mail: SMTP wie bei einem normalen Mailprogramm. Telegram: Bot von @BotFather, chat_id z. B. von @userinfobot. Discord: Webhook-URL des Kanals.",
            font=("Arial", 8),
            wraplength=840,
            style="Download.TLabel",
        )
        sw_help_lbl.pack(anchor=tk.W, pady=(0, 8))
        settings_wrap_labels.append(sw_help_lbl)
        series_watch_tray_enabled_var = tk.BooleanVar(value=self.settings.get('series_watch_tray_enabled', True))
        ttk.Checkbutton(
            sw_frame,
            text="Serien-Wächter verwenden (Icon im Infobereich / Menüleiste). Aus = kein Tray, kein Autostart.",
            variable=series_watch_tray_enabled_var,
            style="Download.TCheckbutton",
        ).pack(anchor=tk.W, pady=2)
        series_watch_enabled_var = tk.BooleanVar(value=self.settings.get('series_watch_enabled', False))
        ttk.Checkbutton(sw_frame, text="Automatische Prüfung aktivieren (Hintergrund)", variable=series_watch_enabled_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=2)
        sw_int_row = ttk.Frame(sw_frame, style="Download.TFrame")
        sw_int_row.pack(anchor=tk.W, pady=4)
        ttk.Label(sw_int_row, text="Prüf-Intervall (Stunden):", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        series_watch_interval_var = tk.StringVar(value=str(int(self.settings.get('series_watch_interval_hours', 6) or 6)))
        ttk.Spinbox(sw_int_row, from_=1, to=168, textvariable=series_watch_interval_var, width=6, style="Download.TEntry").pack(side=tk.LEFT)
        series_watch_auto_dl_var = tk.BooleanVar(value=self.settings.get('series_watch_auto_download', False))
        ttk.Checkbutton(
            sw_frame,
            text="Neue Folgen automatisch herunterladen (global; pro Serie im Serien-Wächter umschaltbar)",
            variable=series_watch_auto_dl_var,
            style="Download.TCheckbutton",
        ).pack(anchor=tk.W, pady=(6, 2))
        series_watch_tray_autostart_var = tk.BooleanVar(value=self.settings.get('series_watch_tray_autostart', True))
        ttk.Checkbutton(
            sw_frame,
            text="Serien-Wächter nach der Anmeldung starten (Windows-Infobereich, macOS-Menüleiste, Linux-Tray)",
            variable=series_watch_tray_autostart_var,
            style="Download.TCheckbutton",
        ).pack(anchor=tk.W, pady=(6, 2))
        series_notify_desktop_var = tk.BooleanVar(value=self.settings.get('series_notify_desktop', True))
        ttk.Checkbutton(sw_frame, text="Desktop-Benachrichtigung (Serien-Wächter)", variable=series_notify_desktop_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=(6, 2))
        sw_tray_help_lbl = ttk.Label(
            sw_frame,
            text="Tray-Helper: Icon in der Taskleiste (Windows), Menüleiste (macOS) bzw. System-Tray (Linux). Startet mit der App und – wenn aktiviert – nach der Anmeldung.",
            font=("Arial", 8),
            wraplength=840,
            style="Download.TLabel",
        )
        sw_tray_help_lbl.pack(anchor=tk.W, pady=(4, 2))
        settings_wrap_labels.append(sw_tray_help_lbl)

        series_notify_email_var = tk.BooleanVar(value=self.settings.get('series_notify_email_enabled', False))
        ttk.Checkbutton(sw_frame, text="E-Mail senden (SMTP)", variable=series_notify_email_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=(8, 2))
        smtp_grid = ttk.Frame(sw_frame, style="Download.TFrame")
        smtp_grid.pack(fill=tk.X, pady=2)
        ttk.Label(smtp_grid, text="SMTP-Host:", style="Download.TLabel").grid(row=0, column=0, sticky=tk.W, pady=2)
        series_smtp_host_var = tk.StringVar(value=self.settings.get('series_smtp_host', '') or '')
        ttk.Entry(smtp_grid, textvariable=series_smtp_host_var, width=36, style="Download.TEntry").grid(row=0, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(smtp_grid, text="Port:", style="Download.TLabel").grid(row=0, column=2, sticky=tk.W, padx=(8, 0), pady=2)
        series_smtp_port_var = tk.StringVar(value=str(self.settings.get('series_smtp_port', 587) or 587))
        ttk.Entry(smtp_grid, textvariable=series_smtp_port_var, width=6, style="Download.TEntry").grid(row=0, column=3, sticky=tk.W, padx=4, pady=2)
        ttk.Label(smtp_grid, text="Benutzer:", style="Download.TLabel").grid(row=1, column=0, sticky=tk.W, pady=2)
        series_smtp_user_var = tk.StringVar(value=self.settings.get('series_smtp_user', '') or '')
        ttk.Entry(smtp_grid, textvariable=series_smtp_user_var, width=36, style="Download.TEntry").grid(row=1, column=1, sticky=tk.W, padx=4, pady=2)
        series_smtp_tls_var = tk.BooleanVar(value=self.settings.get('series_smtp_tls', True))
        ttk.Checkbutton(smtp_grid, text="TLS (STARTTLS)", variable=series_smtp_tls_var, style="Download.TCheckbutton").grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=4, pady=2)
        ttk.Label(smtp_grid, text="Passwort (leer = unverändert):", style="Download.TLabel").grid(row=2, column=0, sticky=tk.W, pady=2)
        series_smtp_password_var = tk.StringVar()
        ttk.Entry(smtp_grid, textvariable=series_smtp_password_var, width=36, show="*", style="Download.TEntry").grid(row=2, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(smtp_grid, text="Von (Absender):", style="Download.TLabel").grid(row=3, column=0, sticky=tk.W, pady=2)
        series_email_from_var = tk.StringVar(value=self.settings.get('series_email_from', '') or '')
        ttk.Entry(smtp_grid, textvariable=series_email_from_var, width=36, style="Download.TEntry").grid(row=3, column=1, sticky=tk.W, padx=4, pady=2)
        ttk.Label(smtp_grid, text="An (Empfänger):", style="Download.TLabel").grid(row=4, column=0, sticky=tk.W, pady=2)
        series_email_to_var = tk.StringVar(value=self.settings.get('series_email_to', '') or '')
        ttk.Entry(smtp_grid, textvariable=series_email_to_var, width=48, style="Download.TEntry").grid(row=4, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=4, pady=2)
        smtp_grid.columnconfigure(1, weight=1)

        series_notify_telegram_var = tk.BooleanVar(value=self.settings.get('series_notify_telegram_enabled', False))
        ttk.Checkbutton(sw_frame, text="Telegram", variable=series_notify_telegram_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=(10, 2))
        tg_row = ttk.Frame(sw_frame, style="Download.TFrame")
        tg_row.pack(fill=tk.X, pady=2)
        ttk.Label(tg_row, text="Bot-Token:", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        series_tg_token_var = tk.StringVar(value=self.settings.get('series_telegram_bot_token', '') or '')
        ttk.Entry(tg_row, textvariable=series_tg_token_var, width=42, style="Download.TEntry").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        tg_row2 = ttk.Frame(sw_frame, style="Download.TFrame")
        tg_row2.pack(fill=tk.X, pady=2)
        ttk.Label(tg_row2, text="Chat-ID:", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        series_tg_chat_var = tk.StringVar(value=self.settings.get('series_telegram_chat_id', '') or '')
        ttk.Entry(tg_row2, textvariable=series_tg_chat_var, width=24, style="Download.TEntry").pack(side=tk.LEFT, padx=4)

        series_notify_discord_var = tk.BooleanVar(value=self.settings.get('series_notify_discord_enabled', False))
        ttk.Checkbutton(sw_frame, text="Discord (Webhook)", variable=series_notify_discord_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=(10, 2))
        series_discord_url_var = tk.StringVar(value=self.settings.get('series_discord_webhook_url', '') or '')
        ttk.Entry(sw_frame, textvariable=series_discord_url_var, width=72, style="Download.TEntry").pack(fill=tk.X, pady=2)
        
        # Allgemeine Einstellungen
        general_frame = ttk.LabelFrame(scrollable_frame, text="⚙️ Allgemeine Einstellungen", padding="10", style="Download.TLabelframe")
        general_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Versionsinformationen
        version_frame = ttk.Frame(general_frame, style="Download.TFrame")
        version_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(version_frame, text="Version:", font=("Arial", 9, "bold"), style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        version_text = get_version_string()
        ttk.Label(version_frame, text=version_text, font=("Arial", 9), style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(
            version_frame,
            text="Was ist neu?",
            command=lambda: self.show_changelog_window(full_history=True),
            style="Download.TButton",
        ).pack(side=tk.LEFT)

        # Separator
        ttk.Separator(general_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Automatisch Ordner öffnen
        auto_open_var = tk.BooleanVar(value=self.settings.get('auto_open_folder', False))
        ttk.Checkbutton(general_frame, text="Ordner nach Download automatisch öffnen", variable=auto_open_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        play_after_var = tk.BooleanVar(value=self.settings.get('play_after_download', False))
        ttk.Checkbutton(general_frame, text="Nach Download abspielen (Standard-Player)", variable=play_after_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        # Theme
        ttk.Label(general_frame, text="Design:", style="Download.TLabel").pack(anchor=tk.W, pady=(10, 2))
        theme_var = tk.StringVar(value=self.settings.get('theme', 'dark'))
        theme_combo = ttk.Combobox(general_frame, textvariable=theme_var, values=['dark', 'light'], state='readonly', width=12, style="Download.TEntry")
        theme_combo.pack(anchor=tk.W, pady=5)
        
        # Benachrichtigungen
        notifications_var = tk.BooleanVar(value=self.settings.get('show_notifications', True))
        ttk.Checkbutton(general_frame, text="Benachrichtigungen anzeigen", variable=notifications_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        # Download-Archiv (bereits heruntergeladene überspringen)
        download_archive_var = tk.BooleanVar(value=self.settings.get('download_archive_enabled', False))
        ttk.Checkbutton(general_frame, text="Bereits heruntergeladene überspringen (Download-Archiv)", variable=download_archive_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        ttk.Label(general_frame, text="Archiv-Datei: download_archive.txt im Download-Ordner (eine URL pro Zeile)", font=("Arial", 8), foreground="gray", style="Download.TLabel").pack(anchor=tk.W, padx=(20, 0))
        
        # Automatische Update-Prüfung
        auto_check_updates_var = tk.BooleanVar(value=self.settings.get('auto_check_updates', True))
        ttk.Checkbutton(general_frame, text="Automatisch auf Updates prüfen beim Start", variable=auto_check_updates_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        # Log-Level-Einstellung
        log_level_frame = ttk.Frame(general_frame, style="Download.TFrame")
        log_level_frame.pack(fill=tk.X, pady=10)
        ttk.Label(log_level_frame, text="Log-Level:", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 10))
        log_level_var = tk.StringVar(value=self.settings.get('log_level', 'debug'))
        log_level_combo = ttk.Combobox(
            log_level_frame, 
            textvariable=log_level_var, 
            values=['normal', 'debug'], 
            state='readonly', 
            width=15,
            style="Download.TEntry"
        )
        log_level_combo.pack(side=tk.LEFT, padx=5)
        
        # Info-Text für Log-Level
        log_level_info = ttk.Label(
            log_level_frame,
            text="Debug: Alle Logs (inkl. Debug-Informationen) | Normal: Nur wichtige Logs",
            font=("Arial", 8),
            style="Download.TLabel"
        )
        log_level_info.pack(side=tk.LEFT, padx=10)
        
        # Maximale gleichzeitige Downloads (Video-Warteschlange)
        ttk.Label(general_frame, text="Max. gleichzeitige Video-Downloads (Warteschlange):", style="Download.TLabel").pack(anchor=tk.W, pady=(10, 5))
        max_downloads_var = tk.StringVar(value=str(min(8, max(1, int(self.settings.get('max_concurrent_downloads', 3))))))
        max_downloads_spin = ttk.Spinbox(general_frame, from_=1, to=8, textvariable=max_downloads_var, width=10, style="Download.TEntry")
        max_downloads_spin.pack(anchor=tk.W, pady=5)
        max_dl_help_lbl = ttk.Label(
            general_frame,
            text="Mehrere URLs aus der Queue gleichzeitig. Was darüber liegt, wartet in der Queue. Bei GPU-Beschleunigung laden die Dateien parallel und werden danach nacheinander umgewandelt. Ohne GPU wird auch parallel umgewandelt.",
            font=("Arial", 8),
            foreground="gray",
            wraplength=840,
            style="Download.TLabel",
        )
        max_dl_help_lbl.pack(anchor=tk.W, padx=(0, 0), pady=(0, 5))
        settings_wrap_labels.append(max_dl_help_lbl)
        
        # Sprache
        ttk.Label(general_frame, text="Sprache:", style="Download.TLabel").pack(anchor=tk.W, pady=(10, 5))
        language_var = tk.StringVar(value=self.settings.get('language', 'de'))
        language_combo = ttk.Combobox(general_frame, textvariable=language_var, values=['de', 'en'], state='readonly', width=15, style="Download.TEntry")
        language_combo.pack(anchor=tk.W, pady=5)
        
        # Log-Verwaltung
        log_frame = ttk.LabelFrame(scrollable_frame, text="📋 Log-Verwaltung", padding="10", style="Download.TLabelframe")
        log_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Automatisches Aufräumen aktivieren
        log_cleanup_enabled_var = tk.BooleanVar(value=self.settings.get('log_cleanup_enabled', False))
        ttk.Checkbutton(log_frame, text="Automatisches Aufräumen alter Logs aktivieren", variable=log_cleanup_enabled_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        # Tage bis zum Löschen
        log_days_frame = ttk.Frame(log_frame, style="Download.TFrame")
        log_days_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(log_days_frame, text="Logs älter als:", style="Download.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        log_cleanup_days_var = tk.StringVar(value=str(self.settings.get('log_cleanup_days', 30)))
        log_days_spin = ttk.Spinbox(log_days_frame, from_=1, to=365, textvariable=log_cleanup_days_var, width=10, style="Download.TEntry")
        log_days_spin.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(log_days_frame, text="Tage werden gelöscht", style="Download.TLabel").pack(side=tk.LEFT)
        
        # Beim Beenden löschen
        log_cleanup_on_exit_var = tk.BooleanVar(value=self.settings.get('log_cleanup_on_exit', False))
        ttk.Checkbutton(log_frame, text="Logs beim Beenden der Anwendung löschen", variable=log_cleanup_on_exit_var, style="Download.TCheckbutton").pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame, style="Download.TFrame")
        button_frame.pack(fill=tk.X, pady=20, padx=5)
        
        def save_settings():
            self.settings['default_deezer_path'] = deezer_path_var.get()
            self.settings['default_audible_path'] = audible_path_var.get()
            self.settings['default_video_path'] = video_path_var.get()
            self.settings['default_video_quality'] = quality_var.get()
            self.settings['default_video_format'] = format_var.get()
            self.settings['series_filename_template'] = series_template_var.get().strip() or 'E{episode2} - {title}'
            self.settings['movie_filename_template'] = movie_template_var.get().strip() or '{title}'
            self.settings['audiothek_filename_template'] = audiothek_template_var.get().strip() or 'E{episode2} - {title}'
            self.settings['speed_limit_enabled'] = speed_limit_enabled_var.get()
            self.settings['speed_limit_value'] = speed_limit_value_var.get()
            self.settings['gpu_enabled'] = gpu_enabled_var.get()
            self.settings['gpu_vendor'] = gpu_vendor_var.get()
            self.settings['subtitle_enabled_by_default'] = subtitle_enabled_by_default_var.get()
            self.settings['subtitle_default_lang'] = subtitle_default_lang_var.get()
            self.settings['video_accounts'] = list(video_accounts_working)
            self.settings['auto_open_folder'] = auto_open_var.get()
            self.settings['play_after_download'] = play_after_var.get()
            self.settings['theme'] = theme_var.get()
            self.settings['domain_quality_format'] = [e for e in domain_presets_working if isinstance(e, dict)]
            self.settings['show_notifications'] = notifications_var.get()
            self.settings['download_archive_enabled'] = download_archive_var.get()
            self.settings['max_concurrent_downloads'] = min(8, max(1, int(max_downloads_var.get() or 1)))
            self.settings['language'] = language_var.get()
            self.settings['log_cleanup_enabled'] = log_cleanup_enabled_var.get()
            self.settings['log_cleanup_days'] = int(log_cleanup_days_var.get())
            self.settings['log_cleanup_on_exit'] = log_cleanup_on_exit_var.get()
            self.settings['auto_check_updates'] = auto_check_updates_var.get()
            self.settings['log_level'] = log_level_var.get()

            self.settings['series_watch_enabled'] = series_watch_enabled_var.get()
            try:
                self.settings['series_watch_interval_hours'] = min(168, max(1, int(series_watch_interval_var.get() or 6)))
            except (TypeError, ValueError):
                self.settings['series_watch_interval_hours'] = 6
            self.settings['series_watch_auto_download'] = series_watch_auto_dl_var.get()
            self.settings['series_watch_tray_enabled'] = series_watch_tray_enabled_var.get()
            self.settings['series_watch_tray_autostart'] = series_watch_tray_autostart_var.get()
            try:
                import series_watch_tray as _swt
                if not self.settings['series_watch_tray_enabled']:
                    _swt.remove_login_autostart()
                    _swt.steal_tray_instance(self.base_download_path)
                    self._series_watch_tray_app = None
                    try:
                        self._write_to_log_file("[Serien-Wächter] Deaktiviert (kein Tray, kein Autostart).", "INFO")
                    except Exception:
                        pass
                else:
                    if self.settings['series_watch_tray_autostart']:
                        _swt.install_login_autostart()
                    else:
                        _swt.remove_login_autostart()
                    self._series_watch_tray_app = None
                    self._start_series_watch_tray()
            except Exception:
                pass
            self.settings['series_notify_desktop'] = series_notify_desktop_var.get()
            self.settings['series_notify_email_enabled'] = series_notify_email_var.get()
            self.settings['series_smtp_host'] = series_smtp_host_var.get().strip()
            try:
                self.settings['series_smtp_port'] = int(series_smtp_port_var.get().strip() or 587)
            except (TypeError, ValueError):
                self.settings['series_smtp_port'] = 587
            self.settings['series_smtp_user'] = series_smtp_user_var.get().strip()
            pw_series = series_smtp_password_var.get().strip()
            if pw_series:
                self.settings['series_smtp_password_enc'] = self._encrypt_password(pw_series)
            self.settings['series_smtp_tls'] = series_smtp_tls_var.get()
            self.settings['series_email_from'] = series_email_from_var.get().strip()
            self.settings['series_email_to'] = series_email_to_var.get().strip()
            self.settings['series_notify_telegram_enabled'] = series_notify_telegram_var.get()
            self.settings['series_telegram_bot_token'] = series_tg_token_var.get().strip()
            self.settings['series_telegram_chat_id'] = series_tg_chat_var.get().strip()
            self.settings['series_notify_discord_enabled'] = series_notify_discord_var.get()
            self.settings['series_discord_webhook_url'] = series_discord_url_var.get().strip()
            self.settings['enabled_tabs'] = {
                'music': bool(tab_music_var.get()),
                'audible': bool(tab_audible_var.get()) and not _store_edition(),
                'video': bool(tab_video_var.get()),
            }
            if not any(self.settings['enabled_tabs'].values()):
                self.settings['enabled_tabs']['music'] = True

            self._save_settings()
            self._apply_enabled_tabs()
            self._apply_theme(self.settings.get('theme', 'dark'))
            self._windows_round_window(self.root)
            
            # Führe Log-Aufräumen aus wenn aktiviert
            if log_cleanup_enabled_var.get():
                self._cleanup_old_logs()
            
            # Aktualisiere Download-Pfade
            self.download_path = Path(self.settings['default_deezer_path'])
            self.audible_download_path = Path(self.settings['default_audible_path'])
            self.video_download_path = Path(self.settings['default_video_path'])
            
            # Erstelle Ordner falls nicht vorhanden
            try:
                self.download_path.mkdir(parents=True, exist_ok=True)
                self.audible_download_path.mkdir(parents=True, exist_ok=True)
                self.video_download_path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                messagebox.showerror(
                    "Einstellungen",
                    "Mindestens ein Download-Ordner konnte nicht angelegt werden:\n\n"
                    f"{e}\n\n"
                    "Prüfen Sie z. B. ob ein externes Laufwerk eingeschlossen ist, oder wählen Sie einen anderen Pfad.",
                    parent=settings_window,
                )
                return
            
            # Aktualisiere UI
            self.update_download_path()
            if hasattr(self, 'audible_download_path_var'):
                self.audible_download_path_var.set(str(self.audible_download_path))
            if hasattr(self, 'video_download_path_var'):
                self.video_download_path_var.set(str(self.video_download_path))
            
            # Aktualisiere Video-Tab UI basierend auf Einstellungen
            self._update_video_tab_visibility()
            
            messagebox.showinfo("Einstellungen", "Einstellungen wurden gespeichert!")
            settings_window.destroy()
        
        ttk.Button(button_frame, text="💾 Speichern", command=save_settings, style="Download.TButton.Large").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Abbrechen", command=settings_window.destroy, style="Download.TButton").pack(side=tk.LEFT, padx=5)
        
        # Pack canvas und scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Fokus auf erstes Widget
        deezer_entry.focus()
    
    def _browse_folder(self, path_var):
        """Öffnet einen Ordner-Dialog"""
        folder = filedialog.askdirectory(initialdir=path_var.get())
        if folder:
            path_var.set(folder)
    
    def _load_window_geometry(self):
        """Lädt gespeicherte Fenstergröße"""
        try:
            config_file = self.base_download_path / "window_config.json"
            if config_file.exists():
                import json
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    geometry = config.get('geometry')
                    if geometry:
                        # Validiere die Geometrie (sollte Format "WIDTHxHEIGHT+X+Y" haben)
                        parts = geometry.split('+')
                        if len(parts) >= 2:
                            size_part = parts[0]
                            if 'x' in size_part.lower():
                                return geometry
                        # Falls Format nicht stimmt, versuche es trotzdem
                        return geometry
        except Exception as e:
            # Fehler beim Laden ignorieren
            pass
        return None
    
    def _save_window_geometry(self):
        """Speichert aktuelle Fenstergröße"""
        try:
            config_file = self.base_download_path / "window_config.json"
            import json
            geometry = self.root.geometry()
            config = {'geometry': geometry}
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            # Debug: Log nur wenn Logging aktiv ist
            if hasattr(self, 'log_file') and self.log_file:
                try:
                    self._write_to_log_file(f"[WINDOW] Fenstergröße gespeichert: {geometry}")
                except:
                    pass
        except Exception as e:
            # Debug: Fehler loggen
            try:
                if hasattr(self, 'log_file') and self.log_file:
                    self._write_to_log_file(f"[WINDOW] Fehler beim Speichern der Fenstergröße: {e}")
            except:
                pass
    
    def _on_window_configure(self, event):
        """Wird aufgerufen, wenn sich die Fenstergröße ändert"""
        # Nur speichern, wenn es sich um das Hauptfenster handelt (nicht um Child-Windows)
        if event.widget == self.root:
            # Download-Bereich einmal nach Ziehende anpassen (entprellt, kein Hänger)
            self._schedule_resize_download_panels()
            # Prüfe ob sich die Größe tatsächlich geändert hat
            current_geometry = self.root.geometry()
            if not hasattr(self, '_last_geometry') or self._last_geometry != current_geometry:
                self._last_geometry = current_geometry
                # Debounce: Speichere nur nach einer kurzen Verzögerung
                if self._geometry_save_timer is not None:
                    self.root.after_cancel(self._geometry_save_timer)
                self._geometry_save_timer = self.root.after(1000, self._save_window_geometry)
    
    def _load_video_data(self):
        """Lädt gespeicherte Video-Daten"""
        try:
            data_file = self.base_download_path / "video_data.json"
            if data_file.exists():
                import json
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.video_scheduled_downloads = [
                        {**item, 'scheduled_time': datetime.fromisoformat(item['scheduled_time'])}
                        for item in data.get('scheduled_downloads', [])
                    ]
                    self.video_download_history = data.get('download_history', [])
                    self.video_favorites = data.get('favorites', [])
                    self.video_statistics = data.get('statistics', self.video_statistics)
                    self.music_statistics = data.get('music_statistics', self.music_statistics)
        except Exception as e:
            self.video_log(f"⚠ Fehler beim Laden der Video-Daten: {e}")
    
    def _save_video_data(self):
        """Speichert Video-Daten"""
        try:
            data_file = self.base_download_path / "video_data.json"
            import json
            data = {
                'scheduled_downloads': [
                    {**item, 'scheduled_time': item['scheduled_time'].isoformat()}
                    for item in self.video_scheduled_downloads
                ],
                'download_history': self.video_download_history,
                'favorites': self.video_favorites,
                'statistics': self.video_statistics,
                'music_statistics': getattr(self, 'music_statistics', {}),
            }
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.video_log(f"⚠ Fehler beim Speichern der Video-Daten: {e}")
    
    def video_log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Video-Log hinzu"""
        # Bestimme Level basierend auf Nachricht
        if "[DEBUG]" in message:
            level = "DEBUG"
        elif "[WARNING]" in message or "⚠" in message:
            level = "WARNING"
        elif "[ERROR]" in message or "✗" in message:
            level = "ERROR"
        
        # Prüfe Log-Level-Einstellung
        log_level_setting = self.settings.get('log_level', 'debug')
        
        # In normalem Modus: Überspringe DEBUG-Logs in GUI
        show_in_gui = True
        if log_level_setting == 'normal' and level == 'DEBUG':
            show_in_gui = False
        
        # Schreibe in Log-Datei (immer, aber mit Level-Filterung)
        self._write_to_log_file(f"[VIDEO] {message}", level)
        
        # Zeige in GUI (wenn nicht übersprungen)
        if show_in_gui and hasattr(self, 'video_log_text'):
            self.video_log_text.config(state=tk.NORMAL)
            level_prefix = f"[{level}] " if level != "INFO" else ""
            self.video_log_text.insert(tk.END, f"{level_prefix}{message}\n")
            self.video_log_text.see(tk.END)
            self.video_log_text.config(state=tk.DISABLED)
            self.root.update_idletasks()
    
    def log(self, message: str, level: str = "INFO"):
        """Fügt eine Nachricht zum Log hinzu"""
        # Bestimme Level basierend auf Nachricht
        if "[DEBUG]" in message:
            level = "DEBUG"
        elif "[WARNING]" in message or "⚠" in message:
            level = "WARNING"
        elif "[ERROR]" in message or "✗" in message:
            level = "ERROR"
        
        # Prüfe Log-Level-Einstellung
        log_level_setting = self.settings.get('log_level', 'debug')
        
        # In normalem Modus: Überspringe DEBUG-Logs in GUI
        show_in_gui = True
        if log_level_setting == 'normal' and level == 'DEBUG':
            show_in_gui = False
        
        # Schreibe in Log-Datei (immer, aber mit Level-Filterung)
        self._write_to_log_file(f"[DEEZER] {message}", level)
        
        # Zeige in GUI (wenn nicht übersprungen)
        if show_in_gui and hasattr(self, 'log_text'):
            self.log_text.config(state=tk.NORMAL)
            level_prefix = f"[{level}] " if level != "INFO" else ""
            self.log_text.insert(tk.END, f"{level_prefix}{message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def show_quality_dialog(self, default_quality: str = "MP3_320") -> Optional[str]:
        """
        Zeigt Qualitätsauswahl-Dialog
        
        Args:
            default_quality: Standard-Qualität
            
        Returns:
            Gewählte Qualität oder None bei Abbruch
        """
        quality_window = tk.Toplevel(self.root)
        quality_window.title("Qualität auswählen")
        quality_window.transient(self.root)
        quality_window.grab_set()
        self._fit_dialog(quality_window, 480, 360, 400, 280)
        
        quality_frame = ttk.Frame(quality_window, padding="20")
        quality_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            quality_frame,
            text="Wählen Sie die gewünschte Qualität:",
            font=("Arial", 10, "bold")
        ).pack(pady=10)
        
        selected_quality = tk.StringVar(value=default_quality)
        
        qualities = [
            ("FLAC (Lossless, beste Qualität)", "FLAC"),
            ("MP3 320 kbps (hohe Qualität)", "MP3_320"),
            ("MP3 192 kbps (mittlere Qualität)", "MP3_192"),
            ("MP3 128 kbps (niedrige Qualität)", "MP3_128"),
        ]
        
        for text, value in qualities:
            rb = ttk.Radiobutton(
                quality_frame,
                text=text,
                variable=selected_quality,
                value=value
            )
            rb.pack(anchor=tk.W, pady=5)
        
        result = [None]
        
        def confirm():
            result[0] = selected_quality.get()
            quality_window.destroy()
        
        def cancel():
            quality_window.destroy()
        
        button_frame = ttk.Frame(quality_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Bestätigen", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        quality_window.wait_window()
        return result[0]
    
    def start_download(self):
        """Startet den Download in einem separaten Thread"""
        url = self.url_var.get().strip()
        
        if not url:
            messagebox.showwarning("Warnung", "Bitte geben Sie eine Deezer-URL ein.")
            return
        
        # Downloader initialisieren
        self.download_path = Path(self.path_var.get())
        self.downloader = DeezerDownloader(download_path=str(self.download_path), auth=self.auth)
        
        # Qualitätsauswahl-Dialog
        default_quality = self.downloader.quality if self.downloader else "MP3_320"
        selected_quality = self.show_quality_dialog(default_quality)
        if not selected_quality:
            return  # Benutzer hat abgebrochen
        
        # Setze gewählte Qualität
        self.downloader.quality = selected_quality
        
        # UI deaktivieren
        self.download_button.config(state=tk.DISABLED)
        self.progress_bar.start()
        self.status_var.set("Download läuft...")
        
        # Download in separatem Thread starten
        thread = threading.Thread(target=self.download_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def download_thread(self, url: str):
        """Download-Thread"""
        try:
            self.log(f"Starte Download für: {url}")
            self.log("=" * 60)
            
            # Führe Download durch
            count = self.downloader.download_from_url(url)
            
            # Zeige alle Log-Einträge an
            for log_entry in self.downloader.download_log:
                self.log(log_entry)
            
            # Zeige Zusammenfassung
            if self.downloader.download_results:
                successful = sum(1 for r in self.downloader.download_results if r.success)
                deezer_count = sum(1 for r in self.downloader.download_results if r.source == "Deezer")
                youtube_count = sum(1 for r in self.downloader.download_results if r.source == "YouTube")
                
                self.log("")
                self.log("=" * 60)
                self.log("ZUSAMMENFASSUNG:")
                self.log(f"Erfolgreich: {successful}/{len(self.downloader.download_results)}")
                self.log(f"  • Deezer: {deezer_count}")
                self.log(f"  • YouTube (Fallback): {youtube_count}")
                self.log("=" * 60)
            
            if count > 0:
                successful = sum(1 for r in self.downloader.download_results if r.success) if self.downloader.download_results else count
                deezer_count = sum(1 for r in self.downloader.download_results if r.source == "Deezer") if self.downloader.download_results else 0
                youtube_count = sum(1 for r in self.downloader.download_results if r.source == "YouTube") if self.downloader.download_results else 0
                
                self.status_var.set(f"Download abgeschlossen: {count} Track(s)")
                messagebox.showinfo(
                    "Erfolg",
                    f"Download erfolgreich abgeschlossen!\n{count} Track(s) heruntergeladen.\n\n"
                    f"Deezer: {deezer_count}\n"
                    f"YouTube: {youtube_count}"
                )
            else:
                self.log("\n✗ Download fehlgeschlagen")
                self.status_var.set("Download fehlgeschlagen")
                messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte Log prüfen.")
        
        except Exception as e:
            error_msg = f"Fehler: {str(e)}"
            self.log(f"\n✗ {error_msg}")
            self.status_var.set("Fehler aufgetreten")
            messagebox.showerror("Fehler", error_msg)
        
        finally:
            # UI wieder aktivieren
            self.progress_bar.stop()
            self.download_button.config(state=tk.NORMAL)
            self.status_var.set("Bereit")


def main():
    """Hauptfunktion"""
    # Setze RESOURCE_NAME Umgebungsvariable für Linux (MUSS vor tk.Tk() gesetzt werden)
    if sys.platform.startswith("linux"):
        os.environ['RESOURCE_NAME'] = 'UniversalDownloader'
    # Apple Silicon: Homebrew/ffmpeg-Pfade voranstellen
    if sys.platform == "darwin":
        try:
            from mac_platform import ensure_macos_native_path
            ensure_macos_native_path()
        except Exception:
            pass
    
    root = tk.Tk()
    # Tk zeigt sonst sofort ein schwarzes Fenster mit dem EXE-Pfad als Titel.
    root.title("Universal Downloader")
    try:
        root.attributes("-alpha", 0.0)
    except Exception:
        pass
    try:
        root.withdraw()
        root.update()
    except Exception:
        pass
    
    # Setze WM_CLASS für Linux (MUSS sofort nach tk.Tk() gesetzt werden, vor allem anderen)
    if sys.platform.startswith("linux"):
        def set_wm_class():
            """Setze WM_CLASS mit mehreren Methoden für maximale Kompatibilität"""
            try:
                # Methode 1: tkinter wm_class (beide Parameter)
                root.wm_class("UniversalDownloader", "UniversalDownloader")
            except:
                pass
            
            try:
                # Methode 2: Direkter tk.call Zugriff
                root.tk.call('wm', 'class', root._w, 'UniversalDownloader')
            except:
                pass
            
            try:
                # Methode 3: WM_NAME separat setzen
                root.tk.call('wm', 'name', root._w, 'Universal Downloader')
            except:
                pass
        
        # Setze sofort
        set_wm_class()
        
        # Setze erneut nach update_idletasks (wenn Fenster vollständig initialisiert ist)
        root.after(10, set_wm_class)
        root.after(100, set_wm_class)
        root.after(500, set_wm_class)
        
        # Verwende xprop als Fallback (nachdem Fenster erstellt wurde)
        root.after(200, lambda: _set_wm_class_x11(root))
        root.after(1000, lambda: _set_wm_class_x11(root))
    
    # Wichtig: update_idletasks() vor dem Erstellen der App, damit das Fenster initialisiert ist.
    # Alpha bleibt 0, damit dabei kein leeres Fenster aufblitzt.
    root.update_idletasks()
    
    app = DeezerDownloaderGUI(root)
    try:
        root.deiconify()
        root.attributes("-alpha", 1.0)
        root.update_idletasks()
    except Exception:
        try:
            root.deiconify()
        except Exception:
            pass
    
    # Setze Icon erneut nach vollständiger Initialisierung
    if sys.platform == "win32":
        root.after(100, app._set_application_icon)
        
        # Versuche App-Namen für Windows Taskleiste zu setzen
        try:
            import ctypes
            from ctypes import wintypes
            
            # Setze App User Model ID (für Windows 7+)
            # Dies hilft Windows, die Anwendung korrekt zu identifizieren
            try:
                shell32 = ctypes.windll.shell32
                # SetCurrentProcessExplicitAppUserModelID
                app_id = "UniversalDownloader.UniversalDownloader.1.0"
                shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
            except:
                pass
        except:
            pass
    elif sys.platform.startswith("linux"):
        # Für Linux: Setze Icon sofort
        root.after(100, app._set_application_icon)
    
    # Cleanup beim Schließen
    def on_closing():
        if app._video_downloads_running():
            app._save_window_geometry()
            root.withdraw()
            try:
                import series_watch as _sw
                _sw.desktop_notify(
                    "Universal Downloader",
                    "Fenster geschlossen. Der Download läuft in der Menüleiste weiter.",
                )
            except Exception:
                pass
            return
        app._save_window_geometry()
        app._close_log_file()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    if sys.platform == "darwin":
        def _mac_reopen():
            try:
                root.deiconify()
                root.lift()
                root.focus_force()
            except Exception:
                pass
        try:
            root.createcommand("::tk::mac::ReopenApplication", _mac_reopen)
        except Exception:
            pass
    root.mainloop()


def _set_wm_class_x11(root):
    """Setze WM_CLASS über xprop (X11 direkt) - Fallback-Methode"""
    if not sys.platform.startswith("linux"):
        return
    
    try:
        # Hole Fenster-ID
        window_id = root.winfo_id()
        if window_id:
            # Verwende xprop um WM_CLASS zu setzen
            # Format: WM_CLASS(STRING) = "name", "class"
            # WICHTIG: xprop erwartet "name,class" als einen String
            cmd = ['xprop', '-id', str(window_id), '-f', 'WM_CLASS', '8s', '-set', 'WM_CLASS', 'UniversalDownloader,UniversalDownloader']
            result = subprocess.run(cmd, capture_output=True, timeout=2, check=False)
            
            # Setze auch WM_NAME
            cmd_name = ['xprop', '-id', str(window_id), '-f', 'WM_NAME', '8s', '-set', 'WM_NAME', 'Universal Downloader']
            subprocess.run(cmd_name, capture_output=True, timeout=2, check=False)
            
            # Setze auch _NET_WM_NAME (für moderne Desktop Environments)
            try:
                cmd_net_name = ['xprop', '-id', str(window_id), '-f', '_NET_WM_NAME', '8s', '-set', '_NET_WM_NAME', 'Universal Downloader']
                subprocess.run(cmd_net_name, capture_output=True, timeout=2, check=False)
            except:
                pass
    except Exception:
        # xprop nicht verfügbar oder Fehler - ignoriere
        pass


if __name__ == "__main__":
    main()

