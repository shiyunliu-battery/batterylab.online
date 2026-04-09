"""Import CellInfoRepository data into a flattened cell catalog for this project."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / ".tmp" / "CellInfoRepository"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "reference" / "cell_catalog"

PROPERTY_FIELD_MAP = {
    "RatedCapacity": ("electrical", "nominal_capacity_ah"),
    "NominalVoltage": ("electrical", "nominal_voltage_v"),
    "UpperVoltageLimit": ("electrical", "charge_voltage_v"),
    "LowerVoltageLimit": ("electrical", "discharge_cutoff_v"),
    "ChargingCurrent": ("currents", "recommended_charge_current_a"),
    "DischargingCurrent": ("currents", "recommended_discharge_current_a"),
    "MaximumContinuousChargingCurrent": ("currents", "max_continuous_charge_current_a"),
    "MaximumContinuousDischargingCurrent": ("currents", "max_continuous_discharge_current_a"),
    "CycleLife": ("lifecycle", "cycle_life_cycles"),
    "Mass": ("physical", "mass_kg"),
    "Diameter": ("physical", "diameter_m"),
    "Height": ("physical", "height_m"),
    "Width": ("physical", "width_m"),
    "Length": ("physical", "length_m"),
    "Thickness": ("physical", "thickness_m"),
}

CHEMISTRY_HINT_MAP = {
    "LithiumIronPhosphate": "lfp",
    "LithiumNickelManganeseCobaltOxide": "nmc",
    "LithiumNickelCobaltAluminiumOxide": "nca",
    "LithiumCobaltOxide": "lco",
    "LithiumManganeseOxide": "lmo",
    "LithiumTitanateOxide": "lto",
}

CASE_TYPE_MAP = {
    "PrismaticCase": "prismatic",
    "PouchCase": "pouch",
    "CylindricalCase": "cylindrical",
    "CoinCase": "coin",
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


def _normalize_text(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _is_non_unknown_text(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and _normalize_text(text) != "unknown"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", ".")
    try:
        numeric = float(text)
    except ValueError:
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _looks_like_cylindrical_code(text: str | None) -> bool:
    if not text:
        return False
    return re.search(r"(?:^|[^0-9])(1[468]\d{3}|2[16]700|26650|32650|38120|40152|4680)(?:$|[^0-9])", text) is not None


def _first_non_generic_type(type_field: Any) -> str | None:
    if isinstance(type_field, str):
        return type_field
    if isinstance(type_field, list):
        for item in type_field:
            if isinstance(item, str) and item != "ConventionalProperty":
                return item
    return None


def _collect_property_citations(properties: list[dict[str, Any]]) -> list[str]:
    citations: list[str] = []
    for item in properties:
        citation = item.get("schema:citation", {})
        if isinstance(citation, dict):
            citation_id = citation.get("@id")
            if isinstance(citation_id, str) and citation_id not in citations:
                citations.append(citation_id)
    return citations


def _convert_metric_convenience_fields(record: dict[str, Any]) -> None:
    physical = record.setdefault("physical", {})
    for metric_key in ("diameter", "height", "width", "length", "thickness"):
        value_m = physical.get(f"{metric_key}_m")
        if isinstance(value_m, (int, float)):
            physical[f"{metric_key}_mm"] = round(float(value_m) * 1000.0, 3)
    mass_kg = physical.get("mass_kg")
    if isinstance(mass_kg, (int, float)):
        physical["mass_g"] = round(float(mass_kg) * 1000.0, 3)


def _normalize_form_factor(
    *,
    schema_name: str | None,
    case_types: list[str],
    record: dict[str, Any],
) -> tuple[str | None, list[str]]:
    notes: list[str] = []
    case_type_value = next((CASE_TYPE_MAP[item] for item in case_types if item in CASE_TYPE_MAP), None)
    physical = record.get("physical", {})
    has_diameter = isinstance(physical.get("diameter_m"), (int, float))
    has_height = isinstance(physical.get("height_m"), (int, float))
    has_width = isinstance(physical.get("width_m"), (int, float))
    has_length = isinstance(physical.get("length_m"), (int, float))
    cylindrical_hint = _looks_like_cylindrical_code(schema_name) or (has_diameter and has_height and not has_width and not has_length)

    if cylindrical_hint and case_type_value != "cylindrical":
        if case_type_value is not None:
            notes.append(
                f"Normalized form factor from `{case_type_value}` to `cylindrical` using model code and dimension heuristics."
            )
        else:
            notes.append("Inferred `cylindrical` form factor from model code and dimension heuristics.")
        return "cylindrical", notes

    if case_type_value is not None:
        return case_type_value, notes
    if has_width and has_length and has_height:
        return "prismatic", notes
    return None, notes


def _load_product_list_index(source_root: Path) -> dict[str, dict[str, str]]:
    product_list_path = source_root / "Sources" / "cell_product_list.csv"
    if not product_list_path.exists():
        return {}

    index: dict[str, dict[str, str]] = {}
    with product_list_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            manufacturer = row.get("manufacturer", "").strip()
            model = row.get("model", "").strip()
            if not manufacturer or not model:
                continue
            index[_normalize_text(f"{manufacturer}::{model}")] = row
    return index


def _build_cell_record(path: Path, product_list_index: dict[str, dict[str, str]]) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    manufacturer = (
        payload.get("schema:manufacturer", {}).get("schema:name")
        if isinstance(payload.get("schema:manufacturer"), dict)
        else None
    )
    schema_name = payload.get("schema:name")
    positive_electrode_type = (
        payload.get("hasPositiveElectrode", {})
        .get("hasActiveMaterial", {})
        .get("@type")
        if isinstance(payload.get("hasPositiveElectrode"), dict)
        else None
    )
    case_types = [
        case_item.get("@type")
        for case_item in payload.get("hasCase", [])
        if isinstance(case_item, dict) and isinstance(case_item.get("@type"), str)
    ]
    project_chemistry_hint = CHEMISTRY_HINT_MAP.get(str(positive_electrode_type), None)

    properties = payload.get("hasProperty", [])
    record: dict[str, Any] = {
        "cell_id": path.stem,
        "display_name": f"{manufacturer} {schema_name}".strip() if manufacturer else path.stem,
        "manufacturer": manufacturer,
        "model": schema_name,
        "schema_name": schema_name,
        "positive_electrode_type": positive_electrode_type,
        "project_chemistry_hint": project_chemistry_hint,
        "case_types": case_types,
        "form_factor": None,
        "electrical": {},
        "currents": {},
        "physical": {},
        "lifecycle": {},
        "normalization_notes": [],
        "citations": _collect_property_citations(properties),
        "source_file": f"BatteryTypeJson/{path.name}",
        "source_repository": "phdechent/CellInfoRepository",
    }

    for property_item in properties:
        if not isinstance(property_item, dict):
            continue
        property_type = _first_non_generic_type(property_item.get("@type"))
        if property_type is None or property_type not in PROPERTY_FIELD_MAP:
            continue
        section_name, field_name = PROPERTY_FIELD_MAP[property_type]
        numerical_value = (
            property_item.get("hasNumericalPart", {}).get("hasNumericalValue")
            if isinstance(property_item.get("hasNumericalPart"), dict)
            else None
        )
        value = _safe_float(numerical_value)
        if value is None:
            continue
        record[section_name][field_name] = value

    _convert_metric_convenience_fields(record)
    form_factor, normalization_notes = _normalize_form_factor(
        schema_name=schema_name,
        case_types=case_types,
        record=record,
    )
    record["form_factor"] = form_factor
    record["normalization_notes"].extend(normalization_notes)

    if manufacturer and schema_name:
        product_match = product_list_index.get(_normalize_text(f"{manufacturer}::{schema_name}"))
        if product_match:
            record["product_list_match"] = {
                "wikidata": product_match.get("wikidata"),
                "source_url": product_match.get("source"),
                "type": product_match.get("Type"),
                "case": product_match.get("Case"),
            }
            product_case = (product_match.get("Case") or "").strip()
            if product_case.startswith("R") and record.get("form_factor") != "cylindrical":
                record["form_factor"] = "cylindrical"
                record["normalization_notes"].append(
                    f"Normalized form factor to `cylindrical` from product-list case `{product_case}`."
                )

    return record


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


def _build_governed_cell_record(record: dict[str, Any]) -> dict[str, Any]:
    missing_required_fields = _missing_required_fields(record)
    completeness_score = round(
        (len(FORMAL_CELL_REQUIRED_FIELDS) - len(missing_required_fields))
        / len(FORMAL_CELL_REQUIRED_FIELDS),
        3,
    )
    is_complete = not missing_required_fields

    enriched = dict(record)
    enriched["required_record_fields"] = list(FORMAL_CELL_REQUIRED_FIELDS)
    enriched["missing_required_fields"] = missing_required_fields
    enriched["completeness_status"] = "complete" if is_complete else "incomplete"
    enriched["completeness_score"] = completeness_score
    enriched["confidence_status"] = "high" if is_complete else "review_required"
    enriched["approval_status"] = "approved" if is_complete else "unapproved"
    enriched["eligible_for_planning"] = is_complete
    enriched["eligibility_tags"] = (
        ["complete_record", "approved_for_planning", "formal_cell_asset"]
        if is_complete
        else ["metadata_incomplete", "planning_ineligible"]
    )
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
        "eligible_for_planning": bool(record.get("eligible_for_planning", False)),
        "eligibility_tags": list(record.get("eligibility_tags", [])),
        "missing_required_fields": list(record.get("missing_required_fields", [])),
    }


def _count_missing_field_reasons(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {field_name: 0 for field_name in FORMAL_CELL_REQUIRED_FIELDS}
    for record in records:
        for field_name in record.get("missing_required_fields", []):
            if field_name in counts:
                counts[field_name] += 1
    return {field_name: count for field_name, count in counts.items() if count > 0}


def build_catalog(source_root: Path) -> dict[str, Any]:
    json_dir = source_root / "BatteryTypeJson"
    if not json_dir.exists():
        raise FileNotFoundError(f"Missing directory: {json_dir}")

    product_list_index = _load_product_list_index(source_root)
    raw_records = [
        _build_cell_record(path, product_list_index)
        for path in sorted(json_dir.glob("*.json"))
    ]
    governed_records = [_build_governed_cell_record(record) for record in raw_records]
    approved_records = [
        record for record in governed_records if _is_formally_approved_cell_record(record)
    ]
    excluded_records = [
        _build_excluded_record_summary(record)
        for record in governed_records
        if not _is_formally_approved_cell_record(record)
    ]

    chemistry_counts = Counter(record.get("project_chemistry_hint") or "unknown" for record in approved_records)
    form_factor_counts = Counter(record.get("form_factor") or "unknown" for record in approved_records)
    source_chemistry_counts = Counter(
        record.get("project_chemistry_hint") or "unknown" for record in governed_records
    )
    source_form_factor_counts = Counter(
        record.get("form_factor") or "unknown" for record in governed_records
    )

    return {
        "catalog_version": "cellinfo_import_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_repository": "https://github.com/phdechent/CellInfoRepository",
        "source_record_count": len(governed_records),
        "record_count": len(approved_records),
        "approved_record_count": len(approved_records),
        "excluded_record_count": len(excluded_records),
        "counts_by_chemistry_hint": dict(sorted(chemistry_counts.items())),
        "counts_by_form_factor": dict(sorted(form_factor_counts.items())),
        "source_counts_by_chemistry_hint": dict(sorted(source_chemistry_counts.items())),
        "source_counts_by_form_factor": dict(sorted(source_form_factor_counts.items())),
        "excluded_counts_by_missing_field": _count_missing_field_reasons(excluded_records),
        "cell_curation_policy": {
            "active_surface": "approved_complete_only",
            "required_record_fields": list(FORMAL_CELL_REQUIRED_FIELDS),
            "approval_rule": "Complete records are automatically marked approved for formal cell lookup and planning.",
        },
        "cells": approved_records,
        "excluded_cells": excluded_records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Path to the cloned CellInfoRepository root.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the flattened catalog should be written.",
    )
    args = parser.parse_args()

    catalog = build_catalog(args.source_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / "cell_catalog.json"
    output_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=True), encoding="utf-8")
    print(f"Wrote {output_path} with {catalog['record_count']} records.")


if __name__ == "__main__":
    main()
