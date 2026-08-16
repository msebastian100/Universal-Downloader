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

    u = normalize_ardmediathek_watch_url((url or "").strip())
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
            eurl = (e.get("url") or "").strip()
            if eurl and not eurl.startswith("http"):
                eurl = "https://www.ardmediathek.de" + (eurl if eurl.startswith("/") else "/" + eurl)
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
        norm = normalize_ardmediathek_watch_url(url)
        if norm != url:
            it["url"] = norm
            url = norm

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
