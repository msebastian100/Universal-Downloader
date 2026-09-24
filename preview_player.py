# -*- coding: utf-8 -*-
"""Eigenes Vorschau-Fenster: Play, Pause und Lautstärke, ohne Browser."""

import json
import os
import subprocess
import threading

_OPEN = []
_CloseStop = None


def _close_delegate_class():
    global _CloseStop
    if _CloseStop is not None:
        return _CloseStop
    from AppKit import NSObject

    class _CloseStopCls(NSObject):
        def initWithStop_(self, stop):
            import objc
            self = objc.super(_CloseStopCls, self).init()
            if self is None:
                return None
            self.stop = stop
            return self

        def windowShouldClose_(self, sender):
            fn = getattr(self, "stop", None)
            if fn:
                fn()
                self.stop = None
            return True

        def windowWillClose_(self, notification):
            fn = getattr(self, "stop", None)
            if fn:
                fn()
                self.stop = None

    _CloseStop = _CloseStopCls
    return _CloseStop


def _unwatch(holder) -> None:
    observer = holder.get("observer")
    holder["observer"] = None
    if observer is None:
        return
    try:
        from Foundation import NSNotificationCenter
        NSNotificationCenter.defaultCenter().removeObserver_(observer)
    except Exception:
        pass


def _watch_end(holder) -> None:
    _unwatch(holder)
    player = holder.get("player")
    item = player.currentItem() if player is not None else None
    if item is None:
        return
    from Foundation import NSNotificationCenter

    def advance():
        if holder.get("closed") or holder.get("player") is None:
            return
        playlist = list(holder.get("playlist") or [])
        index = int(holder.get("playlist_index") or 0) + 1
        if index >= len(playlist):
            _save_position(holder.get("page_url") or "", 0)
            return
        nxt = playlist[index]
        holder["playlist_index"] = index
        schedule = holder.get("schedule")

        def work():
            try:
                stream = _stream_source(nxt.get("stream_url") or "", nxt.get("url") or "")
                cover = _cover_bytes(nxt.get("image") or "")
            except Exception as exc:
                report = holder.get("report_error")
                if schedule and report:
                    _report_later(schedule, report, f"Nächste Folge nicht möglich:\n{exc}")
                return

            def swap():
                pl = holder.get("player")
                if holder.get("closed") or pl is None:
                    return
                ns = holder["ns"]
                from Foundation import NSURL
                new_item = ns["AVPlayerItem"].playerItemWithURL_(NSURL.URLWithString_(stream))
                _save_position(holder.get("page_url") or "", _player_seconds(pl))
                holder["page_url"] = nxt.get("url") or ""
                start = _choose_start(holder["page_url"], nxt.get("title") or "Vorschau", holder.get("ask_resume"))
                pl.replaceCurrentItemWithPlayerItem_(new_item)
                if start >= 8:
                    try:
                        pl.seekToTime_(_cm_time(start))
                    except Exception:
                        pass
                _refresh_now_playing(holder, nxt.get("title") or "Vorschau", cover)
                _watch_end(holder)
                pl.play()

            if schedule:
                schedule(0, swap)
            else:
                swap()

        threading.Thread(target=work, daemon=True).start()

    # Observer als NSObject, damit das Folgen-Ende den nächsten Titel startet.
    if not hasattr(_watch_end, "cls"):
        from AppKit import NSObject
        import objc

        class _EndObs(NSObject):
            def initWithAdvance_(self, fn):
                self = objc.super(_EndObs, self).init()
                if self is None:
                    return None
                self.fn = fn
                return self

            def itemEnded_(self, notification):
                fn = getattr(self, "fn", None)
                if fn:
                    fn()

        _watch_end.cls = _EndObs

    observer = _watch_end.cls.alloc().initWithAdvance_(advance)
    holder["observer"] = observer
    NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
        observer,
        b"itemEnded:",
        "AVPlayerItemDidPlayToEndTimeNotification",
        item,
    )


def _positions_path() -> str:
    try:
        from path_helper import get_app_base_path
        base = str(get_app_base_path())
    except Exception:
        base = os.path.expanduser("~/Downloads/Universal Downloader")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "wiedergabe.json")


