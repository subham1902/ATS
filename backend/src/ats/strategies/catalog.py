"""Compatibility projection of the canonical lineage registry; no second state store."""

from typing import Any

from ats.datasets.ingestion import data_root
from ats.strategies.lineages import bootstrap_store


def strategy_catalog() -> list[dict[str, Any]]:
    store = bootstrap_store(data_root() / "system" / "strategies" / "registry.sqlite3")
    return [
        {
            **record.model_dump(mode="json"),
            "compatible_symbols": ["XAUUSD"],
            "implementation_status": (
                "DESIGN" if record.definition_id == "S5_ORB_XAUUSD" else "GENERIC_DEFINITION"
            ),
            "latest_research_run": None,
            "out_of_sample_status": "NOT_RUN",
            "cost_stress_status": "NOT_RUN",
            "paper_forward_status": "NOT_RUN",
            "promotion_status": "UNVALIDATED_FOR_XAUUSD",
        }
        for record in store.list()
    ]
