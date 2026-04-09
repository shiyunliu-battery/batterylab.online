"""Public API for battery_agent.data_adapters package."""

from battery_agent.data_adapters.models import (
    AdapterError,
    AdapterDetectionError,
    AdapterReadError,
    AdapterSchemaError,
    UnknownAdapterError,
    AdapterParseResult,
)
from battery_agent.data_adapters.schema import (
    load_canonical_schema,
    canonical_field_names,
    required_canonical_fields,
    optional_canonical_fields,
)
from battery_agent.data_adapters.utils import (
    normalize_adapter_id,
    extract_raw_header_candidates,
)
from battery_agent.data_adapters.factory import (
    list_supported_adapter_ids,
    get_adapter,
    detect_adapter_id_from_text,
    parse_raw_export_text,
    parse_raw_export_file,
)

__all__ = [
    # Exceptions
    "AdapterError",
    "AdapterDetectionError",
    "AdapterReadError",
    "AdapterSchemaError",
    "UnknownAdapterError",
    # Result model
    "AdapterParseResult",
    # Schema helpers
    "load_canonical_schema",
    "canonical_field_names",
    "required_canonical_fields",
    "optional_canonical_fields",
    # Utilities
    "normalize_adapter_id",
    "extract_raw_header_candidates",
    # Factory / parse entry points
    "list_supported_adapter_ids",
    "get_adapter",
    "detect_adapter_id_from_text",
    "parse_raw_export_text",
    "parse_raw_export_file",
]
