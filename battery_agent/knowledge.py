"""Unified knowledge-base loaders for Battery Lab Assistant.

All domain knowledge — handbook protocols and research literature — lives in
``data/reference/knowledge/``. This module is the single entry-point for the
agent tools that need to load sources, evidence cards, or summary markdown.

Older import paths such as ``battery_agent.literature`` and
``battery_agent.method_handbook`` are kept as thin compatibility shims that
re-export this module's public helpers.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from battery_agent.kb import REPO_ROOT

KNOWLEDGE_DIR = REPO_ROOT / "data" / "reference" / "knowledge"
SOURCE_INDEX_PATH = KNOWLEDGE_DIR / "source_index.json"
EVIDENCE_CARDS_PATH = KNOWLEDGE_DIR / "evidence_cards.json"
SOURCE_INDEX_GLOB = "source_index_*.json"
EVIDENCE_CARDS_GLOB = "evidence_cards_*.json"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())


def _tokenize(value: str | None) -> list[str]:
    normalized = _normalize_text(value or "")
    return [token for token in normalized.split(" ") if token]


def _build_answer_reference_markdown(
    linked_reference_markdown: str,
    supporting_pages: str | list[str] | None = None,
) -> str:
    if isinstance(supporting_pages, list):
        page_text = "; ".join(item for item in supporting_pages if item)
    else:
        page_text = str(supporting_pages or "").strip()
    if not page_text:
        return linked_reference_markdown
    return f"{linked_reference_markdown} Supporting pages used above: {page_text}."


def _normalize_legacy_evidence_kind(card_type: str) -> str:
    mapping = {
        "scope": "handbook_method_scope",
        "execution": "handbook_execution_rule",
        "output": "handbook_output_rule",
        "outputs": "handbook_output_rule",
    }
    return mapping.get(card_type.strip().lower(), "handbook_note")


def _normalize_evidence_card_item(card: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(card)
    if normalized.get("evidence_kind"):
        normalized.setdefault("citation", {})
        return normalized
    card_type = str(normalized.get("card_type") or "").strip()
    content = str(normalized.get("content") or "").strip()
    planning_constraints = [
        str(item).strip()
        for item in normalized.get("planning_constraints", [])
        if str(item).strip()
    ]
    applicable_methods = [
        str(item).strip()
        for item in normalized.get("applicable_methods", [])
        if str(item).strip()
    ]
    normalized.setdefault("source_type", "core_handbook_chapter")
    normalized["evidence_kind"] = _normalize_legacy_evidence_kind(card_type)
    normalized.setdefault("methods", applicable_methods)
    normalized.setdefault("objective", [])
    normalized.setdefault("factors", [])
    if content and not normalized.get("key_takeaways"):
        normalized["key_takeaways"] = [content]
    normalized.setdefault("limitations", planning_constraints)
    normalized.setdefault("system_targets", ["protocol_agent", "method_lookup"])
    normalized.setdefault("page_refs", [])
    normalized.setdefault("citation", {})
    return normalized


def _normalize_source_item(source: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(source)
    summary_path = str(normalized.get("summary_path") or "").strip()
    chapter_file = str(normalized.get("chapter_file") or "").strip()

    if summary_path:
        summary_exists = (REPO_ROOT / summary_path).exists()
        chapter_exists = bool(chapter_file) and (REPO_ROOT / chapter_file).exists()
        if summary_exists and not chapter_exists:
            normalized["chapter_file"] = summary_path

    return normalized


def _normalize_catalog_payload(
    payload: Any,
    *,
    list_key: str,
    path: Path,
) -> dict[str, Any]:
    version = "2.0"
    status = "unified_knowledge_base"
    items: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        version = str(payload.get("version") or version)
        status = str(payload.get("status") or status)
        raw_items = payload.get(list_key, [])
    elif isinstance(payload, list):
        raw_items = payload
    else:
        raw_items = []

    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            if list_key == "cards":
                items.append(_normalize_evidence_card_item(item))
            else:
                items.append(_normalize_source_item(item))

    return {"version": version, "status": status, list_key: items}


def _load_catalog(
    *,
    base_path: Path,
    extra_glob: str,
    list_key: str,
) -> dict[str, Any]:
    merged_items: list[dict[str, Any]] = []
    version = "2.0"
    status = "unified_knowledge_base"

    ordered_paths = [base_path] + [
        path
        for path in sorted(base_path.parent.glob(extra_glob))
        if path.name != base_path.name
    ]
    for path in ordered_paths:
        payload = _normalize_catalog_payload(
            _read_json(path),
            list_key=list_key,
            path=path,
        )
        merged_items.extend(payload.get(list_key, []))
        version = str(payload.get("version") or version)
        status = str(payload.get("status") or status)

    return {"version": version, "status": status, list_key: merged_items}


def _build_fallback_summary_markdown(source: dict[str, Any]) -> str:
    ingestion_notes = [
        str(item).strip() for item in source.get("ingestion_notes", []) if str(item).strip()
    ]
    complementary_sources = [
        str(item).strip()
        for item in source.get("complementary_literature_source_ids", [])
        if str(item).strip()
    ]
    lines = [
        f"# {source.get('title', 'Method')} — Knowledge Summary",
        "",
        "## Primary Planning Role",
        "",
    ]
    if ingestion_notes:
        lines.extend(f"- {item}" for item in ingestion_notes)
    else:
        lines.append("- Treat this reference as a structured planning reference.")
    if complementary_sources:
        lines.extend(["", "## Complementary Sources", ""])
        lines.extend(f"- `{item}`" for item in complementary_sources)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public API — loaders (cached)
# ─────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_knowledge_source_index() -> dict[str, Any]:
    """Return merged source index spanning handbook + literature."""
    return _load_catalog(
        base_path=SOURCE_INDEX_PATH,
        extra_glob=SOURCE_INDEX_GLOB,
        list_key="sources",
    )


@lru_cache(maxsize=1)
def load_knowledge_evidence_cards() -> dict[str, Any]:
    """Return merged evidence cards spanning handbook + literature."""
    return _load_catalog(
        base_path=EVIDENCE_CARDS_PATH,
        extra_glob=EVIDENCE_CARDS_GLOB,
        list_key="cards",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API — get a full source bundle
# ─────────────────────────────────────────────────────────────────────────────

def get_knowledge_source(source_id: str) -> dict[str, Any]:
    """Return source metadata, summary markdown, and evidence cards for *source_id*.

    Works for both former-handbook and former-literature source IDs.
    """
    source_index = load_knowledge_source_index()
    evidence_cards_data = load_knowledge_evidence_cards()

    raw_source = next(
        (item for item in source_index.get("sources", []) if item.get("source_id") == source_id),
        None,
    )
    if raw_source is None:
        raise KeyError(f"Unknown knowledge source: {source_id!r}. Check source_index.json.")

    source = dict(raw_source)

    # Build default page reference for display
    default_supporting_pages = ""
    if source.get("start_page") and source.get("end_page"):
        if source.get("start_page") != source.get("end_page"):
            default_supporting_pages = f"pp. {source['start_page']}-{source['end_page']}"
        else:
            default_supporting_pages = f"p. {source['start_page']}"

    default_linked_reference = str(source.get("linked_reference_markdown") or "")
    source["answer_reference_markdown"] = _build_answer_reference_markdown(
        default_linked_reference, default_supporting_pages
    )

    # Load summary markdown
    summary_markdown = ""
    summary_path = source.get("summary_path")
    if summary_path:
        summary_markdown = (REPO_ROOT / str(summary_path)).read_text(encoding="utf-8")
    else:
        summary_markdown = _build_fallback_summary_markdown(source)

    # Filter evidence cards for this source
    cards = []
    for card in evidence_cards_data.get("cards", []):
        if card.get("source_id") != source_id:
            continue
        citation = dict(card.get("citation", {}))
        if default_linked_reference and not citation.get("linked_reference_markdown"):
            citation["linked_reference_markdown"] = default_linked_reference
        if default_supporting_pages and not citation.get("supporting_pages"):
            citation["supporting_pages"] = default_supporting_pages
        citation["answer_reference_with_pages_markdown"] = _build_answer_reference_markdown(
            str(citation.get("linked_reference_markdown") or ""),
            str(citation.get("supporting_pages") or ""),
        )
        cards.append({**card, "citation": citation})

    return {
        "status": "ok",
        "source": source,
        "summary_markdown": summary_markdown,
        "evidence_cards": cards,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API — search
# ─────────────────────────────────────────────────────────────────────────────

def _build_search_haystack(card: dict[str, Any], source: dict[str, Any]) -> str:
    values: list[str] = [
        str(card.get("title") or ""),
        str(source.get("title") or ""),
        str(source.get("citation_ieee") or ""),
        str(card.get("evidence_kind") or ""),
    ]
    for key in (
        "objective",
        "methods",
        "system_targets",
        "factors",
        "responses",
        "key_takeaways",
        "theory_notes",
        "equation_notes",
        "limitations",
        "keywords",
    ):
        raw_value = card.get(key, [])
        if isinstance(raw_value, list):
            values.append(" ".join(str(item) for item in raw_value))
        else:
            values.append(str(raw_value or ""))
    return _normalize_text(" ".join(values))


def _score_card(card: dict[str, Any], source: dict[str, Any], tokens: list[str]) -> int:
    if not tokens:
        return 1
    title_text = _normalize_text(str(card.get("title") or ""))
    haystack = _build_search_haystack(card, source)
    score = 0
    for token in tokens:
        if token in title_text:
            score += 3
        elif token in haystack:
            score += 1
    return score


def search_knowledge_evidence(query: str, *, limit: int = 5) -> dict[str, Any]:
    """Full-text search across all evidence cards (handbook + literature).

    Returns ranked matches with IEEE citations and supporting pages.
    """
    source_index = load_knowledge_source_index()
    evidence_cards_data = load_knowledge_evidence_cards()
    source_map = {
        item["source_id"]: item for item in source_index.get("sources", [])
    }
    tokens = _tokenize(query)

    matches: list[dict[str, Any]] = []
    for card in evidence_cards_data.get("cards", []):
        source_id = str(card.get("source_id") or "")
        source = source_map.get(source_id)
        if source is None:
            continue
        score = _score_card(card, source, tokens)
        if score <= 0:
            continue
        matches.append(
            {
                "score": score,
                "card_id": card["card_id"],
                "title": card["title"],
                "source_id": source_id,
                "source_title": source["title"],
                "citation": {
                    **card["citation"],
                    "answer_reference_with_pages_markdown": _build_answer_reference_markdown(
                        str(card["citation"].get("linked_reference_markdown") or ""),
                        str(card["citation"].get("supporting_pages") or ""),
                    ),
                },
                "objective": card.get("objective", []),
                "methods": card.get("methods", []),
                "system_targets": card.get("system_targets", []),
                "key_takeaways": card.get("key_takeaways", []),
                "theory_notes": card.get("theory_notes", []),
                "equation_notes": card.get("equation_notes", []),
                "limitations": card.get("limitations", []),
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["title"].lower(), item["card_id"]))

    per_source_matches: dict[str, list[dict[str, Any]]] = {}
    for item in matches:
        per_source_matches.setdefault(item["source_id"], []).append(item)

    ranked_source_ids = sorted(
        per_source_matches.keys(),
        key=lambda source_id: (
            -per_source_matches[source_id][0]["score"],
            -len(per_source_matches[source_id]),
            per_source_matches[source_id][0]["source_title"].lower(),
        ),
    )

    trimmed_matches: list[dict[str, Any]] = []
    seen_card_ids: set[str] = set()
    max_matches = max(limit, 1)
    primary_source_score = (
        per_source_matches[ranked_source_ids[0]][0]["score"] if ranked_source_ids else 0
    )
    minimum_diversified_source_score = max(2, int(primary_source_score * 0.7))

    for index, source_id in enumerate(ranked_source_ids):
        if len(trimmed_matches) >= max_matches:
            break
        top_card = per_source_matches[source_id][0]
        if index > 0 and top_card["score"] < minimum_diversified_source_score:
            continue
        trimmed_matches.append(top_card)
        seen_card_ids.add(top_card["card_id"])

    if len(trimmed_matches) < max_matches:
        for item in matches:
            if item["card_id"] in seen_card_ids:
                continue
            trimmed_matches.append(item)
            seen_card_ids.add(item["card_id"])
            if len(trimmed_matches) >= max_matches:
                break

    grouped_sources: dict[str, dict[str, Any]] = {}
    for item in trimmed_matches:
        source_id = item["source_id"]
        group = grouped_sources.setdefault(
            source_id,
            {
                "source_id": source_id,
                "source_title": item["source_title"],
                "citation": item["citation"],
                "match_count": 0,
                "best_score": item["score"],
                "card_ids": [],
                "card_titles": [],
                "supporting_pages": [],
                "answer_reference_with_pages_markdown": "",
            },
        )
        group["match_count"] += 1
        group["best_score"] = max(group["best_score"], item["score"])
        group["card_ids"].append(item["card_id"])
        group["card_titles"].append(item["title"])
        supporting_pages = str(item["citation"]["supporting_pages"])
        if supporting_pages not in group["supporting_pages"]:
            group["supporting_pages"].append(supporting_pages)
        group["answer_reference_with_pages_markdown"] = _build_answer_reference_markdown(
            str(group["citation"].get("linked_reference_markdown") or ""),
            group["supporting_pages"],
        )

    matched_sources = sorted(
        grouped_sources.values(),
        key=lambda item: (-item["match_count"], -item["best_score"], item["source_title"].lower()),
    )

    if len(matched_sources) == 1 and trimmed_matches:
        coverage_note = (
            "All returned evidence cards come from one curated source. "
            "Present the result as source-backed guidance rather than broad consensus."
        )
    elif matched_sources:
        coverage_note = (
            f"The current curated match set spans {len(matched_sources)} sources "
            f"(handbook + literature are unified). Prefer the highest-ranked source "
            f"first, then use others for support or contrast."
        )
    else:
        coverage_note = "No curated knowledge source matched the query."

    source_lines = []
    for source in matched_sources:
        source_lines.append(
            "\n".join(
                [
                    f"- Source: {source['citation']['linked_reference_markdown']}",
                    f"  - Matched evidence cards: {source['match_count']}",
                    "  - Card titles: " + "; ".join(source["card_titles"]),
                    "  - Supporting pages: " + "; ".join(source["supporting_pages"]),
                ]
            )
        )

    match_lines = []
    for item in trimmed_matches:
        key_takeaways = item["key_takeaways"][:2]
        match_lines.append(
            "\n".join(
                [
                    f"- **{item['title']}** (`{item['card_id']}`)",
                    f"  - Supporting pages: {item['citation']['supporting_pages']}",
                    (
                        "  - Objectives: " + ", ".join(item["objective"])
                        if item["objective"]
                        else "  - Objectives: none"
                    ),
                    (
                        "  - Methods: " + ", ".join(item["methods"])
                        if item["methods"]
                        else "  - Methods: none"
                    ),
                    (
                        "  - Takeaways: " + "; ".join(key_takeaways)
                        if key_takeaways
                        else "  - Takeaways: none"
                    ),
                ]
            )
        )

    return {
        "status": "ok",
        "query": query,
        "query_tokens": tokens,
        "matched_count": len(trimmed_matches),
        "matched_source_count": len(matched_sources),
        "available_source_count": len(source_map),
        "available_card_count": len(evidence_cards_data.get("cards", [])),
        "coverage_note": coverage_note,
        "matched_sources": matched_sources,
        "matches": trimmed_matches,
        "ui_markdown": "\n".join(
            [
                "## Knowledge Evidence Search",
                "",
                f"- Query: `{query}`",
                f"- Matching sources: {len(matched_sources)}",
                f"- Evidence cards returned: {len(trimmed_matches)}",
                f"- Coverage note: {coverage_note}",
                "",
                "### Sources",
                "\n\n".join(source_lines) if source_lines else "- No matching sources found.",
                "",
                "### Top Evidence Cards",
                "\n\n".join(match_lines) if match_lines else "- No matching evidence cards found.",
            ]
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility aliases (for code that still calls old function names)
# ─────────────────────────────────────────────────────────────────────────────

# Former literature.py aliases
load_literature_source_index = load_knowledge_source_index
load_literature_evidence_cards = load_knowledge_evidence_cards
get_literature_source = get_knowledge_source
search_literature_evidence = search_knowledge_evidence

# Former method_handbook.py aliases
load_method_handbook_source_index = load_knowledge_source_index
load_method_handbook_evidence_cards = load_knowledge_evidence_cards
get_method_handbook_source = get_knowledge_source


def get_method_handbook_source_for_method(
    *,
    method_id: str | None = None,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    """Backward-compat: find a source by method_id or chapter_id."""
    source_index = load_knowledge_source_index()
    for source in source_index.get("sources", []):
        if method_id and source.get("method_id") == method_id:
            return get_knowledge_source(str(source["source_id"]))
        if chapter_id and source.get("chapter_id") == chapter_id:
            return get_knowledge_source(str(source["source_id"]))
    raise KeyError(
        f"Unknown source mapping for method_id={method_id!r}, chapter_id={chapter_id!r}"
    )
