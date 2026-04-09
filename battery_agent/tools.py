"""Starter battery tools for the Battery Lab Assistant deep agent."""

from __future__ import annotations

import copy
import csv
import io
import json
import math
import re
from pathlib import Path
from typing import Annotated, Any

import numpy as np
import pandas as pd
from deepagents.backends.state import StateBackend
from langchain_core.tools import StructuredTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import interrupt as langgraph_interrupt
from pydantic import BaseModel, Field

from battery_agent.data_adapters import (
    AdapterDetectionError,
    AdapterReadError,
    AdapterSchemaError,
    UnknownAdapterError,
    list_supported_adapter_ids,
    parse_raw_export_file,
    parse_raw_export_text,
)
from battery_agent.cell_datasheet_extraction import (
    extract_cell_datasheet_candidate_from_text,
)
from battery_agent.cell_catalog import (
    SUPPORTED_CELL_CATALOG_FILTER_FIELDS,
    get_cell_catalog_field_value,
    get_cell_catalog_record,
    load_cell_catalog,
    search_cell_catalog,
)
from battery_agent.provisional_cell_assets import (
    get_provisional_cell_asset as get_provisional_cell_asset_record,
    promote_provisional_cell_asset as promote_provisional_cell_asset_record,
    register_provisional_cell_asset as register_provisional_cell_asset_record,
    review_provisional_cell_asset as review_provisional_cell_asset_record,
    search_provisional_cell_assets as search_provisional_cell_asset_records,
)
from battery_agent.equipment_manuals import (
    get_equipment_manual_asset,
    search_equipment_manual_assets,
)
from battery_agent.knowledge import (
    get_knowledge_source as get_literature_source,
    search_knowledge_evidence as search_literature_evidence,
)
from battery_agent.kb import (
    REPO_ROOT,
    chamber_required_for_temperature,
    get_authority_and_precedence_model,
    get_chemistry_profile,
    get_decision_conflict_representation,
    get_decision_relation_classes,
    get_equipment_rule,
    get_objective_template,
    get_pretest_approved_equipment_defaults,
    get_pretest_global_defaults,
    get_pretest_objective_guidance,
    get_pretest_rpt_playbook,
    get_requirement_strength_levels,
    get_safety_checklist,
    get_thermocouple_placement_guidance,
    get_thermal_chamber_rule,
    list_instrument_rule_keys,
    list_thermal_chamber_rule_keys,
    list_demo_assets,
    load_kb,
    normalize_objective_key,
    resolve_sample_path,
)
from battery_agent.methods import (
    MissingMethodInputsError,
    build_grouped_reference_markdown,
    build_parameter_request_payload,
    get_method_payload,
    list_method_profiles,
    plan_method_protocol,
    render_method_protocol_steps,
)
from battery_agent.planning_context import (
    build_transient_selected_cell_record,
    build_selected_cell_current_warnings,
    build_selected_cell_reference,
    load_selected_cell_record,
    normalize_optional_text,
    resolve_chemistry_profile,
    resolve_form_factor,
    resolve_voltage_window,
)
from battery_agent.registries import (
    get_chemistry_definition,
    get_default_method_for_objective,
    get_method_definition,
)
from battery_agent.workflow_assets import summarize_workflow_assets

ECM_IDENTIFICATION_TOOL_ENABLED = False


class KnowledgeQuery(BaseModel):
    chemistry: str | None = Field(default=None, description="Chemistry key, for example lfp or nmc811.")
    instrument: str | None = Field(
        default=None,
        description="Equipment key, for example arbin_bt2000 or biologic_bcs815.",
    )
    thermal_chamber: str | None = Field(
        default=None,
        description="Optional thermal chamber key, for example binder_lit_mk.",
    )
    objective: str | None = Field(
        default=None,
        description="Objective key, for example cycle_life, hppc, or rate_capability.",
    )


class ChemistryProfileRequest(BaseModel):
    chemistry: str = Field(
        description="Chemistry key or alias, for example lfp, nmc811, nmc, or nca."
    )


class CellCatalogSearchRequest(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional free-text search over manufacturer, model, chemistry hint, form factor, or cell id.",
    )
    limit: int = Field(
        default=10,
        description="Maximum number of matching records to return.",
    )
    distinct_manufacturers: bool = Field(
        default=False,
        description="When true, return at most one record per manufacturer.",
    )
    filter_field: str | None = Field(
        default=None,
        description=(
            "Optional exact-match field filter such as project_chemistry_hint, "
            "positive_electrode_type, manufacturer, or form_factor."
        ),
    )
    filter_value: str | None = Field(
        default=None,
        description="Exact-match filter value to pair with filter_field.",
    )


class CellCatalogExportRequest(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional free-text search over manufacturer, model, chemistry hint, form factor, or cell id.",
    )
    format: str = Field(
        default="csv",
        description="Export format: csv, markdown, txt, or json.",
    )
    limit: int = Field(
        default=500,
        description="Maximum number of matching records to export.",
    )
    distinct_manufacturers: bool = Field(
        default=False,
        description="When true, export at most one record per manufacturer.",
    )
    filter_field: str | None = Field(
        default=None,
        description=(
            "Optional exact-match field filter such as project_chemistry_hint, "
            "positive_electrode_type, manufacturer, or form_factor."
        ),
    )
    filter_value: str | None = Field(
        default=None,
        description="Exact-match filter value to pair with filter_field.",
    )
    columns_json: str = Field(
        default="[]",
        description=(
            "Optional JSON array of export columns. Supported columns include cell_id, "
            "manufacturer, model, display_name, form_factor, positive_electrode_type, "
            "project_chemistry_hint, nominal_capacity_ah, nominal_voltage_v, "
            "charge_voltage_v, discharge_cutoff_v, max_continuous_charge_current_a, "
            "max_continuous_discharge_current_a, mass_g, cycle_life_cycles, "
            "source_repository, and source_file."
        ),
    )
    filename_hint: str | None = Field(
        default=None,
        description="Optional filename hint such as lfp_cells or positive_electrode_type_cells.",
    )


class CellCatalogRecordRequest(BaseModel):
    cell_id: str = Field(
        description="Exact cell catalog id or a close alias such as manufacturer+model."
    )


class ProvisionalCellAssetSearchRequest(BaseModel):
    query: str | None = Field(
        default=None,
        description="Optional free-text search over provisional id, display name, manufacturer, chemistry hint, or form factor.",
    )
    review_status: str | None = Field(
        default=None,
        description="Optional review status filter such as draft_extracted, submitted_for_review, needs_changes, approved_for_promotion, or promoted_to_manual_asset.",
    )
    limit: int = Field(default=10, description="Maximum number of provisional assets to return.")


class ProvisionalCellAssetRequest(BaseModel):
    provisional_id: str = Field(description="Exact provisional cell asset id.")


class ProvisionalCellAssetRegisterRequest(BaseModel):
    asset_json: str = Field(
        description="JSON object with extracted cell fields. Use the formal cell schema where possible: display_name, manufacturer, project_chemistry_hint, form_factor, electrical, currents, physical, lifecycle, and field_evidence.",
    )
    submitted_by: str = Field(description="Uploader or owner of the provisional asset.")
    source_file: str | None = Field(
        default=None,
        description="Optional original source file path or filename for the uploaded datasheet.",
    )
    extraction_status: str = Field(
        default="machine_extracted",
        description="Extraction state such as machine_extracted or manual_entry.",
    )
    parser_version: str = Field(
        default="manual_entry",
        description="Parser or ingestion version used to create the provisional asset.",
    )
    submit_for_review: bool = Field(
        default=False,
        description="When true, immediately mark the new provisional asset as submitted_for_review.",
    )


class ProvisionalCellAssetReviewRequest(BaseModel):
    provisional_id: str = Field(description="Exact provisional cell asset id.")
    decision: str = Field(
        description="Workflow decision: user_corrected, submit_for_review, needs_changes, reject, or approve_for_promotion.",
    )
    actor: str = Field(description="User or reviewer applying the decision.")
    review_notes_json: str = Field(
        default="[]",
        description="Optional JSON array of review or correction notes.",
    )
    corrected_fields_json: str = Field(
        default="{}",
        description="Optional JSON object with corrected cell fields, for example nested electrical/currents/physical updates.",
    )
    required_field_waivers_json: str = Field(
        default="[]",
        description="Optional JSON array of waived formal required fields when a reviewer accepts a documented exception.",
    )


class ProvisionalCellAssetPromotionRequest(BaseModel):
    provisional_id: str = Field(description="Exact provisional cell asset id.")
    reviewer: str = Field(description="Reviewer approving and executing the promotion.")
    final_cell_id: str | None = Field(
        default=None,
        description="Optional final formal cell id. If omitted, one is generated from manufacturer and model/display name.",
    )
    promotion_notes_json: str = Field(
        default="[]",
        description="Optional JSON array of notes to carry into approval_notes on the promoted manual asset.",
    )
    replace_existing: bool = Field(
        default=False,
        description="When true, allow promotion to overwrite an existing manual asset with the same cell_id.",
    )


class UploadedCellDatasheetRequest(BaseModel):
    file_path: str = Field(
        description="Exact uploaded thread file path such as /uploads/<id>-datasheet.pdf.txt."
    )


class UploadedCellDatasheetToProvisionalAssetRequest(BaseModel):
    file_path: str = Field(
        description="Exact uploaded thread file path such as /uploads/<id>-datasheet.pdf.txt."
    )
    submitted_by: str = Field(
        default="chat_user",
        description="Uploader or owner of the provisional asset record.",
    )
    submit_for_review: bool = Field(
        default=False,
        description="When true, register the extracted provisional asset directly as submitted_for_review.",
    )


class ProtocolDraftRequest(BaseModel):
    objective: str = Field(description="Objective key such as cycle_life, hppc, or rate_capability.")
    chemistry: str | None = Field(
        default=None,
        description="Optional chemistry key such as lfp, nmc811, or nca. Leave blank when the selected cell chemistry is still unknown.",
    )
    selected_cell_id: str | None = Field(
        default=None,
        description="Optional imported cell catalog id such as Panasonic_NCR18650BF. Use this for commercial-cell planning without inventing chemistry.",
    )
    instrument: str | None = Field(
        default=None,
        description="Optional equipment key such as arbin_bt2000. Required to finalize instrument-constrained plans.",
    )
    thermal_chamber: str | None = Field(
        default=None,
        description="Optional thermal chamber key such as binder_lit_mk for chamber-aware preflight guidance.",
    )
    form_factor: str | None = Field(
        default=None,
        description="Optional cell format or pack form factor. If omitted and selected_cell_id is supplied, the imported cell form factor is used.",
    )
    target_temperature_c: float = Field(default=25.0, description="Requested test temperature in Celsius.")
    charge_c_rate: float = Field(default=0.5, description="Requested charge C-rate.")
    discharge_c_rate: float = Field(default=0.5, description="Requested discharge C-rate.")
    cycle_count: int = Field(
        default=100,
        description="Legacy/default numeric run length. Use method_inputs_json for method-specific fields such as block_basis, target_soc, checkpoint_interval, target_voltage, or hold_duration.",
    )
    method_inputs_json: str = Field(
        default="{}",
        description="Optional JSON object with method-specific planning inputs, for example {\"profile_family\":\"BEV\",\"block_basis\":\"cycle_block\",\"stop_criterion\":\"80% SOH\"}.",
    )
    operator_notes: str = Field(default="", description="Optional extra context for the draft.")


class CycleAnalysisRequest(BaseModel):
    csv_path: str = Field(
        description="Absolute path or repo-relative path to a cycle CSV file. Example: data/samples/lfp_cycle_sample.csv."
    )
    nominal_capacity_ah: float | None = Field(
        default=None,
        description="Optional nominal capacity for comparison against measured capacity.",
    )


class RawCyclerParseRequest(BaseModel):
    file_path: str = Field(
        description="Absolute local file path or uploaded thread file path such as /uploads/<id>-raw-export.csv."
    )
    attachment_text: str | None = Field(
        default=None,
        description=(
            "Optional raw attachment text or read_file output for the same dataset. "
            "Use this when a `/uploads/...` preview is readable through read_file but "
            "direct thread-file lookup is unavailable."
        ),
    )
    adapter_id: str | None = Field(
        default=None,
        description=(
            "Optional explicit adapter id such as arbin_csv_v1 or neware_csv_v1. "
            "Leave blank to auto-detect for CSV/TSV uploads."
        ),
    )
    preview_rows: int = Field(
        default=8,
        ge=1,
        le=25,
        description="How many normalized rows to include in the preview payload.",
    )


class ReportRequest(BaseModel):
    goal: str = Field(description="Plain-language experiment or analysis goal.")
    protocol_json: str = Field(description="JSON string from design_battery_protocol.")
    analysis_json: str = Field(description="JSON string from run_cycle_data_analysis.")
    analyst_notes: str = Field(default="", description="Optional final narrative or caveats.")


class MethodLookupRequest(BaseModel):
    method_id: str = Field(
        description="Structured method id or raw chapter title from the supplied battery methods PDF."
    )


class LiteratureEvidenceSearchRequest(BaseModel):
    query: str = Field(
        description="Free-text literature query, for example DOE screening, charging optimization, or ECM parameter identification."
    )
    limit: int = Field(default=3, description="Maximum number of matching evidence cards to return.")


class LiteratureSourceRequest(BaseModel):
    source_id: str = Field(
        description="Structured literature source id such as roman_ramirez_2022_doe_review."
    )


class EquipmentManualSearchRequest(BaseModel):
    query: str = Field(
        description="Free-text equipment/manual query, for example thermal chamber, Neware 5V6A, Ivium EIS setup, or gas detection."
    )
    limit: int = Field(default=5, description="Maximum number of matching manual assets to return.")


class EquipmentManualAssetRequest(BaseModel):
    asset_id: str = Field(
        description="Structured equipment-manual asset id such as binder_lit_mk_battery_test_chamber_manual."
    )


class StandardMethodPlanRequest(BaseModel):
    method_id: str = Field(
        description="Structured method id such as soc_ocv, pulse_hppc, capacity_test, or cycle_life."
    )
    chemistry: str | None = Field(
        default=None,
        description="Optional chemistry key such as lfp, nmc811, or nca. Leave blank when selected_cell_id chemistry is unknown.",
    )
    selected_cell_id: str | None = Field(
        default=None,
        description="Optional imported cell catalog id such as Panasonic_NCR18650BF for selected-cell planning flows.",
    )
    instrument: str | None = Field(
        default=None,
        description="Optional equipment key such as arbin_bt2000. Required before the plan can be finalized against instrument limits.",
    )
    thermal_chamber: str | None = Field(
        default=None,
        description="Optional thermal chamber key such as binder_lit_mk for chamber-aware preflight guidance.",
    )
    form_factor: str | None = Field(
        default=None,
        description="Optional cell format or pack form factor. If omitted and selected_cell_id is supplied, the imported cell form factor is used.",
    )
    target_temperature_c: float = Field(default=25.0, description="Requested test temperature in Celsius.")
    charge_c_rate: float = Field(default=0.5, description="Requested charge C-rate.")
    discharge_c_rate: float = Field(default=0.5, description="Requested discharge C-rate.")
    cycle_count: int = Field(
        default=1,
        description="Legacy/default numeric run length. Use method_inputs_json for method-specific planner fields such as target_soc, checkpoint_interval, elapsed_time_block, target_voltage, or hold_duration.",
    )
    method_inputs_json: str = Field(
        default="{}",
        description="Optional JSON object with method-specific planning inputs, for example {\"target_soc\":50,\"checkpoint_interval\":\"6 weeks\",\"stop_criterion\":\"80% SOH\"}.",
    )
    operator_notes: str = Field(default="", description="Optional planning notes.")


class EcmParameterIdentificationRequest(BaseModel):
    file_path: str = Field(
        description="Absolute local file path or uploaded thread file path such as /uploads/<id>-hppc.csv."
    )
    attachment_text: str | None = Field(
        default=None,
        description="Optional raw attachment text or read_file output for the same dataset.",
    )
    adapter_id: str | None = Field(
        default=None,
        description="Optional explicit adapter id such as arbin_csv_v1, neware_csv_v1, or generic_battery_tabular_v1.",
    )
    ecm_model_id: str = Field(
        default="thevenin_1rc",
        description="ECM model id to fit. The current implementation supports r0_only and thevenin_1rc.",
    )
    target_pulse_index: int | None = Field(
        default=None,
        description="Optional 1-based pulse index when the dataset contains multiple pulse candidates.",
    )
    current_threshold_a: float = Field(
        default=0.02,
        description="Minimum absolute current magnitude treated as an active pulse segment.",
    )
    time_column: str | None = Field(
        default=None,
        description="Optional raw time-column name when the upload cannot be normalized automatically.",
    )
    current_column: str | None = Field(
        default=None,
        description="Optional raw current-column name when the upload cannot be normalized automatically.",
    )
    voltage_column: str | None = Field(
        default=None,
        description="Optional raw voltage-column name when the upload cannot be normalized automatically.",
    )


def _format_preview_value(value: Any) -> Any:
    import math
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (int, str, bool)):
        return value
    if value is None:
        return None
    return str(value)


def _slugify_path_segment(value: str) -> str:
    safe = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in safe:
        safe = safe.replace("--", "-")
    return safe.strip("-") or "parsed-export"


def _adapter_result_to_payload(
    result: Any,
    preview_rows: int = 8,
) -> dict[str, Any]:
    """Build a structured tool payload from an AdapterParseResult.

    This function is the sole owner of UI-facing rendering logic (markdown,
    preview CSV generation, badge labels). AdapterParseResult itself stays
    as a pure data-layer dataclass.
    """
    import pandas as pd
    from battery_agent.data_adapters import (
        required_canonical_fields,
        optional_canonical_fields,
    )
    from battery_agent.data_adapters.generic import GenericBatteryTabularAdapter

    frame = result.frame
    cycle_count = (
        int(frame["cycle_index"].nunique())
        if "cycle_index" in frame.columns
        else None
    )
    preview = (
        frame.head(max(preview_rows, 1))
        .where(pd.notna(frame.head(max(preview_rows, 1))), None)
        .to_dict(orient="records")
    )
    preview = [
        {key: _format_preview_value(value) for key, value in row.items()}
        for row in preview
    ]
    dataset_csv = frame.to_csv(index=False)
    canonical_columns = list(frame.columns)

    is_generic = result.adapter_id == GenericBatteryTabularAdapter.adapter_id
    if is_generic:
        required_fields: list[str] = []
        missing_required: list[str] = []
        missing_optional: list[str] = []
        report_title = f"## Inspected Battery Dataset: {result.adapter_vendor}"
        display_label = f"{result.adapter_vendor} preview"
    else:
        required_fields = required_canonical_fields()
        missing_required = [f for f in required_fields if f not in canonical_columns]
        missing_optional = [f for f in optional_canonical_fields() if f not in canonical_columns]
        report_title = f"## Parsed Raw Cycler Export: {result.adapter_vendor}"
        display_label = f"{result.adapter_vendor} normalized preview"

    source_slug = _slugify_path_segment(Path(result.source_name).stem or result.adapter_id)
    ui_lines = [
        report_title,
        "",
        f"- Source: `{result.source_name}`",
        f"- Adapter: `{result.adapter_id}`",
        f"- Detection: `{'auto' if result.auto_detected else 'explicit'}` via `{result.detected_from}`",
        f"- Dataset kind: `{result.dataset_kind}`",
        f"- Rows: `{len(frame)}`",
        f"- Cycles: `{cycle_count if cycle_count is not None else 'n/a'}`",
        f"- Target schema: `{result.target_schema}`",
        "",
        f"### {result.field_summary_label}",
        "- " + ", ".join(canonical_columns),
    ]
    if result.preview_only:
        ui_lines.extend(["", "### Preview Scope",
            "- Parsed from an attachment preview or truncated upload, "
            "so the result is informational rather than a full ingest."])
    if missing_optional:
        ui_lines.extend(["", "### Missing Optional Fields", "- " + ", ".join(missing_optional)])
    if result.warnings:
        ui_lines.extend(["", "### Warnings", *[f"- {w}" for w in result.warnings]])

    dataset_file_kind = "parsed_cycler_preview" if result.preview_only else "parsed_cycler_dataset"
    dataset_file_stem = "preview" if result.preview_only else "normalized"
    dataset_display_name = (
        f"{display_label}.csv" if result.preview_only
        else f"{result.adapter_vendor} normalized dataset.csv"
    )

    return {
        "status": "ok",
        "source_file": result.source_name,
        "source_kind": "thread_upload" if result.source_name.startswith("/uploads/") else "local_file",
        "adapter_id": result.adapter_id,
        "adapter_vendor": result.adapter_vendor,
        "target_schema": result.target_schema,
        "dataset_kind": result.dataset_kind,
        "field_summary_label": result.field_summary_label,
        "preview_only": result.preview_only,
        "auto_detected": result.auto_detected,
        "detected_from": result.detected_from,
        "row_count": int(len(frame)),
        "cycle_count": cycle_count,
        "canonical_columns": canonical_columns,
        "required_fields": required_fields,
        "missing_required_fields": missing_required,
        "missing_optional_fields": missing_optional,
        "raw_columns_detected": result.raw_columns,
        "warnings": result.warnings,
        "preview_rows": preview,
        "ui_markdown": "\n".join(ui_lines),
        "generated_files": [
            {
                "path": f"/parsed/{source_slug}-summary.md",
                "content": "\n".join(ui_lines),
                "generated_file_kind": "parsed_cycler_summary",
                "display_name": f"{display_label} summary",
            },
            {
                "path": f"/parsed/{source_slug}-{dataset_file_stem}.csv",
                "content": dataset_csv,
                "generated_file_kind": dataset_file_kind,
                "display_name": dataset_display_name,
            },
        ],
    }


def _json_dumps(payload: dict[str, Any]) -> str:
    def sanitize(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    return json.dumps(sanitize(payload), indent=2, ensure_ascii=True)


def _safe_json_loads(payload: str) -> dict[str, Any]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"raw_text": payload}


def _parse_json_object(payload: str | None, *, field_name: str) -> dict[str, Any]:
    if payload is None or not str(payload).strip():
        return {}

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} is not valid JSON: {exc.msg}.") from exc

    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must decode to a JSON object.")
    return parsed


def _parse_json_string_list(payload: str | None, *, field_name: str) -> list[str]:
    if payload is None or not str(payload).strip():
        return []

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} is not valid JSON: {exc.msg}.") from exc

    if not isinstance(parsed, list):
        raise ValueError(f"{field_name} must decode to a JSON array.")
    return [str(item).strip() for item in parsed if str(item).strip()]


def _parse_method_inputs_json(payload: str | None) -> dict[str, Any]:
    return _parse_json_object(payload, field_name="method_inputs_json")


def _runtime_state_mapping(runtime: ToolRuntime | None) -> dict[str, Any]:
    if runtime is None:
        return {}

    state = getattr(runtime, "state", None)
    if isinstance(state, dict):
        return state

    if state is None:
        return {}

    values = getattr(state, "values", None)
    if isinstance(values, dict):
        return values

    state_dict = getattr(state, "__dict__", None)
    if isinstance(state_dict, dict):
        return state_dict

    return {}


def _display_repo_root() -> str:
    return "repo_root"


def _rule_reference_identifier(rule: dict[str, Any]) -> str | None:
    identifier = (
        str(rule.get("source_asset_id") or "").strip()
        or str(rule.get("id") or "").strip()
    )
    return identifier or None


_THERMAL_CHAMBER_REQUIRED_PLANNING_KEYS = {
    "cycle_life",
    "calendar_ageing",
    "calendar_ageing_test",
    "ageing_drive_cycle",
    "constant_voltage_ageing",
    "drive_cycle",
    "drive_cycle_test",
    "thermal_characterisation",
    "thermal_impedance_test",
    "quasi_static_thermal_tests",
}

