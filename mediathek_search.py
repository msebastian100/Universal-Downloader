# -*- coding: utf-8 -*-
"""Suche in der ARD-Mediathek: Serien mit verfügbaren Staffeln und einzelne Filme."""

import json
import os
import re
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_SE = re.compile(r"\(S\s*(\d+)\s*/\s*E\s*(\d+)\)", re.IGNORECASE)
_AD = "audiodeskription"


def _contexts():
    verified = ssl.create_default_context()
    try:
        import certifi
        verified.load_verify_locations(certifi.where())
    except Exception:
        pass
    loose = ssl._create_unverified_context()
    return (verified, loose)


def _get_json(url, timeout=25, headers=None):
    last = None
    hdrs = {"User-Agent": _UA, "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    curl = "/usr/bin/curl"
    if os.path.isfile(curl):
        try:
            cmd = [curl, "-fsS", "--max-time", str(timeout)]
            for key, value in hdrs.items():
                cmd.extend(["-H", f"{key}: {value}"])
            cmd.append(url)
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout + 5,
            )
            if proc.returncode == 0 and proc.stdout:
                return json.loads(proc.stdout.decode("utf-8", errors="replace"))
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            if err:
                last = RuntimeError(err[:240])
        except Exception as exc:
            last = exc
    for ctx in _contexts():
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            last = exc
    if last:
        raise last
    raise RuntimeError("ARD-Suche nicht erreichbar")


def _slug(title: str) -> str:
    text = (title or "").lower()
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "video"


def video_page(asset_id: str) -> str:
    return f"https://www.ardmediathek.de/video/{asset_id}"


def series_page(title: str, asset_id: str, season: int = 1) -> str:
    return (
        f"https://www.ardmediathek.de/serie/{_slug(title)}"
        f"/staffel-{season}/{asset_id}/{season}"
    )


def _image_src(images: dict, width: int = 320) -> str:
    if not isinstance(images, dict):
        return ""
    img = images.get("aspect16x9") or images.get("16x9") or images.get("aspect1x1") or images.get("1x1") or {}
    src = (img.get("src") or "").replace("{width}", str(width))
    return src


def _query_tokens(query: str) -> list:
    return [part for part in re.split(r"\s+", (query or "").casefold()) if len(part) >= 3]


def _mentions(query: str, *parts) -> bool:
    tokens = _query_tokens(query)
    if not tokens:
        return True
    hay = " ".join(str(part or "") for part in parts).casefold()
    return all(re.search(rf"(?<![a-z0-9äöüß]){re.escape(token)}(?![a-z0-9äöüß])", hay) for token in tokens)


def _is_ad(title: str) -> bool:
    return _AD in (title or "").lower()


def _publisher(item: dict) -> str:
    pub = item.get("publicationService") or {}
    return (pub.get("name") or "").strip()


def _partner(item: dict) -> str:
    pub = item.get("publicationService") or {}
    partner = (pub.get("partner") or "").strip()
    if partner:
        return partner
    target = ((item.get("links") or {}).get("target") or {})
    return (target.get("partner") or "ard").strip() or "ard"


def _asset_id(item: dict) -> str:
    target = ((item.get("links") or {}).get("target") or {})
    return (target.get("urlId") or target.get("id") or item.get("id") or "").strip()


def _ard_search_page(query: str, vod_page: int = 0) -> dict:
    # Dieselbe Schreibweise, damit „Altes Fossil“ und „altes fossil“ dieselben Seiten treffen.
    url = "https://api.ardmediathek.de/page-gateway/pages/ard/search?" + urllib.parse.urlencode({
        "searchString": query.casefold(),
        "showPageNumber": 0,
        "showPageSize": 12,
        "vodPageNumber": vod_page,
        "vodPageSize": 24,
    })
    return _get_json(url)


