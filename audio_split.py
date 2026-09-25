#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zerlegt eine durchgehende Aufnahme an den stillen Stellen zwischen Stücken."""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple


def _run(cmd: List[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return (result.stderr or "") + (result.stdout or "")


def _duration(path: Path) -> float:
    out = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path),
    ])
    try:
        return float(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0.0


def _silence_spans(path: Path, noise_db: float = -35, min_silence: float = 1.2) -> List[Tuple[float, float]]:
    log = _run([
        "ffmpeg", "-i", str(path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ])
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", log)]
    spans = []
    for index, start in enumerate(starts):
        end = ends[index] if index < len(ends) else start + min_silence
        spans.append((start, end))
    return spans


def split_recording(path: Path, min_track: float = 20.0) -> List[Path]:
    """Schneidet eine Aufnahme an Pausen. Ein einzelnes Stück bleibt unverändert."""
    path = Path(path)
    total = _duration(path)
    if total <= 0:
        return []
    pieces: List[Tuple[float, float]] = []
    cursor = 0.0
    for start, end in _silence_spans(path):
        if start - cursor >= min_track:
            pieces.append((cursor, start))
        cursor = max(cursor, end)
    if total - cursor >= min_track:
        pieces.append((cursor, total))
    if len(pieces) <= 1:
        return [path]

    written: List[Path] = []
    for index, (start, stop) in enumerate(pieces):
        target = path.with_name(f"{path.stem}_teil{index + 1:02d}{path.suffix}")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(path),
                "-ss", f"{start:.3f}", "-to", f"{stop:.3f}",
                "-c", "copy", str(target),
            ],
            capture_output=True,
            timeout=120,
        )
        if target.is_file() and target.stat().st_size > 0:
            written.append(target)
    return written