def _load_positions() -> dict:
    try:
        with open(_positions_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _saved_position(page_url: str) -> float:
    try:
        return float(_load_positions().get(page_url) or 0)
    except (TypeError, ValueError):
        return 0.0


def _save_position(page_url: str, seconds: float) -> None:
    page_url = (page_url or "").strip()
    if not page_url:
        return
    data = _load_positions()
    if seconds < 8:
        data.pop(page_url, None)
    else:
        data[page_url] = round(float(seconds), 1)
    try:
        with open(_positions_path(), "w", encoding="utf-8") as handle:
            json.dump(data, handle)
    except Exception:
        pass


def _stream_source(direct: str, page_url: str) -> str:
    direct = (direct or "").strip()
    if direct.startswith("http"):
        return _playable_url(direct)
    local = direct if direct.startswith("file:") else direct
    path = __import__("pathlib").Path(local[7:] if local.startswith("file://") else local)
    if local.startswith("file:") or path.is_file():
        return local if local.startswith("file:") else path.resolve().as_uri()
    return _resolve_stream(page_url)


def _playable_url(url: str) -> str:
    # Die gebündelte App blockt unverschlüsseltes http, der Player bleibt dann stumm.
    if (url or "").startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _cm_time(seconds: float):
    import objc
    if not hasattr(_cm_time, "typ"):
        _cm_time.typ = objc.createStructType(
            "CMTime", b"{CMTime=qiIq}", ["value", "timescale", "flags", "epoch"]
        )
    return _cm_time.typ(int(float(seconds) * 600), 600, 1, 0)


def _player_seconds(player) -> float:
    try:
        stamp = player.currentTime()
        if isinstance(stamp, (tuple, list)) and len(stamp) >= 2:
            value, scale = stamp[0], stamp[1]
        else:
            value = getattr(stamp, "value", 0)
            scale = getattr(stamp, "timescale", 0)
        scale = float(scale or 0)
        if scale <= 0:
            return 0.0
        return float(value) / scale
    except Exception:
        return 0.0


def _report_later(schedule, report_error, message) -> None:
    text = str(message)
    schedule(0, lambda m=text: report_error(m))


def _has_video(fmt) -> bool:
    return str((fmt or {}).get("vcodec") or "none") not in ("", "none")


def _stream_from_info(info) -> str:
    """Bei Serien und Filmen die Bildspur nehmen, nicht die reine Audio-Datei."""
    if not isinstance(info, dict):
        return ""
    formats = [fmt for fmt in (info.get("formats") or []) if str(fmt.get("url") or "").startswith("http")]
    video = [fmt for fmt in formats if _has_video(fmt)]
    pool = video or formats
    for fmt in pool:
        url = str(fmt.get("url") or "")
        if "m3u8" in url and "audio" not in url.lower():
            return url
    for fmt in pool:
        url = str(fmt.get("url") or "")
        if "m3u8" in url:
            return url
    direct = str(info.get("url") or "")
    if direct.startswith("http") and (_has_video(info) or "m3u8" in direct):
        return direct
    for fmt in formats:
        url = str(fmt.get("url") or "")
        if any(mark in url.lower() for mark in (".mp3", ".m4a", ".aac")):
            return url
    if direct.startswith("http"):
        return direct
    return str(pool[-1].get("url") or "") if pool else ""


def _resolve_stream(page_url: str) -> str:
    """Eingebettetes yt-dlp. Das System-yt-dlp unter /usr/local ist oft zu alt für die Audiothek."""
    try:
        import yt_dlp
        opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "format": "bv*+ba/b"}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(page_url, download=False)
        found = _stream_from_info(info)
        if found:
            return _playable_url(found)
    except Exception as exc:
        api_error = exc
    else:
        api_error = RuntimeError("kein Stream")
    from yt_dlp_helper import get_ytdlp_command
    cmd = get_ytdlp_command()
    if not cmd:
        raise RuntimeError(str(api_error)[:240])
    result = subprocess.run(
        cmd + ["-g", "-f", "b", "--no-playlist", "--no-warnings", page_url],
        capture_output=True,
        text=True,
        timeout=45,
    )
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip().startswith("http")]
    if not lines:
        err = ((result.stderr or "") + (result.stdout or "")).strip().splitlines()
        detail = err[-1] if err else str(api_error)
        raise RuntimeError(detail[:240])
    for line in lines:
        if "m3u8" in line:
            return _playable_url(line)
    return _playable_url(lines[0])