def search_ard(query: str) -> list:
    """Serien und Filme zur Suchanfrage. Einzelne Folgen einer gefundenen Serie bleiben in der Staffelansicht."""
    query = (query or "").strip()
    if not query:
        return []
    data = _ard_search_page(query, 0)
    shows = data.get("showResults") or []
    results = []
    for show in shows:
        if not isinstance(show, dict):
            continue
        title = (show.get("longTitle") or show.get("mediumTitle") or "").strip()
        if not title or _is_ad(title) or not _mentions(query, title):
            continue
        asset_id = _asset_id(show)
        if not asset_id:
            continue
        seasons_raw = show.get("availableSeasons") or []
        seasons = []
        for value in seasons_raw:
            try:
                seasons.append(int(value))
            except (TypeError, ValueError):
                continue
        seasons = sorted(set(seasons))
        core = (show.get("coreAssetType") or "").upper()
        is_series = core == "SEASON_SERIES" or bool(seasons)
        partner = _partner(show)
        entry = {
            "kind": "series" if is_series else "movie",
            "source": "ard",
            "title": title,
            "publisher": _publisher(show),
            "partner": partner,
            "asset_id": asset_id,
            "image": _image_src(show.get("images") or {}),
            "seasons": seasons,
            "url": series_page(title, asset_id, seasons[0] if seasons else 1) if is_series else "",
        }
        if not is_series:
            film = _main_film(partner, asset_id)
            if not film or not film.get("url"):
                # Nur der Titel liegt in der Suche, ohne abspielbaren Film.
                continue
            entry["url"] = film["url"]
            entry["duration"] = film.get("duration") or 0
            if film.get("image"):
                entry["image"] = film["image"]
        target = ((show.get("links") or {}).get("target") or {})
        entry["page_url"] = (target.get("href") or "").strip()
        results.append(entry)
    videos = []
    seen_videos = set()
    seen_series = {row.get("asset_id") for row in results}
    for page in range(3):
        page_data = data if page == 0 else _ard_search_page(query, page)
        for vod in page_data.get("vodResults") or []:
            if not isinstance(vod, dict):
                continue
            title = (vod.get("longTitle") or vod.get("mediumTitle") or "").strip()
            asset_id = _asset_id(vod)
            core = (vod.get("coreAssetType") or "").upper()
            if not title or not asset_id or asset_id in seen_videos or _is_ad(title) or "TRAILER" in core or "trailer" in title.casefold():
                continue
            if not _mentions(query, title):
                continue
            seen_videos.add(asset_id)
            show = vod.get("show") if isinstance(vod.get("show"), dict) else {}
            series_name = ""
            if core == "EPISODE":
                home = show.get("homepage") if isinstance(show.get("homepage"), dict) else {}
                series_name = (show.get("title") or home.get("title") or "").strip()
                parent = _ard_series_from_show(show, _publisher(vod), _partner(vod))
                if parent and parent["asset_id"] not in seen_series:
                    seen_series.add(parent["asset_id"])
                    results.append(parent)
            videos.append({
                "kind": "movie" if core in ("SINGLE", "MOVIE") else "video",
                "source": "ard",
                "title": title,
                "series_name": series_name,
                "publisher": _publisher(vod),
                "partner": _partner(vod),
                "asset_id": asset_id,
                "image": _image_src(vod.get("images") or {}),
                "seasons": [],
                "url": video_page(asset_id),
                "duration": int(vod.get("duration") or 0),
            })
            if len(videos) >= 8:
                break
        if len(videos) >= 8:
            break
    results.extend(videos)
    if any(row.get("page_url") for row in results):
        _attach_blurbs(results)
    _attach_item_texts([row for row in results if row.get("kind") != "series"])
    return results


def _ard_series_from_show(show: dict, publisher: str, partner: str):
    if not isinstance(show, dict):
        return None
    if (show.get("coreAssetType") or "").upper() != "SEASON_SERIES":
        return None
    home = show.get("homepage") if isinstance(show.get("homepage"), dict) else {}
    title = (show.get("title") or home.get("title") or "").strip()
    asset_id = (show.get("id") or home.get("id") or "").strip()
    if not title or not asset_id:
        return None
    seasons = []
    for value in show.get("availableSeasons") or []:
        try:
            seasons.append(int(value))
        except (TypeError, ValueError):
            continue
    seasons = sorted(set(seasons))
    return {
        "kind": "series",
        "source": "ard",
        "title": title,
        "publisher": publisher,
        "partner": partner or "ard",
        "asset_id": asset_id,
        "image": _image_src(show.get("images") or {}),
        "seasons": seasons,
        "url": series_page(title, asset_id, seasons[0] if seasons else 1),
    }