_DEFAULT_THERMAL_CHAMBER_SOURCES = {
    "settings_lab_defaults",
    "pretest_guidance_default",
}


def _normalize_default_thermal_chamber_usage(
    *,
    planning_key: str | None,
    target_temperature_c: float,
    explicit_thermal_chamber: str | None,
    resolved_thermal_chamber: str | None,
    lab_default_context: dict[str, Any],
) -> tuple[str | None, dict[str, Any], str | None]:
    if normalize_optional_text(explicit_thermal_chamber) is not None:
        return resolved_thermal_chamber, lab_default_context, None

    if resolved_thermal_chamber is None:
        return None, lab_default_context, None

    applied_fields = lab_default_context.get("applied_fields", {})
    thermal_chamber_source = applied_fields.get("thermal_chamber")
    if thermal_chamber_source not in _DEFAULT_THERMAL_CHAMBER_SOURCES:
        return resolved_thermal_chamber, lab_default_context, None

    key_candidates = {
        normalize_optional_text(planning_key),
        normalize_objective_key(planning_key) if planning_key else None,
    }
    if any(candidate in _THERMAL_CHAMBER_REQUIRED_PLANNING_KEYS for candidate in key_candidates):
        return resolved_thermal_chamber, lab_default_context, None

    if target_temperature_c < 20.0 or target_temperature_c > 30.0:
        return resolved_thermal_chamber, lab_default_context, None

    updated_context = dict(lab_default_context)
    updated_applied_fields = dict(applied_fields)
    updated_applied_fields.pop("thermal_chamber", None)
    updated_available_fields = dict(updated_context.get("available_fields", {}))
    updated_available_fields["thermal_chamber"] = f"{thermal_chamber_source}_available"
    updated_context["applied_fields"] = updated_applied_fields
    updated_context["available_fields"] = updated_available_fields

    default_label = (
        updated_context.get("lab_defaults", {}).get("default_thermal_chamber_label")
        or updated_context.get("lab_defaults", {}).get("default_thermal_chamber_id")
        or resolved_thermal_chamber
    )
    note_prefix = (
        "Settings default thermal chamber"
        if thermal_chamber_source == "settings_lab_defaults"
        else "Approved default thermal chamber"
    )
    note = (
        f"{note_prefix} available but not applied as a hard constraint "
        f"for this ambient-compatible plan: `{default_label}`."
    )
    return None, updated_context, note


def _resolve_planning_defaults_from_runtime(
    *,
    instrument: str | None,
    thermal_chamber: str | None,
    runtime: ToolRuntime | None,
) -> tuple[str | None, str | None, dict[str, Any]]:
    state = _runtime_state_mapping(runtime)
    thread_files = (
        state.get("files", {})
        if isinstance(state.get("files", {}), dict)
        else {}
    )
    top_level_lab_defaults = (
        state.get("labDefaults", {})
        if isinstance(state.get("labDefaults", {}), dict)
        else {}
    )
    ui_state = state.get("ui", {}) if isinstance(state.get("ui", {}), dict) else {}
    nested_lab_defaults = (
        ui_state.get("labDefaults", {})
        if isinstance(ui_state.get("labDefaults", {}), dict)
        else {}
    )
    hidden_file_lab_defaults: dict[str, Any] = {}
    if not top_level_lab_defaults and not nested_lab_defaults and runtime is not None:
        try:
            _, hidden_defaults_text = _load_uploaded_thread_file(
                "/context/lab-defaults.json",
                thread_files,
                runtime,
            )
            hidden_defaults_payload = _parse_json_object(
                hidden_defaults_text,
                field_name="lab_defaults_thread_file",
            )
            hidden_candidate = hidden_defaults_payload.get("labDefaults")
            if isinstance(hidden_candidate, dict):
                hidden_file_lab_defaults = hidden_candidate
            elif isinstance(hidden_defaults_payload, dict):
                hidden_file_lab_defaults = hidden_defaults_payload
        except Exception:
            hidden_file_lab_defaults = {}

    lab_defaults = top_level_lab_defaults or nested_lab_defaults or hidden_file_lab_defaults
    kb_defaults = get_pretest_approved_equipment_defaults()

    resolved_instrument = normalize_optional_text(instrument)
    resolved_thermal_chamber = normalize_optional_text(thermal_chamber)

    default_instrument_id = normalize_optional_text(lab_defaults.get("defaultInstrumentId")) or normalize_optional_text(
        kb_defaults.get("default_cycler_id")
    )
    default_instrument_label = normalize_optional_text(lab_defaults.get("defaultInstrumentLabel")) or normalize_optional_text(
        kb_defaults.get("default_cycler_label")
    )
    if default_instrument_label is None and default_instrument_id is not None:
        try:
            default_instrument_label = str(get_equipment_rule(default_instrument_id).get("label") or "").strip() or None
        except KeyError:
            default_instrument_label = None

    default_thermal_chamber_id = normalize_optional_text(lab_defaults.get("defaultThermalChamberId")) or normalize_optional_text(
        kb_defaults.get("default_thermal_chamber_id")
    )
    default_thermal_chamber_label = normalize_optional_text(
        lab_defaults.get("defaultThermalChamberLabel")
    ) or normalize_optional_text(kb_defaults.get("default_thermal_chamber_label"))
    if default_thermal_chamber_label is None and default_thermal_chamber_id is not None:
        try:
            default_thermal_chamber_label = (
                str(get_thermal_chamber_rule(default_thermal_chamber_id).get("label") or "").strip()
                or None
            )
        except KeyError:
            default_thermal_chamber_label = None

    applied_fields: dict[str, str] = {}
    if resolved_instrument is None:
        if default_instrument_id is not None:
            resolved_instrument = default_instrument_id
            applied_fields["instrument"] = (
                "settings_lab_defaults"
                if normalize_optional_text(lab_defaults.get("defaultInstrumentId")) is not None
                else "pretest_guidance_default"
            )

    if resolved_thermal_chamber is None:
        if default_thermal_chamber_id is not None:
            resolved_thermal_chamber = default_thermal_chamber_id
            applied_fields["thermal_chamber"] = (
                "settings_lab_defaults"
                if normalize_optional_text(lab_defaults.get("defaultThermalChamberId")) is not None
                else "pretest_guidance_default"
            )

    default_eis_instrument_id = normalize_optional_text(
        lab_defaults.get("defaultEisInstrumentId")
    ) or normalize_optional_text(kb_defaults.get("default_eis_instrument_id"))
    default_eis_instrument_label = normalize_optional_text(
        lab_defaults.get("defaultEisInstrumentLabel")
    ) or normalize_optional_text(kb_defaults.get("default_eis_instrument_label"))
    default_eis_setup_notes = normalize_optional_text(
        lab_defaults.get("defaultEisSetupNotes")
    )
    if default_eis_setup_notes is None and default_eis_instrument_id is None:
        default_eis_setup_notes = default_eis_instrument_label

    context = {
        "source": (
            "thread_ui_lab_defaults"
            if top_level_lab_defaults or nested_lab_defaults
            else "thread_file_lab_defaults"
            if hidden_file_lab_defaults
            else "pretest_guidance_default"
        ),
        "applied_fields": applied_fields,
        "available_fields": {},
        "lab_defaults": {
            "default_instrument_id": default_instrument_id,
            "default_instrument_label": default_instrument_label,
            "default_thermal_chamber_id": default_thermal_chamber_id,
            "default_thermal_chamber_label": default_thermal_chamber_label,
            "default_eis_instrument_id": default_eis_instrument_id,
            "default_eis_instrument_label": default_eis_instrument_label,
            "default_eis_setup_notes": default_eis_setup_notes,
        },
    }
    return resolved_instrument, resolved_thermal_chamber, context


def _build_effective_pretest_equipment_defaults(
    lab_default_context: dict[str, Any] | None,
) -> dict[str, Any]:
    kb_defaults = get_pretest_approved_equipment_defaults()
    context_defaults = (
        dict((lab_default_context or {}).get("lab_defaults", {}))
        if isinstance((lab_default_context or {}).get("lab_defaults", {}), dict)
        else {}
    )
    return {
        "default_cycler_id": normalize_optional_text(context_defaults.get("default_instrument_id"))
        or normalize_optional_text(kb_defaults.get("default_cycler_id")),
        "default_cycler_label": normalize_optional_text(context_defaults.get("default_instrument_label"))
        or normalize_optional_text(kb_defaults.get("default_cycler_label")),
        "default_thermal_chamber_id": normalize_optional_text(
            context_defaults.get("default_thermal_chamber_id")
        )
        or normalize_optional_text(kb_defaults.get("default_thermal_chamber_id")),
        "default_thermal_chamber_label": normalize_optional_text(
            context_defaults.get("default_thermal_chamber_label")
        )
        or normalize_optional_text(kb_defaults.get("default_thermal_chamber_label")),
        "default_eis_instrument_id": normalize_optional_text(
            context_defaults.get("default_eis_instrument_id")
        )
        or normalize_optional_text(kb_defaults.get("default_eis_instrument_id")),
        "default_eis_instrument_label": normalize_optional_text(
            context_defaults.get("default_eis_instrument_label")
        )
        or normalize_optional_text(kb_defaults.get("default_eis_instrument_label")),
    }


def _mark_default_thermal_chamber_as_available_context(
    lab_default_context: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    applied_fields = dict(lab_default_context.get("applied_fields", {}))
    thermal_chamber_source = applied_fields.get("thermal_chamber")
    if thermal_chamber_source not in _DEFAULT_THERMAL_CHAMBER_SOURCES:
        return lab_default_context, None

    updated_context = dict(lab_default_context)
    applied_fields.pop("thermal_chamber", None)
    available_fields = dict(updated_context.get("available_fields", {}))
    available_fields["thermal_chamber"] = f"{thermal_chamber_source}_available"
    updated_context["applied_fields"] = applied_fields
    updated_context["available_fields"] = available_fields

    default_label = (
        updated_context.get("lab_defaults", {}).get("default_thermal_chamber_label")
        or updated_context.get("lab_defaults", {}).get("default_thermal_chamber_id")
    )
    note_prefix = (
        "Settings default thermal chamber"
        if thermal_chamber_source == "settings_lab_defaults"
        else "Approved default thermal chamber"
    )
    note = (
        f"{note_prefix} retained as available context until a specific "
        f"test temperature or method requires it: `{default_label}`."
        if default_label
        else None
    )
    return updated_context, note


def _normalize_thread_file_path(file_path: str) -> str:
    normalized = str(file_path or "").strip().replace("\\", "/")
    if not normalized:
        return "/"
    return normalized if normalized.startswith("/") else f"/{normalized}"


_UPLOAD_PATH_PATTERN = re.compile(r"(/uploads/[^\s`)\]]+)")


def _extract_message_text_fragments(message: Any) -> list[str]:
    if isinstance(message, str):
        return [message]
    if isinstance(message, dict):
        fragments: list[str] = []
        content = message.get("content")
        if isinstance(content, str):
            fragments.append(content)
        elif isinstance(content, list):
            for block in content:
                fragments.extend(_extract_message_text_fragments(block))
        text = message.get("text")
        if isinstance(text, str):
            fragments.append(text)
        for key in ("artifact", "raw"):
            value = message.get(key)
            if isinstance(value, str):
                fragments.append(value)
        return fragments

    content = getattr(message, "content", None)
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        fragments: list[str] = []
        for block in content:
            fragments.extend(_extract_message_text_fragments(block))
        return fragments

    text = getattr(message, "text", None)
    if isinstance(text, str):
        return [text]
    return []

def _iter_recent_upload_paths_from_runtime(runtime: ToolRuntime | None) -> list[str]:
    state = _runtime_state_mapping(runtime)
    messages = state.get("messages", [])
    if not isinstance(messages, list):
        return []

    discovered: list[str] = []
    seen: set[str] = set()
    for message in reversed(messages):
        for fragment in _extract_message_text_fragments(message):
            for match in _UPLOAD_PATH_PATTERN.findall(fragment):
                normalized_path = _normalize_thread_file_path(match)
                if normalized_path in seen:
                    continue
                seen.add(normalized_path)
                discovered.append(normalized_path)
    return discovered


def _resolve_uploaded_datasheet_selected_cell_record(
    runtime: ToolRuntime | None,
) -> dict[str, Any] | None:
    for upload_path in _iter_recent_upload_paths_from_runtime(runtime):
        try:
            normalized_path, attachment_text = _load_uploaded_thread_file(
                upload_path,
                None,
                runtime,
            )
            extraction_payload = extract_cell_datasheet_candidate_from_text(
                attachment_text,
                thread_file_path=normalized_path,
            )
        except Exception:
            continue

        candidate = extraction_payload.get("candidate")
        transient_record = build_transient_selected_cell_record(
            candidate,
            thread_file_path=normalized_path,
        )
        if transient_record is not None:
            return transient_record

    return None


def _resolve_selected_cell_context(
    *,
    selected_cell_id: str | None,
    runtime: ToolRuntime | None,
    transient_selected_cell_override: dict[str, Any] | None = None,
) -> tuple[str | None, dict[str, Any] | None]:
    normalized_id = normalize_optional_text(selected_cell_id)
    if transient_selected_cell_override is not None:
        return normalized_id, copy.deepcopy(transient_selected_cell_override)

    transient_selected_cell_record: dict[str, Any] | None = None

    if normalized_id is None:
        transient_selected_cell_record = _resolve_uploaded_datasheet_selected_cell_record(runtime)
        return None, transient_selected_cell_record

    if normalized_id.startswith("uploaded_"):
        transient_selected_cell_record = _resolve_uploaded_datasheet_selected_cell_record(runtime)
        if transient_selected_cell_record is not None:
            return None, transient_selected_cell_record

    return normalized_id, None


def _await_parameter_request_answers(
    parameter_request: dict[str, Any] | None,
    runtime: ToolRuntime | None,
) -> dict[str, Any] | None:
    if parameter_request is None or runtime is None:
        return None

    try:
        resume_value = langgraph_interrupt({"parameter_request": parameter_request})
    except RuntimeError:
        return None

    if not isinstance(resume_value, dict):
        return None

    response_payload = (
        resume_value.get("parameter_request_response")
        if isinstance(resume_value.get("parameter_request_response"), dict)
        else resume_value
    )
    if not isinstance(response_payload, dict):
        return None

    request_id = parameter_request.get("request_id")
    response_request_id = response_payload.get("request_id")
    if (
        isinstance(request_id, str)
        and isinstance(response_request_id, str)
        and response_request_id != request_id
    ):
        return None

    answers = response_payload.get("answers")
    if not isinstance(answers, dict):
        return None

    normalized_answers: dict[str, Any] = {}
    for key, value in answers.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, str):
            normalized_value = normalize_optional_text(value)
            if normalized_value is None:
                continue
            normalized_answers[key] = normalized_value
            continue
        if value is None:
            continue
        normalized_answers[key] = value

    return normalized_answers or None


def _merge_parameter_answers(
    *,
    chemistry: str | None,
    selected_cell_id: str | None,
    instrument: str | None,
    thermal_chamber: str | None,
    method_inputs: dict[str, Any] | None,
    transient_selected_cell_record: dict[str, Any] | None,
    answers: dict[str, Any],
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    dict[str, Any],
    dict[str, Any] | None,
]:
    next_chemistry = chemistry
    next_selected_cell_id = selected_cell_id
    next_instrument = instrument
    next_thermal_chamber = thermal_chamber
    next_method_inputs = dict(method_inputs or {})
    next_transient_selected_cell_record = (
        copy.deepcopy(transient_selected_cell_record)
        if transient_selected_cell_record is not None
        else None
    )

    subject_value = normalize_optional_text(
        str(answers.get("chemistry_or_selected_cell") or "")
    )
    if subject_value is not None:
        try:
            get_cell_catalog_record(subject_value)
        except KeyError:
            next_chemistry = subject_value
        else:
            next_selected_cell_id = subject_value
            if chemistry is None:
                next_chemistry = None

    instrument_value = normalize_optional_text(str(answers.get("instrument") or ""))
    if instrument_value is not None:
        next_instrument = instrument_value

    thermal_chamber_value = normalize_optional_text(
        str(answers.get("thermal_chamber") or "")
    )
    if thermal_chamber_value is not None:
        next_thermal_chamber = thermal_chamber_value

    discharge_allowance = answers.get("max_continuous_discharge_current_a")
    if discharge_allowance is not None:
        if next_transient_selected_cell_record is None and next_selected_cell_id is not None:
            try:
                next_transient_selected_cell_record = copy.deepcopy(
                    load_selected_cell_record(next_selected_cell_id)
                )
            except Exception:
                next_transient_selected_cell_record = None
        if next_transient_selected_cell_record is not None:
            currents = dict(next_transient_selected_cell_record.get("currents", {}))
            currents["max_continuous_discharge_current_a"] = discharge_allowance
            next_transient_selected_cell_record["currents"] = currents

    reserved_keys = {
        "chemistry_or_selected_cell",
        "instrument",
        "thermal_chamber",
        "max_continuous_discharge_current_a",
    }
    for key, value in answers.items():
        if key in reserved_keys or value is None:
            continue
        next_method_inputs[key] = value

    return (
        next_chemistry,
        next_selected_cell_id,
        next_instrument,
        next_thermal_chamber,
        next_method_inputs,
        next_transient_selected_cell_record,
    )


def _thread_file_value_to_text(file_value: Any) -> str:
    if isinstance(file_value, str):
        return file_value
    if not isinstance(file_value, dict):
        return ""

    raw_content = file_value.get("content")
    if isinstance(raw_content, list):
        return "\n".join(str(line or "") for line in raw_content)
    if isinstance(raw_content, str):
        return raw_content
    return ""


def _runtime_thread_files(runtime: ToolRuntime | None) -> dict[str, Any]:
    state = _runtime_state_mapping(runtime)
    files = state.get("files", {})
    return files if isinstance(files, dict) else {}


def _uploaded_path_tail(file_path: str) -> str:
    normalized_path = _normalize_thread_file_path(file_path)
    basename = Path(normalized_path).name
    if "-" not in basename:
        return basename
    _prefix, tail = basename.split("-", 1)
    return tail or basename


def _thread_file_original_filename(file_value: Any) -> str | None:
    if not isinstance(file_value, dict):
        return None
    original_filename = file_value.get("original_filename")
    if not isinstance(original_filename, str):
        return None
    normalized = original_filename.strip()
    return normalized or None


def _resolve_uploaded_thread_file_alias(
    normalized_path: str,
    files: dict[str, Any],
) -> tuple[str, Any] | None:
    requested_tail = _uploaded_path_tail(normalized_path)
    requested_basename = Path(normalized_path).name

    tail_matches: list[tuple[str, Any]] = []
    basename_matches: list[tuple[str, Any]] = []
    original_name_matches: list[tuple[str, Any]] = []

    for existing_path, file_value in files.items():
        normalized_existing_path = _normalize_thread_file_path(existing_path)
        if not normalized_existing_path.startswith("/uploads/"):
            continue

        if Path(normalized_existing_path).name == requested_basename:
            basename_matches.append((normalized_existing_path, file_value))

        if _uploaded_path_tail(normalized_existing_path) == requested_tail:
            tail_matches.append((normalized_existing_path, file_value))

        original_filename = _thread_file_original_filename(file_value)
        if original_filename and (
            original_filename == requested_tail
            or f"{original_filename}.txt" == requested_tail
            or requested_tail == Path(original_filename).name
            or requested_tail == f"{Path(original_filename).name}.txt"
        ):
            original_name_matches.append((normalized_existing_path, file_value))

    for matches in (basename_matches, tail_matches, original_name_matches):
        if len(matches) == 1:
            return matches[0]

    return None


def _recent_uploaded_thread_paths(files: dict[str, Any], *, limit: int = 3) -> list[str]:
    recent_paths: list[tuple[str, str]] = []
    for existing_path, file_value in files.items():
        normalized_existing_path = _normalize_thread_file_path(existing_path)
        if not normalized_existing_path.startswith("/uploads/"):
            continue

        modified_at = ""
        if isinstance(file_value, dict):
            raw_modified_at = file_value.get("modified_at")
            if isinstance(raw_modified_at, str):
                modified_at = raw_modified_at
        recent_paths.append((modified_at, normalized_existing_path))

    recent_paths.sort(key=lambda item: item[0], reverse=True)
    return [path for _modified_at, path in recent_paths[:limit]]


def _load_uploaded_thread_file(
    file_path: str,
    thread_files: dict[str, Any] | None,
    runtime: ToolRuntime | None = None,
) -> tuple[str, str]:
    normalized_path = _normalize_thread_file_path(file_path)
    if runtime is not None:
        try:
            responses = StateBackend(runtime).download_files([normalized_path])
        except Exception:
            responses = []
        if responses:
            response = responses[0]
            if response.content is not None:
                content = response.content.decode("utf-8", errors="replace")
                if not content.strip():
                    raise ValueError(
                        f"The uploaded thread file `{normalized_path}` exists, but its extracted text content is empty."
                    )
                return normalized_path, content

    files = thread_files if isinstance(thread_files, dict) else _runtime_thread_files(runtime)

    for existing_path, file_value in files.items():
        if _normalize_thread_file_path(existing_path) != normalized_path:
            continue
        content = _thread_file_value_to_text(file_value)
        if not content.strip():
            raise ValueError(
                f"The uploaded thread file `{normalized_path}` exists, but its extracted text content is empty."
            )
        return normalized_path, content

    alias_match = _resolve_uploaded_thread_file_alias(normalized_path, files)
    if alias_match is not None:
        matched_path, file_value = alias_match
        content = _thread_file_value_to_text(file_value)
        if not content.strip():
            raise ValueError(
                f"The uploaded thread file `{matched_path}` exists, but its extracted text content is empty."
            )
        return matched_path, content

    recent_paths = _recent_uploaded_thread_paths(files)
    if recent_paths:
        raise KeyError(
            "Unknown uploaded thread file: "
            f"{normalized_path}. Available uploads in the current thread include: "
            + ", ".join(recent_paths)
        )

    raise KeyError(f"Unknown uploaded thread file: {normalized_path}")


def _tool_error(
    message: str,
    *,
    error_type: str,
    suggestions: list[str] | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "status": "error",
        "error_type": error_type,
        "message": message,
    }
    if suggestions:
        payload["suggestions"] = suggestions
    if extra_payload:
        payload.update(extra_payload)
    return _json_dumps(payload)


def _normalize_modeling_column_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _match_requested_column(columns: list[str], requested: str | None) -> str | None:
    normalized_requested = _normalize_modeling_column_name(requested)
    if not normalized_requested:
        return None

    for column in columns:
        if column == requested:
            return column
        if _normalize_modeling_column_name(column) == normalized_requested:
            return column
    return None


def _selected_cell_voltage_window(
    selected_cell_record: dict[str, Any] | None,
) -> tuple[float | None, float | None, str | None]:
    if not isinstance(selected_cell_record, dict):
        return None, None, None

    electrical = selected_cell_record.get("electrical", {})
    if not isinstance(electrical, dict):
        return None, None, None

    charge_voltage_v = electrical.get("charge_voltage_v")
    discharge_cutoff_v = electrical.get("discharge_cutoff_v")
    if charge_voltage_v is None or discharge_cutoff_v is None:
        return None, None, None

    source_kind = str(selected_cell_record.get("source_kind") or "selected_cell_imported_metadata")
    source_label = (
        "uploaded_cell_datasheet_candidate"
        if source_kind == "uploaded_cell_datasheet_candidate"
        else "selected_cell_imported_metadata"
    )
    return float(charge_voltage_v), float(discharge_cutoff_v), source_label


