"""Structured equipment-manual loaders and search helpers for Battery Lab Assistant."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from battery_agent.kb import REPO_ROOT

EQUIPMENT_MANUALS_DIR = REPO_ROOT / "data" / "reference" / "equipment_manuals"
MANUAL_INDEX_PATH = EQUIPMENT_MANUALS_DIR / "manual_index.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _tokenize(value: str | None) -> list[str]:
    normalized = _normalize_text(value or "")
    return [token for token in normalized.split(" ") if token]


def _summary_path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def _build_answer_reference_markdown(
    linked_reference_markdown: str,
    supporting_pages: str | list[str] | None = None,
) -> str:
    if isinstance(supporting_pages, list):
        page_text = "; ".join(str(item).strip() for item in supporting_pages if str(item).strip())
    else:
        page_text = str(supporting_pages or "").strip()

    if not page_text:
        return linked_reference_markdown

    return f"{linked_reference_markdown} Supporting pages used above: {page_text}."


def _build_equipment_manual_reference(manual: dict[str, Any]) -> str:
    manufacturer = str(manual.get("manufacturer") or "Unknown manufacturer").strip()
    model = str(manual.get("model") or "Unknown model").strip()
    return f'{manufacturer}, "{model}" structured equipment reference.'


def _enrich_manual(manual: dict[str, Any]) -> dict[str, Any]:
    payload = dict(manual)
    linked_reference_markdown = _build_equipment_manual_reference(payload)
    payload["citation_ieee"] = linked_reference_markdown
    payload["linked_reference_markdown"] = linked_reference_markdown
    payload["answer_reference_markdown"] = _build_answer_reference_markdown(
        linked_reference_markdown,
        payload.get("page_spans_used"),
    )
    return payload


@lru_cache(maxsize=1)
def load_equipment_manual_index() -> dict[str, Any]:
    payload = _read_json(MANUAL_INDEX_PATH)
    return {
        **payload,
        "manuals": [
            _enrich_manual(item)
            for item in payload.get("manuals", [])
        ],
    }


def get_equipment_manual_asset(asset_id: str) -> dict[str, Any]:
    manual_index = load_equipment_manual_index()
    manual = next(
        (item for item in manual_index.get("manuals", []) if item.get("asset_id") == asset_id),
        None,
    )
    if manual is None:
        raise KeyError(f"Unknown equipment manual asset: {asset_id}")

    payload = dict(manual)
    summary_markdown = _summary_path(str(payload["structured_summary_path"])).read_text(encoding="utf-8")
    return {
        "status": "ok",
        "manual": payload,
        "summary_markdown": summary_markdown,
    }


def _build_search_haystack(manual: dict[str, Any]) -> str:
    values: list[str] = [
        str(manual.get("asset_id") or ""),
        str(manual.get("equipment_type") or ""),
        str(manual.get("manufacturer") or ""),
        str(manual.get("model") or ""),
        str(manual.get("source_file") or ""),
    ]
    for key in ("coverage", "notes", "system_targets", "page_spans_used"):
        raw_value = manual.get(key, [])
        if isinstance(raw_value, list):
            values.append(" ".join(str(item) for item in raw_value))
        else:
            values.append(str(raw_value or ""))
    return _normalize_text(" ".join(values))


def _score_manual(manual: dict[str, Any], tokens: list[str]) -> int:
    if not tokens:
        return 1

    title_text = _normalize_text(
        " ".join(
            [
                str(manual.get("manufacturer") or ""),
                str(manual.get("model") or ""),
                str(manual.get("equipment_type") or ""),
            ]
        )
    )
    haystack = _build_search_haystack(manual)
    score = 0
    for token in tokens:
        if token in title_text:
            score += 3
        elif token in haystack:
            score += 1
    return score


def search_equipment_manual_assets(query: str, *, limit: int = 5) -> dict[str, Any]:
    manual_index = load_equipment_manual_index()
    manuals = manual_index.get("manuals", [])
    tokens = _tokenize(query)

    matches: list[dict[str, Any]] = []
    for manual in manuals:
        score = _score_manual(manual, tokens)
        if score <= 0:
            continue
        matches.append(
            {
                "score": score,
                "asset_id": manual["asset_id"],
                "equipment_type": manual["equipment_type"],
                "manufacturer": manual["manufacturer"],
                "model": manual["model"],
                "source_file": manual["source_file"],
                "coverage": manual.get("coverage", [])[:4],
                "notes": manual.get("notes", [])[:3],
                "structured_summary_path": manual["structured_summary_path"],
                "page_spans_used": manual.get("page_spans_used", []),
                "answer_reference_markdown": manual.get("answer_reference_markdown"),
            }
        )

    matches.sort(
        key=lambda item: (-item["score"], item["manufacturer"].lower(), item["model"].lower(), item["asset_id"])
    )
    trimmed_matches = matches[: max(limit, 1)]

    match_lines = []
    for item in trimmed_matches:
        match_lines.append(
            "\n".join(
                [
                    f"- **{item['manufacturer']} {item['model']}** (`{item['asset_id']}`)",
                    f"  - Type: {item['equipment_type']}",
                    (
                        "  - Coverage: " + "; ".join(item["coverage"])
                        if item["coverage"]
                        else "  - Coverage: none"
                    ),
                    (
                        "  - Notes: " + "; ".join(item["notes"])
                        if item["notes"]
                        else "  - Notes: none"
                    ),
                    (
                        f"  - Citation: {item['answer_reference_markdown']}"
                        if item.get("answer_reference_markdown")
                        else "  - Citation: unavailable"
                    ),
                ]
            )
        )

    return {
        "status": "ok",
        "query": query,
        "query_tokens": tokens,
        "matched_count": len(trimmed_matches),
        "available_manual_count": len(manuals),
        "matches": trimmed_matches,
        "ui_markdown": "\n".join(
            [
                "## Equipment Manual Search",
                "",
                f"- Query: `{query}`",
                f"- Matching assets returned: {len(trimmed_matches)}",
                "",
                "### Matches",
                "\n\n".join(match_lines) if match_lines else "- No matching equipment-manual assets found.",
            ]
        ),
    }
