#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serien-Wächter: Mediathek-Playlists (z. B. ARD) per yt-dlp prüfen,
neue Folgen / neue Staffel erkennen, Benachrichtigungen vorbereiten.

ARD: Staffel-URLs werden wie im Video-Downloader zur Serien-URL normalisiert,
damit alle Staffeln in der Playlist erscheinen (nicht nur eine Teilmenge).
"""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
import threading
import time
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


def state_file(base: Path) -> Path:
    return base / "series_watch_state.json"


def load_state(base: Path) -> Dict[str, Any]:
    p = state_file(base)
    if not p.exists():
        return {"items": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"items": []}
        if not isinstance(data.get("items"), list):
            data["items"] = []
        return data
    except Exception:
        return {"items": []}


def save_state(base: Path, data: Dict[str, Any]) -> None:
    p = state_file(base)
    tmp = p.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(p)


def normalize_ardmediathek_watch_url(url: str) -> str:
    """
    Wandelt eine ARD-Staffel-URL in die Serien-URL um (alle Staffeln in einer Playlist).
    Entspricht VideoDownloader._extract_series_url (ARD-Zweig).
    """
    if not url or "ardmediathek.de" not in url.lower() or "/staffel-" not in url.lower():
        return url.strip()
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    parsed = urlparse(url.strip())
    path_parts = [p for p in parsed.path.split("/") if p]

    new_path_parts: List[str] = []
    skip_staffel = False

    for i, part in enumerate(path_parts):
        if part.startswith("staffel-") and part.replace("staffel-", "").isdigit():
            skip_staffel = True
            continue

        if skip_staffel:
            skip_staffel = False

        is_last = i == len(path_parts) - 1
        is_digit_only = part.isdigit() and len(part) <= 2

        if is_last and is_digit_only:
            if i > 0 and any(c.isalpha() for c in path_parts[i - 1]):
                continue

        new_path_parts.append(part)

    new_path = "/" + "/".join(new_path_parts)
    query_params = parse_qs(parsed.query)
    if "isChildContent" in query_params:
        del query_params["isChildContent"]
    new_query = urlencode(query_params, doseq=True) if query_params else ""

    return urlunparse((parsed.scheme, parsed.netloc, new_path, parsed.params, new_query, parsed.fragment))


# Hörbuch / Hörspiel / Audiothek (Musik-Tab) – nicht die Video-Mediathek
AUDIO_WATCH_DOMAINS = (
    "ardaudiothek.de",
    "ardsounds.de",
    "librivox.org",
    "vorleser.net",
    "hoerspielprojekt.de",
    "deutschlandfunk.de",
    "deutschlandradio.de",
    "dradio.de",
    "music.youtube.com",
)
AUDIO_WATCH_HINTS = (
    "audiothek",
    "/hoerspiel",
    "/podcast",
    "/sendung/",
    "/episode/",
)


def is_audio_watch_url(url: str) -> bool:
    """True bei Audiothek/Hörbuch/Hörspiel – dann Musik-Ordner und MP3, nicht Video."""
    ul = (url or "").lower()
    if not ul:
        return False
    if any(d in ul for d in AUDIO_WATCH_DOMAINS):
        return True
    if "ardmediathek.de" in ul:
        return False
    return any(h in ul for h in AUDIO_WATCH_HINTS)


def normalize_ard_audio_watch_url(url: str) -> str:
    """ARD Sounds / Audiothek: URN-URLs für yt-dlp glätten."""
    u = (url or "").strip()
    if not u:
        return u
    ul = u.lower()
    if "ardsounds.de" not in ul and "ardaudiothek.de" not in ul:
        return u
    urn_match = re.search(r"urn:ard:(?:episode|show):[^/\s\"'<>]+", u, re.IGNORECASE)
    if urn_match:
        urn = urn_match.group(0).rstrip("/")
        host = "www.ardsounds.de" if "ardsounds.de" in ul else "www.ardaudiothek.de"
        if "urn:ard:episode:" in urn.lower():
            return f"https://{host}/episode/{urn}"
        return f"https://{host}/sendung/{urn}"
    if "/embed/" in ul:
        u = u.replace("/embed/episode/", "/episode/")
        u = u.replace("/embed/podcast/", "/podcast/")
        u = u.replace("/embed/sendung/", "/sendung/")
        return u.rstrip("/")
    return u


def normalize_watch_url(url: str) -> str:
    u = (url or "").strip()
    if is_audio_watch_url(u):
        return normalize_ard_audio_watch_url(u)
    return normalize_ardmediathek_watch_url(u)


def episode_url_for_watch(series_url: str, eurl: str) -> str:
    """Macht relative yt-dlp-IDs zu vollständigen Video- oder Audiothek-URLs."""
    eurl = (eurl or "").strip()
    if not eurl:
        return ""
    if eurl.startswith("http://") or eurl.startswith("https://"):
        if is_audio_watch_url(series_url) or is_audio_watch_url(eurl):
            return normalize_ard_audio_watch_url(eurl)
        return eurl
    rel = eurl.lstrip("/")
    if is_audio_watch_url(series_url):
        sl = (series_url or "").lower()
        host = "www.ardsounds.de" if "ardsounds.de" in sl else "www.ardaudiothek.de"
        if rel.startswith("urn:ard:episode:"):
            return f"https://{host}/episode/{rel}"
        if rel.startswith("urn:ard:show:"):
            return f"https://{host}/sendung/{rel}"
        return f"https://{host}/{rel}"
    return "https://www.ardmediathek.de/" + rel


def watch_item_kind(it: Optional[Dict[str, Any]], url: str = "") -> str:
    if isinstance(it, dict) and it.get("kind") in ("audio", "video"):
        return str(it.get("kind"))
    u = url or ((it or {}).get("url") if isinstance(it, dict) else "") or ""
    return "audio" if is_audio_watch_url(u) else "video"


def is_youtube_watch_url(url: str) -> bool:
    ul = (url or "").lower()
    return "youtube.com" in ul or "youtu.be" in ul


def format_choices_for_watch(it: Optional[Dict[str, Any]] = None, url: str = "") -> List[str]:
    """Wählbare Ausgabeformate für eine überwachte Serie oder Playlist."""
    u = url or ((it or {}).get("url") if isinstance(it, dict) else "") or ""
    if watch_item_kind(it, u) == "audio" or is_audio_watch_url(u):
        return ["mp3"]
    if is_youtube_watch_url(u):
        return ["mp4", "mkv", "mp3"]
    return ["mp4", "mkv"]


def effective_download_format(it: Optional[Dict[str, Any]] = None, url: str = "") -> str:
    """Gespeichertes Format, sonst der Standard (Video MP4, Audio MP3)."""
    choices = format_choices_for_watch(it, url)
    raw = ""
    if isinstance(it, dict):
        raw = str(it.get("download_format") or "").lower().strip()
    if raw in choices:
        return raw
    return choices[0]


def download_format_for_series(state: Dict[str, Any], series_url: str = "", series_name: str = "") -> str:
    """Format der passenden überwachten Serie."""
    url = _normalize_url_key(series_url)
    name = (series_name or "").strip()
    for it in state.get("items") or []:
        if not isinstance(it, dict):
            continue
        iu = _normalize_url_key(it.get("url") or "")
        labels = {
            (it.get("display_name") or "").strip(),
            (it.get("playlist_title") or "").strip(),
        }
        if (url and iu and iu == url) or (name and name in labels):
            return effective_download_format(it, it.get("url") or series_url)
    return effective_download_format(None, series_url)


def season_from_title(title: str) -> Optional[int]:
    m = re.search(r"\(S(\d+)/", title or "", re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def episode_s_e_from_title(title: str) -> Tuple[Optional[int], Optional[int]]:
    m = re.search(r"\(S(\d+)/E(\d+)\)", title or "", re.IGNORECASE)
    if not m:
        return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except ValueError:
        return None, None


def max_season_in_episodes(episodes: Dict[str, Any]) -> int:
    m = 0
    for _eid, meta in episodes.items():
        if not isinstance(meta, dict):
            continue
        s = season_from_title(meta.get("title") or "")
        if s is not None and s > m:
            m = s
    return m


def _have_ids_as_set(it: Dict[str, Any]) -> Set[str]:
    raw = it.get("have_ids")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x}


def _ignore_ids_as_set(it: Dict[str, Any]) -> Set[str]:
    raw = it.get("ignore_ids")
    if not isinstance(raw, list):
        return set()
    return {str(x) for x in raw if x}


_EXTRA_TITLE_RE = re.compile(
    r"(?i)(?:"
    r"trailer|teaser|\bvorschau\b|\bpreview\b|"
    r"making[\s\-]?of|makingoff|"
    r"behind[\s\-]?the[\s\-]?scenes|hinter den kulissen|"
    r"\bblooper\b|\bbloopers\b|\bouttake\b|\bouttakes\b|"
    r"\brecap\b|\brückblick\b|"
    r"\bbonus(?:material)?\b|\bfeaturette\b"
    r")"
)


def is_likely_extra_title(title: str) -> bool:
    """Trailer, Making-of u. Ä. — standardmäßig ignorieren, kein Fehlend-Hinweis."""
    t = (title or "").strip()
    if not t:
        return False
    return bool(_EXTRA_TITLE_RE.search(t))


def is_episode_ignored(ep: Dict[str, Any], it: Dict[str, Any]) -> bool:
    eid = str(ep.get("id") or "")
    return bool(eid) and eid in _ignore_ids_as_set(it)


def item_has_ownership_marks(it: Dict[str, Any]) -> bool:
    if _have_ids_as_set(it) or _ignore_ids_as_set(it):
        return True
    try:
        if int(it.get("have_full_seasons_upto") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    return bool(it.get("have_partial_seasons"))


def _normalize_url_key(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    return u


def mark_downloaded_episodes(
    base: Path,
    *,
    urls: Optional[List[str]] = None,
    episode_ids: Optional[List[str]] = None,
) -> int:
    """
    Markiert heruntergeladene Folgen in have_ids aller passenden Watch-Einträge.
    Match über Episode-ID und/oder URL (gegen episodes{} und neue Listen-URLs).
    Rückgabe: Anzahl neu hinzugefügter IDs (gesamt über Einträge).
    """
    urls = [u for u in (urls or []) if (u or "").strip()]
    ids = [str(i) for i in (episode_ids or []) if i]
    if not urls and not ids:
        return 0

    state = load_state(base)
    items = state.get("items")
    if not isinstance(items, list) or not items:
        return 0

    url_keys = {_normalize_url_key(u) for u in urls}
    id_set = set(ids)
    added = 0

    for it in items:
        if not isinstance(it, dict):
            continue
        episodes = it.get("episodes")
        if not isinstance(episodes, dict):
            episodes = {}
            it["episodes"] = episodes
        matched = set()
        ep_ids = {str(k) for k in episodes}
        for eid in id_set:
            if eid in ep_ids:
                matched.add(eid)
        for eid, meta in episodes.items():
            if not isinstance(meta, dict):
                continue
            eu = _normalize_url_key(meta.get("url") or "")
            if eu and eu in url_keys:
                matched.add(str(eid))
        if not matched:
            continue
        hid = _have_ids_as_set(it)
        before = len(hid)
        hid |= matched
        if len(hid) > before:
            added += len(hid) - before
            it["have_ids"] = sorted(hid)

    if added:
        save_state(base, state)
    return added


def mark_ignored_episodes(
    base: Path,
    *,
    episode_ids: Optional[List[str]] = None,
    series_url: str = "",
) -> int:
    """Setzt ignore_ids (Trailer/Making-of o. Ä.) und nimmt die IDs aus have_ids."""
    ids = [str(i) for i in (episode_ids or []) if i]
    if not ids:
        return 0
    state = load_state(base)
    items = state.get("items")
    if not isinstance(items, list) or not items:
        return 0
    want_url = _normalize_url_key(series_url)
    added = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        if want_url:
            iu = _normalize_url_key(it.get("url") or "")
            if iu and iu != want_url:
                continue
        ign = _ignore_ids_as_set(it)
        hid = _have_ids_as_set(it)
        before = len(ign)
        for eid in ids:
            ign.add(eid)
            hid.discard(eid)
        if len(ign) > before:
            added += len(ign) - before
            it["ignore_ids"] = sorted(ign)
            it["have_ids"] = sorted(hid)
    if added:
        save_state(base, state)
    return added


def check_lock_path(base: Path) -> Path:
    return Path(base) / "series_watch_check.lock"


def try_acquire_check_lock(base: Path, holder: str = "app") -> Optional[Any]:
    """
    Einfacher File-Lock gegen parallele Prüfungen (GUI + Tray).
    Rückgabe: Lock-Handle (mit .close() freigeben) oder None wenn belegt.
    """
    import os

    path = check_lock_path(base)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(path, "a+", encoding="utf-8")
        if sys_platform_is_windows():
            import msvcrt

            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                fh.close()
                return None
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                return None
        fh.seek(0)
        fh.truncate()
        fh.write(f"{holder}:{os.getpid()}:{time.time()}\n")
        fh.flush()
        return fh
    except Exception:
        return None


def release_check_lock(fh: Any) -> None:
    if not fh:
        return
    try:
        if sys_platform_is_windows():
            import msvcrt

            try:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        else:
            import fcntl

            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        fh.close()
    except Exception:
        pass


def sys_platform_is_windows() -> bool:
    import sys

    return sys.platform == "win32"


def item_wants_auto_download(it: Dict[str, Any], settings: Optional[Dict[str, Any]] = None) -> bool:
    """Pro-Serie auto_download, sonst globale Einstellung series_watch_auto_download."""
    if isinstance(it, dict) and "auto_download" in it:
        return bool(it.get("auto_download"))
    if settings and isinstance(settings, dict):
        return bool(settings.get("series_watch_auto_download", False))
    return False


def episodes_for_video_download(
    new_eps: List[Dict[str, Any]],
    series_name: str = "",
    *,
    kind: str = "video",
    series_url: str = "",
    output_format: str = "",
) -> List[Dict[str, Any]]:
    """Formatiert New-Episodes für Video- oder Audiothek-Download/Queue."""
    out: List[Dict[str, Any]] = []
    k = "audio" if kind == "audio" or is_audio_watch_url(series_url) else "video"
    for ep in new_eps or []:
        if not isinstance(ep, dict):
            continue
        url = episode_url_for_watch(series_url, (ep.get("url") or "").strip())
        if not url:
            continue
        title = ep.get("title") or ""
        if "audiodeskription" in title.lower():
            continue
        s, e = episode_s_e_from_title(title)
        out.append({
            "url": url,
            "title": title,
            "id": ep.get("id"),
            "series": series_name or "",
            "series_name": series_name or "",
            "series_url": series_url or "",
            "kind": k,
            "season_number": s if s is not None else 1,
            "episode_number": e,
            "playlist_index": e,
            "output_format": (output_format or "").lower(),
        })
    return out


def is_episode_had(ep: Dict[str, Any], it: Dict[str, Any]) -> bool:
    """True, wenn die Folge laut Nutzer-Angaben „schon vorhanden“ ist (kein Hinweis nötig)."""
    if is_episode_ignored(ep, it):
        return True
    eid = str(ep.get("id") or "")
    if eid and eid in _have_ids_as_set(it):
        return True

    s, e = episode_s_e_from_title(ep.get("title") or "")
    if s is None:
        s = ep.get("season_number")  # type: ignore[assignment]
    if e is None:
        e = ep.get("episode_number")  # type: ignore[assignment]
    try:
        s_i = int(s) if s is not None else None
    except (TypeError, ValueError):
        s_i = None
    try:
        e_i = int(e) if e is not None else None
    except (TypeError, ValueError):
        e_i = None

    try:
        upto = int(it.get("have_full_seasons_upto") or 0)
    except (TypeError, ValueError):
        upto = 0
    if upto > 0 and s_i is not None and s_i <= upto:
        return True

    for rule in it.get("have_partial_seasons") or []:
        if not isinstance(rule, dict):
            continue
        try:
            rs = int(rule.get("season", 0))
            re_upto = int(rule.get("episode_upto", 0))
        except (TypeError, ValueError):
            continue
        if re_upto <= 0:
            continue
        if s_i == rs and e_i is not None and e_i <= re_upto:
            return True
    return False


def filter_skip_audiodeskription(episodes: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for ep in episodes:
        t = (ep.get("title") or "").lower()
        if "audiodeskription" in t:
            continue
        out.append(ep)
    return out


_ARD_AUDIO_API = "https://api.ardaudiothek.de"
_ARD_SHOW_PAGE_SIZE = 24
_ARD_SHOW_EPISODE_QUERY = (
    "query ProgramSetEpisodesQuery($id: ID!, $offset: Int!, $count: Int!) {"
    " result: programSet(id: $id) {"
    " id title numberOfElements"
    " items(offset: $offset, first: $count, filter: {isPublished: {equalTo: true},"
    " itemType: {notEqualTo: EVENT_LIVESTREAM}}) {"
    " pageInfo { hasNextPage }"
    " nodes { id assetId title path }"
    " } } }"
)


def is_ard_audio_show_url(url: str) -> bool:
    """Sendungsseite von ARD Sounds / Audiothek, nicht eine einzelne Folge."""
    ul = (url or "").lower()
    if "ardsounds.de" not in ul and "ardaudiothek.de" not in ul:
        return False
    return "/sendung/" in ul or "urn:ard:show:" in ul


def _ard_audio_site_host(url: str) -> str:
    if "ardaudiothek.de" in (url or "").lower():
        return "www.ardaudiothek.de"
    return "www.ardsounds.de"


def _http_bytes(url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 30) -> bytes:
    import urllib.request

    hdrs = {"User-Agent": "Mozilla/5.0"}
    if headers:
        hdrs.update(headers)

    def _open(context: Optional[ssl.SSLContext] = None) -> bytes:
        req = urllib.request.Request(url, data=data, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout, context=context) as resp:
            return resp.read()

    try:
        return _open()
    except Exception as ex:
        msg = str(ex).lower()
        if "certificate verify failed" not in msg and "certificate_verify_failed" not in msg:
            raise
        return _open(ssl._create_unverified_context())


def _episode_from_ard_node(node: Any, host: str) -> Optional[Dict[str, str]]:
    if not isinstance(node, dict):
        return None
    asset = str(node.get("assetId") or "").strip()
    eid = asset or str(node.get("id") or "").strip()
    if not eid:
        return None
    title = (node.get("title") or "").strip() or eid
    path = str(node.get("path") or "").strip()
    if path.startswith("/"):
        eurl = f"https://{host}{path}"
    elif asset.lower().startswith("urn:ard:episode:"):
        eurl = f"https://{host}/episode/{asset}"
    else:
        return None
    return {"id": eid, "title": title, "url": eurl.rstrip("/")}


def fetch_ard_audio_show_episodes(url: str, timeout: int = 180) -> Tuple[str, str, List[Dict[str, str]]]:
    """
    Folgen einer ARD-Sounds-/Audiothek-Sendung.
    yt-dlp kennt die Sendungsseite nicht; die Seite und die Audiothek-API schon.
    """
    u = normalize_ard_audio_watch_url((url or "").strip())
    raw_html = _http_bytes(u, timeout=min(40, timeout))
    html = raw_html.decode("utf-8", "replace")
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not match:
        raise RuntimeError("ARD Sounds: Sendungsseite ohne Folgenliste")
    try:
        page = json.loads(match.group(1))
    except json.JSONDecodeError as ex:
        raise RuntimeError("ARD Sounds: Folgenliste nicht lesbar") from ex
    result = (
        ((page.get("props") or {}).get("pageProps") or {}).get("initialData") or {}
    ).get("data", {}).get("result") or {}
    if not isinstance(result, dict) or not result.get("id"):
        raise RuntimeError("ARD Sounds: keine Sendung in der Seite")
    pid = str(result.get("id") or "")
    ptitle = (result.get("title") or "ARD Sounds").strip()
    try:
        total = int(result.get("numberOfElements") or 0)
    except (TypeError, ValueError):
        total = 0
    host = _ard_audio_site_host(u)
    items = result.get("items") if isinstance(result.get("items"), dict) else {}
    out: List[Dict[str, str]] = []
    seen: Set[str] = set()

    def add_nodes(nodes: Any) -> int:
        added = 0
        if not isinstance(nodes, list):
            return 0
        for node in nodes:
            ep = _episode_from_ard_node(node, host)
            if not ep or ep["id"] in seen:
                continue
            seen.add(ep["id"])
            out.append(ep)
            added += 1
        return added

    first_nodes = items.get("nodes") if isinstance(items.get("nodes"), list) else []
    add_nodes(first_nodes)
    page_info = items.get("pageInfo") if isinstance(items.get("pageInfo"), dict) else {}
    has_next = bool(page_info.get("hasNextPage"))
    offset = len(first_nodes) or _ARD_SHOW_PAGE_SIZE
    pages = 0
    while has_next and pages < 40 and (total <= 0 or len(out) < total):
        pages += 1
        body = json.dumps({
            "query": _ARD_SHOW_EPISODE_QUERY,
            "variables": {"id": pid, "offset": offset, "count": _ARD_SHOW_PAGE_SIZE},
        }).encode("utf-8")
        payload_raw = _http_bytes(
            _ARD_AUDIO_API + "/graphql",
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Origin": f"https://{host}",
                "Referer": u,
            },
            timeout=min(40, timeout),
        )
        try:
            payload = json.loads(payload_raw.decode("utf-8", "replace"))
        except json.JSONDecodeError as ex:
            raise RuntimeError("ARD Sounds: weitere Folgen nicht lesbar") from ex
        block = ((payload.get("data") or {}).get("result") or {}).get("items") or {}
        if not isinstance(block, dict):
            break
        new_nodes = block.get("nodes") if isinstance(block.get("nodes"), list) else []
        added = add_nodes(new_nodes)
        info = block.get("pageInfo") if isinstance(block.get("pageInfo"), dict) else {}
        has_next = bool(info.get("hasNextPage")) and added > 0 and bool(new_nodes)
        offset += len(new_nodes) or _ARD_SHOW_PAGE_SIZE
    if not out:
        raise RuntimeError("ARD Sounds: keine Folgen gefunden")
    return pid, ptitle, filter_skip_audiodeskription(out)


def _parse_json_stdout(stdout: str) -> Optional[dict]:
    if not stdout or not stdout.strip():
        return None
    s = stdout.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        for line in s.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
    return None


def fetch_playlist_episodes(url: str, timeout: int = 180) -> Tuple[str, str, List[Dict[str, str]]]:
    """
    Liest eine Playlist/Serien-URL mit yt-dlp (flat).
    ARD-Staffel-Links werden zur Serien-URL normalisiert.
    Rückgabe: (playlist_id, playlist_title, [{id, title, url}, ...])
    """
    from yt_dlp_helper import run_ytdlp

    u = normalize_watch_url((url or "").strip())
    if not u:
        raise ValueError("Leere URL")
    if is_ard_audio_show_url(u):
        return fetch_ard_audio_show_episodes(u, timeout=timeout)

    r = run_ytdlp(
        [
            "--flat-playlist",
            "--skip-download",
            "-J",
            "--no-warnings",
            "--socket-timeout",
            "30",
            u,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    data = _parse_json_stdout(r.stdout or "")
    if not data:
        err = ((r.stderr or "") + (r.stdout or ""))[:800]
        raise RuntimeError(f"yt-dlp: keine Playlist-Daten (Exit {r.returncode}). {err}")

    pid = str(data.get("id") or "")
    ptitle = (data.get("title") or "Serie / Playlist").strip()
    out: List[Dict[str, str]] = []

    if data.get("_type") == "playlist" and isinstance(data.get("entries"), list):
        for e in data["entries"]:
            if not isinstance(e, dict):
                continue
            eid = e.get("id")
            if eid is None:
                continue
            etitle = (e.get("title") or "").strip() or str(eid)
            eurl = episode_url_for_watch(u, (e.get("url") or "").strip() or str(eid))
            out.append({"id": str(eid), "title": etitle, "url": eurl})
    else:
        eid = data.get("id")
        if eid is not None:
            etitle = (data.get("title") or str(eid)).strip()
            eurl = (data.get("url") or u).strip()
            out.append({"id": str(eid), "title": etitle, "url": eurl})

    out = filter_skip_audiodeskription(out)
    return pid, ptitle, out


def merge_have_ids_from_current(it: Dict[str, Any], current: List[Dict[str, Any]]) -> None:
    """Erweitert have_ids anhand von have_full_seasons_upto und have_partial_seasons auf der aktuellen Liste."""
    hid = _have_ids_as_set(it)
    try:
        upto = int(it.get("have_full_seasons_upto") or 0)
    except (TypeError, ValueError):
        upto = 0
    if upto > 0:
        for ep in current:
            s, _e = episode_s_e_from_title(ep.get("title") or "")
            if s is not None and s <= upto:
                eid = str(ep.get("id") or "")
                if eid:
                    hid.add(eid)
    for rule in it.get("have_partial_seasons") or []:
        if not isinstance(rule, dict):
            continue
        try:
            rs = int(rule.get("season", 0))
            re_upto = int(rule.get("episode_upto", 0))
        except (TypeError, ValueError):
            continue
        if re_upto <= 0:
            continue
        for ep in current:
            s, e = episode_s_e_from_title(ep.get("title") or "")
            if s == rs and e is not None and e <= re_upto:
                eid = str(ep.get("id") or "")
                if eid:
                    hid.add(eid)
    it["have_ids"] = sorted(hid)


def check_all(
    base: Path,
    on_item_error: Optional[Callable[[str, str], None]] = None,
    report_unowned: bool = False,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Prüft alle gespeicherten Serien-Einträge, aktualisiert Zustand.
    Rückgabe: (neuer_state, benachrichtigungen)
    """
    state = load_state(base)
    items = state.get("items")
    if not isinstance(items, list):
        items = []
        state["items"] = items

    notifications: List[Dict[str, Any]] = []

    for it in items:
        if not isinstance(it, dict):
            continue
        url = (it.get("url") or "").strip()
        if not url:
            continue
        norm = normalize_watch_url(url)
        if norm != url:
            it["url"] = norm
            url = norm
        it["kind"] = watch_item_kind(it, url)

        name = (it.get("display_name") or "").strip() or url
        episodes = it.get("episodes")
        if not isinstance(episodes, dict):
            episodes = {}
            it["episodes"] = episodes
        if not isinstance(it.get("have_ids"), list):
            it["have_ids"] = []
        if not isinstance(it.get("ignore_ids"), list):
            it["ignore_ids"] = []
        if not isinstance(it.get("alerted_ids"), list):
            it["alerted_ids"] = []
        if not isinstance(it.get("have_partial_seasons"), list):
            it["have_partial_seasons"] = []

        baseline = bool(it.get("baseline_done"))
        max_seen = int(it.get("max_season_seen") or 0)

        try:
            _pid, ptitle, current = fetch_playlist_episodes(url)
        except Exception as ex:
            if on_item_error:
                on_item_error(name, str(ex))
            continue

        ign = _ignore_ids_as_set(it)
        hid = _have_ids_as_set(it)
        old_ids = set(episodes.keys())
        seed_extras = not ign
        for ep in current:
            eid = str(ep.get("id") or "")
            if not eid:
                continue
            if is_likely_extra_title(ep.get("title") or "") and eid not in hid:
                if seed_extras or eid not in old_ids:
                    ign.add(eid)
        it["ignore_ids"] = sorted(ign)

        merge_have_ids_from_current(it, current)

        it["playlist_title"] = ptitle
        it["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")
        for ep in current:
            eid = str(ep.get("id") or "")
            if eid:
                episodes[eid] = {"title": ep.get("title") or "", "url": ep.get("url") or ""}

        if not baseline:
            it["baseline_done"] = True
            it["max_season_seen"] = max_season_in_episodes(episodes)
            if item_has_ownership_marks(it):
                continue
            reported = [ep for ep in current if not is_episode_had(ep, it)]
            if not reported:
                continue
            alerted = {str(x) for x in (it.get("alerted_ids") or []) if x}
            for ep in reported:
                eid = str(ep.get("id") or "")
                if eid:
                    alerted.add(eid)
            it["alerted_ids"] = sorted(alerted)
            notifications.append(
                {
                    "watch_name": (it.get("display_name") or "").strip() or ptitle or name,
                    "series_url": url,
                    "playlist_title": ptitle,
                    "is_new_season": False,
                    "gap": True,
                    "catalog": True,
                    "new_episodes": [
                        {"title": ep["title"], "url": ep.get("url") or "", "id": ep.get("id")}
                        for ep in reported
                    ],
                }
            )
            continue

        alerted = {str(x) for x in (it.get("alerted_ids") or []) if x}
        for ep in current:
            if ep["id"] in episodes:
                episodes[ep["id"]] = {"title": ep["title"], "url": ep.get("url") or ""}

        fresh = [ep for ep in current if ep["id"] not in old_ids and not is_episode_had(ep, it)]
        gaps = []
        if item_has_ownership_marks(it):
            for ep in current:
                eid = str(ep.get("id") or "")
                if not eid or eid not in old_ids or is_episode_had(ep, it):
                    continue
                if report_unowned or eid not in alerted:
                    gaps.append(ep)

        if not fresh and not gaps:
            it["max_season_seen"] = max(max_seen, max_season_in_episodes(episodes))
            continue

        seasons_new = [season_from_title(ep["title"]) for ep in fresh]
        seasons_new_n = [s for s in seasons_new if s is not None]
        is_new_season = bool(fresh) and bool(seasons_new_n) and max(seasons_new_n) > max_seen
        reported = fresh + gaps
        catalog = (not item_has_ownership_marks(it)) and not old_ids and bool(fresh)

        for ep in reported:
            episodes[ep["id"]] = {"title": ep["title"], "url": ep.get("url") or ""}
            eid = str(ep.get("id") or "")
            if eid:
                alerted.add(eid)
        it["alerted_ids"] = sorted(alerted)
        it["max_season_seen"] = max(max_seen, max_season_in_episodes(episodes))

        notifications.append(
            {
                "watch_name": (it.get("display_name") or "").strip() or ptitle or name,
                "series_url": url,
                "playlist_title": ptitle,
                "is_new_season": False if catalog else is_new_season,
                "gap": True if catalog else (bool(gaps) and not fresh),
                "catalog": catalog,
                "new_episodes": [{"title": ep["title"], "url": ep.get("url") or "", "id": ep.get("id")} for ep in reported],
            }
        )

    save_state(base, state)
    return state, notifications