def _cover_bytes(image_url: str) -> bytes:
    image_url = (image_url or "").replace("{width}", "640").strip()
    if not image_url.startswith("http"):
        return b""
    curl = "/usr/bin/curl"
    if os.path.isfile(curl):
        try:
            proc = subprocess.run(
                [curl, "-fsS", "-A", "Mozilla/5.0", "--max-time", "12", image_url],
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0 and proc.stdout:
                return proc.stdout
        except Exception:
            pass
    try:
        import urllib.request
        req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            return resp.read()
    except Exception:
        return b""


def _playlist_text(rows, index: int) -> str:
    lines = []
    for number, row in enumerate(rows or [], start=1):
        mark = "▶" if number - 1 == index else " "
        title = (row.get("title") or "Folge").strip()
        lines.append(f"{mark}   {number}.   {title}")
    return "\n".join(lines)


def _refresh_now_playing(holder, title: str, cover: bytes) -> None:
    title = (title or "Vorschau").strip()
    label = holder.get("title_label")
    if label is not None:
        try:
            label.setStringValue_(title)
        except Exception:
            pass
    playlist_view = holder.get("playlist_view")
    if playlist_view is not None:
        try:
            playlist_view.setString_(_playlist_text(holder.get("playlist") or [], int(holder.get("playlist_index") or 0)))
        except Exception:
            pass
    try:
        word = "Anhören" if holder.get("audio") else "Ansehen"
        holder["window"].setTitle_(f"{word} – {title}"[:120])
    except Exception:
        pass
    _show_cover(holder, cover)


def _label(frame, text, size, bold=False, center=False):
    from AppKit import NSColor, NSFont, NSTextField
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text or "")
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setTextColor_(NSColor.whiteColor())
    label.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if center:
        label.setAlignment_(1)
    try:
        label.cell().setWraps_(True)
        label.setMaximumNumberOfLines_(3)
    except Exception:
        pass
    return label


def _playlist_view(frame, text):
    from AppKit import NSColor, NSFont, NSMakeSize, NSScrollView, NSTextView
    scroll = NSScrollView.alloc().initWithFrame_(frame)
    scroll.setHasVerticalScroller_(True)
    scroll.setDrawsBackground_(True)
    scroll.setBackgroundColor_(NSColor.colorWithCalibratedWhite_alpha_(0.08, 1))
    scroll.setBorderType_(0)
    text_view = NSTextView.alloc().initWithFrame_(scroll.bounds())
    text_view.setString_(text or "")
    text_view.setEditable_(False)
    text_view.setSelectable_(False)
    text_view.setDrawsBackground_(False)
    text_view.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.92, 1))
    text_view.setFont_(NSFont.systemFontOfSize_(13))
    text_view.setVerticallyResizable_(True)
    text_view.setHorizontallyResizable_(False)
    try:
        text_view.setTextContainerInset_(NSMakeSize(10, 8))
        text_view.textContainer().setWidthTracksTextView_(True)
        text_view.textContainer().setContainerSize_(NSMakeSize(frame.size.width - 16, 100000))
    except Exception:
        pass
    scroll.setDocumentView_(text_view)
    return scroll, text_view


def _show_cover(holder, raw: bytes) -> None:
    view = holder.get("image_view")
    if view is None or not raw:
        return
    try:
        from AppKit import NSImage
        from Foundation import NSData
        data = NSData.dataWithBytes_length_(raw, len(raw))
        image = NSImage.alloc().initWithData_(data)
        if image is not None:
            view.setImage_(image)
    except Exception:
        pass


def open_preview(page_url: str, title: str, schedule, report_error, ask_resume=None, on_started=None, image: str = "", stream_url: str = "") -> None:
    """schedule(ms, fn) läuft im UI-Thread, z. B. root.after."""
    page_url = (page_url or "").strip()
    if not page_url and not (stream_url or "").strip():
        report_error("Für diesen Treffer gibt es keinen Wiedergabe-Link.")
        return

    def work():
        try:
            stream = _stream_source(stream_url, page_url)
            cover = _cover_bytes(image)
        except Exception as exc:
            _report_later(schedule, report_error, f"Vorschau nicht möglich:\n{exc}")
            return
        def present():
            try:
                start = _choose_start(page_url, title or "Vorschau", ask_resume)
                _show(
                    stream,
                    title or "Vorschau",
                    page_url=page_url,
                    start_at=start,
                    cover=cover,
                    playlist=[{
                        "title": title or "Vorschau",
                        "url": page_url,
                        "image": image,
                        "stream_url": stream_url,
                    }],
                )
                if on_started:
                    on_started()
            except Exception as exc:
                report_error(f"Vorschau nicht möglich:\n{exc}")

        schedule(0, present)

    threading.Thread(target=work, daemon=True).start()


