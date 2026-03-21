#!/usr/bin/env python3
"""Generate an Awesome-CV from the repository data files."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"
DEFAULT_CONFIG_PATH = REPO_ROOT / "_config.yml"
DEFAULT_OUTPUT_TEX = SCRIPT_DIR / "generated_cv.tex"
DEFAULT_SECTIONS_DIR = SCRIPT_DIR / "generated"
DEFAULT_PHOTO_PATH = REPO_ROOT / "data" / "image" / "profile.jpg"

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

CJK_RE = re.compile(r"[\u3000-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Awesome-CV files from repo data.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-tex", type=Path, default=DEFAULT_OUTPUT_TEX)
    parser.add_argument("--sections-dir", type=Path, default=DEFAULT_SECTIONS_DIR)
    parser.add_argument("--photo", type=Path, default=DEFAULT_PHOTO_PATH)
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, skipinitialspace=True)
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {key: normalize_cell(value) for key, value in row.items() if key}
            if any(cleaned.values()):
                rows.append(normalize_row(cleaned))
        return rows


def normalize_cell(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).strip('"')


def normalize_row(row: dict[str, str]) -> dict[str, str]:
    if {"venue", "url"}.issubset(row):
        venue = row.get("venue", "")
        url = row.get("url", "")
        slides = row.get("slides", "")
        if venue and url and not looks_like_url(url) and not slides:
            row["venue"] = f"{venue}, {url}"
            row["url"] = ""
    return row


def looks_like_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://") or value.startswith("/")


def clean_yaml_scalar(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"^&\S+\s*", "", value)
    if value in {"", "null"}:
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def load_site_metadata(config_path: Path) -> dict[str, str]:
    top_level: dict[str, str] = {}
    author: dict[str, str] = {}
    current_section = ""

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split(" #", 1)[0].rstrip()
        if not line.strip():
            continue

        if re.match(r"^[A-Za-z0-9_-]+\s*:", line):
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_section = key if not value else ""
            if key != "author" and value:
                top_level[key] = clean_yaml_scalar(value)
            continue

        if current_section == "author" and re.match(r"^\s{2}[A-Za-z0-9_-]+\s*:", line):
            key, value = line.split(":", 1)
            author[key.strip()] = clean_yaml_scalar(value)

    description = top_level.get("description") or author.get("bio", "")
    return {
        "name": author.get("name") or top_level.get("title", ""),
        "position": description,
        "location": author.get("location", ""),
        "email": author.get("email", ""),
        "github": author.get("github", ""),
        "linkedin": author.get("linkedin", ""),
        "twitter": author.get("twitter", ""),
        "googlescholar": author.get("googlescholar", ""),
        "site_url": (top_level.get("url") or "").rstrip("/") + "/",
    }


def split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.split()
    if len(parts) < 2:
        return full_name, ""
    return " ".join(parts[:-1]), parts[-1]


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text))


def latex_text(text: str) -> str:
    escaped = latex_escape(text)
    if contains_cjk(text):
        return r"{\jpfont " + escaped + "}"
    return escaped


def latex_escape_url(url: str) -> str:
    replacements = {
        "\\": "/",
        "%": r"\%",
        "#": r"\#",
        "&": r"\&",
        "{": r"\{",
        "}": r"\}",
        " ": "%20",
    }
    return "".join(replacements.get(char, char) for char in url)


def latex_href(url: str, label: str) -> str:
    return rf"\href{{{latex_escape_url(url)}}}{{{latex_escape(label)}}}"


def local_or_remote_url(raw: str, site_url: str) -> str:
    if not raw:
        return ""
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/"):
        return urljoin(site_url, raw.lstrip("/"))
    return raw


def date_sort_key(raw: str) -> tuple[int, int]:
    text = raw.lower()
    if "current" in text or "present" in text:
        year = 9999
    else:
        years = [int(match) for match in re.findall(r"(?:19|20)\d{2}", text)]
        year = years[-1] if years else 0

    month = 0
    for token, number in MONTHS.items():
        if re.search(rf"\b{re.escape(token)}\.?\b", text):
            month = number
    return (year, month)


def sort_by_date_desc(rows: list[dict[str, str]], key: str = "date") -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: date_sort_key(row.get(key, "")), reverse=True)


def sort_by_date_asc(rows: list[dict[str, str]], key: str = "date") -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: date_sort_key(row.get(key, "")))


def sort_by_year_desc(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: int(row.get("year", "0") or 0), reverse=True)


def strip_equal_contribution_note(text: str) -> str:
    return re.sub(r"\s*\(\s*\*\s*-\s*equal contribution\s*\)\s*$", "", text, flags=re.IGNORECASE).strip()


def emphasize_name(text: str) -> str:
    escaped = latex_escape(strip_equal_contribution_note(text))
    return escaped.replace("Masaki Kuribayashi", r"\textbf{Masaki Kuribayashi}")


def hostname_from_url(url: str) -> str:
    host = urlparse(url).netloc
    return host.removeprefix("www.")


def extract_year(text: str) -> str:
    matches = re.findall(r"(?:19|20)\d{2}", text)
    return matches[-1] if matches else ""


def bio_to_entry(row: dict[str, str]) -> dict[str, object]:
    date = latex_text(row.get("date", ""))
    raw_title = row.get("title", "")
    advisor_note = ""
    if ", Advisor:" in raw_title:
        raw_title, advisor = raw_title.split(", Advisor:", 1)
        advisor_note = f"Advisor: {advisor.strip()}"

    if " at " in raw_title and "," not in raw_title:
        role, org = [part.strip() for part in raw_title.split(" at ", 1)]
    else:
        parts = [part.strip() for part in raw_title.split(",") if part.strip()]
        if len(parts) >= 2:
            role = parts[0]
            org = ", ".join(parts[1:])
        else:
            role = raw_title.strip()
            org = ""

    items: list[str] = []
    if advisor_note:
        items.append(latex_text(advisor_note))

    return {
        "position": latex_text(role),
        "title": latex_text(org),
        "location": "",
        "date": date,
        "items": items,
    }


def is_education_row(row: dict[str, str]) -> bool:
    title = row.get("title", "").lower()
    return "student at" in title or "ph.d." in title


def publication_to_entry(row: dict[str, str], site_url: str) -> dict[str, object]:
    items = [f"Authors: {emphasize_name(row.get('authors', ''))}"]

    award = row.get("award", "")
    if award:
        items.append(f"{latex_text(award)}")

    links: list[str] = []
    doi = local_or_remote_url(row.get("doi", ""), site_url)
    paper = local_or_remote_url(row.get("paper_url", ""), site_url)
    slides = local_or_remote_url(row.get("slides", ""), site_url)
    if doi:
        links.append(latex_href(doi, "DOI"))
    if paper:
        links.append(latex_href(paper, "Paper"))
    if slides:
        links.append(latex_href(slides, "Slides"))
    if links:
        items.append("Links: " + r" \enskip\textbar\enskip ".join(links))

    return {
        "position": latex_text(row.get("venue", "")),
        "title": latex_text(row.get("title", "")),
        "location": "",
        "date": latex_text(row.get("year", "")),
        "items": items,
    }


def talk_to_entry(row: dict[str, str], site_url: str) -> dict[str, object]:
    links: list[str] = []
    url = local_or_remote_url(row.get("url", ""), site_url)
    slides = local_or_remote_url(row.get("slides", ""), site_url)
    if url:
        links.append(latex_href(url, "Event"))
    if slides:
        links.append(latex_href(slides, "Slides"))

    items: list[str] = []
    if links:
        items.append("Links: " + r" \enskip\textbar\enskip ".join(links))

    return {
        "position": latex_text(row.get("venue", "")),
        "title": latex_text(row.get("title", "")),
        "location": "",
        "date": latex_text(row.get("date", "")),
        "items": items,
    }


def article_to_entry(row: dict[str, str], site_url: str) -> dict[str, object]:
    url = local_or_remote_url(row.get("url", ""), site_url)
    items = [f"Read: {latex_href(url, 'Link')}"] if url else []
    return {
        "position": latex_escape(hostname_from_url(url) if url else "Article"),
        "title": latex_text(row.get("title", "")),
        "location": "",
        "date": "",
        "items": items,
    }


def honor_from_title_date(title: str, date: str) -> dict[str, str]:
    return {
        "position": latex_text(title),
        "title": "",
        "location": "",
        "date": latex_text(date),
    }


def service_to_honor(row: dict[str, str]) -> dict[str, str]:
    service = row.get("service", "")
    parts = [part.strip() for part in service.split(",") if part.strip()]
    position = parts[0] if parts else service
    title = ", ".join(parts[1:]) if len(parts) > 1 else ""
    return {
        "position": latex_text(position),
        "title": latex_text(title),
        "location": "",
        "date": latex_text(extract_year(service)),
    }


def render_items(items: list[str]) -> str:
    if not items:
        return "    {}"
    lines = ["    {", "      \\begin{cvitems}"]
    for item in items:
        lines.append(f"        \\item {{{item}}}")
    lines.extend(["      \\end{cvitems}", "    }"])
    return "\n".join(lines)


def render_cventry(entry: dict[str, object]) -> str:
    return "\n".join(
        [
            "  \\cventry",
            f"    {{{entry['position']}}}",
            f"    {{{entry['title']}}}",
            f"    {{{entry['location']}}}",
            f"    {{{entry['date']}}}",
            render_items(entry["items"]),
            "",
        ]
    )


def render_cventries_section(title: str, entries: list[dict[str, object]]) -> str:
    lines = [
        "%-------------------------------------------------------------------------------",
        f"\\cvsection{{{latex_escape(title)}}}",
        "",
        "\\begin{cventries}",
        "",
    ]
    for entry in entries:
        lines.append("%---------------------------------------------------------")
        lines.append(render_cventry(entry).rstrip())
        lines.append("")
    lines.append("\\end{cventries}")
    lines.append("")
    return "\n".join(lines)


def render_honors_block(items: list[dict[str, str]]) -> list[str]:
    lines = ["\\begin{cvhonors}", ""]
    for item in items:
        lines.extend(
            [
                "%---------------------------------------------------------",
                "  \\cvhonor",
                f"    {{{item['position']}}}",
                f"    {{{item['title']}}}",
                f"    {{{item['location']}}}",
                f"    {{{item['date']}}}",
                "",
            ]
        )
    lines.append("\\end{cvhonors}")
    lines.append("")
    return lines


def render_honors_section(
    title: str,
    subsections: list[tuple[str, list[dict[str, str]]]],
) -> str:
    lines = [
        "%-------------------------------------------------------------------------------",
        f"\\cvsection{{{latex_escape(title)}}}",
        "",
    ]
    for subsection_title, items in subsections:
        if not items:
            continue
        lines.extend(
            [
                "%-------------------------------------------------------------------------------",
                f"\\cvsubsection{{{latex_escape(subsection_title)}}}",
                "",
            ]
        )
        lines.extend(render_honors_block(items))
    return "\n".join(lines)


def render_publications_section(
    peer_reviewed: list[dict[str, object]],
    posters_workshops: list[dict[str, object]],
) -> str:
    lines = [
        "%-------------------------------------------------------------------------------",
        "\\cvsection{Publications}",
        "",
        "\\begin{cvparagraph}",
        "\\textasteriskcentered{} indicates equal contribution.",
        "\\end{cvparagraph}",
        "",
    ]

    if peer_reviewed:
        lines.extend(
            [
                "%-------------------------------------------------------------------------------",
                "\\cvsubsection{Peer-Reviewed}",
                "",
                "\\begin{cventries}",
                "",
            ]
        )
        for entry in peer_reviewed:
            lines.append("%---------------------------------------------------------")
            lines.append(render_cventry(entry).rstrip())
            lines.append("")
        lines.append("\\end{cventries}")
        lines.append("")

    if posters_workshops:
        lines.extend(
            [
                "%-------------------------------------------------------------------------------",
                "\\cvsubsection{Posters \\& Workshops}",
                "",
                "\\begin{cventries}",
                "",
            ]
        )
        for entry in posters_workshops:
            lines.append("%---------------------------------------------------------")
            lines.append(render_cventry(entry).rstrip())
            lines.append("")
        lines.append("\\end{cventries}")
        lines.append("")

    return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_main_tex(metadata: dict[str, str], section_names: list[str], photo_path: Path) -> str:
    first_name, last_name = split_name(metadata["name"])
    position_parts = [latex_escape(part.strip()) for part in metadata["position"].split("|") if part.strip()]
    position = r"{\enskip\cdotp\enskip}".join(position_parts)

    photo_line = ""
    if photo_path.exists():
        relative_photo = Path("..") / photo_path.relative_to(REPO_ROOT)
        photo_line = rf"\photo[circle,noedge,right]{{{relative_photo.as_posix()}}}"

    scholar_url = metadata.get("googlescholar", "")
    scholar_id = ""
    if "user=" in scholar_url:
        scholar_id = scholar_url.split("user=", 1)[1].split("&", 1)[0]

    lines = [
        "%!TEX TS-program = xelatex",
        "%!TEX encoding = UTF-8 Unicode",
        "\\documentclass[11pt, a4paper]{awesome-cv}",
        "",
        "\\geometry{left=1.4cm, top=.8cm, right=1.4cm, bottom=1.8cm, footskip=.5cm}",
        "\\colorlet{awesome}{awesome-red}",
        "\\setbool{acvSectionColorHighlight}{true}",
        "\\renewcommand{\\acvHeaderSocialSep}{\\quad\\textbar\\quad}",
        "\\IfFontExistsTF{Hiragino Sans}{%",
        "  \\newfontfamily\\jpfont{Hiragino Sans}%",
        "}{%",
        "  \\newfontfamily\\jpfont{HaranoAjiGothic-Medium}%",
        "}",
        "",
    ]
    if photo_line:
        lines.append(photo_line)
    lines.extend(
        [
            rf"\name{{{latex_escape(first_name)}}}{{{latex_escape(last_name)}}}",
            rf"\position{{{position}}}",
            rf"\address{{{latex_escape(metadata['location'])}}}",
        ]
    )

    if metadata.get("email"):
        lines.append(rf"\email{{{latex_escape(metadata['email'])}}}")
    if metadata.get("github"):
        lines.append(rf"\github{{{latex_escape(metadata['github'])}}}")
    if metadata.get("linkedin"):
        lines.append(rf"\linkedin{{{latex_escape(metadata['linkedin'])}}}")
    if metadata.get("twitter"):
        lines.append(rf"\twitter{{{latex_escape(metadata['twitter'])}}}")
    if scholar_id:
        lines.append(rf"\googlescholar{{{latex_escape(scholar_id)}}}{{}}")

    lines.extend(
        [
            "",
            "\\begin{document}",
            "\\makecvheader",
            "\\makecvfooter",
            "  {\\today}",
            rf"  {{{latex_escape(metadata['name'])}~~~\textperiodcentered~~~Curriculum Vitae}}",
            "  {\\thepage}",
            "",
        ]
    )

    for section_name in section_names:
        lines.append(rf"\input{{generated/{section_name}.tex}}")

    lines.extend(["", "\\end{document}", ""])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    metadata = load_site_metadata(args.config)
    site_url = metadata.get("site_url", "")

    bio_rows = read_csv_rows(args.data_dir / "bio.csv")
    awards_rows = read_csv_rows(args.data_dir / "awards.csv")
    fellowships_rows = read_csv_rows(args.data_dir / "fellowships.csv")
    service_rows = read_csv_rows(args.data_dir / "academic_service.csv")
    talks_rows = read_csv_rows(args.data_dir / "talks.csv")
    articles_rows = read_csv_rows(args.data_dir / "articles.csv")
    publications_rows = read_csv_rows(args.data_dir / "en" / "publications.csv")
    short_publications_rows = read_csv_rows(args.data_dir / "en" / "publications_short.csv")

    args.sections_dir.mkdir(parents=True, exist_ok=True)
    for stale_tex in args.sections_dir.glob("*.tex"):
        stale_tex.unlink()

    education_entries = [
        bio_to_entry(row) for row in sort_by_date_desc([row for row in bio_rows if is_education_row(row)])
    ]
    experience_entries = [
        bio_to_entry(row) for row in sort_by_date_desc([row for row in bio_rows if not is_education_row(row)])
    ]
    peer_reviewed_entries = [
        publication_to_entry(row, site_url) for row in sort_by_year_desc(publications_rows)
    ]
    short_publication_entries = [
        publication_to_entry(row, site_url) for row in sort_by_year_desc(short_publications_rows)
    ]
    talk_entries = [talk_to_entry(row, site_url) for row in sort_by_date_asc(talks_rows)]
    article_entries = [article_to_entry(row, site_url) for row in articles_rows]

    awards = [
        honor_from_title_date(row.get("title", ""), row.get("date", ""))
        for row in sort_by_date_desc(awards_rows)
    ]
    fellowships = [
        honor_from_title_date(row.get("title", ""), row.get("date", ""))
        for row in sort_by_date_desc(fellowships_rows)
    ]
    services = [service_to_honor(row) for row in sort_by_date_desc(service_rows, key="service")]

    section_names: list[str] = []
    if education_entries:
        write_text(args.sections_dir / "education.tex", render_cventries_section("Education", education_entries))
        section_names.append("education")
    if experience_entries:
        write_text(args.sections_dir / "experience.tex", render_cventries_section("Experience", experience_entries))
        section_names.append("experience")
    if peer_reviewed_entries or short_publication_entries:
        write_text(
            args.sections_dir / "publications.tex",
            render_publications_section(peer_reviewed_entries, short_publication_entries),
        )
        section_names.append("publications")
    if talk_entries:
        write_text(args.sections_dir / "talks.tex", render_cventries_section("Talks", talk_entries))
        section_names.append("talks")
    if article_entries:
        write_text(args.sections_dir / "writing.tex", render_cventries_section("Writing", article_entries))
        section_names.append("writing")
    if awards or fellowships:
        write_text(
            args.sections_dir / "honors.tex",
            render_honors_section("Honors & Funding", [("Awards", awards), ("Fellowships", fellowships)]),
        )
        section_names.append("honors")
    if services:
        write_text(
            args.sections_dir / "service.tex",
            render_honors_section("Academic Service", [("Service", services)]),
        )
        section_names.append("service")

    main_tex = build_main_tex(metadata, section_names, args.photo)
    write_text(args.output_tex, main_tex)

    print(f"Generated {args.output_tex}")
    for section_name in section_names:
        print(f"Generated {args.sections_dir / f'{section_name}.tex'}")


if __name__ == "__main__":
    main()