def format_notification_text(n: Dict[str, Any]) -> Tuple[str, str]:
    """Titel und mehrzeiliger Text für Desktop/Mail/Telegram/Discord."""
    episodes = [ep for ep in (n.get("new_episodes") or []) if isinstance(ep, dict)]
    if n.get("catalog"):
        title = f"Verfügbare Folgen: {n.get('watch_name')}"
        lead = "Noch nichts als „habe ich“ markiert. Im Menü auswählen, was geladen werden soll:"
    elif n.get("gap"):
        title = f"Fehlende Folgen: {n.get('watch_name')}"
        lead = "Noch nicht als „habe ich“ markiert:"
    elif n.get("is_new_season"):
        title = f"Neue Staffel: {n.get('watch_name')}"
        lead = "Neu:"
    else:
        title = f"Neue Folgen: {n.get('watch_name')}"
        lead = "Neu:"

    lines = [
        f"Playlist: {n.get('playlist_title') or ''}",
        f"Link: {n.get('series_url') or ''}",
        "",
        lead,
    ]
    shown = episodes[:8]
    for ep in shown:
        t = ep.get("title") or ""
        u = ep.get("url") or ""
        if u and len(episodes) <= 8:
            lines.append(f"• {t}\n  {u}")
        else:
            lines.append(f"• {t}")
    rest = len(episodes) - len(shown)
    if rest > 0:
        lines.append(f"… und {rest} weitere. Folgenliste im Menü öffnen.")
    body = "\n".join(lines)
    return title, body


