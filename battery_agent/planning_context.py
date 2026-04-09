"""Helpers for combining imported and uploaded cell metadata with planning rules."""

from __future__ import annotations

import re
from typing import Any

from battery_agent.cell_catalog import get_cell_catalog_record
from battery_agent.kb import get_chemistry_profile

UNKNOWN_TOKENS = {"", "na", "n_a", "n/a", "none", "null", "unknown"}


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if _normalize_key(stripped) in UNKNOWN_TOKENS:
        return None
    return stripped


def load_selected_cell_record(selected_cell_id: str | None) -> dict[str, Any] | None:
    normalized_id = normalize_optional_text(selected_cell_id)
    if normalized_id is None:
        return None
    return get_cell_catalog_record(normalized_id)


def _slugify_record_token(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")
    return cleaned or "uploaded_cell"


def build_transient_selected_cell_record(
    candidate: dict[str, Any] | None,
    *,
    thread_file_path: str | None = None,
) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    electrical = candidate.get("electrical", {})
    currents = candidate.get("currents", {})
    physical = candidate.get("physical", {})
    lifecycle = candidate.get("lifecycle", {})
    source_document = candidate.get("source_document", {})

    display_name = (
        normalize_optional_text(str(candidate.get("display_name") or ""))
        or normalize_optional_text(str(candidate.get("model") or ""))
        or normalize_optional_text(str(candidate.get("schema_name") or ""))
    )
    if display_name is None:
        return None

    manufacturer = normalize_optional_text(str(candidate.get("manufacturer") or "")) or "Unknown"
    model_name = normalize_optional_text(
        str(candidate.get("model") or candidate.get("schema_name") or display_name)
    ) or display_name
    generated_cell_id = f"uploaded_{_slugify_record_token(model_name)}"
    file_path = thread_file_path or normalize_optional_text(
        str(source_document.get("thread_file_path") or "")
    )

    return {
        "cell_id": generated_cell_id,
        "display_name": display_name,
        "manufacturer": manufacturer,
        "project_chemistry_hint": candidate.get("project_chemistry_hint") or "unknown",
        "form_factor": candidate.get("form_factor") or "unknown",
        "positive_electrode_type": candidate.get("positive_electrode_type"),
        "electrical": dict(electrical) if isinstance(electrical, dict) else {},
        "currents": dict(currents) if isinstance(currents, dict) else {},
        "physical": dict(physical) if isinstance(physical, dict) else {},
        "lifecycle": dict(lifecycle) if isinstance(lifecycle, dict) else {},
        "normalization_notes": list(candidate.get("normalization_notes", [])),
        "approval_status": "draft_uploaded_datasheet",
        "approval_basis": "uploaded_thread_datasheet",
        "confidence_status": "machine_extracted_review_required",
        "completeness_status": "draft_uploaded_candidate",
        "eligible_for_planning": False,
        "eligibility_tags": ["uploaded_datasheet_candidate", "draft_planning_only"],
        "waived_missing_required_fields": [],
        "literature_reference": None,
        "source_kind": "uploaded_cell_datasheet_candidate",
        "source_document": {
            "thread_file_path": file_path,
            "original_filename": source_document.get("original_filename"),
            "mime_type": source_document.get("mime_type"),
            "extraction_mode": source_document.get("extraction_mode"),
            "detected_pages": source_document.get("detected_pages"),
        },
    }


def resolve_chemistry_profile(
    *,
    chemistry: str | None,
    selected_cell_record: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []

    explicit_chemistry = normalize_optional_text(chemistry)
    chemistry_hint = normalize_optional_text(
        str(selected_cell_record.get("project_chemistry_hint"))
        if selected_cell_record and selected_cell_record.get("project_chemistry_hint") is not None
        else None
    )

    if explicit_chemistry and chemistry_hint and _normalize_key(explicit_chemistry) != _normalize_key(
        chemistry_hint
    ):
        warnings.append(
            f"Explicit chemistry `{explicit_chemistry}` overrides imported cell chemistry hint `{chemistry_hint}`."
        )

    if explicit_chemistry is not None:
        return get_chemistry_profile(explicit_chemistry), warnings

    if chemistry_hint is None:
        return None, warnings

    try:
        return get_chemistry_profile(chemistry_hint), warnings
    except KeyError:
        warnings.append(
            f"Imported cell chemistry hint `{chemistry_hint}` is not mapped to a controlled registry profile yet."
        )
        return None, warnings


def resolve_form_factor(
    *,
    form_factor: str | None,
    selected_cell_record: dict[str, Any] | None,
) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    requested_form_factor = normalize_optional_text(form_factor)
    record_form_factor = normalize_optional_text(
        str(selected_cell_record.get("form_factor"))
        if selected_cell_record and selected_cell_record.get("form_factor") is not None
        else None
    )

    effective_form_factor = requested_form_factor or record_form_factor

    if requested_form_factor and record_form_factor and _normalize_key(requested_form_factor) != _normalize_key(
        record_form_factor
    ):
        warnings.append(
            f"Requested form factor `{requested_form_factor}` differs from selected cell record `{record_form_factor}`."
        )

    return effective_form_factor, warnings


def build_selected_cell_reference(selected_cell_record: dict[str, Any] | None) -> dict[str, Any] | None:
    if selected_cell_record is None:
        return None

    electrical = selected_cell_record.get("electrical", {})
    currents = selected_cell_record.get("currents", {})
    physical = selected_cell_record.get("physical", {})

    return {
        "cell_id": selected_cell_record.get("cell_id"),
        "display_name": selected_cell_record.get("display_name"),
        "manufacturer": selected_cell_record.get("manufacturer"),
        "chemistry_hint": selected_cell_record.get("project_chemistry_hint") or "unknown",
        "completeness_status": selected_cell_record.get("completeness_status", "unknown"),
        "approval_status": selected_cell_record.get("approval_status", "unknown"),
        "approval_basis": selected_cell_record.get("approval_basis", "unknown"),
        "confidence_status": selected_cell_record.get("confidence_status", "unknown"),
        "eligible_for_planning": bool(selected_cell_record.get("eligible_for_planning", False)),
        "eligibility_tags": list(selected_cell_record.get("eligibility_tags", [])),
        "waived_missing_required_fields": list(
            selected_cell_record.get("waived_missing_required_fields", [])
        ),
        "literature_reference": selected_cell_record.get("literature_reference"),
        "positive_electrode_type": selected_cell_record.get("positive_electrode_type") or "unknown",
        "form_factor": selected_cell_record.get("form_factor") or "unknown",
        "nominal_capacity_ah": electrical.get("nominal_capacity_ah"),
        "nominal_voltage_v": electrical.get("nominal_voltage_v"),
        "charge_voltage_v": electrical.get("charge_voltage_v"),
        "discharge_cutoff_v": electrical.get("discharge_cutoff_v"),
        "recommended_charge_current_a": currents.get("recommended_charge_current_a"),
        "recommended_discharge_current_a": currents.get("recommended_discharge_current_a"),
        "max_continuous_charge_current_a": currents.get("max_continuous_charge_current_a"),
        "max_continuous_discharge_current_a": currents.get("max_continuous_discharge_current_a"),
        "mass_g": physical.get("mass_g"),
        "normalization_notes": list(selected_cell_record.get("normalization_notes", [])),
        "source_kind": selected_cell_record.get("source_kind", "imported_cell_catalog"),
        "source_document": selected_cell_record.get("source_document"),
    }


def resolve_voltage_window(
    *,
    chemistry_profile: dict[str, Any] | None,
    selected_cell_record: dict[str, Any] | None,
    prefer_selected_cell_constraints: bool = False,
) -> tuple[float, float, str]:
    if prefer_selected_cell_constraints and selected_cell_record is not None:
        electrical = selected_cell_record.get("electrical", {})
        charge_voltage_v = electrical.get("charge_voltage_v")
        discharge_cutoff_v = electrical.get("discharge_cutoff_v")
        if charge_voltage_v is not None and discharge_cutoff_v is not None:
            source_kind = selected_cell_record.get("source_kind", "imported_cell_catalog")
            source_key = (
                "uploaded_cell_datasheet_candidate"
                if source_kind == "uploaded_cell_datasheet_candidate"
                else "selected_cell_imported_metadata"
            )
            return float(charge_voltage_v), float(discharge_cutoff_v), source_key

    if chemistry_profile is not None:
        return (
            float(chemistry_profile["charge_voltage_v"]),
            float(chemistry_profile["discharge_cutoff_v"]),
            "registry_chemistry_profile",
        )

    if selected_cell_record is None:
        raise KeyError("Provide a chemistry or selected cell to determine the voltage window.")

    electrical = selected_cell_record.get("electrical", {})
    charge_voltage_v = electrical.get("charge_voltage_v")
    discharge_cutoff_v = electrical.get("discharge_cutoff_v")
    if charge_voltage_v is None or discharge_cutoff_v is None:
        raise KeyError("Selected cell record does not define a usable voltage window.")

    source_kind = selected_cell_record.get("source_kind", "imported_cell_catalog")
    source_key = (
        "uploaded_cell_datasheet_candidate"
        if source_kind == "uploaded_cell_datasheet_candidate"
        else "selected_cell_imported_metadata"
    )
    return float(charge_voltage_v), float(discharge_cutoff_v), source_key


def build_selected_cell_current_warnings(
    *,
    selected_cell_record: dict[str, Any] | None,
    charge_c_rate: float,
    discharge_c_rate: float,
) -> list[str]:
    if selected_cell_record is None:
        return []

    electrical = selected_cell_record.get("electrical", {})
    currents = selected_cell_record.get("currents", {})
    nominal_capacity_ah = electrical.get("nominal_capacity_ah")
    if nominal_capacity_ah in (None, 0):
        return []

    nominal_capacity_ah = float(nominal_capacity_ah)
    requested_charge_current_a = charge_c_rate * nominal_capacity_ah
    requested_discharge_current_a = discharge_c_rate * nominal_capacity_ah

    warnings: list[str] = []
    max_charge_current_a = currents.get("max_continuous_charge_current_a")
    max_discharge_current_a = currents.get("max_continuous_discharge_current_a")
    source_kind = selected_cell_record.get("source_kind", "imported_cell_catalog")
    source_label = (
        "uploaded datasheet"
        if source_kind == "uploaded_cell_datasheet_candidate"
        else "imported selected-cell"
    )

    if max_charge_current_a is not None and requested_charge_current_a > float(max_charge_current_a):
        warnings.append(
            "Requested charge current "
            f"{requested_charge_current_a:.2f} A ({charge_c_rate:.2f}C on {nominal_capacity_ah:.2f} Ah) "
            f"exceeds the {source_label} continuous-charge rating "
            f"{float(max_charge_current_a):.2f} A. Treat that rating as external reference data pending review."
        )
    if max_discharge_current_a is not None and requested_discharge_current_a > float(max_discharge_current_a):
        warnings.append(
            "Requested discharge current "
            f"{requested_discharge_current_a:.2f} A ({discharge_c_rate:.2f}C on {nominal_capacity_ah:.2f} Ah) "
            f"exceeds the {source_label} continuous-discharge rating "
            f"{float(max_discharge_current_a):.2f} A. Treat that rating as external reference data pending review."
        )

    return warnings
