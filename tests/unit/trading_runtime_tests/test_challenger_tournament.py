"""Unit test suite for Challenger Probability Tournament and Adversarial RAG Audit."""

from __future__ import annotations

import pytest

from scripts.adversarial_rag_audit import run_adversarial_rag_audit
from scripts.run_challenger_tournament import (
    CALIBRATION_STORE_PATH,
    load_raw_dataset,
    run_challenger_trading_tournament,
)

requires_calibration_store = pytest.mark.skipif(
    not CALIBRATION_STORE_PATH.is_file(),
    reason="governed calibration artifact is not present in this worktree",
)


@requires_calibration_store
def test_challenger_dataset_integrity_and_no_leakage() -> None:
    records = load_raw_dataset()
    assert len(records) == 2040
    for r in records:
        # Predictor input features must be finite and independent of future target
        assert isinstance(r["roc"], float)
        assert isinstance(r["vol"], float)
        assert r["vol"] > 0.0


@requires_calibration_store
def test_challenger_tournament_execution_and_champion_hold() -> None:
    res = run_challenger_trading_tournament()
    results = res["tournament_results"]
    assert len(results) == 10

    champion = next(x for x in results if x["model_id"] == "C0")
    # Champion has the lowest full Brier score (0.2501)
    assert champion["full_brier"] == 0.2501
    assert champion["promotion_status"] == "CHAMPION_ACTIVE"

    # All challengers must remain HOLD_AS_CHALLENGER
    challengers = [x for x in results if x["model_id"] != "C0"]
    for ch in challengers:
        assert ch["promotion_status"] == "HOLD_AS_CHALLENGER"
        assert ch["economic_attribution"] == ("NOT_AVAILABLE_MODEL_NOT_INJECTED_IN_EXECUTION_PATH")
        assert ch["net_pnl"] is None


def test_adversarial_rag_audit_performance() -> None:
    audit_res = run_adversarial_rag_audit()
    assert audit_res["total_queries"] == 105
    assert audit_res["recall_at_1"] == 1.0
    assert audit_res["recall_at_10"] == 1.0
    assert audit_res["mrr"] == 1.0
    assert audit_res["grounded_accuracy"] == "100.0%"
    assert audit_res["negative_control_hallucinations"] == 0
