#!/usr/bin/env python3
"""Build a short context-link block from a stream summary."""

from __future__ import annotations

import argparse
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path


DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)\],;]*)?", re.IGNORECASE)


@dataclass(frozen=True)
class LinkCandidate:
    title: str
    keywords: tuple[str, ...]


LINK_CANDIDATES = [
    LinkCandidate("Рыбный день", ("рыбн", "конкурс трейдер")),
    LinkCandidate(
        "Про безопасность активов",
        ("безопасност", "актив", "cold storage", "аппаратн", "hardware wallet"),
    ),
    LinkCandidate(
        "Про гифты в Telegram",
        ("telegram", "gift", "гифт", "подар", "stars"),
    ),
    LinkCandidate(
        "Arkham аналитика предикшнов",
        ("arkham", "prediction"),
    ),
    LinkCandidate("Собираем роли в Discord", ("discord", "рол")),
    LinkCandidate(
        "Уязвимость для VPS",
        ("vps", "privilege escalation", "уязвим", "root-доступ"),
    ),
    LinkCandidate("Умные очки", ("apple glasses", "ai-очки", "очки")),
    LinkCandidate(
        "Google перевод",
        ("google перевод", "google translate", "переводчик от google"),
    ),
    LinkCandidate("Hyperliquid Spot", ("hyperliquid spot", "zec", "usdc")),
    LinkCandidate("Polymarket и Kalshi", ("polymarket", "kalshi")),
    LinkCandidate("Notion MCP", ("notion mcp", "gtd")),
    LinkCandidate("Playwright и Selenium", ("playwright", "selenium")),
    LinkCandidate("Trezor и SafePal", ("trezor", "safepal")),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build useful context links from a stream summary.")
    parser.add_argument("inputs", type=Path, nargs="+", help="Paths to summary, summary_source, or transcript files")
    parser.add_argument("--output", type=Path, help="Output markdown path; prints to stdout when omitted")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of links")
    return parser.parse_args()


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    ) as handle:
        handle.write(content)
        tmp = Path(handle.name)
    tmp.replace(path)


def normalize_text(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


def candidate_matches(candidate: LinkCandidate, normalized: str) -> bool:
    return any(keyword.lower().replace("ё", "е") in normalized for keyword in candidate.keywords)


def build_links(summary_text: str, limit: int) -> list[str]:
    normalized = normalize_text(summary_text)
    links: list[str] = []
    seen_titles: set[str] = set()

    for candidate in LINK_CANDIDATES:
        if candidate_matches(candidate, normalized):
            links.append(candidate.title)
            seen_titles.add(candidate.title)
            if len(links) >= limit:
                return links

    for match in DOMAIN_RE.finditer(summary_text):
        domain = match.group(0).rstrip(".,;:)")
        title = domain.replace("https://", "").replace("http://", "")
        if title not in seen_titles:
            links.append(title)
            seen_titles.add(title)
            if len(links) >= limit:
                return links

    return links


def render_link_block(links: list[str]) -> str:
    lines = ["## Полезные ссылки из чата:", ""]
    if not links:
        lines.append("• Не найдено явных инструментов, сервисов или тем для отдельного поиска.")
    else:
        lines.extend(f"• {title}" for title in links)
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be positive")
    text = "\n".join(path.expanduser().resolve().read_text(encoding="utf-8") for path in args.inputs)
    content = render_link_block(build_links(text, args.limit))
    if args.output:
        atomic_write_text(args.output.expanduser().resolve(), content)
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
