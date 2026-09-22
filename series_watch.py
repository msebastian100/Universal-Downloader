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
        hid = _have_ids_as_set(it)
        before = len(hid)
        episodes = it.get("episodes")
        if not isinstance(episodes, dict):
            episodes = {}
            it["episodes"] = episodes

        for eid in id_set:
            if eid:
                hid.add(eid)

        for eid, meta in list(episodes.items()):
            if not isinstance(meta, dict):
                continue
            eu = _normalize_url_key(meta.get("url") or "")
            if eu and eu in url_keys:
                hid.add(str(eid))

        # Falls URL bekannt, aber noch keine Episode-ID in episodes: ID aus URL-Ende ableiten
        for u in urls:
            uk = _normalize_url_key(u)
            if not uk:
                continue
            # z. B. …/urn:ard:episode:xxx oder youtube id
            m = re.search(r"(urn:ard:(?:episode|section|extra):[a-f0-9]+)", uk, re.I)
            if m:
                hid.add(m.group(1))
            for eid, meta in episodes.items():
                if isinstance(meta, dict) and _normalize_url_key(meta.get("url") or "") == uk:
                    hid.add(str(eid))

        if len(hid) > before:
            added += len(hid) - before
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
        })
    return out


def is_episode_had(ep: Dict[str, Any], it: Dict[str, Any]) -> bool:
    """True, wenn die Folge laut Nutzer-Angaben „schon vorhanden“ ist (kein Hinweis nötig)."""
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

        merge_have_ids_from_current(it, current)

        it["playlist_title"] = ptitle
        it["last_check"] = time.strftime("%Y-%m-%d %H:%M:%S")

        if not baseline:
            for ep in current:
                episodes[ep["id"]] = {"title": ep["title"], "url": ep.get("url") or ""}
            it["baseline_done"] = True
            it["max_season_seen"] = max_season_in_episodes(episodes)
            continue

        old_ids = set(episodes.keys())
        new_eps = [ep for ep in current if ep["id"] not in old_ids]
        for ep in current:
            if ep["id"] in episodes:
                episodes[ep["id"]] = {"title": ep["title"], "url": ep.get("url") or ""}

        new_eps = [ep for ep in new_eps if not is_episode_had(ep, it)]

        if not new_eps:
            it["max_season_seen"] = max(max_seen, max_season_in_episodes(episodes))
            continue

        seasons_new = [season_from_title(ep["title"]) for ep in new_eps]
        seasons_new_n = [s for s in seasons_new if s is not None]
        is_new_season = bool(seasons_new_n) and max(seasons_new_n) > max_seen

        for ep in new_eps:
            episodes[ep["id"]] = {"title": ep["title"], "url": ep.get("url") or ""}
        it["max_season_seen"] = max(max_seen, max_season_in_episodes(episodes))

        notifications.append(
            {
                "watch_name": name,
                "series_url": url,
                "playlist_title": ptitle,
                "is_new_season": is_new_season,
                "new_episodes": [{"title": ep["title"], "url": ep.get("url") or "", "id": ep.get("id")} for ep in new_eps],
            }
        )

    save_state(base, state)
    return state, notifications


def format_notification_text(n: Dict[str, Any]) -> Tuple[str, str]:
    """Titel und mehrzeiliger Text für Desktop/Mail/Telegram/Discord."""
    if n.get("is_new_season"):
        title = f"Neue Staffel: {n.get('watch_name')}"
    else:
        title = f"Neue Folgen: {n.get('watch_name')}"

    lines = [
        f"Playlist: {n.get('playlist_title') or ''}",
        f"Link: {n.get('series_url') or ''}",
        "",
        "Neu:",
    ]
    for ep in n.get("new_episodes") or []:
        t = ep.get("title") or ""
        u = ep.get("url") or ""
        if u:
            lines.append(f"• {t}\n  {u}")
        else:
            lines.append(f"• {t}")
    body = "\n".join(lines)
    return title, body


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


