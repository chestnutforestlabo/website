#!/usr/bin/env python3
"""Generate _pages/about.md from all CSV files under data/."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path
import re

URL_RE = re.compile(r"^https?://", re.IGNORECASE)
DEFAULT_PROJECT_IMAGE = "/images/comingsoon.jpg"
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
JAPANESE_PUBLICATION_TOP_BLOCK = """---
permalink: /japanese_publication/
title: "Japanese Publications"
author_profile: true
---

## Japanese Publications
"""

LONG_FORM_OPEN = '<div class="long-form-content" markdown="1">'
LONG_FORM_CLOSE = "</div>"


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
    parser.add_argument(
        "--jp-output",
        default="_pages/japanese_publication.md",
        help="Output markdown file path for Japanese publications (default: _pages/japanese_publication.md)",
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


def parse_year_for_sorting(raw: str) -> int:
    value = clean_plain_text(raw)
    try:
        return int(value)
    except ValueError:
        return -1


def sort_rows_newest_first(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: parse_year_for_sorting(row.get("year", "")), reverse=True)


def sort_rows_oldest_first(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: parse_year_for_sorting(row.get("year", "")))


def is_truthy(value: str) -> bool:
    return clean_plain_text(value).lower() in {"true", "1", "yes", "y"}


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
    text = text.replace("|", "\\|")
    # Prevent markdown from treating CSV asterisks as emphasis.
    text = text.replace("*", "\\*")
    return text


def clean_plain_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def emphasize_author_names(text: str) -> str:
    text = re.sub(r"Masaki Kuribayashi(\\\*)?", r"**Masaki Kuribayashi**\1", text)
    text = re.sub(r"栗林雅希(\\\*)?", r"**栗林雅希**\1", text)
    return text


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


def get_csv_by_relative_path(data_dir: Path, csv_files: list[Path], relative_path: str) -> Path | None:
    target = relative_path.replace("\\", "/")
    for csv_path in csv_files:
        if csv_path.relative_to(data_dir).as_posix() == target:
            return csv_path
    return None


def render_publication_item(index: int, row: dict[str, str]) -> str:
    year = clean_text(row.get("year", ""))
    authors = emphasize_author_names(clean_text(row.get("authors", "")))
    title = clean_text(row.get("title", ""))
    venue = clean_text(row.get("venue", ""))
    award = clean_text(row.get("award", ""))

    parts: list[str] = []
    if authors:
        parts.append(authors)
    if title:
        parts.append(f"**{title}**")
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

    return f"{index}. {sentence}".rstrip()


def resolve_project_image_path(raw: str) -> str:
    value = clean_plain_text(raw)
    if not value:
        return DEFAULT_PROJECT_IMAGE
    if URL_RE.match(value) or value.startswith("/"):
        return value

    normalized = value.lstrip("./")
    if normalized.startswith("images/"):
        return f"/{normalized}"
    return f"/images/{normalized}"


def render_project_item(row: dict[str, str]) -> str:
    title = clean_plain_text(row.get("title", ""))
    venue = clean_plain_text(row.get("venue", ""))
    image_path = resolve_project_image_path(row.get("image", ""))

    title_html = html.escape(title or "Untitled Project")
    venue_html = html.escape(venue)
    image_html = html.escape(image_path, quote=True)
    alt_html = html.escape(title or "Project image", quote=True)

    return "\n".join(
        [
            '<div class="project-item">',
            f'  <div class="project-item__media"><img src="{image_html}" alt="{alt_html}" loading="lazy"></div>',
            '  <div class="project-item__body">',
            f'    <div class="project-item__title">{title_html}</div>',
            f'    <div class="project-item__venue">{venue_html}</div>',
            "  </div>",
            "</div>",
        ]
    )


def render_generic_item(
    columns: list[str], row: dict[str, str], date_last: bool = False, bold_title: bool = False
) -> str:
    lower_cols = {c.lower() for c in columns}
    date = clean_text(row.get("date", ""))
    title = clean_text(row.get("title", ""))
    venue = clean_text(row.get("venue", ""))
    url = clean_text(row.get("url", "")) or clean_text(row.get("link", ""))

    title_display = f"**{title}**" if (bold_title and title) else title

    if "title" in lower_cols and ("url" in lower_cols or "link" in lower_cols) and len(columns) <= 3:
        if URL_RE.match(url):
            if title:
                return f"[{title_display}]({url})"
            return f"[Link]({url})"
        if title and url:
            return f"{title_display} ({url})"
        if title:
            return title_display

    if date and title and venue:
        if date_last:
            return f"{title_display} ({venue}) - {date}"
        return f"{date}: {title_display} ({venue})"
    if date and title:
        if date_last:
            return f"{title_display} - {date}"
        return f"{date}: {title_display}"

    chunks: list[str] = []
    for col in columns:
        value = clean_text(row.get(col, ""))
        if not value:
            continue
        if col.lower() in {"url", "link", "paper_url", "slides", "doi"}:
            chunks.append(format_cell(col, value))
        else:
            label = col.replace("_", " ").title()
            chunks.append(f"{label}: {value}")
    return " | ".join(chunks) if chunks else "-"


def build_section_entries(csv_path: Path, data_dir: Path) -> list[str]:
    fieldnames, rows = read_csv_rows(csv_path)
    columns = used_columns(fieldnames, rows)
    if not columns or not rows:
        return ["_No data available._"]

    if is_publications_csv(csv_path, data_dir):
        sorted_rows = sort_rows_oldest_first(rows)
        return [render_publication_item(i, row) for i, row in enumerate(sorted_rows, start=1)]
    rel = csv_path.relative_to(data_dir).as_posix()
    date_last = rel in {
        "awards.csv",
        "academic_service.csv",
        "talks.csv",
        "fellowships.csv",
        "articles.csv",
    }
    bold_title = rel in {"awards.csv", "academic_service.csv", "talks.csv", "fellowships.csv"}
    entries = [
        render_generic_item(columns, row, date_last=date_last, bold_title=bold_title)
        for row in rows
    ]
    if rel in {"awards.csv", "academic_service.csv", "articles.csv", "fellowships.csv", "talks.csv"}:
        return [f"{i}. {entry}" for i, entry in enumerate(entries, start=1)]
    return entries


def build_markdown(data_dir: Path, csv_files: list[Path]) -> str:
    lines: list[str] = [
        ABOUT_TOP_BLOCK.rstrip(),
        "",
    ]

    # 1) English publications (merge both English publication CSV files)
    en_main = get_csv_by_relative_path(data_dir, csv_files, "en/publications.csv")
    en_short = get_csv_by_relative_path(data_dir, csv_files, "en/publications_short.csv")
    full_rows_newest: list[dict[str, str]] = []
    short_rows_newest: list[dict[str, str]] = []
    project_rows: list[dict[str, str]] = []
    if en_main is not None:
        _, rows = read_csv_rows(en_main)
        full_rows_newest = sort_rows_newest_first(rows)
        project_rows.extend(full_rows_newest)
    if en_short is not None:
        _, rows = read_csv_rows(en_short)
        short_rows_newest = sort_rows_newest_first(rows)
        project_rows.extend([row for row in short_rows_newest if is_truthy(row.get("include", ""))])

    full_rows_oldest = sort_rows_oldest_first(full_rows_newest)
    short_rows_oldest = sort_rows_oldest_first(short_rows_newest)

    lines.append("## Projects")
    lines.append("")
    if project_rows:
        lines.append('<div class="project-list">')
        for row in project_rows:
            lines.append(render_project_item(row))
        lines.append("</div>")
    else:
        lines.append("_No data available._")
    lines.append("")

    lines.append(LONG_FORM_OPEN)
    lines.append("")
    lines.append("## English Publications")
    lines.append("")
    pub_index = 1

    lines.append("### Full Papers")
    lines.append("")
    if en_main is None:
        lines.append("_No data available._<br>")
    else:
        if not full_rows_oldest:
            lines.append("_No data available._<br>")
        for row in full_rows_oldest:
            lines.append(f"{render_publication_item(pub_index, row)}<br>")
            pub_index += 1

    lines.append("")
    lines.append("### Short Papers")
    lines.append("")
    if en_short is None:
        lines.append("_No data available._<br>")
    else:
        if not short_rows_oldest:
            lines.append("_No data available._<br>")
        for row in short_rows_oldest:
            lines.append(f"{render_publication_item(pub_index, row)}<br>")
            pub_index += 1
    lines.append("")
    lines.append("Japanese publications are available [here](/japanese_publication/).<br>")
    lines.append("")

    # 2) Remaining sections in requested order
    ordered_sections = [
        ("awards.csv", "Awards"),
        ("academic_service.csv", "Academic Service"),
        ("fellowships.csv", "Fellowships"),
        ("talks.csv", "Talks"),
        ("articles.csv", "Articles"),
    ]
    for rel_path, title in ordered_sections:
        csv_path = get_csv_by_relative_path(data_dir, csv_files, rel_path)
        if csv_path is None:
            continue
        lines.append(f"## {title}")
        lines.append("")
        entries = build_section_entries(csv_path, data_dir)
        for entry in entries:
            lines.append(f"{entry}<br>")
        lines.append("")

    lines.append(LONG_FORM_CLOSE)
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_japanese_publications_markdown(data_dir: Path, csv_files: list[Path]) -> str:
    jp_csv = get_csv_by_relative_path(data_dir, csv_files, "jp/publications.csv")
    lines: list[str] = [
        JAPANESE_PUBLICATION_TOP_BLOCK.rstrip(),
        "",
        LONG_FORM_OPEN,
        "",
    ]

    if jp_csv is None:
        lines.append("_No data available._")
        lines.append("")
        lines.append(LONG_FORM_CLOSE)
        lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    entries = build_section_entries(jp_csv, data_dir)
    for entry in entries:
        lines.append(f"{entry}<br>")
    lines.append("")
    lines.append("[Back to About](/)<br>")
    lines.append("")
    lines.append(LONG_FORM_CLOSE)
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    output_path = Path(args.output).resolve()
    jp_output_path = Path(args.jp_output).resolve()

    if not data_dir.exists() or not data_dir.is_dir():
        raise SystemExit(f"Data directory not found: {data_dir}")

    csv_files = discover_csv_files(data_dir)
    if not csv_files:
        raise SystemExit(f"No CSV files found under: {data_dir}")

    about_markdown = build_markdown(data_dir, csv_files)
    output_path.write_text(about_markdown, encoding="utf-8")

    jp_markdown = build_japanese_publications_markdown(data_dir, csv_files)
    jp_output_path.write_text(jp_markdown, encoding="utf-8")

    print(
        f"Generated {output_path} and {jp_output_path} from {len(csv_files)} CSV files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