def _blurb(page_url: str) -> str:
    if not page_url:
        return ""
    try:
        data = _get_json(page_url, timeout=12)
    except Exception:
        return ""
    text = data.get("synopsis") or data.get("shortSynopsis") or data.get("descriptionSeo") or ""
    text = " ".join(str(text).split())
    if len(text) > 180:
        text = text[:177] + "…"
    return text


def _attach_blurbs(results: list) -> None:
    pending = [row for row in results if row.get("page_url")]
    if not pending:
        return
    with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
        futures = {pool.submit(_blurb, row["page_url"]): row for row in pending}
        for future in as_completed(futures):
            row = futures[future]
            try:
                row["description"] = future.result() or ""
            except Exception:
                row["description"] = ""


def fetch_item_details(partner: str, asset_id: str) -> dict:
    """Beschreibung, Jahr, Ausstrahlung, FSK, Mitwirkende und Bild eines ARD-Beitrags."""
    asset_id = (asset_id or "").strip()
    if not asset_id:
        return {}
    partner = (partner or "ard").strip() or "ard"
    url = (
        f"https://api.ardmediathek.de/page-gateway/pages/{urllib.parse.quote(partner)}"
        f"/item/{urllib.parse.quote(asset_id)}?embedded=true"
    )
    try:
        data = _get_json(url, timeout=15)
    except Exception:
        if partner != "ard":
            return fetch_item_details("ard", asset_id)
        return {}
    player = None
    for widget in data.get("widgets") or []:
        if isinstance(widget, dict) and (widget.get("synopsis") or widget.get("type") == "player_ondemand"):
            player = widget
            break
    if not player:
        return {}
    raw = str(player.get("synopsis") or "").strip()
    synopsis = " ".join(raw.split())
    first_line = raw.split("\n", 1)[0]
    year_match = re.search(r"\b(?:19|20)\d{2}\b", first_line)
    names = re.findall(r"\(([A-ZÄÖÜ][^)]{2,60})\)", raw)
    cast = []
    for name in names:
        name = " ".join(name.split())
        if re.fullmatch(r"(?:19|20)\d{2}", name):
            continue
        if name not in cast:
            cast.append(name)
    image = player.get("image") or {}
    src = (image.get("src") or "").replace("{width}", "640")
    broadcast = str(player.get("broadcastedOn") or "")
    if len(broadcast) >= 10:
        broadcast = broadcast[:10]
    return {
        "title": player.get("title") or data.get("title") or "",
        "synopsis": synopsis,
        "year": year_match.group(0) if year_match else "",
        "broadcast": broadcast,
        "fsk": str(player.get("maturityContentRating") or ""),
        "publisher": ((player.get("publicationService") or {}).get("name") or ""),
        "cast": cast[:8],
        "image": src,
    }


def _attach_item_texts(results: list) -> None:
    pending = [row for row in results if row.get("asset_id") and not (row.get("description") or "").strip()]
    if not pending:
        return
    with ThreadPoolExecutor(max_workers=min(4, len(pending))) as pool:
        futures = {
            pool.submit(fetch_item_details, row.get("partner") or "ard", row["asset_id"]): row
            for row in pending
        }
        for future in as_completed(futures):
            row = futures[future]
            try:
                info = future.result() or {}
            except Exception:
                info = {}
            text = info.get("synopsis") or ""
            if len(text) > 220:
                text = text[:217] + "…"
            if text:
                row["description"] = text
            if info.get("year"):
                row["year"] = info["year"]
            if info.get("image") and not row.get("image"):
                row["image"] = info["image"]
            if info.get("publisher") and not row.get("publisher"):
                row["publisher"] = info["publisher"]


