import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest
from ats.execution.demo_supervisor import (
    CommissionedFacts,
    DemoApproval,
    DemoApprovalStore,
    DemoExecutionSupervisor,
    PeriodBook,
    commissioned_risk,
)
from ats.execution.external import ExternalLedger
from pydantic import ValidationError

from tests.unit.test_external_authority import Adapter, inputs


def fixture_inputs():
    intent, account, _, now = inputs()
    intent = intent.model_copy(
        update={"volume": Decimal(".01"), "risk_cash": Decimal("10.22"), "margin_cash": Decimal(5)}
    )
    account = account.model_copy(
        update={"observed_risk_cash": Decimal(10), "observed_margin_cash": Decimal(5)}
    )
    approval = DemoApproval(
        approval_id="APP-1",
        account_id=intent.account_id,
        session_identity_hash="a" * 64,
        operator_consent_reference="operator-action-123",
        strategy_id=intent.strategy_id,
        strategy_version=1,
        research_preset_hash="b" * 64,
        broker_symbol=intent.broker_symbol,
        tested_starting_equity=1000,
        minimum_current_equity=900,
        maximum_current_equity=2000,
        risk_fraction=".015",
        maximum_volume=".01",
        roundtrip_cost_per_lot=22,
        expires_at=now + timedelta(days=1),
    )
    facts = CommissionedFacts(
        account=account,
        session_identity_hash=approval.session_identity_hash,
        research_preset_hash=approval.research_preset_hash,
        verified_proposal_hash=hashlib.sha256(intent.model_dump_json().encode()).hexdigest(),
        funded_equity=1000,
        current_equity=1000,
        account_wide_flat=True,
        no_pending_orders=True,
        periods=PeriodBook(
            utc_day=now.strftime("%Y-%m-%d"),
            utc_month=now.strftime("%Y-%m"),
            starting_day_equity=1000,
            starting_month_equity=1000,
            net_booked_day=0,
            net_booked_month=0,
            entries_today=0,
            losing_trades_today=0,
            last_close_at=None,
            observed_at=now,
            evidence_hash="c" * 64,
            complete_history=True,
            verified_baselines=True,
            verified_historical_utc=True,
        ),
    )
    return intent, approval, facts, now


def test_durable_approval_and_single_use_demo_dispatch(tmp_path):
    intent, approval, facts, now = fixture_inputs()
    approvals = DemoApprovalStore(tmp_path / "approvals.db")
    approvals.approve(approval)
    restarted = DemoApprovalStore(approvals.path)
    assert restarted.get(approval.approval_id) == approval
    ledger = ExternalLedger(tmp_path / "execution.db")
    adapter = Adapter()
    supervisor = DemoExecutionSupervisor(restarted, ledger, lambda _: facts, adapter, lambda: now)
    assert supervisor.dispatch(approval.approval_id, intent)["state"] == "ACCEPTED"
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        supervisor.dispatch(approval.approval_id, intent)
    assert adapter.calls == 1
    assert ledger.list()[0]["authority"] == "A3_EXTERNAL_DEMO"


@pytest.mark.parametrize(
    "changes",
    [
        {"session_identity_hash": "d" * 64},
        {"research_preset_hash": "d" * 64},
        {"verified_proposal_hash": "d" * 64},
        {"funded_equity": Decimal(500)},
        {"current_equity": Decimal(500)},
    ],
)
def test_identity_evidence_and_capital_cannot_be_substituted(changes):
    intent, approval, facts, now = fixture_inputs()
    with pytest.raises(ValueError):
        commissioned_risk(intent, approval, facts.model_copy(update=changes), now)


def test_live_mode_not_admitted_by_demo_commissioning():
    intent, approval, facts, now = fixture_inputs()
    live = facts.account.model_copy(update={"mode": "LIVE"})
    with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
        commissioned_risk(intent, approval, facts.model_copy(update={"account": live}), now)


