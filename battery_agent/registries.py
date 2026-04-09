"""Registry loaders for chemistry and method definitions."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = REPO_ROOT / "data" / "registries"

CHEMISTRY_REGISTRY_PATH = REGISTRY_DIR / "chemistry_registry.json"
METHOD_REGISTRY_PATH = REGISTRY_DIR / "method_registry.json"
METHOD_REGISTRY_GLOB = "method_registry_*.json"


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _attach_id(entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["id"] = entry_id
    return enriched


def _normalize_notes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    rendered = str(value).strip()
    return [rendered] if rendered else []


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    rendered = str(value).strip()
    return [rendered] if rendered else []


def _infer_step_bundle_strictness(step_bundle: Any) -> str:
    if not isinstance(step_bundle, list):
        return "not_declared"

    strictness_values = {
        str(step.get("strictness") or "").strip()
        for step in step_bundle
        if isinstance(step, dict) and str(step.get("strictness") or "").strip()
    }
    if not strictness_values:
        return "not_declared"
    if len(strictness_values) == 1:
        return next(iter(strictness_values))
    return "mixed"


def _materialize_core_rpt_block(
    core_rpt_set: dict[str, Any],
    block: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rpt_id": str(block.get("rpt_id") or core_rpt_set.get("bundle_id") or "core_rpt_set"),
        "label": str(block.get("label") or core_rpt_set.get("label") or "Core RPT set"),
        "purpose": str(
            block.get("purpose")
            or core_rpt_set.get("summary")
            or "No purpose declared."
        ),
        "source_method_ids": _normalize_string_list(
            block.get("source_method_ids") or core_rpt_set.get("source_method_ids")
        ),
        "mandatory_at": _normalize_string_list(
            block.get("mandatory_at") or core_rpt_set.get("mandatory_at")
        ),
        "strictness": str(
            block.get("strictness")
            or core_rpt_set.get("default_strictness")
            or _infer_step_bundle_strictness(core_rpt_set.get("step_bundle"))
        ),
        "complementary_literature_card_ids": _normalize_string_list(
            block.get("complementary_literature_card_ids")
            or core_rpt_set.get("complementary_literature_card_ids")
        ),
    }


def _materialize_extension_rpt_block(
    extension: dict[str, Any],
    block: dict[str, Any],
) -> dict[str, Any]:
    return {
        "rpt_id": str(
            block.get("rpt_id") or extension.get("extension_id") or "checkpoint_extension"
        ),
        "label": str(
            block.get("label") or extension.get("label") or "Checkpoint extension"
        ),
        "purpose": str(
            block.get("purpose")
            or extension.get("summary")
            or "No purpose declared."
        ),
        "source_method_ids": _normalize_string_list(
            block.get("source_method_ids") or extension.get("method_ids")
        ),
        "mandatory_at": _normalize_string_list(
            block.get("mandatory_at") or extension.get("trigger_at")
        ),
        "strictness": str(
            block.get("strictness")
            or extension.get("default_strictness")
            or _infer_step_bundle_strictness(extension.get("step_bundle"))
        ),
        "complementary_literature_card_ids": _normalize_string_list(
            block.get("complementary_literature_card_ids")
            or extension.get("complementary_literature_card_ids")
        ),
    }


def _normalize_reference_check_policy(reference_check_policy: Any) -> dict[str, Any]:
    if not isinstance(reference_check_policy, dict):
        return {}

    normalized = dict(reference_check_policy)
    core_rpt_set = (
        dict(reference_check_policy.get("core_rpt_set"))
        if isinstance(reference_check_policy.get("core_rpt_set"), dict)
        else {}
    )
    checkpoint_extension_tests = [
        dict(extension)
        for extension in reference_check_policy.get("checkpoint_extension_tests", [])
        if isinstance(extension, dict)
    ]
    extension_map = {
        str(extension.get("extension_id")): extension
        for extension in checkpoint_extension_tests
        if isinstance(extension.get("extension_id"), str)
    }

    materialized_rpt_blocks: list[dict[str, Any]] = []
    raw_rpt_blocks = reference_check_policy.get("rpt_blocks", [])
    for raw_block in raw_rpt_blocks:
        if not isinstance(raw_block, dict):
            continue

        if {"purpose", "source_method_ids", "mandatory_at"}.issubset(raw_block.keys()):
            materialized_rpt_blocks.append(
                {
                    **raw_block,
                    "source_method_ids": _normalize_string_list(raw_block.get("source_method_ids")),
                    "mandatory_at": _normalize_string_list(raw_block.get("mandatory_at")),
                    "complementary_literature_card_ids": _normalize_string_list(
                        raw_block.get("complementary_literature_card_ids")
                    ),
                }
            )
            continue

        if str(raw_block.get("rpt_source") or "") == "core_rpt_set" or raw_block.get("bundle_ref"):
            if core_rpt_set:
                materialized_rpt_blocks.append(_materialize_core_rpt_block(core_rpt_set, raw_block))
            continue

        extension_ref = str(
            raw_block.get("extension_ref") or raw_block.get("extension_id") or ""
        ).strip()
        if str(raw_block.get("rpt_source") or "") == "checkpoint_extension_tests" or extension_ref:
            extension = extension_map.get(extension_ref)
            if extension is not None:
                materialized_rpt_blocks.append(
                    _materialize_extension_rpt_block(extension, raw_block)
                )

    if not materialized_rpt_blocks:
        if core_rpt_set:
            materialized_rpt_blocks.append(_materialize_core_rpt_block(core_rpt_set, {}))
        for extension in checkpoint_extension_tests:
            materialized_rpt_blocks.append(_materialize_extension_rpt_block(extension, {}))

    normalized["core_rpt_set"] = core_rpt_set
    normalized["checkpoint_extension_tests"] = checkpoint_extension_tests
    normalized["checkpoint_templates"] = [
        dict(template)
        for template in reference_check_policy.get("checkpoint_templates", [])
        if isinstance(template, dict)
    ]
    normalized["rpt_blocks"] = materialized_rpt_blocks
    normalized["timing_basis_options"] = _normalize_string_list(
        reference_check_policy.get("timing_basis_options")
    )
    normalized["default_breakpoint_examples"] = _normalize_string_list(
        reference_check_policy.get("default_breakpoint_examples")
    )
    return normalized


def _normalize_method_payload(entry_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    current_support = _normalize_string_list(
        normalized.get("currently_supported_chemistries")
        or normalized.get("supported_chemistries")
    )
    if current_support:
        normalized["currently_supported_chemistries"] = current_support
        normalized["supported_chemistries"] = current_support

    applicable_scope = _normalize_string_list(normalized.get("applicable_chemistry_scope"))
    if applicable_scope:
        normalized["applicable_chemistry_scope"] = applicable_scope

    normalized["required_inputs"] = _normalize_string_list(normalized.get("required_inputs"))
    normalized["recommended_defaults"] = dict(normalized.get("recommended_defaults", {}))

    protocol_template = normalized.get("protocol_template")
    if isinstance(protocol_template, dict):
        normalized["protocol_template"] = {
            **protocol_template,
            "defaults": dict(protocol_template.get("defaults", {})),
            "steps": [
                dict(step)
                for step in protocol_template.get("steps", [])
                if isinstance(step, dict)
            ],
        }

    normalized["conditional_required_inputs"] = [
        dict(item)
        for item in normalized.get("conditional_required_inputs", [])
        if isinstance(item, dict)
    ]
    normalized["optional_inputs"] = _normalize_string_list(normalized.get("optional_inputs"))
    normalized["source_example_defaults"] = dict(normalized.get("source_example_defaults", {}))

    if not normalized.get("method_status"):
        strict_mode = str(normalized.get("strict_reference_policy", {}).get("mode") or "")
        if strict_mode == "outline_only_review_required":
            normalized["method_status"] = "draft_placeholder"
            normalized["execution_readiness"] = str(
                normalized.get("execution_readiness") or "not_releaseable"
            )
            normalized["human_review_required"] = True
        else:
            normalized["method_status"] = "structured_method"
            normalized["execution_readiness"] = str(
                normalized.get("execution_readiness") or "planner_ready_review_required"
            )
            normalized["human_review_required"] = bool(
                normalized.get("human_review_required", True)
            )

    normalized["reference_check_policy"] = _normalize_reference_check_policy(
        normalized.get("reference_check_policy")
    )
    return normalized


def _merge_registry_payloads(
    base_payload: dict[str, Any],
    overlay_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base_payload)
    for key, value in overlay_payload.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _merge_registry_payloads(existing, value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def load_chemistry_registry() -> dict[str, dict[str, Any]]:
    return _read_json(CHEMISTRY_REGISTRY_PATH)


@lru_cache(maxsize=1)
def load_method_registry() -> dict[str, dict[str, Any]]:
    registry = _read_json(METHOD_REGISTRY_PATH)
    for extra_path in sorted(REGISTRY_DIR.glob(METHOD_REGISTRY_GLOB)):
        if extra_path.name == METHOD_REGISTRY_PATH.name:
            continue
        overlay = _read_json(extra_path)
        for entry_id, payload in overlay.items():
            if entry_id in registry:
                registry[entry_id] = _merge_registry_payloads(registry[entry_id], payload)
            else:
                registry[entry_id] = payload
    return {
        entry_id: _normalize_method_payload(entry_id, payload)
        for entry_id, payload in registry.items()
    }


def _build_lookup(
    registry: dict[str, dict[str, Any]],
    *,
    extra_fields: tuple[str, ...] = (),
) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for entry_id, payload in registry.items():
        lookup[_normalize_key(entry_id)] = entry_id
        for alias in payload.get("aliases", []):
            lookup[_normalize_key(alias)] = entry_id
        for field_name in extra_fields:
            value = payload.get(field_name)
            if isinstance(value, str) and value.strip():
                lookup[_normalize_key(value)] = entry_id
    return lookup


@lru_cache(maxsize=1)
def _chemistry_lookup() -> dict[str, str]:
    return _build_lookup(load_chemistry_registry())


@lru_cache(maxsize=1)
def _method_lookup() -> dict[str, str]:
    return _build_lookup(
        load_method_registry(),
        extra_fields=("label", "source_title", "objective_key", "chapter_id"),
    )


def resolve_chemistry_id(query: str) -> str:
    key = _normalize_key(query)
    lookup = _chemistry_lookup()
    if key not in lookup:
        raise KeyError(f"Unknown chemistry profile: {query}")
    return lookup[key]


def resolve_method_id(query: str) -> str:
    key = _normalize_key(query)
    lookup = _method_lookup()
    if key not in lookup:
        raise KeyError(f"Unknown test method: {query}")
    return lookup[key]


def get_chemistry_definition(query: str) -> dict[str, Any]:
    chemistry_id = resolve_chemistry_id(query)
    return _attach_id(chemistry_id, load_chemistry_registry()[chemistry_id])


def get_method_definition(query: str) -> dict[str, Any]:
    method_id = resolve_method_id(query)
    return _attach_id(method_id, load_method_registry()[method_id])


def get_supported_methods_for_chemistry(chemistry: str) -> list[dict[str, Any]]:
    chemistry_definition = get_chemistry_definition(chemistry)
    supported_ids = chemistry_definition.get("supported_methods", [])
    methods = load_method_registry()
    return [
        _attach_id(method_id, methods[method_id])
        for method_id in supported_ids
        if method_id in methods
    ]


def get_default_method_for_objective(objective_key: str) -> dict[str, Any] | None:
    normalized_objective = _normalize_key(objective_key)
    first_match: dict[str, Any] | None = None
    for method_id, payload in load_method_registry().items():
        if _normalize_key(payload.get("objective_key", "")) != normalized_objective:
            continue
        enriched = _attach_id(method_id, payload)
        if payload.get("default_for_objective", False):
            return enriched
        if first_match is None:
            first_match = enriched
    return first_match
