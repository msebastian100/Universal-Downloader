#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI für Deezer Downloader
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
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


class DeezerDownloaderGUI:
    """GUI-Klasse für den Deezer Downloader"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Downloader")
        
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
            self.root.geometry("1000x700")
        
        self.root.resizable(True, True)
        
        # Speichere Fenstergröße bei Änderungen
        self.root.bind('<Configure>', self._on_window_configure)
        
        # Initialisiere Timer-Variable
        self._geometry_save_timer = None
        
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
        
        # Prüfe auf Updates beim Start (wenn aktiviert)
        if self.settings.get('auto_check_updates', True):
            # Prüfe im Hintergrund nach 5 Sekunden (damit GUI vollständig geladen ist)
            self.root.after(5000, self._check_updates_on_start)
        
        # Downloader-Instanz
        self.downloader = None
        # Verwende gespeicherte Pfade aus Einstellungen
        # Gemeinsamer Pfad für Deezer und Spotify
        self.music_download_path = Path(self.settings.get('default_music_path', str(self.base_download_path / "Musik")))
        self.music_download_path.mkdir(parents=True, exist_ok=True)
        self.auth = None
        
        # Audible
        self.audible_auth = None
        self.audible_library = None
        self.audible_download_path = Path(self.settings.get('default_audible_path', str(self.base_download_path / "Audible")))
        self.audible_download_path.mkdir(parents=True, exist_ok=True)
        
        # Video Downloader
        self.video_download_path = Path(self.settings.get('default_video_path', str(self.base_download_path / "Video")))
        self.video_download_path.mkdir(parents=True, exist_ok=True)
        
        # Download-Prozess-Referenz für Abbrechen
        self.video_download_process = None
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
        
        # Initialisiere letzte Geometrie nach dem Setzen
        self._last_geometry = self.root.geometry()
        
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
                temp_audible_auth = AudibleAuth()
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
        except Exception as e:
            self._safe_log(f"[ICON] Fehler beim Setzen des Icons: {e}")
    
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
    
    def create_widgets(self):
        """Erstellt alle UI-Widgets"""
        
        # Hauptframe
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Konfiguriere Grid-Gewichtung
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Titel-Bar mit Einstellungs-Button
        title_frame = ttk.Frame(main_frame)
        title_frame.grid(row=0, column=0, pady=(0, 10), sticky=(tk.W, tk.E))
        title_frame.columnconfigure(0, weight=1)
        
        title_label = ttk.Label(
            title_frame,
            text="🎵 Universal Downloader",
            font=("Arial", 18, "bold")
        )
        title_label.grid(row=0, column=0, sticky=tk.W)
        
        # Buttons rechts (Historie, Favoriten, Statistiken, Einstellungen)
        buttons_frame = ttk.Frame(title_frame)
        buttons_frame.grid(row=0, column=1, sticky=tk.E)
        
        ttk.Button(
            buttons_frame,
            text="🔍 Suche",
            command=self.show_search_dialog
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            buttons_frame,
            text="📝 Historie",
            command=self.show_download_history
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            buttons_frame,
            text="⭐ Favoriten",
            command=self.show_favorites
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            buttons_frame,
            text="📊 Statistiken",
            command=self.show_statistics
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            buttons_frame,
            text="⚙️ Einstellungen",
            command=self.show_settings_dialog
        ).pack(side=tk.LEFT, padx=2)
        
        # Notebook für Tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Musik Tab (Deezer & Spotify kombiniert)
        self.music_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.music_frame, text="🎵 Musik")
        # Verwende die umbenannte create_deezer_tab als Basis für create_music_tab
        self.create_music_tab()
        
        # Audible Tab
        if AudibleAuth:
            self.audible_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(self.audible_frame, text="📚 Audible")
            self.create_audible_tab()
        
        # Video Downloader Tab
        if VideoDownloader:
            self.video_frame = ttk.Frame(self.notebook, padding="10")
            self.notebook.add(self.video_frame, text="🎬 Video Downloader")
            self.create_video_tab()
    
    def create_music_tab(self):
        """Erstellt den kombinierten Musik-Tab (Deezer & Spotify)"""
        main_frame = self.music_frame
        
        # Konfiguriere Grid
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Info-Label
        info_frame = ttk.Frame(main_frame)
        info_frame.grid(row=0, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        
        info_text = (
            "Unterstützt Deezer und Spotify URLs.\n"
            "Downloads erfolgen über YouTube/Deezer-Fallback.\n"
            "Metadaten werden von der ursprünglichen Quelle abgerufen."
        )
        ttk.Label(
            info_frame,
            text=info_text,
            foreground="gray",
            justify=tk.LEFT
        ).pack(anchor=tk.W)
        
        # Authentifizierungs-Status (nur für Deezer)
        auth_frame = ttk.Frame(main_frame)
        auth_frame.grid(row=1, column=0, columnspan=3, pady=(0, 10), sticky=(tk.W, tk.E))
        
        self.auth_status_var = tk.StringVar(value="Deezer: Nicht angemeldet")
        auth_status_label = ttk.Label(
            auth_frame,
            textvariable=self.auth_status_var,
            foreground="gray"
        )
        auth_status_label.pack(side=tk.LEFT, padx=5)
        
        self.login_button = ttk.Button(
            auth_frame,
            text="Deezer anmelden",
            command=self.show_login_dialog
        )
        self.login_button.pack(side=tk.RIGHT, padx=5)
        
        self.logout_button = ttk.Button(
            auth_frame,
            text="Abmelden",
            command=self.logout,
            state=tk.DISABLED
        )
        self.logout_button.pack(side=tk.RIGHT, padx=5)
        
        # Spotify API Button
        if SpotifyDownloader:
            ttk.Button(
                auth_frame,
                text="⚙️ Spotify API",
                command=self.show_spotify_api_config
            ).pack(side=tk.RIGHT, padx=5)
        
        # Download-Pfad Auswahl
        ttk.Label(main_frame, text="Download-Pfad:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )
        
        self.music_path_var = tk.StringVar(value=str(self.music_download_path))
        path_entry = ttk.Entry(main_frame, textvariable=self.music_path_var, width=50, state="readonly")
        path_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        path_button = ttk.Button(
            main_frame,
            text="Durchsuchen...",
            command=self.browse_music_download_path
        )
        path_button.grid(row=2, column=2, padx=5, pady=5)
        
        # URL-Eingabe
        ttk.Label(main_frame, text="URL (Deezer oder Spotify):").grid(
            row=3, column=0, sticky=tk.W, pady=5
        )
        
        self.music_url_var = tk.StringVar()
        url_entry = ttk.Entry(main_frame, textvariable=self.music_url_var, width=50)
        url_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        url_entry.bind('<Return>', lambda e: self.start_music_download())
        # Unterstützung für Paste (Strg+V / Cmd+V) - verhindere doppelte Auslösung
        def handle_paste(event):
            # Erlaube Standard-Paste-Verhalten
            return None  # None erlaubt Standard-Verhalten
        url_entry.bind('<Control-v>', handle_paste)
        url_entry.bind('<Command-v>', handle_paste)
        # Stelle sicher, dass das Feld fokussierbar ist
        url_entry.focus_set()
        
        # Download-Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=2, padx=5, pady=5, sticky=tk.E)
        
        self.music_download_button = ttk.Button(
            button_frame,
            text="⬇️ Download starten",
            command=self.start_music_download,
            state=tk.NORMAL
        )
        self.music_download_button.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            button_frame,
            text="➕ Zur Queue",
            command=self.add_music_to_queue
        ).pack(side=tk.LEFT)
        
        # Log-Ausgabe
        ttk.Label(main_frame, text="Log:").grid(
            row=4, column=0, sticky=(tk.W, tk.N), pady=5
        )
        
        self.music_log_text = scrolledtext.ScrolledText(
            main_frame,
            width=70,
            height=20,
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.music_log_text.grid(
            row=4, column=1, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5
        )
        
        # Progress Bar
        self.music_progress_var = tk.DoubleVar()
        self.music_progress_bar = ttk.Progressbar(
            main_frame,
            variable=self.music_progress_var,
            maximum=100,
            mode='indeterminate'
        )
        self.music_progress_bar.grid(
            row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10
        )
        
        # Status-Label
        self.music_status_var = tk.StringVar(value="Bereit")
        status_label = ttk.Label(
            main_frame,
            textvariable=self.music_status_var,
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        status_label.grid(
            row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )
    
    def create_audible_tab(self):
        """Erstellt den Audible-Tab"""
        main_frame = self.audible_frame
        
        # Konfiguriere Grid
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(2, weight=1)
        
        # Authentifizierung
        auth_frame = ttk.Frame(main_frame)
        auth_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.audible_status_var = tk.StringVar(value="Nicht angemeldet")
        ttk.Label(auth_frame, textvariable=self.audible_status_var).pack(side=tk.LEFT, padx=5)
        
        button_container = ttk.Frame(auth_frame)
        button_container.pack(side=tk.RIGHT, padx=5)
        
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
        
        ttk.Button(
            button_container,
            text="Activation Bytes",
            command=self.show_activation_bytes_dialog
        ).pack(side=tk.LEFT, padx=2)
        
        # Bibliothek-Liste
        library_frame = ttk.LabelFrame(main_frame, text="Meine Hörbücher (sortiert nach zuletzt gekauft)", padding="10")
        library_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        library_frame.columnconfigure(0, weight=1)
        library_frame.rowconfigure(0, weight=1)
        
        # Treeview für Hörbücher
        columns = ('Titel', 'Autor', 'Dauer', 'Gekauft')
        self.audible_tree = ttk.Treeview(library_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.audible_tree.heading(col, text=col)
            self.audible_tree.column(col, width=200)
        
        scrollbar = ttk.Scrollbar(library_frame, orient=tk.VERTICAL, command=self.audible_tree.yview)
        self.audible_tree.configure(yscrollcommand=scrollbar.set)
        
        self.audible_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Download-Button
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=10)
        
        ttk.Button(
            button_frame,
            text="Ausgewählte Hörbücher herunterladen",
            command=self.download_selected_audible_books
        ).pack(side=tk.LEFT, padx=5)
    
    def create_video_tab(self):
        """Erstellt den Video-Downloader-Tab"""
        main_frame = self.video_frame
        
        # Konfiguriere Grid
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # Erstelle PanedWindow für bessere Aufteilung (links Optionen, rechts Log)
        paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        main_frame.rowconfigure(0, weight=1)
        
        # ===== LINKE SEITE: OPTIONEN (mit Scrollbar) =====
        options_container = ttk.Frame(paned, width=400)
        paned.add(options_container, weight=0)
        
        # Info-Text oben
        info_text = "Unterstützte Sender: YouTube, ARD, ZDF, ORF, SWR, BR, WDR, MDR, NDR, HR, RBB, SR, Phoenix, Arte, Tagesschau, RocketBeans TV"
        info_label = ttk.Label(options_container, text=info_text, foreground="gray", font=("Arial", 8), justify=tk.LEFT, wraplength=380)
        info_label.pack(pady=(0, 10), padx=5)
        
        # Scrollbar für Optionen
        options_canvas = tk.Canvas(options_container, width=380)
        options_scrollbar = ttk.Scrollbar(options_container, orient="vertical", command=options_canvas.yview)
        scrollable_options = ttk.Frame(options_canvas)
        
        scrollable_options.bind("<Configure>", lambda e: options_canvas.configure(scrollregion=options_canvas.bbox("all")))
        options_canvas.create_window((0, 0), window=scrollable_options, anchor="nw")
        options_canvas.configure(yscrollcommand=options_scrollbar.set)
        
        options_canvas.pack(side="left", fill="both", expand=True)
        options_scrollbar.pack(side="right", fill="y")
        
        # Verwende scrollable_options für alle Optionen
        opt = scrollable_options
        
        # Download-Pfad
        path_frame = ttk.LabelFrame(opt, text="Download-Pfad", padding="5")
        path_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_path_var = tk.StringVar()
        path_entry = ttk.Entry(path_frame, textvariable=self.video_path_var)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(path_frame, text="...", width=3, command=self.browse_video_download_path).pack(side=tk.RIGHT)
        
        # URL-Eingabe
        url_frame = ttk.LabelFrame(opt, text="Video-URL", padding="5")
        url_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_url_var = tk.StringVar()
        url_entry = ttk.Entry(url_frame, textvariable=self.video_url_var)
        url_entry.pack(fill=tk.X, padx=(0, 5))
        url_entry.bind('<Return>', lambda e: self.start_video_download())
        # Unterstützung für Paste (Strg+V / Cmd+V) - verhindere doppelte Auslösung
        def handle_paste(event):
            # Erlaube Standard-Paste-Verhalten
            return None  # None erlaubt Standard-Verhalten
        url_entry.bind('<Control-v>', handle_paste)
        url_entry.bind('<Command-v>', handle_paste)
        # Stelle sicher, dass das Feld fokussierbar ist
        url_entry.focus_set()
        
        # Batch-Download Button
        ttk.Button(url_frame, text="📁 URLs aus Datei laden", command=self.load_urls_from_file).pack(fill=tk.X, pady=(5, 0))
        
        # Format-Auswahl
        format_frame = ttk.LabelFrame(opt, text="Format", padding="5")
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Lade Format aus Einstellungen
        default_format = self.settings.get('default_video_format', 'mp4')
        self.video_format_var = tk.StringVar(value=default_format)
        formats = [("MP4", "mp4"), ("MP3", "mp3"), ("WebM", "webm"), ("MKV", "mkv"), ("AVI", "avi"), ("Keine", "none")]
        for text, value in formats:
            ttk.Radiobutton(format_frame, text=text, variable=self.video_format_var, value=value).pack(side=tk.LEFT, padx=5)
        
        # Qualität
        quality_frame = ttk.LabelFrame(opt, text="Qualität", padding="5")
        quality_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Lade Qualität aus Einstellungen
        default_quality = self.settings.get('default_video_quality', 'best')
        self.video_quality_var = tk.StringVar(value=default_quality)
        qualities = [("Beste", "best"), ("1080p", "1080p"), ("720p", "720p"), ("Niedrigste", "niedrigste")]
        for text, value in qualities:
            ttk.Radiobutton(quality_frame, text=text, variable=self.video_quality_var, value=value).pack(side=tk.LEFT, padx=5)
        
        # Erweiterte Optionen
        advanced_frame = ttk.LabelFrame(opt, text="Erweiterte Optionen", padding="5")
        advanced_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_resume_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text="Download fortsetzen (Resume)", variable=self.video_resume_var).pack(anchor=tk.W, pady=2)
        
        # Beschreibungstext und Thumbnail (unter Erweiterte Optionen)
        self.video_description_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Beschreibungstext (Info.txt)", variable=self.video_description_var).pack(anchor=tk.W, pady=2)
        
        self.video_thumbnail_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Thumbnail/Cover (cover.jpg)", variable=self.video_thumbnail_var).pack(anchor=tk.W, pady=2)
        
        # Untertitel (nur anzeigen wenn in Einstellungen aktiviert)
        self.subtitle_frame = ttk.LabelFrame(opt, text="Untertitel", padding="5")
        self.subtitle_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_subtitle_var = tk.BooleanVar(value=self.settings.get('subtitle_enabled_by_default', False))
        subtitle_checkbox = ttk.Checkbutton(self.subtitle_frame, text="Untertitel herunterladen", variable=self.video_subtitle_var, command=lambda: self._update_subtitle_language_state())
        subtitle_checkbox.pack(anchor=tk.W, pady=2)
        
        subtitle_lang_frame = ttk.Frame(self.subtitle_frame)
        subtitle_lang_frame.pack(anchor=tk.W, padx=(20, 0))
        ttk.Label(subtitle_lang_frame, text="Sprache:").pack(side=tk.LEFT, padx=(0, 5))
        self.video_subtitle_lang_var = tk.StringVar(value=self.settings.get('subtitle_default_lang', 'de'))
        subtitle_lang_combo = ttk.Combobox(subtitle_lang_frame, textvariable=self.video_subtitle_lang_var, values=["de", "en", "all"], state="readonly", width=10)
        subtitle_lang_combo.pack(side=tk.LEFT)
        self.subtitle_lang_combo = subtitle_lang_combo
        
        # Geschwindigkeits-Limit Variablen (werden aus Einstellungen geladen)
        self.video_speed_limit_var = tk.BooleanVar(value=self.settings.get('speed_limit_enabled', False))
        self.video_speed_value_var = tk.StringVar(value=str(self.settings.get('speed_limit_value', '5')))
        
        # Button-Frame für Download und Queue
        button_frame = ttk.Frame(opt)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Download-Button
        self.video_download_button = ttk.Button(button_frame, text="▶ Download starten", command=self.start_video_download, state=tk.NORMAL)
        self.video_download_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        # Zur Queue hinzufügen Button
        self.video_add_to_queue_button = ttk.Button(button_frame, text="➕ Zur Queue", command=self.add_video_to_queue, state=tk.NORMAL)
        self.video_add_to_queue_button.pack(side=tk.LEFT, padx=5)
        
        # Abbrechen-Button
        self.video_cancel_button = ttk.Button(opt, text="⏹ Download abbrechen", command=self.cancel_video_download, state=tk.DISABLED)
        self.video_cancel_button.pack(fill=tk.X, padx=5, pady=5)
        
        # Queue-Status-Label
        self.video_queue_status_label = ttk.Label(opt, text="📋 Queue: 0 Downloads", font=("Arial", 9))
        self.video_queue_status_label.pack(fill=tk.X, padx=5, pady=(0, 5))
        
        # Queue-Buttons
        queue_button_frame = ttk.Frame(opt)
        queue_button_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(queue_button_frame, text="📋 Queue anzeigen", command=self.show_download_queue).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(queue_button_frame, text="▶ Queue starten", command=self.start_queue_download).pack(side=tk.LEFT, padx=2)
        
        # Geplante Downloads
        ttk.Button(opt, text="⏰ Geplante Downloads", command=self.show_scheduled_downloads).pack(fill=tk.X, padx=5, pady=2)
        
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
        
        # Lade gespeicherte Daten
        self._load_video_data()
        
        # Starte Scheduler-Thread für geplante Downloads
        self.scheduler_running = True
        scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        scheduler_thread.start()
        
        # ===== RECHTE SEITE: LOG UND STATUS =====
        log_container = ttk.Frame(paned)
        paned.add(log_container, weight=1)
        
        log_container.columnconfigure(0, weight=1)
        log_container.rowconfigure(0, weight=1)
        
        # Log-Ausgabe
        ttk.Label(log_container, text="Download-Log:", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 0))
        
        self.video_log_text = scrolledtext.ScrolledText(log_container, wrap=tk.WORD, state=tk.DISABLED, height=25)
        self.video_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Progress Bar und Status
        status_frame = ttk.Frame(log_container)
        status_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.video_progress_var = tk.DoubleVar()
        self.video_progress_bar = ttk.Progressbar(status_frame, variable=self.video_progress_var, maximum=100, mode='determinate')
        self.video_progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        self.video_status_var = tk.StringVar(value="Bereit")
        video_status_label = ttk.Label(status_frame, textvariable=self.video_status_var, relief=tk.SUNKEN, anchor=tk.W, font=("Arial", 9))
        video_status_label.pack(fill=tk.X)
        
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
        # Unterstützung für Paste (Strg+V / Cmd+V)
        url_entry.bind('<Control-v>', lambda e: url_entry.event_generate('<<Paste>>'))
        url_entry.bind('<Command-v>', lambda e: url_entry.event_generate('<<Paste>>'))
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
        config_window.geometry("600x500")
        config_window.resizable(True, True)
        
        # Zentriere das Fenster
        config_window.transient(self.root)
        config_window.grab_set()
        
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
            wraplength=620,
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
    
    def start_music_download(self):
        """Startet den Musik-Download (Deezer oder Spotify)"""
        url = self.music_url_var.get().strip()
        
        # Bereinige URL von doppelten Einträgen
        url = self._clean_url(url)
        
        # Aktualisiere das Feld mit der bereinigten URL
        self.music_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine URL ein.")
            return
        
        # Erkenne URL-Typ
        is_spotify = 'spotify.com' in url.lower()
        is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower() or 'link.deezer.com' in url.lower()
        
        if not (is_spotify or is_deezer):
            messagebox.showwarning("Ungültige URL", "Bitte geben Sie eine gültige Deezer- oder Spotify-URL ein.")
            return
        
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
        
        # Aktualisiere das Feld mit der bereinigten URL
        self.music_url_var.set(url)
        
        if not url:
            messagebox.showwarning("Keine URL", "Bitte geben Sie eine URL ein.")
            return
        
        # Erkenne URL-Typ
        is_spotify = 'spotify.com' in url.lower()
        is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower() or 'link.deezer.com' in url.lower()
        
        if not (is_spotify or is_deezer):
            messagebox.showwarning("Ungültige URL", "Bitte geben Sie eine gültige Deezer- oder Spotify-URL ein.")
            return
        
        # Füge zur Queue hinzu
        if not hasattr(self, 'music_download_queue'):
            self.music_download_queue = []
        
        self.music_download_queue.append(url)
        self.music_log(f"Zur Queue hinzugefügt: {url}")
        self.music_status_var.set(f"Zur Queue hinzugefügt ({len(self.music_download_queue)} Einträge)")
        messagebox.showinfo("Queue", f"URL zur Queue hinzugefügt.\nAktuelle Queue-Größe: {len(self.music_download_queue)}")
    
    def music_download_thread(self, url: str):
        """Download-Thread für Musik (Deezer oder Spotify)"""
        try:
            # Erkenne URL-Typ
            is_spotify = 'spotify.com' in url.lower()
            is_deezer = 'deezer.com' in url.lower() or 'deezer.page.link' in url.lower()
            
            self.root.after(0, lambda: self.music_status_var.set("Download läuft..."))
            self.root.after(0, lambda: self.music_progress_bar.start())
            self.root.after(0, lambda: self.music_download_button.config(state=tk.DISABLED))
            
            self.music_log(f"Starte Download: {url}")
            
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
                    self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                    self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                    self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                else:
                    self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                    self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
            
            elif is_deezer:
                # Deezer-Download
                if not self.downloader:
                    self.downloader = DeezerDownloader(
                        download_path=self.music_download_path,
                        auth=self.auth
                    )
                
                # Redirect log output
                original_log = self.downloader.log
                def logged_log(message, level="INFO"):
                    original_log(message, level)
                    self.root.after(0, lambda: self.music_log(f"[{level}] {message}"))
                self.downloader.log = logged_log
                
                # Prüfe ob es Artist oder Playlist ist - zeige Auswahl-Dialog
                if '/artist/' in url:
                    artist_id = self.downloader.extract_id_from_url(url)
                    if artist_id:
                        # Hole Artist-Info und Tracks
                        artist_info = self.downloader.get_artist_info(artist_id)
                        if artist_info:
                            # Hole Top-Tracks
                            try:
                                tracks_url = f"{self.downloader.api_base}/artist/{artist_id}/top?limit=100"
                                response = self.downloader.session.get(tracks_url, timeout=10)
                                response.raise_for_status()
                                data = response.json()
                                tracks = data.get('data', [])
                                
                                if tracks:
                                    # Zeige Auswahl-Dialog
                                    selected_tracks = self.show_track_selection_dialog(
                                        title=f"🎵 Artist: {artist_info.get('name', 'Unbekannt')}",
                                        tracks=tracks,
                                        is_artist=True
                                    )
                                    
                                    if selected_tracks:
                                        # Lade ausgewählte Tracks herunter
                                        artist_name = artist_info.get('name', 'Unbekannt')
                                        count = self.download_selected_tracks(
                                            selected_tracks,
                                            context_type='artist',
                                            context_name=artist_name,
                                            artist_name=artist_name
                                        )
                                        if count > 0:
                                            self.root.after(0, lambda: self.music_status_var.set(f"✓ Download abgeschlossen: {count} Track(s)"))
                                            self.root.after(0, lambda: self.music_log(f"\n✓ Download erfolgreich abgeschlossen: {count} Track(s)"))
                                            self.root.after(0, lambda: messagebox.showinfo("Erfolg", f"Download abgeschlossen!\n{count} Track(s) heruntergeladen."))
                                        else:
                                            self.root.after(0, lambda: self.music_status_var.set("✗ Download fehlgeschlagen"))
                                            self.root.after(0, lambda: messagebox.showerror("Fehler", "Download fehlgeschlagen. Bitte prüfen Sie die Logs."))
                                    else:
                                        self.root.after(0, lambda: self.music_status_var.set("Download abgebrochen"))
                                else:
                                    self.root.after(0, lambda: messagebox.showwarning("Warnung", "Keine Tracks für diesen Artist gefunden."))
                            except Exception as e:
                                self.music_log(f"Fehler beim Abrufen der Artist-Tracks: {e}")
                                self.root.after(0, lambda: messagebox.showerror("Fehler", f"Fehler beim Abrufen der Tracks: {e}"))
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
            self.root.after(0, lambda: self.music_progress_bar.stop())
            self.root.after(0, lambda: self.music_download_button.config(state=tk.NORMAL))
    
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
        login_window.geometry("500x400")
        login_window.transient(self.root)
        login_window.grab_set()
        
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
        login_window.geometry("450x300")
        login_window.transient(self.root)
        login_window.grab_set()
        
        login_frame = ttk.Frame(login_window, padding="20")
        login_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info-Text
        info_text = (
            "Wählen Sie eine Anmeldemethode:\n\n"
            "🌐 Browser-Anmeldung (empfohlen):\n"
            "   Öffnet einen Browser, Sie können sich dort\n"
            "   normal anmelden (inkl. 2FA). Cookies werden\n"
            "   automatisch aus dem Browser-Profil extrahiert.\n\n"
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
        """Führt Browser-Anmeldung durch"""
        login_window.destroy()
        
        # Zeige Info-Dialog
        messagebox.showinfo(
            "Browser-Anmeldung",
            "Ein Browser-Fenster wird jetzt geöffnet.\n\n"
            "Bitte:\n"
            "1. Melden Sie sich bei Audible an (inkl. 2FA falls aktiviert)\n"
            "2. Gehen Sie nach erfolgreicher Anmeldung zu:\n"
            "   https://www.audible.de/library\n"
            "3. Stellen Sie sicher, dass Sie eingeloggt sind\n"
            "4. Kehren Sie hier zurück und klicken Sie auf 'Weiter'\n"
            "5. Cookies werden automatisch aus Ihrem Browser-Profil extrahiert\n\n"
            "💡 Die Cookies werden direkt aus Safari/Chrome/Firefox gelesen,\n"
            "   sodass sie genau so sind, wie der Browser sie verwendet.\n\n"
            "Klicken Sie auf OK, um fortzufahren."
        )
        
        # Verwende Event für Thread-Haupt-Thread-Kommunikation
        # Der Dialog wird VOR dem Thread-Start geöffnet
        continue_event = threading.Event()
        result_queue = queue.Queue()
        
        # Erstelle Dialog für Bestätigung nach Browser-Anmeldung
        # Dieser Dialog wird im Haupt-Thread geöffnet, BEVOR der Thread startet
        continue_window = tk.Toplevel(self.root)
        continue_window.title("Browser-Anmeldung")
        continue_window.geometry("500x300")
        continue_window.transient(self.root)
        continue_window.grab_set()
        
        continue_frame = ttk.Frame(continue_window, padding="20")
        continue_frame.pack(fill=tk.BOTH, expand=True)
        
        info_text = (
            "Bitte folgen Sie diesen Schritten:\n\n"
            "1. Melden Sie sich im geöffneten Browser an (inkl. 2FA)\n"
            "2. Gehen Sie nach erfolgreicher Anmeldung zu:\n"
            "   https://www.audible.de/library\n"
            "3. Stellen Sie sicher, dass Sie eingeloggt sind\n"
            "4. Klicken Sie dann auf 'Weiter'"
        )
        
        ttk.Label(continue_frame, text=info_text, justify=tk.LEFT).pack(pady=10)
        
        def continue_login():
            result_queue.put(True)
            continue_event.set()
            continue_window.destroy()
        
        def cancel():
            result_queue.put(False)
            continue_event.set()
            continue_window.destroy()
        
        button_frame = ttk.Frame(continue_frame)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Weiter", command=continue_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Abbrechen", command=cancel).pack(side=tk.LEFT, padx=5)
        
        # GUI-Callback, der auf das Event wartet (wird im Thread aufgerufen)
        def gui_callback_safe() -> bool:
            """Thread-sicherer GUI-Callback - wartet auf Event"""
            # Warte auf das Event (blockierend, aber OK im Thread)
            timeout = 300  # 5 Minuten
            if continue_event.wait(timeout=timeout):
                # Event wurde gesetzt, hole Ergebnis
                try:
                    return result_queue.get_nowait()
                except queue.Empty:
                    return False
            else:
                # Timeout
                return False
        
        def login_thread():
            try:
                # Wechsle zum Deezer-Tab für Logs
                self.root.after(0, lambda: self.notebook.select(0))
                self.log("Starte Browser-Anmeldung...")
                self.log("=" * 60)
                
                auth = AudibleAuth()
                
                # Führe Browser-Anmeldung durch mit GUI-Callback
                # Dies öffnet einen Browser und wartet auf GUI-Bestätigung
                success = auth.login_with_browser(gui_callback=gui_callback_safe)
                
                if success:
                    self.audible_auth = auth
                    self.audible_library = AudibleLibrary(auth)
                    
                    # Bestimme Email falls verfügbar
                    email = auth.email if auth.email else "Browser-Anmeldung"
                    self.audible_status_var.set(f"✓ Angemeldet ({email})")
                    self.audible_load_button.config(state=tk.NORMAL)
                    
                    self.log("✓ Browser-Anmeldung erfolgreich!")
                    self.log("=" * 60)
                    
                    # Wechsle zurück zum Audible-Tab
                    self.notebook.select(1)
                    
                    messagebox.showinfo("Erfolg", "Erfolgreich angemeldet über Browser!")
                else:
                    self.log("✗ Browser-Anmeldung fehlgeschlagen")
                    self.log("=" * 60)
                    self.notebook.select(1)
                    
                    messagebox.showwarning(
                        "Anmeldung fehlgeschlagen",
                        "Browser-Anmeldung konnte Cookies nicht automatisch extrahieren.\n\n"
                        "Bitte verwenden Sie stattdessen:\n"
                        "• Cookie-Anmeldung (manuell) - Kopieren Sie Cookies aus dem Browser\n"
                        "• Oder versuchen Sie es erneut"
                    )
            except Exception as e:
                self.log(f"✗ Fehler bei Browser-Anmeldung: {e}")
                self.notebook.select(1)
                messagebox.showerror("Fehler", f"Fehler bei der Browser-Anmeldung: {e}")
        
        thread = threading.Thread(target=login_thread)
        thread.daemon = True
        thread.start()
    
    def show_cookie_login(self, parent_window):
        """Zeigt Dialog für Cookie-Anmeldung"""
        cookie_window = tk.Toplevel(self.root)
        cookie_window.title("Cookie-Anmeldung")
        cookie_window.geometry("600x550")
        cookie_window.transient(self.root)
        cookie_window.grab_set()
        
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
                auth = AudibleAuth()
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
    
    def load_audible_library(self):
        """Lädt die Audible-Bibliothek"""
        if not self.audible_auth or not self.audible_auth.is_logged_in():
            messagebox.showwarning("Warnung", "Bitte zuerst anmelden.")
            return
        
        def load_thread():
            try:
                # Wechsle zum Deezer-Tab für Logs
                self.notebook.select(0)
                self.log("Lade Audible-Bibliothek...")
                books = self.audible_library.fetch_library()
                
                # Lösche alte Einträge
                for item in self.audible_tree.get_children():
                    self.audible_tree.delete(item)
                
                # Füge Hörbücher hinzu (sortiert nach zuletzt gekauft)
                for book in books:
                    self.audible_tree.insert(
                        '',
                        tk.END,
                        values=(
                            book.get('title', 'Unbekannt'),
                            book.get('author', 'Unbekannt'),
                            book.get('duration', 'Unbekannt'),
                            book.get('purchase_date', 'Unbekannt')[:10] if book.get('purchase_date') else 'Unbekannt'
                        ),
                        tags=(book.get('asin', ''),)
                    )
                
                self.log(f"✓ Bibliothek geladen: {len(books)} Hörbücher")
                # Wechsle zurück zum Audible-Tab
                self.notebook.select(1)
                messagebox.showinfo("Erfolg", f"Bibliothek geladen: {len(books)} Hörbücher")
            except Exception as e:
                self.log(f"✗ Fehler beim Laden der Bibliothek: {e}")
                messagebox.showerror("Fehler", f"Fehler beim Laden der Bibliothek: {e}")
        
        thread = threading.Thread(target=load_thread)
        thread.daemon = True
        thread.start()
    
    def show_activation_bytes_dialog(self):
        """Zeigt Dialog zur manuellen Eingabe von Activation Bytes"""
        if not self.audible_auth:
            messagebox.showwarning("Warnung", "Bitte melden Sie sich zuerst bei Audible an.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Activation Bytes")
        dialog.geometry("550x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
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
        ttk.Label(auto_frame, text=info_text, justify=tk.LEFT, wraplength=500).pack(pady=5)
        
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
        options_window.geometry("450x350")
        options_window.transient(self.root)
        options_window.grab_set()
        
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
            info_window.geometry("600x380")
            info_window.transient(self.root)
            info_window.grab_set()
            
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
                wraplength=550
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
        
        # Prüfe ob URL unterstützt wird
        if not self.video_downloader.is_supported_url(url):
            response = messagebox.askyesno(
                "URL möglicherweise nicht unterstützt",
                f"Die URL scheint nicht von einem bekannten Sender zu stammen.\n\n"
                f"Trotzdem versuchen? (yt-dlp unterstützt viele weitere Quellen)"
            )
            if not response:
                return
        
        # Prüfe ob es eine Serie/Staffel ist
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
        self.video_status_var.set("Download läuft...")
        self.video_download_cancelled = False
        
        # Download in separatem Thread starten
        thread = threading.Thread(target=self.video_download_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def video_download_thread(self, url: str):
        """Video-Download-Thread"""
        try:
            # Wechsle zum Video-Tab für Logs
            self.notebook.select(self.notebook.index(self.video_frame))
            
            # Prüfe ob es eine YouTube-URL ist
            is_youtube = 'youtube.com' in url.lower() or 'youtu.be' in url.lower()
            is_youtube_playlist = 'list=' in url.lower() or '/playlist' in url.lower()
            
            self.video_log("=" * 60)
            self.video_log(f"Starte Video-Download")
            self.video_log(f"URL: {url}")
            format_display = self.video_format_var.get().upper() if self.video_format_var.get() != "none" else "Keine"
            self.video_log(f"Format: {format_display}")
            self.video_log(f"Qualität: {self.video_quality_var.get()}")
            if is_youtube and is_youtube_playlist:
                self.video_log(f"YouTube-Playlist erkannt: Gesamte Playlist wird heruntergeladen")
            self.video_log(f"Ziel: {self.video_download_path}")
            self.video_log("=" * 60)
            
            # Hole Video-Informationen
            self.video_log("\nRufe Video-Informationen ab...")
            video_info = self.video_downloader.get_video_info(url)
            
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
                self.video_log(f"  Dauer: {duration_str}")
                self.video_log(f"  Uploader: {video_info.get('uploader', 'Unbekannt')}")
                
                # Zeige tatsächlich verwendete Auflösung basierend auf ausgewählter Qualität
                selected_quality = self.video_quality_var.get()
                actual_resolution = self.video_downloader._get_actual_resolution(video_info, selected_quality)
                if actual_resolution:
                    quality_display = selected_quality
                    if selected_quality == "best":
                        quality_display = "Beste"
                    elif selected_quality == "niedrigste":
                        quality_display = "Niedrigste"
                    self.video_log(f"  Qualität: {quality_display} → {actual_resolution}")
            
            # Starte Download mit Fortschritts-Callback
            self.video_log("\nStarte Download...")
            
            def progress_callback(percent, status_line):
                """Callback für Fortschritts-Updates"""
                try:
                    self.video_progress_var.set(percent)
                    
                    # Extrahiere Geschwindigkeit und ETA aus Status-Line
                    speed_str = ""
                    eta_str = ""
                    
                    if status_line:
                        # Geschwindigkeit extrahieren (z.B. "at 5.2MiB/s" oder "at 1.5MB/s")
                        speed_match = re.search(r'at\s+([\d.]+)\s*([KMGT]?i?B/s)', status_line, re.IGNORECASE)
                        if speed_match:
                            speed_value = speed_match.group(1)
                            speed_unit = speed_match.group(2)
                            speed_str = f" - {speed_value}{speed_unit}"
                        
                        # ETA extrahieren
                        eta_match = re.search(r'ETA\s+(\d+:\d+)', status_line)
                        if eta_match:
                            eta_str = f" - ETA: {eta_match.group(1)}"
                    
                    # Status-Text zusammenstellen
                    status_text = f"Download läuft... {percent:.1f}%{speed_str}{eta_str}"
                    self.video_status_var.set(status_text)
                    self.root.update_idletasks()
                except:
                    pass
            
            # Prüfe ob es eine Serie ist (nur für nicht-YouTube URLs)
            is_series = False
            series_name = None
            season_number = None
            
            if not is_youtube and video_info:
                is_series = bool(video_info.get('series') or video_info.get('season_number'))
                series_name = video_info.get('series')
                season_number = video_info.get('season_number')
            
            # Für YouTube: Playlist automatisch erkennen
            download_playlist = is_youtube and is_youtube_playlist
            
            # Geschwindigkeits-Limit (aus Einstellungen)
            speed_limit = None
            if self.settings.get('speed_limit_enabled', False):
                try:
                    speed_limit = float(self.settings.get('speed_limit_value', '5'))
                except ValueError:
                    speed_limit = None
            
            success, file_path, error = self.video_downloader.download_video(
                url,
                output_dir=self.video_download_path,
                quality=self.video_quality_var.get(),
                output_format=self.video_format_var.get(),
                download_playlist=download_playlist,
                progress_callback=progress_callback,
                video_info=video_info,
                is_series=is_series,
                series_name=series_name,
                season_number=season_number,
                download_subtitles=self.video_subtitle_var.get(),
                subtitle_language=self.video_subtitle_lang_var.get(),
                download_description=self.video_description_var.get(),
                download_thumbnail=self.video_thumbnail_var.get(),
                resume_download=self.video_resume_var.get(),
                speed_limit=speed_limit,
                embed_metadata=True,  # Immer aktiviert
                gui_instance=self  # Übergebe GUI-Instanz direkt
            )
            
            if success:
                if file_path:
                    self.video_log(f"\n✓ Download erfolgreich!")
                    self.video_log(f"  Datei: {file_path.name}")
                    self.video_log(f"  Pfad: {file_path}")
                    self.video_status_var.set(f"✓ Download erfolgreich: {file_path.name}")
                    
                    # Aktualisiere Statistiken
                    self._update_statistics(success=True, file_path=file_path, url=url)
                    
                    # Füge zur Historie hinzu
                    self._add_to_history(url, file_path.name, "Erfolgreich")
                    
                    messagebox.showinfo(
                        "Erfolg",
                        f"Download erfolgreich!\n\nDatei: {file_path.name}\n\nGespeichert in:\n{file_path.parent}"
                    )
                else:
                    self.video_log(f"\n⚠ Download scheint erfolgreich, aber Datei nicht gefunden")
                    self.video_status_var.set("⚠ Download abgeschlossen (Datei nicht gefunden)")
                    
                    # Aktualisiere Statistiken
                    self._update_statistics(success=True, file_path=None, url=url)
                    
                    # Füge zur Historie hinzu
                    self._add_to_history(url, "N/A", "Datei nicht gefunden")
                    
                    messagebox.showwarning(
                        "Warnung",
                        "Download abgeschlossen, aber Datei nicht gefunden.\nBitte prüfen Sie das Download-Verzeichnis."
                    )
            else:
                self.video_log(f"\n✗ Download fehlgeschlagen: {error}")
                self.video_status_var.set(f"✗ Download fehlgeschlagen")
                
                # Aktualisiere Statistiken
                self._update_statistics(success=False, file_path=None, url=url)
                
                # Füge zur Historie hinzu
                self._add_to_history(url, "N/A", f"Fehlgeschlagen: {error}")
                
                messagebox.showerror("Fehler", f"Download fehlgeschlagen:\n\n{error}")
            
        except Exception as e:
            self.video_log(f"\n✗ Fehler: {e}")
            import traceback
            self.video_log(traceback.format_exc())
            self.video_status_var.set(f"✗ Fehler: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Download: {e}")
        finally:
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
            
            # Prüfe ob Queue-Downloads vorhanden sind und starte automatisch
            self._process_download_queue()
    
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
            
            # Beende den Prozess falls vorhanden
            if self.video_download_process:
                try:
                    import os
                    import signal
                    import sys
                    import time
                    
                    self.video_log(f"[DEBUG] Prozess-Objekt vorhanden: {type(self.video_download_process)}")
                    self.video_log(f"[DEBUG] Prozess PID: {self.video_download_process.pid if hasattr(self.video_download_process, 'pid') else 'N/A'}")
                    self.video_log(f"[DEBUG] Prozess Status (poll()): {self.video_download_process.poll()}")
                    
                    # Beende Prozessgruppe (alle Kindprozesse werden auch beendet)
                    if sys.platform != 'win32':
                        # Unix/macOS: Beende ganze Prozessgruppe
                        try:
                            pgid = os.getpgid(self.video_download_process.pid)
                            self.video_log(f"[DEBUG] Beende Prozessgruppe {pgid} mit SIGTERM")
                            os.killpg(pgid, signal.SIGTERM)
                            time.sleep(0.3)
                            if self.video_download_process.poll() is None:
                                self.video_log(f"[DEBUG] Prozess läuft noch, sende SIGKILL")
                                os.killpg(pgid, signal.SIGKILL)
                            else:
                                self.video_log(f"[DEBUG] Prozess erfolgreich beendet")
                        except (ProcessLookupError, OSError) as e:
                            # Prozess bereits beendet oder Prozessgruppe nicht gefunden
                            self.video_log(f"[DEBUG] Prozessgruppe nicht gefunden: {e}, versuche direkt")
                            try:
                                self.video_download_process.terminate()
                                time.sleep(0.3)
                                if self.video_download_process.poll() is None:
                                    self.video_log(f"[DEBUG] Prozess läuft noch, kill()")
                                    self.video_download_process.kill()
                            except Exception as e2:
                                self.video_log(f"[DEBUG] Fehler beim direkten Beenden: {e2}")
                    else:
                        # Windows: Beende Prozessgruppe
                        self.video_log(f"[DEBUG] Windows: Beende Prozess")
                        self.video_download_process.terminate()
                        time.sleep(0.3)
                        if self.video_download_process.poll() is None:
                            self.video_log(f"[DEBUG] Prozess läuft noch, kill()")
                            self.video_download_process.kill()
                except Exception as e:
                    self.video_log(f"⚠ Fehler beim Abbrechen: {e}")
                    import traceback
                    self.video_log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                self.video_log("[DEBUG] WARNUNG: Kein Prozess-Objekt gespeichert!")
                self.video_log("[DEBUG] Der Download-Thread läuft möglicherweise noch...")
            
            # UI aktualisieren
            self.video_download_button.config(state=tk.NORMAL)
            if hasattr(self, 'video_cancel_button'):
                self.video_cancel_button.config(state=tk.DISABLED)
            self.video_status_var.set("Download abgebrochen")
            self.video_progress_var.set(0)
        else:
            # Einzelner Download - normale Abfrage
            if not messagebox.askyesno("Download abbrechen", "Möchten Sie den laufenden Download wirklich abbrechen?"):
                return
            
            import time
            self.video_log("\n" + "="*60)
            self.video_log("⚠ ABBRUCH ANGEORDNET")
            self.video_log(f"[DEBUG] Abbrechen-Button geklickt um {time.strftime('%H:%M:%S')}")
            self.video_log(f"[DEBUG] video_download_cancelled wird auf True gesetzt")
            self.video_download_cancelled = True
            self.video_download_cancel_current_only = False
            self.video_log(f"[DEBUG] video_download_cancelled ist jetzt: {self.video_download_cancelled}")
            self.video_log("⚠ Download wird abgebrochen...")
            self.video_status_var.set("Download wird abgebrochen...")
            
            # Beende den Prozess falls vorhanden
            if self.video_download_process:
                try:
                    import os
                    import signal
                    import sys
                    
                    self.video_log(f"[DEBUG] Prozess-Objekt vorhanden: {type(self.video_download_process)}")
                    self.video_log(f"[DEBUG] Prozess PID: {self.video_download_process.pid if hasattr(self.video_download_process, 'pid') else 'N/A'}")
                    self.video_log(f"[DEBUG] Prozess Status (poll()): {self.video_download_process.poll()}")
                    self.video_log(f"[DEBUG] Prozess vorhanden: PID {self.video_download_process.pid}")
                    
                    # Beende Prozessgruppe (alle Kindprozesse werden auch beendet)
                    if sys.platform != 'win32':
                        # Unix/macOS: Beende ganze Prozessgruppe
                        try:
                            pgid = os.getpgid(self.video_download_process.pid)
                            self.video_log(f"[DEBUG] Beende Prozessgruppe {pgid} mit SIGTERM")
                            os.killpg(pgid, signal.SIGTERM)
                            time.sleep(0.3)
                            if self.video_download_process.poll() is None:
                                self.video_log(f"[DEBUG] Prozess läuft noch, sende SIGKILL")
                                os.killpg(pgid, signal.SIGKILL)
                            else:
                                self.video_log(f"[DEBUG] Prozess erfolgreich beendet")
                        except (ProcessLookupError, OSError) as e:
                            # Prozess bereits beendet oder Prozessgruppe nicht gefunden
                            self.video_log(f"[DEBUG] Prozessgruppe nicht gefunden: {e}, versuche direkt")
                            try:
                                self.video_download_process.terminate()
                                time.sleep(0.3)
                                if self.video_download_process.poll() is None:
                                    self.video_log(f"[DEBUG] Prozess läuft noch, kill()")
                                    self.video_download_process.kill()
                            except Exception as e2:
                                self.video_log(f"[DEBUG] Fehler beim direkten Beenden: {e2}")
                    else:
                        # Windows: Beende Prozessgruppe
                        self.video_log(f"[DEBUG] Windows: Beende Prozess")
                        self.video_download_process.terminate()
                        time.sleep(0.3)
                        if self.video_download_process.poll() is None:
                            self.video_log(f"[DEBUG] Prozess läuft noch, kill()")
                            self.video_download_process.kill()
                except Exception as e:
                    self.video_log(f"⚠ Fehler beim Abbrechen: {e}")
                    import traceback
                    self.video_log(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                self.video_log("[DEBUG] WARNUNG: Kein Prozess-Objekt gespeichert!")
                self.video_log("[DEBUG] Der Download-Thread läuft möglicherweise noch...")
            
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
        selection_window.geometry("950x750")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        # Hauptcontainer mit einheitlichem Design
        main_frame = ttk.Frame(selection_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Titel-Bereich mit Hintergrund
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        series_name = series_data.get('series_name', 'Unbekannte Serie/Playlist')
        total_episodes = series_data.get('total_episodes', 0)
        seasons = series_data.get('seasons', {})
        
        if is_youtube_playlist:
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
        
        # Variablen für Checkboxen
        season_vars = {}  # {season_num: BooleanVar}
        episode_vars = {}  # {(season_num, episode_idx): BooleanVar}
        
        # Erstelle UI für jede Staffel/Playlist
        for season_num in sorted(seasons.keys()):
            season_episodes = seasons[season_num]
            
            # Staffel/Playlist-Frame mit verbessertem Design
            if is_youtube_playlist:
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
                
                if ep_num is not None:
                    if is_youtube_playlist:
                        label_text = f"▶ {ep_num:02d}. {title}"
                    else:
                        label_text = f"▶ E{ep_num:02d}: {title}"
                else:
                    label_text = f"▶ {title}"
                
                # Füge Dauer hinzu
                if duration:
                    label_text += f" ({duration})"
                
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
                if is_youtube_playlist:
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
            if is_youtube_playlist:
                confirm_button.config(text=f"▶ Download ({count} Video(s))")
            else:
                confirm_button.config(text=f"▶ Download ({count} Folge(n))")
        
        # Initialisiere Button-Text
        if is_youtube_playlist:
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
        selection_window.geometry("800x700")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
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
                    for remaining_episode in remaining_episodes:
                        remaining_url = remaining_episode.get('url')
                        if remaining_url:
                            # Erstelle Episode-Info für Queue-Eintrag
                            remaining_episode_info = {
                                'title': remaining_episode.get('title', 'Unbekannt'),
                                'series_name': remaining_episode.get('series', series_name),
                                'season_number': remaining_episode.get('season_number', season_number),
                                'episode_number': remaining_episode.get('episode_number'),
                                'url': remaining_url
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
                
                # Fortschritt für alle Episoden berechnen
                def progress_callback(percent, status_line):
                    """Callback für Fortschritts-Updates"""
                    try:
                        # Gesamtfortschritt = (abgeschlossene Episoden + aktuelle Episode Fortschritt) / Gesamtanzahl
                        episode_progress = percent / len(episodes)
                        total_progress = ((i - 1) / len(episodes)) * 100 + episode_progress
                        self.video_progress_var.set(total_progress)
                        
                        # Extrahiere Geschwindigkeit und ETA
                        speed_str = ""
                        eta_str = ""
                        
                        if status_line:
                            # Geschwindigkeit extrahieren
                            speed_match = re.search(r'at\s+([\d.]+)\s*([KMGT]?i?B/s)', status_line, re.IGNORECASE)
                            if speed_match:
                                speed_value = speed_match.group(1)
                                speed_unit = speed_match.group(2)
                                speed_str = f" - {speed_value}{speed_unit}"
                            
                            # ETA extrahieren
                            eta_match = re.search(r'ETA\s+(\d+:\d+)', status_line)
                            if eta_match:
                                eta_str = f" - ETA: {eta_match.group(1)}"
                        
                        # Status-Text mit Geschwindigkeit
                        status_text = f"Download läuft... {total_progress:.1f}% ({i}/{len(episodes)}){speed_str}{eta_str}"
                        self.video_status_var.set(status_text)
                        self.root.update_idletasks()
                    except:
                        pass
                
                # Hole Video-Info für diese Episode
                episode_info = self.video_downloader.get_video_info(url)
                
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
                        output_dir=self.video_download_path,
                        quality=self.video_quality_var.get(),
                        output_format=self.video_format_var.get(),
                        download_playlist=False,
                        progress_callback=progress_callback,
                        video_info=episode_info,
                        is_series=True,
                        series_name=series_name,
                        season_number=season_number,
                        download_subtitles=self.video_subtitle_var.get(),
                        subtitle_language=self.video_subtitle_lang_var.get(),
                        download_description=self.video_description_var.get(),
                        download_thumbnail=self.video_thumbnail_var.get(),
                        resume_download=self.video_resume_var.get(),
                        speed_limit=speed_limit,
                        embed_metadata=True,  # Immer aktiviert
                        gui_instance=self  # Übergebe GUI-Instanz direkt
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
                
                if success:
                    if file_path:
                        self.video_log(f"  ✓ Erfolgreich: {file_path.name}")
                        success_count += 1
                    else:
                        self.video_log(f"  ⚠ Download scheint erfolgreich, aber Datei nicht gefunden")
                        success_count += 1
                else:
                    self.video_log(f"  ✗ Fehlgeschlagen: {error}")
                    failed_count += 1
                
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
                
                messagebox.showinfo(
                    "Erfolg",
                    f"Download abgeschlossen!\n\n"
                    f"Erfolgreich: {success_count}/{len(episodes)} Folgen\n"
                    f"Fehlgeschlagen: {failed_count} Folgen"
                )
            
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
            
            # Prüfe ob Queue-Downloads vorhanden sind und starte automatisch
            self._process_download_queue()
    
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
        
    
    def load_urls_from_file(self):
        """Lädt URLs aus einer Textdatei"""
        filename = filedialog.askopenfilename(
            title="URLs aus Datei laden",
            filetypes=[("Textdateien", "*.txt"), ("Alle Dateien", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    urls = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
                if urls:
                    if messagebox.askyesno("URLs geladen", f"{len(urls)} URLs gefunden.\n\nSoll die Queue mit diesen URLs gefüllt werden?"):
                        self.video_download_queue.extend(urls)
                        self.video_log(f"✓ {len(urls)} URLs zur Queue hinzugefügt")
                        messagebox.showinfo("Erfolg", f"{len(urls)} URLs zur Download-Queue hinzugefügt!")
                else:
                    messagebox.showwarning("Warnung", "Keine URLs in der Datei gefunden.")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Laden der Datei: {e}")
    
    def _add_to_download_queue(self, url: str, episode_info: Optional[Dict] = None, show_dialog: bool = True):
        """Fügt einen Download zur Queue hinzu
        
        Args:
            url: Die Video-URL
            episode_info: Optional: Episode-Informationen für Serien
            show_dialog: Wenn True, wird ein Dialog-Fenster angezeigt (Standard: True)
        """
        from datetime import datetime
        
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
            'status': 'Wartend'
        }
        
        # Füge Episode-Informationen hinzu falls vorhanden
        if episode_info:
            queue_item['episode_info'] = episode_info
            queue_item['is_series'] = True
            queue_item['series_name'] = episode_info.get('series_name', '')
            queue_item['season_number'] = episode_info.get('season_number')
            queue_item['episode_number'] = episode_info.get('episode_number')
            queue_item['episode_title'] = episode_info.get('title', '')
        
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
            log_text = f"📋 Zur Queue hinzugefügt: {url[:60]}..."
        
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
    
    def _update_queue_status(self):
        """Aktualisiert die Queue-Status-Anzeige"""
        if hasattr(self, 'video_queue_status_label'):
            queue_count = len(self.video_download_queue)
            if queue_count > 0:
                self.video_queue_status_label.config(text=f"📋 Queue: {queue_count} Download{'s' if queue_count != 1 else ''} wartend")
            else:
                self.video_queue_status_label.config(text="📋 Queue: 0 Downloads")
    
    def _process_download_queue(self):
        """Startet automatisch den nächsten Download aus der Queue"""
        # Prüfe ob bereits ein Download läuft (aber ignoriere video_download_queue_processing, 
        # da das nur ein Flag ist, dass die Queue aktiv ist)
        if (self.video_download_process is not None or 
            (hasattr(self, 'video_download_episodes_total') and self.video_download_episodes_total > 0)):
            return  # Download läuft noch
        
        # Prüfe ob Queue-Einträge vorhanden sind
        if not self.video_download_queue:
            if hasattr(self, 'video_download_queue_processing'):
                self.video_download_queue_processing = False
            return  # Queue ist leer
        
        # Starte nächsten Download aus Queue
        queue_item = self.video_download_queue.pop(0)
        url = queue_item.get('url', queue_item) if isinstance(queue_item, dict) else queue_item
        
        self.video_log(f"\n{'='*60}")
        self.video_log(f"📋 Starte nächsten Download aus Queue")
        self.video_log(f"URL: {url}")
        self.video_log(f"Verbleibend in Queue: {len(self.video_download_queue)}")
        self.video_log(f"{'='*60}\n")
        
        # Setze Optionen aus Queue-Eintrag
        if isinstance(queue_item, dict):
            self.video_quality_var.set(queue_item.get('quality', 'best'))
            self.video_format_var.set(queue_item.get('format', 'mp4'))
            self.video_subtitle_var.set(queue_item.get('subtitle', False))
            self.video_subtitle_lang_var.set(queue_item.get('subtitle_lang', 'de'))
            self.video_description_var.set(queue_item.get('description', False))
            self.video_thumbnail_var.set(queue_item.get('thumbnail', False))
            self.video_resume_var.set(queue_item.get('resume', True))
        
        # Setze URL und starte Download
        self.video_url_var.set(url)
        # Rufe start_video_download rekursiv auf, aber ohne Queue-Prüfung
        self._start_video_download_direct(url)
    
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
    
    def show_download_queue(self):
        """Zeigt die Download-Queue an"""
        queue_window = tk.Toplevel(self.root)
        queue_window.title("Download-Queue")
        queue_window.geometry("700x450")
        queue_window.transient(self.root)
        
        frame = ttk.Frame(queue_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header-Zeile mit Label und Buttons
        header_frame = ttk.Frame(frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Download-Queue:", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        
        # Button-Frame rechts
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=tk.RIGHT)
        
        # Treeview für bessere Anzeige
        columns = ("Status", "URL", "Qualität", "Format", "Hinzugefügt")
        queue_tree = ttk.Treeview(frame, columns=columns, show="headings", height=15)
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
        
        # Buttons in Header-Frame einfügen (button_frame wurde bereits oben erstellt)
        ttk.Button(button_frame, text="▶ Starten", command=start_queue).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↑", command=move_up, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↓", command=move_down, width=3).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Entfernen", command=remove_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Löschen", command=clear_queue).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="🔄", command=refresh_queue, width=3).pack(side=tk.LEFT, padx=2)
    
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
        
        # Starte Queue-Verarbeitung
        self.video_download_queue_processing = True
        self.video_log(f"\n{'='*60}")
        self.video_log(f"📋 Starte Queue-Download: {len(self.video_download_queue)} Downloads")
        self.video_log(f"{'='*60}\n")
        self._process_download_queue()
    
    def show_scheduled_downloads(self):
        """Zeigt Dialog für geplante Downloads"""
        schedule_window = tk.Toplevel(self.root)
        schedule_window.title("Geplante Downloads")
        schedule_window.geometry("700x500")
        schedule_window.transient(self.root)
        
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
            add_window.geometry("500x300")
            add_window.transient(schedule_window)
            
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
        """Zeigt Download-Historie"""
        history_window = tk.Toplevel(self.root)
        history_window.title("Download-Historie")
        history_window.geometry("800x500")
        history_window.transient(self.root)
        
        frame = ttk.Frame(history_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Download-Historie", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Treeview
        columns = ("Zeitpunkt", "URL", "Status", "Datei")
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=20)
        tree.heading("Zeitpunkt", text="Zeitpunkt")
        tree.heading("URL", text="URL")
        tree.heading("Status", text="Status")
        tree.heading("Datei", text="Datei")
        tree.column("Zeitpunkt", width=150)
        tree.column("URL", width=300)
        tree.column("Status", width=100)
        tree.column("Datei", width=200)
        
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Lade Historie
        for entry in sorted(self.video_download_history, key=lambda x: x.get('timestamp', ''), reverse=True):
            tree.insert("", tk.END, values=(
                entry.get('timestamp', 'Unbekannt'),
                entry.get('url', '')[:50] + "..." if len(entry.get('url', '')) > 50 else entry.get('url', ''),
                entry.get('status', 'Unbekannt'),
                entry.get('filename', 'N/A')
            ))
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        def clear_history():
            if messagebox.askyesno("Bestätigen", "Historie wirklich löschen?"):
                self.video_download_history.clear()
                self._save_video_data()
                tree.delete(*tree.get_children())
        
        ttk.Button(button_frame, text="Historie löschen", command=clear_history).pack(side=tk.LEFT, padx=5)
    
    def show_favorites(self):
        """Zeigt Favoriten-Verwaltung"""
        fav_window = tk.Toplevel(self.root)
        fav_window.title("Favoriten")
        fav_window.geometry("600x400")
        fav_window.transient(self.root)
        
        frame = ttk.Frame(fav_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Favoriten", font=("Arial", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        listbox = tk.Listbox(frame, height=15)
        listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        for fav in self.video_favorites:
            listbox.insert(tk.END, fav.get('name', fav.get('url', 'Unbekannt')))
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X)
        
        def add_favorite():
            add_window = tk.Toplevel(fav_window)
            add_window.title("Favorit hinzufügen")
            add_window.geometry("400x200")
            add_window.transient(fav_window)
            
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
        search_window.geometry("900x700")
        search_window.transient(self.root)
        
        main_frame = ttk.Frame(search_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Suchfeld
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(search_frame, text="Suche:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=50, font=("Arial", 10))
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        search_button = ttk.Button(search_frame, text="🔍 Suchen", command=lambda: self._perform_search(search_var.get(), results_frame, status_label))
        search_button.pack(side=tk.LEFT, padx=5)
        
        # Enter-Taste für Suche
        search_entry.bind('<Return>', lambda e: self._perform_search(search_var.get(), results_frame, status_label))
        
        # Status-Label
        status_label = ttk.Label(main_frame, text="Geben Sie einen Suchbegriff ein und klicken Sie auf 'Suchen'", foreground='gray')
        status_label.pack(pady=5)
        
        # Ergebnisse-Frame mit Scrollbar
        results_container = ttk.Frame(main_frame)
        results_container.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(results_container)
        scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=canvas.yview)
        results_frame = ttk.Frame(canvas)
        
        results_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=results_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
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
    
    def _perform_search(self, query: str, results_frame: ttk.Frame, status_label: ttk.Label):
        """Führt die Suche aus - durchsucht alle Standard-Mediatheken"""
        if not query.strip():
            messagebox.showwarning("Warnung", "Bitte geben Sie einen Suchbegriff ein.")
            return
        
        # Lösche alte Ergebnisse
        for widget in results_frame.winfo_children():
            widget.destroy()
        
        status_label.config(text=f"Suche nach: {query}... (durchsuche alle Mediatheken)", foreground='blue')
        results_frame.update()
        
        # Suche in separatem Thread
        def search_thread():
            try:
                import subprocess
                all_results = []
                
                # 1. YouTube-Suche
                status_label.config(text=f"Suche auf YouTube...", foreground='blue')
                self.root.update()
                
                search_url = f"ytsearch20:{query}"  # Erste 20 Ergebnisse
                from yt_dlp_helper import get_ytdlp_command
                cmd = get_ytdlp_command() + [
                    '--dump-json',
                    '--flat-playlist',
                    '--no-warnings',
                    search_url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line.strip():
                            try:
                                info = json.loads(line)
                                url = info.get('url', info.get('webpage_url', ''))
                                if not url:
                                    continue
                                
                                sender = self._detect_sender_from_url(url)
                                uploader = info.get('uploader', info.get('channel', 'Unbekannt'))
                                
                                # Für YouTube: Verwende Uploader als Sender-Name
                                if sender == 'youtube':
                                    sender_name = f"YouTube ({uploader})"
                                else:
                                    sender_name = sender.upper()
                                
                                all_results.append({
                                    'title': info.get('title', info.get('id', 'Unbekannt')),
                                    'url': url,
                                    'duration': info.get('duration', 0),
                                    'uploader': uploader,
                                    'view_count': info.get('view_count', 0),
                                    'is_playlist': info.get('_type') == 'playlist' or 'playlist' in str(info.get('_type', '')),
                                    'sender': sender,
                                    'sender_name': sender_name
                                })
                            except json.JSONDecodeError as e:
                                continue
                                # Debug: Zeige Fehler bei JSON-Parsing
                                # print(f"JSON-Fehler: {e}, Zeile: {line[:100]}")
                
                # 2. Suche auf ARD Mediathek (falls möglich)
                # ARD Mediathek hat eine Such-API, aber yt-dlp unterstützt das nicht direkt
                # Wir könnten versuchen, direkt URLs zu konstruieren, aber das ist komplex
                # Für jetzt fokussieren wir uns auf YouTube, da dort die meisten Inhalte verfügbar sind
                
                # KEINE Gruppierung - zeige jedes Ergebnis einzeln als Liste
                # Debug: Zeige Anzahl der Ergebnisse
                print(f"[DEBUG] {len(all_results)} Ergebnisse gefunden - zeige alle einzeln")
                
                # Zeige Ergebnisse im UI-Thread
                self.root.after(0, lambda results=all_results, rf=results_frame, sl=status_label, q=query: self._display_search_results_list(results, rf, sl, q))
                
            except Exception as e:
                import traceback
                error_msg = f"Fehler: {str(e)}\n{traceback.format_exc()}"
                self.root.after(0, lambda: status_label.config(text=error_msg[:200], foreground='red'))
        
        thread = threading.Thread(target=search_thread, daemon=True)
        thread.start()
    
    def _display_search_results_list(self, results: List[Dict], results_frame: ttk.Frame, status_label: ttk.Label, query: str):
        """Zeigt Suchergebnisse als einfache Liste an - jedes Ergebnis einzeln"""
        # Lösche alte Ergebnisse
        for widget in results_frame.winfo_children():
            widget.destroy()
        
        if not results:
            status_label.config(text=f"Keine Ergebnisse für '{query}' gefunden", foreground='orange')
            return
        
        status_label.config(text=f"{len(results)} Ergebnis(se) gefunden für '{query}'", foreground='green')
        
        # Debug: Zeige Anzahl der Ergebnisse
        print(f"[DEBUG] Zeige {len(results)} Ergebnisse als Liste")
        
        # Zeige jedes Ergebnis einzeln
        for idx, result in enumerate(results):
            # Ergebnis-Frame (ein Frame pro Ergebnis)
            result_frame = ttk.LabelFrame(results_frame, padding="10")
            result_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Titel
            title = result.get('title', 'Unbekannter Titel')
            title_label = ttk.Label(
                result_frame,
                text=title,
                font=("Arial", 11, "bold"),
                wraplength=800
            )
            title_label.pack(anchor=tk.W, pady=(0, 5))
            
            # Info-Zeile
            info_parts = []
            if result.get('uploader'):
                info_parts.append(f"Kanal: {result['uploader']}")
            if result.get('duration'):
                minutes = result['duration'] // 60
                seconds = result['duration'] % 60
                info_parts.append(f"Dauer: {minutes}:{seconds:02d}")
            if result.get('view_count'):
                views = result['view_count']
                if views > 1000000:
                    info_parts.append(f"Aufrufe: {views/1000000:.1f}M")
                elif views > 1000:
                    info_parts.append(f"Aufrufe: {views/1000:.1f}K")
                else:
                    info_parts.append(f"Aufrufe: {views}")
            
            if info_parts:
                info_label = ttk.Label(result_frame, text=" | ".join(info_parts), foreground='gray')
                info_label.pack(anchor=tk.W, pady=(0, 5))
            
            # Sender-Info
            sender = result.get('sender', 'unknown')
            sender_logo = self._get_sender_logo(sender)
            sender_name = result.get('sender_name', sender.upper())
            
            sender_label = ttk.Label(
                result_frame,
                text=f"{sender_logo} {sender_name}",
                font=("Arial", 9),
                foreground='blue'
            )
            sender_label.pack(anchor=tk.W, pady=(0, 10))
            
            # Button-Frame
            button_frame = ttk.Frame(result_frame)
            button_frame.pack(fill=tk.X, pady=(0, 5))
            
            # WICHTIG: Closure-Variablen korrekt binden
            result_url = result['url']
            result_title = title
            
            # Download-Button
            download_btn = ttk.Button(
                button_frame,
                text="⬇️ Sofort herunterladen",
                command=lambda u=result_url, t=result_title: self._download_from_search(u, t, direct=True)
            )
            download_btn.pack(side=tk.LEFT, padx=5, pady=2)
            
            # Queue-Button
            queue_btn = ttk.Button(
                button_frame,
                text="➕ Zur Warteschlange",
                command=lambda u=result_url, t=result_title: self._download_from_search(u, t, direct=False)
            )
            queue_btn.pack(side=tk.LEFT, padx=5, pady=2)
            
            # Staffelauswahl-Button (wenn Playlist)
            if result.get('is_playlist'):
                season_btn = ttk.Button(
                    button_frame,
                    text="📺 Staffeln auswählen",
                    command=lambda u=result_url, t=result_title: self._select_seasons_from_search(u, t)
                )
                season_btn.pack(side=tk.LEFT, padx=5, pady=2)
            
            # Separator (außer beim letzten Element)
            if idx < len(results) - 1:
                separator = ttk.Separator(result_frame, orient='horizontal')
                separator.pack(fill=tk.X, pady=5)
        
        # Aktualisiere Scroll-Region nach dem Hinzufügen aller Ergebnisse
        results_frame.update_idletasks()
        # Finde das Canvas-Element (parent von results_frame)
        canvas = results_frame.master
        if isinstance(canvas, tk.Canvas):
            canvas.configure(scrollregion=canvas.bbox("all"))
    
    def _download_from_search(self, url: str, title: str, direct: bool = True):
        """Startet Download von Suchergebnis"""
        if direct:
            # Setze URL und starte Download
            self.video_url_var.set(url)
            self.start_video_download()
            messagebox.showinfo("Download gestartet", f"Download von '{title}' wurde gestartet.")
        else:
            # Zur Queue hinzufügen
            self.video_download_queue.append(url)
            messagebox.showinfo("Zur Queue hinzugefügt", f"'{title}' wurde zur Download-Queue hinzugefügt.")
    
    def _select_seasons_from_search(self, url: str, title: str):
        """Zeigt Staffelauswahl für Serie aus Suchergebnissen"""
        # Initialisiere Downloader falls noch nicht geschehen
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
        
        # Verwende die vorhandene Staffelauswahl-Funktion
        self.video_url_var.set(url)
        # Prüfe ob es eine Serie ist und zeige Auswahl
        if self.video_downloader.is_series_or_season(url):
            self.start_video_download()  # Dies wird automatisch die Staffelauswahl zeigen
        else:
            messagebox.showinfo("Info", "Diese URL scheint keine Serie zu sein. Verwenden Sie 'Sofort herunterladen' oder 'Zur Warteschlange'.")
    
    def show_statistics(self):
        """Zeigt Download-Statistiken"""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Download-Statistiken")
        stats_window.geometry("500x400")
        stats_window.transient(self.root)
        
        frame = ttk.Frame(stats_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Download-Statistiken", font=("Arial", 14, "bold")).pack(pady=(0, 20))
        
        stats_text = f"""
