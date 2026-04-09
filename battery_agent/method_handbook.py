"""Backward-compatible method handbook module.

This compatibility shim keeps older imports working after the unified
``battery_agent.knowledge`` migration.
"""

from battery_agent.knowledge import (
    get_method_handbook_source,
    get_method_handbook_source_for_method,
    load_method_handbook_evidence_cards,
    load_method_handbook_source_index,
)

__all__ = [
    "get_method_handbook_source",
    "get_method_handbook_source_for_method",
    "load_method_handbook_evidence_cards",
    "load_method_handbook_source_index",
]