def _build_blocked_modeling_markdown(
    *,
    title: str,
    known_context: list[tuple[str, Any]],
    missing_inputs: list[str],
    notes: list[str] | None = None,
) -> str:
    lines = [f"## {title}", "", "### Known Context"]
    if known_context:
        lines.extend(
            f"- {label}: `{value}`" if value not in (None, "") else f"- {label}: missing"
            for label, value in known_context
        )
    else:
        lines.append("- None yet.")

    lines.extend(["", "### Inputs Needed"])
    lines.extend(f"- {item}" for item in missing_inputs)

    if notes:
        lines.extend(["", "### Notes"])
        lines.extend(f"- {item}" for item in notes if str(item).strip())

    return "\n".join(lines)


def _resolve_local_or_sample_path(file_path: str) -> Path:
    try:
        return resolve_sample_path(file_path)
    except FileNotFoundError:
        local_candidate = Path(file_path)
        if local_candidate.exists():
            return local_candidate.resolve()
        raise


def _read_flexible_tabular_frame(
    *,
    source_name: str,
    source_text: str | None,
    resolved_path: Path | None,
) -> pd.DataFrame:
    if source_text is not None:
        return pd.read_csv(io.StringIO(source_text), sep=None, engine="python")

    if resolved_path is None:
        raise ValueError(f"No tabular source is available for `{source_name}`.")

    suffix = resolved_path.suffix.lower()
    if suffix in {".csv", ".tsv", ".txt"}:
        return pd.read_csv(resolved_path, sep=None, engine="python")
    if suffix in {".xls", ".xlsx"}:
        workbook = pd.read_excel(resolved_path, sheet_name=None)
        sheets = [
            frame
            for sheet_name, frame in workbook.items()
            if str(sheet_name).strip().lower() not in {"info", "metadata"}
        ]
        if not sheets:
            raise ValueError(f"No visible sheets were found in `{resolved_path}`.")
        return pd.concat(sheets, ignore_index=True)
    raise ValueError(f"Unsupported fallback tabular format `{suffix or 'unknown'}`.")


def _preview_table_rows(frame: pd.DataFrame, *, row_count: int = 5) -> list[dict[str, Any]]:
    preview = frame.head(max(row_count, 1)).where(pd.notna(frame.head(max(row_count, 1))), None)
    records = preview.to_dict(orient="records")
    return [
        {key: _format_preview_value(value) for key, value in row.items()}
        for row in records
    ]


