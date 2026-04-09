"""Backward-compatible literature module.

This compatibility shim keeps older imports working after the unified
``battery_agent.knowledge`` migration.
"""

from battery_agent.knowledge import (
    get_knowledge_source as get_literature_source,
    load_knowledge_evidence_cards as load_literature_evidence_cards,
    load_knowledge_source_index as load_literature_source_index,
    search_knowledge_evidence as search_literature_evidence,
)

__all__ = [
    "get_literature_source",
    "load_literature_evidence_cards",
    "load_literature_source_index",
    "search_literature_evidence",
]
