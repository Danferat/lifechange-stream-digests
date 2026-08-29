#!/usr/bin/env python3
"""Build question-aligned AMA timecodes from Groq speech segments.

The first pass writes candidates only. A reviewed file turns those candidates
into the final AMA timecode list and a question-aligned source document.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from merge_groq_parts import reject_path_like_stem


STOP_WORDS = {
    "а", "и", "в", "во", "вы", "для", "до", "если", "же", "из", "или", "как", "ли", "на",
    "не", "но", "о", "об", "по", "с", "со", "то", "у", "что", "это", "бы", "вам", "вас",
}
CUE_RE = re.compile(r"\b(?:вопрос\w*|следующ\w*\s+вопрос\w*)\b", re.IGNORECASE)
REVIEW_RE = re.compile(r"^(?P<time>(?:\d+:)?\d{2}:\d{2})\s+-\s+(?P<text>.+)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build reviewed AMA question timecodes from transcript segments.")
    parser.add_argument("work_dir", type=Path)
    parser.add_argument("stem")
    parser.add_argument("questions", type=Path, help="One full chat question per non-empty line")
    parser.add_argument(
        "--review-file",
        type=Path,
        help="Reviewed lines in the form MM:SS - short question topic; writes final AMA files",
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


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parse_questions(path: Path) -> list[str]:
    questions = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", line)
        if line:
            questions.append(line)
    if not questions:
        raise ValueError("questions file must contain at least one question")
    return questions


def parse_timecode(value: str) -> float:
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"invalid timecode: {value}")
    if minutes > 59 or seconds > 59:
        raise ValueError(f"invalid timecode: {value}")
    return float(hours * 3600 + minutes * 60 + seconds)


def fmt_timecode(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[^\W\d_]+", text.lower(), re.UNICODE) if len(token) > 2 and token not in STOP_WORDS}


def find_candidate(question: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    wanted = tokens(question)
    if not wanted:
        raise ValueError(f"question has no searchable words: {question}")
    best: dict[str, Any] | None = None
    for index, segment in enumerate(segments):
        window = " ".join(str(item["text"]) for item in segments[index : index + 5])
        overlap = len(wanted & tokens(window)) / len(wanted)
        ratio = difflib.SequenceMatcher(None, " ".join(sorted(wanted)), " ".join(sorted(tokens(window)))).ratio()
        score = round(overlap * 0.85 + ratio * 0.15, 3)
        candidate = {"index": index, "score": score, "match_text": str(segment["text"]), "match_start_seconds": float(segment["start"])}
        if best is None or score > best["score"]:
            best = candidate
    assert best is not None
    boundary_index = best["index"]
    for index in range(best["index"] - 1, -1, -1):
        candidate = segments[index]
        if best["match_start_seconds"] - float(candidate["start"]) > 20:
            break
        if CUE_RE.search(str(candidate["text"])):
            boundary_index = index
    boundary = segments[boundary_index]
    return {
        "question": question,
        "score": best["score"],
        "match_start_seconds": best["match_start_seconds"],
        "match_text": best["match_text"],
        "suggested_start_seconds": float(boundary["start"]),
        "suggested_boundary_text": str(boundary["text"]),
    }


def read_segments(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not value:
        raise ValueError(f"invalid segment list: {path}")
    ordered = sorted(value, key=lambda item: float(item["start"]))
    for item in ordered:
        if not isinstance(item, dict) or not {"start", "end", "text"} <= item.keys():
            raise ValueError(f"invalid segment in {path}")
    return ordered


def parse_review(path: Path, expected_count: int) -> list[tuple[float, str]]:
    reviewed = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = REVIEW_RE.match(line)
        if not match:
            raise ValueError(f"review line must use MM:SS - topic: {line}")
        reviewed.append((parse_timecode(match.group("time")), match.group("text").strip()))
    if len(reviewed) != expected_count:
        raise ValueError(f"review file must contain exactly {expected_count} lines")
    if any(current[0] >= following[0] for current, following in zip(reviewed, reviewed[1:])):
        raise ValueError("review timecodes must be strictly increasing")
    return reviewed


def build_ama_timecodes(work_dir: Path, stem: str, questions_path: Path, review_path: Path | None) -> list[Path]:
    safe_stem = reject_path_like_stem(stem)
    work_dir = work_dir.expanduser().resolve()
    groq_dir = work_dir / "groq_outputs"
    summary_dir = work_dir / "summary_outputs"
    segments = read_segments(groq_dir / f"{safe_stem}_segments.json")
    questions = parse_questions(questions_path.expanduser().resolve())
    candidates = [find_candidate(question, segments) for question in questions]
    candidate_json = summary_dir / f"{safe_stem}_ama_timecodes_candidates.json"
    candidate_md = summary_dir / f"{safe_stem}_ama_timecodes_candidates.md"
    atomic_write_json(candidate_json, {"questions": candidates, "review_required": True})
    draft_lines = ["# Кандидаты таймкодов АМА", "", "Проверь начало чтения каждого вопроса и перенеси подтверждённые строки в review-файл", ""]
    draft_lines.extend(
        f"{fmt_timecode(item['suggested_start_seconds'])} - {item['question']}" for item in candidates
    )
    atomic_write_text(candidate_md, "\n".join(draft_lines) + "\n")
    written = [candidate_json, candidate_md]
    if review_path is None:
        return written

    reviewed = parse_review(review_path.expanduser().resolve(), len(questions))
    duration = max(float(item["end"]) for item in segments)
    if reviewed[-1][0] > duration:
        raise ValueError("review timecode is after the transcript end")
    final_path = summary_dir / f"{safe_stem}_ama_timecodes.md"
    source_path = groq_dir / f"{safe_stem}_ama_source.md"
    final_lines = [f"{fmt_timecode(seconds)} - {topic}" for seconds, topic in reviewed]
    atomic_write_text(final_path, "\n".join(final_lines) + "\n")
    source_chunks = ["# АМА по вопросам", ""]
    for index, (start, topic) in enumerate(reviewed):
        end = reviewed[index + 1][0] if index + 1 < len(reviewed) else duration + 0.001
        text = " ".join(str(segment["text"]).strip() for segment in segments if start <= float(segment["start"]) < end)
        source_chunks.extend([f"## {fmt_timecode(start)} {topic}", "", text, ""])
    atomic_write_text(source_path, "\n".join(source_chunks).rstrip() + "\n")
    atomic_write_json(
        summary_dir / f"{safe_stem}_ama_timecodes.json",
        {"questions": [{"start_seconds": start, "topic": topic, "reviewed": True} for start, topic in reviewed]},
    )
    return [*written, final_path, source_path]


def main() -> None:
    args = parse_args()
    for path in build_ama_timecodes(args.work_dir, args.stem, args.questions, args.review_file):
        print(f"AMA_OUTPUT={path}")


if __name__ == "__main__":
    main()
