#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_ama_timecodes.py"
VALIDATE_SCRIPT = ROOT / "scripts" / "validate_outputs.py"


class BuildAmaTimecodesTest(unittest.TestCase):
    def test_builds_candidates_and_reviewed_question_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            groq = work / "groq_outputs"
            output = work / "summary_outputs"
            groq.mkdir()
            output.mkdir()
            segments = [
                {"start": 10, "end": 14, "text": "переходим к следующему вопросу"},
                {"start": 14, "end": 19, "text": "если строить систему исследования крипторынка с нуля"},
                {"start": 19, "end": 25, "text": "какие источники информации оставить обязательно"},
                {"start": 40, "end": 44, "text": "вопрос номер два"},
                {"start": 44, "end": 49, "text": "какие задачи сегодня можно передать искусственному интеллекту"},
                {"start": 49, "end": 55, "text": "а какие нужно делать вручную"},
            ]
            (groq / "ama_segments.json").write_text(json.dumps(segments, ensure_ascii=False), encoding="utf-8")
            (groq / "ama_transcript.txt").write_text("00:00:10  вопрос\n", encoding="utf-8")
            (groq / "ama_summary_source.md").write_text("00:00:00  блок\n", encoding="utf-8")
            (groq / "ama_meta.json").write_text(
                json.dumps({"provider": "groq", "summary_source_lines": 1}, ensure_ascii=False), encoding="utf-8"
            )
            questions = work / "questions.md"
            questions.write_text(
                "- Если строить исследование крипторынка с нуля, какие источники оставить?\n"
                "- Какие задачи передать ИИ, а какие делать вручную?\n",
                encoding="utf-8",
            )
            subprocess.run(["python3", str(SCRIPT), str(work), "ama", str(questions)], check=True, capture_output=True, text=True)
            draft = (output / "ama_ama_timecodes_candidates.md").read_text(encoding="utf-8")
            self.assertIn("00:10", draft)
            review = work / "review.md"
            review.write_text("00:10 - Источники для исследования крипторынка\n00:40 - Ручные и ИИ-задачи\n", encoding="utf-8")
            subprocess.run(
                ["python3", str(SCRIPT), str(work), "ama", str(questions), "--review-file", str(review)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                (output / "ama_ama_timecodes.md").read_text(encoding="utf-8").splitlines()[0],
                "00:10 - Источники для исследования крипторынка",
            )
            source = (groq / "ama_ama_source.md").read_text(encoding="utf-8")
            self.assertIn("## 00:10 Источники для исследования крипторынка", source)
            self.assertIn("## 00:40 Ручные и ИИ-задачи", source)
            result = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "ama", "--check-ama"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("VALIDATION_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
