#!/usr/bin/env python3
"""Build export files followed by context topics."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from build_context_links import build_links, render_link_block
from merge_groq_parts import reject_path_like_stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build final stream digest from summary and transcript.")
    parser.add_argument("work_dir", type=Path, help="Work directory containing groq_outputs/ and summary_outputs/")
    parser.add_argument("stem", help="Output stem")
    parser.add_argument("--limit", type=int, default=12, help="Maximum number of context topics")
    return parser.parse_args()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    tmp.replace(path)


def build_final_digest(work_dir: Path, stem: str, limit: int) -> list[Path]:
    if limit < 1:
        raise ValueError("limit must be positive")
    safe_stem = reject_path_like_stem(stem)
    resolved_work_dir = work_dir.expanduser().resolve()
    summary_dir = resolved_work_dir / "summary_outputs"
    groq_dir = resolved_work_dir / "groq_outputs"
    summary_path = summary_dir / f"{safe_stem}_summary.md"
    short_path = summary_dir / f"{safe_stem}_summary_short.md"
    transcript_path = groq_dir / f"{safe_stem}_transcript.txt"
    mentioned_materials_path = summary_dir / f"{safe_stem}_summary_mentioned_materials.md"
    long_with_links_path = summary_dir / f"{safe_stem}_summary_with_links.md"
    short_with_links_path = summary_dir / f"{safe_stem}_summary_short_with_links.md"

    if not short_path.is_file():
        raise FileNotFoundError(short_path)

    short = short_path.read_text(encoding="utf-8").strip()
    if mentioned_materials_path.is_file():
        titles = [
            line.strip().lstrip("•").strip()
            for line in mentioned_materials_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        context_block = render_link_block(titles).strip()
    else:
        if not transcript_path.is_file():
            raise FileNotFoundError(transcript_path)
        transcript = transcript_path.read_text(encoding="utf-8")
        context_block = render_link_block(build_links(transcript, limit)).strip()

    written = []
    if summary_path.is_file():
        summary = summary_path.read_text(encoding="utf-8").strip()
        atomic_write_text(long_with_links_path, f"{summary}\n\n{context_block}\n")
        written.append(long_with_links_path)
    atomic_write_text(short_with_links_path, f"{short}\n\n{context_block}\n")
    written.append(short_with_links_path)
    return written


def main() -> None:
    args = parse_args()
    for path in build_final_digest(args.work_dir, args.stem, args.limit):
        if path.name.endswith("_summary_with_links.md"):
            print(f"SUMMARY_WITH_LINKS={path}")
        elif path.name.endswith("_summary_short_with_links.md"):
            print(f"SUMMARY_SHORT_WITH_LINKS={path}")


if __name__ == "__main__":
    main()
