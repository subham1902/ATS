from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from ats.trading_runtime.connected_readiness import (
    ConnectedReadinessInput,
    InstrumentSpecTruth,
    ReadinessContext,
    evaluate_connected_readiness,
)
from ats.trading_runtime.session_reconciliation import ReconciliationResult, ReconciliationState

NOW = datetime(2026, 8, 31, 3, 35, tzinfo=UTC)


def reconciliation(
    state: ReconciliationState = ReconciliationState.CLEAN_NO_PRIOR_SESSION,
) -> ReconciliationResult:
    return ReconciliationResult(
        state,
        NOW.isoformat(),
        "state.json",
        None,
        None,
        (),
        (),
        False,
        False,
        None,
        None,
        0,
        False,
        "TEST",
    )


def probe(**changes: Any) -> ConnectedReadinessInput:
    specs = (
        InstrumentSpecTruth(
            "NIFTY", "NSE_INDEX|Nifty 50", 65, "0.05", "2026-09-03", ("NCE", "NPE")
        ),
        InstrumentSpecTruth(
            "BANKNIFTY", "NSE_INDEX|Nifty Bank", 30, "0.05", "2026-09-30", ("BCE", "BPE")
        ),
    )
    base = ConnectedReadinessInput(
        ReadinessContext.CONNECTED_PREMARKET,
        NOW,
        "2026-08-31",
        "PREOPEN",
        False,
        "AGGRESSIVE",
        None,
        "PAPER",
        False,
        False,
        Decimal("100000"),
        None,
        "PASS",
        "PASS",
        "PASS",
        "CONFIGURED_DECODER_READY",
        "PASS",
        specs,
        0,
        0,
        "PRE_OPEN_NOT_APPLICABLE",
        "CONFIGURED_PAPERBROKER_READY",
        "RECORDER_CONFIG_READY",
        "FORENSICS_CONFIG_READY",
        "CONFIGURED_READY",
        reconciliation(),
    )
    return replace(base, **changes)


def test_connected_preopen_can_be_ready_without_ticks_but_cannot_enter() -> None:
    result = evaluate_connected_readiness(probe())
    assert result.ready_for_a2_paper_session is True
    assert result.stage2_market_data_ready is False
    assert result.can_enter_new_risk is False


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"provider_auth": "TOKEN_INVALID"}, "PROVIDER_AUTH_FAILED"),
        ({"provider_reference": "REFERENCE_DATA_EMPTY", "specs": ()}, "PROVIDER_REFERENCE_FAILED"),
        ({"execution_target": "REAL", "real_broker_enabled": True}, "EXECUTION_AUTHORITY_UNKNOWN"),
        ({"live_money_enabled": True}, "LIVE_MONEY_OR_AUTHORITY_UNKNOWN"),
        ({"configured_capital": Decimal("99999")}, "CAPITAL_MISMATCH"),
        ({"recorder_status": "RECORDER_CONFIG_UNUSABLE"}, "RECORDER_CONFIG_UNUSABLE"),
        ({"a04_status": "UNKNOWN"}, "A04_CONFIG_UNAVAILABLE"),
    ],
)
def test_connected_safety_failures_block(changes: dict[str, Any], reason: str) -> None:
    result = evaluate_connected_readiness(probe(**changes))
    assert result.ready_for_a2_paper_session is False
    assert reason in result.blocking_reasons


def test_none_provider_contracts_can_never_be_ready() -> None:
    result = evaluate_connected_readiness(
        probe(provider_reference="UNKNOWN", specs=(), subscription_status="UNKNOWN")
    )
    assert not result.ready_for_a2_paper_session


def test_market_open_requires_fresh_stage_two_data() -> None:
    stale = evaluate_connected_readiness(
        probe(
            market_phase="ENTRY_ALLOWED",
            session_can_enter=True,
            market_data_stage="MARKET_OPEN_DATA_NOT_OBSERVED",
        )
    )
    assert not stale.ready_for_a2_paper_session
    assert not stale.can_enter_new_risk
    fresh = evaluate_connected_readiness(
        probe(
            market_phase="ENTRY_ALLOWED",
            session_can_enter=True,
            market_data_stage="MARKET_OPEN_DATA_READY",
        )
    )
    assert fresh.ready_for_a2_paper_session
    assert fresh.can_enter_new_risk


def test_offline_synthetic_cannot_emit_connected_verdict() -> None:
    result = evaluate_connected_readiness(probe(context=ReadinessContext.OFFLINE_SYNTHETIC))
    assert result.status_verdict != "READY_FOR_A2_PAPER_SESSION"


def test_reconciliation_is_deterministic_exit_three() -> None:
    unresolved = reconciliation(ReconciliationState.UNFINALIZED_SESSION)
    result = evaluate_connected_readiness(probe(reconciliation=unresolved))
    assert result.exit_code == 3
    assert result.status_verdict == "BLOCKED_RECONCILIATION_REQUIRED"
