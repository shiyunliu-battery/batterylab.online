"""Structured extraction of uploaded cell datasheets using a dedicated OpenAI model."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Any, Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

from battery_agent.kb import REPO_ROOT

load_dotenv(REPO_ROOT / ".env")

CELL_DATASHEET_EXTRACTION_MODEL_ENV = "BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_MODEL"
CELL_DATASHEET_EXTRACTION_TEMPERATURE_ENV = (
    "BATTERY_AGENT_CELL_DATASHEET_EXTRACTION_TEMPERATURE"
)
MAIN_AGENT_MODEL_ENV = "BATTERY_AGENT_MODEL"
DEFAULT_MAIN_AGENT_MODEL = "openai:gpt-4o-mini"
DEFAULT_CELL_DATASHEET_EXTRACTION_TEMPERATURE = 0.0
CELL_DATASHEET_EXTRACTION_PARSER_VERSION = "openai_structured_cell_datasheet_v1"

_PREVIEW_HEADER_PATTERN = re.compile(r"^Attachment extraction preview\s*$", re.IGNORECASE)
_PREVIEW_FIELD_MAP = {
    "original filename": "original_filename",
    "mime type": "mime_type",
    "extraction mode": "extraction_mode",
    "detected pages": "detected_pages",
}

_SYSTEM_INSTRUCTIONS = """You extract structured commercial cell datasheet facts into a strict JSON schema.

