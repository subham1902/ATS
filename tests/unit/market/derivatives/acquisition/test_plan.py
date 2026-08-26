from __future__ import annotations

import pytest
from ats.market.derivatives.acquisition import (
    OI_RESAMPLE_RULE,
    AcquisitionObjective,
    PlannedAcquisition,
    derivatives_readiness_plan,
)
from ats.market.derivatives.contract_master import DerivativeUnderlying


class TestReadinessPlan:
    def test_plan_covers_both_research_underlyings(self) -> None:
        plan = derivatives_readiness_plan()
        underlyings = {item.underlying for item in plan.items}
        assert underlyings == {DerivativeUnderlying.NIFTY, DerivativeUnderlying.BANKNIFTY}

    def test_every_item_requires_authorization(self) -> None:
        for item in derivatives_readiness_plan().items:
            assert item.requires_authorization is True

    def test_underlying_candles_target_one_minute_source(self) -> None:
        plan = derivatives_readiness_plan()
        candles = [
            item
            for item in plan.items
            if item.objective is AcquisitionObjective.UNDERLYING_CANDLES_1M
        ]
        assert len(candles) == 2
        assert all(item.interval_minutes == 1 for item in candles)

    def test_items_are_unique(self) -> None:
        items = derivatives_readiness_plan().items
        identities = [
            (item.objective, item.underlying, item.instrument_key, item.expiry)
            for item in items
        ]
        assert len(set(identities)) == len(identities)

    def test_plan_is_deterministic(self) -> None:
        assert derivatives_readiness_plan() == derivatives_readiness_plan()

    def test_oi_resample_rule_is_documented_constant(self) -> None:
        assert "LAST_SOURCE_MINUTE" in OI_RESAMPLE_RULE


class TestPlannedItemValidation:
    def test_unauthorized_item_is_refused(self) -> None:
        with pytest.raises(ValueError):
            PlannedAcquisition(
                objective=AcquisitionObjective.BOD_INSTRUMENTS,
                endpoint_class="BOD_INSTRUMENTS",
                underlying=DerivativeUnderlying.NIFTY,
                requires_authorization=False,  # type: ignore[arg-type]
                instrument_key=None,
                expiry=None,
                interval_minutes=None,
                entitlement_class="PUBLIC_EXPORT",
            )

    @pytest.mark.parametrize(
        "objective",
        [
            AcquisitionObjective.EXPIRED_OPTION_CANDLES_1M,
            AcquisitionObjective.UNDERLYING_CANDLES_1M,
        ],
    )
    def test_interval_objectives_require_interval(self, objective: AcquisitionObjective) -> None:
        with pytest.raises(ValueError):
            PlannedAcquisition(
                objective=objective,
                endpoint_class="HISTORY",
                underlying=DerivativeUnderlying.NIFTY,
                instrument_key="NSE_INDEX|NIFTY 50",
                expiry=None,
                interval_minutes=None,
                entitlement_class="AUTHENTICATED_READ",
            )

    def test_contract_objectives_require_expiry(self) -> None:
        with pytest.raises(ValueError):
            PlannedAcquisition(
                objective=AcquisitionObjective.EXPIRED_OPTION_CONTRACTS,
                endpoint_class="EXPIRED_OPTION_CONTRACTS",
                underlying=DerivativeUnderlying.NIFTY,
                instrument_key="NSE_INDEX|NIFTY 50",
                expiry=None,
                interval_minutes=None,
                entitlement_class="AUTHENTICATED_READ",
            )