@pytest.mark.parametrize(
    "changes",
    [
        {"net_booked_day": Decimal(-20)},
        {"net_booked_month": Decimal(-55)},
        {"utc_day": "2020-01-01"},
        {"utc_month": "2020-01"},
        {"entries_today": 3},
        {"losing_trades_today": 2},
    ],
)
def test_period_limits_require_remaining_risk_capacity(changes):
    intent, approval, facts, now = fixture_inputs()
    periods = facts.periods.model_copy(update=changes)
    with pytest.raises(ValueError):
        commissioned_risk(intent, approval, facts.model_copy(update={"periods": periods}), now)


def test_net_booked_profits_offset_losses_without_changing_denominator():
    intent, approval, facts, now = fixture_inputs()
    periods = facts.periods.model_copy(update={"net_booked_day": Decimal(20)})
    risk = commissioned_risk(intent, approval, facts.model_copy(update={"periods": periods}), now)
    assert risk.max_daily_loss == 45  # Start-of-day 1,000 * 2.5% + net booked 20.
    assert risk.max_trade_risk == 15


def test_cooldown_future_and_stale_period_observations():
    intent, approval, facts, now = fixture_inputs()
    for changes in (
        {"last_close_at": now - timedelta(seconds=899)},
        {"last_close_at": now + timedelta(seconds=1)},
        {"observed_at": now - timedelta(seconds=6)},
        {"observed_at": now + timedelta(seconds=1)},
    ):
        periods = facts.periods.model_copy(update=changes)
        with pytest.raises(ValueError):
            commissioned_risk(intent, approval, facts.model_copy(update={"periods": periods}), now)


@pytest.mark.parametrize(
    "field", ["complete_history", "verified_baselines", "verified_historical_utc"]
)
def test_unknown_or_incomplete_period_provenance_never_commissions(field):
    _, _, facts, _ = fixture_inputs()
    document = facts.periods.model_dump()
    document[field] = False
    with pytest.raises(ValidationError):
        PeriodBook.model_validate(document)


def test_stop_commission_and_margin_are_broker_observed_not_trusted_from_intent():
    intent, approval, facts, now = fixture_inputs()
    for account_changes in ({"observed_risk_cash": Decimal("10.01")},):
        account = facts.account.model_copy(update=account_changes)
        with pytest.raises(ValueError, match="COST_RISK_UNDERSTATED"):
            commissioned_risk(intent, approval, facts.model_copy(update={"account": account}), now)
    intent = intent.model_copy(update={"margin_cash": Decimal(301)})
    facts = facts.model_copy(
        update={
            "verified_proposal_hash": hashlib.sha256(intent.model_dump_json().encode()).hexdigest()
        }
    )
    with pytest.raises(ValueError, match="MARGIN_ALLOCATION_LIMIT"):
        commissioned_risk(intent, approval, facts, now)


def test_revocation_between_reservation_and_dispatch_never_calls_adapter(tmp_path):
    intent, approval, facts, now = fixture_inputs()
    approvals = DemoApprovalStore(tmp_path / "a.db")
    approvals.approve(approval)
    adapter = Adapter()

    def observe(_):
        approvals.revoke(approval.approval_id)
        return facts

    ledger = ExternalLedger(tmp_path / "e.db")
    supervisor = DemoExecutionSupervisor(approvals, ledger, observe, adapter, lambda: now)
    with pytest.raises(ValueError, match="OPERATOR_APPROVAL_REQUIRED"):
        supervisor.dispatch(approval.approval_id, intent)
    assert ledger.list()[0]["state"] == "RESERVED"
    assert adapter.calls == 0


def test_approval_is_immutable_and_corruption_fails_closed(tmp_path):
    _, approval, _, _ = fixture_inputs()
    approvals = DemoApprovalStore(tmp_path / "a.db")
    approvals.approve(approval)
    with pytest.raises(ValueError, match="IMMUTABLE_APPROVAL"):
        approvals.approve(approval.model_copy(update={"risk_fraction": Decimal(".02")}))
    with approvals._db() as db:
        db.execute("UPDATE approvals SET document='{}'")
    with pytest.raises(ValueError, match="APPROVAL_CORRUPT"):
        approvals.get(approval.approval_id)
