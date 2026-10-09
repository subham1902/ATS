from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from ats.execution.account_reconciliation import (
    ExpectedAccount,
    Exposure,
    ObservedAccount,
    OwnedExposure,
    reconcile_account,
)


def fixture(mode="LIVE"):
    now = datetime.now(UTC)
    exposure = Exposure(
        broker_id="101",
        kind="POSITION",
        symbol="XAUUSDm",
        side="BUY",
        volume=".01",
        sl="3900",
        tp="4100",
    )
    expected = ExpectedAccount(
        account_id="ACC-1",
        session_identity_hash="a" * 64,
        mode=mode,
        broker_symbol="XAUUSDm",
        unresolved_execution_ids=(),
        exposures=(
            OwnedExposure(
                execution_id="EXE-1", strategy_id="XAU-003", strategy_version=1, exposure=exposure
            ),
        ),
    )
    observed = ObservedAccount(
        account_id="ACC-1",
        session_identity_hash="a" * 64,
        mode=mode,
        observed_at=now,
        connected=True,
        complete_account_snapshot=True,
        exposures=(exposure,),
    )
    return expected, observed, now


@pytest.mark.parametrize("mode", ["LIVE", "DEMO"])
def test_snapshot_match_has_no_financial_authority(mode):
    expected, observed, now = fixture(mode)
    result = reconcile_account(expected, observed, now)
    assert result.state == "SNAPSHOT_MATCHED"
    assert not result.grants_authority
    assert not result.releases_reservations


@pytest.mark.parametrize(
    "changes",
    [
        {"account_id": "ACC-2"},
        {"session_identity_hash": "b" * 64},
        {"mode": "DEMO"},
        {"connected": False},
        {"complete_account_snapshot": False},
        {"mode": "UNKNOWN"},
    ],
)
def test_identity_and_unknown_snapshot_block(changes):
    expected, observed, now = fixture()
    assert reconcile_account(expected, observed.model_copy(update=changes), now).state == "UNKNOWN"


def test_absent_position_never_proves_closed_trade_or_frees_risk():
    expected, observed, now = fixture()
    result = reconcile_account(expected, observed.model_copy(update={"exposures": ()}), now)
    assert result.reason_codes == ("EXPECTED_EXPOSURE_MISSING",)
    assert not result.releases_reservations


def test_manual_other_symbol_exposure_is_account_risk():
    expected, observed, now = fixture()
    other = observed.exposures[0].model_copy(update={"broker_id": "102", "symbol": "EURUSD"})
    result = reconcile_account(
        expected, observed.model_copy(update={"exposures": (*observed.exposures, other)}), now
    )
    assert "UNOWNED_ACCOUNT_EXPOSURE" in result.reason_codes


@pytest.mark.parametrize(
    "changes",
    [
        {"volume": Decimal(".005")},
        {"sl": Decimal(0)},
        {"tp": Decimal(0)},
        {"side": "SELL"},
        {"symbol": "GOLD"},
    ],
)
def test_partial_fill_and_protection_changes_require_reconciliation(changes):
    expected, observed, now = fixture()
    modified = observed.exposures[0].model_copy(update=changes)
    result = reconcile_account(
        expected, observed.model_copy(update={"exposures": (modified,)}), now
    )
    assert "BROKER_VOLUME_SIDE_SYMBOL_OR_PROTECTION_MISMATCH" in result.reason_codes


def test_unknown_ack_cannot_be_cleared_by_flat_snapshot():
    expected, observed, now = fixture()
    expected = expected.model_copy(
        update={"exposures": (), "unresolved_execution_ids": ("EXE-UNKNOWN",)}
    )
    observed = observed.model_copy(update={"exposures": ()})
    assert reconcile_account(expected, observed, now).state == "RECONCILIATION_REQUIRED"


def test_stale_future_and_duplicate_observations():
    expected, observed, now = fixture()
    for delta in (-6, 1):
        assert (
            reconcile_account(
                expected,
                observed.model_copy(update={"observed_at": now + timedelta(seconds=delta)}),
                now,
            ).state
            == "UNKNOWN"
        )
    with pytest.raises(ValueError, match="DUPLICATE"):
        reconcile_account(
            expected, observed.model_copy(update={"exposures": observed.exposures * 2}), now
        )
