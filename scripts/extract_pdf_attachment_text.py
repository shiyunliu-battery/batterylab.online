from __future__ import annotations

import json
import sys
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


def _append_page_text(
    page_text: list[str], text: str, max_chars: int | None
) -> tuple[bool, bool]:
    if not text:
        return False, False

    if max_chars is None:
        page_text.append(text)
        return True, False

    current_length = len("\n\n".join(page_text))
    remaining = max_chars - current_length
    if remaining <= 0:
        return False, True

    separator = "\n\n" if page_text else ""
    available = remaining - len(separator)
    if available <= 0:
        return False, True

    if len(text) <= available:
        page_text.append(text)
        return True, False

    page_text.append(text[:available])
    return True, True


def _extract_with_pdfplumber(pdf_path: Path, max_chars: int | None) -> tuple[str, int, bool]:
    page_text: list[str] = []
    truncated = False
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            _, did_truncate = _append_page_text(page_text, text, max_chars)
            if did_truncate:
                truncated = True
                break
    return "\n\n".join(page_text), len(pdf.pages), truncated


def _extract_with_pypdf(pdf_path: Path, max_chars: int | None) -> tuple[str, int, bool]:
    reader = PdfReader(str(pdf_path))
    page_text: list[str] = []
    truncated = False
    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        _, did_truncate = _append_page_text(page_text, text, max_chars)
        if did_truncate:
            truncated = True
            break
    return "\n\n".join(page_text), len(reader.pages), truncated


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) not in {2, 3}:
        print(json.dumps({"error": "Expected a PDF path and optional max char limit."}))
        return 1

    pdf_path = Path(sys.argv[1])
    max_chars = int(sys.argv[2]) if len(sys.argv) == 3 else None
    errors: list[str] = []

    try:
        text, page_count, truncated = _extract_with_pdfplumber(pdf_path, max_chars)
        if text.strip():
            print(
                json.dumps(
                    {
                        "text": text,
                        "page_count": page_count,
                        "engine": "pdfplumber",
                        "truncated": truncated,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
    except Exception as exc:  # pragma: no cover - fallback path
        errors.append(f"pdfplumber: {exc}")

    try:
        text, page_count, truncated = _extract_with_pypdf(pdf_path, max_chars)
        print(
            json.dumps(
                {
                    "text": text,
                    "page_count": page_count,
                    "engine": "pypdf",
                    "truncated": truncated,
                    "fallback_errors": errors,
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        errors.append(f"pypdf: {exc}")
        print(
            json.dumps(
                {
                    "error": "PDF text extraction failed.",
                    "details": errors,
                },
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
