# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec-Datei für Universal Downloader

import os

block_cipher = None

# Icon-Daten hinzufügen falls vorhanden
datas_list = []
if os.path.exists('icon.ico'):
    datas_list.append(('icon.ico', '.'))
elif os.path.exists('icon.png'):
    datas_list.append(('icon.png', '.'))

a = Analysis(
    ['start.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'tkinter',
        'PIL',
        'mutagen',
        'deezer',
        'yt_dlp',
        'yt_dlp_helper',
        'auto_install_dependencies',
        'path_helper',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'bs4',  # Import-Name (Paket heißt beautifulsoup4)
        'beautifulsoup4',
        'selenium',
        'webdriver_manager',
        'audible',
        'browser_cookie3',
        'deezer_auth',
        'deezer_downloader',
        'spotify_downloader',
        'video_downloader',
        'audible_integration',
        'changelog',
        'updater',
        # Wie UniversalDownloader_mac.spec: oft erst per lazy import (Methode/Dialog)
        'audiobook_providers',
        'audiobook_search',
        'stream_automation',
        'audio_recorder',
        'audio_device_detector',
        'update_from_github',
        'create_shortcut',
        'setup_audio_recording',
        'series_watch',
        'series_watch_tray',
        'pystray',
        # URL-Liste aus Dateien (gui.py, optional dynamisch)
        'docx',
        'striprtf',
        'odf.opendocument',
        'odf.text',
        'odf.teletype',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='UniversalDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Kein Konsolen-Fenster
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else ('icon.png' if os.path.exists('icon.png') else None),
)