def _main_film(partner: str, asset_id: str) -> dict:
    url = (
        f"https://api.ardmediathek.de/page-gateway/widgets/{urllib.parse.quote(partner)}/asset/"
        f"{urllib.parse.quote(asset_id)}?pageNumber=0&pageSize=12&embedded=true"
    )
    try:
        data = _get_json(url, timeout=20)
    except Exception:
        return {}
    best = None
    for teaser in data.get("teasers") or []:
        if not isinstance(teaser, dict):
            continue
        title = (teaser.get("longTitle") or "").strip()
        tid = (teaser.get("id") or "").strip()
        core = (teaser.get("coreAssetType") or "").upper()
        if not tid or _is_ad(title) or "TRAILER" in core or "trailer" in title.casefold():
            continue
        duration = int(teaser.get("duration") or 0)
        if best is None or duration > best["duration"]:
            best = {
                "url": video_page(tid),
                "duration": duration,
                "image": _image_src(teaser.get("images") or {}),
            }
    return best or {}


def _season_episodes(partner: str, asset_id: str, series_title: str, season: int) -> list:
    url = (
        f"https://api.ardmediathek.de/page-gateway/widgets/{urllib.parse.quote(partner)}/asset/"
        f"{urllib.parse.quote(asset_id)}?pageNumber=0&pageSize=100&seasoned=true&seasonNumber={season}"
    )
    data = _get_json(url, timeout=25)
    episodes = []
    seen = set()
    for teaser in data.get("teasers") or []:
        if not isinstance(teaser, dict):
            continue
        title = (teaser.get("longTitle") or teaser.get("mediumTitle") or "").strip()
        tid = (teaser.get("id") or "").strip()
        if not tid or not title or _is_ad(title) or tid in seen:
            continue
        seen.add(tid)
        season_no, episode_no = season, None
        match = _SE.search(title)
        if match:
            season_no = int(match.group(1))
            episode_no = int(match.group(2))
        episodes.append({
            "id": tid,
            "url": video_page(tid),
            "title": title,
            "series": series_title,
            "series_name": series_title,
            "season_number": season_no,
            "episode_number": episode_no,
            "duration": int(teaser.get("duration") or 0),
        })
    episodes.sort(key=lambda ep: (ep.get("episode_number") is None, ep.get("episode_number") or 0, ep.get("title") or ""))
    return episodes


