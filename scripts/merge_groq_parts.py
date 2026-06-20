#!/usr/bin/env python3
"""Merge one or more Groq transcription parts and build summary_source.md."""

from __future__ import annotations

import argparse
import json
import math
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_BLOCK_SECONDS = 240


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge transcribed parts into final source files.")
    parser.add_argument("work_dir", type=Path, help="Work directory containing groq_outputs/")
    parser.add_argument("stem", help="Final output stem")
    parser.add_argument("parts", nargs="+", help="Part stems, for example part1 part2")
    parser.add_argument(
        "--block-seconds",
        type=int,
        default=DEFAULT_BLOCK_SECONDS,
        help="Target seconds per summary block (default 240 = 4 min)",
    )
    return parser.parse_args()


def reject_path_like_stem(stem: str) -> str:
    if not stem or stem in {".", ".."}:
        raise ValueError("stem must not be empty")
    if "/" in stem or "\\" in stem or "\x00" in stem:
        raise ValueError("stem must be a file name, not a path")
    return stem


def fmt_ts(seconds: float) -> str:
    total = max(0, int(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    tmp.replace(path)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_part(out_dir: Path, part: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    safe_part = reject_path_like_stem(part)
    seg_path = out_dir / f"{safe_part}_segments.json"
    meta_path = out_dir / f"{safe_part}_meta.json"
    if not seg_path.is_file():
        raise FileNotFoundError(seg_path)
    if not meta_path.is_file():
        raise FileNotFoundError(meta_path)
    segments = load_json(seg_path)
    meta = load_json(meta_path)
    if not isinstance(segments, list):
        raise RuntimeError(f"{seg_path} must contain a list")
    if not isinstance(meta, dict) or "audio_duration_seconds" not in meta:
        raise RuntimeError(f"{meta_path} has no audio_duration_seconds")
    for segment in segments:
        if not isinstance(segment, dict) or not {"start", "end", "text"} <= set(segment):
            raise RuntimeError(f"{seg_path} contains invalid segment data")
    return segments, meta


def write_transcript(path: Path, segments: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    next_marker = 0.0
    for seg in segments:
        start = float(seg["start"])
        if not lines or start >= next_marker:
            lines.append(f"{fmt_ts(start)}  {seg['text']}")
            next_marker = start + 30
        else:
            lines[-1] = f"{lines[-1]} {seg['text']}"
    atomic_write_text(path, "\n".join(lines).strip() + "\n")


def write_summary_source(
    path: Path, segments: list[dict[str, Any]], total_duration: float, block_seconds: int
) -> int:
    if total_duration <= 0:
        raise RuntimeError("total duration must be positive")
    target_lines = max(1, math.ceil(total_duration / block_seconds))
    bucket = total_duration / target_lines
    lines: list[str] = []
    cursor = 0
    ordered = sorted(segments, key=lambda item: float(item["start"]))
    for index in range(target_lines):
        start = index * bucket
        end = total_duration + 0.001 if index == target_lines - 1 else (index + 1) * bucket
        texts: list[str] = []
        while cursor < len(ordered) and float(ordered[cursor]["start"]) < start:
            cursor += 1
        scan = cursor
        while scan < len(ordered) and float(ordered[scan]["start"]) < end:
            text = str(ordered[scan]["text"]).strip()
            if text:
                texts.append(text)
            scan += 1
        lines.append(f"{fmt_ts(start)}  {' '.join(texts).strip()}")
    atomic_write_text(path, "\n".join(lines) + "\n")
    return target_lines


def main() -> None:
    args = parse_args()
    work_dir = args.work_dir.expanduser().resolve()
    out_dir = work_dir / "groq_outputs"
    stem = reject_path_like_stem(args.stem)

    merged: list[dict[str, Any]] = []
    part_metas: list[dict[str, Any]] = []
    total_duration = 0.0
    total_cost = 0.0
    for part in args.parts:
        segments, meta = load_part(out_dir, part)
        offset = total_duration
        for seg in segments:
            merged.append(
                {
                    "start": round(float(seg["start"]) + offset, 3),
                    "end": round(float(seg["end"]) + offset, 3),
                    "text": str(seg["text"]).strip(),
                }
            )
        duration = float(meta["audio_duration_seconds"])
        total_duration += duration
        total_cost += float(meta.get("cost_usd", 0.0))
        part_metas.append({"name": part, "duration_seconds": duration, "segments": len(segments)})

    merged.sort(key=lambda item: (float(item["start"]), float(item["end"])))
    atomic_write_json(out_dir / f"{stem}_segments.json", merged)
    write_transcript(out_dir / f"{stem}_transcript.txt", merged)
    summary_source_lines = write_summary_source(
        out_dir / f"{stem}_summary_source.md", merged, total_duration, args.block_seconds
    )
    atomic_write_json(
        out_dir / f"{stem}_meta.json",
        {
            "provider": "groq",
            "parts": part_metas,
            "audio_duration_seconds": round(total_duration, 3),
            "segment_count": len(merged),
            "cost_usd": round(total_cost, 6),
            "summary_source_lines": summary_source_lines,
        },
    )
    print(
        f"[{stem}] merged parts={len(args.parts)} segments={len(merged)} "
        f"duration={total_duration:.1f}s blocks={summary_source_lines}"
    )


if __name__ == "__main__":
    main()
