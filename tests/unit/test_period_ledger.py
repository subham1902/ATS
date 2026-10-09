import sqlite3
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.execution.period_ledger import (
    BookedDeal,
    BrokerPeriodLedger,
    DealHistory,
    PeriodBaseline,
)

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
DAY = NOW.replace(hour=0)
MONTH = DAY.replace(day=1)


def deal(ticket, at=NOW, kind="TRADE", profit="0", commission="0", swap="0", fee="0"):
    return BookedDeal(
        deal_id=ticket,
        timestamp=at,
        kind=kind,
        profit=profit,
        commission=commission,
        swap=swap,
        fee=fee,
        symbol="EURUSD",
    )


def setup(tmp_path, deals=(), balance="1000", day_balance="1000"):
    ledger = BrokerPeriodLedger(tmp_path / "periods.db")
    for at, value in ((MONTH, "1000"), (DAY, day_balance)):
        ledger.record_baseline(
            PeriodBaseline(
                account_id="ACC-1",
                session_identity_hash="a" * 64,
                currency="USD",
                boundary=at,
                balance=value,
                equity=value,
                source_evidence_hash="b" * 64,
            )
        )
    history = DealHistory(
        account_id="ACC-1",
        session_identity_hash="a" * 64,
        currency="USD",
        observed_at=NOW,
        coverage_start=MONTH,
        coverage_end=NOW,
        complete_account_history=True,
        historical_utc_verified=True,
        timezone_evidence_hash="c" * 64,
        observed_balance=balance,
        balance_tolerance="0.001",
        deals=deals,
    )
    return ledger, history


def budget(ledger, now=NOW, account="ACC-1"):
    return ledger.budget(account, now, Decimal(".03"), Decimal(".08"))


def test_net_realized_costs_cashflows_all_symbols_and_restart(tmp_path):
    deals = (
        deal("old", DAY - timedelta(days=1), profit="-20", swap="-2"),
        deal("loss", profit="-25", commission="-1", swap="-1", fee="-1"),
        deal("profit", profit="10", commission="-1"),
        deal("deposit", kind="CASH_FLOW", profit="100"),
    )
    ledger, history = setup(tmp_path, deals, balance="1059", day_balance="978")
    ledger.record_history(history)
    result = budget(BrokerPeriodLedger(ledger.path))
    assert result.state == "VERIFIED_BUDGET"
    assert result.net_booked_day == -19
    assert result.net_booked_month == -41
    assert result.cash_flows_month == 100
    assert result.daily_remaining == Decimal("10.34")
    assert result.monthly_remaining == 39
    assert result.grants_authority is False


def test_empty_history_requires_actual_complete_proof(tmp_path):
    ledger, history = setup(tmp_path)
    ledger.record_history(history)
    assert budget(ledger).monthly_remaining == 80
    ledger.record_history(history.model_copy(update={"complete_account_history": False}))
    assert budget(ledger).state == "UNKNOWN"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"complete_account_history": False}, "COMPLETE_ACCOUNT_HISTORY_REQUIRED"),
        ({"coverage_start": DAY}, "COMPLETE_ACCOUNT_HISTORY_REQUIRED"),
        ({"coverage_end": NOW - timedelta(seconds=1)}, "COMPLETE_ACCOUNT_HISTORY_REQUIRED"),
        ({"historical_utc_verified": False}, "HISTORICAL_UTC_EVIDENCE_REQUIRED"),
        ({"observed_balance": Decimal(1001)}, "BROKER_BALANCE_RECONCILIATION_REQUIRED"),
        ({"session_identity_hash": "d" * 64}, "PERIOD_BASELINE_IDENTITY_MISMATCH"),
    ],
)
def test_unknown_evidence_is_not_a_zero_loss_budget(tmp_path, changes, reason):
    ledger, history = setup(tmp_path)
    ledger.record_history(history.model_copy(update=changes))
    result = budget(ledger)
    assert result.state == "UNKNOWN"
    assert reason in result.reason_codes
    assert result.daily_remaining is None
    assert result.net_booked_month is None


def test_unknown_deal_kind_blocks_even_when_balance_matches(tmp_path):
    ledger, history = setup(tmp_path, (deal("unknown", kind="UNKNOWN"),))
    ledger.record_history(history)
    assert "UNKNOWN_BROKER_DEAL_KIND" in budget(ledger).reason_codes


def test_missing_baseline_cross_account_and_rollover(tmp_path):
    ledger, history = setup(tmp_path)
    ledger.record_history(history)
    assert budget(ledger, account="ACC-2").state == "UNKNOWN"
    assert budget(ledger, now=NOW + timedelta(days=1)).state == "UNKNOWN"


def test_day_baseline_must_reconcile_to_month_history(tmp_path):
    ledger, history = setup(tmp_path, day_balance="1010")
    ledger.record_history(history)
    assert "DAY_BASELINE_BALANCE_RECONCILIATION_REQUIRED" in budget(ledger).reason_codes


def test_baseline_immutable_idempotent_and_exact_boundary(tmp_path):
    ledger, _ = setup(tmp_path)
    baseline = PeriodBaseline(
        account_id="ACC-1",
        session_identity_hash="a" * 64,
        currency="USD",
        boundary=DAY,
        balance=1000,
        equity=1000,
        source_evidence_hash="b" * 64,
    )
    ledger.record_baseline(baseline)
    with pytest.raises(ValueError, match="IMMUTABLE"):
        ledger.record_baseline(baseline.model_copy(update={"equity": Decimal(900)}))
    with pytest.raises(ValueError, match="EXACT_UTC"):
        ledger.record_baseline(baseline.model_copy(update={"boundary": NOW}))


def test_duplicate_corrections_and_removed_deals_require_review(tmp_path):
    observed = deal("one", profit="-10")
    ledger, history = setup(tmp_path, (observed,), balance="990")
    assert ledger.record_history(history) == ledger.record_history(history)
    for deals in ((), (deal("one", profit="-5"),)):
        with pytest.raises(ValueError, match="CORRECTION"):
            ledger.record_history(history.model_copy(update={"deals": deals}))
    with pytest.raises(ValueError, match="DUPLICATE"):
        ledger.record_history(history.model_copy(update={"deals": (observed, observed)}))


def test_stale_future_and_naive_time(tmp_path):
    ledger, history = setup(tmp_path)
    ledger.record_history(history)
    for delta in (-1, 6):
        assert (
            "FRESH_HISTORY_REQUIRED" in budget(ledger, NOW + timedelta(seconds=delta)).reason_codes
        )
    with pytest.raises(ValueError, match="UTC"):
        budget(ledger, NOW.replace(tzinfo=None))


def test_tampered_database_fail_closed(tmp_path):
    ledger, history = setup(tmp_path)
    ledger.record_history(history)
    with sqlite3.connect(ledger.path) as db:
        db.execute("UPDATE history_snapshots SET document='{}'")
    with pytest.raises(ValueError, match="CORRUPT"):
        budget(ledger)


def test_negative_remaining_budget_preserved(tmp_path):
    ledger, history = setup(tmp_path, (deal("loss", profit="-100"),), balance="900")
    ledger.record_history(history)
    result = budget(ledger)
    assert result.daily_remaining == -70
    assert result.monthly_remaining == -20


def test_limits_cannot_exceed_requested_caps(tmp_path):
    ledger, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="INVALID_PERIOD_LOSS_LIMITS"):
        ledger.budget("ACC-1", NOW, Decimal(".031"), Decimal(".08"))
