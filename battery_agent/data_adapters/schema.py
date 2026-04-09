"""Schema loading and definition utilities."""

import json
from pathlib import Path
from typing import Any

import yaml

from battery_agent.kb import REPO_ROOT
from battery_agent.data_adapters.models import AdapterSchemaError

PREPROCESSING_DIR = REPO_ROOT / "data" / "workflows" / "preprocessing"
CANONICAL_SCHEMA_PATH = PREPROCESSING_DIR / "battery_timeseries_v1.json"
MAPPER_CONFIG_DIR = PREPROCESSING_DIR / "mapper_configs"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise AdapterSchemaError(f"Mapper config `{path}` must be a mapping.")
    return loaded


def load_canonical_schema() -> dict[str, Any]:
    with CANONICAL_SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise AdapterSchemaError("Canonical schema must be a JSON object.")
    return loaded


def _schema_field_entries() -> list[dict[str, Any]]:
    schema = load_canonical_schema()
    raw_fields = schema.get("fields", [])
    if not isinstance(raw_fields, list):
        raise AdapterSchemaError("Canonical schema `fields` must be a list.")
    entries = [entry for entry in raw_fields if isinstance(entry, dict)]
    if not entries:
        raise AdapterSchemaError("Canonical schema does not define any fields.")
    return entries


def canonical_field_names() -> list[str]:
    return [str(entry["name"]) for entry in _schema_field_entries() if "name" in entry]


def required_canonical_fields() -> list[str]:
    return [
        str(entry["name"])
        for entry in _schema_field_entries()
        if entry.get("required") is True and "name" in entry
    ]


def optional_canonical_fields() -> list[str]:
    required = set(required_canonical_fields())
    return [field for field in canonical_field_names() if field not in required]
