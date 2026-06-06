#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINKS_SCRIPT = PROJECT_ROOT / "scripts" / "build_context_links.py"


class BuildContextLinksTest(unittest.TestCase):
    def test_builds_context_link_block_from_summary_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            summary = work / "summary.md"
            output = work / "links.md"
            summary.write_text(
                "\n".join(
                    [
                        "00:00:00 Обсудили рыбный день и fund.thevsedefi.xyz.",
                        "00:10:00 Отметили Arkham prediction analytics, Polymarket и Kalshi.",
                        "00:20:00 Разобрали Telegram gifts, Discord роли и Google перевод.",
                        "00:30:00 Подняли безопасность активов, VPS privilege escalation и cold storage.",
                        "00:40:00 Обсудили Apple Glasses и AI-очки.",
                    ]
                ),
                encoding="utf-8",
            )

            transcript = work / "transcript.txt"
            transcript.write_text("Позже отдельно упомянули Trezor и SafePal.", encoding="utf-8")

            subprocess.run(
                ["python3", str(LINKS_SCRIPT), str(summary), str(transcript), "--output", str(output), "--limit", "12"],
                check=True,
                capture_output=True,
                text=True,
            )

            content = output.read_text(encoding="utf-8")
            self.assertIn("## Полезные ссылки из чата:", content)
            self.assertIn("• Рыбный день", content)
            self.assertIn("• Про безопасность активов", content)
            self.assertIn("• Arkham аналитика предикшнов", content)
            self.assertIn("• fund.thevsedefi.xyz", content)
            self.assertIn("• Собираем роли в Discord", content)
            self.assertIn("• Уязвимость для VPS", content)
            self.assertIn("• Умные очки", content)
            self.assertIn("• Trezor и SafePal", content)
            self.assertNotIn("http", content)
            self.assertNotIn("](", content)


if __name__ == "__main__":
    unittest.main()
