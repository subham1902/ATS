from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.execution.external import AccountFacts, ExternalIntent, ExternalLedger, RiskProfile


def inputs(account="ACC-1", mode="DEMO", key="one"):
    now = datetime.now(UTC)
    intent = ExternalIntent(
        account_id=account,
        strategy_id="XAU-003",
        strategy_version=1,
        signal_id="signal",
        broker_symbol="XAUUSDm",
        side="BUY",
        volume=".1",
        entry=2000,
        sl=1990,
        tp=2020,
        risk_cash=100,
        margin_cash=50,
        max_deviation_points=5,
        expires_at=now + timedelta(seconds=20),
        idempotency=key,
    )
    facts = AccountFacts(
        account_id=account,
        broker_symbol="XAUUSDm",
        mode=mode,
        execution_enabled=True,
        connected=True,
        reconciled=True,
        strategy_eligible=True,
        eligible_strategy_version=1,
        allowed_strategy_ids=("XAU-003",),
        killed=False,
        quote_time=now,
        snapshot_time=now,
        free_margin=1000,
        daily_loss=0,
        monthly_loss=0,
        open_risk=0,
        strategy_risk=0,
        positions=0,
        volume_min=".01",
        volume_max=10,
        volume_step=".01",
        tick_size=".01",
        observed_risk_cash=100,
        observed_margin_cash=50,
    )
    risk = RiskProfile(
        version="R1",
        max_trade_risk=100,
        max_daily_loss=100,
        max_monthly_loss=300,
        max_open_risk=200,
        max_volume=1,
        max_positions=2,
        max_strategy_risk=200,
    )
    return intent, facts, risk, now


class Adapter:
    def __init__(self, outcome="ACCEPTED"):
        self.calls = 0
        self.outcome = outcome

    def submit(self, intent):
        self.calls += 1
        if self.outcome == "timeout":
            raise TimeoutError("vendor exception with secrets must not escape")
        return {"state": self.outcome, "broker_order_id": 42}


@pytest.mark.parametrize("mode", ["DEMO", "LIVE"])
def test_same_pipeline_distinct_external_scope(tmp_path, mode):
    intent, facts, risk, now = inputs(mode=mode)
    ledger = ExternalLedger(tmp_path / "execution.db")
    execution = ledger.reserve(intent, facts, risk, now)
    assert ledger.reserve(intent, facts, risk, now) == execution
    adapter = Adapter()
    assert ledger.dispatch(execution, facts, risk, now, adapter)["state"] == "ACCEPTED"
    with pytest.raises(ValueError):
        ledger.dispatch(execution, facts, risk, now, adapter)
    assert adapter.calls == 1
    assert ledger.list()[0]["authority"] == (
        "A3_EXTERNAL_DEMO" if mode == "DEMO" else "A4_EXTERNAL_LIVE"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"mode": "UNKNOWN"},
        {"execution_enabled": False},
        {"connected": False},
        {"reconciled": False},
        {"strategy_eligible": False},
        {"killed": True},
        {"allowed_strategy_ids": ()},
        {"eligible_strategy_version": 2},
        {"account_id": "OTHER"},
        {"broker_symbol": "OTHER"},
        {"positions": 2},
        {"daily_loss": Decimal(100)},
        {"monthly_loss": Decimal(201)},
        {"free_margin": Decimal(1)},
        {"observed_risk_cash": Decimal(101)},
        {"observed_margin_cash": Decimal(51)},
    ],
)
def test_fail_closed_gates(tmp_path, changes):
    intent, facts, risk, now = inputs()
    with pytest.raises(ValueError):
        ExternalLedger(tmp_path / "e.db").reserve(
            intent, facts.model_copy(update=changes), risk, now
        )


def test_stale_future_and_expired(tmp_path):
    intent, facts, risk, now = inputs()
    ledger = ExternalLedger(tmp_path / "e.db")
    for seconds in (-6, 1):
        with pytest.raises(ValueError):
            ledger.reserve(
                intent,
                facts.model_copy(update={"quote_time": now + timedelta(seconds=seconds)}),
                risk,
                now,
            )
    with pytest.raises(ValueError):
        ledger.reserve(intent, facts, risk, now + timedelta(seconds=30))


def test_unknown_outcome_persists_and_other_account_isolated(tmp_path):
    intent, facts, risk, now = inputs()
    ledger = ExternalLedger(tmp_path / "e.db")
    execution = ledger.reserve(intent, facts, risk, now)
    adapter = Adapter("timeout")
    assert ledger.dispatch(execution, facts, risk, now, adapter)["state"] == "UNKNOWN"
    restarted = ExternalLedger(ledger.path)
    with pytest.raises(ValueError):
        restarted.dispatch(execution, facts, risk, now, adapter)
    with pytest.raises(ValueError, match="RECONCILIATION_REQUIRED"):
        restarted.reserve(intent.model_copy(update={"idempotency": "another"}), facts, risk, now)
    other = inputs(account="ACC-2")
    assert restarted.reserve(*other)
    assert "vendor" not in str(ledger.list())
    assert adapter.calls == 1