def available_groups(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Folgen, die weder vorhanden noch ignoriert sind, gruppiert nach Serie."""
    groups: List[Dict[str, Any]] = []
    for it in state.get("items") or []:
        if not isinstance(it, dict):
            continue
        episodes = it.get("episodes")
        if not isinstance(episodes, dict) or not episodes:
            continue
        rows: List[Dict[str, str]] = []
        for eid, meta in episodes.items():
            if not isinstance(meta, dict):
                meta = {}
            ep = {
                "id": str(eid),
                "title": str(meta.get("title") or ""),
                "url": str(meta.get("url") or ""),
            }
            if is_episode_had(ep, it):
                continue
            rows.append(ep)
        if not rows:
            continue
        name = (it.get("display_name") or it.get("playlist_title") or "").strip() or "Serie"
        groups.append({
            "name": name,
            "series_url": it.get("url") or "",
            "count": len(rows),
            "episodes": rows,
        })
    return groups


def count_available_episodes(state: Dict[str, Any]) -> int:
    return sum(int(g.get("count") or 0) for g in available_groups(state))


def send_external_notifications(settings: Dict[str, Any], title: str, body: str) -> None:
    if settings.get("series_notify_email_enabled") and settings.get("series_email_to"):
        _send_smtp(settings, title, body)
    if settings.get("series_notify_telegram_enabled"):
        _send_telegram(settings, title, body)
    if settings.get("series_notify_discord_enabled"):
        _send_discord(settings, title, body)


def _send_smtp(settings: Dict[str, Any], subject: str, body: str) -> None:
    host = (settings.get("series_smtp_host") or "").strip()
    if not host:
        return
    try:
        port = int(settings.get("series_smtp_port") or 587)
    except (TypeError, ValueError):
        port = 587
    user = (settings.get("series_smtp_user") or "").strip()
    raw_pw = settings.get("series_smtp_password_enc") or ""
    password = _decrypt_series_pw(raw_pw)
    mail_from = (settings.get("series_email_from") or user or "").strip()
    to_raw = (settings.get("series_email_to") or "").strip()
    if not mail_from or not to_raw:
        return
    recipients = [x.strip() for x in to_raw.replace(";", ",").split(",") if x.strip()]
    if not recipients:
        return

    use_tls = bool(settings.get("series_smtp_tls", True))
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)

    if use_tls:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ctx)
            smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.sendmail(mail_from, recipients, msg.as_string())
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            if user:
                smtp.login(user, password)
            smtp.sendmail(mail_from, recipients, msg.as_string())
    return


def _decrypt_series_pw(enc: str) -> str:
    if not enc:
        return ""
    try:
        import base64

        return base64.b64decode(enc.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def _send_telegram(settings: Dict[str, Any], title: str, body: str) -> None:
    token = (settings.get("series_telegram_bot_token") or "").strip()
    chat = (settings.get("series_telegram_chat_id") or "").strip()
    if not token or not chat:
        return
    text = f"{title}\n\n{body}"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text[:4090]}
    try:
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=25)
    except Exception:
        try:
            import requests

            requests.post(url, json=payload, timeout=25)
        except Exception:
            pass


def _send_discord(settings: Dict[str, Any], title: str, body: str) -> None:
    wh = (settings.get("series_discord_webhook_url") or "").strip()
    if not wh:
        return
    content = f"**{title}**\n\n{body}"[:1990]
    try:
        import urllib.request

        data = json.dumps({"content": content}).encode("utf-8")
        req = urllib.request.Request(wh, data=data, headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=25)
    except Exception:
        try:
            import requests

            requests.post(wh, json={"content": content}, timeout=25)
        except Exception:
            pass


def runtime_status_path(base: Path) -> Path:
    return Path(base) / "series_watch_runtime.json"


def read_runtime_status(base: Path) -> Dict[str, Any]:
    p = runtime_status_path(base)
    if not p.exists():
        return {"phase": "idle"}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {"phase": "idle"}
    except Exception:
        return {"phase": "idle"}


_status_lock = threading.Lock()


def write_runtime_status(base: Path, **fields: Any) -> None:
    """Aktualisiert den gemeinsamen Runtime-Status (GUI + Tray)."""
    with _status_lock:
        cur = read_runtime_status(base)
        cur.update(fields)
        cur["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        p = runtime_status_path(base)
        tmp = p.with_suffix(".json.tmp")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cur, f, indent=2, ensure_ascii=False)
            tmp.replace(p)
        except Exception:
            pass


def set_download_progress(
    base: Path,
    *,
    title: str = "",
    series: str = "",
    percent: float = 0.0,
    index: int = 0,
    total: int = 0,
    pending: Optional[List[Dict[str, Any]]] = None,
    cancel_requested: Optional[bool] = None,
) -> None:
    payload: Dict[str, Any] = {
        "phase": "downloading",
        "download": {
            "title": title,
            "series": series,
            "percent": max(0.0, min(100.0, float(percent or 0))),
            "index": int(index or 0),
            "total": int(total or 0),
        },
    }
    if pending is not None:
        payload["pending"] = pending
    if cancel_requested is not None:
        payload["cancel_requested"] = bool(cancel_requested)
    write_runtime_status(base, **payload)


def request_download_cancel(base: Path) -> None:
    write_runtime_status(base, cancel_requested=True)


def is_download_cancel_requested(base: Path) -> bool:
    return bool(read_runtime_status(base).get("cancel_requested"))


def clear_download_status(base: Path, *, phase: str = "idle") -> None:
    write_runtime_status(
        base,
        phase=phase,
        download=None,
        downloads=[],
        pending=[],
        cancel_requested=False,
    )


def have_ids_for_series(state: Dict[str, Any], series_url: str = "", series_name: str = "") -> Set[str]:
    """have_ids nur der Serie, zu der der Hinweis gehört. Andere Serien zählen nicht."""
    items = [it for it in (state.get("items") or []) if isinstance(it, dict)]
    url = _normalize_url_key(series_url)
    name = (series_name or "").strip()
    matched = []
    for it in items:
        iu = _normalize_url_key(it.get("url") or "")
        labels = {
            (it.get("display_name") or "").strip(),
            (it.get("playlist_title") or "").strip(),
        }
        if url and iu and iu == url:
            matched.append(it)
        elif name and name in labels:
            matched.append(it)
    if not matched:
        return set()
    had: Set[str] = set()
    for it in matched:
        had |= _have_ids_as_set(it)
    return had


def remove_cross_series_have_ids(state: Dict[str, Any]) -> bool:
    """Nimmt Folgen-IDs aus have_ids, die nur zu einer anderen Serie gehören."""
    items = [it for it in (state.get("items") or []) if isinstance(it, dict)]
    owners: Dict[str, Set[int]] = {}
    for i, it in enumerate(items):
        episodes = it.get("episodes")
        if not isinstance(episodes, dict):
            continue
        for eid in episodes:
            owners.setdefault(str(eid), set()).add(i)
    changed = False
    for i, it in enumerate(items):
        hid = _have_ids_as_set(it)
        drop = [eid for eid in hid if owners.get(eid) and i not in owners[eid]]
        if not drop:
            continue
        for eid in drop:
            hid.discard(eid)
        it["have_ids"] = sorted(hid)
        changed = True
    return changed


def prune_owned_alerts(base: Path) -> bool:
    """Nimmt Folgen aus den Hinweisen, die in derselben Serie schon als „habe ich“ gelten.

    Eine andere Serie mit derselben ID blendet den Hinweis nicht aus.
    Lässt einen laufenden Download (phase) unangetastet.
    """
    state = load_state(base)
    if remove_cross_series_have_ids(state):
        save_state(base, state)
    rt = read_runtime_status(base)
    alerts = rt.get("new_alerts") if isinstance(rt.get("new_alerts"), list) else []
    if not alerts:
        return False
    kept = []
    changed = False
    for alert in alerts:
        if not isinstance(alert, dict):
            changed = True
            continue
        had = have_ids_for_series(state, alert.get("series_url") or "", alert.get("name") or "")
        eps = [
            ep for ep in (alert.get("episodes") or [])
            if isinstance(ep, dict) and str(ep.get("id") or "") not in had
        ]
        if len(eps) != len(alert.get("episodes") or []):
            changed = True
        if not eps:
            changed = True
            continue
        row = dict(alert)
        row["episodes"] = eps
        row["count"] = len(eps)
        kept.append(row)
    if changed:
        write_runtime_status(base, new_alerts=kept)
    return changed


class _HeadlessCancel:
    """Sieht für yt-dlp wie die GUI aus: Abbruch-Flag aus der Tray-Datei, eigener Prozess."""

    def __init__(self, base: Path):
        self._base = base
        self.video_download_process = None

    @property
    def video_download_cancelled(self) -> bool:
        return is_download_cancel_requested(self._base)


def gui_queue_file(base: Path) -> Path:
    return Path(base) / "series_watch_gui_queue.json"


def enqueue_gui_video_queue(base: Path, episodes: List[Dict[str, Any]]) -> int:
    """Legt Folgen für die Video-Queue des Hauptprogramms ab."""
    rows = []
    for ep in episodes or []:
        if not isinstance(ep, dict):
            continue
        url = (ep.get("url") or "").strip()
        if not url:
            continue
        rows.append({
            "url": url,
            "title": ep.get("title") or "",
            "series_name": ep.get("series") or ep.get("series_name") or "",
            "series_url": ep.get("series_url") or "",
            "id": ep.get("id"),
            "season_number": ep.get("season_number"),
            "episode_number": ep.get("episode_number"),
            "kind": ep.get("kind") or "video",
            "output_format": (ep.get("output_format") or "").lower(),
        })
    if not rows:
        return 0
    path = gui_queue_file(base)
    existing: List[Any] = []
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                existing = data
    except Exception:
        existing = []
    existing.extend(rows)
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
    return len(rows)


def take_gui_video_queue(base: Path) -> List[Dict[str, Any]]:
    path = gui_queue_file(base)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    try:
        path.unlink()
    except Exception:
        pass
    return [x for x in data if isinstance(x, dict)] if isinstance(data, list) else []


def _max_parallel_from_settings(settings: Dict[str, Any]) -> int:
    try:
        n = int(settings.get("max_concurrent_downloads", 1))
    except (TypeError, ValueError):
        n = 1
    return max(1, min(8, n))


def load_app_settings(base: Path) -> Dict[str, Any]:
    """Lädt settings.json aus dem App-Basisordner (für Tray ohne GUI)."""
    p = Path(base) / "settings.json"
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_desktop_notify_impl = None


def set_desktop_notify_impl(fn) -> None:
    """Tray kann eine native Balloon-Funktion setzen (kein PowerShell-Fenster)."""
    global _desktop_notify_impl
    _desktop_notify_impl = fn


def desktop_notify(title: str, message: str) -> None:
    """Plattform-Benachrichtigung ohne Tk (macOS/Linux/Windows Fallback)."""
    import subprocess
    import sys

    t = (title or "")[:120].replace('"', "'")
    m = (message or "")[:400].replace('"', "'")
    try:
        if sys.platform == "darwin":
            subprocess.run(
                ["osascript", "-e", f'display notification "{m}" with title "{t}"'],
                check=False,
                timeout=3,
                capture_output=True,
            )
        elif sys.platform.startswith("linux"):
            subprocess.run(["notify-send", t, m], check=False, timeout=3, capture_output=True)
        elif sys.platform == "win32":
            impl = globals().get("_desktop_notify_impl")
            if callable(impl):
                impl(t, m)
                return
            from path_helper import win_hidden_kwargs

            ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                f"$n.ShowBalloonTip(4000, '{t.replace(chr(39), '')}', '{m.replace(chr(39), '')}', "
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep -Seconds 4; $n.Dispose()"
            )
            # Versteckt, nicht warten – sonst bleibt ein PowerShell-Fenster mehrere Sekunden offen
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **win_hidden_kwargs(),
            )
    except Exception:
        pass


def collect_auto_download_episodes(
    base: Path,
    notifications: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Neue Folgen aus Notifications, gefiltert nach Auto-Download-Einstellung."""
    settings = settings or load_app_settings(base)
    state = load_state(base)
    items = [it for it in (state.get("items") or []) if isinstance(it, dict)]
    by_url = {(it.get("url") or "").strip(): it for it in items}
    out: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for n in notifications or []:
        if not isinstance(n, dict):
            continue
        url = (n.get("series_url") or "").strip()
        it = by_url.get(url) or {}
        if n.get("catalog"):
            continue
        if not item_wants_auto_download(it, settings):
            continue
        name = (n.get("watch_name") or "").strip()
        kind = watch_item_kind(it, url)
        fmt = effective_download_format(it, url)
        for ep in episodes_for_video_download(
            n.get("new_episodes") or [], name, kind=kind, series_url=url, output_format=fmt
        ):
            u = (ep.get("url") or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            out.append(ep)
    return out


def download_episodes_headless(
    base: Path,
    episodes: List[Dict[str, Any]],
    settings: Optional[Dict[str, Any]] = None,
    log: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float, str, Dict[str, Any]], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Tuple[int, int, bool]:
    """
    Lädt Folgen ohne GUI (Tray-Helper). Markiert have_ids bei Erfolg.
    progress_callback(percent, status_line, meta) – meta: title/series/index/total
    should_cancel() -> True bricht ab.
    Rückgabe: (success_count, fail_count, abgebrochen)
    """
    settings = settings or load_app_settings(base)
    _log = log or (lambda _m: None)
    if not episodes:
        return 0, 0
    try:
        from video_downloader import VideoDownloader
    except Exception as e:
        _log(f"VideoDownloader nicht ladbar: {e}")
        return 0, len(episodes), False

    video_path = Path(settings.get("default_video_path") or (Path(base) / "Video"))
    music_path = Path(settings.get("default_music_path") or (Path(base) / "Musik"))
    quality = settings.get("default_video_quality") or "best"
    output_format = settings.get("default_video_format") or "mp4"
    ok = 0
    fail = 0
    speed_limit = None
    if settings.get("speed_limit_enabled", False):
        try:
            speed_limit = float(settings.get("speed_limit_value", "5"))
        except (TypeError, ValueError):
            speed_limit = None

    total = len(episodes)
    max_c = min(_max_parallel_from_settings(settings), total)
    write_runtime_status(base, cancel_requested=False, phase="downloading", downloads=[], pending=[])

    from queue import Empty, Queue

    jobs: Queue = Queue()
    for i, ep in enumerate(episodes, 1):
        jobs.put((i, ep))
    active: Dict[int, Dict[str, Any]] = {}
    state_lock = threading.Lock()
    count_lock = threading.Lock()

    def _pending_rows() -> List[Dict[str, str]]:
        waiting = []
        try:
            snapshot = list(jobs.queue)
        except Exception:
            snapshot = []
        for _i, ep in snapshot:
            if isinstance(ep, dict):
                waiting.append({
                    "title": (ep.get("title") or "")[:80],
                    "series": (ep.get("series") or ep.get("series_name") or "")[:60],
                })
        return waiting

    def _publish() -> None:
        with state_lock:
            items = [active[k] for k in sorted(active)]
        first = items[0] if items else {"title": "", "series": "", "percent": 0.0, "index": 0, "total": total}
        write_runtime_status(
            base,
            phase="downloading",
            downloads=items,
            download={
                "title": first.get("title") or "",
                "series": first.get("series") or "",
                "percent": float(first.get("percent") or 0),
                "index": int(first.get("index") or 0),
                "total": total,
            },
            pending=_pending_rows(),
        )
        if progress_callback and items:
            try:
                top = items[0]
                progress_callback(
                    float(top.get("percent") or 0),
                    top.get("title") or "",
                    {"title": top.get("title"), "series": top.get("series"), "index": top.get("index"), "total": total},
                )
            except Exception:
                pass

    def _worker() -> None:
        nonlocal ok, fail
        try:
            from video_downloader import VideoDownloader as _VD
            vd = _VD(
                download_path=str(video_path),
                quality=quality,
                output_format=output_format,
                gui_instance=None,
            )
        except Exception as e:
            _log(f"VideoDownloader Init fehlgeschlagen: {e}")
            return
        while True:
            if is_download_cancel_requested(base) or (should_cancel and should_cancel()):
                break
            try:
                i, ep = jobs.get_nowait()
            except Empty:
                break
            url = (ep.get("url") or "").strip()
            title = ep.get("title") or url or "Folge"
            series_name = ep.get("series") or ep.get("series_name") or ""
            if not url:
                with count_lock:
                    fail += 1
                continue
            is_audio = (ep.get("kind") == "audio") or is_audio_watch_url(url) or is_audio_watch_url(
                ep.get("series_url") or ""
            )
            out_fmt = (ep.get("output_format") or "").lower()
            if out_fmt not in ("mp3", "mp4", "mkv"):
                out_fmt = "mp3" if is_audio else output_format
            if out_fmt == "mp3":
                is_audio = True
            out_dir = music_path if is_audio or out_fmt == "mp3" else video_path
            season_number = ep.get("season_number")
            with state_lock:
                active[i] = {
                    "title": title,
                    "series": series_name,
                    "percent": 0.0,
                    "index": i,
                    "total": total,
                }
            _publish()
            _log(f"Download [{i}/{total}]: {title}")
            cancel_bridge = _HeadlessCancel(base)

            def _prog(percent, _status, _i=i, _title=title, _series=series_name):
                try:
                    pct = float(percent or 0)
                except (TypeError, ValueError):
                    pct = 0.0
                with state_lock:
                    slot = active.get(_i)
                    if slot is not None:
                        slot["percent"] = max(0.0, min(100.0, pct))
                _publish()

            try:
                if is_download_cancel_requested(base):
                    break
                info = vd.get_video_info(url) or {}
                if ep.get("title"):
                    info["title"] = ep.get("title")
                if series_name:
                    info["series"] = series_name
                if season_number is not None:
                    info["season_number"] = season_number
                if ep.get("episode_number") is not None:
                    info["episode_number"] = ep.get("episode_number")
                if is_download_cancel_requested(base):
                    break
                success, _fp, err = vd.download_video(
                    url,
                    output_dir=out_dir,
                    quality=quality,
                    output_format=out_fmt,
                    download_playlist=False,
                    progress_callback=_prog,
                    video_info=info,
                    is_series=bool(series_name),
                    series_name=series_name or None,
                    season_number=season_number,
                    playlist_index=ep.get("playlist_index") or ep.get("episode_number"),
                    speed_limit=speed_limit,
                    embed_metadata=True,
                    gui_instance=cancel_bridge,
                    gpu_enabled=bool(settings.get("gpu_enabled", False)) and max_c == 1,
                    gpu_vendor=settings.get("gpu_vendor", "auto"),
                )
                aborted_now = is_download_cancel_requested(base) or bool(getattr(cancel_bridge, "video_download_cancelled", False))
                if aborted_now or (err and "abgebrochen" in str(err).lower()):
                    _log(f"Abgebrochen: {title}")
                    with state_lock:
                        active.pop(i, None)
                    _publish()
                    break
                if success:
                    with count_lock:
                        ok += 1
                    mark_downloaded_episodes(
                        base,
                        urls=[url],
                        episode_ids=[str(ep["id"])] if ep.get("id") else None,
                    )
                    with state_lock:
                        if i in active:
                            active[i]["percent"] = 100.0
                    _publish()
                else:
                    with count_lock:
                        fail += 1
                    _log(f"Fehlgeschlagen: {err}")
            except Exception as e:
                with count_lock:
                    fail += 1
                _log(f"Fehler: {e}")
            finally:
                with state_lock:
                    active.pop(i, None)
                _publish()

    threads = [threading.Thread(target=_worker, daemon=True) for _ in range(max_c)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    aborted = is_download_cancel_requested(base) or bool(should_cancel and should_cancel())
    clear_download_status(base, phase="idle")
    return ok, fail, aborted


_last_open_main_ts = 0.0


def _macos_gui_pids() -> List[int]:
    """PIDs des Hauptfensters (ohne Tray-Helfer)."""
    me = os.getpid()
    found: List[int] = []
    try:
        import subprocess

        out = subprocess.check_output(
            ["pgrep", "-lf", "Universal Downloader.app/Contents/MacOS/Universal Downloader"],
            text=True,
            timeout=2,
        )
    except Exception:
        return found
    for line in out.splitlines():
        if "--series-watch-tray" in line:
            continue
        try:
            pid = int(line.split(None, 1)[0])
        except ValueError:
            continue
        if pid != me:
            found.append(pid)
    return found


def _gui_lock_pid() -> Optional[int]:
    """PID des laufenden Hauptfensters, oder None."""
    lock = Path.home() / ".universal_downloader.lock"
    try:
        pid = int((lock.read_text(encoding="utf-8") or "0").strip().split()[0])
    except Exception:
        return None
    if pid <= 0 or pid == os.getpid():
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def _other_main_pids() -> List[int]:
    """Laufende Hauptfenster, ohne den Tray-Helfer und ohne diesen Prozess."""
    me = os.getpid()
    found: List[int] = []
    try:
        import subprocess

        out = subprocess.check_output(
            ["ps", "-u", str(os.getuid()), "-o", "pid=,args="],
            text=True,
            timeout=2,
        )
    except Exception:
        return found
    for line in out.splitlines():
        if "--series-watch-tray" in line:
            continue
        if "start.py" not in line and "universal-downloader" not in line and "UniversalDownloader" not in line:
            continue
        try:
            pid = int(line.split(None, 1)[0])
        except ValueError:
            continue
        if pid != me:
            found.append(pid)
    return found


def _macos_activate_pid(pid: int) -> bool:
    """Holt einen bestehenden GUI-Prozess nach vorn (nicht den Tray-Helfer)."""
    try:
        from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
        if app is None:
            return False
        app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        return True
    except Exception:
        pass
    try:
        import subprocess

        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "System Events" to set frontmost of '
                f"(first process whose unix id is {int(pid)}) to true",
            ],
            capture_output=True,
            timeout=2,
            check=False,
        )
        return True
    except Exception:
        return False


def find_main_app_command() -> List[str]:
    """Befehl zum Starten der Haupt-App (plattformabhängig)."""
    import shutil
    import sys

    root = Path(__file__).resolve().parent
    start_py = root / "start.py"

    if sys.platform == "darwin":
        for app in (
            Path("/Applications/Universal Downloader.app"),
            Path.home() / "Applications" / "Universal Downloader.app",
            root / "dist" / "Universal Downloader.app",
        ):
            if app.exists():
                return ["open", "-a", str(app)]
        if start_py.exists():
            return [sys.executable, str(start_py)]
    elif sys.platform == "win32":
        for exe in (
            root / "dist" / "UniversalDownloader" / "UniversalDownloader.exe",
            root / "UniversalDownloader.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Universal Downloader" / "UniversalDownloader.exe",
        ):
            if exe and Path(exe).exists():
                return [str(exe)]
        if start_py.exists():
            return [sys.executable, str(start_py)]
    else:
        for name in ("universal-downloader", "UniversalDownloader"):
            which = shutil.which(name)
            if which:
                return [which]
        if start_py.exists():
            return [sys.executable, str(start_py)]
    if start_py.exists():
        return [sys.executable, str(start_py)]
    return []


def _request_show_main_window() -> None:
    """Bitten das versteckte Hauptfenster, sich wieder zu zeigen."""
    try:
        from path_helper import get_app_base_path
        p = Path(get_app_base_path()) / "series_watch_show_window"
        p.write_text("1", encoding="utf-8")
    except Exception:
        pass


def open_main_app() -> bool:
    """Startet/aktiviert das Hauptprogramm. True bei Startversuch."""
    import subprocess
    import sys
    import time

    global _last_open_main_ts

    if sys.platform == "darwin":
        now = time.time()
        if now - _last_open_main_ts < 2.5:
            return True
        for pid in _macos_gui_pids():
            _last_open_main_ts = now
            _request_show_main_window()
            return _macos_activate_pid(pid)
        gui_pid = _gui_lock_pid()
        if gui_pid and gui_pid != os.getpid():
            _last_open_main_ts = now
            _request_show_main_window()
            if _macos_activate_pid(gui_pid):
                return True
        # Nicht „open -a“: das aktiviert den Tray derselben .app.
        if getattr(sys, "frozen", False):
            cmd = [sys.executable]
        else:
            start_py = Path(__file__).resolve().parent / "start.py"
            if start_py.exists():
                cmd = [sys.executable, str(start_py)]
            else:
                cmd = find_main_app_command()
                if cmd and cmd[0] == "open":
                    cmd = ["open", "-n", *cmd[1:]]
        if not cmd:
            return False
        try:
            _last_open_main_ts = now
            subprocess.Popen(cmd, start_new_session=True, close_fds=True)
            return True
        except Exception:
            return False

    now = time.time()
    if now - _last_open_main_ts < 2.5:
        return True
    if _gui_lock_pid() or _other_main_pids():
        _last_open_main_ts = now
        _request_show_main_window()
        return True

    cmd = find_main_app_command()
    if not cmd:
        return False
    try:
        _last_open_main_ts = now
        if sys.platform == "win32":
            from path_helper import win_hidden_kwargs
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            extra = win_hidden_kwargs()
            extra["creationflags"] = extra.get("creationflags", 0) | flags
            subprocess.Popen(cmd, **extra)
        else:
            subprocess.Popen(cmd, start_new_session=True)
        return True
    except Exception:
        return False