def _apply_modeling_column_mapping(
    raw_frame: pd.DataFrame,
    *,
    time_column: str | None,
    current_column: str | None,
    voltage_column: str | None,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    working = raw_frame.copy()
    working.columns = [str(column) for column in working.columns]
    available_columns = list(working.columns)

    alias_candidates = {
        "test_time_s": [
            "test_time_s",
            "test_time",
            "elapsed_time_s",
            "elapsed_time",
            "time_s",
            "time_sec",
            "seconds",
            "time",
        ],
        "current_a": [
            "current_a",
            "current",
            "current_amp",
            "current_amps",
            "amps",
            "i",
        ],
        "voltage_v": [
            "voltage_v",
            "voltage",
            "terminal_voltage_v",
            "cell_voltage_v",
            "volts",
            "u",
            "v",
        ],
        "cycle_index": ["cycle_index", "cycle", "cycle_id"],
        "step_index": ["step_index", "step", "step_id"],
    }

    requested_mapping = {
        "test_time_s": time_column,
        "current_a": current_column,
        "voltage_v": voltage_column,
    }
    rename_map: dict[str, str] = {}
    mapping_used: dict[str, str] = {}

    for canonical_name in ("test_time_s", "current_a", "voltage_v", "cycle_index", "step_index"):
        if canonical_name in available_columns:
            mapping_used[canonical_name] = canonical_name
            continue

        actual_column = None
        if canonical_name in requested_mapping:
            actual_column = _match_requested_column(
                available_columns,
                requested_mapping.get(canonical_name),
            )

        if actual_column is None:
            for alias in alias_candidates.get(canonical_name, []):
                actual_column = _match_requested_column(available_columns, alias)
                if actual_column is not None:
                    break

        if actual_column is not None:
            rename_map[actual_column] = canonical_name
            mapping_used[canonical_name] = actual_column

    if rename_map:
        working = working.rename(columns=rename_map)
        working = working.loc[:, ~working.columns.duplicated()].copy()

    missing_mapping_fields = [
        field_name
        for canonical_name, field_name in (
            ("test_time_s", "time_column"),
            ("current_a", "current_column"),
            ("voltage_v", "voltage_column"),
        )
        if canonical_name not in working.columns
    ]

    if missing_mapping_fields:
        return working, mapping_used, missing_mapping_fields

    for column in ("test_time_s", "current_a", "voltage_v"):
        working[column] = pd.to_numeric(working[column], errors="coerce")

    if "cycle_index" not in working.columns:
        working["cycle_index"] = 1
    else:
        working["cycle_index"] = pd.to_numeric(
            working["cycle_index"],
            errors="coerce",
        ).astype("Int64")

    if "step_index" in working.columns:
        working["step_index"] = pd.to_numeric(
            working["step_index"],
            errors="coerce",
        ).astype("Int64")

    working = working.dropna(subset=["test_time_s", "current_a", "voltage_v"]).copy()
    if "step_index" not in working.columns:
        working["step_index"] = pd.Series([pd.NA] * len(working), dtype="Int64")
    working = working.sort_values(["test_time_s"], kind="stable").reset_index(drop=True)
    return working, mapping_used, []


def _load_modeling_frame(
    *,
    file_path: str,
    attachment_text: str | None,
    adapter_id: str | None,
    runtime: ToolRuntime | None,
    time_column: str | None = None,
    current_column: str | None = None,
    voltage_column: str | None = None,
) -> dict[str, Any]:
    normalized_path = _normalize_thread_file_path(file_path)
    source_name = normalized_path
    source_text: str | None = None
    resolved_path: Path | None = None

    if attachment_text is not None and str(attachment_text).strip():
        source_text = str(attachment_text)
    elif normalized_path.startswith("/uploads/"):
        source_name, source_text = _load_uploaded_thread_file(
            normalized_path,
            None,
            runtime,
        )
    else:
        resolved_path = _resolve_local_or_sample_path(file_path)
        source_name = str(resolved_path)

    try:
        if source_text is not None:
            parse_result = parse_raw_export_text(
                source_text,
                source_name=source_name,
                adapter_id=adapter_id,
            )
        else:
            parse_result = parse_raw_export_file(
                resolved_path,
                adapter_id=adapter_id,
            )
    except (FileNotFoundError, KeyError, UnknownAdapterError):
        raise
    except (AdapterDetectionError, AdapterReadError, AdapterSchemaError, ValueError) as exc:
        if adapter_id is not None:
            raise

        raw_frame = _read_flexible_tabular_frame(
            source_name=source_name,
            source_text=source_text,
            resolved_path=resolved_path,
        )
        mapped_frame, mapping_used, missing_mapping_fields = _apply_modeling_column_mapping(
            raw_frame,
            time_column=time_column,
            current_column=current_column,
            voltage_column=voltage_column,
        )
        if missing_mapping_fields:
            return {
                "status": "needs_columns",
                "source_name": source_name,
                "raw_columns": [str(column) for column in raw_frame.columns],
                "preview_rows": _preview_table_rows(raw_frame),
                "missing_mapping_fields": missing_mapping_fields,
                "parse_error": str(exc),
            }

        return {
            "status": "ok",
            "frame": mapped_frame,
            "source_name": source_name,
            "frame_origin": "manual_column_mapping",
            "mapping_used": mapping_used,
            "raw_columns": [str(column) for column in raw_frame.columns],
            "preview_rows": _preview_table_rows(raw_frame),
            "parse_error": str(exc),
        }

    payload = _adapter_result_to_payload(parse_result, preview_rows=5)
    return {
        "status": "ok",
        "frame": parse_result.frame,
        "source_name": parse_result.source_name,
        "frame_origin": "adapter_normalized",
        "adapter_payload": payload,
        "mapping_used": {},
        "raw_columns": list(parse_result.raw_columns),
        "preview_rows": payload.get("preview_rows", []),
    }


def _generated_file(
    *,
    path: str,
    content: str,
    generated_file_kind: str,
    display_name: str,
) -> dict[str, str]:
    return {
        "path": path,
        "content": content,
        "generated_file_kind": generated_file_kind,
        "display_name": display_name,
    }


def _build_planning_response_policy(
    *,
    planning_mode: str,
    allow_step_level_protocol: bool,
    allow_generic_placeholders: bool,
    must_request_missing_inputs: bool,
    references_section_required: bool = False,
) -> dict[str, Any]:
    return {
        "planning_mode": planning_mode,
        "allow_step_level_protocol": allow_step_level_protocol,
        "allow_generic_placeholders": allow_generic_placeholders,
        "must_request_missing_inputs": must_request_missing_inputs,
        "must_state_blockers_before_release": True,
        "must_use_numeric_citations": references_section_required,
        "references_section_required": references_section_required,
        "citation_style": "numeric_brackets",
        "must_preserve_relation_class_semantics": True,
        "must_apply_authority_and_precedence": True,
        "must_preserve_requirement_strength": True,
        "must_keep_review_and_release_semantics_explicit": True,
    }


def _build_controlled_planning_state(
    *,
    status: str,
    planning_mode: str,
    blocking_reason: str | None = None,
    missing_inputs: list[str] | None = None,
    satisfied_by: list[str] | None = None,
    recommended_sources: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": status,
        "planning_mode": planning_mode,
        "must_call_controlled_source_before_step_guidance": True,
    }
    if blocking_reason:
        payload["blocking_reason"] = blocking_reason
    if missing_inputs:
        payload["missing_inputs"] = missing_inputs
    if satisfied_by:
        payload["satisfied_by"] = satisfied_by
    if recommended_sources:
        payload["recommended_sources"] = recommended_sources
    return payload


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "- None."

    def humanize_header(value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return "Item"
        mapping = {
            "source_type": "Source",
            "lock_status": "Status",
            "reference_type": "Reference type",
            "value/status": "Value / status",
            "next_action": "Next action",
        }
        lowered = normalized.lower()
        if lowered in mapping:
            return mapping[lowered]
        if "_" in normalized:
            tokens = normalized.replace("_", " ").split()
            upper_tokens = {"soc", "dcr", "dcir", "rpt", "eol", "cv", "cc"}
            return " ".join(
                token.upper() if token.lower() in upper_tokens else token.capitalize()
                for token in tokens
            )
        return normalized

    def humanize_token(value: Any) -> str:
        text = str(value or "").strip()
        mapping = {
            "user_supplied": "User-supplied",
            "public": "Public",
            "built_in_guidance": "Built-in guidance",
            "uploaded_cell_datasheet_candidate": "Uploaded cell datasheet",
            "fixed": "Fixed",
            "blocked": "Blocked",
            "review_required": "Review required",
            "execution_blocker": "Execution blocker",
            "review_gate": "Review gate",
            "safety_boundary": "Safety boundary",
            "method_core": "Method core",
            "project_choice": "Project choice",
            "statistics_key": "Statistics key",
        }
        return mapping.get(text, text)

    def render(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, bool):
            return "yes" if value else "no"
        text = str(value).replace("\r\n", " ").replace("\n", " ").strip()
        return text.replace("|", "\\|") if text else "n/a"

    normalized_headers = [str(header).strip() for header in headers]
    header_line = "| " + " | ".join(humanize_header(header) for header in normalized_headers) + " |"
    separator_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines: list[str] = []
    for row in rows:
        rendered_cells: list[str] = []
        for index, cell in enumerate(row):
            header = normalized_headers[index] if index < len(normalized_headers) else ""
            if header in {"source_type", "lock_status", "type", "severity", "reference_type"}:
                rendered_cells.append(render(humanize_token(cell)))
            else:
                rendered_cells.append(render(cell))
        body_lines.append("| " + " | ".join(rendered_cells) + " |")
    return "\n".join([header_line, separator_line, *body_lines])


def _build_blocked_experiment_plan_markdown(
    *,
    objective_or_method_label: str,
    release_status: str,
    known_constraints: list[list[Any]],
    pending_confirmations: list[list[Any]],
) -> str:
    locked_limit_rows = [
        [row[0], row[1], row[4] if len(row) > 4 else ""]
        for row in known_constraints
        if len(row) >= 2 and str(row[3] if len(row) > 3 else "").strip() != "blocked"
    ]
    review_items = []
    for row in known_constraints:
        if len(row) < 2:
            continue
        status = str(row[3] if len(row) > 3 else "").strip()
        note = str(row[4] if len(row) > 4 else "").strip()
        if status == "blocked":
            text = f"{row[0]}: {row[1]}"
            if note:
                text += f". {note}"
            review_items.append(text)
    for row in pending_confirmations:
        if not row:
            continue
        item = str(row[0]).strip()
        reason = str(row[3] if len(row) > 3 else "").strip()
        next_action = str(row[4] if len(row) > 4 else "").strip()
        text = item
        if reason:
            text += f": {reason}"
        if next_action:
            text += f". Next action: {next_action}"
        review_items.append(text)

    sections = [
        "# Experiment Plan",
        "",
        f"Status: {release_status}",
        "",
        "## Plan Status & Constraints",
        "### Objective",
        objective_or_method_label,
        "",
        "### Controlled Test Object And Locked Limits",
        _markdown_table(
            ["Item", "Value", "Notes"],
            locked_limit_rows,
        ),
    ]
    if review_items:
        sections.extend(
            [
                "",
                "### Review Items Before Release",
                "\n".join(f"- {item}" for item in review_items),
            ]
        )
    sections.extend(
        [
            "",
            "## Protocol",
            "- Protocol parameters and the recommended execution sequence will be emitted after the blocking inputs are confirmed.",
            "",
            "## Outputs & Basis",
            "- Outputs, calculation notes, and references will appear after the blocking inputs are cleared.",
        ]
    )
    return "\n".join(sections)


def _normalize_text(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _query_requests_distinct_manufacturers(query: str | None) -> bool:
    if not query:
        return False
    lowered = query.lower()
    return "manufactur" in lowered and (
        "different" in lowered or "various" in lowered or "multiple" in lowered
    )


DEFAULT_CELL_CATALOG_EXPORT_COLUMNS = (
    "cell_id",
    "manufacturer",
    "model",
    "display_name",
    "form_factor",
    "positive_electrode_type",
    "project_chemistry_hint",
    "nominal_capacity_ah",
    "nominal_voltage_v",
    "charge_voltage_v",
    "discharge_cutoff_v",
    "max_continuous_charge_current_a",
    "max_continuous_discharge_current_a",
    "mass_g",
    "cycle_life_cycles",
)

CELL_CATALOG_EXPORT_FORMAT_EXTENSIONS = {
    "csv": "csv",
    "json": "json",
    "markdown": "md",
    "md": "md",
    "txt": "txt",
}

CELL_CATALOG_EXPORT_COLUMN_LABELS = {
    "cell_id": "Cell ID",
    "manufacturer": "Manufacturer",
    "model": "Model",
    "display_name": "Display Name",
    "form_factor": "Form Factor",
    "positive_electrode_type": "Positive Electrode Type",
    "project_chemistry_hint": "Chemistry Hint",
    "nominal_capacity_ah": "Nominal Capacity (Ah)",
    "nominal_voltage_v": "Nominal Voltage (V)",
    "charge_voltage_v": "Charge Voltage (V)",
    "discharge_cutoff_v": "Discharge Cutoff (V)",
    "max_continuous_charge_current_a": "Max Continuous Charge Current (A)",
    "max_continuous_discharge_current_a": "Max Continuous Discharge Current (A)",
    "mass_g": "Mass (g)",
    "cycle_life_cycles": "Cycle Life (cycles)",
    "source_repository": "Source Repository",
    "source_file": "Source File",
}


def _slugify_filename_segment(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _humanize_catalog_field_name(field_name: str | None) -> str:
    normalized = _normalize_text(str(field_name or ""))
    if normalized == "project_chemistry_hint":
        return "Chemistry"
    if normalized == "positive_electrode_type":
        return "Positive Electrode"
    label = CELL_CATALOG_EXPORT_COLUMN_LABELS.get(normalized)
    if label:
        return label
    if not normalized:
        return "Field"
    return " ".join(segment.capitalize() for segment in normalized.split("_"))


def _format_catalog_filter_summary(
    field_name: str | None,
    field_value: str | None,
) -> str:
    if not field_name or not field_value:
        return "None"
    normalized_field = _normalize_text(field_name)
    rendered_value = str(field_value)
    if normalized_field == "project_chemistry_hint":
        rendered_value = rendered_value.upper()
    return f"{_humanize_catalog_field_name(field_name)} = {rendered_value}"


def _summarize_catalog_export_subject(
    *,
    query: str | None,
    filter_field: str | None,
    filter_value: str | None,
) -> str:
    if filter_field and filter_value:
        if _normalize_text(filter_field) == "project_chemistry_hint":
            return f"{str(filter_value).upper()} cells"
        return f"cells matching {_format_catalog_filter_summary(filter_field, filter_value)}"
    if query and str(query).strip():
        return f"cells matching '{str(query).strip()}'"
    return "cell catalog results"


def _parse_cell_catalog_columns(columns_json: str | None) -> list[str]:
    if columns_json is None or not str(columns_json).strip():
        return list(DEFAULT_CELL_CATALOG_EXPORT_COLUMNS)

    parsed = _parse_json_string_list(columns_json, field_name="columns_json")
    if not parsed:
        return list(DEFAULT_CELL_CATALOG_EXPORT_COLUMNS)

    normalized_columns: list[str] = []
    for item in parsed:
        normalized = _normalize_text(str(item))
        if normalized not in CELL_CATALOG_EXPORT_COLUMN_LABELS:
            raise ValueError(
                "Unsupported cell catalog export column: "
                f"{item}. Supported columns: {', '.join(sorted(CELL_CATALOG_EXPORT_COLUMN_LABELS))}."
            )
        if normalized not in normalized_columns:
            normalized_columns.append(normalized)
    return normalized_columns


def _normalize_cell_catalog_export_format(export_format: str) -> str:
    normalized = str(export_format or "csv").strip().lower()
    if normalized not in CELL_CATALOG_EXPORT_FORMAT_EXTENSIONS:
        raise ValueError(
            "Unsupported cell catalog export format: "
            f"{export_format}. Supported formats: {', '.join(sorted(CELL_CATALOG_EXPORT_FORMAT_EXTENSIONS))}."
        )
    return normalized


def _build_cell_catalog_export_rows(
    records: list[dict[str, Any]],
    *,
    columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        for column in columns:
            value = get_cell_catalog_field_value(record, column)
            row[column] = "" if value is None else value
        rows.append(row)
    return rows


def _render_cell_catalog_csv(rows: list[dict[str, Any]], *, columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in columns})
    return buffer.getvalue()


def _render_cell_catalog_json(
    rows: list[dict[str, Any]],
    *,
    columns: list[str],
    query: str | None,
    filter_field: str | None,
    filter_value: str | None,
) -> str:
    payload = {
        "status": "ok",
        "query": query,
        "filter_field": filter_field,
        "filter_value": filter_value,
        "columns": columns,
        "records": rows,
    }
    return _json_dumps(payload)


def _render_cell_catalog_markdown(rows: list[dict[str, Any]], *, columns: list[str]) -> str:
    headers = [CELL_CATALOG_EXPORT_COLUMN_LABELS.get(column, column) for column in columns]
    table_rows = [[row.get(column, "") for column in columns] for row in rows]
    return "\n".join(
        [
            "# Imported Cell Catalog Export",
            "",
            _markdown_table(headers, table_rows),
        ]
    )


def _render_cell_catalog_text(rows: list[dict[str, Any]], *, columns: list[str]) -> str:
    headers = [CELL_CATALOG_EXPORT_COLUMN_LABELS.get(column, column) for column in columns]
    body_rows = [[str(row.get(column, "") or "") for column in columns] for row in rows]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in body_rows)) if body_rows else len(headers[index])
        for index in range(len(headers))
    ]

    def render_line(values: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(values))

    separator = "-+-".join("-" * width for width in widths)
    lines = [
        "Imported Cell Catalog Export",
        "",
        render_line(headers),
        separator,
    ]
    lines.extend(render_line(row) for row in body_rows)
    return "\n".join(lines)


def _build_cell_catalog_export_path(
    *,
    export_format: str,
    filename_hint: str | None,
    query: str | None,
    filter_field: str | None,
    filter_value: str | None,
    distinct_manufacturers: bool,
) -> str:
    extension = CELL_CATALOG_EXPORT_FORMAT_EXTENSIONS[export_format]
    path_segments: list[str] = []
    if filename_hint:
        path_segments.append(_slugify_filename_segment(filename_hint))
    elif filter_field and filter_value:
        path_segments.extend(
            [
                _slugify_filename_segment(filter_value),
                _slugify_filename_segment(filter_field),
                "cells",
            ]
        )
    elif query:
        path_segments.extend([_slugify_filename_segment(query), "cells"])
    else:
        path_segments.append("imported-cell-catalog")

    if distinct_manufacturers:
        path_segments.append("distinct-manufacturers")

    file_stem = "-".join(segment for segment in path_segments if segment) or "imported-cell-catalog"
    return f"/exports/{file_stem}.{extension}"


def _record_completeness_score(record: dict[str, Any]) -> tuple[int, float, float]:
    electrical = record.get("electrical", {})
    currents = record.get("currents", {})
    physical = record.get("physical", {})
    lifecycle = record.get("lifecycle", {})
    checks = [
        electrical.get("nominal_capacity_ah"),
        electrical.get("nominal_voltage_v"),
        electrical.get("charge_voltage_v"),
        electrical.get("discharge_cutoff_v"),
        currents.get("max_continuous_charge_current_a"),
        currents.get("max_continuous_discharge_current_a"),
        lifecycle.get("cycle_life_cycles"),
        physical.get("mass_g"),
        record.get("form_factor"),
    ]
    completeness = sum(value is not None for value in checks)
    capacity = float(electrical.get("nominal_capacity_ah") or 0.0)
    cycle_life = float(lifecycle.get("cycle_life_cycles") or 0.0)
    return completeness, cycle_life, capacity


def _planner_context_for_record(record: dict[str, Any]) -> dict[str, Any]:
    chemistry_hint = record.get("project_chemistry_hint")
    context: dict[str, Any] = {
        "selected_cell_id": record.get("cell_id"),
        "chemistry": chemistry_hint,
        "chemistry_registry_status": "unknown",
        "controlled_chemistry_id": None,
        "completeness_status": record.get("completeness_status", "unknown"),
        "approval_status": record.get("approval_status", "unknown"),
        "approval_basis": record.get("approval_basis", "unknown"),
        "confidence_status": record.get("confidence_status", "unknown"),
        "eligible_for_planning": bool(record.get("eligible_for_planning", False)),
        "eligibility_tags": list(record.get("eligibility_tags", [])),
        "waived_missing_required_fields": list(record.get("waived_missing_required_fields", [])),
        "literature_reference": record.get("literature_reference"),
        "form_factor": record.get("form_factor"),
        "nominal_capacity_ah": record.get("electrical", {}).get("nominal_capacity_ah"),
        "nominal_voltage_v": record.get("electrical", {}).get("nominal_voltage_v"),
        "charge_voltage_v": record.get("electrical", {}).get("charge_voltage_v"),
        "discharge_cutoff_v": record.get("electrical", {}).get("discharge_cutoff_v"),
        "supported_methods": [],
    }

    if chemistry_hint:
        try:
            chemistry_profile = get_chemistry_profile(str(chemistry_hint))
            context["chemistry"] = chemistry_profile["id"]
            context["chemistry_registry_status"] = "controlled"
            context["controlled_chemistry_id"] = chemistry_profile["id"]
            context["supported_methods"] = chemistry_profile.get("supported_methods", [])
        except KeyError:
            context["chemistry_registry_status"] = "unmapped"

    return context


def _build_manufacturer_groups(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        manufacturer = str(record.get("manufacturer") or "unknown")
        grouped.setdefault(manufacturer, []).append(record)

    groups: list[dict[str, Any]] = []
    for manufacturer, items in sorted(grouped.items(), key=lambda item: _normalize_text(item[0])):
        ranked_items = sorted(
            items,
            key=lambda record: (
                *_record_completeness_score(record),
                -len(record.get("normalization_notes", [])),
            ),
            reverse=True,
        )
        groups.append(
            {
                "manufacturer": manufacturer,
                "count": len(items),
                "representative_cell_id": ranked_items[0].get("cell_id") if ranked_items else None,
                "cells": ranked_items,
            }
        )
    return groups


def _select_top_representative_cells(
    manufacturer_groups: list[dict[str, Any]],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    representatives = [
        group["cells"][0]
        for group in manufacturer_groups
        if group.get("cells")
    ]
    representatives.sort(
        key=lambda record: (
            *_record_completeness_score(record),
            -len(record.get("normalization_notes", [])),
        ),
        reverse=True,
    )
    return representatives[: max(limit, 1)]


def _build_step_deviation_policy(
    steps: list[dict[str, Any]],
    strict_reference_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    policy = dict(strict_reference_policy or {})
    review_items: list[str] = []
    for step in steps:
        step_name = str(step.get("name") or "Unnamed step")
        if not bool(step.get("source_backed", False)):
            review_items.append(
                f"{step_name}: planner completion or non-source-backed detail must be reviewed before release."
            )
        elif str(step.get("step_strictness") or "") in {
            "tailorable_after_review",
            "framework_after_review",
        }:
            review_items.append(
                f"{step_name}: handbook allows tailoring here, but the chosen narrowing still needs review."
            )

        deviation_note = str(step.get("deviation_note") or "").strip()
        if deviation_note:
            review_items.append(f"{step_name}: {deviation_note}")

    unique_review_items: list[str] = []
    seen: set[str] = set()
    for item in review_items:
        if item in seen:
            continue
        seen.add(item)
        unique_review_items.append(item)

    return {
        "mode": policy.get("mode", "draft_reference"),
        "summary": policy.get(
            "summary",
            "Use the structured handbook method as the primary planning reference and surface any deviations for review.",
        ),
        "locked_planning_fields": list(policy.get("locked_planning_fields", [])),
        "tailorable_fields": list(policy.get("tailorable_fields", [])),
        "review_required": bool(policy.get("deviation_review_required", False)),
        "deviation_review_items": unique_review_items,
    }


@tool(args_schema=CellCatalogSearchRequest)
def search_imported_cell_catalog(
    query: str | None = None,
    limit: int = 10,
    distinct_manufacturers: bool = False,
    filter_field: str | None = None,
    filter_value: str | None = None,
) -> str:
    """Search the imported external cell catalog and return flattened, project-usable battery cell metadata."""

    normalized_filter_field = _normalize_text(str(filter_field or "")) or None
    normalized_filter_value = str(filter_value or "").strip() or None
    if normalized_filter_field and not normalized_filter_value:
        return _tool_error(
            "filter_value is required when filter_field is provided.",
            error_type="missing_cell_catalog_filter_value",
            suggestions=[
                "Supply both filter_field and filter_value, for example project_chemistry_hint + lfp.",
            ],
        )
    if normalized_filter_field and normalized_filter_field not in SUPPORTED_CELL_CATALOG_FILTER_FIELDS:
        return _tool_error(
            f"Unsupported cell catalog filter_field: {filter_field}",
            error_type="unsupported_cell_catalog_filter_field",
            suggestions=[
                "Use one of: " + ", ".join(SUPPORTED_CELL_CATALOG_FILTER_FIELDS),
            ],
        )

    try:
        applied_distinct_manufacturers = distinct_manufacturers or _query_requests_distinct_manufacturers(query)
        payload = search_cell_catalog(
            query,
            limit=limit,
            distinct_manufacturers=applied_distinct_manufacturers,
            filter_field=normalized_filter_field,
            filter_value=normalized_filter_value,
        )
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="missing_cell_catalog",
            suggestions=[
                "Run `uv run python .\\scripts\\import_cellinfo_repository.py` to generate the local cell catalog first.",
            ],
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unsupported_cell_catalog_filter_field",
            suggestions=[
                "Use one of: " + ", ".join(SUPPORTED_CELL_CATALOG_FILTER_FIELDS),
            ],
        )

    records = payload.get("records", [])
    for record in records:
        record["planner_context"] = _planner_context_for_record(record)

    manufacturer_groups = _build_manufacturer_groups(records)
    representative_cells = _select_top_representative_cells(manufacturer_groups)
    payload["manufacturer_groups"] = manufacturer_groups
    payload["top_representative_cells"] = representative_cells

    summary_lines = []
    for record in records:
        electrical = record.get("electrical", {})
        lifecycle = record.get("lifecycle", {})
        planner_context = record.get("planner_context", {})
        chemistry_hint = record.get("project_chemistry_hint") or "unknown"
        chemistry_registry_status = planner_context.get("chemistry_registry_status", "unknown")
        summary_lines.append(
            "\n".join(
                [
                    f"- `{record.get('cell_id')}`",
                    f"  - Display name: {record.get('display_name')}",
                    f"  - Manufacturer: {record.get('manufacturer') or 'unknown'}",
                    f"  - Chemistry hint: {chemistry_hint}",
                    f"  - Chemistry registry status: {chemistry_registry_status}",
                    f"  - Completeness: {record.get('completeness_status', 'unknown')}",
                    f"  - Approval: {record.get('approval_status', 'unknown')}",
                    f"  - Approval basis: {record.get('approval_basis', 'unknown')}",
                    f"  - Confidence: {record.get('confidence_status', 'unknown')}",
                    "  - Eligibility tags: "
                    + ", ".join(record.get("eligibility_tags", [])),
                    (
                        "  - Waived required fields: "
                        + ", ".join(record.get("waived_missing_required_fields", []))
                        if record.get("waived_missing_required_fields")
                        else "  - Waived required fields: none"
                    ),
                    f"  - Form factor: {record.get('form_factor') or 'unknown'}",
                    f"  - Nominal voltage: {electrical.get('nominal_voltage_v', 'n/a')} V",
                    f"  - Nominal capacity: {electrical.get('nominal_capacity_ah', 'n/a')} Ah",
                    f"  - Cycle life: {lifecycle.get('cycle_life_cycles', 'n/a')} cycles",
                    (
                        "  - Literature reference: "
                        + str(
                            record.get("literature_reference", {}).get("citation_text")
                            or "none"
                        )
                        if isinstance(record.get("literature_reference"), dict)
                        else "  - Literature reference: none"
                    ),
                ]
            )
        )

    manufacturer_count = len(
        {
            str(record.get("manufacturer", "")).strip()
            for record in records
            if str(record.get("manufacturer", "")).strip()
        }
    )
    filter_summary = (
        f"`{payload['applied_filter']['field']} = {payload['applied_filter']['value']}`"
        if isinstance(payload.get("applied_filter"), dict)
        else "`none`"
    )
    payload["ui_markdown"] = "\n\n".join(
        [
            "## Imported Cell Catalog Search",
            "",
            f"- Catalog version: `{payload.get('catalog_version', 'unknown')}`",
            f"- Exact filter: {filter_summary}",
            f"- Query tokens: `{', '.join(payload.get('query_tokens', [])) or 'none'}`",
            f"- Total matches before distinct/limit: {payload.get('matched_record_count', 0)}",
            f"- Matches after distinct-manufacturer pass: {payload.get('post_distinct_record_count', 0)}",
            f"- Returned records: {payload.get('returned_record_count', payload.get('record_count', 0))}",
            f"- Approved records in full active catalog: {payload.get('approved_record_count', 0)}",
            f"- Raw records before formal filtering: {payload.get('raw_record_count', 0)}",
            f"- Excluded incomplete records: {payload.get('excluded_record_count', 0)}",
            f"- Unique manufacturers in result: {manufacturer_count}",
            f"- Distinct-manufacturer mode: `{applied_distinct_manufacturers}`",
            "- Active cell surface keeps approved records with either full required fields or an explicit literature-backed waiver.",
            "",
            "### Top Representative Cells",
            "\n".join(
                f"- {record.get('display_name')} ({record.get('manufacturer')})"
                for record in representative_cells
            )
            or "- None.",
            "",
            "### Matches",
            "\n\n".join(summary_lines) if summary_lines else "- No matches found.",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=CellCatalogExportRequest)
def export_imported_cell_catalog(
    query: str | None = None,
    format: str = "csv",
    limit: int = 500,
    distinct_manufacturers: bool = False,
    filter_field: str | None = None,
    filter_value: str | None = None,
    columns_json: str = "[]",
    filename_hint: str | None = None,
) -> str:
    """Export imported cell catalog results to a structured CSV, Markdown, TXT, or JSON file."""

    normalized_filter_field = _normalize_text(str(filter_field or "")) or None
    normalized_filter_value = str(filter_value or "").strip() or None
    if normalized_filter_field and not normalized_filter_value:
        return _tool_error(
            "filter_value is required when filter_field is provided.",
            error_type="missing_cell_catalog_filter_value",
            suggestions=[
                "Supply both filter_field and filter_value, for example positive_electrode_type + LithiumIronPhosphate.",
            ],
        )
    if normalized_filter_field and normalized_filter_field not in SUPPORTED_CELL_CATALOG_FILTER_FIELDS:
        return _tool_error(
            f"Unsupported cell catalog filter_field: {filter_field}",
            error_type="unsupported_cell_catalog_filter_field",
            suggestions=[
                "Use one of: " + ", ".join(SUPPORTED_CELL_CATALOG_FILTER_FIELDS),
            ],
        )

    try:
        export_format = _normalize_cell_catalog_export_format(format)
        columns = _parse_cell_catalog_columns(columns_json)
        payload = search_cell_catalog(
            query,
            limit=limit,
            distinct_manufacturers=(
                distinct_manufacturers or _query_requests_distinct_manufacturers(query)
            ),
            filter_field=normalized_filter_field,
            filter_value=normalized_filter_value,
        )
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="missing_cell_catalog",
            suggestions=[
                "Run `uv run python .\\scripts\\import_cellinfo_repository.py` to generate the local cell catalog first.",
            ],
        )
    except (KeyError, ValueError) as exc:
        return _tool_error(
            str(exc),
            error_type="cell_catalog_export_configuration_error",
            suggestions=[
                "Use a supported format, supported filter field, and JSON-array column list.",
            ],
        )

    export_rows = _build_cell_catalog_export_rows(payload.get("records", []), columns=columns)
    if export_format == "csv":
        file_content = _render_cell_catalog_csv(export_rows, columns=columns)
    elif export_format == "json":
        file_content = _render_cell_catalog_json(
            export_rows,
            columns=columns,
            query=query,
            filter_field=normalized_filter_field,
            filter_value=normalized_filter_value,
        )
    elif export_format in {"markdown", "md"}:
        file_content = _render_cell_catalog_markdown(export_rows, columns=columns)
    else:
        file_content = _render_cell_catalog_text(export_rows, columns=columns)

    export_path = _build_cell_catalog_export_path(
        export_format=export_format,
        filename_hint=filename_hint,
        query=query,
        filter_field=normalized_filter_field,
        filter_value=normalized_filter_value,
        distinct_manufacturers=bool(payload.get("distinct_manufacturers")),
    )
    filter_summary = _format_catalog_filter_summary(
        normalized_filter_field,
        normalized_filter_value,
    )
    exported_record_count = len(export_rows)
    subject_summary = _summarize_catalog_export_subject(
        query=query,
        filter_field=normalized_filter_field,
        filter_value=normalized_filter_value,
    )
    file_name = export_path.rsplit("/", 1)[-1]

    export_payload = {
        "status": "ok",
        "export_format": export_format,
        "catalog_version": payload.get("catalog_version"),
        "query": query,
        "query_tokens": payload.get("query_tokens", []),
        "applied_filter": payload.get("applied_filter"),
        "distinct_manufacturers": payload.get("distinct_manufacturers"),
        "matched_record_count": payload.get("matched_record_count", exported_record_count),
        "post_distinct_record_count": payload.get("post_distinct_record_count", exported_record_count),
        "exported_record_count": exported_record_count,
        "approved_record_count": payload.get("approved_record_count"),
        "export_columns": columns,
        "generated_files": [
            {
                "path": export_path,
                "content": file_content,
                "generated_file_kind": "cell_catalog_export",
                "display_name": export_path.rsplit("/", 1)[-1],
            }
        ],
        "ui_markdown": "\n".join(
            [
                "## Imported Cell Catalog Export",
                "",
                f"Exported {subject_summary} to {export_format.upper()}.",
                "",
                f"- Rows: {exported_record_count}",
                f"- File: `{file_name}`",
                (
                    f"- Filter: {filter_summary}"
                    if normalized_filter_field and normalized_filter_value
                    else "- Filter: None"
                ),
                f"- Columns included: {len(columns)}",
                (
                    f"- Note: showing the first {exported_record_count} matching records because limit={limit}."
                    if payload.get("matched_record_count", exported_record_count) > exported_record_count
                    else "- Note: export includes the full current result set."
                ),
            ]
        ),
    }
    return _json_dumps(export_payload)


@tool(args_schema=CellCatalogRecordRequest)
def load_imported_cell_record(cell_id: str) -> str:
    """Load one flattened cell record from the imported external cell catalog."""

    try:
        record = get_cell_catalog_record(cell_id)
        catalog = load_cell_catalog()
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="missing_cell_catalog",
            suggestions=[
                "Run `uv run python .\\scripts\\import_cellinfo_repository.py` to generate the local cell catalog first.",
            ],
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_cell_record",
            suggestions=[
                "Use `search_imported_cell_catalog` first if you are not sure about the exact cell id.",
            ],
        )

    electrical = record.get("electrical", {})
    currents = record.get("currents", {})
    physical = record.get("physical", {})
    lifecycle = record.get("lifecycle", {})
    chemistry_hint = record.get("project_chemistry_hint") or "unknown"
    planner_context = _planner_context_for_record(record)
    chemistry_registry_status = planner_context.get("chemistry_registry_status", "unknown")
    payload = {
        "status": "ok",
        "catalog_version": catalog.get("catalog_version"),
        "record": record,
        "planner_context": planner_context,
        "ui_markdown": "\n".join(
            [
                f"## Cell Record: {record.get('display_name')}",
                "",
                f"- Cell id: `{record.get('cell_id')}`",
                f"- Chemistry hint: `{chemistry_hint}`",
                f"- Chemistry registry status: `{chemistry_registry_status}`",
                f"- Completeness: `{record.get('completeness_status', 'unknown')}`",
                f"- Approval: `{record.get('approval_status', 'unknown')}`",
                f"- Approval basis: `{record.get('approval_basis', 'unknown')}`",
                f"- Confidence: `{record.get('confidence_status', 'unknown')}`",
                "- Eligibility tags: `"
                + ", ".join(record.get("eligibility_tags", []))
                + "`",
                (
                    "- Waived required fields: `"
                    + ", ".join(record.get("waived_missing_required_fields", []))
                    + "`"
                    if record.get("waived_missing_required_fields")
                    else "- Waived required fields: `none`"
                ),
                f"- Positive electrode type: `{record.get('positive_electrode_type') or 'unknown'}`",
                f"- Form factor: `{record.get('form_factor') or 'unknown'}`",
                f"- Nominal voltage: {electrical.get('nominal_voltage_v', 'n/a')} V",
                f"- Charge voltage: {electrical.get('charge_voltage_v', 'n/a')} V",
                f"- Discharge cut-off: {electrical.get('discharge_cutoff_v', 'n/a')} V",
                f"- Nominal capacity: {electrical.get('nominal_capacity_ah', 'n/a')} Ah",
                f"- Max continuous charge current: {currents.get('max_continuous_charge_current_a', 'n/a')} A",
                f"- Max continuous discharge current: {currents.get('max_continuous_discharge_current_a', 'n/a')} A",
                f"- Mass: {physical.get('mass_g', 'n/a')} g",
                f"- Height: {physical.get('height_mm', 'n/a')} mm",
                f"- Width: {physical.get('width_mm', 'n/a')} mm",
                f"- Length: {physical.get('length_mm', 'n/a')} mm",
                f"- Cycle life: {lifecycle.get('cycle_life_cycles', 'n/a')} cycles",
                (
                    "- Normalization notes: "
                    + "; ".join(record.get("normalization_notes", []))
                    if record.get("normalization_notes")
                    else "- Normalization notes: none"
                ),
                (
                    "- Literature reference: "
                    + str(
                        record.get("literature_reference", {}).get("citation_text")
                        or "none"
                    )
                    if isinstance(record.get("literature_reference"), dict)
                    else "- Literature reference: none"
                ),
                "",
                "This imported record remains available because it is approved for formal cell lookup and planning support, either through full metadata coverage or an explicit literature-backed waiver.",
            ]
        ),
    }
    return _json_dumps(payload)


def _extract_uploaded_cell_datasheet_impl(
    file_path: str,
    runtime: ToolRuntime | None = None,
) -> str:
    """Extract a structured cell datasheet candidate from an uploaded thread file."""

    try:
        normalized_path, attachment_text = _load_uploaded_thread_file(
            file_path,
            None,
            runtime,
        )
        payload = extract_cell_datasheet_candidate_from_text(
            attachment_text,
            thread_file_path=normalized_path,
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="uploaded_thread_file_not_found",
            suggestions=[
                "Use the exact `/uploads/...` path shown in the chat attachment notice.",
                "If the attachment came from an older thread, re-upload it so extracted text is available in the current thread file state.",
            ],
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="uploaded_thread_file_validation_error",
            suggestions=[
                "Re-upload the datasheet if this thread file only contains a metadata placeholder.",
                "Use a PDF, TXT, CSV, XLSX, or XLS attachment with extractable text.",
            ],
        )
    except RuntimeError as exc:
        return _tool_error(
            str(exc),
            error_type="datasheet_extraction_runtime_error",
            suggestions=[
                "Confirm OPENAI_API_KEY is configured and BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_MODEL is available.",
            ],
        )
    except Exception as exc:  # pragma: no cover - defensive guard around API/runtime failures
        return _tool_error(
            f"Structured cell datasheet extraction failed: {exc}",
            error_type="datasheet_extraction_error",
        )

    candidate = payload.get("candidate", {})
    electrical = candidate.get("electrical", {})
    currents = candidate.get("currents", {})
    physical = candidate.get("physical", {})
    lifecycle = candidate.get("lifecycle", {})
    source_document = payload.get("source_document", {})

    summary_rows = [
        ["Manufacturer", candidate.get("manufacturer") or "Unknown", ""],
        ["Model", candidate.get("model") or candidate.get("schema_name") or "unknown", ""],
        ["Chemistry hint", candidate.get("project_chemistry_hint") or "unknown", ""],
        ["Form factor", candidate.get("form_factor") or "unknown", ""],
        [
            "Case types",
            ", ".join(candidate.get("case_types", [])) if candidate.get("case_types") else "none",
            "",
        ],
        ["Nominal capacity", f"{electrical.get('nominal_capacity_ah', 'n/a')} Ah", ""],
        ["Nominal voltage", f"{electrical.get('nominal_voltage_v', 'n/a')} V", ""],
        ["Charge voltage limit", f"{electrical.get('charge_voltage_v', 'n/a')} V", ""],
        ["Discharge cut-off", f"{electrical.get('discharge_cutoff_v', 'n/a')} V", ""],
        ["Max continuous charge current", f"{currents.get('max_continuous_charge_current_a', 'n/a')} A", ""],
        ["Max continuous discharge current", f"{currents.get('max_continuous_discharge_current_a', 'n/a')} A", ""],
        ["Mass", f"{physical.get('mass_g', 'n/a')} g", ""],
        ["Cycle life", f"{lifecycle.get('cycle_life_cycles', 'n/a')} cycles", ""],
    ]
    payload["ui_markdown"] = "\n".join(
        [
            f"## Cell Datasheet: {candidate.get('display_name') or 'unknown'}",
            "",
            _markdown_table(["Field", "Value", "Notes"], summary_rows),
            "",
            "### Source",
            f"- Thread file: `{normalized_path}`",
            f"- Original filename: `{source_document.get('original_filename') or 'unknown'}`",
            f"- Extraction model: `{payload.get('model_name') or 'unknown'}`",
            f"- Parser version: `{payload.get('parser_version') or 'unknown'}`",
            "",
            "### Missing Or Unclear Fields",
            (
                "- `"
                + "`, `".join(payload.get("missing_or_uncertain_fields", []))
                + "`"
                if payload.get("missing_or_uncertain_fields")
                else "- None"
            ),
            "",
            "### Suggested Review Notes",
            (
                "\n".join(f"- {item}" for item in payload.get("suggested_review_notes", []))
                if payload.get("suggested_review_notes")
                else "- None"
            ),
        ]
    )
    return _json_dumps(payload)


def _extract_uploaded_cell_datasheet_tool(
    file_path: Annotated[
        str,
        "Absolute `/uploads/...` thread file path for the extracted datasheet text preview.",
    ],
    runtime: ToolRuntime,
) -> str:
    return _extract_uploaded_cell_datasheet_impl(file_path=file_path, runtime=runtime)


extract_uploaded_cell_datasheet = StructuredTool.from_function(
    name="extract_uploaded_cell_datasheet",
    description="Extract a structured cell datasheet candidate from an uploaded thread file.",
    func=_extract_uploaded_cell_datasheet_tool,
)


def _extract_uploaded_cell_datasheet_to_provisional_asset_impl(
    file_path: str,
    submitted_by: str = "chat_user",
    submit_for_review: bool = False,
    runtime: ToolRuntime | None = None,
) -> str:
    """Extract a structured cell datasheet candidate from an uploaded thread file and register it into the provisional review queue."""

    try:
        normalized_path, attachment_text = _load_uploaded_thread_file(
            file_path,
            None,
            runtime,
        )
        extraction_payload = extract_cell_datasheet_candidate_from_text(
            attachment_text,
            thread_file_path=normalized_path,
        )
        payload = register_provisional_cell_asset_record(
            extraction_payload["candidate"],
            submitted_by=submitted_by,
            source_file=normalized_path,
            extraction_status="machine_extracted",
            parser_version=str(extraction_payload.get("parser_version") or "manual_entry"),
            submit_for_review=submit_for_review,
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="uploaded_thread_file_not_found",
            suggestions=[
                "Use the exact `/uploads/...` path shown in the chat attachment notice.",
            ],
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="provisional_asset_extraction_validation_error",
            suggestions=[
                "Re-upload the datasheet if the current thread file only contains metadata.",
                "If the datasheet text is present but incomplete, use `extract_uploaded_cell_datasheet` first and then `register_provisional_cell_asset` manually with corrections.",
            ],
        )
    except RuntimeError as exc:
        return _tool_error(
            str(exc),
            error_type="datasheet_extraction_runtime_error",
            suggestions=[
                "Confirm OPENAI_API_KEY is configured and BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_MODEL is available.",
            ],
        )
    except Exception as exc:  # pragma: no cover - defensive guard around API/runtime failures
        return _tool_error(
            f"Failed to extract and register the uploaded datasheet: {exc}",
            error_type="datasheet_extraction_error",
        )

    asset_summary = payload.get("asset_summary", {})
    payload["extraction"] = {
        key: extraction_payload.get(key)
        for key in (
            "parser_version",
            "model_name",
            "temperature",
            "source_document",
            "extraction_summary",
            "missing_or_uncertain_fields",
            "suggested_review_notes",
        )
    }
    payload["ui_markdown"] = "\n".join(
        [
            "## Uploaded Datasheet Registered As Provisional Cell Asset",
            "",
            f"- Thread file: `{normalized_path}`",
            f"- Provisional id: `{asset_summary.get('provisional_id')}`",
            f"- Review status: `{asset_summary.get('review_status')}`",
            f"- Promotion readiness: `{asset_summary.get('promotion_readiness')}`",
            f"- Submitted by: `{asset_summary.get('submitted_by')}`",
            f"- Extraction model: `{payload['extraction'].get('model_name') or 'unknown'}`",
            (
                "- Missing or uncertain fields: `"
                + ", ".join(payload["extraction"].get("missing_or_uncertain_fields", []))
                + "`"
                if payload["extraction"].get("missing_or_uncertain_fields")
                else "- Missing or uncertain fields: `none`"
            ),
        ]
    )
    return _json_dumps(payload)


def _extract_uploaded_cell_datasheet_to_provisional_asset_tool(
    file_path: Annotated[
        str,
        "Absolute `/uploads/...` thread file path for the extracted datasheet text preview.",
    ],
    submitted_by: Annotated[
        str,
        "Reviewer or uploader label to record on the provisional asset.",
    ] = "chat_user",
    submit_for_review: Annotated[
        bool,
        "When true, place the extracted provisional asset into submitted_for_review status immediately.",
    ] = False,
    runtime: ToolRuntime = None,
) -> str:
    return _extract_uploaded_cell_datasheet_to_provisional_asset_impl(
        file_path=file_path,
        submitted_by=submitted_by,
        submit_for_review=submit_for_review,
        runtime=runtime,
    )


extract_uploaded_cell_datasheet_to_provisional_asset = StructuredTool.from_function(
    name="extract_uploaded_cell_datasheet_to_provisional_asset",
    description="Extract a structured cell datasheet candidate from an uploaded thread file and register it into the provisional review queue.",
    func=_extract_uploaded_cell_datasheet_to_provisional_asset_tool,
)


@tool(args_schema=ProvisionalCellAssetSearchRequest)
def search_provisional_cell_assets(
    query: str | None = None,
    review_status: str | None = None,
    limit: int = 10,
) -> str:
    """Search user-supplied provisional cell assets that are still under review."""

    payload = search_provisional_cell_asset_records(
        query=query,
        review_status=review_status,
        limit=limit,
    )
    assets = payload.get("assets", [])
    payload["ui_markdown"] = "\n".join(
        [
            "## Provisional Cell Assets",
            "",
            f"- Store version: `{payload.get('store_version', 'unknown')}`",
            f"- Total provisional assets: {payload.get('total_asset_count', 0)}",
            f"- Returned assets: {payload.get('asset_count', 0)}",
            f"- Review status filter: `{review_status or 'none'}`",
            "",
            "### Review Status Counts",
            "\n".join(
                f"- {status}: {count}"
                for status, count in payload.get("review_status_counts", {}).items()
            )
            or "- None.",
            "",
            "### Matches",
            "\n\n".join(
                "\n".join(
                    [
                        f"- `{asset.get('provisional_id')}`",
                        f"  - Display name: {asset.get('display_name')}",
                        f"  - Manufacturer: {asset.get('manufacturer') or 'Unknown'}",
                        f"  - Review status: {asset.get('review_status')}",
                        f"  - Promotion readiness: {asset.get('promotion_readiness')}",
                        (
                            "  - Missing required fields: "
                            + ", ".join(asset.get("missing_required_fields", []))
                            if asset.get("missing_required_fields")
                            else "  - Missing required fields: none"
                        ),
                        f"  - Submitted by: {asset.get('submitted_by') or 'unknown'}",
                        (
                            f"  - Promoted cell id: {asset.get('promoted_cell_id')}"
                            if asset.get("promoted_cell_id")
                            else "  - Promoted cell id: not promoted"
                        ),
                    ]
                )
                for asset in assets
            )
            or "- No matches found.",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=ProvisionalCellAssetRequest)
def load_provisional_cell_asset(provisional_id: str) -> str:
    """Load one provisional cell asset, including review history and promotion readiness."""

    try:
        payload = get_provisional_cell_asset_record(provisional_id)
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_provisional_cell_asset",
            suggestions=[
                "Use `search_provisional_cell_assets` to find the exact provisional id first.",
            ],
        )

    asset_summary = payload.get("asset_summary", {})
    asset = payload.get("asset", {})
    payload["ui_markdown"] = "\n".join(
        [
            f"## Provisional Cell Asset: {asset_summary.get('display_name')}",
            "",
            f"- Provisional id: `{asset_summary.get('provisional_id')}`",
            f"- Review status: `{asset_summary.get('review_status')}`",
            f"- Approval status: `{asset_summary.get('approval_status')}`",
            f"- Promotion readiness: `{asset_summary.get('promotion_readiness')}`",
            f"- Submitted by: `{asset_summary.get('submitted_by') or 'unknown'}`",
            f"- Source file: `{asset_summary.get('source_file') or 'unknown'}`",
            (
                "- Missing required fields: `"
                + ", ".join(asset_summary.get("missing_required_fields", []))
                + "`"
                if asset_summary.get("missing_required_fields")
                else "- Missing required fields: `none`"
            ),
            (
                "- Review notes: " + "; ".join(asset.get("review_notes", []))
                if asset.get("review_notes")
                else "- Review notes: none"
            ),
            (
                f"- Proposed final cell id: `{asset.get('formal_promotion_preview', {}).get('proposed_cell_id')}`"
                if isinstance(asset.get("formal_promotion_preview"), dict)
                else "- Proposed final cell id: unknown"
            ),
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=ProvisionalCellAssetRegisterRequest)
def register_provisional_cell_asset(
    asset_json: str,
    submitted_by: str,
    source_file: str | None = None,
    extraction_status: str = "machine_extracted",
    parser_version: str = "manual_entry",
    submit_for_review: bool = False,
) -> str:
    """Register a new provisional cell asset extracted from a user-supplied datasheet or manual entry."""

    try:
        asset_data = _parse_json_object(asset_json, field_name="asset_json")
        payload = register_provisional_cell_asset_record(
            asset_data,
            submitted_by=submitted_by,
            source_file=source_file,
            extraction_status=extraction_status,
            parser_version=parser_version,
            submit_for_review=submit_for_review,
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="provisional_asset_validation_error",
            suggestions=[
                "asset_json should be a JSON object that follows the formal cell schema where possible.",
                "Include display_name, manufacturer, chemistry/form_factor hints, nested electrical/currents/physical blocks, and field_evidence when available.",
            ],
        )

    payload["ui_markdown"] = "\n".join(
        [
            "## Provisional Cell Asset Registered",
            "",
            f"- Provisional id: `{payload['asset_summary'].get('provisional_id')}`",
            f"- Review status: `{payload['asset_summary'].get('review_status')}`",
            f"- Promotion readiness: `{payload['asset_summary'].get('promotion_readiness')}`",
            f"- Submitted by: `{payload['asset_summary'].get('submitted_by')}`",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=ProvisionalCellAssetReviewRequest)
def review_provisional_cell_asset(
    provisional_id: str,
    decision: str,
    actor: str,
    review_notes_json: str = "[]",
    corrected_fields_json: str = "{}",
    required_field_waivers_json: str = "[]",
) -> str:
    """Apply a correction, review decision, or approval step to a provisional cell asset."""

    try:
        review_notes = _parse_json_string_list(review_notes_json, field_name="review_notes_json")
        corrected_fields = _parse_json_object(
            corrected_fields_json,
            field_name="corrected_fields_json",
        )
        required_field_waivers = _parse_json_string_list(
            required_field_waivers_json,
            field_name="required_field_waivers_json",
        )
        payload = review_provisional_cell_asset_record(
            provisional_id,
            decision=decision,
            actor=actor,
            review_notes=review_notes,
            corrected_fields=corrected_fields,
            required_field_waivers=required_field_waivers,
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_provisional_cell_asset",
            suggestions=[
                "Use `search_provisional_cell_assets` to find the exact provisional id first.",
            ],
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="provisional_review_validation_error",
            suggestions=[
                "Use one of: user_corrected, submit_for_review, needs_changes, reject, approve_for_promotion.",
                "Provide corrected_fields_json as a JSON object and review_notes_json / required_field_waivers_json as JSON arrays.",
            ],
        )

    asset_summary = payload.get("asset_summary", {})
    payload["ui_markdown"] = "\n".join(
        [
            "## Provisional Cell Asset Reviewed",
            "",
            f"- Provisional id: `{asset_summary.get('provisional_id')}`",
            f"- Decision: `{payload.get('decision')}`",
            f"- New review status: `{asset_summary.get('review_status')}`",
            (
                "- Missing required fields: `"
                + ", ".join(asset_summary.get("missing_required_fields", []))
                + "`"
                if asset_summary.get("missing_required_fields")
                else "- Missing required fields: `none`"
            ),
            f"- Promotion readiness: `{asset_summary.get('promotion_readiness')}`",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=ProvisionalCellAssetPromotionRequest)
def promote_provisional_cell_asset(
    provisional_id: str,
    reviewer: str,
    final_cell_id: str | None = None,
    promotion_notes_json: str = "[]",
    replace_existing: bool = False,
) -> str:
    """Promote an approved provisional cell asset into the formal manual cell asset catalog."""

    try:
        promotion_notes = _parse_json_string_list(
            promotion_notes_json,
            field_name="promotion_notes_json",
        )
        payload = promote_provisional_cell_asset_record(
            provisional_id,
            reviewer=reviewer,
            final_cell_id=final_cell_id,
            promotion_notes=promotion_notes,
            replace_existing=replace_existing,
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_provisional_cell_asset",
            suggestions=[
                "Use `search_provisional_cell_assets` to find the exact provisional id first.",
            ],
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="provisional_promotion_validation_error",
            suggestions=[
                "Only assets with review_status=approved_for_promotion can be promoted.",
                "Use review_provisional_cell_asset to resolve missing fields or request an explicit waiver before promotion.",
            ],
        )

    asset_summary = payload.get("asset_summary", {})
    promoted_manual_record = payload.get("promoted_manual_record", {})
    payload["ui_markdown"] = "\n".join(
        [
            "## Provisional Cell Asset Promoted",
            "",
            f"- Provisional id: `{asset_summary.get('provisional_id')}`",
            f"- Promoted cell id: `{promoted_manual_record.get('cell_id')}`",
            f"- Reviewer: `{reviewer}`",
            f"- Review status: `{asset_summary.get('review_status')}`",
            "- This record is now available on the formal manual cell asset surface and will participate in approved cell lookup/planning if it passes the existing governance filters.",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=ChemistryProfileRequest)
def describe_chemistry_profile(chemistry: str) -> str:
    """Return registry-backed chemistry constraints only. This tool does not generate waveform or impedance previews."""

    try:
        chemistry_profile = get_chemistry_profile(chemistry)
    except KeyError as exc:
        kb = load_kb()
        return _tool_error(
            str(exc),
            error_type="unknown_chemistry_profile",
            suggestions=[
                "Available chemistries: " + ", ".join(sorted(kb["chemistry_profiles"].keys())),
            ],
        )

    alias_resolution_note = None
    if _normalize_text(chemistry) != chemistry_profile["id"]:
        alias_resolution_note = (
            f"Requested chemistry `{chemistry}` resolves to registry profile `{chemistry_profile['id']}` in this demo."
        )

    not_defined_in_registry = [
        "capacity",
        "internal resistance",
        "cycle life",
        "energy density",
        "cell dimensions",
    ]
    supported_methods = chemistry_profile.get("supported_methods", [])
    electrical_parameters = {
        "nominal_voltage_v": chemistry_profile["nominal_voltage_v"],
        "charge_voltage_v": chemistry_profile["charge_voltage_v"],
        "discharge_cutoff_v": chemistry_profile["discharge_cutoff_v"],
        "recommended_temperature_range_c": chemistry_profile["recommended_temperature_range_c"],
        "max_recommended_charge_c_rate": chemistry_profile["max_recommended_charge_c_rate"],
        "max_recommended_discharge_c_rate": chemistry_profile["max_recommended_discharge_c_rate"],
        "rest_minutes_before_pulse": chemistry_profile["rest_minutes_before_pulse"],
    }
    note_lines = "\n".join(f"- {item}" for item in chemistry_profile.get("notes", [])) or "- None."
    undefined_lines = "\n".join(f"- {item}" for item in not_defined_in_registry)
    supported_method_lines = "\n".join(f"- {item}" for item in supported_methods) or "- None."

    sections = [
        f"## Chemistry Profile: {chemistry_profile['label']}",
        "",
        f"- Registry chemistry id: `{chemistry_profile['id']}`",
        f"- Nominal voltage: {chemistry_profile['nominal_voltage_v']} V",
        f"- Charge voltage: {chemistry_profile['charge_voltage_v']} V",
        f"- Lower cut-off voltage: {chemistry_profile['discharge_cutoff_v']} V",
        f"- Recommended temperature range: {chemistry_profile['recommended_temperature_range_c'][0]} to {chemistry_profile['recommended_temperature_range_c'][1]} C",
        f"- Max recommended charge C-rate: {chemistry_profile['max_recommended_charge_c_rate']} C",
        f"- Max recommended discharge C-rate: {chemistry_profile['max_recommended_discharge_c_rate']} C",
        f"- Rest before pulse guidance: {chemistry_profile['rest_minutes_before_pulse']} min",
    ]
    if alias_resolution_note:
        sections.extend(["", alias_resolution_note])
    sections.extend(
        [
            "",
            "### Supported Methods",
            supported_method_lines,
            "",
            "### Registry Notes",
            note_lines,
            "",
            "### Not Defined In This Demo Registry",
            undefined_lines,
            "",
            "Only the fields listed above should be treated as hard, registry-backed values in this demo.",
        ]
    )

    payload = {
        "status": "ok",
        "chemistry_id": chemistry_profile["id"],
        "label": chemistry_profile["label"],
        "alias_resolution_note": alias_resolution_note,
        "electrical_parameters": electrical_parameters,
        "supported_methods": supported_methods,
        "trust_level": "formal_input",
        "notes": chemistry_profile.get("notes", []),
        "not_defined_in_registry": not_defined_in_registry,
        "ui_markdown": "\n".join(sections),
    }
    return _json_dumps(payload)


def _load_battery_knowledge_impl(
    chemistry: str | None = None,
    instrument: str | None = None,
    thermal_chamber: str | None = None,
    objective: str | None = None,
    runtime: ToolRuntime | None = None,
) -> str:
    """Load structured battery knowledge and constraints from the local knowledge base."""

    resolved_instrument, resolved_thermal_chamber, lab_default_context = (
        _resolve_planning_defaults_from_runtime(
            instrument=instrument,
            thermal_chamber=thermal_chamber,
            runtime=runtime,
        )
    )
    effective_approved_equipment_defaults = _build_effective_pretest_equipment_defaults(
        lab_default_context
    )
    preflight_thermal_chamber_note: str | None = None
    if normalize_optional_text(thermal_chamber) is None:
        lab_default_context, preflight_thermal_chamber_note = (
            _mark_default_thermal_chamber_as_available_context(lab_default_context)
        )

    payload: dict[str, Any] = {"workspace_root": _display_repo_root()}
    answer_references: list[dict[str, Any]] = []
    display_prefix = {
        "user_supplied": "U",
        "public": "P",
        "built_in_guidance": "G",
    }

    def built_in_reference_text(category: str, summary: str) -> str:
        category_text = str(category or "").strip() or "Internal guidance"
        summary_text = str(summary or "").strip()
        if not summary_text:
            return f"{category_text}."
        return f"{category_text}. {summary_text}"

    def append_reference(
        *,
        key: str,
        source_type: str,
        preferred_for: str,
        reference_text: str,
        source_id: str | None = None,
        reference_type: str = "built_in_guidance",
        title: str | None = None,
        visibility_note: str | None = None,
    ) -> None:
        citation_number = len(answer_references) + 1
        display_number = (
            sum(
                1
                for item in answer_references
                if item.get("reference_type") == reference_type
            )
            + 1
        )
        answer_references.append(
            {
                "reference_key": key,
                "citation_number": citation_number,
                "citation_token": f"[{citation_number}]",
                "display_token": f"{display_prefix.get(reference_type, 'G')}{display_number}",
                "source_type": source_type,
                "reference_type": reference_type,
                "source_id": source_id,
                "preferred_for": preferred_for,
                "scope_of_use": preferred_for,
                "title": title or key.replace("_", " ").title(),
                "visibility_note": visibility_note
                or (
                    "Built-in system guidance or governed local knowledge."
                    if reference_type == "built_in_guidance"
                    else "User-provided source record."
                    if reference_type == "user_supplied"
                    else "Public source."
                ),
                "reference_text": reference_text,
            }
        )

    pretest_global_defaults = get_pretest_global_defaults()
    payload["pretest_guidance"] = {
        "global_defaults": pretest_global_defaults,
        "approved_equipment_defaults": effective_approved_equipment_defaults,
    }
    payload["decision_graph_semantics"] = {
        "relation_classes": get_decision_relation_classes(),
        "authority_and_precedence": get_authority_and_precedence_model(),
        "requirement_strength_levels": get_requirement_strength_levels(),
        "conflict_representation": get_decision_conflict_representation(),
    }
    append_reference(
        key="pretest_guidance",
        source_type="local_pretest_guidance",
        source_id="pretest_assistant_guidance_v0_1",
        preferred_for="lab-wide SOP defaults, minimum pretest packages, and approved equipment defaults",
        title="Lab pretest guidance",
        visibility_note="Built-in lab SOP and planning guidance.",
        reference_type="built_in_guidance",
        reference_text=(
            built_in_reference_text(
                "Internal lab pretest guidance",
                "Global safety defaults, thermocouple placement, objective minimum packages, RPT playbook, and approved equipment defaults.",
            )
        ),
    )
    append_reference(
        key="decision_relation_model",
        source_type="local_decision_relation_model",
        source_id="decision_relation_model_v0_1",
        preferred_for="source precedence and release-review rules for controlled planning",
        title="Planning governance guidance",
        visibility_note="Built-in planning governance guidance.",
        reference_type="built_in_guidance",
        reference_text=(
            built_in_reference_text(
                "Internal planning governance guidance",
                "Source precedence and release-review rules for controlled planning.",
            )
        ),
    )

    try:
        if chemistry:
            chemistry_profile = get_chemistry_profile(chemistry)
            payload["chemistry_profile"] = chemistry_profile
            append_reference(
                key="chemistry_profile",
                source_type="local_registry",
                source_id=chemistry_profile.get("id"),
                preferred_for="chemistry-backed planning constraints from the local registry",
                title=f"Chemistry registry - {chemistry_profile.get('label', 'Unknown chemistry')}",
                visibility_note="Built-in governed chemistry registry entry.",
                reference_type="built_in_guidance",
                reference_text=(
                    built_in_reference_text(
                        "Internal chemistry constraints",
                        f"{chemistry_profile.get('label', 'Unknown chemistry')} cells.",
                    )
                ),
            )
        effective_instrument = normalize_optional_text(instrument) or normalize_optional_text(
            resolved_instrument
        )
        if effective_instrument:
            equipment_rule = get_equipment_rule(effective_instrument)
            payload["equipment_rule"] = equipment_rule
            append_reference(
                key="equipment_rule",
                source_type="local_equipment_rule",
                source_id=_rule_reference_identifier(equipment_rule),
                preferred_for="instrument limits and logging constraints from the local equipment rule",
                title=str(equipment_rule.get("label") or "Equipment rule"),
                visibility_note="Built-in governed equipment rule.",
                reference_type="built_in_guidance",
                reference_text=(
                    built_in_reference_text(
                        "Internal equipment constraints",
                        f"{equipment_rule.get('label', 'Unknown instrument')}.",
                    )
                ),
            )
        if thermal_chamber:
            chamber_rule = get_thermal_chamber_rule(thermal_chamber)
            payload["thermal_chamber_rule"] = chamber_rule
            append_reference(
                key="thermal_chamber_rule",
                source_type="local_thermal_chamber_rule",
                source_id=_rule_reference_identifier(chamber_rule),
                preferred_for="thermal chamber operating range and hazard envelope constraints",
                title=str(chamber_rule.get("label") or "Thermal chamber rule"),
                visibility_note="Built-in governed thermal chamber rule.",
                reference_type="built_in_guidance",
                reference_text=(
                    built_in_reference_text(
                        "Internal thermal chamber constraints",
                        f"{chamber_rule.get('label', 'Unknown chamber')}.",
                    )
                ),
            )
        if objective:
            objective_template = get_objective_template(objective)
            payload["objective_template"] = objective_template
            payload["safety_checklist"] = get_safety_checklist(
                objective,
                thermal_chamber=thermal_chamber,
            )
            objective_guidance = get_pretest_objective_guidance(objective)
            if objective_guidance is not None:
                payload["pretest_guidance"]["objective_guidance"] = objective_guidance
            if normalize_objective_key(objective) in {"cycle_life", "rpt", "soh_modeling", "calendar_ageing"}:
                payload["pretest_guidance"]["rpt_playbook"] = get_pretest_rpt_playbook()
            append_reference(
                key="objective_template",
                source_type="local_objective_template",
                source_id=objective_template.get("id"),
                preferred_for="objective-level planning intent and checklist scope from the local registry",
                title=f"Objective template - {objective_template.get('label', objective)}",
                visibility_note="Built-in governed objective template.",
                reference_type="built_in_guidance",
                reference_text=(
                    built_in_reference_text(
                        "Internal planning template",
                        f"{objective_template.get('label', objective)}.",
                    )
                ),
            )
    except KeyError as exc:
        normalized_objective = normalize_objective_key(objective) if objective else None
        if (
            objective
            and normalized_objective is not None
            and chemistry is None
            and instrument is None
            and thermal_chamber is None
        ):
            kb = load_kb()
            available_objectives = sorted(
                set(kb["objective_templates"].keys())
                | set(kb.get("pretest_assistant_guidance", {}).get("objective_minimum_packages", {}).keys())
            )
            return _json_dumps(
                {
                    "status": "not_applicable",
                    "workspace_root": _display_repo_root(),
                    "pretest_guidance": payload["pretest_guidance"],
                    "requested_objective": objective,
                    "normalized_objective": normalized_objective,
                    "message": (
                        f"No controlled objective template is registered for `{objective}`. "
                        "This request is better handled through curated literature evidence or a future DOE-specific workflow asset."
                    ),
                    "available_objectives": available_objectives,
                    "recommended_tool": "search_knowledge_evidence_cards",
                    "trust_level": "advisory_handoff",
                    "ui_markdown": "\n".join(
                        [
                            "## Battery Knowledge Handoff",
                            "",
                            f"- Requested objective: `{objective}`",
                            f"- Normalized objective key: `{normalized_objective}`",
                            "- Controlled objective status: not registered in the current battery knowledge layer",
                            "- Recommended next step: use curated literature evidence instead of the controlled objective registry for this question.",
                        ]
                    ),
                }
            )

        kb = load_kb()
        available_objectives = sorted(
            set(kb["objective_templates"].keys())
            | set(kb.get("pretest_assistant_guidance", {}).get("objective_minimum_packages", {}).keys())
        )
        return _tool_error(
            str(exc),
            error_type="unknown_lookup_key",
            suggestions=[
                "Available chemistries: " + ", ".join(sorted(kb["chemistry_profiles"].keys())),
                "Available instruments: " + ", ".join(list_instrument_rule_keys()),
                "Available thermal chambers: " + ", ".join(list_thermal_chamber_rule_keys()),
                "Available objectives: " + ", ".join(available_objectives),
            ],
        )

    if len(payload) == 2:
        payload["hint"] = "Provide chemistry, instrument, thermal_chamber, or objective to load a focused rule pack."

    payload["lab_default_context"] = lab_default_context
    if preflight_thermal_chamber_note:
        payload["warnings"] = [preflight_thermal_chamber_note]
    payload["planning_mode"] = "knowledge_preflight_mode"
    payload["controlled_planning_state"] = _build_controlled_planning_state(
        status="preflight_loaded",
        planning_mode="knowledge_preflight_mode",
        satisfied_by=["load_battery_knowledge"],
        recommended_sources=["plan_standard_test", "design_battery_protocol"],
    )
    payload["response_policy"] = _build_planning_response_policy(
        planning_mode="knowledge_preflight_mode",
        allow_step_level_protocol=False,
        allow_generic_placeholders=False,
        must_request_missing_inputs=False,
        references_section_required=bool(answer_references),
    )
    citation_lookup = {
        item["reference_key"]: item["citation_token"]
        for item in answer_references
    }
    payload["answer_references"] = answer_references
    payload["answer_citation_map"] = {
        "pretest_guidance": citation_lookup.get("pretest_guidance"),
        "decision_relation_model": citation_lookup.get("decision_relation_model"),
        "chemistry_profile": citation_lookup.get("chemistry_profile"),
        "equipment_rule": citation_lookup.get("equipment_rule"),
        "thermal_chamber_rule": citation_lookup.get("thermal_chamber_rule"),
        "objective_template": citation_lookup.get("objective_template"),
        "claim_bindings": {
            "authority_and_precedence": [
                token
                for token in (
                    citation_lookup.get("pretest_guidance"),
                    citation_lookup.get("decision_relation_model"),
                )
                if token
            ],
            "equipment_defaults": [
                token
                for token in (
                    citation_lookup.get("equipment_rule"),
                    citation_lookup.get("thermal_chamber_rule"),
                    citation_lookup.get("pretest_guidance"),
                )
                if token
            ],
        },
        "constraint_sources": {
            "pretest_assistant_guidance": citation_lookup.get("pretest_guidance"),
            "equipment_rule": citation_lookup.get("equipment_rule"),
            "thermal_chamber_rule": citation_lookup.get("thermal_chamber_rule"),
            "chemistry_profile": citation_lookup.get("chemistry_profile"),
        },
    }
    payload["references_markdown"] = build_grouped_reference_markdown(
        answer_references,
        include_section_heading=True,
    )

    return _json_dumps(payload)


def _load_battery_knowledge_tool(
    chemistry: Annotated[
        str | None,
        "Chemistry key, for example lfp or nmc811.",
    ] = None,
    instrument: Annotated[
        str | None,
        "Optional equipment key such as arbin_bt2000 or biologic_bcs815.",
    ] = None,
    thermal_chamber: Annotated[
        str | None,
        "Optional thermal chamber key such as binder_lit_mk.",
    ] = None,
    objective: Annotated[
        str | None,
        "Objective key such as cycle_life, hppc, or rate_capability.",
    ] = None,
    runtime: ToolRuntime = None,
) -> str:
    return _load_battery_knowledge_impl(
        chemistry=chemistry,
        instrument=instrument,
        thermal_chamber=thermal_chamber,
        objective=objective,
        runtime=runtime,
    )


load_battery_knowledge = StructuredTool.from_function(
    name="load_battery_knowledge",
    description="Load structured battery knowledge and constraints from the local knowledge base.",
    func=_load_battery_knowledge_tool,
)


@tool
def get_demo_assets() -> str:
    """List the local demo assets, including sample files and available knowledge-base keys."""

    return _json_dumps(list_demo_assets())


@tool
def describe_lab_backend_framework() -> str:
    """Describe the current backend scaffold and the structured assets that should be filled next."""

    return _json_dumps(summarize_workflow_assets())


@tool(args_schema=EquipmentManualSearchRequest)
def search_equipment_manual_knowledge(query: str, limit: int = 5) -> str:
    """Search curated equipment-manual assets such as tester, chamber, and EIS setup summaries."""

    return _json_dumps(search_equipment_manual_assets(query, limit=limit))


@tool(args_schema=EquipmentManualAssetRequest)
def load_equipment_manual_knowledge(asset_id: str) -> str:
    """Load one structured equipment-manual asset together with its summary markdown."""

    try:
        payload = get_equipment_manual_asset(asset_id)
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_equipment_manual_asset",
            suggestions=[
                "Use search_equipment_manual_knowledge first to discover available equipment-manual asset ids.",
            ],
        )

    manual = payload["manual"]
    summary_markdown = payload["summary_markdown"]
    payload["ui_markdown"] = "\n".join(
        [
            f"## Equipment Manual: {manual['manufacturer']} {manual['model']}",
            "",
            f"- Asset id: `{manual['asset_id']}`",
            f"- Equipment type: `{manual['equipment_type']}`",
            f"- Page spans used: {', '.join(manual.get('page_spans_used', [])) or 'Not recorded'}",
            f"- Citation: {manual.get('answer_reference_markdown') or 'Unavailable'}",
            "",
            "### Summary",
            summary_markdown or "No summary markdown stored for this asset.",
        ]
    )
    return _json_dumps(payload)


@tool(args_schema=LiteratureEvidenceSearchRequest)
def search_knowledge_evidence_cards(query: str, limit: int = 3) -> str:
    """Search all curated domain knowledge evidence cards (handbook protocols + research literature) and return source-linked, page-specific summaries."""

    return _json_dumps(search_literature_evidence(query, limit=limit))


# Backward-compat alias — keep old name functional in case any session references it
search_literature_evidence_cards = search_knowledge_evidence_cards


@tool(args_schema=LiteratureSourceRequest)
def load_knowledge_source(source_id: str) -> str:
    """Load one curated knowledge source summary (handbook chapter or research paper) together with its evidence cards."""

    try:
        payload = get_literature_source(source_id)
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_knowledge_source",
            suggestions=[
                "Use search_knowledge_evidence_cards first to discover available source ids.",
            ],
        )

    source = payload["source"]
    cards = payload.get("evidence_cards", [])
    summary_markdown = payload.get("summary_markdown", "")
    payload["ui_markdown"] = "\n".join(
        [
            f"## Knowledge Source: {source['title']}",
            "",
            f"- Source id: `{source['source_id']}`",
            f"- Citation: {source.get('linked_reference_markdown', 'See summary')}",
            f"- Evidence cards: {len(cards)}",
            "",
            "### Card Titles",
            "\n".join(f"- {card['title']} (`{card['card_id']}`)" for card in cards) or "- None.",
            "",
            "### Summary",
            summary_markdown or "No summary markdown stored for this source.",
        ]
    )
    return _json_dumps(payload)


# Backward-compat alias
load_literature_source = load_knowledge_source


def _design_battery_protocol_impl(
    objective: str,
    chemistry: str | None = None,
    selected_cell_id: str | None = None,
    instrument: str | None = None,
    thermal_chamber: str | None = None,
    form_factor: str | None = None,
    target_temperature_c: float = 25.0,
    charge_c_rate: float = 0.5,
    discharge_c_rate: float = 0.5,
    cycle_count: int = 100,
    method_inputs_json: str = "{}",
    operator_notes: str = "",
    runtime: ToolRuntime | None = None,
    _transient_selected_cell_override: dict[str, Any] | None = None,
) -> str:
    """Draft a starter battery test protocol from structured assets and controlled constraints."""

    objective_key = normalize_objective_key(objective)
    resolved_instrument, resolved_thermal_chamber, lab_default_context = (
        _resolve_planning_defaults_from_runtime(
            instrument=instrument,
            thermal_chamber=thermal_chamber,
            runtime=runtime,
        )
    )
    effective_pretest_defaults = _build_effective_pretest_equipment_defaults(
        lab_default_context
    )
    (
        resolved_thermal_chamber,
        lab_default_context,
        deferred_thermal_chamber_note,
    ) = _normalize_default_thermal_chamber_usage(
        planning_key=objective_key,
        target_temperature_c=target_temperature_c,
        explicit_thermal_chamber=thermal_chamber,
        resolved_thermal_chamber=resolved_thermal_chamber,
        lab_default_context=lab_default_context,
    )

    kb = load_kb()
    effective_selected_cell_id, transient_selected_cell_record = _resolve_selected_cell_context(
        selected_cell_id=selected_cell_id,
        runtime=runtime,
        transient_selected_cell_override=_transient_selected_cell_override,
    )

    if normalize_optional_text(resolved_instrument) is None:
        parameter_request = build_parameter_request_payload(
            request_id=f"{objective_key}::instrument",
            method={"id": objective_key, "label": objective_key},
            release_status="blocker_aware_draft",
            missing_fields=["instrument"],
            requested_conditions={
                "target_temperature_c": target_temperature_c,
                "charge_c_rate": charge_c_rate,
                "discharge_c_rate": discharge_c_rate,
            },
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            (
                next_chemistry,
                next_selected_cell_id,
                next_instrument,
                next_thermal_chamber,
                next_method_inputs,
                next_transient_selected_cell_record,
            ) = _merge_parameter_answers(
                chemistry=chemistry,
                selected_cell_id=selected_cell_id,
                instrument=instrument,
                thermal_chamber=thermal_chamber,
                method_inputs={},
                transient_selected_cell_record=transient_selected_cell_record,
                answers=resumed_answers,
            )
            return _design_battery_protocol_impl(
                objective=objective,
                chemistry=next_chemistry,
                selected_cell_id=next_selected_cell_id,
                instrument=next_instrument,
                thermal_chamber=next_thermal_chamber,
                form_factor=form_factor,
                target_temperature_c=target_temperature_c,
                charge_c_rate=charge_c_rate,
                discharge_c_rate=discharge_c_rate,
                cycle_count=cycle_count,
                method_inputs_json=_json_dumps(next_method_inputs),
                operator_notes=operator_notes,
                runtime=runtime,
                _transient_selected_cell_override=next_transient_selected_cell_record,
            )
        return _tool_error(
            "Instrument information is required to finalize an instrument-constrained protocol draft.",
            error_type="missing_instrument",
            suggestions=[
                "Available instruments: " + ", ".join(list_instrument_rule_keys()),
                "Use load_battery_knowledge with the available objective and chemistry/selected cell context before giving any fallback guidance.",
                "Do not invent instrument-specific pulse, logging, or compliance defaults from memory when the controlled instrument is still unresolved.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="missing_instrument",
                    missing_inputs=["instrument"],
                    recommended_sources=["load_battery_knowledge", "design_battery_protocol"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "ui_markdown": _build_blocked_experiment_plan_markdown(
                    objective_or_method_label=f"Objective: {objective_key}",
                    release_status="blocker_aware_draft",
                    known_constraints=[
                        ["Objective", objective_key, "requested_objective", "fixed", ""],
                        ["Instrument", "missing", "user_input_required", "blocked", "Select or provide the cycler/instrument before release."],
                        ["Target temperature", f"{target_temperature_c:.1f} C", "requested_conditions", "fixed", ""],
                    ],
                    pending_confirmations=[
                        [
                            "instrument",
                            "safety_boundary",
                            "execution_blocker",
                            "The instrument defines the available current, voltage, and logging limits.",
                            "Provide the instrument key or lab-default cycler selection.",
                        ]
                    ],
                ),
            },
        )

    if (
        normalize_optional_text(chemistry) is None
        and effective_selected_cell_id is None
        and transient_selected_cell_record is None
    ):
        parameter_request = build_parameter_request_payload(
            request_id=f"{objective_key}::chemistry_or_selected_cell",
            method={"id": objective_key, "label": objective_key},
            release_status="blocker_aware_draft",
            missing_fields=["chemistry_or_selected_cell"],
            requested_conditions={
                "target_temperature_c": target_temperature_c,
                "charge_c_rate": charge_c_rate,
                "discharge_c_rate": discharge_c_rate,
            },
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            (
                next_chemistry,
                next_selected_cell_id,
                next_instrument,
                next_thermal_chamber,
                next_method_inputs,
                next_transient_selected_cell_record,
            ) = _merge_parameter_answers(
                chemistry=chemistry,
                selected_cell_id=selected_cell_id,
                instrument=resolved_instrument,
                thermal_chamber=thermal_chamber,
                method_inputs={},
                transient_selected_cell_record=transient_selected_cell_record,
                answers=resumed_answers,
            )
            return _design_battery_protocol_impl(
                objective=objective,
                chemistry=next_chemistry,
                selected_cell_id=next_selected_cell_id,
                instrument=next_instrument,
                thermal_chamber=next_thermal_chamber,
                form_factor=form_factor,
                target_temperature_c=target_temperature_c,
                charge_c_rate=charge_c_rate,
                discharge_c_rate=discharge_c_rate,
                cycle_count=cycle_count,
                method_inputs_json=_json_dumps(next_method_inputs),
                operator_notes=operator_notes,
                runtime=runtime,
                _transient_selected_cell_override=next_transient_selected_cell_record,
            )
        return _tool_error(
            "Provide either a registry chemistry or a selected_cell_id before drafting the protocol.",
            error_type="missing_planning_subject",
            suggestions=[
                "Available chemistries: " + ", ".join(sorted(kb["chemistry_profiles"].keys())),
                "Use load_imported_cell_record with a commercial cell id when chemistry is still unknown.",
                "Use load_battery_knowledge with the objective and instrument context before giving any advisory fallback, but keep chemistry-specific steps unresolved until chemistry or selected_cell_id is provided.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="missing_planning_subject",
                    missing_inputs=["chemistry_or_selected_cell"],
                    recommended_sources=["load_imported_cell_record", "load_battery_knowledge"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "ui_markdown": _build_blocked_experiment_plan_markdown(
                    objective_or_method_label=f"Objective: {objective_key}",
                    release_status="blocker_aware_draft",
                    known_constraints=[
                        ["Objective", objective_key, "requested_objective", "fixed", ""],
                        ["Chemistry or selected cell", "missing", "user_input_required", "blocked", "Provide either a governed chemistry or a selected cell reference."],
                        ["Instrument", resolved_instrument, "instrument", "fixed", ""],
                    ],
                    pending_confirmations=[
                        [
                            "chemistry_or_selected_cell",
                            "method_core",
                            "execution_blocker",
                            "The planner cannot lock chemistry-specific or selected-cell constraints without a defined planning subject.",
                            "Provide a registry chemistry or selected cell.",
                        ]
                    ],
                ),
            },
        )

    try:
        objective_template = get_objective_template(objective_key)
        method_definition = get_default_method_for_objective(objective_key)
        if method_definition is None:
            return _tool_error(
                f"No default method registry entry is mapped to objective '{objective_key}'.",
                error_type="missing_method_registry_entry",
            )
        method_inputs = _parse_method_inputs_json(method_inputs_json)
        payload = plan_method_protocol(
            method_id=method_definition["id"],
            chemistry=chemistry,
            selected_cell_id=effective_selected_cell_id,
            transient_selected_cell_record=transient_selected_cell_record,
            instrument=resolved_instrument,
            thermal_chamber=resolved_thermal_chamber,
            target_temperature_c=target_temperature_c,
            charge_c_rate=charge_c_rate,
            discharge_c_rate=discharge_c_rate,
            form_factor=form_factor,
            cycle_count=cycle_count,
            operator_notes=operator_notes,
            method_inputs=method_inputs,
            approved_equipment_defaults=effective_pretest_defaults,
        )
        if (
            payload.get("release_status") == "blocker_aware_draft"
            and isinstance(payload.get("parameter_request"), dict)
        ):
            resumed_answers = _await_parameter_request_answers(
                payload.get("parameter_request"),
                runtime,
            )
            if resumed_answers is not None:
                (
                    next_chemistry,
                    next_selected_cell_id,
                    next_instrument,
                    next_thermal_chamber,
                    next_method_inputs,
                    next_transient_selected_cell_record,
                ) = _merge_parameter_answers(
                    chemistry=chemistry,
                    selected_cell_id=selected_cell_id,
                    instrument=resolved_instrument,
                    thermal_chamber=thermal_chamber,
                    method_inputs=method_inputs,
                    transient_selected_cell_record=transient_selected_cell_record,
                    answers=resumed_answers,
                )
                return _design_battery_protocol_impl(
                    objective=objective,
                    chemistry=next_chemistry,
                    selected_cell_id=next_selected_cell_id,
                    instrument=next_instrument,
                    thermal_chamber=next_thermal_chamber,
                    form_factor=form_factor,
                    target_temperature_c=target_temperature_c,
                    charge_c_rate=charge_c_rate,
                    discharge_c_rate=discharge_c_rate,
                    cycle_count=cycle_count,
                    method_inputs_json=_json_dumps(next_method_inputs),
                    operator_notes=operator_notes,
                    runtime=runtime,
                    _transient_selected_cell_override=next_transient_selected_cell_record,
                )
        equipment_rule = get_equipment_rule(resolved_instrument)
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_protocol_input",
            suggestions=[
                "Available objectives: " + ", ".join(sorted(kb["objective_templates"].keys())),
                "Available chemistries: " + ", ".join(sorted(kb["chemistry_profiles"].keys())),
                "Available instruments: " + ", ".join(list_instrument_rule_keys()),
                "Available thermal chambers: " + ", ".join(list_thermal_chamber_rule_keys()),
                "Use load_battery_knowledge before drafting any fallback steps so the answer stays inside the controlled asset layer.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="unknown_protocol_input",
                    recommended_sources=["load_battery_knowledge"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
            },
        )
    except MissingMethodInputsError as exc:
        parameter_request = build_parameter_request_payload(
            request_id=f"{exc.method_id}::{'-'.join(exc.missing_fields)}",
            method={"id": exc.method_id, "label": exc.method_id},
            release_status="blocker_aware_draft",
            missing_fields=exc.missing_fields,
            input_contract=exc.input_contract,
            requested_conditions=exc.declared_inputs,
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            (
                next_chemistry,
                next_selected_cell_id,
                next_instrument,
                next_thermal_chamber,
                next_method_inputs,
                next_transient_selected_cell_record,
            ) = _merge_parameter_answers(
                chemistry=chemistry,
                selected_cell_id=selected_cell_id,
                instrument=resolved_instrument,
                thermal_chamber=thermal_chamber,
                method_inputs=method_inputs if "method_inputs" in locals() else {},
                transient_selected_cell_record=transient_selected_cell_record,
                answers=resumed_answers,
            )
            return _design_battery_protocol_impl(
                objective=objective,
                chemistry=next_chemistry,
                selected_cell_id=next_selected_cell_id,
                instrument=next_instrument,
                thermal_chamber=next_thermal_chamber,
                form_factor=form_factor,
                target_temperature_c=target_temperature_c,
                charge_c_rate=charge_c_rate,
                discharge_c_rate=discharge_c_rate,
                cycle_count=cycle_count,
                method_inputs_json=_json_dumps(next_method_inputs),
                operator_notes=operator_notes,
                runtime=runtime,
                _transient_selected_cell_override=next_transient_selected_cell_record,
            )
        return _tool_error(
            str(exc),
            error_type="planning_validation_error",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in list_method_profiles().get("structured_methods", [])),
                "Use method_inputs_json for method-specific fields such as target_soc, checkpoint_interval, target_voltage, hold_duration, profile_family, or stop_criterion.",
                "Do not replace blocked method-specific inputs with model-authored defaults. Keep those fields unresolved until they are supplied or loaded from a controlled asset.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="planning_validation_error",
                    missing_inputs=exc.missing_fields,
                    recommended_sources=["load_battery_knowledge", "design_battery_protocol"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "ui_markdown": _build_blocked_experiment_plan_markdown(
                    objective_or_method_label=f"Objective: {objective_key}",
                    release_status="blocker_aware_draft",
                    known_constraints=[
                        ["Objective", objective_key, "requested_objective", "fixed", ""],
                        ["Instrument", resolved_instrument, "instrument", "fixed", ""],
                        ["Target temperature", f"{target_temperature_c:.1f} C", "requested_conditions", "fixed", ""],
                    ],
                    pending_confirmations=[
                        [
                            field_name,
                            next(
                                (
                                    question.get("severity")
                                    for question in parameter_request.get("questions", [])
                                    if question.get("key") == field_name
                                ),
                                "method_core",
                            ),
                            "execution_blocker",
                            next(
                                (
                                    question.get("why_needed")
                                    for question in parameter_request.get("questions", [])
                                    if question.get("key") == field_name
                                ),
                                f"{field_name} is required before release.",
                            ),
                            "Provide the missing value in the parameter request popup.",
                        ]
                        for field_name in exc.missing_fields
                    ],
                ),
            },
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="planning_validation_error",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in list_method_profiles().get("structured_methods", [])),
                "Use method_inputs_json for method-specific fields such as target_soc, checkpoint_interval, target_voltage, hold_duration, profile_family, or stop_criterion.",
                "Do not replace blocked method-specific inputs with model-authored pulse/rest/SOC defaults. Keep those fields unresolved until they are supplied or loaded from a controlled asset.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="planning_validation_error",
                    recommended_sources=["load_battery_knowledge", "design_battery_protocol"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
            },
        )

    warnings = list(payload.get("warnings", []))
    instrument_default_source = lab_default_context["applied_fields"].get("instrument")
    if instrument_default_source == "settings_lab_defaults":
        warnings.append(
            f"Instrument resolved from Settings lab defaults: `{resolved_instrument}`."
        )
    elif instrument_default_source == "pretest_guidance_default":
        warnings.append(
            f"Instrument resolved from approved default guidance: `{resolved_instrument}`."
        )
    thermal_chamber_default_source = lab_default_context["applied_fields"].get("thermal_chamber")
    if thermal_chamber_default_source == "settings_lab_defaults":
        warnings.append(
            f"Thermal chamber resolved from Settings lab defaults: `{resolved_thermal_chamber}`."
        )
    elif thermal_chamber_default_source == "pretest_guidance_default":
        warnings.append(
            f"Thermal chamber resolved from approved default guidance: `{resolved_thermal_chamber}`."
        )
    elif deferred_thermal_chamber_note:
        warnings.append(deferred_thermal_chamber_note)
    default_eis_instrument_label = lab_default_context["lab_defaults"].get(
        "default_eis_instrument_label"
    )
    default_eis_instrument_id = lab_default_context["lab_defaults"].get(
        "default_eis_instrument_id"
    )
    default_eis_setup_notes = lab_default_context["lab_defaults"].get(
        "default_eis_setup_notes"
    )
    if default_eis_instrument_label or default_eis_instrument_id:
        warnings.append(
            "EIS-oriented requests may use the Settings default EIS instrument: "
            f"`{default_eis_instrument_label or default_eis_instrument_id}`."
        )
    if default_eis_setup_notes:
        warnings.append(
            "Settings default EIS setup notes available: "
            f"`{default_eis_setup_notes}`."
        )

    log_interval_s = max(
        objective_template["default_log_interval_seconds"],
        equipment_rule["min_sampling_seconds"],
    )
    if log_interval_s != objective_template["default_log_interval_seconds"]:
        warnings.append(
            f"Logging interval increased to {log_interval_s} s to respect the instrument minimum sampling interval."
        )
    if equipment_rule["temperature_channels"] < 2:
        warnings.append("Temperature channel coverage is minimal. Review thermocouple allocation before release.")

    applied_constraints = dict(payload.get("applied_constraints", {}))
    applied_constraints["logging_interval_s"] = log_interval_s
    constraint_sources = dict(payload.get("constraint_sources", {}))
    constraint_sources["logging_interval_s"] = "objective_template_and_equipment_rule"

    protocol_name = str(payload.get("protocol_name") or method_definition["label"])
    protocol_name_parts = protocol_name.split(" - ", 1)
    if len(protocol_name_parts) == 2:
        protocol_name = f"{objective_template['label']} - {protocol_name_parts[1]}"
    else:
        protocol_name = f"{objective_template['label']} - {protocol_name}"

    protocol = {
        **payload,
        "protocol_name": protocol_name,
        "status": "draft",
        "objective": objective_template["label"],
        "chemistry": payload.get("chemistry_label", "unknown"),
        "chemistry_id": payload.get("chemistry_id"),
        "instrument": equipment_rule["label"],
        "thermal_chamber": payload.get("thermal_chamber"),
        "form_factor": (
            payload.get("metadata", {}).get("form_factor")
            or payload.get("requested_conditions", {}).get("form_factor")
        ),
        "steps": list(payload.get("protocol_steps", [])),
        "qa_checklist": list(payload.get("safety_checklist", [])),
        "report_focus": objective_template["report_focus"],
        "warnings": warnings,
        "applied_constraints": applied_constraints,
        "constraint_sources": constraint_sources,
        "lab_default_context": lab_default_context,
        "planning_mode": payload.get("planning_mode", "grounded_protocol_mode"),
        "controlled_planning_state": payload.get("controlled_planning_state"),
        "response_policy": payload.get("response_policy"),
        "answer_references": payload.get("answer_references", []),
        "answer_citation_map": payload.get("answer_citation_map", {}),
        "references_markdown": payload.get("references_markdown", ""),
        "step_provenance_summary": payload.get("step_provenance_summary", {}),
    }

    return _json_dumps(protocol)


def _design_battery_protocol_tool(
    objective: Annotated[
        str,
        "Objective key such as cycle_life, hppc, rate_capability, or soc_ocv.",
    ],
    chemistry: Annotated[
        str | None,
        "Optional chemistry key such as lfp, nmc811, or nca.",
    ] = None,
    selected_cell_id: Annotated[
        str | None,
        "Optional imported cell catalog id such as Panasonic_NCR18650BF for selected-cell planning flows.",
    ] = None,
    instrument: Annotated[
        str | None,
        "Optional equipment key such as arbin_bt2000. Required before the plan can be finalized against instrument limits.",
    ] = None,
    thermal_chamber: Annotated[
        str | None,
        "Optional thermal chamber key such as binder_lit_mk.",
    ] = None,
    form_factor: Annotated[
        str | None,
        "Optional form factor override such as cylindrical, pouch, or prismatic.",
    ] = None,
    target_temperature_c: Annotated[
        float,
        "Target planning temperature in degrees Celsius.",
    ] = 25.0,
    charge_c_rate: Annotated[
        float,
        "Charge rate in C used when the method template requires one.",
    ] = 0.5,
    discharge_c_rate: Annotated[
        float,
        "Discharge rate in C used when the method template requires one.",
    ] = 0.5,
    cycle_count: Annotated[
        int,
        "Cycle or block count placeholder used for objective defaults.",
    ] = 100,
    method_inputs_json: Annotated[
        str,
        "JSON object for method-specific fields such as target_soc, checkpoint_interval, target_voltage, or hold_duration.",
    ] = "{}",
    operator_notes: Annotated[
        str,
        "Optional planning notes.",
    ] = "",
    runtime: ToolRuntime = None,
) -> str:
    return _design_battery_protocol_impl(
        objective=objective,
        chemistry=chemistry,
        selected_cell_id=selected_cell_id,
        instrument=instrument,
        thermal_chamber=thermal_chamber,
        form_factor=form_factor,
        target_temperature_c=target_temperature_c,
        charge_c_rate=charge_c_rate,
        discharge_c_rate=discharge_c_rate,
        cycle_count=cycle_count,
        method_inputs_json=method_inputs_json,
        operator_notes=operator_notes,
        runtime=runtime,
    )


design_battery_protocol = StructuredTool.from_function(
    name="design_battery_protocol",
    description="Draft a starter battery test protocol from structured assets and controlled constraints.",
    func=_design_battery_protocol_tool,
)


def _parse_raw_cycler_export_impl(
    file_path: str,
    attachment_text: str | None = None,
    adapter_id: str | None = None,
    preview_rows: int = 8,
    runtime: ToolRuntime | None = None,
) -> str:
    normalized_path = _normalize_thread_file_path(file_path)

    try:
        if attachment_text is not None and str(attachment_text).strip():
            parse_result = parse_raw_export_text(
                str(attachment_text),
                source_name=normalized_path,
                adapter_id=adapter_id,
            )
        elif normalized_path.startswith("/uploads/"):
            normalized_path, attachment_text = _load_uploaded_thread_file(
                normalized_path,
                None,
                runtime,
            )
            stripped_attachment = attachment_text.lstrip()
            if stripped_attachment.startswith("{") and "placeholder" in stripped_attachment:
                return _tool_error(
                    (
                        f"The uploaded thread file `{normalized_path}` only contains "
                        "attachment metadata, not raw tabular export data."
                    ),
                    error_type="uploaded_thread_file_validation_error",
                    suggestions=[
                        "Upload the raw CSV or TSV export directly so the adapter can parse the tabular rows.",
                        "If you only have Excel output, use a local file path with an explicit adapter_id for now.",
                    ],
                )
            parse_result = parse_raw_export_text(
                attachment_text,
                source_name=normalized_path,
                adapter_id=adapter_id,
            )
        else:
            try:
                resolved_path = resolve_sample_path(file_path)
            except FileNotFoundError:
                local_candidate = Path(file_path)
                if local_candidate.exists():
                    resolved_path = local_candidate.resolve()
                else:
                    raise
            parse_result = parse_raw_export_file(
                resolved_path,
                adapter_id=adapter_id,
            )
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="file_not_found",
            suggestions=[
                "Use an exact `/uploads/...` path from the chat attachment notice.",
                "Or provide a real local CSV/TSV/XLS/XLSX path.",
            ],
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="uploaded_thread_file_not_found",
            suggestions=[
                "Use the exact `/uploads/...` path shown in the attachment notice.",
                "If the export came from another thread, upload it again in the current thread.",
            ],
        )
    except UnknownAdapterError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_adapter_id",
            suggestions=[
                "Supported adapters: " + ", ".join(list_supported_adapter_ids()),
            ],
        )
    except AdapterDetectionError as exc:
        return _tool_error(
            str(exc),
            error_type="adapter_detection_failed",
            suggestions=[
                "Pass an explicit adapter_id such as `arbin_csv_v1`, `neware_csv_v1`, or `generic_battery_tabular_v1`.",
                "For public datasets and spreadsheet previews, the tool can fall back to a generic tabular inspection path when battery-like columns are present.",
                "If `read_file` can open the `/uploads/...` path but this tool cannot, retry parse_raw_cycler_export with the same file_path plus `attachment_text` from read_file.",
            ],
        )
    except AdapterSchemaError as exc:
        return _tool_error(
            str(exc),
            error_type="adapter_schema_error",
            suggestions=[
                "Confirm the file is a supported Arbin or Neware export.",
                "Check that required columns for cycle index, step index, time, current, and voltage are present.",
            ],
        )
    except AdapterReadError as exc:
        return _tool_error(
            str(exc),
            error_type="adapter_read_error",
            suggestions=[
                "Use raw CSV/TSV text exports for auto-detection.",
                "For Excel exports, provide adapter_id explicitly.",
            ],
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="raw_export_validation_error",
        )

    payload = _adapter_result_to_payload(parse_result, preview_rows=preview_rows)
    return _json_dumps(payload)


def _parse_raw_cycler_export_tool(
    file_path: Annotated[
        str,
        "Absolute local file path or uploaded thread file path such as /uploads/<id>-raw-export.csv.",
    ],
    attachment_text: Annotated[
        str | None,
        "Optional raw attachment text or read_file output for the same dataset.",
    ] = None,
    adapter_id: Annotated[
        str | None,
        "Optional explicit adapter id such as arbin_csv_v1 or neware_csv_v1.",
    ] = None,
    preview_rows: Annotated[
        int,
        "How many normalized rows to include in the preview payload.",
    ] = 8,
    runtime: ToolRuntime = None,
) -> str:
    return _parse_raw_cycler_export_impl(
        file_path=file_path,
        attachment_text=attachment_text,
        adapter_id=adapter_id,
        preview_rows=preview_rows,
        runtime=runtime,
    )


parse_raw_cycler_export = StructuredTool.from_function(
    name="parse_raw_cycler_export",
    description="Parse or inspect a battery-data table from a local path, `/uploads/...` thread file, or raw attachment text/read_file output. Use Arbin/Neware normalization when possible and a generic battery-tabular preview fallback otherwise.",
    func=_parse_raw_cycler_export_tool,
    args_schema=RawCyclerParseRequest,
)


def _identify_ecm_parameters_impl(
    file_path: str,
    attachment_text: str | None = None,
    adapter_id: str | None = None,
    ecm_model_id: str = "thevenin_1rc",
    target_pulse_index: int | None = None,
    current_threshold_a: float = 0.02,
    time_column: str | None = None,
    current_column: str | None = None,
    voltage_column: str | None = None,
    runtime: ToolRuntime | None = None,
) -> str:
    if not ECM_IDENTIFICATION_TOOL_ENABLED:
        return _tool_error(
            "ECM parameter identification is temporarily disabled in the current publish build.",
            error_type="ecm_identification_disabled",
            suggestions=[
                "Use parse_raw_cycler_export to inspect and normalize the uploaded dataset.",
                "Keep ECM fitting parked until the governed modeling workflow is rebuilt.",
            ],
        )

    try:
        frame_payload = _load_modeling_frame(
            file_path=file_path,
            attachment_text=attachment_text,
            adapter_id=adapter_id,
            runtime=runtime,
            time_column=time_column,
            current_column=current_column,
            voltage_column=voltage_column,
        )
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="file_not_found",
            suggestions=[
                "Use an exact `/uploads/...` path from the current thread or a real local CSV/TSV/XLS/XLSX path.",
            ],
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="uploaded_thread_file_not_found",
            suggestions=[
                "Use the exact `/uploads/...` path shown in the attachment notice.",
            ],
        )
    except UnknownAdapterError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_adapter_id",
            suggestions=[
                "Supported adapters: " + ", ".join(list_supported_adapter_ids()),
            ],
        )
    except Exception as exc:
        return _tool_error(
            f"Failed to load the ECM modeling dataset: {exc}",
            error_type="ecm_input_error",
            suggestions=[
                "Retry with a raw CSV/TSV export or provide explicit time/current/voltage column names.",
            ],
        )

    if frame_payload.get("status") == "needs_columns":
        missing_mapping_fields = list(frame_payload.get("missing_mapping_fields", []))
        parameter_request = build_parameter_request_payload(
            request_id=f"ecm::{_slugify_path_segment(Path(str(frame_payload['source_name'])).stem)}::columns",
            method={"id": "ecm_parameter_identification", "label": "ECM Parameter Identification"},
            release_status="blocker_aware_draft",
            missing_fields=missing_mapping_fields,
            requested_conditions={
                "time_column": time_column,
                "current_column": current_column,
                "voltage_column": voltage_column,
            },
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            return _identify_ecm_parameters_impl(
                file_path=file_path,
                attachment_text=attachment_text,
                adapter_id=adapter_id,
                ecm_model_id=ecm_model_id,
                target_pulse_index=target_pulse_index,
                current_threshold_a=current_threshold_a,
                time_column=normalize_optional_text(str(resumed_answers.get("time_column") or ""))
                or time_column,
                current_column=normalize_optional_text(
                    str(resumed_answers.get("current_column") or "")
                )
                or current_column,
                voltage_column=normalize_optional_text(
                    str(resumed_answers.get("voltage_column") or "")
                )
                or voltage_column,
                runtime=runtime,
            )

        raw_columns = [str(item) for item in frame_payload.get("raw_columns", [])]
        return _tool_error(
            "The uploaded table could not be mapped to time/current/voltage columns automatically.",
            error_type="ecm_column_mapping_required",
            suggestions=[
                "Provide the column names that correspond to elapsed time, current, and voltage.",
                "If you know the source system, retry with an explicit adapter_id.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="ecm_column_mapping_required",
                    missing_inputs=missing_mapping_fields,
                    recommended_sources=["parse_raw_cycler_export", "identify_ecm_parameters"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "raw_columns": raw_columns,
                "preview_rows": frame_payload.get("preview_rows", []),
                "ui_markdown": _build_blocked_modeling_markdown(
                    title="ECM Identification Blocked",
                    known_context=[
                        ("Source", frame_payload.get("source_name")),
                        ("ECM model", ecm_model_id),
                        ("Raw columns", ", ".join(raw_columns[:12]) or "none"),
                    ],
                    missing_inputs=[
                        "Map the source columns that contain elapsed time, current, and voltage."
                    ],
                    notes=[
                        str(frame_payload.get("parse_error") or "").strip()
                    ],
                ),
            },
        )

    try:
        ecm_payload = fit_ecm_parameters_from_frame(
            frame_payload["frame"],
            ecm_model_id=ecm_model_id,
            current_threshold_a=current_threshold_a,
            target_pulse_index=target_pulse_index,
        )
    except EcmPulseSelectionRequiredError as exc:
        parameter_request = build_parameter_request_payload(
            request_id=f"ecm::{_slugify_path_segment(Path(str(frame_payload['source_name'])).stem)}::pulse",
            method={"id": "ecm_parameter_identification", "label": "ECM Parameter Identification"},
            release_status="blocker_aware_draft",
            missing_fields=["target_pulse_index"],
            input_contract={
                "source_example_defaults": {
                    "target_pulse_index": 1,
                }
            },
            requested_conditions={
                "target_pulse_index": target_pulse_index,
                "current_threshold_a": current_threshold_a,
            },
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            next_target_pulse_index = resumed_answers.get("target_pulse_index")
            return _identify_ecm_parameters_impl(
                file_path=file_path,
                attachment_text=attachment_text,
                adapter_id=adapter_id,
                ecm_model_id=ecm_model_id,
                target_pulse_index=int(next_target_pulse_index)
                if next_target_pulse_index is not None
                else target_pulse_index,
                current_threshold_a=current_threshold_a,
                time_column=time_column,
                current_column=current_column,
                voltage_column=voltage_column,
                runtime=runtime,
            )

        candidate_notes = [
            (
                f"Pulse {item['pulse_index']}: cycle={item.get('cycle_index')}, "
                f"step={item.get('step_index')}, mode={item.get('mode')}, "
                f"duration={item.get('duration_s')} s, mean current={item.get('mean_current_a')} A"
            )
            for item in exc.candidates
        ]
        return _tool_error(
            str(exc),
            error_type="ecm_pulse_selection_required",
            suggestions=[
                "Choose the pulse block that best represents the HPPC or DCR segment you want to parameterize.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="ecm_pulse_selection_required",
                    missing_inputs=["target_pulse_index"],
                    recommended_sources=["identify_ecm_parameters"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "pulse_candidates": exc.candidates,
                "ui_markdown": _build_blocked_modeling_markdown(
                    title="ECM Identification Needs Pulse Selection",
                    known_context=[
                        ("Source", frame_payload.get("source_name")),
                        ("ECM model", ecm_model_id),
                        ("Detected pulse count", len(exc.candidates)),
                    ],
                    missing_inputs=[
                        "Choose the target pulse index to use for the ECM fit."
                    ],
                    notes=candidate_notes,
                ),
            },
        )
    except EcmModelSelectionError as exc:
        return _tool_error(
            str(exc),
            error_type="unknown_ecm_model",
            suggestions=[
                "The current implementation supports `r0_only` and `thevenin_1rc`.",
            ],
        )
    except KeyError as exc:
        return _tool_error(
            str(exc),
            error_type="ecm_schema_error",
            suggestions=[
                "Confirm the dataset includes elapsed time, current, and voltage traces after normalization.",
                "If adapter normalization was incomplete, provide explicit time/current/voltage column names.",
            ],
        )
    except ValueError as exc:
        message = str(exc)
        if "No pulse-like current segments were detected" in message:
            parameter_request = build_parameter_request_payload(
                request_id=f"ecm::{_slugify_path_segment(Path(str(frame_payload['source_name'])).stem)}::threshold",
                method={"id": "ecm_parameter_identification", "label": "ECM Parameter Identification"},
                release_status="blocker_aware_draft",
                missing_fields=["current_threshold_a"],
                input_contract={
                    "source_example_defaults": {
                        "current_threshold_a": 0.02,
                    }
                },
                requested_conditions={
                    "current_threshold_a": current_threshold_a,
                },
            )
            resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
            if resumed_answers is not None and resumed_answers.get("current_threshold_a") is not None:
                return _identify_ecm_parameters_impl(
                    file_path=file_path,
                    attachment_text=attachment_text,
                    adapter_id=adapter_id,
                    ecm_model_id=ecm_model_id,
                    target_pulse_index=target_pulse_index,
                    current_threshold_a=float(resumed_answers["current_threshold_a"]),
                    time_column=time_column,
                    current_column=current_column,
                    voltage_column=voltage_column,
                    runtime=runtime,
                )

            return _tool_error(
                message,
                error_type="ecm_pulse_detection_failed",
                suggestions=[
                    "Lower the pulse current threshold if the active pulse amplitude is small.",
                    "Confirm the dataset actually contains a pulse or HPPC segment rather than a flat cycle summary.",
                ],
                extra_payload={
                    "planning_mode": "advisory_gap_mode",
                    "controlled_planning_state": _build_controlled_planning_state(
                        status="blocked",
                        planning_mode="advisory_gap_mode",
                        blocking_reason="ecm_pulse_detection_failed",
                        missing_inputs=["current_threshold_a"],
                        recommended_sources=["identify_ecm_parameters"],
                    ),
                    "response_policy": _build_planning_response_policy(
                        planning_mode="advisory_gap_mode",
                        allow_step_level_protocol=False,
                        allow_generic_placeholders=False,
                        must_request_missing_inputs=True,
                    ),
                    "release_status": "blocker_aware_draft",
                    "parameter_request": parameter_request,
                    "ui_markdown": _build_blocked_modeling_markdown(
                        title="ECM Identification Could Not Find A Pulse",
                        known_context=[
                            ("Source", frame_payload.get("source_name")),
                            ("ECM model", ecm_model_id),
                            ("Current threshold", f"{current_threshold_a:g} A"),
                        ],
                        missing_inputs=[
                            "Confirm or reduce the minimum pulse-current threshold."
                        ],
                    ),
                },
            )

        return _tool_error(
            message,
            error_type="ecm_fit_error",
            suggestions=[
                "Use a pulse or HPPC dataset with real time/current/voltage traces rather than a cycle summary table.",
            ],
        )

    parameter_estimates = dict(ecm_payload.get("parameter_estimates", {}))
    warnings: list[str] = []
    if frame_payload.get("frame_origin") == "manual_column_mapping":
        warnings.append(
            "The dataset was prepared through manual column mapping because adapter normalization did not fully resolve the source table."
        )
        if frame_payload.get("parse_error"):
            warnings.append(
                f"Initial adapter parse note: {frame_payload['parse_error']}"
            )

    summary_lines = [
        "## ECM Parameter Identification",
        "",
        f"- Source: `{frame_payload['source_name']}`",
        f"- ECM model: `{ecm_payload['ecm_model_id']}`",
        f"- Selected pulse index: `{ecm_payload['pulse_selection']['pulse_index']}`",
        f"- Pulse mode: `{ecm_payload['pulse_selection']['mode']}`",
        f"- Candidate pulse count: `{ecm_payload['candidate_count']}`",
        f"- Current threshold: `{ecm_payload['current_threshold_a']}` A",
        f"- R0: `{parameter_estimates.get('r0_mohm')}` mOhm",
    ]
    if parameter_estimates.get("r1_mohm") is not None:
        summary_lines.append(f"- R1: `{parameter_estimates.get('r1_mohm')}` mOhm")
    if parameter_estimates.get("c1_f") is not None:
        summary_lines.append(f"- C1: `{parameter_estimates.get('c1_f')}` F")
    if parameter_estimates.get("tau1_s") is not None:
        summary_lines.append(f"- Tau1: `{parameter_estimates.get('tau1_s')}` s")
    if parameter_estimates.get("fit_rmse_v") is not None:
        summary_lines.append(f"- Fit RMSE: `{parameter_estimates.get('fit_rmse_v')}` V")

    fit_assumptions = [
        str(item).strip()
        for item in ecm_payload.get("fit_assumptions", [])
        if str(item).strip()
    ]
    if fit_assumptions:
        summary_lines.extend(["", "### Fit Assumptions", *[f"- {item}" for item in fit_assumptions]])
    if warnings:
        summary_lines.extend(["", "### Notes", *[f"- {item}" for item in warnings]])
    ui_markdown = "\n".join(summary_lines)

    slug = _slugify_path_segment(
        "-".join(
            part
            for part in (
                Path(str(frame_payload["source_name"])).stem,
                ecm_payload["ecm_model_id"],
                f"pulse-{ecm_payload['pulse_selection']['pulse_index']}",
            )
            if part
        )
    )
    generated_files = list(
        (frame_payload.get("adapter_payload") or {}).get("generated_files", [])
    )
    generated_files.append(
        _generated_file(
            path=f"/modeling/{slug}-ecm-summary.md",
            content=ui_markdown,
            generated_file_kind="ecm_fit_summary",
            display_name="ECM fit summary",
        )
    )
    generated_files.append(
        _generated_file(
            path=f"/modeling/{slug}-ecm-parameters.json",
            content=json.dumps(parameter_estimates, indent=2, ensure_ascii=True),
            generated_file_kind="ecm_parameter_estimates",
            display_name="ECM parameter estimates",
        )
    )
    if frame_payload.get("frame_origin") == "manual_column_mapping":
        generated_files.append(
            _generated_file(
                path=f"/modeling/{slug}-canonical.csv",
                content=frame_payload["frame"].to_csv(index=False),
                generated_file_kind="ecm_modeling_dataset",
                display_name="ECM modeling dataset",
            )
        )

    payload = {
        **ecm_payload,
        "status": "ok",
        "tool_kind": "ecm_parameter_identification",
        "source_file": frame_payload["source_name"],
        "frame_origin": frame_payload.get("frame_origin"),
        "mapping_used": frame_payload.get("mapping_used", {}),
        "raw_columns": frame_payload.get("raw_columns", []),
        "preview_rows": frame_payload.get("preview_rows", []),
        "warnings": warnings,
        "ui_markdown": ui_markdown,
        "generated_files": generated_files,
    }
    return _json_dumps(payload)


def _identify_ecm_parameters_tool(
    file_path: Annotated[
        str,
        "Absolute local file path or uploaded thread file path such as /uploads/<id>-hppc.csv.",
    ],
    attachment_text: Annotated[
        str | None,
        "Optional raw attachment text or read_file output for the same dataset.",
    ] = None,
    adapter_id: Annotated[
        str | None,
        "Optional explicit adapter id such as arbin_csv_v1, neware_csv_v1, or generic_battery_tabular_v1.",
    ] = None,
    ecm_model_id: Annotated[
        str,
        "ECM model id to fit. The current implementation supports r0_only and thevenin_1rc.",
    ] = "thevenin_1rc",
    target_pulse_index: Annotated[
        int | None,
        "Optional 1-based pulse index when the dataset contains multiple pulse candidates.",
    ] = None,
    current_threshold_a: Annotated[
        float,
        "Minimum absolute current magnitude treated as an active pulse segment.",
    ] = 0.02,
    time_column: Annotated[
        str | None,
        "Optional raw time-column name when the upload cannot be normalized automatically.",
    ] = None,
    current_column: Annotated[
        str | None,
        "Optional raw current-column name when the upload cannot be normalized automatically.",
    ] = None,
    voltage_column: Annotated[
        str | None,
        "Optional raw voltage-column name when the upload cannot be normalized automatically.",
    ] = None,
    runtime: ToolRuntime = None,
) -> str:
    return _identify_ecm_parameters_impl(
        file_path=file_path,
        attachment_text=attachment_text,
        adapter_id=adapter_id,
        ecm_model_id=ecm_model_id,
        target_pulse_index=target_pulse_index,
        current_threshold_a=current_threshold_a,
        time_column=time_column,
        current_column=current_column,
        voltage_column=voltage_column,
        runtime=runtime,
    )


identify_ecm_parameters = StructuredTool.from_function(
    name="identify_ecm_parameters",
    description="Identify ECM parameters from raw or normalized pulse/HPPC time-series data. The tool can pause for missing column mappings, pulse selection, or a lower pulse-current threshold.",
    func=_identify_ecm_parameters_tool,
    args_schema=EcmParameterIdentificationRequest,
)


@tool(args_schema=CycleAnalysisRequest)
def run_cycle_data_analysis(csv_path: str, nominal_capacity_ah: float | None = None) -> str:
    """Run starter cycle-level battery analysis on a local CSV file."""

    try:
        resolved_path = resolve_sample_path(csv_path)
    except FileNotFoundError as exc:
        return _tool_error(
            str(exc),
            error_type="file_not_found",
            suggestions=[
                "Provide a real CSV path, for example `data/samples/lfp_cycle_sample.csv`.",
                "Use get_demo_assets to list bundled sample files first.",
            ],
        )

    try:
        frame = pd.read_csv(resolved_path)
    except Exception as exc:
        return _tool_error(
            f"Failed to read CSV: {exc}",
            error_type="csv_read_error",
        )

    required_columns = {
        "cycle",
        "charge_capacity_ah",
        "discharge_capacity_ah",
        "average_temperature_c",
        "dcir_mohm",
    }
    missing_columns = sorted(required_columns.difference(frame.columns))
    if missing_columns:
        return _tool_error(
            "Missing required columns: " + ", ".join(missing_columns),
            error_type="schema_mismatch",
            suggestions=[
                "Expected columns: cycle, charge_capacity_ah, discharge_capacity_ah, average_temperature_c, dcir_mohm."
            ],
        )

    cycle_count = int(frame["cycle"].max())
    initial_capacity = float(frame["discharge_capacity_ah"].iloc[0])
    final_capacity = float(frame["discharge_capacity_ah"].iloc[-1])
    retention_pct = round((final_capacity / initial_capacity) * 100.0, 2)
    average_ce_pct = round(
        ((frame["discharge_capacity_ah"] / frame["charge_capacity_ah"]).mean()) * 100.0,
        2,
    )
    dcir_delta_mohm = round(float(frame["dcir_mohm"].iloc[-1] - frame["dcir_mohm"].iloc[0]), 3)
    peak_temperature_c = round(float(frame["average_temperature_c"].max()), 2)
    retention_slope_ah_per_cycle = round(
        float(np.polyfit(frame["cycle"], frame["discharge_capacity_ah"], 1)[0]),
        6,
    )

    analysis: dict[str, Any] = {
        "source_file": str(resolved_path),
        "rows": int(len(frame)),
        "cycle_count": cycle_count,
        "initial_discharge_capacity_ah": round(initial_capacity, 4),
        "final_discharge_capacity_ah": round(final_capacity, 4),
        "capacity_retention_pct": retention_pct,
        "average_coulombic_efficiency_pct": average_ce_pct,
        "dcir_delta_mohm": dcir_delta_mohm,
        "peak_temperature_c": peak_temperature_c,
        "retention_slope_ah_per_cycle": retention_slope_ah_per_cycle,
        "observations": [
            f"Capacity retention after {cycle_count} cycles is {retention_pct:.2f}%.",
            f"Average coulombic efficiency is {average_ce_pct:.2f}%.",
            f"DCIR increased by {dcir_delta_mohm:.3f} mOhm across the file window.",
        ],
    }

    if nominal_capacity_ah is not None:
        analysis["nominal_capacity_utilization_pct"] = round(
            (initial_capacity / nominal_capacity_ah) * 100.0,
            2,
        )

    return _json_dumps(analysis)

@tool
def list_pdf_test_methods() -> str:
    """List extracted chapters from the supplied battery methods PDF and the curated structured methods."""

    return _json_dumps(list_method_profiles())


@tool(args_schema=MethodLookupRequest)
def load_pdf_test_method(method_id: str) -> str:
    """Load a structured method or raw extracted chapter from the supplied battery methods PDF."""

    try:
        return _json_dumps(get_method_payload(method_id))
    except KeyError as exc:
        payload = list_method_profiles()
        return _tool_error(
            str(exc),
            error_type="unknown_test_method",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in payload.get("structured_methods", [])),
            ],
        )


def _plan_standard_test_impl(
    method_id: str,
    chemistry: str | None = None,
    selected_cell_id: str | None = None,
    instrument: str | None = None,
    thermal_chamber: str | None = None,
    form_factor: str | None = None,
    target_temperature_c: float = 25.0,
    charge_c_rate: float = 0.5,
    discharge_c_rate: float = 0.5,
    cycle_count: int = 1,
    method_inputs_json: str = "{}",
    operator_notes: str = "",
    runtime: ToolRuntime | None = None,
    _transient_selected_cell_override: dict[str, Any] | None = None,
) -> str:
    """Plan a protocol by combining the supplied PDF method and local controlled constraints."""

    resolved_instrument, resolved_thermal_chamber, lab_default_context = (
        _resolve_planning_defaults_from_runtime(
            instrument=instrument,
            thermal_chamber=thermal_chamber,
            runtime=runtime,
        )
    )
    effective_pretest_defaults = _build_effective_pretest_equipment_defaults(
        lab_default_context
    )
    (
        resolved_thermal_chamber,
        lab_default_context,
        deferred_thermal_chamber_note,
    ) = _normalize_default_thermal_chamber_usage(
        planning_key=method_id,
        target_temperature_c=target_temperature_c,
        explicit_thermal_chamber=thermal_chamber,
        resolved_thermal_chamber=resolved_thermal_chamber,
        lab_default_context=lab_default_context,
    )
    effective_selected_cell_id, transient_selected_cell_record = _resolve_selected_cell_context(
        selected_cell_id=selected_cell_id,
        runtime=runtime,
        transient_selected_cell_override=_transient_selected_cell_override,
    )

    kb = load_kb()
    if normalize_optional_text(resolved_instrument) is None:
        parameter_request = build_parameter_request_payload(
            request_id=f"{method_id}::instrument",
            method={"id": method_id, "label": method_id},
            release_status="blocker_aware_draft",
            missing_fields=["instrument"],
            requested_conditions={
                "target_temperature_c": target_temperature_c,
                "charge_c_rate": charge_c_rate,
                "discharge_c_rate": discharge_c_rate,
            },
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            (
                next_chemistry,
                next_selected_cell_id,
                next_instrument,
                next_thermal_chamber,
                next_method_inputs,
                next_transient_selected_cell_record,
            ) = _merge_parameter_answers(
                chemistry=chemistry,
                selected_cell_id=selected_cell_id,
                instrument=instrument,
                thermal_chamber=thermal_chamber,
                method_inputs={},
                transient_selected_cell_record=transient_selected_cell_record,
                answers=resumed_answers,
            )
            return _plan_standard_test_impl(
                method_id=method_id,
                chemistry=next_chemistry,
                selected_cell_id=next_selected_cell_id,
                instrument=next_instrument,
                thermal_chamber=next_thermal_chamber,
                form_factor=form_factor,
                target_temperature_c=target_temperature_c,
                charge_c_rate=charge_c_rate,
                discharge_c_rate=discharge_c_rate,
                cycle_count=cycle_count,
                method_inputs_json=_json_dumps(next_method_inputs),
                operator_notes=operator_notes,
                runtime=runtime,
                _transient_selected_cell_override=next_transient_selected_cell_record,
            )
        return _tool_error(
            "Instrument information is required to finalize an instrument-constrained standard-method plan.",
            error_type="missing_instrument",
            suggestions=[
                "Available instruments: " + ", ".join(list_instrument_rule_keys()),
                "Use load_battery_knowledge with the available chemistry/objective context before giving any fallback guidance.",
                "Do not invent instrument-specific pulse, logging, or compliance defaults from memory when the controlled instrument is still unresolved.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="missing_instrument",
                    missing_inputs=["instrument"],
                    recommended_sources=["load_battery_knowledge", "plan_standard_test"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "ui_markdown": _build_blocked_experiment_plan_markdown(
                    objective_or_method_label=f"Method: {method_id}",
                    release_status="blocker_aware_draft",
                    known_constraints=[
                        ["Method", method_id, "requested_method", "fixed", ""],
                        ["Instrument", "missing", "user_input_required", "blocked", "Select or provide the cycler/instrument before release."],
                        ["Target temperature", f"{target_temperature_c:.1f} C", "requested_conditions", "fixed", ""],
                    ],
                    pending_confirmations=[
                        [
                            "instrument",
                            "safety_boundary",
                            "execution_blocker",
                            "The instrument defines the available current, voltage, and logging limits.",
                            "Provide the instrument key or lab-default cycler selection.",
                        ]
                    ],
                ),
            },
        )

    try:
        method_inputs = _parse_method_inputs_json(method_inputs_json)
        payload = plan_method_protocol(
            method_id=method_id,
            chemistry=chemistry,
            selected_cell_id=effective_selected_cell_id,
            transient_selected_cell_record=transient_selected_cell_record,
            instrument=resolved_instrument,
            thermal_chamber=resolved_thermal_chamber,
            target_temperature_c=target_temperature_c,
            charge_c_rate=charge_c_rate,
            discharge_c_rate=discharge_c_rate,
            form_factor=form_factor,
            cycle_count=cycle_count,
            operator_notes=operator_notes,
            method_inputs=method_inputs,
            approved_equipment_defaults=effective_pretest_defaults,
        )
        if (
            payload.get("release_status") == "blocker_aware_draft"
            and isinstance(payload.get("parameter_request"), dict)
        ):
            resumed_answers = _await_parameter_request_answers(
                payload.get("parameter_request"),
                runtime,
            )
            if resumed_answers is not None:
                (
                    next_chemistry,
                    next_selected_cell_id,
                    next_instrument,
                    next_thermal_chamber,
                    next_method_inputs,
                    next_transient_selected_cell_record,
                ) = _merge_parameter_answers(
                    chemistry=chemistry,
                    selected_cell_id=selected_cell_id,
                    instrument=resolved_instrument,
                    thermal_chamber=thermal_chamber,
                    method_inputs=method_inputs,
                    transient_selected_cell_record=transient_selected_cell_record,
                    answers=resumed_answers,
                )
                return _plan_standard_test_impl(
                    method_id=method_id,
                    chemistry=next_chemistry,
                    selected_cell_id=next_selected_cell_id,
                    instrument=next_instrument,
                    thermal_chamber=next_thermal_chamber,
                    form_factor=form_factor,
                    target_temperature_c=target_temperature_c,
                    charge_c_rate=charge_c_rate,
                    discharge_c_rate=discharge_c_rate,
                    cycle_count=cycle_count,
                    method_inputs_json=_json_dumps(next_method_inputs),
                    operator_notes=operator_notes,
                    runtime=runtime,
                    _transient_selected_cell_override=next_transient_selected_cell_record,
                )
        equipment_rule = get_equipment_rule(resolved_instrument)
        warnings = list(payload.get("warnings", []))
        instrument_default_source = lab_default_context["applied_fields"].get("instrument")
        if instrument_default_source == "settings_lab_defaults":
            warnings.append(
                f"Instrument resolved from Settings lab defaults: `{resolved_instrument}`."
            )
        elif instrument_default_source == "pretest_guidance_default":
            warnings.append(
                f"Instrument resolved from approved default guidance: `{resolved_instrument}`."
            )
        thermal_chamber_default_source = lab_default_context["applied_fields"].get("thermal_chamber")
        if thermal_chamber_default_source == "settings_lab_defaults":
            warnings.append(
                f"Thermal chamber resolved from Settings lab defaults: `{resolved_thermal_chamber}`."
            )
        elif thermal_chamber_default_source == "pretest_guidance_default":
            warnings.append(
                f"Thermal chamber resolved from approved default guidance: `{resolved_thermal_chamber}`."
            )
        elif deferred_thermal_chamber_note:
            warnings.append(deferred_thermal_chamber_note)
        default_eis_instrument_label = lab_default_context["lab_defaults"].get(
            "default_eis_instrument_label"
        )
        default_eis_instrument_id = lab_default_context["lab_defaults"].get(
            "default_eis_instrument_id"
        )
        default_eis_setup_notes = lab_default_context["lab_defaults"].get(
            "default_eis_setup_notes"
        )
        if default_eis_instrument_label or default_eis_instrument_id:
            warnings.append(
                "Settings default EIS instrument available: "
                f"`{default_eis_instrument_label or default_eis_instrument_id}`."
            )
        if default_eis_setup_notes:
            warnings.append(
                "Settings default EIS setup notes available: "
                f"`{default_eis_setup_notes}`."
            )
        payload["instrument"] = equipment_rule["label"]
        payload["warnings"] = warnings
        payload["lab_default_context"] = lab_default_context
        payload["planning_mode"] = payload.get("planning_mode", "grounded_protocol_mode")
        payload["controlled_planning_state"] = payload.get(
            "controlled_planning_state",
            _build_controlled_planning_state(
                status="ready",
                planning_mode="grounded_protocol_mode",
                satisfied_by=["plan_standard_test"],
            ),
        )
        payload["response_policy"] = payload.get(
            "response_policy",
            _build_planning_response_policy(
                planning_mode="grounded_protocol_mode",
                allow_step_level_protocol=True,
                allow_generic_placeholders=False,
                must_request_missing_inputs=True,
                references_section_required=bool(payload.get("answer_references")),
            ),
        )
        return _json_dumps(payload)
    except KeyError as exc:
        payload = list_method_profiles()
        return _tool_error(
            str(exc),
            error_type="planning_lookup_error",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in payload.get("structured_methods", [])),
                "Available chemistries: " + ", ".join(sorted(kb["chemistry_profiles"].keys())),
                "Available instruments: " + ", ".join(list_instrument_rule_keys()),
                "Available thermal chambers: " + ", ".join(list_thermal_chamber_rule_keys()),
                "Use load_battery_knowledge with the same planning context before giving any advisory fallback so the answer stays anchored to the controlled KB.",
                "Do not replace missing chemistry, selected cell, or method inputs with generic pulse/rest/SOC defaults and present them as handbook-backed guidance.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="planning_lookup_error",
                    recommended_sources=["load_battery_knowledge", "load_pdf_test_method"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
            },
        )
    except MissingMethodInputsError as exc:
        parameter_request = build_parameter_request_payload(
            request_id=f"{exc.method_id}::{'-'.join(exc.missing_fields)}",
            method={"id": exc.method_id, "label": exc.method_id},
            release_status="blocker_aware_draft",
            missing_fields=exc.missing_fields,
            input_contract=exc.input_contract,
            requested_conditions=exc.declared_inputs,
        )
        resumed_answers = _await_parameter_request_answers(parameter_request, runtime)
        if resumed_answers is not None:
            (
                next_chemistry,
                next_selected_cell_id,
                next_instrument,
                next_thermal_chamber,
                next_method_inputs,
                next_transient_selected_cell_record,
            ) = _merge_parameter_answers(
                chemistry=chemistry,
                selected_cell_id=selected_cell_id,
                instrument=resolved_instrument,
                thermal_chamber=thermal_chamber,
                method_inputs=method_inputs if "method_inputs" in locals() else {},
                transient_selected_cell_record=transient_selected_cell_record,
                answers=resumed_answers,
            )
            return _plan_standard_test_impl(
                method_id=method_id,
                chemistry=next_chemistry,
                selected_cell_id=next_selected_cell_id,
                instrument=next_instrument,
                thermal_chamber=next_thermal_chamber,
                form_factor=form_factor,
                target_temperature_c=target_temperature_c,
                charge_c_rate=charge_c_rate,
                discharge_c_rate=discharge_c_rate,
                cycle_count=cycle_count,
                method_inputs_json=_json_dumps(next_method_inputs),
                operator_notes=operator_notes,
                runtime=runtime,
                _transient_selected_cell_override=next_transient_selected_cell_record,
            )
        return _tool_error(
            str(exc),
            error_type="planning_validation_error",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in list_method_profiles().get("structured_methods", [])),
                "Use method_inputs_json for method-specific fields such as target_soc, checkpoint_interval, target_voltage, hold_duration, profile_family, or stop_criterion.",
                "Do not replace blocked method-specific inputs with model-authored pulse/rest/SOC defaults. Keep those fields unresolved until they are supplied or loaded from a controlled asset.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="planning_validation_error",
                    missing_inputs=exc.missing_fields,
                    recommended_sources=["load_battery_knowledge", "load_pdf_test_method"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
                "release_status": "blocker_aware_draft",
                "parameter_request": parameter_request,
                "ui_markdown": _build_blocked_experiment_plan_markdown(
                    objective_or_method_label=f"Method: {method_id}",
                    release_status="blocker_aware_draft",
                    known_constraints=[
                        ["Method", method_id, "requested_method", "fixed", ""],
                        ["Instrument", resolved_instrument, "instrument", "fixed", ""],
                        ["Target temperature", f"{target_temperature_c:.1f} C", "requested_conditions", "fixed", ""],
                    ],
                    pending_confirmations=[
                        [
                            field_name,
                            next(
                                (
                                    question.get("severity")
                                    for question in parameter_request.get("questions", [])
                                    if question.get("key") == field_name
                                ),
                                "method_core",
                            ),
                            "execution_blocker",
                            next(
                                (
                                    question.get("why_needed")
                                    for question in parameter_request.get("questions", [])
                                    if question.get("key") == field_name
                                ),
                                f"{field_name} is required before release.",
                            ),
                            "Provide the missing value in the parameter request popup.",
                        ]
                        for field_name in exc.missing_fields
                    ],
                ),
            },
        )
    except ValueError as exc:
        return _tool_error(
            str(exc),
            error_type="planning_validation_error",
            suggestions=[
                "Structured methods: "
                + ", ".join(item["id"] for item in list_method_profiles().get("structured_methods", [])),
                "Use method_inputs_json for method-specific fields such as target_soc, checkpoint_interval, target_voltage, hold_duration, profile_family, or stop_criterion.",
                "Do not replace blocked method-specific inputs with model-authored pulse/rest/SOC defaults. Keep those fields unresolved until they are supplied or loaded from a controlled asset.",
            ],
            extra_payload={
                "planning_mode": "advisory_gap_mode",
                "controlled_planning_state": _build_controlled_planning_state(
                    status="blocked",
                    planning_mode="advisory_gap_mode",
                    blocking_reason="planning_validation_error",
                    recommended_sources=["load_battery_knowledge", "load_pdf_test_method"],
                ),
                "response_policy": _build_planning_response_policy(
                    planning_mode="advisory_gap_mode",
                    allow_step_level_protocol=False,
                    allow_generic_placeholders=False,
                    must_request_missing_inputs=True,
                ),
            },
        )


def _plan_standard_test_tool(
    method_id: Annotated[
        str,
        "Structured method id such as soc_ocv, capacity_test, pulse_hppc, or cycle_life.",
    ],
    chemistry: Annotated[
        str | None,
        "Optional chemistry key such as lfp, nmc811, or nca.",
    ] = None,
    selected_cell_id: Annotated[
        str | None,
        "Optional imported cell catalog id such as Panasonic_NCR18650BF.",
    ] = None,
    instrument: Annotated[
        str | None,
        "Optional equipment key such as arbin_bt2000. Required to finalize an instrument-constrained plan.",
    ] = None,
    thermal_chamber: Annotated[
        str | None,
        "Optional thermal chamber key such as binder_lit_mk.",
    ] = None,
    form_factor: Annotated[
        str | None,
        "Optional form factor override such as cylindrical, pouch, or prismatic.",
    ] = None,
    target_temperature_c: Annotated[
        float,
        "Target planning temperature in degrees Celsius.",
    ] = 25.0,
    charge_c_rate: Annotated[
        float,
        "Charge rate in C used when the method template requires one.",
    ] = 0.5,
    discharge_c_rate: Annotated[
        float,
        "Discharge rate in C used when the method template requires one.",
    ] = 0.5,
    cycle_count: Annotated[
        int,
        "Cycle or block count placeholder used for method defaults.",
    ] = 1,
    method_inputs_json: Annotated[
        str,
        "JSON object for method-specific fields such as target_soc, checkpoint_interval, target_voltage, hold_duration, profile_family, or stop_criterion.",
    ] = "{}",
    operator_notes: Annotated[
        str,
        "Optional planning notes.",
    ] = "",
    runtime: ToolRuntime = None,
) -> str:
    return _plan_standard_test_impl(
        method_id=method_id,
        chemistry=chemistry,
        selected_cell_id=selected_cell_id,
        instrument=instrument,
        thermal_chamber=thermal_chamber,
        form_factor=form_factor,
        target_temperature_c=target_temperature_c,
        charge_c_rate=charge_c_rate,
        discharge_c_rate=discharge_c_rate,
        cycle_count=cycle_count,
        method_inputs_json=method_inputs_json,
        operator_notes=operator_notes,
        runtime=runtime,
    )


plan_standard_test = StructuredTool.from_function(
    name="plan_standard_test",
    description="Plan a protocol by combining the supplied PDF method and local controlled constraints.",
    func=_plan_standard_test_tool,
)


@tool(args_schema=ReportRequest)
def generate_lab_report_markdown(
    goal: str,
    protocol_json: str,
    analysis_json: str,
    analyst_notes: str = "",
) -> str:
    """Generate a Markdown lab report draft from structured protocol and analysis outputs."""

    protocol = _safe_json_loads(protocol_json)
    analysis = _safe_json_loads(analysis_json)

    steps = protocol.get("steps", [])
    checklist = protocol.get("qa_checklist", [])
    observations = analysis.get("observations", [])

    step_lines = "\n".join(
        f"{index}. **{step.get('name', 'Step')}** - {step.get('details', '')}"
        for index, step in enumerate(steps, start=1)
    )
    checklist_lines = "\n".join(f"- {item}" for item in checklist)
    observation_lines = "\n".join(f"- {item}" for item in observations)
    warnings = protocol.get("warnings", [])
    warning_lines = "\n".join(f"- {item}" for item in warnings) or "- None surfaced by the starter tool."

    return f"""# Battery Lab Assistant Report

## Goal

{goal}

## Protocol Draft

- **Protocol name:** {protocol.get("protocol_name", "Unavailable")}
- **Status:** {protocol.get("status", "draft")}
- **Chemistry:** {protocol.get("chemistry", "Unavailable")}
- **Instrument:** {protocol.get("instrument", "Unavailable")}

### Planned Steps

{step_lines or "No structured steps available."}

### QA and Safety Checklist

{checklist_lines or "- No checklist available."}

### Draft Warnings

{warning_lines}

## Analysis Summary

- **Source file:** {analysis.get("source_file", "Unavailable")}
- **Capacity retention:** {analysis.get("capacity_retention_pct", "Unavailable")}%
- **Average coulombic efficiency:** {analysis.get("average_coulombic_efficiency_pct", "Unavailable")}%
- **DCIR delta:** {analysis.get("dcir_delta_mohm", "Unavailable")} mOhm
- **Peak temperature:** {analysis.get("peak_temperature_c", "Unavailable")} C

### Observations

{observation_lines or "- No structured observations available."}

## Analyst Notes

{analyst_notes or "Add your interpretation, standards references, and release notes here."}
"""


TOOLS = [
    describe_lab_backend_framework,
    get_demo_assets,
    search_equipment_manual_knowledge,
    load_equipment_manual_knowledge,
    search_knowledge_evidence_cards,
    load_knowledge_source,
    search_imported_cell_catalog,
    export_imported_cell_catalog,
    load_imported_cell_record,
    extract_uploaded_cell_datasheet,
    extract_uploaded_cell_datasheet_to_provisional_asset,
    search_provisional_cell_assets,
    load_provisional_cell_asset,
    register_provisional_cell_asset,
    review_provisional_cell_asset,
    promote_provisional_cell_asset,
    describe_chemistry_profile,
    load_battery_knowledge,
    design_battery_protocol,
    parse_raw_cycler_export,
    *([identify_ecm_parameters] if ECM_IDENTIFICATION_TOOL_ENABLED else []),
    list_pdf_test_methods,
    load_pdf_test_method,
    plan_standard_test,
    run_cycle_data_analysis,
    generate_lab_report_markdown,
]
