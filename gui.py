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
    
    def start_music_download(self):
        """Startet den Musik-Download (Deezer oder Spotify)"""
        url = self.music_url_var.get().strip()
        
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
        # Prüfe ob bereits ein Download läuft
        if (self.video_download_process is not None or 
            self.video_download_queue_processing or
            (hasattr(self, 'video_download_episodes_total') and self.video_download_episodes_total > 0)):
            return  # Download läuft noch
        
        # Prüfe ob Queue-Einträge vorhanden sind
        if not self.video_download_queue:
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