def _choose_start(page_url: str, title: str, ask_resume) -> float:
    saved = _saved_position(page_url)
    if saved < 8 or not ask_resume:
        return 0.0
    try:
        resume = bool(ask_resume(title, saved))
    except Exception:
        resume = False
    if not resume:
        _save_position(page_url, 0)
    return saved if resume else 0.0


def open_preview_list(entries, schedule, report_error, ask_resume=None, on_started=None) -> None:
    """Spielt die gewählten Folgen nacheinander. Eine einzelne Folge bleibt eine einzelne."""
    rows = [row for row in (entries or []) if (row.get("url") or row.get("stream_url") or "").strip()]
    if not rows:
        report_error("Keine Folge zum Ansehen ausgewählt.")
        return
    if len(rows) == 1:
        open_preview(
            rows[0]["url"],
            rows[0].get("title") or "Vorschau",
            schedule,
            report_error,
            ask_resume,
            on_started,
            image=rows[0].get("image") or "",
            stream_url=rows[0].get("stream_url") or "",
        )
        return
    first, rest = rows[0], rows[1:]

    def work():
        try:
            stream = _stream_source(first.get("stream_url") or "", first.get("url") or "")
            cover = _cover_bytes(first.get("image") or "")
        except Exception as exc:
            _report_later(schedule, report_error, f"Vorschau nicht möglich:\n{exc}")
            return

        def present():
            try:
                start = _choose_start(first["url"], first.get("title") or "Vorschau", ask_resume)
                _show(
                    stream,
                    first.get("title") or "Vorschau",
                    schedule,
                    report_error,
                    page_url=first["url"],
                    start_at=start,
                    ask_resume=ask_resume,
                    cover=cover,
                    playlist=rows,
                )
                if on_started:
                    on_started()
            except Exception as exc:
                report_error(f"Vorschau nicht möglich:\n{exc}")

        schedule(0, present)

    threading.Thread(target=work, daemon=True).start()