def write_runtime_status(base: Path, **fields: Any) -> None:
    """Aktualisiert den gemeinsamen Runtime-Status (GUI + Tray)."""
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
        pending=[],
        cancel_requested=False,
    )


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
        if not item_wants_auto_download(it, settings):
            continue
        name = (n.get("watch_name") or "").strip()
        kind = watch_item_kind(it, url)
        for ep in episodes_for_video_download(
            n.get("new_episodes") or [], name, kind=kind, series_url=url
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
) -> Tuple[int, int]:
    """
    Lädt Folgen ohne GUI (Tray-Helper). Markiert have_ids bei Erfolg.
    progress_callback(percent, status_line, meta) – meta: title/series/index/total
    should_cancel() -> True bricht ab.
    Rückgabe: (success_count, fail_count)
    """
    settings = settings or load_app_settings(base)
    _log = log or (lambda _m: None)
    if not episodes:
        return 0, 0
    try:
        from video_downloader import VideoDownloader
    except Exception as e:
        _log(f"VideoDownloader nicht ladbar: {e}")
        return 0, len(episodes)

    video_path = Path(settings.get("default_video_path") or (Path(base) / "Video"))
    music_path = Path(settings.get("default_music_path") or (Path(base) / "Musik"))
    quality = settings.get("default_video_quality") or "best"
    output_format = settings.get("default_video_format") or "mp4"
    try:
        vd = VideoDownloader(
            download_path=str(video_path),
            quality=quality,
            output_format=output_format,
            gui_instance=None,
        )
    except Exception as e:
        _log(f"VideoDownloader Init fehlgeschlagen: {e}")
        return 0, len(episodes)

    ok = 0
    fail = 0
    speed_limit = None
    if settings.get("speed_limit_enabled", False):
        try:
            speed_limit = float(settings.get("speed_limit_value", "5"))
        except (TypeError, ValueError):
            speed_limit = None

    total = len(episodes)
    write_runtime_status(base, cancel_requested=False, phase="downloading")

    for i, ep in enumerate(episodes, 1):
        if should_cancel and should_cancel():
            _log("Download abgebrochen.")
            break
        if is_download_cancel_requested(base):
            _log("Download abgebrochen (Tray).")
            break

        url = (ep.get("url") or "").strip()
        if not url:
            fail += 1
            continue
        is_audio = (ep.get("kind") == "audio") or is_audio_watch_url(url) or is_audio_watch_url(
            ep.get("series_url") or ""
        )
        out_dir = music_path if is_audio else video_path
        out_fmt = "mp3" if is_audio else output_format
        title = ep.get("title") or url
        series_name = ep.get("series") or ep.get("series_name") or ""
        season_number = ep.get("season_number")
        pending_rest = [
            {
                "title": (x.get("title") or "")[:80],
                "series": (x.get("series") or x.get("series_name") or "")[:60],
            }
            for x in episodes[i:]
        ]
        set_download_progress(
            base,
            title=title,
            series=series_name,
            percent=0.0,
            index=i,
            total=total,
            pending=pending_rest,
        )
        _log(f"Download [{i}/{total}]: {title}")

        def _prog(percent, status_line, _title=title, _series=series_name, _i=i):
            set_download_progress(
                base,
                title=_title,
                series=_series,
                percent=percent,
                index=_i,
                total=total,
                pending=pending_rest,
            )
            if progress_callback:
                try:
                    progress_callback(
                        percent,
                        status_line or "",
                        {"title": _title, "series": _series, "index": _i, "total": total},
                    )
                except Exception:
                    pass

        try:
            info = vd.get_video_info(url) or {}
            if ep.get("title"):
                info["title"] = ep.get("title")
            if series_name:
                info["series"] = series_name
            if season_number is not None:
                info["season_number"] = season_number
            if ep.get("episode_number") is not None:
                info["episode_number"] = ep.get("episode_number")

            if should_cancel and should_cancel():
                break
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
                gui_instance=None,
                gpu_enabled=bool(settings.get("gpu_enabled", False)),
                gpu_vendor=settings.get("gpu_vendor", "auto"),
            )
            if success:
                ok += 1
                mark_downloaded_episodes(
                    base,
                    urls=[url],
                    episode_ids=[str(ep["id"])] if ep.get("id") else None,
                )
                set_download_progress(
                    base,
                    title=title,
                    series=series_name,
                    percent=100.0,
                    index=i,
                    total=total,
                    pending=pending_rest,
                )
            else:
                fail += 1
                _log(f"Fehlgeschlagen: {err}")
        except Exception as e:
            fail += 1
            _log(f"Fehler: {e}")

    clear_download_status(base, phase="idle")
    return ok, fail


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


def open_main_app() -> bool:
    """Startet/aktiviert das Hauptprogramm. True bei Startversuch."""
    import subprocess
    import sys

    cmd = find_main_app_command()
    if not cmd:
        return False
    try:
        if sys.platform == "darwin" and cmd[0] == "open":
            subprocess.Popen(cmd)
        elif sys.platform == "win32":
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
