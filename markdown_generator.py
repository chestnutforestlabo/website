#!/usr/bin/env python3
"""Generate _pages/about.md from all CSV files under data/."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
ABOUT_TOP_BLOCK = """---
permalink: /
title: "Masaki Kuribayashi"
author_profile: true
redirect_from: 
  - /about/
  - /about.html
---

Resercher at Miraikan Accessibility Lab.

**Reserach Interest**: Assitive Navigation for Blind People, Vision and Language Navigation
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate _pages/about.md from all CSV files under data/."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing CSV files (default: data)",
    )
    parser.add_argument(
        "--output",
        default="_pages/about.md",
        help="Output markdown file path (default: _pages/about.md)",
    )
    return parser.parse_args()


def discover_csv_files(data_dir: Path) -> list[Path]:
    return sorted(p for p in data_dir.rglob("*.csv") if p.is_file())


def prettify_section_name(csv_path: Path, data_dir: Path) -> str:
    relative = csv_path.relative_to(data_dir)
    parts = list(relative.parts)
    parts[-1] = Path(parts[-1]).stem
    words = []
    for part in parts:
        token = part.replace("_", " ").replace("-", " ").strip()
        if token.lower() in {"en", "jp"}:
            words.append(token.upper())
        else:
            words.append(token.title())
    return " / ".join(words)


def read_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        fieldnames = reader.fieldnames or []
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {k: (v or "").strip() for k, v in row.items() if k is not None}
            if any(cleaned.values()):
                cleaned = normalize_row(cleaned)
                rows.append(cleaned)
        return fieldnames, rows


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    # Some records put plain location text in `url` because the source has an
    # extra comma in the venue field. Merge it back for cleaner output.
    if {"venue", "url"}.issubset(row.keys()):
        venue = row.get("venue", "").strip()
        url = row.get("url", "").strip()
        slides = row.get("slides", "").strip()
        if venue and url and not URL_RE.match(url) and not slides:
            row["venue"] = f"{venue}, {url}"
            row["url"] = ""
    return row


def used_columns(fieldnames: list[str], rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return fieldnames
    cols: list[str] = []
    for col in fieldnames:
        if any((row.get(col) or "").strip() for row in rows):
            cols.append(col)
    return cols


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text.replace("|", "\\|")


def format_cell(key: str, raw: str) -> str:
    value = clean_text(raw)
    if not value:
        return "-"

    key_lower = key.lower()
    if key_lower == "doi":
        doi_url = value if URL_RE.match(value) else f"https://doi.org/{value}"
        return f"[DOI]({doi_url})"

    if key_lower in {"url", "link", "paper_url", "slides"}:
        if URL_RE.match(value):
            label = "Slides" if key_lower == "slides" else "Link"
            return f"[{label}]({value})"
        return value

    if URL_RE.match(value):
        return f"[Link]({value})"

    return value


def is_publications_csv(csv_path: Path, data_dir: Path) -> bool:
    rel = csv_path.relative_to(data_dir).as_posix().lower()
    return "publications" in rel


def render_publication_item(index: int, row: dict[str, str]) -> str:
    year = clean_text(row.get("year", ""))
    authors = clean_text(row.get("authors", ""))
    title = clean_text(row.get("title", ""))
    venue = clean_text(row.get("venue", ""))
    award = clean_text(row.get("award", ""))

    parts: list[str] = []
    if authors:
        parts.append(authors)
    if title:
        parts.append(f"\"{title}\"")
    if venue:
        parts.append(venue)
    if year:
        parts.append(f"({year})")
    if award:
        parts.append(f"Award: {award}")

    links: list[str] = []
    for key in ("doi", "paper_url", "url", "slides"):
        value = clean_text(row.get(key, ""))
        if not value:
            continue
        formatted = format_cell(key, value)
        if formatted != "-":
            links.append(formatted)

    sentence = ". ".join(parts).strip()
    if sentence and not sentence.endswith("."):
        sentence += "."
    if links:
        sentence += " " + " ".join(links)

    return f"- [{index}] {sentence}".rstrip()


def render_generic_item(columns: list[str], row: dict[str, str]) -> str:
    lower_cols = {c.lower() for c in columns}
    date = clean_text(row.get("date", ""))
    title = clean_text(row.get("title", ""))
    venue = clean_text(row.get("venue", ""))
    url = clean_text(row.get("url", "")) or clean_text(row.get("link", ""))

    if "title" in lower_cols and ("url" in lower_cols or "link" in lower_cols) and len(columns) <= 3:
        if URL_RE.match(url):
            return f"- [{title}]({url})" if title else f"- [Link]({url})"
        if title and url:
            return f"- {title} ({url})"
        if title:
            return f"- {title}"

    if date and title and venue:
        return f"- **{date}**: {title} ({venue})"
    if date and title:
        return f"- **{date}**: {title}"

    chunks: list[str] = []
    for col in columns:
        value = clean_text(row.get(col, ""))
        if not value:
            continue
        if col.lower() in {"url", "link", "paper_url", "slides", "doi"}:
            chunks.append(format_cell(col, value))
        else:
            label = col.replace("_", " ").title()
            chunks.append(f"**{label}:** {value}")
    return "- " + (" | ".join(chunks) if chunks else "-")


def build_markdown(data_dir: Path, csv_files: list[Path]) -> str:
    lines: list[str] = [
        ABOUT_TOP_BLOCK.rstrip(),
        "",
    ]

    for csv_path in csv_files:
        section = prettify_section_name(csv_path, data_dir)
        fieldnames, rows = read_csv_rows(csv_path)
        columns = used_columns(fieldnames, rows)

        lines.append(f"## {section}")
        lines.append("")

        if not columns:
            lines.append("_No data available._")
            lines.append("")
            continue

        if not rows:
            lines.append("_No data available._")
            lines.append("")
            continue

        if is_publications_csv(csv_path, data_dir):
            for i, row in enumerate(rows, start=1):
                lines.append(render_publication_item(i, row))
        else:
            for row in rows:
                lines.append(render_generic_item(columns, row))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    output_path = Path(args.output).resolve()

    if not data_dir.exists() or not data_dir.is_dir():
        raise SystemExit(f"Data directory not found: {data_dir}")

    csv_files = discover_csv_files(data_dir)
    if not csv_files:
        raise SystemExit(f"No CSV files found under: {data_dir}")

    markdown = build_markdown(data_dir, csv_files)
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Generated {output_path} from {len(csv_files)} CSV files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
