"""Extract chapter-bounded Markdown files from a locally supplied white paper PDF."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = REPO_ROOT / "Test methods for battery understanding_v3_0.pdf"
OUTPUT_DIR = REPO_ROOT / "data" / "methods" / "battery_understanding_v3_0"
CHAPTERS_DIR = OUTPUT_DIR / "chapters"
CHAPTER_INDEX_PATH = OUTPUT_DIR / "chapter_index.json"

TOP_LEVEL_TITLES = {
    "Introduction",
    "Glossary",
    "Introductory topics about battery cell testing",
    "Battery cell performance",
    "Ageing effects",
    "Safety aspects",
    "Thermal",
    "Discussion",
    "Recommendations to specific test standards",
    "Conclusion",
    "Appendix A Battery test methods in international standards",
    "Appendix B Summary of the contributing projects",
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return slug.strip("_")


def _extract_toc_lines() -> list[tuple[str, int]]:
    with pdfplumber.open(SOURCE_PDF) as doc:
        toc_text = "\n".join(
            (doc.pages[2].extract_text() or "").splitlines()
            + (doc.pages[3].extract_text() or "").splitlines()
        )

    entries: list[tuple[str, int]] = []
    for raw_line in toc_text.splitlines():
        line = raw_line.strip()
        if not line or line in {"3", "4"}:
            continue
        match = re.match(r"^(.*?)\s+_+\s+(\d+)$", line)
        if match is None:
            continue
        entries.append((match.group(1).strip(), int(match.group(2))))
    return entries


def _build_index() -> list[dict[str, object]]:
    toc_entries = _extract_toc_lines()
    chapter_entries: list[dict[str, object]] = []
    section_entries: list[dict[str, object]] = []
    current_section_id = "front_matter"
    current_section_title = "Front matter"
    seen_ids: dict[str, int] = {}

    for title, page in toc_entries:
        if title in TOP_LEVEL_TITLES:
            current_section_id = _slug(title)
            current_section_title = title
            section_entries.append(
                {
                    "id": current_section_id,
                    "title": title,
                    "section": title,
                    "level": 1,
                    "start_page": page,
                }
            )
            continue

        entry_id = f"{current_section_id}__{_slug(title)}"
        seen_ids[entry_id] = seen_ids.get(entry_id, 0) + 1
        if seen_ids[entry_id] > 1:
            entry_id = f"{entry_id}_{seen_ids[entry_id]}"

        chapter_entries.append(
            {
                "id": entry_id,
                "title": title,
                "section": current_section_title,
                "level": 2,
                "start_page": page,
            }
        )

    for index, entry in enumerate(chapter_entries):
        next_entry = chapter_entries[index + 1] if index + 1 < len(chapter_entries) else None
        start_page = int(entry["start_page"])
        end_page = 99 if next_entry is None else max(start_page, int(next_entry["start_page"]) - 1)
        entry["end_page"] = end_page

    for index, entry in enumerate(section_entries):
        next_entry = section_entries[index + 1] if index + 1 < len(section_entries) else None
        start_page = int(entry["start_page"])
        end_page = 99 if next_entry is None else max(start_page, int(next_entry["start_page"]) - 1)
        entry["end_page"] = end_page

    return section_entries + chapter_entries


def _extract_page_text(doc: pdfplumber.PDF, start_page: int, end_page: int, title: str) -> str:
    chunks: list[str] = []
    for page_number in range(start_page, end_page + 1):
        text = (doc.pages[page_number - 1].extract_text() or "").strip()
        if page_number == start_page:
            lowered_text = text.lower()
            lowered_title = title.lower()
            title_index = lowered_text.find(lowered_title)
            if title_index != -1:
                text = text[title_index:]
        chunks.append(text)
    return "\n\n".join(chunk for chunk in chunks if chunk)


def main() -> None:
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(
            f"Expected source PDF at {SOURCE_PDF}. Place the white paper there before running this extractor."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTERS_DIR.mkdir(parents=True, exist_ok=True)

    index = _build_index()
    CHAPTER_INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=True), encoding="utf-8")

    chapter_entries = [entry for entry in index if entry["level"] == 2]
    with pdfplumber.open(SOURCE_PDF) as doc:
        for entry in chapter_entries:
            text = _extract_page_text(
                doc,
                int(entry["start_page"]),
                int(entry["end_page"]),
                str(entry["title"]),
            )
            chapter_text = "\n".join(
                [
                    f"# {entry['title']}",
                    "",
                    f"- Section: {entry['section']}",
                    f"- Pages: {entry['start_page']}-{entry['end_page']}",
                    f"- Source PDF: {SOURCE_PDF.name}",
                    "",
                    text,
                ]
            )
            (CHAPTERS_DIR / f"{entry['id']}.md").write_text(chapter_text, encoding="utf-8")

    print(f"Wrote chapter index to {CHAPTER_INDEX_PATH}")
    print(f"Wrote {len(chapter_entries)} chapter markdown files to {CHAPTERS_DIR}")


if __name__ == "__main__":
    main()
