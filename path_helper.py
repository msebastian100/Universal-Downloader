#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hilfsfunktionen für Pfad-Erkennung
Erkennt den Standard-Download-Ordner des Systems
"""

import os
import sys
from pathlib import Path


def get_downloads_folder():
    """
    Gibt den Standard-Download-Ordner des Systems zurück
    
    Returns:
        Path: Pfad zum Download-Ordner
    """
    if sys.platform == "win32":
        # Windows: Verwende Windows Shell API um den echten Download-Ordner zu bekommen
        try:
            import ctypes
            from ctypes import wintypes
            
            # CSIDL_PERSONAL = 5 (My Documents)
            # CSIDL_MYPICTURES = 39 (My Pictures)
            # CSIDL_MYMUSIC = 13 (My Music)
            # CSIDL_MYVIDEO = 14 (My Video)
            # FOLDERID_Downloads = {374DE290-123F-4565-9164-39C4925E467B}
            
            # Versuche zuerst über SHGetKnownFolderPath (Windows Vista+)
            try:
                shell32 = ctypes.windll.shell32
                # FOLDERID_Downloads GUID
                downloads_guid = "{374DE290-123F-4565-9164-39C4925E467B}"
                
                # SHGetKnownFolderPath
                # HRESULT SHGetKnownFolderPath(
                #   REFKNOWNFOLDERID rfid,
                #   DWORD dwFlags,
                #   HANDLE hToken,
                #   PWSTR *ppszPath
                # );
                class GUID(ctypes.Structure):
                    _fields_ = [
                        ("Data1", ctypes.c_ulong),
                        ("Data2", ctypes.c_ushort),
                        ("Data3", ctypes.c_ushort),
                        ("Data4", ctypes.c_ubyte * 8)
                    ]
                
                # Konvertiere GUID-String zu GUID-Struktur
                def guid_from_string(guid_string):
                    guid_string = guid_string.replace('{', '').replace('}', '').replace('-', '')
                    data1 = int(guid_string[0:8], 16)
                    data2 = int(guid_string[8:12], 16)
                    data3 = int(guid_string[12:16], 16)
                    data4 = [int(guid_string[16:18], 16), int(guid_string[18:20], 16),
                            int(guid_string[20:22], 16), int(guid_string[22:24], 16),
                            int(guid_string[24:26], 16), int(guid_string[26:28], 16),
                            int(guid_string[28:30], 16), int(guid_string[30:32], 16)]
                    return GUID(data1, data2, data3, (ctypes.c_ubyte * 8)(*data4))
                
                guid = guid_from_string(downloads_guid)
                
                # Definiere SHGetKnownFolderPath
                shell32.SHGetKnownFolderPath.argtypes = [
                    ctypes.POINTER(GUID),
                    ctypes.c_uint32,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_wchar_p)
                ]
                shell32.SHGetKnownFolderPath.restype = ctypes.c_ulong
                
                # Rufe API auf
                path_ptr = ctypes.c_wchar_p()
                result = shell32.SHGetKnownFolderPath(
                    ctypes.byref(guid),
                    0,  # KF_FLAG_DEFAULT
                    None,
                    ctypes.byref(path_ptr)
                )
                
                if result == 0:  # S_OK
                    downloads_path = path_ptr.value
                    # Speicher freigeben
                    ctypes.windll.ole32.CoTaskMemFree(path_ptr)
                    if downloads_path and os.path.exists(downloads_path):
                        return Path(downloads_path)
            except Exception:
                pass
            
            # Fallback: Verwende SHGetFolderPath (ältere Windows-Versionen)
            try:
                CSIDL_PERSONAL = 5  # My Documents
                SHGFP_TYPE_CURRENT = 0
                
                buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
                result = shell32.SHGetFolderPathW(
                    None,
                    CSIDL_PERSONAL,
                    None,
                    SHGFP_TYPE_CURRENT,
                    buf
                )
                
                if result == 0:  # S_OK
                    # Versuche Downloads-Ordner in My Documents zu finden
                    # Oder verwende direkt den User-Profile-Pfad
                    user_profile = os.getenv('USERPROFILE', '')
                    if user_profile:
                        downloads_path = os.path.join(user_profile, 'Downloads')
                        if os.path.exists(downloads_path):
                            return Path(downloads_path)
            except Exception:
                pass
            
            # Letzter Fallback: Standard-Pfad
            user_profile = os.getenv('USERPROFILE', '')
            if user_profile:
                downloads_path = os.path.join(user_profile, 'Downloads')
                return Path(downloads_path)
        except Exception:
            pass
        
        # Fallback: Verwende Path.home()
        return Path.home() / "Downloads"
    
    elif sys.platform == "darwin":
        # macOS: Downloads-Ordner ist normalerweise ~/Downloads
        downloads_path = Path.home() / "Downloads"
        if downloads_path.exists():
            return downloads_path
        # Fallback
        return Path.home() / "Downloads"
    
    else:
        # Linux: XDG User Directories
        try:
            # Prüfe XDG_USER_DIRS
            xdg_config_home = os.getenv('XDG_CONFIG_HOME', Path.home() / '.config')
            user_dirs_file = Path(xdg_config_home) / 'user-dirs.dirs'
            
            if user_dirs_file.exists():
                with open(user_dirs_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('XDG_DOWNLOAD_DIR='):
                            # Extrahiere Pfad: XDG_DOWNLOAD_DIR="$HOME/Downloads"
                            path_str = line.split('=', 1)[1].strip().strip('"').strip("'")
                            # Ersetze $HOME mit tatsächlichem Home-Pfad
                            if path_str.startswith('$HOME'):
                                path_str = str(Path.home()) + path_str[5:]
                            elif path_str.startswith('~'):
                                path_str = str(Path(path_str).expanduser())
                            
                            downloads_path = Path(path_str)
                            if downloads_path.exists():
                                return downloads_path
        except Exception:
            pass
        
        # Fallback: Standard-Pfad
        downloads_path = Path.home() / "Downloads"
        if downloads_path.exists():
            return downloads_path
        return Path.home() / "Downloads"


def get_app_base_path():
    """
    Gibt den Basis-Pfad für die Anwendung zurück (Downloads/Universal Downloader)
    
    Returns:
        Path: Pfad zum Basis-Verzeichnis der Anwendung
    """
    downloads_folder = get_downloads_folder()
    app_path = downloads_folder / "Universal Downloader"
    
    # Versuche Ordner zu erstellen
    try:
        app_path.mkdir(parents=True, exist_ok=True)
    except (PermissionError, OSError):
        # Fallback: Verwende AppData oder ähnliches
        if sys.platform == "win32":
            appdata = os.getenv('APPDATA', Path.home() / "AppData" / "Roaming")
            app_path = Path(appdata) / "Universal Downloader"
        elif sys.platform == "darwin":
            app_path = Path.home() / "Library" / "Application Support" / "Universal Downloader"
        else:
            app_path = Path.home() / ".universal-downloader"
        app_path.mkdir(parents=True, exist_ok=True)
    
    return app_path


if __name__ == "__main__":
    # Test
    print("Download-Ordner:", get_downloads_folder())
    print("App-Basis-Pfad:", get_app_base_path())