Rules:
- Use only the provided datasheet text. Do not invent or interpolate unsupported values.
- If a field is not explicitly supported by the text, leave it null instead of guessing.
- Prefer recommended / normal operating conditions for formal planning fields such as charge voltage, discharge cut-off, and continuous currents.
- Preserve harsher absolute or maximum conditions only in the dedicated maximum-operating-conditions block.
- Do not infer chemistry from model names alone. Only set project_chemistry_hint when the datasheet text explicitly supports it.
- Use broad form-factor categories only: cylindrical, prismatic, pouch, coin, pack, module, unknown.
- Put subtype hints such as 18650, 21700, or 26650 into case_types.
- display_name should be human-readable. Combine manufacturer and model when possible.
- schema_name should be the canonical model token if present.
- field_evidence must cite numbered source lines from the provided text.
- If nominal_voltage_v is populated from a phrase such as "Average Operating Voltage", mark extraction_mode as derived and explain that in note.
- If cycle life is only shown as a plot without a crisp numeric value, leave cycle_life_cycles null and mention that in suggested_review_notes.
- Keep outputs concise and schema-valid.
"""


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceDocumentMetadata(_StrictBaseModel):
    original_filename: str | None = None
    mime_type: str | None = None
    extraction_mode: str | None = None
    detected_pages: int | None = None
    thread_file_path: str | None = None


class ElectricalFields(_StrictBaseModel):
    nominal_capacity_ah: float | None = None
    nominal_voltage_v: float | None = None
    charge_voltage_v: float | None = None
    discharge_cutoff_v: float | None = None
    internal_impedance_mohm: float | None = None


class CurrentFields(_StrictBaseModel):
    max_continuous_charge_current_a: float | None = None
    max_continuous_discharge_current_a: float | None = None
    pulse_discharge_current_a_30s: float | None = None


class PhysicalFields(_StrictBaseModel):
    mass_g: float | None = None
    diameter_mm: float | None = None
    height_mm: float | None = None
    width_mm: float | None = None
    length_mm: float | None = None


class LifecycleFields(_StrictBaseModel):
    cycle_life_cycles: int | None = None


class RecommendedOperatingConditions(_StrictBaseModel):
    continuous_discharge_a: float | None = None
    pulse_discharge_a_30s: float | None = None
    charge_current_a: float | None = None
    charge_voltage_cutoff_v: float | None = None
    discharge_voltage_cutoff_v: float | None = None
    high_operating_temp_c: float | None = None
    low_operating_temp_c: float | None = None


class MaximumOperatingConditions(_StrictBaseModel):
    continuous_discharge_a: float | None = None
    pulse_discharge_a_30s: float | None = None
    short_pulse_discharge_a: float | None = None
    charge_current_a: float | None = None
    charge_voltage_cutoff_v: float | None = None
    discharge_voltage_cutoff_v: float | None = None


class FieldEvidenceItem(_StrictBaseModel):
    field_name: str
    text_excerpt: str
    source_lines: list[int] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    extraction_mode: Literal["explicit", "derived", "inferred", "not_found"] = "explicit"
    note: str | None = None


class CellDatasheetCandidate(_StrictBaseModel):
    display_name: str
    manufacturer: str = "Unknown"
    model: str | None = None
    schema_name: str | None = None
    project_chemistry_hint: str | None = None
    form_factor: Literal[
        "cylindrical",
        "prismatic",
        "pouch",
        "coin",
        "pack",
        "module",
        "unknown",
    ] = "unknown"
    case_types: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    positive_electrode_type: str | None = None
    electrical: ElectricalFields = Field(default_factory=ElectricalFields)
    currents: CurrentFields = Field(default_factory=CurrentFields)
    physical: PhysicalFields = Field(default_factory=PhysicalFields)
    lifecycle: LifecycleFields = Field(default_factory=LifecycleFields)
    recommended_operating_conditions: RecommendedOperatingConditions = Field(
        default_factory=RecommendedOperatingConditions
    )
    maximum_operating_conditions: MaximumOperatingConditions = Field(
        default_factory=MaximumOperatingConditions
    )
    normalization_notes: list[str] = Field(default_factory=list)
    suggested_review_notes: list[str] = Field(default_factory=list)
    field_evidence: list[FieldEvidenceItem] = Field(default_factory=list)
    source_document: SourceDocumentMetadata


class CellDatasheetExtractionResponse(_StrictBaseModel):
    candidate: CellDatasheetCandidate
    extraction_summary: list[str] = Field(default_factory=list)
    missing_or_uncertain_fields: list[str] = Field(default_factory=list)


def _normalize_openai_model_name(model_name: str | None) -> str:
    normalized = str(model_name or "").strip()
    if not normalized:
        return ""
    if ":" not in normalized:
        return normalized

    provider, raw_model_name = normalized.split(":", 1)
    if provider.strip().lower() == "openai":
        return raw_model_name.strip()
    return normalized


def get_cell_datasheet_extraction_model() -> str:
    configured_model = os.getenv(CELL_DATASHEET_EXTRACTION_MODEL_ENV, "").strip()
    if configured_model:
        return configured_model

    main_agent_model = os.getenv(MAIN_AGENT_MODEL_ENV, DEFAULT_MAIN_AGENT_MODEL)
    normalized_main_agent_model = _normalize_openai_model_name(main_agent_model)
    if normalized_main_agent_model:
        return normalized_main_agent_model

    return _normalize_openai_model_name(DEFAULT_MAIN_AGENT_MODEL)


def get_cell_datasheet_extraction_temperature() -> float:
    raw_value = os.getenv(
        CELL_DATASHEET_EXTRACTION_TEMPERATURE_ENV,
        str(DEFAULT_CELL_DATASHEET_EXTRACTION_TEMPERATURE),
    ).strip()
    try:
        return float(raw_value)
    except ValueError:
        return DEFAULT_CELL_DATASHEET_EXTRACTION_TEMPERATURE


def clear_cell_datasheet_extraction_client_cache() -> None:
    _get_openai_client.cache_clear()


def _require_openai_api_key() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key in {
        "replace_with_real_key",
        "replace-with-real-openai-key",
    }:
        raise RuntimeError(
            "OPENAI_API_KEY is required for structured datasheet extraction. "
            "Add a real API key to .env before using this feature."
        )


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI:
    _require_openai_api_key()
    return OpenAI()


def _clean_text(value: str | None) -> str:
    return str(value or "").strip()


def _parse_attachment_preview(
    attachment_text: str,
    *,
    thread_file_path: str,
) -> tuple[dict[str, Any], str]:
    raw_text = str(attachment_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = raw_text.split("\n")
    metadata: dict[str, Any] = {
        "thread_file_path": thread_file_path,
        "original_filename": os.path.basename(thread_file_path),
        "mime_type": None,
        "extraction_mode": None,
        "detected_pages": None,
    }

    if lines and _PREVIEW_HEADER_PATTERN.match(lines[0]):
        body_start = 1
        for index in range(1, len(lines)):
            line = lines[index].strip()
            if not line:
                body_start = index + 1
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            normalized_key = key.strip().lower()
            mapped_key = _PREVIEW_FIELD_MAP.get(normalized_key)
            if not mapped_key:
                continue
            parsed_value: Any = value.strip()
            if mapped_key == "detected_pages":
                try:
                    parsed_value = int(parsed_value)
                except ValueError:
                    parsed_value = None
            metadata[mapped_key] = parsed_value
        body = "\n".join(lines[body_start:]).strip()
        return metadata, body

    return metadata, raw_text.strip()


def _maybe_raise_placeholder_error(body_text: str, *, file_path: str) -> None:
    stripped = body_text.strip()
    if not stripped.startswith("{"):
        return

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, dict):
        return

    kind = _clean_text(str(payload.get("kind") or ""))
    if kind.endswith("_placeholder"):
        raise ValueError(
            f"The uploaded thread file `{file_path}` only contains attachment metadata, not extracted datasheet text. "
            "Re-upload the PDF/XLSX in the current UI so the attachment preview text is available for extraction."
        )


def _numbered_source_text(body_text: str) -> str:
    lines = body_text.split("\n")
    return "\n".join(f"L{index + 1}: {line}" for index, line in enumerate(lines))


def _normalize_evidence(items: list[FieldEvidenceItem]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for item in items:
        field_name = _clean_text(item.field_name)
        if not field_name:
            continue
        evidence[field_name] = {
            "text": item.text_excerpt,
            "source_lines": list(item.source_lines),
            "confidence": item.confidence,
            "extraction_mode": item.extraction_mode,
            **({"note": item.note} if item.note else {}),
        }
    return evidence


def _compact_model_dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(exclude_none=True)


def extract_cell_datasheet_candidate_from_text(
    attachment_text: str,
    *,
    thread_file_path: str,
) -> dict[str, Any]:
    metadata, body_text = _parse_attachment_preview(
        attachment_text,
        thread_file_path=thread_file_path,
    )
    _maybe_raise_placeholder_error(body_text, file_path=thread_file_path)
    if not body_text or body_text == "[No extractable text was found in this PDF.]":
        raise ValueError(
            f"The uploaded thread file `{thread_file_path}` does not contain extractable datasheet text."
        )

    numbered_text = _numbered_source_text(body_text)
    client = _get_openai_client()
    model_name = get_cell_datasheet_extraction_model()
    temperature = get_cell_datasheet_extraction_temperature()
    response = client.responses.parse(
        model=model_name,
        temperature=temperature,
        text_format=CellDatasheetExtractionResponse,
        instructions=_SYSTEM_INSTRUCTIONS,
        input="\n".join(
            [
                "Uploaded cell datasheet extraction request.",
                f"Thread file path: {thread_file_path}",
                f"Original filename: {metadata.get('original_filename') or 'unknown'}",
                f"MIME type: {metadata.get('mime_type') or 'unknown'}",
                f"Extraction mode: {metadata.get('extraction_mode') or 'unknown'}",
                (
                    f"Detected pages: {metadata['detected_pages']}"
                    if metadata.get("detected_pages") is not None
                    else "Detected pages: unknown"
                ),
                "",
                "Datasheet text with source line numbers:",
                numbered_text,
            ]
        ),
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("OpenAI did not return a structured datasheet extraction payload.")

    candidate = _compact_model_dump(parsed.candidate)
    field_evidence = _normalize_evidence(parsed.candidate.field_evidence)
    source_document = {
        **_compact_model_dump(parsed.candidate.source_document),
        "thread_file_path": thread_file_path,
        "extraction_provider": "openai_responses_api",
        "model_name": model_name,
    }
    if metadata.get("original_filename") and not source_document.get("original_filename"):
        source_document["original_filename"] = metadata["original_filename"]
    if metadata.get("mime_type") and not source_document.get("mime_type"):
        source_document["mime_type"] = metadata["mime_type"]
    if metadata.get("extraction_mode") and not source_document.get("extraction_mode"):
        source_document["extraction_mode"] = metadata["extraction_mode"]
    if metadata.get("detected_pages") is not None and source_document.get("detected_pages") is None:
        source_document["detected_pages"] = metadata["detected_pages"]

    candidate["source_document"] = source_document
    candidate["field_evidence"] = field_evidence
    if parsed.candidate.model:
        candidate.setdefault("model", parsed.candidate.model)
    if parsed.candidate.schema_name:
        candidate.setdefault("schema_name", parsed.candidate.schema_name)

    return {
        "status": "ok",
        "parser_version": CELL_DATASHEET_EXTRACTION_PARSER_VERSION,
        "model_name": model_name,
        "temperature": temperature,
        "source_document": source_document,
        "candidate": candidate,
        "extraction_summary": list(parsed.extraction_summary),
        "missing_or_uncertain_fields": list(parsed.missing_or_uncertain_fields),
        "suggested_review_notes": list(parsed.candidate.suggested_review_notes),
    }
