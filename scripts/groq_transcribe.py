#!/usr/bin/env python3
"""Transcribe one audio file with Groq Whisper in resumable chunks."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


API_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
DEFAULT_MODEL = "whisper-large-v3-turbo"
DEFAULT_LANGUAGE = "ru"
DEFAULT_CHUNK_SECONDS = 300
DEFAULT_PRICE_PER_HOUR = 0.04
MAX_CHUNK_SECONDS = 900
MAX_RETRIES = 6


def parse_args() -> argparse.Namespace:
    load_dotenv(Path.cwd() / ".env")
    parser = argparse.ArgumentParser(
        description="Chunk an audio file and transcribe it through Groq Whisper."
    )
    parser.add_argument("source", type=Path, help="Input audio file, usually .ogg")
    parser.add_argument("out_dir", type=Path, help="Directory for JSON/text outputs")
    parser.add_argument("stem", help="Safe output stem, for example part1")
    parser.add_argument("--api-key-file", type=Path, help="File containing primary Groq key")
    parser.add_argument(
        "--fallback-api-key-file", type=Path, help="File containing fallback Groq key"
    )
    parser.add_argument("--model", default=os.environ.get("GROQ_TRANSCRIBE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--language", default=os.environ.get("GROQ_LANGUAGE", DEFAULT_LANGUAGE))
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=int(os.environ.get("GROQ_CHUNK_SECONDS", str(DEFAULT_CHUNK_SECONDS))),
    )
    parser.add_argument(
        "--price-per-hour",
        type=float,
        default=float(os.environ.get("GROQ_PRICE_PER_HOUR", str(DEFAULT_PRICE_PER_HOUR))),
    )
    return parser.parse_args()


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def reject_path_like_stem(stem: str) -> str:
    if not stem or stem in {".", ".."}:
        raise ValueError("stem must not be empty")
    if "/" in stem or "\\" in stem or "\x00" in stem:
        raise ValueError("stem must be a file name, not a path")
    return stem


def read_key(path: Path | None, env_name: str) -> str | None:
    if path:
        key = path.expanduser().read_text(encoding="utf-8").strip()
    else:
        key = os.environ.get(env_name, "").strip()
    return key or None


def load_api_keys(args: argparse.Namespace) -> list[str]:
    keys = [
        read_key(args.api_key_file, "GROQ_API_KEY"),
        read_key(args.fallback_api_key_file, "GROQ_API_KEY_FALLBACK"),
    ]
    unique_keys: list[str] = []
    for key in keys:
        if key and key not in unique_keys:
            unique_keys.append(key)
    if not unique_keys:
        raise RuntimeError(
            "No Groq API key found. Use GROQ_API_KEY or --api-key-file .secrets/groq_primary.key"
        )
    return unique_keys


def run_checked(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def audio_duration_seconds(source: Path) -> float:
    raw = run_checked(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(source),
        ]
    )
    return float(raw)


def make_chunk(source: Path, chunk_path: Path, start: float, duration: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            "32k",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(chunk_path),
        ],
        check=True,
    )


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


def load_existing_segments(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise RuntimeError(f"{path} is not a segment list")
    for item in data:
        if not isinstance(item, dict) or not {"start", "end", "text"} <= set(item):
            raise RuntimeError(f"{path} contains invalid segment data")
    return data


def multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = f"----codex-groq-{int(time.time() * 1000)}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    parts.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(parts), boundary


def post_transcription(api_key: str, chunk_path: Path, model: str, language: str) -> dict[str, Any]:
    body, boundary = multipart_body(
        {
            "model": model,
            "response_format": "verbose_json",
            "language": language,
            "temperature": "0",
        },
        "file",
        chunk_path,
    )
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "lifechange-stream-summary/1.0",
        },
        method="POST",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=180, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def retry_after_seconds(error: urllib.error.HTTPError) -> float | None:
    header = error.headers.get("Retry-After") if error.headers else None
    if not header:
        return None
    try:
        return max(0.0, min(300.0, float(header)))
    except ValueError:
        return None


def transcribe_chunk(
    api_keys: list[str], chunk_path: Path, model: str, language: str, retries: int = MAX_RETRIES
) -> dict[str, Any]:
    last_error = "unknown error"
    for attempt in range(retries):
        wait_hint: float | None = None
        for key_index, key in enumerate(api_keys, start=1):
            try:
                return post_transcription(key, chunk_path, model, language)
            except urllib.error.HTTPError as error:
                body = error.read().decode("utf-8", errors="replace")[:500]
                last_error = f"key{key_index} HTTP {error.code}: {body}"
                print(last_error)
                if error.code in {401, 403}:
                    continue
                if error.code == 429:
                    wait_hint = retry_after_seconds(error)
            except Exception as error:  # noqa: BLE001 - final message is intentionally sanitized.
                last_error = f"key{key_index} request failed: {type(error).__name__}: {error}"
                print(last_error)
        delay = wait_hint if wait_hint is not None else min(60, 2**attempt)
        print(f"retry in {delay:.0f}s")
        time.sleep(delay)
    raise RuntimeError(f"Groq transcription failed after retries: {last_error}")


def normalize_segments(raw: dict[str, Any], offset: float) -> list[dict[str, Any]]:
    segments = raw.get("segments")
    if not isinstance(segments, list):
        text = raw.get("text")
        if isinstance(text, str) and text.strip():
            return [{"start": offset, "end": offset, "text": text.strip()}]
        raise RuntimeError("Groq response did not include segments")
    normalized: list[dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        start = float(seg.get("start", 0.0)) + offset
        end = float(seg.get("end", seg.get("start", 0.0))) + offset
        normalized.append({"start": round(start, 3), "end": round(end, 3), "text": text})
    return normalized


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


def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input file does not exist: {source}")
    if args.chunk_seconds <= 0 or args.chunk_seconds > MAX_CHUNK_SECONDS:
        raise SystemExit(f"--chunk-seconds must be between 1 and {MAX_CHUNK_SECONDS}")

    stem = reject_path_like_stem(args.stem)
    out_dir = args.out_dir.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    api_keys = load_api_keys(args)

    seg_path = out_dir / f"{stem}_segments.json"
    transcript_path = out_dir / f"{stem}_transcript.txt"
    meta_path = out_dir / f"{stem}_meta.json"

    duration = audio_duration_seconds(source)
    all_segments = load_existing_segments(seg_path)
    resume_from = max((float(s["end"]) for s in all_segments), default=0.0)
    if resume_from:
        print(f"[{stem}] resume from {resume_from:.0f}s ({len(all_segments)} segs)")

    chunk_count = int((duration + args.chunk_seconds - 0.001) // args.chunk_seconds)
    with tempfile.TemporaryDirectory(prefix="groq_chunks_") as temp_dir:
        temp_root = Path(temp_dir)
        for index in range(chunk_count):
            offset = float(index * args.chunk_seconds)
            chunk_duration = min(float(args.chunk_seconds), duration - offset)
            if offset + chunk_duration <= resume_from + 0.25:
                print(f"[{stem}] skip chunk {index + 1}/{chunk_count} (already done)")
                continue
            chunk_path = temp_root / f"chunk_{index:04d}.ogg"
            make_chunk(source, chunk_path, offset, chunk_duration)
            size_kb = chunk_path.stat().st_size // 1024
            print(
                f"[{stem}] chunk {index + 1}/{chunk_count} "
                f"offset={offset:.0f}s dur={chunk_duration:.0f}s size={size_kb}KB"
            )
            response = transcribe_chunk(api_keys, chunk_path, args.model, args.language)
            all_segments.extend(normalize_segments(response, offset))
            all_segments.sort(key=lambda item: (float(item["start"]), float(item["end"])))
            atomic_write_json(seg_path, all_segments)

    write_transcript(transcript_path, all_segments)
    meta = {
        "provider": "groq",
        "transcription_model": args.model,
        "language": args.language,
        "source_file": source.name,
        "audio_duration_seconds": round(duration, 3),
        "chunk_seconds": args.chunk_seconds,
        "segment_count": len(all_segments),
        "cost_usd": round((duration / 3600.0) * args.price_per_hour, 6),
    }
    atomic_write_json(meta_path, meta)
    print(f"[{stem}] DONE segments={len(all_segments)} duration={duration:.1f}s cost=${meta['cost_usd']}")


if __name__ == "__main__":
    main()
