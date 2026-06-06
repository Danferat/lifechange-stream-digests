#!/usr/bin/env python3
"""Send a short audio chunk to Groq before running a long transcription."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import tempfile
from pathlib import Path


def load_transcribe_module() -> object:
    module_path = Path(__file__).with_name("groq_transcribe.py")
    spec = importlib.util.spec_from_file_location("groq_transcribe", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["groq_transcribe"] = module
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a 30-second Groq transcription smoke test.")
    parser.add_argument("source", type=Path, help="Input audio file")
    parser.add_argument("--api-key-file", type=Path, help="File containing primary Groq key")
    parser.add_argument("--offset", type=float, default=60.0, help="Start offset in seconds")
    parser.add_argument("--duration", type=float, default=30.0, help="Smoke chunk duration in seconds")
    parser.add_argument("--model", default="whisper-large-v3-turbo")
    parser.add_argument("--language", default="ru")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    transcribe = load_transcribe_module()
    transcribe.load_dotenv(Path.cwd() / ".env")
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Input file does not exist: {source}")
    fake_args = argparse.Namespace(api_key_file=args.api_key_file, fallback_api_key_file=None)
    api_keys = transcribe.load_api_keys(fake_args)
    with tempfile.TemporaryDirectory(prefix="groq_smoke_") as temp_dir:
        chunk = Path(temp_dir) / "smoke.ogg"
        transcribe.make_chunk(source, chunk, args.offset, args.duration)
        response = transcribe.transcribe_chunk(api_keys, chunk, args.model, args.language, retries=2)
    text = str(response.get("text", "")).strip()
    if not text and isinstance(response.get("segments"), list):
        text = " ".join(str(s.get("text", "")).strip() for s in response["segments"][:3]).strip()
    print("SMOKE_OK")
    print(text[:500])


if __name__ == "__main__":
    main()
