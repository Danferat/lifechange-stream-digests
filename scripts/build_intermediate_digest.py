#!/usr/bin/env python3
"""Build a technical intermediate digest from 48 source blocks and 48 labels."""

from __future__ import annotations

import argparse
import re
import tempfile
from pathlib import Path

from merge_groq_parts import reject_path_like_stem


TIMECODE_RE = re.compile(r"^\d{2}:\d{2}:\d{2}\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an intermediate stream digest for context review.")
    parser.add_argument("work_dir", type=Path, help="Work directory containing groq_outputs/ and summary_outputs/")
    parser.add_argument("stem", help="Output stem")
    parser.add_argument(
        "--labels",
        type=Path,
        help=(
            "Optional 48-line label file. Defaults to "
            "summary_outputs/<stem>_summary_intermediate_notes.md, then <stem>_summary.md."
        ),
    )
    return parser.parse_args()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    tmp.replace(path)


def read_blocks(path: Path, kind: str, expected: int | None = None) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(path)
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if expected is not None and len(lines) != expected:
        raise RuntimeError(f"{kind} must contain exactly {expected} non-empty lines: {path}")
    for line in lines:
        if not TIMECODE_RE.match(line):
            raise RuntimeError(f"{kind} line must start with HH:MM:SS: {line[:80]}")
    return lines


def pick_label_path(summary_dir: Path, stem: str, explicit: Path | None) -> Path:
    if explicit:
        return explicit.expanduser().resolve()
    intermediate_notes = summary_dir / f"{stem}_summary_intermediate_notes.md"
    if intermediate_notes.is_file():
        return intermediate_notes
    return summary_dir / f"{stem}_summary.md"


def split_timecode(line: str) -> tuple[str, str]:
    timecode, text = line[:8], line[8:].strip()
    return timecode, text


def build_intermediate_digest(work_dir: Path, stem: str, labels: Path | None = None) -> Path:
    safe_stem = reject_path_like_stem(stem)
    resolved_work_dir = work_dir.expanduser().resolve()
    summary_dir = resolved_work_dir / "summary_outputs"
    groq_dir = resolved_work_dir / "groq_outputs"
    source_path = groq_dir / f"{safe_stem}_summary_source.md"
    label_path = pick_label_path(summary_dir, safe_stem, labels)
    output_path = summary_dir / f"{safe_stem}_summary_intermediate.md"

    source_lines = read_blocks(source_path, "summary_source")
    block_count = len(source_lines)
    label_lines = read_blocks(label_path, "labels", expected=block_count)

    chunks = ["# Промежуточная выжимка", ""]
    for label_line, source_line in zip(label_lines, source_lines, strict=True):
        label_ts, label_text = split_timecode(label_line)
        source_ts, source_text = split_timecode(source_line)
        if label_ts != source_ts:
            raise RuntimeError(f"timecode mismatch: label {label_ts}, source {source_ts}")
        chunks.extend([f"## {label_ts} {label_text}", "", source_text, ""])

    atomic_write_text(output_path, "\n".join(chunks).rstrip() + "\n")
    return output_path


def main() -> None:
    args = parse_args()
    output_path = build_intermediate_digest(args.work_dir, args.stem, args.labels)
    print(f"SUMMARY_INTERMEDIATE={output_path}")


if __name__ == "__main__":
    main()
