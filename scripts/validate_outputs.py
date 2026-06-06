#!/usr/bin/env python3
"""Validate final stream-summary artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generated summary artifacts.")
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("stem")
    parser.add_argument("--check-final", action="store_true", help="Also validate summary_outputs files")
    return parser.parse_args()


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def count_intermediate_blocks(path: Path) -> int:
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ") and len(line) >= 12 and line[3:11].count(":") == 2
    )


def main() -> None:
    args = parse_args()
    work_dir = args.work_dir.expanduser().resolve()
    out_dir = work_dir / "groq_outputs"
    required = [
        out_dir / f"{args.stem}_segments.json",
        out_dir / f"{args.stem}_transcript.txt",
        out_dir / f"{args.stem}_summary_source.md",
        out_dir / f"{args.stem}_meta.json",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Missing required files:\n" + "\n".join(missing))
    segments = json.loads((out_dir / f"{args.stem}_segments.json").read_text(encoding="utf-8"))
    meta = json.loads((out_dir / f"{args.stem}_meta.json").read_text(encoding="utf-8"))
    if not segments:
        raise SystemExit("segments file is empty")
    if meta.get("provider") != "groq":
        raise SystemExit("meta provider must be groq")
    if count_lines(out_dir / f"{args.stem}_summary_source.md") != 48:
        raise SystemExit("summary_source must contain exactly 48 lines")

    if args.check_final:
        summary = work_dir / "summary_outputs" / f"{args.stem}_summary.md"
        intermediate = work_dir / "summary_outputs" / f"{args.stem}_summary_intermediate.md"
        short = work_dir / "summary_outputs" / f"{args.stem}_summary_short.md"
        long_with_links = work_dir / "summary_outputs" / f"{args.stem}_summary_with_links.md"
        short_with_links = work_dir / "summary_outputs" / f"{args.stem}_summary_short_with_links.md"
        missing_final = [
            str(path)
            for path in (intermediate, short, short_with_links)
            if not path.is_file()
        ]
        if missing_final:
            raise SystemExit("Missing final files:\n" + "\n".join(missing_final))
        intermediate_text = intermediate.read_text(encoding="utf-8")
        if count_intermediate_blocks(intermediate) != 48:
            raise SystemExit("summary_intermediate.md must contain exactly 48 timecoded blocks")
        if "Полезные ссылки из чата" in intermediate_text:
            raise SystemExit("summary_intermediate.md must not include useful links block")
        if summary.is_file():
            if count_lines(summary) != 48:
                raise SystemExit("summary.md must contain exactly 48 lines")
            summary_text = summary.read_text(encoding="utf-8")
            if "Полезные ссылки из чата" in summary_text:
                raise SystemExit("summary.md must not include useful links block")
            if not long_with_links.is_file():
                raise SystemExit(f"Missing final files:\n{long_with_links}")
            long_with_links_text = long_with_links.read_text(encoding="utf-8")
            if not long_with_links_text.startswith(summary_text.strip()):
                raise SystemExit("summary_with_links.md must start with summary.md content")
            if "Полезные ссылки из чата" not in long_with_links_text:
                raise SystemExit("summary_with_links.md must include useful links block")
        short_lines = count_lines(short)
        if short_lines < 19 or short_lines > 24:
            raise SystemExit("summary_short.md must contain 19-24 lines")
        short_text = short.read_text(encoding="utf-8")
        if len(short_text) > 4000:
            raise SystemExit("summary_short.md must be <= 4000 characters")
        if "Полезные ссылки из чата" in short_text:
            raise SystemExit("summary_short.md must not include useful links block")
        short_with_links_text = short_with_links.read_text(encoding="utf-8")
        if not short_with_links_text.startswith(short_text.strip()):
            raise SystemExit("summary_short_with_links.md must start with summary_short.md content")
        if "Полезные ссылки из чата" not in short_with_links_text:
            raise SystemExit("summary_short_with_links.md must include useful links block")
    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