def test_mode_change_and_paper_token_rejected(tmp_path):
    intent, facts, risk, now = inputs()
    ledger = ExternalLedger(tmp_path / "e.db")
    execution = ledger.reserve(intent, facts, risk, now)
    with pytest.raises(ValueError, match="SCOPE_CHANGED"):
        ledger.dispatch(execution, facts.model_copy(update={"mode": "LIVE"}), risk, now, Adapter())
    with pytest.raises(ValueError):
        ledger.dispatch("A2_PAPER", facts, risk, now, Adapter())


def test_reservations_prevent_overcommit_and_conflict(tmp_path):
    intent, facts, risk, now = inputs()
    # Two reservations need capacity in every budget, including daily booked loss.
    risk = risk.model_copy(update={"max_daily_loss": Decimal(200)})
    ledger = ExternalLedger(tmp_path / "e.db")
    ledger.reserve(intent, facts, risk, now)
    with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
        ledger.reserve(intent.model_copy(update={"volume": Decimal(".2")}), facts, risk, now)
    ledger.reserve(intent.model_copy(update={"idempotency": "second"}), facts, risk, now)
    with pytest.raises(ValueError, match="RESERVATION_LIMIT"):
        ledger.reserve(intent.model_copy(update={"idempotency": "third"}), facts, risk, now)


def test_remaining_daily_risk_and_same_version_risk_mutation_block(tmp_path):
    intent, facts, risk, now = inputs()
    ledger = ExternalLedger(tmp_path / "e.db")
    with pytest.raises(ValueError, match="ACCOUNT_RISK_LIMIT"):
        ledger.reserve(intent, facts.model_copy(update={"daily_loss": Decimal(1)}), risk, now)
    execution = ledger.reserve(intent, facts, risk, now)
    with pytest.raises(ValueError, match="EXTERNAL_SCOPE_CHANGED"):
        ledger.dispatch(
            execution,
            facts,
            risk.model_copy(update={"max_open_risk": Decimal(300)}),
            now,
            Adapter(),
        )


def test_accepted_or_ambiguous_sibling_blocks_preexisting_reservation(tmp_path):
    intent, facts, risk, now = inputs()
    risk = risk.model_copy(update={"max_daily_loss": Decimal(200)})
    ledger = ExternalLedger(tmp_path / "e.db")
    first = ledger.reserve(intent, facts, risk, now)
    second = ledger.reserve(intent.model_copy(update={"idempotency": "second"}), facts, risk, now)
    adapter = Adapter()
    ledger.dispatch(first, facts, risk, now, adapter)
    with pytest.raises(ValueError, match="RECONCILIATION_REQUIRED"):
        ledger.dispatch(second, facts, risk, now, adapter)
    assert adapter.calls == 1


def test_monthly_reservations_and_dispatch_recheck(tmp_path):
    intent, facts, risk, now = inputs(mode="LIVE")
    risk = risk.model_copy(
        update={"max_daily_loss": Decimal(1000), "max_monthly_loss": Decimal(150)}
    )
    ledger = ExternalLedger(tmp_path / "e.db")
    execution = ledger.reserve(intent, facts, risk, now)
    with pytest.raises(ValueError, match="RESERVATION_LIMIT"):
        ledger.reserve(intent.model_copy(update={"idempotency": "second"}), facts, risk, now)
    adapter = Adapter()
    with pytest.raises(ValueError, match="ACCOUNT_RISK_LIMIT"):
        ledger.dispatch(
            execution, facts.model_copy(update={"monthly_loss": Decimal(51)}), risk, now, adapter
        )
    assert adapter.calls == 0


def test_unknown_monthly_budget_rejected():
    _, facts, risk, _ = inputs()
    for model, field in ((facts, "monthly_loss"), (risk, "max_monthly_loss")):
        document = model.model_dump()
        document.pop(field)
        with pytest.raises(ValueError):
            type(model).model_validate(document)


def test_dispatch_counts_other_reservations_against_monthly_budget(tmp_path):
    intent, facts, risk, now = inputs(mode="LIVE")
    risk = risk.model_copy(
        update={"max_daily_loss": Decimal(1000), "max_monthly_loss": Decimal(250)}
    )
    ledger = ExternalLedger(tmp_path / "e.db")
    first = ledger.reserve(intent, facts, risk, now)
    ledger.reserve(intent.model_copy(update={"idempotency": "second"}), facts, risk, now)
    adapter = Adapter()
    with pytest.raises(ValueError, match="RESERVATION_LIMIT"):
        ledger.dispatch(
            first, facts.model_copy(update={"monthly_loss": Decimal(51)}), risk, now, adapter
        )
    assert adapter.calls == 0
