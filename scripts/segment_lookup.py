#!/usr/bin/env python3
"""Look up exact Whisper segment timestamps by keyword or time window.

Reads the fine-grained {stem}_segments.json (per-utterance start/end from
Whisper, ~5-15s resolution) instead of the coarser merged transcript.txt or
4-minute summary_source.md blocks. Every timestamp printed is read directly
from the JSON - no manual HH:MM:SS conversion, no eyeballing a position
inside a merged paragraph.

Usage:
    segment_lookup.py work_dir stem --search "метеор"
    segment_lookup.py work_dir stem --around 1:43:30 --window 90
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TIME_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find exact segment timestamps by keyword or time window."
    )
    parser.add_argument("work_dir", type=Path, help="Work directory containing groq_outputs/")
    parser.add_argument("stem", help="Stream stem, for example stream_28_august")
    parser.add_argument("--search", help="Case-insensitive substring to find across all segments")
    parser.add_argument("--around", help="Time to center the window on, e.g. 1:43:30 or 07:50")
    parser.add_argument(
        "--window", type=float, default=60.0, help="Seconds before/after --around to include"
    )
    parser.add_argument("--limit", type=int, default=40, help="Max results to print for --search")
    args = parser.parse_args()
    if not args.search and not args.around:
        parser.error("pass --search or --around")
    return args


def reject_path_like_stem(stem: str) -> str:
    if not stem or stem in {".", ".."} or "/" in stem or "\\" in stem or "\x00" in stem:
        raise ValueError("stem must be a plain file name")
    return stem


def load_segments(work_dir: Path, stem: str) -> list[dict[str, Any]]:
    path = work_dir.expanduser().resolve() / "groq_outputs" / f"{reject_path_like_stem(stem)}_segments.json"
    if not path.is_file():
        raise SystemExit(f"segments file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise SystemExit(f"{path} must contain a list")
    return sorted(data, key=lambda item: float(item["start"]))


def fmt_short(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_time(value: str) -> float:
    match = TIME_RE.match(value.strip())
    if not match:
        raise SystemExit(f"cannot parse time {value!r}, expected MM:SS or H:MM:SS")
    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def print_segment(index: int, seg: dict[str, Any]) -> None:
    start = float(seg["start"])
    print(f"[{index:04d}] {fmt_short(start)}  {seg['text'].strip()}")


def run_search(segments: list[dict[str, Any]], needle: str, limit: int) -> None:
    needle_lower = needle.lower()
    hits = 0
    for index, seg in enumerate(segments):
        if needle_lower in str(seg["text"]).lower():
            print_segment(index, seg)
            hits += 1
            if hits >= limit:
                print(f"... limit {limit} reached, refine --search or raise --limit")
                break
    if hits == 0:
        print(f"no segments contain {needle!r}")


def run_around(segments: list[dict[str, Any]], center: float, window: float) -> None:
    lo, hi = center - window, center + window
    printed = 0
    for index, seg in enumerate(segments):
        start = float(seg["start"])
        if lo <= start <= hi:
            print_segment(index, seg)
            printed += 1
    if printed == 0:
        print(f"no segments in [{fmt_short(lo)}, {fmt_short(hi)}]")


def main() -> None:
    args = parse_args()
    segments = load_segments(args.work_dir, args.stem)
    if args.search:
        run_search(segments, args.search, args.limit)
    else:
        center = parse_time(args.around)
        run_around(segments, center, args.window)


if __name__ == "__main__":
    main()
