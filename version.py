#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Versionsinformationen für Universal Downloader
"""

__version__ = "2.0.7"
__version_info__ = (2, 0, 7)
__build_date__ = "2025-01-19"

# GitHub Repository URL (für Links und Updates)
GITHUB_REPO_URL = "https://github.com/msebastian100/Universal-Downloader"
GITHUB_RELEASES_URL = "https://github.com/msebastian100/Universal-Downloader/releases"

# Update-URL (GitHub Releases API)
UPDATE_CHECK_URL = "https://api.github.com/repos/msebastian100/Universal-Downloader/releases/latest"

# Alternative: Eigene Update-Server-URL
# UPDATE_CHECK_URL = "https://your-server.com/updates/universal-downloader.json"

def get_version():
    """Gibt die aktuelle Version zurück"""
    return __version__

def get_version_info():
    """Gibt Versionsinfo als Tuple zurück"""
    return __version_info__

def get_version_string():
    """Gibt formatierte Versionszeichenkette zurück"""
    return f"Universal Downloader v{__version__} (Build: {__build_date__})"

def compare_versions(version1: str, version2: str) -> int:
    """
    Vergleicht zwei Versionsnummern
    
    Returns:
        -1 wenn version1 < version2
         0 wenn version1 == version2
         1 wenn version1 > version2
    """
    def version_tuple(v):
        return tuple(map(int, v.split('.')))
    
    v1 = version_tuple(version1)
    v2 = version_tuple(version2)
    
    if v1 < v2:
        return -1
    elif v1 > v2:
        return 1
    else:
        return 0