def _show(stream_url: str, title: str, schedule=None, report_error=None, page_url: str = "", start_at: float = 0, ask_resume=None, cover: bytes = b"", playlist=None, playlist_index: int = 0) -> None:
    try:
        import objc
        from AppKit import NSImageView, NSMakeRect, NSView, NSWindow
        from Foundation import NSURL
    except Exception as exc:
        raise RuntimeError(f"Player nicht verfügbar: {exc}") from exc
    ns = {}
    objc.loadBundle("AVKit", ns, bundle_path="/System/Library/Frameworks/AVKit.framework")
    objc.loadBundle("AVFoundation", ns, bundle_path="/System/Library/Frameworks/AVFoundation.framework")
    stream_url = _playable_url(stream_url)
    audio = any(mark in stream_url.lower() for mark in (".mp3", ".m4a", ".m4b", ".aac", "audio_"))
    rows = [row for row in (playlist or []) if isinstance(row, dict)]
    if not rows:
        rows = [{"title": title or "Vorschau", "url": page_url}]
    count = len(rows)
    cover_size = 280
    title_h = 68
    player_h = 100
    list_h = min(240, max(120, count * 46)) if count > 1 else 0
    caption_h = 22 if count > 1 else 0
    if audio:
        width = 560
        height = 16 + cover_size + 10 + title_h + (8 + caption_h + list_h if count > 1 else 0) + 8 + player_h + 12
    elif count > 1:
        width = 800
        height = 380 + 8 + title_h + 8 + caption_h + list_h + 12
    else:
        width, height = 960, 540
    player = ns["AVPlayer"].playerWithURL_(NSURL.URLWithString_(stream_url))
    view = ns["AVPlayerView"].alloc().initWithFrame_(NSMakeRect(0, 0, width, player_h if audio else (height if count == 1 else 380)))
    view.setPlayer_(player)
    try:
        view.setControlsStyle_(1)
    except Exception:
        pass
    if not audio:
        try:
            view.setShowsFullScreenToggleButton_(True)
        except Exception:
            pass
        try:
            view.setAutoresizingMask_(18)
        except Exception:
            pass
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(80, 80, width, height),
        15,
        2,
        False,
    )
    window.setTitle_(f"{'Anhören' if audio else 'Ansehen'} – {title}"[:120])
    image_view = None
    title_label = None
    playlist_view = None
    if audio or count > 1:
        from AppKit import NSColor
        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        try:
            window.setBackgroundColor_(NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.15, 0.16, 1))
            container.setWantsLayer_(True)
            container.layer().setBackgroundColor_(window.backgroundColor().CGColor())
        except Exception:
            pass
        y = 12 if audio else 8
        if audio:
            view.setFrame_(NSMakeRect(0, y, width, player_h))
            y += player_h + 8
        if count > 1:
            scroll, playlist_view = _playlist_view(NSMakeRect(16, y, width - 32, list_h), _playlist_text(rows, playlist_index))
            container.addSubview_(scroll)
            y += list_h + 4
            caption = _label(NSMakeRect(16, y, width - 32, caption_h), "Ausgewählt", 12, bold=True)
            try:
                caption.setTextColor_(NSColor.colorWithCalibratedWhite_alpha_(0.62, 1))
            except Exception:
                pass
            container.addSubview_(caption)
            y += caption_h + 8
        title_label = _label(NSMakeRect(16, y, width - 32, title_h), title or "Vorschau", 16, bold=True, center=True)
        container.addSubview_(title_label)
        y += title_h + 10
        if audio:
            image_view = NSImageView.alloc().initWithFrame_(NSMakeRect((width - cover_size) / 2, y, cover_size, cover_size))
            try:
                image_view.setImageScaling_(3)
            except Exception:
                pass
            container.addSubview_(image_view)
        else:
            view.setFrame_(NSMakeRect(0, y, width, 380))
        container.addSubview_(view)
        window.setContentView_(container)
    else:
        window.setContentView_(view)
    window.setReleasedWhenClosed_(False)
    holder = {
        "player": player,
        "view": view,
        "window": window,
        "ns": ns,
        "playlist": rows,
        "playlist_index": playlist_index,
        "schedule": schedule,
        "report_error": report_error,
        "ask_resume": ask_resume,
        "page_url": page_url,
        "audio": audio,
        "image_view": image_view,
        "title_label": title_label,
        "playlist_view": playlist_view,
        "closed": False,
        "observer": None,
        "timer": None,
    }

    def _remember():
        seconds = _player_seconds(holder.get("player"))
        if seconds >= 8:
            _save_position(holder.get("page_url") or "", seconds)

    def _arm():
        if holder.get("player") is None:
            return
        timer = threading.Timer(5.0, lambda: (holder.get("schedule") or (lambda _d, fn: fn()))(0, _pulse))
        timer.daemon = True
        holder["timer"] = timer
        timer.start()

    def _pulse():
        if holder.get("player") is None:
            return
        _remember()
        _arm()

    def _stop():
        timer = holder.get("timer")
        holder["timer"] = None
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
        _remember()
        holder["closed"] = True
        _unwatch(holder)
        pl = holder.get("player")
        vw = holder.get("view")
        if pl is None:
            return
        holder["player"] = None
        try:
            pl.pause()
        except Exception:
            pass
        try:
            if vw is not None:
                vw.setPlayer_(None)
        except Exception:
            pass
        try:
            pl.replaceCurrentItemWithPlayerItem_(None)
        except Exception:
            pass

    delegate = _close_delegate_class().alloc().initWithStop_(_stop)
    window.setDelegate_(delegate)
    holder["delegate"] = delegate
    try:
        from AppKit import NSApp, NSScreen, NSMakePoint
        NSApp.activateIgnoringOtherApps_(True)
        if audio:
            window.setLevel_(8)
        else:
            window.setLevel_(0)
            window.setCollectionBehavior_(128)
        screen = window.screen() or NSScreen.mainScreen()
        frame = screen.visibleFrame()
        origin = frame.origin
        size = frame.size
        window.setFrameOrigin_(NSMakePoint(
            origin.x + max(0, (size.width - width) / 2),
            origin.y + max(0, (size.height - height) / 2),
        ))
    except Exception:
        pass
    try:
        player.setVolume_(1.0)
    except Exception:
        pass
    _refresh_now_playing(holder, title or "Vorschau", cover)
    window.orderFrontRegardless()
    window.makeKeyAndOrderFront_(None)
    if start_at >= 8:
        try:
            player.seekToTime_(_cm_time(start_at))
        except Exception:
            pass
    _watch_end(holder)
    player.play()
    _arm()
    _OPEN.append(holder)
    if len(_OPEN) > 6:
        old = _OPEN.pop(0)
        try:
            old_player = old.get("player")
            if old_player is not None:
                old_player.pause()
                old_player.replaceCurrentItemWithPlayerItem_(None)
            old.get("window").close()
        except Exception:
            pass
