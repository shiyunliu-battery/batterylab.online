"""Core models and exceptions for data adapters."""

from dataclasses import dataclass
import pandas as pd

class AdapterError(ValueError):
    """Base adapter-layer error."""

class UnknownAdapterError(AdapterError):
    """Raised when an adapter id is unknown."""

class AdapterDetectionError(AdapterError):
    """Raised when raw export detection fails."""

class AdapterReadError(AdapterError):
    """Raised when the raw export cannot be read."""

class AdapterSchemaError(AdapterError):
    """Raised when the normalized frame does not satisfy the schema."""

@dataclass(frozen=True)
class AdapterParseResult:
    adapter_id: str
    adapter_vendor: str
    frame: pd.DataFrame
    source_name: str
    auto_detected: bool
    raw_columns: list[str]
    warnings: list[str]
    detected_from: str
    target_schema: str = "battery_timeseries_v1"
    dataset_kind: str = "raw_timeseries"
    field_summary_label: str = "Canonical fields"
    preview_only: bool = False
