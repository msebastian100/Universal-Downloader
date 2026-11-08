#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VOE-Seiten (voe.sx) in eine direkte Datei auflösen."""

import base64
import json
import re
import urllib.request
from typing import Optional, Dict
from urllib.parse import urlparse


_FILE_CODE = re.compile(r"^[a-z0-9]{8,20}$")
_PAGE_CACHE: Dict[str, str] = {}
# Bekannte Fremddatei, die nicht geladen wird.
_BLOCKED_CODES = {"qtwt0ynagj6p"}


def _file_code(url: str) -> str:
    parts = [part for part in (urlparse(url or "").path or "").split("/") if part]
    if len(parts) != 1:
        return ""
    return parts[0].lower()


def _is_voe_host(url: str) -> bool:
    host = (urlparse(url or "").hostname or "").lower()
    return host == "voe.sx" or host.endswith(".voe.sx")


def _fetch_cached(url: str) -> str:
    key = (url or "").strip()
    cached = _PAGE_CACHE.get(key)
    if cached is None:
        cached = _fetch(key)
        _PAGE_CACHE[key] = cached
    return cached


def _player_page(url: str) -> str:
    page = _fetch_cached(url)
    redirect = re.search(r"window\.location\.href\s*=\s*'(https://[^']+)'", page)
    if redirect:
        page = _fetch_cached(redirect.group(1))
    return page


def _is_voe_player(page: str) -> bool:
    text = (page or "").lower()
    return 'type="application/json"' in text and " - voe" in text


def is_voe_url(url: str) -> bool:
    if _file_code(url) in _BLOCKED_CODES:
        return False
    if _is_voe_host(url):
        return True
    if not _FILE_CODE.fullmatch(_file_code(url)):
        return False
    try:
        return _is_voe_player(_player_page(url.strip()))
    except Exception:
        return False


def _rot13(text: str) -> str:
    out = []
    for char in text:
        if "A" <= char <= "Z":
            out.append(chr((ord(char) - 65 + 13) % 26 + 65))
        elif "a" <= char <= "z":
            out.append(chr((ord(char) - 97 + 13) % 26 + 97))
        else:
            out.append(char)
    return "".join(out)


def _decrypt_payload(encoded: str) -> Dict:
    text = _rot13(encoded)
    for pattern in ("@$", "^^", "~@", "%?", "*~", "!!", "#&"):
        text = text.replace(pattern, "_")
    text = text.replace("_", "")
    text = base64.b64decode(text).decode("utf-8")
    text = "".join(chr(ord(char) - 3) for char in text)
    text = base64.b64decode(text[::-1]).decode("utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("VOE-Antwort ist kein Objekt")
    return data


def _fetch(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def resolve_voe(url: str) -> Optional[Dict]:
    """Liefert Titel und direkte Datei. None, wenn es keine VOE-Adresse ist."""
    if not is_voe_url(url):
        return None
    page = _player_page(url.strip())
    player_url = url.strip()
    redirect = re.search(r"window\.location\.href\s*=\s*'(https://[^']+)'", _fetch_cached(url.strip()))
    if redirect:
        player_url = redirect.group(1)
    if not _is_voe_player(page):
        raise ValueError("VOE-Player enthält keine Dateiinformation")
    match = re.search(
        r'<script type="application/json">\s*\[\s*"(.*?)"\s*\]\s*</script>',
        page,
        re.S,
    )
    if not match:
        raise ValueError("VOE-Player enthält keine Dateiinformation")
    info = _decrypt_payload(match.group(1))
    media = (info.get("direct_access_url") or info.get("source") or "").strip()
    if not media.startswith("http"):
        raise ValueError("VOE-Player enthält keinen Dateilink")
    title = (info.get("title") or info.get("file_code") or "VOE").strip()
    title = re.sub(r"\.(mp4|mkv|webm|m4v)$", "", title, flags=re.I).strip() or "VOE"
    site = (info.get("site_name") or urlparse(player_url).hostname or "voe.sx").strip()
    return {
        "id": info.get("file_code") or "",
        "title": title,
        "url": media,
        "webpage_url": url.strip(),
        "extractor": "VOE",
        "extractor_key": "VOE",
        "uploader": "VOE",
        "referer": f"https://{site}/",
        "ext": "mp4" if ".mp4" in media.lower() else "mp4",
        "duration": 0,
    }
