# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec für macOS: erzeugt .app-Bundle (für .dmg)
# Auf Apple Silicon: natives arm64 (UNIVERSAL_DOWNLOADER_TARGET_ARCH oder platform.machine())

import os
import platform

try:
    from version import __version__ as _APP_VERSION
except Exception:
    _APP_VERSION = "0.0.0"

_target_arch = os.environ.get("UNIVERSAL_DOWNLOADER_TARGET_ARCH") or platform.machine()
if _target_arch not in ("arm64", "x86_64"):
    _target_arch = None

block_cipher = None

datas_list = []
if os.path.exists('icon.png'):
    datas_list.append(('icon.png', '.'))
if os.path.exists('icon.icns'):
    datas_list.append(('icon.icns', '.'))

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
        'mac_platform',
        'series_watch',
        'series_watch_tray',
        'pystray',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'bs4',
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
        'audiobook_providers',
        'audiobook_search',
        'stream_automation',
        'audio_recorder',
        'audio_device_detector',
        'update_from_github',
        'create_shortcut',
        'setup_audio_recording',
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
    [],
    exclude_binaries=True,
    name='Universal Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=_target_arch,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Universal Downloader',
)

# macOS .app Bundle (für .dmg)
app = BUNDLE(
    coll,
    name='Universal Downloader.app',
    icon='icon.icns' if os.path.exists('icon.icns') else None,
    bundle_identifier='de.universaldownloader.app',
    info_plist={
        'CFBundleName': 'Universal Downloader',
        'CFBundleDisplayName': 'Universal Downloader',
        'CFBundleVersion': _APP_VERSION,
        'CFBundleShortVersionString': _APP_VERSION,
        'NSHighResolutionCapable': True,
        'LSMultipleInstancesProhibited': False,
        'LSRequiresNativeExecution': True if _target_arch == 'arm64' else False,
        'NSDownloadsFolderUsageDescription': (
            'Universal Downloader speichert Downloads, Einstellungen und Protokolle '
            'im Ordner Downloads/Universal Downloader.'
        ),
        'NSRemovableVolumesUsageDescription': (
            'Universal Downloader kann Dateien auf externe Laufwerke herunterladen.'
        ),
    },
)
