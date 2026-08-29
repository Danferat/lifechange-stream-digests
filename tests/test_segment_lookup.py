#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "segment_lookup.py"


class SegmentLookupTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        work = Path(self.tmp.name)
        groq_out = work / "groq_outputs"
        groq_out.mkdir(parents=True)
        segments = [
            {"start": 0.0, "end": 3.0, "text": "открытие стрима"},
            {"start": 103.5, "end": 106.0, "text": "переходим к метеоре и стейкингу"},
            {"start": 3800.0, "end": 3803.0, "text": "снова метеора и награды"},
        ]
        (groq_out / "stream_segments.json").write_text(
            json.dumps(segments, ensure_ascii=False), encoding="utf-8"
        )
        self.work = work

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, *extra_args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(SCRIPT), str(self.work), "stream", *extra_args],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_search_finds_exact_timestamp_not_containing_block(self) -> None:
        result = self.run_script("--search", "метеор")
        self.assertIn("01:43", result.stdout)
        self.assertIn("1:03:20", result.stdout)
        self.assertNotIn("открытие стрима", result.stdout)

    def test_around_returns_only_window(self) -> None:
        result = self.run_script("--around", "1:43", "--window", "5")
        self.assertIn("переходим к метеоре", result.stdout)
        self.assertNotIn("снова метеора", result.stdout)
        self.assertNotIn("открытие стрима", result.stdout)

    def test_search_without_hits_reports_clearly(self) -> None:
        result = self.run_script("--search", "несуществующее-слово-зюзюзю")
        self.assertIn("no segments contain", result.stdout)


if __name__ == "__main__":
    unittest.main()
