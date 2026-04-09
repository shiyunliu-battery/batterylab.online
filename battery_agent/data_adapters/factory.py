"""Adapter registry, auto-detection, and public parse entry points."""

from __future__ import annotations

from pathlib import Path

from battery_agent.data_adapters.models import (
    AdapterDetectionError,
    AdapterParseResult,
    UnknownAdapterError,
)
from battery_agent.data_adapters.schema import optional_canonical_fields
from battery_agent.data_adapters.utils import (
    extract_raw_header_candidates,
    normalize_adapter_id,
)
from battery_agent.data_adapters.generic import (
    ATTACHMENT_PREVIEW_PREFIX,
    GenericBatteryTabularAdapter,
    classify_generic_dataset,
)
from battery_agent.data_adapters.vendors import ArbinAdapter, NewareAdapter
from battery_agent.data_adapters.base import BaseCyclerAdapter


ADAPTERS: dict[str, type[BaseCyclerAdapter]] = {
    ArbinAdapter.adapter_id: ArbinAdapter,
    NewareAdapter.adapter_id: NewareAdapter,
    GenericBatteryTabularAdapter.adapter_id: GenericBatteryTabularAdapter,
}

AUTO_DETECTION_ADAPTER_IDS = (
    ArbinAdapter.adapter_id,
    NewareAdapter.adapter_id,
)


def list_supported_adapter_ids() -> list[str]:
    return sorted(ADAPTERS.keys())


def get_adapter(adapter_id: str) -> BaseCyclerAdapter:
    normalized = normalize_adapter_id(adapter_id)
    if normalized is None or normalized not in ADAPTERS:
        raise UnknownAdapterError(
            "Unknown adapter id: "
            + str(adapter_id)
            + ". Supported adapters: "
            + ", ".join(list_supported_adapter_ids())
        )
    return ADAPTERS[normalized]()


def detect_adapter_id_from_text(text: str) -> tuple[str, str]:
    stripped = text.lstrip()
    if not stripped:
        raise AdapterDetectionError("Raw export text is empty.")

    matched: list[tuple[str, str]] = []
    for adapter_id in AUTO_DETECTION_ADAPTER_IDS:
        adapter_class = ADAPTERS[adapter_id]
        adapter = adapter_class()
        if adapter.sniff_text(stripped):
            matched.append((adapter_id, "header_signals"))

    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        raise AdapterDetectionError(
            "Multiple adapters matched this raw export. Pass an explicit adapter_id."
        )
    generic_adapter = GenericBatteryTabularAdapter()
    if generic_adapter.sniff_text(stripped):
        return (generic_adapter.adapter_id, "generic_header_signals")
    raise AdapterDetectionError(
        "Could not detect a supported battery-data parser from the provided export."
    )


def parse_raw_export_text(
    text: str,
    *,
    source_name: str,
    adapter_id: str | None = None,
) -> AdapterParseResult:
    normalized_adapter_id = normalize_adapter_id(adapter_id)
    auto_detected = normalized_adapter_id is None
    detected_from = "explicit_adapter_id"

    if normalized_adapter_id is None:
        normalized_adapter_id, detected_from = detect_adapter_id_from_text(text)

    adapter = get_adapter(normalized_adapter_id)
    frame = adapter.process_text(text, source_name=source_name)
    raw_columns = extract_raw_header_candidates(text)
    warnings: list[str] = []
    missing_optional = [
        field for field in optional_canonical_fields() if field not in frame.columns
    ]
    if missing_optional and normalized_adapter_id != GenericBatteryTabularAdapter.adapter_id:
        warnings.append("Optional fields missing after normalization: " + ", ".join(missing_optional))

    dataset_kind = "raw_timeseries"
    target_schema = "battery_timeseries_v1"
    field_summary_label = "Canonical fields"
    preview_only = ATTACHMENT_PREVIEW_PREFIX in text or "[Truncated after" in text
    if normalized_adapter_id == GenericBatteryTabularAdapter.adapter_id:
        dataset_kind, target_schema, field_summary_label = classify_generic_dataset(
            list(frame.columns)
        )
        if preview_only:
            warnings.append(
                "The uploaded attachment was parsed from a preview/truncated view, so only an informational subset is shown."
            )

    return AdapterParseResult(
        adapter_id=adapter.adapter_id,
        adapter_vendor=adapter.vendor,
        frame=frame,
        source_name=source_name,
        auto_detected=auto_detected,
        raw_columns=raw_columns or list(frame.columns),
        warnings=warnings,
        detected_from=detected_from,
        target_schema=target_schema,
        dataset_kind=dataset_kind,
        field_summary_label=field_summary_label,
        preview_only=preview_only,
    )


def parse_raw_export_file(
    file_path: str | Path,
    *,
    adapter_id: str | None = None,
) -> AdapterParseResult:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Raw data file `{path}` not found.")

    normalized_adapter_id = normalize_adapter_id(adapter_id)
    auto_detected = normalized_adapter_id is None
    detected_from = "explicit_adapter_id"
    preview_text: str | None = None
    if path.suffix.lower() in {".csv", ".tsv", ".txt"}:
        # Sniff only first 20 lines; avoids loading multi-GB files into memory.
        with path.open("r", encoding="utf-8", errors="replace") as f:
            preview_text = "".join(f.readline() for _ in range(20))

    if normalized_adapter_id is None:
        suffix = path.suffix.lower()
        if suffix not in {".csv", ".tsv", ".txt"}:
            raise AdapterDetectionError(
                "Auto-detection currently supports text-delimited exports only. "
                "Provide adapter_id for Excel exports."
            )
        assert preview_text is not None
        normalized_adapter_id, detected_from = detect_adapter_id_from_text(preview_text)
        raw_columns = extract_raw_header_candidates(preview_text)
    else:
        raw_columns = extract_raw_header_candidates(preview_text) if preview_text else []

    adapter = get_adapter(normalized_adapter_id)
    frame = adapter.process_file(path)
    warnings: list[str] = []
    missing_optional = [
        field for field in optional_canonical_fields() if field not in frame.columns
    ]
    if missing_optional and normalized_adapter_id != GenericBatteryTabularAdapter.adapter_id:
        warnings.append("Optional fields missing after normalization: " + ", ".join(missing_optional))

    dataset_kind = "raw_timeseries"
    target_schema = "battery_timeseries_v1"
    field_summary_label = "Canonical fields"
    preview_only = False
    if normalized_adapter_id == GenericBatteryTabularAdapter.adapter_id:
        dataset_kind, target_schema, field_summary_label = classify_generic_dataset(
            list(frame.columns)
        )

    return AdapterParseResult(
        adapter_id=adapter.adapter_id,
        adapter_vendor=adapter.vendor,
        frame=frame,
        source_name=str(path),
        auto_detected=auto_detected,
        raw_columns=raw_columns or list(frame.columns),
        warnings=warnings,
        detected_from=detected_from,
        target_schema=target_schema,
        dataset_kind=dataset_kind,
        field_summary_label=field_summary_label,
        preview_only=preview_only,
    )
