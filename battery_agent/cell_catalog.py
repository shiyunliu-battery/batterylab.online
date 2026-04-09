"""Helpers for loading and querying the imported external cell catalog."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
CELL_CATALOG_PATH = REPO_ROOT / "data" / "reference" / "cell_catalog" / "cell_catalog.json"
MANUAL_CELL_CATALOG_PATH = (
    REPO_ROOT / "data" / "reference" / "cell_catalog" / "manual_cell_assets.json"
)

QUERY_ALIAS_MAP = {
    "lpf": "lfp",
    "lifepo4": "lfp",
    "li_fe_po4": "lfp",
    "manufactures": "manufacturer",
}
STOPWORDS = {
    "any",
    "do",
    "you",
    "know",
    "made",
    "by",
    "different",
    "manufacturer",
    "manufacturers",
    "battery",
    "batteries",
    "cell",
    "cells",
    "the",
    "a",
    "an",
    "of",
    "for",
    "from",
    "with",
    "show",
    "list",
    "give",
    "me",
}

FORMAL_CELL_REQUIRED_FIELDS = (
    "project_chemistry_hint",
    "form_factor",
    "nominal_capacity_ah",
    "nominal_voltage_v",
    "charge_voltage_v",
    "discharge_cutoff_v",
    "max_continuous_charge_current_a",
    "max_continuous_discharge_current_a",
    "cycle_life_cycles",
    "mass_g",
)

SUPPORTED_CELL_CATALOG_FILTER_FIELDS = (
    "approval_basis",
    "approval_status",
    "cell_id",
    "completeness_status",
    "confidence_status",
    "display_name",
    "form_factor",
    "manufacturer",
    "model",
    "positive_electrode_type",
    "project_chemistry_hint",
    "schema_name",
)


def _normalize_text(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _is_non_unknown_text(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and _normalize_text(text) != "unknown"


def _normalize_required_field_waivers(record: dict[str, Any]) -> list[str]:
    raw_waivers = record.get("required_field_waivers", [])
    if not isinstance(raw_waivers, list):
        return []

    normalized_waivers: list[str] = []
    for item in raw_waivers:
        normalized_item = _normalize_text(str(item))
        if (
            normalized_item in FORMAL_CELL_REQUIRED_FIELDS
            and normalized_item not in normalized_waivers
        ):
            normalized_waivers.append(normalized_item)
    return normalized_waivers


def _count_records(records: list[dict[str, Any]], field_name: str, *, default: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        raw_value = record.get(field_name)
        normalized_value = _normalize_text(str(raw_value or default))
        counts[normalized_value] = counts.get(normalized_value, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _merge_catalog_records(
    base_records: list[dict[str, Any]],
    overlay_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged_records: dict[str, dict[str, Any]] = {}
    insertion_order: list[str] = []

    for collection in (base_records, overlay_records):
        for record in collection:
            normalized_id = _normalize_text(str(record.get("cell_id") or ""))
            if not normalized_id:
                continue
            if normalized_id not in merged_records:
                insertion_order.append(normalized_id)
            merged_records[normalized_id] = record

    return [merged_records[normalized_id] for normalized_id in insertion_order]


def _normalize_query_tokens(query: str) -> list[str]:
    tokens = [
        token
        for token in re.split(r"[^a-zA-Z0-9]+", query.lower())
        if token
    ]
    normalized_tokens: list[str] = []
    for token in tokens:
        mapped = QUERY_ALIAS_MAP.get(token, token)
        if mapped in STOPWORDS or len(mapped) < 3:
            continue
        normalized_tokens.append(mapped)
    return normalized_tokens


def _missing_required_fields(record: dict[str, Any]) -> list[str]:
    electrical = record.get("electrical", {})
    currents = record.get("currents", {})
    lifecycle = record.get("lifecycle", {})
    physical = record.get("physical", {})

    checks = {
        "project_chemistry_hint": _is_non_unknown_text(record.get("project_chemistry_hint")),
        "form_factor": _is_non_unknown_text(record.get("form_factor")),
        "nominal_capacity_ah": electrical.get("nominal_capacity_ah") is not None,
        "nominal_voltage_v": electrical.get("nominal_voltage_v") is not None,
        "charge_voltage_v": electrical.get("charge_voltage_v") is not None,
        "discharge_cutoff_v": electrical.get("discharge_cutoff_v") is not None,
        "max_continuous_charge_current_a": currents.get("max_continuous_charge_current_a") is not None,
        "max_continuous_discharge_current_a": currents.get("max_continuous_discharge_current_a")
        is not None,
        "cycle_life_cycles": lifecycle.get("cycle_life_cycles") is not None,
        "mass_g": physical.get("mass_g") is not None,
    }
    return [field_name for field_name in FORMAL_CELL_REQUIRED_FIELDS if not checks[field_name]]


def _partition_missing_required_fields(
    record: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    missing_required_fields = _missing_required_fields(record)
    required_field_waivers = _normalize_required_field_waivers(record)
    blocking_missing_fields = [
        field_name
        for field_name in missing_required_fields
        if field_name not in required_field_waivers
    ]
    waived_missing_fields = [
        field_name
        for field_name in missing_required_fields
        if field_name in required_field_waivers
    ]
    return blocking_missing_fields, waived_missing_fields, required_field_waivers


def _build_governed_cell_record(record: dict[str, Any]) -> dict[str, Any]:
    (
        missing_required_fields,
        waived_missing_fields,
        required_field_waivers,
    ) = _partition_missing_required_fields(record)
    completeness_score = round(
        (len(FORMAL_CELL_REQUIRED_FIELDS) - len(missing_required_fields))
        / len(FORMAL_CELL_REQUIRED_FIELDS),
        3,
    )
    is_complete = not missing_required_fields

    enriched = dict(record)
    enriched["required_record_fields"] = list(FORMAL_CELL_REQUIRED_FIELDS)
    enriched["required_field_waivers"] = required_field_waivers
    enriched["waived_missing_required_fields"] = waived_missing_fields
    enriched["missing_required_fields"] = missing_required_fields
    enriched["completeness_status"] = "complete" if is_complete else "incomplete"
    enriched["completeness_score"] = completeness_score
    if is_complete and waived_missing_fields:
        enriched["confidence_status"] = "literature_backed"
    else:
        enriched["confidence_status"] = "high" if is_complete else "review_required"
    enriched["approval_status"] = "approved" if is_complete else "unapproved"
    enriched["eligible_for_planning"] = is_complete
    approval_basis = str(record.get("approval_basis") or "").strip()
    if is_complete and not approval_basis:
        approval_basis = (
            "literature_backed_manual_asset"
            if waived_missing_fields
            else "complete_record"
        )
    enriched["approval_basis"] = approval_basis or "incomplete_record"

    if is_complete:
        eligibility_tags = ["complete_record", "approved_for_planning", "formal_cell_asset"]
        if waived_missing_fields:
            eligibility_tags.append("literature_backed_exception")
        if _normalize_text(str(record.get("manufacturer") or "unknown")) == "unknown":
            eligibility_tags.append("manufacturer_unknown")
        enriched["eligibility_tags"] = eligibility_tags
    else:
        enriched["eligibility_tags"] = ["metadata_incomplete", "planning_ineligible"]
    return enriched


def _is_formally_approved_cell_record(record: dict[str, Any]) -> bool:
    return (
        _normalize_text(str(record.get("completeness_status") or "incomplete")) == "complete"
        and _normalize_text(str(record.get("approval_status") or "unapproved")) == "approved"
        and bool(record.get("eligible_for_planning"))
    )


def _build_excluded_record_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "cell_id": record.get("cell_id"),
        "display_name": record.get("display_name"),
        "manufacturer": record.get("manufacturer"),
        "model": record.get("model"),
        "schema_name": record.get("schema_name"),
        "project_chemistry_hint": record.get("project_chemistry_hint") or "unknown",
        "form_factor": record.get("form_factor") or "unknown",
        "completeness_status": record.get("completeness_status", "incomplete"),
        "completeness_score": record.get("completeness_score", 0.0),
        "confidence_status": record.get("confidence_status", "review_required"),
        "approval_status": record.get("approval_status", "unapproved"),
        "approval_basis": record.get("approval_basis", "incomplete_record"),
        "eligible_for_planning": bool(record.get("eligible_for_planning", False)),
        "eligibility_tags": list(record.get("eligibility_tags", [])),
        "required_field_waivers": list(record.get("required_field_waivers", [])),
        "waived_missing_required_fields": list(record.get("waived_missing_required_fields", [])),
        "missing_required_fields": list(record.get("missing_required_fields", [])),
        "literature_reference": record.get("literature_reference"),
        "citations": list(record.get("citations", [])),
    }


def _count_missing_field_reasons(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {field_name: 0 for field_name in FORMAL_CELL_REQUIRED_FIELDS}
    for record in records:
        for field_name in record.get("missing_required_fields", []):
            if field_name in counts:
                counts[field_name] += 1
    return {field_name: count for field_name, count in counts.items() if count > 0}


def _prepare_base_catalog_records(catalog: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_records = list(catalog.get("cells", []))
    if catalog.get("excluded_cells"):
        approved_records = [_build_governed_cell_record(record) for record in base_records]
        approved_records = [
            record for record in approved_records if _is_formally_approved_cell_record(record)
        ]
        excluded_records = [dict(record) for record in catalog.get("excluded_cells", [])]
        return approved_records, excluded_records

    governed_records = [_build_governed_cell_record(record) for record in base_records]
    approved_records = [
        record for record in governed_records if _is_formally_approved_cell_record(record)
    ]
    excluded_records = [
        _build_excluded_record_summary(record)
        for record in governed_records
        if not _is_formally_approved_cell_record(record)
    ]
    return approved_records, excluded_records


def _match_record_identifier(record: dict[str, Any], normalized_query: str) -> bool:
    if _normalize_text(str(record.get("cell_id", ""))) == normalized_query:
        return True
    aliases = [
        str(record.get("display_name", "")),
        str(record.get("model", "")),
        str(record.get("schema_name", "")),
    ]
    return any(_normalize_text(alias) == normalized_query for alias in aliases if alias)


def get_cell_catalog_field_value(record: dict[str, Any], field_name: str) -> Any:
    normalized_field = _normalize_text(field_name)
    electrical = record.get("electrical", {})
    currents = record.get("currents", {})
    physical = record.get("physical", {})
    lifecycle = record.get("lifecycle", {})
    field_map = {
        "approval_basis": record.get("approval_basis"),
        "approval_status": record.get("approval_status"),
        "cell_id": record.get("cell_id"),
        "charge_voltage_v": electrical.get("charge_voltage_v"),
        "completeness_status": record.get("completeness_status"),
        "confidence_status": record.get("confidence_status"),
        "cycle_life_cycles": lifecycle.get("cycle_life_cycles"),
        "discharge_cutoff_v": electrical.get("discharge_cutoff_v"),
        "display_name": record.get("display_name"),
        "form_factor": record.get("form_factor"),
        "manufacturer": record.get("manufacturer"),
        "mass_g": physical.get("mass_g"),
        "max_continuous_charge_current_a": currents.get("max_continuous_charge_current_a"),
        "max_continuous_discharge_current_a": currents.get("max_continuous_discharge_current_a"),
        "model": record.get("model"),
        "nominal_capacity_ah": electrical.get("nominal_capacity_ah"),
        "nominal_voltage_v": electrical.get("nominal_voltage_v"),
        "positive_electrode_type": record.get("positive_electrode_type"),
        "project_chemistry_hint": record.get("project_chemistry_hint"),
        "schema_name": record.get("schema_name"),
        "source_file": record.get("source_file"),
        "source_repository": record.get("source_repository"),
    }
    if normalized_field not in field_map:
        raise KeyError(f"Unsupported cell catalog field: {field_name}")

    return field_map[normalized_field]


def filter_cell_catalog_records(
    records: list[dict[str, Any]],
    *,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> list[dict[str, Any]]:
    if filter_field is None:
        return records

    normalized_filter_value = _normalize_text(str(filter_value or ""))
    if not normalized_filter_value:
        return records

    filtered_records: list[dict[str, Any]] = []
    for record in records:
        record_value = get_cell_catalog_field_value(record, filter_field)
        if _normalize_text(str(record_value or "")) == normalized_filter_value:
            filtered_records.append(record)
    return filtered_records


@lru_cache(maxsize=1)
def load_cell_catalog() -> dict[str, Any]:
    if not CELL_CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Cell catalog not found. Run `uv run python .\\scripts\\import_cellinfo_repository.py` first."
        )
    catalog = json.loads(CELL_CATALOG_PATH.read_text(encoding="utf-8"))
    approved_records, excluded_records = _prepare_base_catalog_records(catalog)

    manual_catalog: dict[str, Any] = {}
    if MANUAL_CELL_CATALOG_PATH.exists():
        manual_catalog = json.loads(MANUAL_CELL_CATALOG_PATH.read_text(encoding="utf-8"))

    manual_records = list(manual_catalog.get("cells", []))
    governed_manual_records = [_build_governed_cell_record(record) for record in manual_records]
    approved_manual_records = [
        record
        for record in governed_manual_records
        if _is_formally_approved_cell_record(record)
    ]
    excluded_manual_records = [
        _build_excluded_record_summary(record)
        for record in governed_manual_records
        if not _is_formally_approved_cell_record(record)
    ]

    merged_records = _merge_catalog_records(approved_records, approved_manual_records)
    merged_excluded_records = _merge_catalog_records(excluded_records, excluded_manual_records)
    all_records = [*merged_records, *merged_excluded_records]

    merged_catalog = dict(catalog)
    merged_catalog["cells"] = merged_records
    merged_catalog["record_count"] = len(merged_records)
    merged_catalog["approved_record_count"] = len(merged_records)
    merged_catalog["excluded_cells"] = merged_excluded_records
    merged_catalog["excluded_record_count"] = len(merged_excluded_records)
    merged_catalog["raw_record_count"] = len(all_records)
    merged_catalog["counts_by_chemistry_hint"] = _count_records(
        merged_records,
        "project_chemistry_hint",
        default="unknown",
    )
    merged_catalog["counts_by_form_factor"] = _count_records(
        merged_records,
        "form_factor",
        default="unknown",
    )
    merged_catalog["all_counts_by_chemistry_hint"] = _count_records(
        all_records,
        "project_chemistry_hint",
        default="unknown",
    )
    merged_catalog["all_counts_by_form_factor"] = _count_records(
        all_records,
        "form_factor",
        default="unknown",
    )
    merged_catalog["excluded_counts_by_missing_field"] = _count_missing_field_reasons(
        merged_excluded_records
    )
    merged_catalog["manual_asset_count"] = len(manual_records)
    merged_catalog["manual_catalog_version"] = manual_catalog.get("catalog_version", "manual_assets")
    merged_catalog["source_record_count"] = int(
        catalog.get("source_record_count")
        or catalog.get("raw_record_count")
        or len(list(catalog.get("cells", [])))
    )
    merged_catalog["cell_curation_policy"] = {
        "active_surface": "approved_complete_or_literature_waived",
        "required_record_fields": list(FORMAL_CELL_REQUIRED_FIELDS),
        "approval_rule": (
            "Complete records are automatically approved for formal cell lookup and "
            "planning. Manual literature assets can retain approval when they declare "
            "explicit waivers for named missing required fields."
        ),
    }

    base_version = str(catalog.get("catalog_version") or "cell_catalog")
    if manual_records:
        manual_version = str(merged_catalog["manual_catalog_version"])
        merged_catalog["catalog_version"] = f"{base_version}+{manual_version}"
    else:
        merged_catalog["catalog_version"] = base_version
    return merged_catalog


def _search_haystacks(record: dict[str, Any]) -> list[str]:
    electrical = record.get("electrical", {})
    physical = record.get("physical", {})
    literature_reference = record.get("literature_reference", {})
    citation_strings = []
    for citation in record.get("citations", []):
        citation_strings.append(str(citation))
    return [
        str(record.get("cell_id", "")),
        str(record.get("display_name", "")),
        str(record.get("manufacturer", "")),
        str(record.get("model", "")),
        str(record.get("schema_name", "")),
        str(record.get("project_chemistry_hint", "")),
        str(record.get("positive_electrode_type", "")),
        str(record.get("form_factor", "")),
        str(record.get("approval_basis", "")),
        str(record.get("source_repository", "")),
        str(electrical.get("nominal_voltage_v", "")),
        str(electrical.get("nominal_capacity_ah", "")),
        str(physical.get("diameter_mm", "")),
        str(physical.get("height_mm", "")),
        str(literature_reference.get("citation_text", "")),
        str(literature_reference.get("doi", "")),
        str(literature_reference.get("url", "")),
        *citation_strings,
    ]


def search_cell_catalog(
    query: str | None = None,
    *,
    limit: int = 10,
    distinct_manufacturers: bool = False,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> dict[str, Any]:
    catalog = load_cell_catalog()
    records = list(catalog.get("cells", []))

    normalized_filter_field = _normalize_text(str(filter_field or "")) or None
    normalized_filter_value = str(filter_value or "").strip() or None
    if normalized_filter_field:
        records = filter_cell_catalog_records(
            records,
            filter_field=normalized_filter_field,
            filter_value=normalized_filter_value,
        )

    applied_tokens: list[str] = []
    if query:
        normalized_query = _normalize_text(query)
        applied_tokens = _normalize_query_tokens(query)
        scored_records: list[tuple[int, dict[str, Any]]] = []
        for record in records:
            haystacks = [_normalize_text(haystack) for haystack in _search_haystacks(record)]
            score = 0
            if any(normalized_query in haystack for haystack in haystacks):
                score += 10
            for token in applied_tokens:
                if any(token in haystack for haystack in haystacks):
                    score += 3
            if score > 0:
                scored_records.append((score, record))
        scored_records.sort(
            key=lambda item: (
                -item[0],
                _normalize_text(str(item[1].get("manufacturer", ""))),
                _normalize_text(str(item[1].get("display_name", ""))),
            )
        )
        records = [record for _, record in scored_records]

    matched_record_count = len(records)

    if distinct_manufacturers:
        deduped_records: list[dict[str, Any]] = []
        seen_manufacturers: set[str] = set()
        for record in records:
            manufacturer = _normalize_text(str(record.get("manufacturer", "unknown")))
            if manufacturer in seen_manufacturers:
                continue
            seen_manufacturers.add(manufacturer)
            deduped_records.append(record)
        records = deduped_records

    distinct_record_count = len(records)

    records = records[: max(limit, 1)]
    return {
        "status": "ok",
        "catalog_version": catalog.get("catalog_version"),
        "query": query,
        "query_tokens": applied_tokens,
        "applied_filter": (
            {
                "field": normalized_filter_field,
                "value": normalized_filter_value,
            }
            if normalized_filter_field and normalized_filter_value
            else None
        ),
        "distinct_manufacturers": distinct_manufacturers,
        "catalog_record_count": int(catalog.get("record_count", len(catalog.get("cells", [])))),
        "approved_record_count": int(catalog.get("approved_record_count", len(catalog.get("cells", [])))),
        "raw_record_count": int(catalog.get("raw_record_count", len(catalog.get("cells", [])))),
        "excluded_record_count": int(catalog.get("excluded_record_count", 0)),
        "cell_curation_policy": catalog.get("cell_curation_policy"),
        "matched_record_count": matched_record_count,
        "post_distinct_record_count": distinct_record_count,
        "returned_record_count": len(records),
        "record_count": len(records),
        "records": records,
    }


def get_cell_catalog_record(cell_id: str) -> dict[str, Any]:
    catalog = load_cell_catalog()
    records = catalog.get("cells", [])
    normalized_query = _normalize_text(cell_id)

    for record in records:
        if _match_record_identifier(record, normalized_query):
            return record

    for record in catalog.get("excluded_cells", []):
        if _match_record_identifier(record, normalized_query):
            missing_fields = ", ".join(record.get("missing_required_fields", [])) or "required fields"
            raise KeyError(
                "Cell catalog record exists in the raw import but is excluded from the formal "
                f"catalog because it is missing: {missing_fields}."
            )

    raise KeyError(f"Unknown cell catalog record: {cell_id}")


def govern_cell_record(record: dict[str, Any]) -> dict[str, Any]:
    """Expose the formal catalog governance pass for adjacent asset workflows."""

    return _build_governed_cell_record(record)


def is_formally_approved_cell_record(record: dict[str, Any]) -> bool:
    return _is_formally_approved_cell_record(record)


def clear_cell_catalog_cache() -> None:
    load_cell_catalog.cache_clear()
