#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
macOS / Apple-Silicon Hilfen: native Pfade, ffmpeg, VideoToolbox-GPU.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_apple_silicon() -> bool:
    if not is_macos():
        return False
    machine = (platform.machine() or "").lower()
    if machine in ("arm64", "aarch64"):
        return True
    # Unter Rosetta: Prozess x86_64, Chip trotzdem Apple Silicon
    try:
        r = subprocess.run(
            ["sysctl", "-n", "sysctl.proc_translated"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and (r.stdout or "").strip() == "1":
            return True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["sysctl", "-n", "hw.optional.arm64"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0 and (r.stdout or "").strip() == "1":
            return True
    except Exception:
        pass
    return False


def apple_chip_name() -> str:
    """z. B. 'Apple M5 Max' oder 'Apple Silicon'."""
    if not is_macos():
        return ""
    try:
        r = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        name = (r.stdout or "").strip()
        if name:
            return name
    except Exception:
        pass
    return "Apple Silicon" if is_apple_silicon() else "Intel Mac"


def _macho_is_arm64(path: str) -> Optional[bool]:
    """True = arm64 (oder Universal inkl. arm64), False = nur x86_64, None = unbekannt."""
    try:
        r = subprocess.run(["file", "-b", path], capture_output=True, text=True, timeout=3)
        out = (r.stdout or "").lower()
        if "arm64" in out or "arm64e" in out:
            return True
        if "x86_64" in out or "i386" in out:
            return False
    except Exception:
        pass
    return None


def ensure_macos_native_path() -> None:
    """
    Stellt sicher, dass Homebrew-arm64 (/opt/homebrew) vor Intel-Homebrew (/usr/local)
    und System-Pfaden steht — wichtig für natives ffmpeg/yt-dlp auf Apple Silicon.
    """
    if not is_macos():
        return
    extras: List[str] = []
    if is_apple_silicon():
        extras.extend(
            [
                "/opt/homebrew/bin",
                "/opt/homebrew/sbin",
            ]
        )
    extras.extend(
        [
            "/usr/local/bin",
            os.path.expanduser("~/.local/bin"),
        ]
    )
    path = os.environ.get("PATH", "")
    parts = [p for p in path.split(os.pathsep) if p]
    for p in reversed(extras):
        if os.path.isdir(p) and p not in parts:
            parts.insert(0, p)
        elif p in parts:
            # nach vorne ziehen
            parts = [p] + [x for x in parts if x != p]
    os.environ["PATH"] = os.pathsep.join(parts)


def find_ffmpeg(prefer_arm64: bool = True) -> Optional[str]:
    """Sucht ffmpeg; auf Apple Silicon bevorzugt arm64-Binary."""
    ensure_macos_native_path()
    candidates: List[str] = []
    which = shutil.which("ffmpeg")
    if which:
        candidates.append(which)
    for p in (
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/local/bin/ffmpeg",
    ):
        if p not in candidates and os.path.isfile(p) and os.access(p, os.X_OK):
            candidates.append(p)

    if not candidates:
        return None

    if prefer_arm64 and is_apple_silicon():
        arm = [c for c in candidates if _macho_is_arm64(c) is True]
        if arm:
            return arm[0]
        # Fallback: erstes vorhandenes (kann Rosetta/x86 sein — VideoToolbox funktioniert trotzdem)
    return candidates[0]


def has_videotoolbox(ffmpeg_path: Optional[str] = None) -> bool:
    """True wenn ffmpeg h264_videotoolbox (Apple GPU) anbietet."""
    if not is_macos():
        return False
    ff = ffmpeg_path or find_ffmpeg()
    if not ff:
        return False
    try:
        r = subprocess.run(
            [ff, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        out = (r.stdout or "") + (r.stderr or "")
        return "h264_videotoolbox" in out
    except Exception:
        return False


def videotoolbox_encoder_args(prefer_hevc: bool = False) -> List[str]:
    """
    FFmpeg-Args für Hardware-Encoding über VideoToolbox (Apple Silicon / Mac GPU).
    -b:v 0 + -q:v: Qualitätsmodus (1–100, höher = besser; 65 ist guter Standard).
    """
    codec = "hevc_videotoolbox" if prefer_hevc else "h264_videotoolbox"
    return [
        "-c:v",
        codec,
        "-allow_sw",
        "1",
        "-b:v",
        "0",
        "-q:v",
        "65",
        "-c:a",
        "copy",
    ]


def gpu_status_summary() -> Tuple[bool, str]:
    """
    Kurzinfo für Einstellungen/Log.
    Returns: (videotoolbox_ok, text)
    """
    if not is_macos():
        return False, ""
    chip = apple_chip_name() or "Mac"
    ff = find_ffmpeg()
    if not ff:
        return False, f"{chip}: ffmpeg fehlt (brew install ffmpeg)"
    vt = has_videotoolbox(ff)
    arch = _macho_is_arm64(ff)
    arch_note = "arm64" if arch is True else ("x86_64/Rosetta" if arch is False else "?")
    if vt:
        return True, f"{chip} · VideoToolbox OK · ffmpeg ({arch_note})"
    return False, f"{chip} · ffmpeg ohne VideoToolbox ({arch_note})"