Gesamt-Downloads: {self.video_statistics.get('total_downloads', 0)}
Erfolgreich: {self.video_statistics.get('successful_downloads', 0)}
Fehlgeschlagen: {self.video_statistics.get('failed_downloads', 0)}

Gesamt-Größe: {self._format_size(self.video_statistics.get('total_size', 0))}

Letzter Download: {self.video_statistics.get('last_download', 'Nie')}

Geplante Downloads: {len(self.video_scheduled_downloads)}
Favoriten: {len(self.video_favorites)}
Historie-Einträge: {len(self.video_download_history)}
        """
        
        ttk.Label(frame, text=stats_text.strip(), font=("Arial", 10), justify=tk.LEFT).pack(anchor=tk.W)
        
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        def reset_stats():
            if messagebox.askyesno("Bestätigen", "Statistiken wirklich zurücksetzen?"):
                self.video_statistics = {
                    'total_downloads': 0,
                    'total_size': 0,
                    'successful_downloads': 0,
                    'failed_downloads': 0,
                    'last_download': None
                }
                self._save_video_data()
                stats_window.destroy()
                self.show_statistics()
        
        ttk.Button(button_frame, text="Statistiken zurücksetzen", command=reset_stats).pack()
    
    def _ensure_dependencies_background(self):
        """Prüft und installiert Abhängigkeiten im Hintergrund"""
        def check_thread():
            try:
                # Prüfe ob wir gerade nach einem Neustart sind (verhindere Endlosschleife)
                restart_flag_file = Path(tempfile.gettempdir()) / "universal_downloader_restarting.flag"
                if restart_flag_file.exists():
                    # Wir wurden gerade neu gestartet - überspringe Abhängigkeits-Installation
                    self._write_to_log_file("[DEBUG] Restart-Flag gefunden - überspringe Abhängigkeits-Installation", "DEBUG")
                    return
                
                # Prüfe ob wir über den Launcher gestartet wurden
                # Wenn ja, wurden Abhängigkeiten bereits installiert - überspringe Popup
                started_by_launcher = os.environ.get('UNIVERSAL_DOWNLOADER_STARTED_BY_LAUNCHER', '0') == '1'
                if started_by_launcher:
                    self._write_to_log_file("[DEBUG] Gestartet über Launcher - Abhängigkeiten sollten bereits installiert sein", "DEBUG")
                
                from auto_install_dependencies import check_ffmpeg
                
                # Schnelle Prüfung ob Installation nötig ist (nur ffmpeg, yt-dlp wird automatisch installiert)
                ffmpeg_ok, _ = check_ffmpeg()
                
                self._write_to_log_file(f"[DEBUG] Abhängigkeits-Prüfung: ffmpeg={ffmpeg_ok}", "DEBUG")
                
                # Installiere nur ffmpeg (yt-dlp wird automatisch über requirements.txt installiert)
                from auto_install_dependencies import ensure_dependencies
                
                # Setze Progress-Callback für Abhängigkeits-Installation
                def update_progress(message):
                    if hasattr(self, '_dep_status_text') and self._dep_status_text.winfo_exists():
                        self.root.after(0, lambda: self._add_status_message(message))
                
                # Setze Callback für ensure_dependencies
                ensure_dependencies._progress_callback = update_progress
                
                # Prüfe ob requirements.txt installiert werden muss
                from auto_install_dependencies import check_requirements_txt
                requirements_ok, missing_packages = check_requirements_txt()
                
                # Zeige Installations-Dialog nur wenn:
                # 1. NICHT über Launcher gestartet wurde UND (ffmpeg fehlt ODER requirements.txt nicht vollständig installiert ist)
                # 2. ODER wenn über Launcher gestartet, aber trotzdem etwas fehlt (z.B. ffmpeg wenn winget nicht verfügbar war)
                if not started_by_launcher and (not ffmpeg_ok or not requirements_ok):
                    # Normale Installation - zeige Dialog
                    self.root.after(0, self._show_dependency_installation_dialog)
                elif started_by_launcher and not ffmpeg_ok:
                    # Über Launcher gestartet, aber ffmpeg fehlt (z.B. winget nicht verfügbar)
                    # Zeige Dialog nur für ffmpeg, nicht für requirements.txt (die sollten bereits installiert sein)
                    self._write_to_log_file("[DEBUG] Launcher-Start erkannt, aber ffmpeg fehlt - zeige Dialog nur für ffmpeg", "DEBUG")
                    self.root.after(0, self._show_dependency_installation_dialog)
                elif started_by_launcher and not requirements_ok:
                    # Über Launcher gestartet, aber requirements.txt fehlt trotzdem (unwahrscheinlich, aber möglich)
                    # Zeige Dialog nur für requirements.txt
                    self._write_to_log_file("[WARNING] Launcher-Start erkannt, aber requirements.txt fehlt trotzdem", "WARNING")
                    self.root.after(0, self._show_dependency_installation_dialog)
                elif started_by_launcher:
                    # Alles OK - keine Installation nötig
                    self._write_to_log_file("[DEBUG] Launcher-Start erkannt - überspringe Abhängigkeits-Dialog (alles sollte bereits installiert sein)", "DEBUG")
                
                try:
                    # ensure_dependencies installiert requirements.txt und ffmpeg automatisch
                    ytdlp_ok, ffmpeg_ok, messages, has_updates = ensure_dependencies()
                    
                    # Zeige alle Meldungen (inkl. requirements.txt)
                    filtered_messages = messages
                finally:
                    # Entferne Callback
                    if hasattr(ensure_dependencies, '_progress_callback'):
                        delattr(ensure_dependencies, '_progress_callback')
                
                self._write_to_log_file(f"[DEBUG] Abhängigkeits-Installation abgeschlossen: ffmpeg={ffmpeg_ok}, updates={has_updates}", "DEBUG")
                
                # Aktualisiere Dialog mit Ergebnissen (nur ffmpeg)
                # Zeige Dialog immer, wenn der Dialog geöffnet wurde (d.h. wenn ffmpeg fehlte oder installiert wurde)
                # Der Dialog wird automatisch aktualisiert, wenn er geöffnet ist
                if not ffmpeg_ok or has_updates:
                    self.root.after(0, lambda: self._update_dependency_dialog(True, ffmpeg_ok, filtered_messages, has_updates))
                elif ffmpeg_ok:
                    # Auch wenn ffmpeg jetzt OK ist, aber der Dialog geöffnet wurde, aktualisiere ihn
                    # (z.B. wenn es bereits vorhanden war)
                    self.root.after(0, lambda: self._update_dependency_dialog(True, ffmpeg_ok, filtered_messages, False))
                
            except Exception as e:
                # Zeige Fehler im Dialog
                self._write_to_log_file(f"[ERROR] Fehler bei Abhängigkeits-Installation: {e}", "ERROR")
                import traceback
                self._write_to_log_file(f"[ERROR] Traceback: {traceback.format_exc()}", "ERROR")
                self.root.after(0, lambda: self._update_dependency_dialog(False, False, [f"[ERROR] Fehler: {e}"]))
        
        threading.Thread(target=check_thread, daemon=True).start()
    
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
        update_window.geometry("500x300")
        update_window.transient(self.root)
        update_window.grab_set()
        
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
        response = messagebox.askyesno(
            "Update verfügbar",
            f"Eine neue Version ({update_info['version']}) ist verfügbar!\n\n"
            f"Möchten Sie das Update jetzt herunterladen?",
            icon='question'
        )
        if response:
            self._download_update(update_info)
    
    def _download_update(self, update_info, parent_window=None):
        """Lädt ein Update herunter und installiert es automatisch"""
        if not update_info.get('download_url'):
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
        download_window.title("Update herunterladen")
        download_window.geometry("400x150")
        download_window.transient(parent_window or self.root)
        
        frame = ttk.Frame(download_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Lade Update herunter...").pack(pady=10)
        
        progress = ttk.Progressbar(frame, mode='indeterminate')
        progress.pack(fill=tk.X, pady=10)
        progress.start()
        
        status_label = ttk.Label(frame, text="")
        status_label.pack()
        
        def download_thread():
            try:
                checker = UpdateChecker()
                success = checker.download_update(update_info['download_url'], Path(save_path))
                
                def update_ui():
                    progress.stop()
                    if success:
                        status_label.config(text="✓ Download erfolgreich! Installiere Update...")
                        self.root.update()
                        
                        # Installiere Update (ersetze alte .exe)
                        install_success = self._install_update(Path(save_path), update_info['version'])
                        
                        if install_success:
                            status_label.config(text="✓ Update installiert! Starte Programm neu...")
                            self.root.update()
                            
                            # Starte Programm neu
                            self._restart_application(Path(save_path))
                        else:
                            status_label.config(text="⚠ Installation fehlgeschlagen")
                            messagebox.showwarning(
                                "Warnung",
                                f"Update wurde heruntergeladen, aber die Installation ist fehlgeschlagen.\n\n"
                                f"Bitte installieren Sie das Update manuell:\n{save_path}"
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
                    progress.stop()
                    status_label.config(text="✗ Fehler")
                    messagebox.showerror("Fehler", f"Fehler beim Download: {str(e)}")
                self.root.after(0, show_error)
        
        threading.Thread(target=download_thread, daemon=True).start()
    
    def _install_update(self, update_file: Path, new_version: str) -> bool:
        """
        Installiert das Update, indem die alte .exe ersetzt wird
        
        Args:
            update_file: Pfad zur neuen .exe/.deb Datei
            new_version: Neue Versionsnummer
            
        Returns:
            True bei Erfolg, False sonst
        """
        try:
            if sys.platform == "win32":
                # Windows: Ersetze die aktuelle .exe
                current_exe = Path(sys.executable)
                
                # Prüfe ob wir in einer .exe sind
                if not getattr(sys, 'frozen', False):
                    # Normale Python-Umgebung - kann nicht automatisch installieren
                    return False
                
                # Erstelle Backup der alten .exe
                backup_path = current_exe.parent / f"{current_exe.stem}_backup_{get_version()}.exe"
                if current_exe.exists():
                    shutil.copy2(current_exe, backup_path)
                
                # Ersetze die .exe
                shutil.copy2(update_file, current_exe)
                
                # Lösche Update-Datei aus Temp
                update_file.unlink(missing_ok=True)
                
                return True
            elif sys.platform == "linux":
                # Linux: Installiere .deb Paket
                result = subprocess.run(
                    ['sudo', 'dpkg', '-i', str(update_file)],
                    capture_output=True,
                    text=True
                )
                return result.returncode == 0
            else:
                # macOS: Kann nicht automatisch installieren
                return False
                
        except Exception as e:
            print(f"[ERROR] Fehler bei Update-Installation: {e}")
            return False
    
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
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
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
                            creationflags=subprocess.CREATE_NEW_CONSOLE,
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
        about_window.geometry("500x400")
        about_window.transient(self.root)
        
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
    
    def _update_statistics(self, success, file_path, url):
        """Aktualisiert Download-Statistiken"""
        self.video_statistics['total_downloads'] += 1
        if success:
            self.video_statistics['successful_downloads'] += 1
            if file_path and file_path.exists():
                try:
                    size = file_path.stat().st_size
                    self.video_statistics['total_size'] += size
                except:
                    pass
        else:
            self.video_statistics['failed_downloads'] += 1
        self.video_statistics['last_download'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            'auto_open_folder': False,
            'max_concurrent_downloads': 3,
            'show_notifications': True,
            'language': 'de',
            'log_cleanup_enabled': False,
            'log_cleanup_days': 30,
            'log_cleanup_on_exit': False,
            'auto_check_updates': True,  # Automatische Update-Prüfung beim Start
            'log_level': 'debug',  # Log-Level: 'normal' oder 'debug'
            'video_accounts': []  # Liste von Account-Dictionaries
        }
        
        try:
            config_file = self.base_download_path / "settings.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # Merge mit Defaults (falls neue Einstellungen hinzugefügt wurden)
                    default_settings.update(saved_settings)
                    # Stelle sicher, dass video_accounts existiert
                    if 'video_accounts' not in default_settings:
                        default_settings['video_accounts'] = []
                    return default_settings
        except Exception as e:
            pass
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
    
    def show_settings_dialog(self):
        """Zeigt das Einstellungsfenster"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("⚙️ Einstellungen")
        settings_window.geometry("600x700")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # Hauptframe mit Scrollbar
        main_frame = ttk.Frame(settings_window, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Standard-Download-Pfade
        paths_frame = ttk.LabelFrame(scrollable_frame, text="📁 Standard-Download-Pfade", padding="10")
        paths_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Deezer-Pfad
        ttk.Label(paths_frame, text="Deezer:").grid(row=0, column=0, sticky=tk.W, pady=5)
        deezer_path_var = tk.StringVar(value=self.settings.get('default_deezer_path', ''))
        deezer_entry = ttk.Entry(paths_frame, textvariable=deezer_path_var, width=50)
        deezer_entry.grid(row=0, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(deezer_path_var)).grid(row=0, column=2, padx=5)
        
        # Audible-Pfad
        ttk.Label(paths_frame, text="Audible:").grid(row=1, column=0, sticky=tk.W, pady=5)
        audible_path_var = tk.StringVar(value=self.settings.get('default_audible_path', ''))
        audible_entry = ttk.Entry(paths_frame, textvariable=audible_path_var, width=50)
        audible_entry.grid(row=1, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(audible_path_var)).grid(row=1, column=2, padx=5)
        
        # Video-Pfad
        ttk.Label(paths_frame, text="Video:").grid(row=2, column=0, sticky=tk.W, pady=5)
        video_path_var = tk.StringVar(value=self.settings.get('default_video_path', ''))
        video_entry = ttk.Entry(paths_frame, textvariable=video_path_var, width=50)
        video_entry.grid(row=2, column=1, padx=5, pady=5, sticky=(tk.W, tk.E))
        ttk.Button(paths_frame, text="📂", command=lambda: self._browse_folder(video_path_var)).grid(row=2, column=2, padx=5)
        
        paths_frame.columnconfigure(1, weight=1)
        
        # Video-Einstellungen
        video_frame = ttk.LabelFrame(scrollable_frame, text="🎬 Video-Einstellungen", padding="10")
        video_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Standard-Qualität
        ttk.Label(video_frame, text="Standard-Qualität:").grid(row=0, column=0, sticky=tk.W, pady=5)
        quality_var = tk.StringVar(value=self.settings.get('default_video_quality', 'best'))
        quality_combo = ttk.Combobox(video_frame, textvariable=quality_var, values=['best', '1080p', '720p', 'niedrigste'], state='readonly', width=15)
        quality_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Standard-Format
        ttk.Label(video_frame, text="Standard-Format:").grid(row=1, column=0, sticky=tk.W, pady=5)
        format_var = tk.StringVar(value=self.settings.get('default_video_format', 'mp4'))
        format_combo = ttk.Combobox(video_frame, textvariable=format_var, values=['mp4', 'mp3', 'webm', 'mkv', 'avi'], state='readonly', width=15)
        format_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Geschwindigkeits-Limit
        ttk.Label(video_frame, text="Geschwindigkeits-Limit:").grid(row=2, column=0, sticky=tk.W, pady=5)
        speed_limit_frame = ttk.Frame(video_frame)
        speed_limit_frame.grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        speed_limit_enabled_var = tk.BooleanVar(value=self.settings.get('speed_limit_enabled', False))
        speed_limit_check = ttk.Checkbutton(speed_limit_frame, text="Aktivieren", variable=speed_limit_enabled_var)
        speed_limit_check.pack(side=tk.LEFT, padx=(0, 5))
        
        speed_limit_value_var = tk.StringVar(value=str(self.settings.get('speed_limit_value', '5')))
        speed_limit_entry = ttk.Entry(speed_limit_frame, textvariable=speed_limit_value_var, width=8)
        speed_limit_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(speed_limit_frame, text="MB/s").pack(side=tk.LEFT)
        
        # Untertitel-Einstellungen
        subtitle_settings_frame = ttk.LabelFrame(scrollable_frame, text="📝 Untertitel-Einstellungen", padding="10")
        subtitle_settings_frame.pack(fill=tk.X, pady=5, padx=5)
        
        subtitle_enabled_by_default_var = tk.BooleanVar(value=self.settings.get('subtitle_enabled_by_default', False))
        ttk.Checkbutton(subtitle_settings_frame, text="Untertitel standardmäßig aktivieren", variable=subtitle_enabled_by_default_var).pack(anchor=tk.W, pady=5)
        
        ttk.Label(subtitle_settings_frame, text="Standard-Untertitel-Sprache:").pack(anchor=tk.W, pady=(10, 5))
        subtitle_default_lang_var = tk.StringVar(value=self.settings.get('subtitle_default_lang', 'de'))
        subtitle_default_lang_combo = ttk.Combobox(subtitle_settings_frame, textvariable=subtitle_default_lang_var, values=['de', 'en', 'all'], state='readonly', width=15)
        subtitle_default_lang_combo.pack(anchor=tk.W, pady=5)
        
        # Allgemeine Einstellungen
        general_frame = ttk.LabelFrame(scrollable_frame, text="⚙️ Allgemeine Einstellungen", padding="10")
        general_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Versionsinformationen
        version_frame = ttk.Frame(general_frame)
        version_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(version_frame, text="Version:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        version_text = get_version_string()
        ttk.Label(version_frame, text=version_text, font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Separator
        ttk.Separator(general_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Automatisch Ordner öffnen
        auto_open_var = tk.BooleanVar(value=self.settings.get('auto_open_folder', False))
        ttk.Checkbutton(general_frame, text="Ordner nach Download automatisch öffnen", variable=auto_open_var).pack(anchor=tk.W, pady=5)
        
        # Benachrichtigungen
        notifications_var = tk.BooleanVar(value=self.settings.get('show_notifications', True))
        ttk.Checkbutton(general_frame, text="Benachrichtigungen anzeigen", variable=notifications_var).pack(anchor=tk.W, pady=5)
        
        # Automatische Update-Prüfung
        auto_check_updates_var = tk.BooleanVar(value=self.settings.get('auto_check_updates', True))
        ttk.Checkbutton(general_frame, text="Automatisch auf Updates prüfen beim Start", variable=auto_check_updates_var).pack(anchor=tk.W, pady=5)
        
        # Log-Level-Einstellung
        log_level_frame = ttk.Frame(general_frame)
        log_level_frame.pack(fill=tk.X, pady=10)
        ttk.Label(log_level_frame, text="Log-Level:").pack(side=tk.LEFT, padx=(0, 10))
        log_level_var = tk.StringVar(value=self.settings.get('log_level', 'debug'))
        log_level_combo = ttk.Combobox(
            log_level_frame, 
            textvariable=log_level_var, 
            values=['normal', 'debug'], 
            state='readonly', 
            width=15
        )
        log_level_combo.pack(side=tk.LEFT, padx=5)
        
        # Info-Text für Log-Level
        log_level_info = ttk.Label(
            log_level_frame,
            text="Debug: Alle Logs (inkl. Debug-Informationen) | Normal: Nur wichtige Logs",
            foreground="gray",
            font=("Arial", 8)
        )
        log_level_info.pack(side=tk.LEFT, padx=10)
        
        # Maximale gleichzeitige Downloads
        ttk.Label(general_frame, text="Max. gleichzeitige Downloads:").pack(anchor=tk.W, pady=(10, 5))
        max_downloads_var = tk.StringVar(value=str(self.settings.get('max_concurrent_downloads', 3)))
        max_downloads_spin = ttk.Spinbox(general_frame, from_=1, to=10, textvariable=max_downloads_var, width=10)
        max_downloads_spin.pack(anchor=tk.W, pady=5)
        
        # Sprache
        ttk.Label(general_frame, text="Sprache:").pack(anchor=tk.W, pady=(10, 5))
        language_var = tk.StringVar(value=self.settings.get('language', 'de'))
        language_combo = ttk.Combobox(general_frame, textvariable=language_var, values=['de', 'en'], state='readonly', width=15)
        language_combo.pack(anchor=tk.W, pady=5)
        
        # Log-Verwaltung
        log_frame = ttk.LabelFrame(scrollable_frame, text="📋 Log-Verwaltung", padding="10")
        log_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Automatisches Aufräumen aktivieren
        log_cleanup_enabled_var = tk.BooleanVar(value=self.settings.get('log_cleanup_enabled', False))
        ttk.Checkbutton(log_frame, text="Automatisches Aufräumen alter Logs aktivieren", variable=log_cleanup_enabled_var).pack(anchor=tk.W, pady=5)
        
        # Tage bis zum Löschen
        log_days_frame = ttk.Frame(log_frame)
        log_days_frame.pack(anchor=tk.W, pady=5)
        ttk.Label(log_days_frame, text="Logs älter als:").pack(side=tk.LEFT, padx=(0, 5))
        log_cleanup_days_var = tk.StringVar(value=str(self.settings.get('log_cleanup_days', 30)))
        log_days_spin = ttk.Spinbox(log_days_frame, from_=1, to=365, textvariable=log_cleanup_days_var, width=10)
        log_days_spin.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(log_days_frame, text="Tage werden gelöscht").pack(side=tk.LEFT)
        
        # Beim Beenden löschen
        log_cleanup_on_exit_var = tk.BooleanVar(value=self.settings.get('log_cleanup_on_exit', False))
        ttk.Checkbutton(log_frame, text="Logs beim Beenden der Anwendung löschen", variable=log_cleanup_on_exit_var).pack(anchor=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(fill=tk.X, pady=20, padx=5)
        
        def save_settings():
            self.settings['default_deezer_path'] = deezer_path_var.get()
            self.settings['default_audible_path'] = audible_path_var.get()
            self.settings['default_video_path'] = video_path_var.get()
            self.settings['default_video_quality'] = quality_var.get()
            self.settings['default_video_format'] = format_var.get()
            self.settings['speed_limit_enabled'] = speed_limit_enabled_var.get()
            self.settings['speed_limit_value'] = speed_limit_value_var.get()
            self.settings['subtitle_enabled_by_default'] = subtitle_enabled_by_default_var.get()
            self.settings['subtitle_default_lang'] = subtitle_default_lang_var.get()
            self.settings['auto_open_folder'] = auto_open_var.get()
            self.settings['show_notifications'] = notifications_var.get()
            self.settings['max_concurrent_downloads'] = int(max_downloads_var.get())
            self.settings['language'] = language_var.get()
            self.settings['log_cleanup_enabled'] = log_cleanup_enabled_var.get()
            self.settings['log_cleanup_days'] = int(log_cleanup_days_var.get())
            self.settings['log_cleanup_on_exit'] = log_cleanup_on_exit_var.get()
            self.settings['auto_check_updates'] = auto_check_updates_var.get()
            self.settings['log_level'] = log_level_var.get()
            
            self._save_settings()
            
            # Führe Log-Aufräumen aus wenn aktiviert
            if log_cleanup_enabled_var.get():
                self._cleanup_old_logs()
            
            # Aktualisiere Download-Pfade
            self.download_path = Path(self.settings['default_deezer_path'])
            self.audible_download_path = Path(self.settings['default_audible_path'])
            self.video_download_path = Path(self.settings['default_video_path'])
            
            # Erstelle Ordner falls nicht vorhanden
            self.download_path.mkdir(parents=True, exist_ok=True)
            self.audible_download_path.mkdir(parents=True, exist_ok=True)
            self.video_download_path.mkdir(parents=True, exist_ok=True)
            
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
        
        ttk.Button(button_frame, text="💾 Speichern", command=save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Abbrechen", command=settings_window.destroy).pack(side=tk.LEFT, padx=5)
        
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
                'statistics': self.video_statistics
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
        quality_window.geometry("400x300")
        quality_window.transient(self.root)
        quality_window.grab_set()
        
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
    
    root = tk.Tk()
    
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
    
    # Setze Fenstertitel (wichtig für Windows Taskleiste)
    root.title("Universal Downloader")
    
    # Wichtig: update_idletasks() vor dem Erstellen der App, damit das Fenster initialisiert ist
    root.update_idletasks()
    
    app = DeezerDownloaderGUI(root)
    
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
        app._save_window_geometry()  # Speichere Fenstergröße
        app._close_log_file()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
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