def load_series_seasons(item: dict) -> dict:
    """Staffelnummer -> Folgen, die in der Mediathek gerade liegen."""
    if (item.get("source") or "") == "zdf":
        return _zdf_series_seasons(item)
    if (item.get("source") or "") == "audiothek":
        return _audiothek_episodes(item)
    partner = (item.get("partner") or "ard").strip()
    asset_id = (item.get("asset_id") or "").strip()
    title = (item.get("title") or "").strip()
    seasons = list(item.get("seasons") or [])
    if not asset_id:
        return {}
    if not seasons:
        seasons = [None]
    out = {}
    workers = min(6, max(1, len(seasons)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for season in seasons:
            if season is None:
                continue
            futures[pool.submit(_season_episodes, partner, asset_id, title, int(season))] = int(season)
        for future in as_completed(futures):
            season = futures[future]
            try:
                rows = future.result()
            except Exception:
                rows = []
            if rows:
                out[season] = rows
    return out


def search_audiothek(query: str) -> list:
    """Hörspiele und Podcasts in der ARD Audiothek. Sendungen vor einzelnen Folgen."""
    query = (query or "").strip()
    if not query:
        return []
    url = "https://api.ardaudiothek.de/search?" + urllib.parse.urlencode({"query": query})
    data = _get_json(url, timeout=20)
    search = ((data.get("data") or {}).get("search") or {})
    results = []
    seen = set()
    for node in ((search.get("programSets") or {}).get("nodes") or [])[:8]:
        if not isinstance(node, dict):
            continue
        title = (node.get("title") or "").strip()
        page = (node.get("sharingUrl") or "").strip()
        if not title or not page or page in seen:
            continue
        seen.add(page)
        image = ((node.get("image") or {}).get("url") or "").replace("{width}", "320")
        count = int(node.get("numberOfElements") or 0)
        publisher = ((node.get("publicationService") or {}).get("title") or "ARD Audiothek")
        text = " ".join(str(node.get("synopsis") or "").split())
        if len(text) > 220:
            text = text[:217] + "…"
        results.append({
            "kind": "audio",
            "source": "audiothek",
            "title": title,
            "publisher": publisher,
            "partner": "audiothek",
            "asset_id": str(node.get("id") or "").strip(),
            "url": page,
            "image": image,
            "description": text,
            "episode_count": count,
            "seasons": [],
        })
    if results:
        return results
    for node in ((search.get("items") or {}).get("nodes") or [])[:8]:
        if not isinstance(node, dict):
            continue
        title = (node.get("title") or "").strip()
        page = (node.get("sharingUrl") or "").strip()
        if not title or not page or page in seen or "trailer" in title.casefold():
            continue
        seen.add(page)
        text = " ".join(str(node.get("synopsis") or "").split())
        if len(text) > 220:
            text = text[:217] + "…"
        results.append({
            "kind": "audio",
            "source": "audiothek",
            "title": title,
            "publisher": "ARD Audiothek",
            "url": page,
            "image": "",
            "description": text,
            "duration": int(node.get("duration") or 0),
            "seasons": [],
        })
    return results


def _audiothek_episodes(item: dict) -> dict:
    """Alle Folgen einer Hörspiel- oder Podcast-Sendung, neueste zuerst."""
    program_id = (item.get("asset_id") or "").strip()
    series = (item.get("title") or "").strip()
    if not program_id:
        return {}
    episodes = []
    seen = set()
    offset = 0
    while offset < 500:
        data = _get_json(
            f"https://api.ardaudiothek.de/programsets/{urllib.parse.quote(program_id)}?limit=100&offset={offset}",
            timeout=25,
        )
        nodes = (((data.get("data") or {}).get("programSet") or {}).get("items") or {}).get("nodes") or []
        if not nodes:
            break
        for node in nodes:
            if not isinstance(node, dict):
                continue
            title = (node.get("title") or "").strip()
            page = (node.get("sharingUrl") or "").strip()
            eid = str(node.get("id") or page or "").strip()
            if not title or not page or eid in seen or "trailer" in title.casefold():
                continue
            seen.add(eid)
            picture = node.get("image") if isinstance(node.get("image"), dict) else {}
            cover = (picture.get("url1X1") or picture.get("url") or "").replace("{width}", "640")
            stream_url = ""
            for audio in node.get("audios") or []:
                if not isinstance(audio, dict):
                    continue
                candidate = (audio.get("url") or audio.get("downloadUrl") or "").strip()
                if candidate.startswith("http"):
                    stream_url = candidate
                    break
            episodes.append({
                "image": cover,
                "stream_url": stream_url,
                "id": eid,
                "url": page,
                "title": title,
                "series": series,
                "series_name": series,
                "season_number": None,
                "episode_number": None,
                "duration": int(node.get("duration") or 0),
                "kind": "audio",
                "output_format": "mp3",
            })
        if len(nodes) < 100:
            break
        offset += 100
    if not episodes:
        return {}
    return {None: episodes}


_ZDF_TOKEN = {"expires": 0, "header": ""}
_ZDF_TARGET = "http://zdf.de/rels/target"
_ZDF_RESULTS = "http://zdf.de/rels/search/results"
_ZDF_SHARING = "http://zdf.de/rels/sharing-url"


def _zdf_auth() -> str:
    now = int(time.time())
    if _ZDF_TOKEN["header"] and int(_ZDF_TOKEN["expires"] or 0) > now + 120:
        return _ZDF_TOKEN["header"]
    data = _get_json("https://zdf-prod-futura.zdf.de/mediathekV2/token", timeout=15)
    header = f"{data.get('type') or 'Bearer'} {data.get('token') or ''}".strip()
    if not data.get("token"):
        raise RuntimeError("ZDF-Zugang abgelaufen")
    _ZDF_TOKEN["header"] = header
    _ZDF_TOKEN["expires"] = int(data.get("expires") or 0)
    return header


def _zdf_get(url: str, timeout=20):
    return _get_json(url, timeout=timeout, headers={
        "Api-Auth": _zdf_auth(),
        "Accept": "application/vnd.de.zdf.v1.0+json",
    })


def _zdf_image(ref) -> str:
    layouts = (ref or {}).get("layouts") or {}
    if not isinstance(layouts, dict):
        return ""
    for key in ("384x216", "768x432", "1280x720", "1920x1080", "original"):
        src = layouts.get(key)
        if isinstance(src, str) and src.startswith("http"):
            return src
    for src in layouts.values():
        if isinstance(src, str) and src.startswith("http"):
            return src
    return ""


def _zdf_text(value: str, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def _zdf_mentions(query: str, *parts) -> bool:
    tokens = [part for part in re.split(r"\s+", (query or "").casefold()) if len(part) >= 3]
    if not tokens:
        return True
    hay = " ".join(str(part or "") for part in parts).casefold()
    return all(re.search(rf"(?<![a-z0-9äöüß]){re.escape(token)}(?![a-z0-9äöüß])", hay) for token in tokens)


def _zdf_target(row: dict) -> dict:
    target = row.get(_ZDF_TARGET) if isinstance(row, dict) else None
    return target if isinstance(target, dict) else {}


def _zdf_row(target: dict, kind: str) -> dict:
    title = (target.get("teaserHeadline") or target.get("title") or "").strip()
    url = (target.get(_ZDF_SHARING) or target.get("webCanonical") or "").strip()
    conf = target.get("http://zdf.de/rels/content/conf-section") or {}
    publisher = ((conf.get("homeTvService") or {}).get("tvServiceTitle") or "ZDF").strip()
    editorial = str(target.get("editorialDate") or "")
    year = editorial[:4] if len(editorial) >= 4 and editorial[:4].isdigit() else ""
    return {
        "kind": kind,
        "source": "zdf",
        "title": title,
        "publisher": publisher,
        "partner": "zdf",
        "asset_id": (target.get("structureNodePath") or "").strip(),
        "url": url,
        "image": _zdf_image(target.get("teaserImageRef")),
        "description": _zdf_text(target.get("teasertext") or ""),
        "year": year,
        "seasons": [],
    }


def _zdf_parent_series(target: dict):
    """Serie zu einer gefundenen Folge, auch wenn der Serientitel nicht im Suchbegriff steht."""
    if (target.get("contentType") or "").casefold() != "episode":
        return None
    brand = target.get("http://zdf.de/rels/brand") or {}
    inner = brand.get("http://zdf.de/rels/target") if isinstance(brand, dict) else None
    if not isinstance(inner, dict):
        return None
    if (inner.get("contentType") or "").casefold() != "brand":
        return None
    if not inner.get("hasVideo") or not inner.get("structureNodePath"):
        return None
    title = (inner.get("title") or brand.get("title") or "").strip()
    vid = (inner.get("id") or "").strip()
    if not title or not vid:
        return None
    image_ref = {}
    for stage in inner.get("stage") or []:
        if not isinstance(stage, dict):
            continue
        for teaser in stage.get("teaser") or []:
            ref = teaser.get("http://zdf.de/rels/target") if isinstance(teaser, dict) else None
            if isinstance(ref, dict) and isinstance(ref.get("layouts"), dict):
                image_ref = ref
                break
        if image_ref:
            break
    return _zdf_row({
        "title": title,
        "teaserHeadline": title,
        "structureNodePath": inner.get("structureNodePath"),
        "webCanonical": f"https://www.zdf.de/serien/{vid}",
        "teaserImageRef": image_ref,
    }, "series")


def search_zdf(query: str) -> list:
    """Serien und Filme, die in der ZDF-Mediathek liegen. Einzelne Folgen einer Serie bleiben in der Staffelansicht."""
    query = (query or "").strip()
    if not query:
        return []
    folded = query.casefold()
    url = "https://api.zdf.de/search/documents?" + urllib.parse.urlencode({
        "q": folded,
        "limit": 24,
    })
    data = _zdf_get(url)
    series = []
    videos = []
    seen = set()
    series_titles = set()
    series_paths = set()
    pending_videos = []
    for row in data.get(_ZDF_RESULTS) or []:
        target = _zdf_target(row)
        if not target.get("hasVideo"):
            continue
        title = (target.get("teaserHeadline") or target.get("title") or "").strip()
        if not title or "trailer" in title.casefold():
            continue
        if not _zdf_mentions(query, title, target.get("teasertext") or ""):
            continue
        content = (target.get("contentType") or "").casefold()
        profile = str(target.get("profile") or "")
        if content == "brand" and target.get("structureNodePath"):
            item = _zdf_row(target, "series")
            if not item["url"] or item["url"] in seen:
                continue
            seen.add(item["url"])
            series.append(item)
            series_titles.add(" ".join(title.casefold().split()))
            if item.get("asset_id"):
                series_paths.add(item["asset_id"])
            continue
        if profile.endswith("page-video-teaser"):
            pending_videos.append(target)
    for target in pending_videos:
        item = _zdf_row(target, "movie" if (target.get("contentType") or "").casefold() == "movie" else "video")
        if not item["url"] or item["url"] in seen:
            continue
        brand = target.get("http://zdf.de/rels/brand") or {}
        brand_label = str(brand.get("title") or "").strip()
        brand_title = " ".join(brand_label.casefold().split())
        if brand_title and brand_title in series_titles:
            continue
        if (target.get("contentType") or "").casefold() == "episode" and brand_label:
            item["series_name"] = brand_label
        seen.add(item["url"])
        videos.append(item)
        parent = _zdf_parent_series(target)
        if not parent or parent.get("asset_id") in series_paths or parent.get("url") in seen:
            continue
        seen.add(parent["url"])
        series_paths.add(parent.get("asset_id") or "")
        series.append(parent)
    return series[:8] + videos[:8]


def _zdf_series_seasons(item: dict) -> dict:
    path = (item.get("asset_id") or "").strip()
    title = (item.get("title") or "").strip()
    if not path:
        return {}
    episodes = []
    seen = set()
    url = "https://api.zdf.de/search/documents?" + urllib.parse.urlencode({
        "q": "",
        "paths": path,
        "contentTypes": "episode",
        "hasVideo": "true",
        "limit": 100,
        "sortBy": "date",
        "sortOrder": "desc",
    })
    for _page in range(4):
        data = _zdf_get(url, timeout=25)
        for row in data.get(_ZDF_RESULTS) or []:
            target = _zdf_target(row)
            if not target.get("hasVideo"):
                continue
            name = (target.get("teaserHeadline") or target.get("title") or "").strip()
            page = (target.get(_ZDF_SHARING) or target.get("webCanonical") or "").strip()
            vid = (target.get("id") or page or "").strip()
            if not name or not page or vid in seen or "trailer" in name.casefold():
                continue
            seen.add(vid)
            editorial = str(target.get("editorialDate") or "")
            year = int(editorial[:4]) if len(editorial) >= 4 and editorial[:4].isdigit() else 0
            episodes.append({
                "id": vid,
                "url": page,
                "title": name,
                "series": title,
                "series_name": title,
                "season_number": year or None,
                "episode_number": None,
                "duration": 0,
            })
        nxt = data.get("next") or ""
        if not nxt or not isinstance(nxt, str):
            break
        url = nxt if nxt.startswith("http") else "https://api.zdf.de" + nxt
    grouped = {}
    for episode in episodes:
        season = episode.get("season_number")
        grouped.setdefault(season if season else None, []).append(episode)
    return grouped
