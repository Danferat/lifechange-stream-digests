#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
import unittest
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIGEST_SCRIPT = PROJECT_ROOT / "scripts" / "build_final_digest.py"
VALIDATE_SCRIPT = PROJECT_ROOT / "scripts" / "validate_outputs.py"


class BuildFinalDigestTest(unittest.TestCase):
    def test_builds_optional_long_and_required_short_export_files_with_context_topics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            summary_out = work / "summary_outputs"
            groq_out = work / "groq_outputs"
            summary_out.mkdir()
            groq_out.mkdir()
            (groq_out / "stream_segments.json").write_text(
                json.dumps([{"start": 0, "end": 1, "text": "старт"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (groq_out / "stream_summary_source.md").write_text(
                "\n".join(f"00:00:{index:02d}  строка" for index in range(48)) + "\n",
                encoding="utf-8",
            )
            (groq_out / "stream_meta.json").write_text(
                json.dumps({"provider": "groq", "summary_source_lines": 48}, ensure_ascii=False),
                encoding="utf-8",
            )
            (summary_out / "stream_summary.md").write_text(
                "\n".join(f"00:00:{index:02d}  Обсудили строку {index}." for index in range(48)) + "\n",
                encoding="utf-8",
            )
            (summary_out / "stream_summary_intermediate.md").write_text(
                "# Промежуточная выжимка\n\n"
                + "\n\n".join(f"## 00:00:{index:02d} Обсудили строку {index}.\n\nсырой блок" for index in range(48))
                + "\n",
                encoding="utf-8",
            )
            (summary_out / "stream_summary_short.md").write_text(
                "\n".join(f"00:00:{index:02d} Краткая строка {index}" for index in range(19)) + "\n",
                encoding="utf-8",
            )
            (groq_out / "stream_transcript.txt").write_text(
                "00:00:00  Упомянули Arkham prediction analytics, VPS privilege escalation и fund.thevsedefi.xyz.",
                encoding="utf-8",
            )

            digest_result = subprocess.run(
                ["python3", str(DIGEST_SCRIPT), str(work), "stream", "--limit", "5"],
                check=True,
                capture_output=True,
                text=True,
            )

            long_with_links = (summary_out / "stream_summary_with_links.md").read_text(encoding="utf-8")
            short_with_links = (summary_out / "stream_summary_short_with_links.md").read_text(encoding="utf-8")
            summary = (summary_out / "stream_summary.md").read_text(encoding="utf-8")
            short = (summary_out / "stream_summary_short.md").read_text(encoding="utf-8")
            self.assertIn("SUMMARY_WITH_LINKS=", digest_result.stdout)
            self.assertIn("SUMMARY_SHORT_WITH_LINKS=", digest_result.stdout)
            self.assertNotIn("CONTEXT_LINKS=", digest_result.stdout)
            self.assertNotIn("FINAL_DIGEST=", digest_result.stdout)
            self.assertNotIn("Полезные ссылки из чата", summary)
            self.assertNotIn("Полезные ссылки из чата", short)
            self.assertTrue(long_with_links.startswith("00:00:00  Обсудили строку 0."))
            self.assertTrue(short_with_links.startswith("00:00:00 Краткая строка 0"))
            self.assertIn("\n\n## Полезные ссылки из чата:\n\n", long_with_links)
            self.assertIn("\n\n## Полезные ссылки из чата:\n\n", short_with_links)
            self.assertIn("• Arkham аналитика предикшнов", long_with_links)
            self.assertIn("• Уязвимость для VPS", short_with_links)
            self.assertIn("• fund.thevsedefi.xyz", long_with_links)
            self.assertIn("• fund.thevsedefi.xyz", short_with_links)
            self.assertNotIn("http", long_with_links)
            self.assertNotIn("http", short_with_links)

            result = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "stream", "--check-final"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("VALIDATION_OK", result.stdout)

            (summary_out / "stream_summary_short_with_links.md").unlink()
            missing_final = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "stream", "--check-final"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(missing_final.returncode, 0)
            self.assertIn("summary_short_with_links", missing_final.stderr.lower() + missing_final.stdout.lower())

            (summary_out / "stream_summary_short_with_links.md").write_text(short_with_links, encoding="utf-8")
            polluted_short = short.replace("00:00:00 Краткая строка 0", "00:00:00 Полезные ссылки из чата")
            (summary_out / "stream_summary_short.md").write_text(polluted_short, encoding="utf-8")
            polluted_result = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "stream", "--check-final"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(polluted_result.returncode, 0)
            self.assertIn("summary_short", polluted_result.stderr.lower() + polluted_result.stdout.lower())

            (summary_out / "stream_summary_short.md").write_text(short, encoding="utf-8")
            dotted_short = short.replace("00:00:01 Краткая строка 1", "00:00:01 Краткая строка 1.")
            (summary_out / "stream_summary_short.md").write_text(dotted_short, encoding="utf-8")
            dotted_result = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "stream", "--check-final"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(dotted_result.returncode, 0)
            self.assertIn("must not end with a period", dotted_result.stderr + dotted_result.stdout)

    def test_builds_short_only_export_when_long_summary_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            summary_out = work / "summary_outputs"
            groq_out = work / "groq_outputs"
            summary_out.mkdir()
            groq_out.mkdir()
            (groq_out / "stream_segments.json").write_text(
                json.dumps([{"start": 0, "end": 1, "text": "старт"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (groq_out / "stream_summary_source.md").write_text(
                "\n".join(f"00:00:{index:02d}  строка" for index in range(48)) + "\n",
                encoding="utf-8",
            )
            (groq_out / "stream_meta.json").write_text(
                json.dumps({"provider": "groq", "summary_source_lines": 48}, ensure_ascii=False),
                encoding="utf-8",
            )
            (summary_out / "stream_summary_intermediate.md").write_text(
                "# Промежуточная выжимка\n\n"
                + "\n\n".join(f"## 00:00:{index:02d} Блок {index}.\n\nсырой блок" for index in range(48))
                + "\n",
                encoding="utf-8",
            )
            (summary_out / "stream_summary_short.md").write_text(
                "\n".join(f"00:00:{index:02d} Краткая строка {index}" for index in range(19)) + "\n",
                encoding="utf-8",
            )
            (groq_out / "stream_transcript.txt").write_text(
                "00:00:00  Упомянули Arkham prediction analytics и VPS privilege escalation.",
                encoding="utf-8",
            )

            digest_result = subprocess.run(
                ["python3", str(DIGEST_SCRIPT), str(work), "stream", "--limit", "5"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertNotIn("SUMMARY_WITH_LINKS=", digest_result.stdout)
            self.assertIn("SUMMARY_SHORT_WITH_LINKS=", digest_result.stdout)
            self.assertFalse((summary_out / "stream_summary_with_links.md").exists())
            self.assertTrue((summary_out / "stream_summary_short_with_links.md").exists())

            result = subprocess.run(
                ["python3", str(VALIDATE_SCRIPT), str(work), "stream", "--check-final"],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("VALIDATION_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
