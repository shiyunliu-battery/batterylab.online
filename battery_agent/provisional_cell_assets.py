"""Governance helpers for user-supplied provisional cell assets."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import battery_agent.cell_catalog as cell_catalog
from battery_agent.cell_catalog import FORMAL_CELL_REQUIRED_FIELDS, govern_cell_record

REPO_ROOT = Path(__file__).resolve().parents[1]
PROVISIONAL_CELL_ASSET_PATH = (
    REPO_ROOT / "data" / "reference" / "cell_catalog" / "provisional_cell_assets.json"
)

PROVISIONAL_SCHEMA_VERSION = "0.2.0"
REVIEW_STATUSES = (
    "draft_extracted",
    "user_corrected",
    "submitted_for_review",
    "needs_changes",
    "rejected",
    "approved_for_promotion",
    "promoted_to_manual_asset",
)
REVIEW_DECISIONS = (
    "user_corrected",
    "submit_for_review",
    "needs_changes",
    "reject",
    "approve_for_promotion",
)
PROVISIONAL_IMMUTABLE_FIELDS = {
    "provisional_id",
    "submitted_by",
    "submitted_at",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "review_notes",
    "review_events",
    "approval_status",
    "approval_basis",
    "eligible_for_planning",
    "eligibility_tags",
    "completeness_status",
    "completeness_score",
    "confidence_status",
    "missing_required_fields",
    "waived_missing_required_fields",
    "required_record_fields",
    "formal_promotion_preview",
    "promotion_readiness",
    "promotable_if_reviewed",
    "promotion_target",
    "promotion_status",
    "promoted_cell_id",
    "promoted_at",
    "promoted_by",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_text(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _slug_fragment(value: str | None, *, default: str) -> str:
    raw_value = str(value or "").strip()
    if not raw_value:
        return default
    slug = re.sub(r"[^A-Za-z0-9]+", "_", raw_value).strip("_")
    return slug or default


def _sanitize_utf8_text(value: str) -> str:
    return re.sub(r"[\ud800-\udfff]", "\uFFFD", value)


def _sanitize_utf8_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_utf8_text(value)
    if isinstance(value, list):
        return [_sanitize_utf8_value(item) for item in value]
    if isinstance(value, dict):
        return {
            (_sanitize_utf8_text(key) if isinstance(key, str) else key): _sanitize_utf8_value(item)
            for key, item in value.items()
        }
    return value


def _json_read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sanitized_payload = _sanitize_utf8_value(payload)
    path.write_text(
        json.dumps(sanitized_payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_string_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _default_provisional_store() -> dict[str, Any]:
    return {
        "version": PROVISIONAL_SCHEMA_VERSION,
        "status": "active",
        "asset_type": "provisional_cell_asset_store",
        "review_statuses": list(REVIEW_STATUSES),
        "review_decisions": list(REVIEW_DECISIONS),
        "promotion_target": "manual_cell_assets",
        "required_formal_fields": list(FORMAL_CELL_REQUIRED_FIELDS),
        "required_provisional_fields": [
            "provisional_id",
            "display_name",
            "manufacturer",
            "source_document",
            "extraction_status",
            "field_evidence",
            "review_status",
            "missing_required_fields",
        ],
        "notes": [
            "Use this store for user-supplied datasheets before formal cell catalog promotion.",
            "Provisional assets remain planning-ineligible until they are explicitly promoted into manual_cell_assets.json.",
            "Every promoted record should carry reviewer identity, review notes, and field-level evidence.",
        ],
        "assets": [],
    }


def _normalize_candidate_record(raw_record: dict[str, Any]) -> dict[str, Any]:
    candidate = _sanitize_utf8_value(deepcopy(raw_record))
    if not isinstance(candidate, dict):
        raise ValueError("Provisional cell asset payload must be a JSON object.")

    chemistry_hint = candidate.pop("chemistry_hint", None)
    if chemistry_hint is not None and not candidate.get("project_chemistry_hint"):
        candidate["project_chemistry_hint"] = chemistry_hint

    source_pdf = candidate.pop("source_pdf", None)
    if source_pdf is not None and not candidate.get("source_file"):
        candidate["source_file"] = source_pdf

    dimensions = candidate.pop("dimensions", None)
    if dimensions is not None and not candidate.get("physical"):
        candidate["physical"] = dimensions

    if not candidate.get("display_name"):
        manufacturer = str(candidate.get("manufacturer") or "").strip()
        model = str(candidate.get("model") or candidate.get("schema_name") or "").strip()
        if manufacturer or model:
            candidate["display_name"] = " ".join(part for part in [manufacturer, model] if part)
        else:
            raise ValueError("display_name is required for provisional cell assets.")

    candidate["manufacturer"] = str(candidate.get("manufacturer") or "Unknown").strip() or "Unknown"

    if not candidate.get("model") and candidate.get("schema_name"):
        candidate["model"] = candidate.get("schema_name")
    if not candidate.get("schema_name") and candidate.get("model"):
        candidate["schema_name"] = candidate.get("model")

    for key in ("electrical", "currents", "physical", "lifecycle", "source_document", "field_evidence"):
        candidate[key] = _normalize_string_dict(candidate.get(key))

    for key in (
        "case_types",
        "aliases",
        "citations",
        "normalization_notes",
        "approval_notes",
        "required_field_waivers",
    ):
        candidate[key] = _normalize_string_list(candidate.get(key))

    return candidate


def _extract_candidate_record(asset: dict[str, Any]) -> dict[str, Any]:
    candidate = {
        key: deepcopy(value)
        for key, value in asset.items()
        if key not in PROVISIONAL_IMMUTABLE_FIELDS
    }
    return _normalize_candidate_record(candidate)


def _candidate_preview(candidate: dict[str, Any]) -> dict[str, Any]:
    preview = govern_cell_record(candidate)
    preview["would_be_formally_approved"] = cell_catalog.is_formally_approved_cell_record(preview)
    return preview


def _provisional_confidence_status(
    *,
    extraction_status: str,
    review_status: str,
    preview: dict[str, Any],
) -> str:
    normalized_extraction = _normalize_text(extraction_status)
    normalized_review = _normalize_text(review_status)

    if normalized_review == "approved_for_promotion":
        return "reviewed_pending_promotion"
    if normalized_review == "promoted_to_manual_asset":
        return "promoted"
    if normalized_extraction == "manual_entry":
        return "manual_entry_review_required"
    if normalized_extraction == "machine_extracted":
        return "machine_extracted_review_required"
    return str(preview.get("confidence_status") or "review_required")


def _provisional_eligibility_tags(
    *,
    review_status: str,
    preview: dict[str, Any],
) -> list[str]:
    tags = ["provisional_asset", "planning_ineligible", review_status]
    if preview.get("missing_required_fields"):
        tags.append("missing_required_fields")
    else:
        tags.append("candidate_complete")
    if preview.get("waived_missing_required_fields"):
        tags.append("waiver_declared")
    return tags


def _normalize_source_document(
    *,
    existing_document: dict[str, Any] | None,
    candidate: dict[str, Any],
    source_file: str | None,
    submitted_by: str | None,
    extraction_status: str,
    parser_version: str,
) -> dict[str, Any]:
    source_document = dict(existing_document or {})
    candidate_source_file = str(candidate.get("source_file") or "").strip()
    effective_source_file = str(source_file or candidate_source_file).strip()

    source_document.setdefault("document_type", "cell_datasheet")
    source_document.setdefault("original_filename", Path(effective_source_file).name if effective_source_file else "")
    source_document["path"] = effective_source_file
    if submitted_by and not source_document.get("uploaded_by"):
        source_document["uploaded_by"] = submitted_by
    source_document.setdefault("uploaded_at", _utc_now_iso())
    source_document["extraction_status"] = extraction_status
    source_document["parser_version"] = parser_version
    return source_document


def _build_provisional_asset(
    candidate: dict[str, Any],
    *,
    provisional_id: str,
    submitted_by: str,
    submitted_at: str,
    source_file: str | None,
    extraction_status: str,
    parser_version: str,
    review_status: str,
    reviewed_by: str | None,
    reviewed_at: str | None,
    review_notes: list[str],
    review_events: list[dict[str, Any]],
    human_edits: list[dict[str, Any]],
    promoted_cell_id: str | None,
    promoted_at: str | None,
    promoted_by: str | None,
) -> dict[str, Any]:
    preview = _candidate_preview(candidate)
    promotable_if_reviewed = not preview.get("missing_required_fields")

    asset = deepcopy(candidate)
    asset["provisional_id"] = provisional_id
    asset["submitted_by"] = submitted_by
    asset["submitted_at"] = submitted_at
    asset["source_document"] = _normalize_source_document(
        existing_document=asset.get("source_document"),
        candidate=asset,
        source_file=source_file,
        submitted_by=submitted_by,
        extraction_status=extraction_status,
        parser_version=parser_version,
    )
    asset["source_file"] = asset["source_document"].get("path", "")
    asset["extraction_status"] = extraction_status
    asset["parser_version"] = parser_version
    asset["field_evidence"] = _normalize_string_dict(asset.get("field_evidence"))
    asset["review_status"] = review_status
    asset["reviewed_by"] = reviewed_by
    asset["reviewed_at"] = reviewed_at
    asset["review_notes"] = list(review_notes)
    asset["review_events"] = [dict(event) for event in review_events]
    asset["human_edits"] = [dict(event) for event in human_edits]
    asset["required_record_fields"] = list(preview.get("required_record_fields", FORMAL_CELL_REQUIRED_FIELDS))
    asset["required_field_waivers"] = list(preview.get("required_field_waivers", []))
    asset["waived_missing_required_fields"] = list(preview.get("waived_missing_required_fields", []))
    asset["missing_required_fields"] = list(preview.get("missing_required_fields", []))
    asset["completeness_status"] = preview.get("completeness_status", "incomplete")
    asset["completeness_score"] = preview.get("completeness_score", 0.0)
    asset["confidence_status"] = _provisional_confidence_status(
        extraction_status=extraction_status,
        review_status=review_status,
        preview=preview,
    )
    asset["approval_status"] = "unapproved"
    asset["approval_basis"] = "provisional_extraction"
    asset["eligible_for_planning"] = False
    asset["eligibility_tags"] = _provisional_eligibility_tags(
        review_status=review_status,
        preview=preview,
    )
    asset["promotion_target"] = "manual_cell_assets"
    asset["promotion_status"] = (
        "promoted"
        if review_status == "promoted_to_manual_asset"
        else "ready_for_promotion"
        if review_status == "approved_for_promotion"
        else "awaiting_review"
    )
    asset["promoted_cell_id"] = promoted_cell_id
    asset["promoted_at"] = promoted_at
    asset["promoted_by"] = promoted_by
    asset["promotable_if_reviewed"] = promotable_if_reviewed
    asset["promotion_readiness"] = (
        "ready_for_review" if promotable_if_reviewed else "missing_required_fields"
    )
    asset["formal_promotion_preview"] = {
        "display_name": asset.get("display_name"),
        "proposed_cell_id": _generate_cell_id(asset),
        "would_be_formally_approved": bool(preview.get("would_be_formally_approved")),
        "completeness_status": preview.get("completeness_status"),
        "confidence_status": preview.get("confidence_status"),
        "missing_required_fields": list(preview.get("missing_required_fields", [])),
        "waived_missing_required_fields": list(preview.get("waived_missing_required_fields", [])),
        "approval_basis_if_promoted": preview.get("approval_basis"),
    }
    return asset


def _asset_summary(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "provisional_id": asset.get("provisional_id"),
        "display_name": asset.get("display_name"),
        "manufacturer": asset.get("manufacturer"),
        "model": asset.get("model"),
        "project_chemistry_hint": asset.get("project_chemistry_hint"),
        "form_factor": asset.get("form_factor"),
        "review_status": asset.get("review_status"),
        "approval_status": asset.get("approval_status"),
        "eligible_for_planning": bool(asset.get("eligible_for_planning")),
        "promotion_readiness": asset.get("promotion_readiness"),
        "promotable_if_reviewed": bool(asset.get("promotable_if_reviewed")),
        "missing_required_fields": list(asset.get("missing_required_fields", [])),
        "required_field_waivers": list(asset.get("required_field_waivers", [])),
        "submitted_by": asset.get("submitted_by"),
        "reviewed_by": asset.get("reviewed_by"),
        "promoted_cell_id": asset.get("promoted_cell_id"),
        "source_file": asset.get("source_file"),
    }


def _review_status_counts(assets: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in assets:
        review_status = str(asset.get("review_status") or "unknown")
        counts[review_status] = counts.get(review_status, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _generate_provisional_id(record: dict[str, Any]) -> str:
    display_name = str(record.get("display_name") or record.get("model") or "cell").strip()
    fragment = _slug_fragment(display_name, default="cell").lower()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"prov_{fragment}_{timestamp}"


def _generate_cell_id(record: dict[str, Any]) -> str:
    manufacturer = _slug_fragment(str(record.get("manufacturer") or "Unknown"), default="Unknown")
    model = _slug_fragment(
        str(record.get("model") or record.get("schema_name") or record.get("display_name") or "Cell"),
        default="Cell",
    )
    return f"{manufacturer}_{model}"


def _load_manual_catalog() -> dict[str, Any]:
    path = cell_catalog.MANUAL_CELL_CATALOG_PATH
    if path.exists():
        return _json_read(path)
    return {
        "catalog_version": "manual_assets_v1",
        "generated_at_utc": _utc_now_iso(),
        "source_repository": "manual_review_queue",
        "cells": [],
    }


def _save_manual_catalog(payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["generated_at_utc"] = _utc_now_iso()
    _json_write(cell_catalog.MANUAL_CELL_CATALOG_PATH, payload)
    cell_catalog.clear_cell_catalog_cache()


@lru_cache(maxsize=1)
def load_provisional_cell_assets() -> dict[str, Any]:
    if not PROVISIONAL_CELL_ASSET_PATH.exists():
        return _default_provisional_store()

    payload = _json_read(PROVISIONAL_CELL_ASSET_PATH)
    default_payload = _default_provisional_store()
    merged_payload = dict(default_payload)
    merged_payload.update({key: value for key, value in payload.items() if key != "assets"})
    merged_payload["assets"] = list(payload.get("assets", []))
    return merged_payload


def clear_provisional_cell_asset_cache() -> None:
    load_provisional_cell_assets.cache_clear()


def _save_provisional_store(payload: dict[str, Any]) -> None:
    payload = dict(payload)
    payload["version"] = PROVISIONAL_SCHEMA_VERSION
    payload["status"] = "active"
    _json_write(PROVISIONAL_CELL_ASSET_PATH, payload)
    clear_provisional_cell_asset_cache()


def _find_asset_index(assets: list[dict[str, Any]], provisional_id: str) -> int:
    normalized_query = _normalize_text(provisional_id)
    for index, asset in enumerate(assets):
        if _normalize_text(str(asset.get("provisional_id") or "")) == normalized_query:
            return index
    raise KeyError(f"Unknown provisional cell asset: {provisional_id}")


def search_provisional_cell_assets(
    query: str | None = None,
    *,
    review_status: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    store = load_provisional_cell_assets()
    assets = list(store.get("assets", []))

    if review_status:
        normalized_review_status = _normalize_text(review_status)
        assets = [
            asset
            for asset in assets
            if _normalize_text(str(asset.get("review_status") or "")) == normalized_review_status
        ]

    if query:
        normalized_query = _normalize_text(query)

        def asset_score(asset: dict[str, Any]) -> tuple[int, str]:
            haystacks = [
                str(asset.get("provisional_id") or ""),
                str(asset.get("display_name") or ""),
                str(asset.get("manufacturer") or ""),
                str(asset.get("model") or ""),
                str(asset.get("project_chemistry_hint") or ""),
                str(asset.get("form_factor") or ""),
            ]
            score = sum(normalized_query in _normalize_text(haystack) for haystack in haystacks)
            return score, str(asset.get("display_name") or "")

        assets = [asset for asset in assets if asset_score(asset)[0] > 0]
        assets.sort(key=lambda asset: (-asset_score(asset)[0], asset_score(asset)[1]))

    limited_assets = assets[: max(limit, 1)]
    return {
        "status": "ok",
        "store_version": store.get("version"),
        "query": query,
        "review_status_filter": review_status,
        "asset_count": len(limited_assets),
        "total_asset_count": len(store.get("assets", [])),
        "review_status_counts": _review_status_counts(list(store.get("assets", []))),
        "assets": [_asset_summary(asset) for asset in limited_assets],
    }


def get_provisional_cell_asset(provisional_id: str) -> dict[str, Any]:
    store = load_provisional_cell_assets()
    index = _find_asset_index(list(store.get("assets", [])), provisional_id)
    asset = list(store.get("assets", []))[index]
    return {
        "status": "ok",
        "store_version": store.get("version"),
        "asset": asset,
        "asset_summary": _asset_summary(asset),
    }


def register_provisional_cell_asset(
    asset_data: dict[str, Any],
    *,
    submitted_by: str,
    source_file: str | None = None,
    extraction_status: str = "machine_extracted",
    parser_version: str = "manual_entry",
    submit_for_review: bool = False,
) -> dict[str, Any]:
    store = deepcopy(load_provisional_cell_assets())
    candidate = _normalize_candidate_record(asset_data)
    provisional_id = str(candidate.pop("provisional_id", "") or "").strip() or _generate_provisional_id(candidate)
    now = _utc_now_iso()

    asset = _build_provisional_asset(
        candidate,
        provisional_id=provisional_id,
        submitted_by=str(submitted_by).strip() or "unknown_submitter",
        submitted_at=now,
        source_file=source_file,
        extraction_status=str(extraction_status).strip() or "machine_extracted",
        parser_version=str(parser_version).strip() or "manual_entry",
        review_status="submitted_for_review" if submit_for_review else "draft_extracted",
        reviewed_by=None,
        reviewed_at=None,
        review_notes=[],
        review_events=[
            {
                "at": now,
                "actor": str(submitted_by).strip() or "unknown_submitter",
                "decision": "submit_for_review" if submit_for_review else "draft_extracted",
                "notes": [],
                "corrected_fields": [],
            }
        ],
        human_edits=[],
        promoted_cell_id=None,
        promoted_at=None,
        promoted_by=None,
    )

    assets = list(store.get("assets", []))
    try:
        existing_index = _find_asset_index(assets, provisional_id)
    except KeyError:
        assets.append(asset)
    else:
        assets[existing_index] = asset

    store["assets"] = assets
    _save_provisional_store(store)
    return {
        "status": "ok",
        "action": "registered_provisional_cell_asset",
        "asset": asset,
        "asset_summary": _asset_summary(asset),
        "review_status_counts": _review_status_counts(assets),
    }


def review_provisional_cell_asset(
    provisional_id: str,
    *,
    decision: str,
    actor: str,
    review_notes: list[str] | None = None,
    corrected_fields: dict[str, Any] | None = None,
    required_field_waivers: list[str] | None = None,
) -> dict[str, Any]:
    normalized_decision = _normalize_text(decision)
    if normalized_decision not in {_normalize_text(item) for item in REVIEW_DECISIONS}:
        raise ValueError(
            "Unsupported decision. Expected one of: " + ", ".join(REVIEW_DECISIONS) + "."
        )

    store = deepcopy(load_provisional_cell_assets())
    assets = list(store.get("assets", []))
    index = _find_asset_index(assets, provisional_id)
    current_asset = deepcopy(assets[index])
    now = _utc_now_iso()
    corrections = {
        key: deepcopy(value)
        for key, value in (corrected_fields or {}).items()
        if key not in PROVISIONAL_IMMUTABLE_FIELDS
    }

    merged_asset = _deep_merge(current_asset, corrections)
    if required_field_waivers is not None:
        merged_asset["required_field_waivers"] = _normalize_string_list(required_field_waivers)

    candidate = _extract_candidate_record(merged_asset)
    preview = _candidate_preview(candidate)
    if normalized_decision == "approve_for_promotion" and preview.get("missing_required_fields"):
        missing_fields = ", ".join(preview.get("missing_required_fields", []))
        raise ValueError(
            "Cannot approve provisional cell asset for promotion while required fields are still missing: "
            f"{missing_fields}."
        )

    existing_review_events = [
        dict(event) for event in current_asset.get("review_events", []) if isinstance(event, dict)
    ]
    existing_human_edits = [
        dict(event) for event in current_asset.get("human_edits", []) if isinstance(event, dict)
    ]
    normalized_notes = _normalize_string_list(review_notes)
    corrected_field_names = sorted(corrections.keys())
    if corrected_field_names:
        existing_human_edits.append(
            {
                "at": now,
                "actor": actor,
                "fields": corrected_field_names,
            }
        )
    existing_review_events.append(
        {
            "at": now,
            "actor": actor,
            "decision": normalized_decision,
            "notes": normalized_notes,
            "corrected_fields": corrected_field_names,
        }
    )

    new_review_status_map = {
        "user_corrected": "user_corrected",
        "submit_for_review": "submitted_for_review",
        "needs_changes": "needs_changes",
        "reject": "rejected",
        "approve_for_promotion": "approved_for_promotion",
    }
    new_review_status = new_review_status_map[normalized_decision]
    reviewed_by = actor if normalized_decision in {"needs_changes", "reject", "approve_for_promotion"} else None
    reviewed_at = now if reviewed_by else None

    updated_asset = _build_provisional_asset(
        candidate,
        provisional_id=str(current_asset.get("provisional_id")),
        submitted_by=str(current_asset.get("submitted_by") or actor),
        submitted_at=str(current_asset.get("submitted_at") or now),
        source_file=str(current_asset.get("source_file") or ""),
        extraction_status=str(current_asset.get("extraction_status") or "machine_extracted"),
        parser_version=str(current_asset.get("parser_version") or "manual_entry"),
        review_status=new_review_status,
        reviewed_by=reviewed_by,
        reviewed_at=reviewed_at,
        review_notes=_normalize_string_list(current_asset.get("review_notes", [])) + normalized_notes,
        review_events=existing_review_events,
        human_edits=existing_human_edits,
        promoted_cell_id=current_asset.get("promoted_cell_id"),
        promoted_at=current_asset.get("promoted_at"),
        promoted_by=current_asset.get("promoted_by"),
    )

    assets[index] = updated_asset
    store["assets"] = assets
    _save_provisional_store(store)
    return {
        "status": "ok",
        "action": "reviewed_provisional_cell_asset",
        "decision": normalized_decision,
        "asset": updated_asset,
        "asset_summary": _asset_summary(updated_asset),
        "review_status_counts": _review_status_counts(assets),
    }


def promote_provisional_cell_asset(
    provisional_id: str,
    *,
    reviewer: str,
    final_cell_id: str | None = None,
    promotion_notes: list[str] | None = None,
    replace_existing: bool = False,
) -> dict[str, Any]:
    store = deepcopy(load_provisional_cell_assets())
    assets = list(store.get("assets", []))
    index = _find_asset_index(assets, provisional_id)
    provisional_asset = deepcopy(assets[index])

    if _normalize_text(str(provisional_asset.get("review_status") or "")) != "approved_for_promotion":
        raise ValueError(
            "Only provisional assets with review_status=approved_for_promotion can be promoted."
        )

    preview = provisional_asset.get("formal_promotion_preview", {})
    if not preview.get("would_be_formally_approved"):
        missing_fields = ", ".join(provisional_asset.get("missing_required_fields", []))
        raise ValueError(
            "Provisional asset is not ready for promotion because required fields remain missing: "
            f"{missing_fields}."
        )

    candidate = _extract_candidate_record(provisional_asset)
    promoted_cell_id = str(final_cell_id or preview.get("proposed_cell_id") or _generate_cell_id(candidate)).strip()
    if not promoted_cell_id:
        promoted_cell_id = _generate_cell_id(candidate)

    manual_catalog = _load_manual_catalog()
    manual_cells = list(manual_catalog.get("cells", []))
    existing_manual_index = None
    for manual_index, record in enumerate(manual_cells):
        if _normalize_text(str(record.get("cell_id") or "")) == _normalize_text(promoted_cell_id):
            existing_manual_index = manual_index
            break

    if existing_manual_index is not None and not replace_existing:
        raise ValueError(
            f"A manual cell asset with cell_id={promoted_cell_id} already exists. "
            "Set replace_existing=True to overwrite it explicitly."
        )

    normalized_promotion_notes = _normalize_string_list(promotion_notes)
    approval_notes = _normalize_string_list(candidate.get("approval_notes", []))
    approval_notes.extend(normalized_promotion_notes)
    approval_notes.append(
        f"Promoted from provisional asset {provisional_asset['provisional_id']} after reviewer approval."
    )
    review_notes = _normalize_string_list(provisional_asset.get("review_notes", []))
    for note in review_notes:
        if note not in approval_notes:
            approval_notes.append(note)

    manual_record = deepcopy(candidate)
    manual_record["cell_id"] = promoted_cell_id
    manual_record["source_repository"] = "reviewed_provisional_cell_asset"
    manual_record["source_file"] = manual_record.get("source_file") or provisional_asset.get("source_file")
    manual_record["approval_basis"] = "reviewed_provisional_asset"
    manual_record["approval_notes"] = approval_notes
    manual_record["provisional_source"] = {
        "provisional_id": provisional_asset["provisional_id"],
        "submitted_by": provisional_asset.get("submitted_by"),
        "submitted_at": provisional_asset.get("submitted_at"),
        "reviewed_by": reviewer,
        "reviewed_at": _utc_now_iso(),
        "review_status": provisional_asset.get("review_status"),
        "source_document": deepcopy(provisional_asset.get("source_document", {})),
    }
    manual_record["field_evidence"] = deepcopy(provisional_asset.get("field_evidence", {}))

    if existing_manual_index is None:
        manual_cells.append(manual_record)
    else:
        manual_cells[existing_manual_index] = manual_record

    manual_catalog["cells"] = manual_cells
    _save_manual_catalog(manual_catalog)

    now = _utc_now_iso()
    updated_asset = _build_provisional_asset(
        candidate,
        provisional_id=str(provisional_asset.get("provisional_id")),
        submitted_by=str(provisional_asset.get("submitted_by") or reviewer),
        submitted_at=str(provisional_asset.get("submitted_at") or now),
        source_file=str(provisional_asset.get("source_file") or ""),
        extraction_status=str(provisional_asset.get("extraction_status") or "machine_extracted"),
        parser_version=str(provisional_asset.get("parser_version") or "manual_entry"),
        review_status="promoted_to_manual_asset",
        reviewed_by=reviewer,
        reviewed_at=now,
        review_notes=_normalize_string_list(provisional_asset.get("review_notes", [])) + normalized_promotion_notes,
        review_events=[
            *[
                dict(event)
                for event in provisional_asset.get("review_events", [])
                if isinstance(event, dict)
            ],
            {
                "at": now,
                "actor": reviewer,
                "decision": "promote_to_manual_asset",
                "notes": normalized_promotion_notes,
                "corrected_fields": [],
            },
        ],
        human_edits=[
            dict(event)
            for event in provisional_asset.get("human_edits", [])
            if isinstance(event, dict)
        ],
        promoted_cell_id=promoted_cell_id,
        promoted_at=now,
        promoted_by=reviewer,
    )

    assets[index] = updated_asset
    store["assets"] = assets
    _save_provisional_store(store)
    return {
        "status": "ok",
        "action": "promoted_provisional_cell_asset",
        "asset": updated_asset,
        "asset_summary": _asset_summary(updated_asset),
        "promoted_manual_record": manual_record,
    }
