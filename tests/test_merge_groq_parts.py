#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MERGE_SCRIPT = PROJECT_ROOT / "scripts" / "merge_groq_parts.py"


class MergeGroqPartsTest(unittest.TestCase):
    def test_merges_parts_with_offset_and_summary_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            out = work / "groq_outputs"
            out.mkdir()
            (out / "part1_segments.json").write_text(
                json.dumps(
                    [
                        {"start": 0.0, "end": 5.0, "text": "первая тема"},
                        {"start": 30.0, "end": 35.0, "text": "вторая тема"},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (out / "part1_meta.json").write_text(
                json.dumps({"audio_duration_seconds": 60.0, "cost_usd": 0.001}),
                encoding="utf-8",
            )
            (out / "part2_segments.json").write_text(
                json.dumps([{"start": 0.0, "end": 4.0, "text": "третья тема"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (out / "part2_meta.json").write_text(
                json.dumps({"audio_duration_seconds": 60.0, "cost_usd": 0.001}),
                encoding="utf-8",
            )

            subprocess.run(
                ["python3", str(MERGE_SCRIPT), str(work), "stream", "part1", "part2"],
                check=True,
                capture_output=True,
                text=True,
            )

            merged = json.loads((out / "stream_segments.json").read_text(encoding="utf-8"))
            self.assertEqual(merged[2]["start"], 60.0)
            self.assertEqual(len((out / "stream_summary_source.md").read_text(encoding="utf-8").splitlines()), 48)
            meta = json.loads((out / "stream_meta.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["audio_duration_seconds"], 120.0)


if __name__ == "__main__":
    unittest.main()
