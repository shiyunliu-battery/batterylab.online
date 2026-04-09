"""Asset-first workflow scaffold loaders for the Battery Lab Assistant backend."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_REGISTRY_PATH = REPO_ROOT / "data" / "registries" / "lab_workflow_registry.json"

ACTIVE_WORKFLOWS = [
    "Cell lookup and selected-cell context",
    "Method lookup and structured protocol drafting",
    "Preflight QA and review-point assembly",
    "Deterministic cycle CSV analysis",
    "Markdown report drafting",
]

EXPERIMENTAL_MODULES = []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_workflow_asset_registry() -> dict[str, dict[str, Any]]:
    return _read_json(WORKFLOW_REGISTRY_PATH)


def _resolve_repo_path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def _summarize_registered_asset(asset_id: str, definition: dict[str, Any]) -> dict[str, Any]:
    relative_path = str(definition["path"])
    path = _resolve_repo_path(relative_path)
    payload = _read_json(path)
    collection_key = str(definition["collection_key"])
    records = payload.get(collection_key, [])
    required_fields = payload.get("required_fields", [])

    return {
        "id": asset_id,
        "label": definition["label"],
        "category": definition["category"],
        "trust_level": definition["trust_level"],
        "path": relative_path,
        "status": payload.get("status", "unknown"),
        "version": payload.get("version", "unknown"),
        "record_count": len(records) if isinstance(records, list) else 0,
        "collection_key": collection_key,
        "fill_priority": definition["fill_priority"],
        "next_step": definition["next_step"],
        "description": definition["description"],
        "required_fields": required_fields,
    }


def summarize_workflow_assets() -> dict[str, Any]:
    registry = load_workflow_asset_registry()
    asset_summaries = sorted(
        (
            _summarize_registered_asset(asset_id, definition)
            for asset_id, definition in registry.items()
        ),
        key=lambda item: (item["fill_priority"], item["label"].lower()),
    )
    next_fill_priorities = [
        {
            "id": item["id"],
            "label": item["label"],
            "next_step": item["next_step"],
            "path": item["path"],
        }
        for item in asset_summaries
        if item["fill_priority"] <= 2
    ]

    asset_lines = "\n".join(
        [
            (
                f"- `{item['id']}`: {item['label']} "
                f"({item['record_count']} records, trust=`{item['trust_level']}`, path=`{item['path']}`)"
            )
            for item in asset_summaries
        ]
    )
    next_step_lines = "\n".join(
        f"- {item['label']}: {item['next_step']}" for item in next_fill_priorities
    )
    experimental_lines = "\n".join(
        f"- {item['label']}: {item['reason']} (`{item['path']}`)"
        for item in EXPERIMENTAL_MODULES
    )

    return {
        "status": "ok",
        "scope_label": "battery_lab_assistant_v1",
        "active_workflows": ACTIVE_WORKFLOWS,
        "workflow_assets": asset_summaries,
        "next_fill_priorities": next_fill_priorities,
        "experimental_modules": EXPERIMENTAL_MODULES,
        "ui_markdown": "\n".join(
            [
                "## Backend Framework",
                "",
                "### Active Scope",
                "\n".join(f"- {item}" for item in ACTIVE_WORKFLOWS),
                "",
                "### Structured Asset Scaffold",
                asset_lines or "- None.",
                "",
                "### Fill Next",
                next_step_lines or "- None.",
                "",
                "### Experimental Modules Parked Outside The Main Flow",
                experimental_lines or "- None.",
            ]
        ),
    }
