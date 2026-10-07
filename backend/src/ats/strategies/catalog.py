"""Definitions only. No old scores, calibration or promotion are imported."""

from typing import Any

from ats.strategies.definitions import STRATEGY_REGISTRY, ensure_diverse_families_loaded


def strategy_catalog() -> list[dict[str, Any]]:
    ensure_diverse_families_loaded()
    ids = sorted(STRATEGY_REGISTRY)
    return [
        {
            "strategy_id": key,
            "version": "xauusd-research-v1",
            "canonical_symbol": "XAUUSD",
            "compatible_symbols": ["XAUUSD"],
            "status": "RESEARCH_ONLY",
            "implementation_status": "GENERIC_DEFINITION",
            "datasets_tested": [],
            "latest_research_run": None,
            "out_of_sample_status": "NOT_RUN",
            "cost_stress_status": "NOT_RUN",
            "paper_forward_status": "NOT_RUN",
            "promotion_status": "UNVALIDATED_FOR_XAUUSD",
        }
        for key in ids
    ] + [
        {
            "strategy_id": "S5_ORB_XAUUSD",
            "version": "design-v1",
            "canonical_symbol": "XAUUSD",
            "compatible_symbols": ["XAUUSD"],
            "status": "RESEARCH_ONLY",
            "implementation_status": "DESIGN",
            "datasets_tested": [],
            "latest_research_run": None,
            "out_of_sample_status": "NOT_RUN",
            "cost_stress_status": "NOT_RUN",
            "paper_forward_status": "NOT_RUN",
            "promotion_status": "UNVALIDATED_FOR_XAUUSD",
        }
    ]
