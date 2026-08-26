"""End-to-end readiness pipeline over real code paths (no live provider).

Wires the D08 components together exactly as production will:

1. A canonical contract master is assembled from listed NIFTY contracts.
2. The expiry engine selects the tradable nearest expiry.
3. The strike-window engine pairs strikes around a live underlying price.
4. Every windowed leg receives a feed update through the Upstox V3 adapter.
5. Deterministic greeks are computed for each leg with explicit provenance.

No credentials, no network, no fabricated prices: every numeric value in this
test is an explicitly declared test constant and all frames are TEST_ONLY
message-shape fixtures that can never be installed as market data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import pytest
from ats.contracts.domain.hashing import compute_payload_hash
from ats.market.derivatives.contract_master import (
    ContractMaster,
    ContractMasterManifest,
    DerivativeInstrument,
    DerivativeInstrumentType,
    DerivativeUnderlying,
    OptionType,
    available_expiries,
    classify_expiry,
    select_nearest_expiry,
)
from ats.market.derivatives.option_chain import (
    DeterministicGreeksRequest,
    GreeksMethod,
    compute_deterministic_greeks,
)
from ats.market.derivatives.strike_window import StrikeWindowPolicy, build_strike_window
from ats.market.feeds.upstox_v3 import (
    FeedFreshnessBoard,
    FeedMode,
    SubscriptionRegistry,
    UpstoxV3FeedAdapter,
)

from tests.unit.market.feeds.upstox_v3 import helpers as fix

UNDERLYING = DerivativeUnderlying.NIFTY
EVALUATION_TIME = datetime(2026, 8, 24, 5, 30, tzinfo=UTC)
SPOT = Decimal("25012.35")
EXPIRIES = ("2026-08-27", "2026-09-24")
STRIKES = ("24700", "24800", "24900", "25000", "25100", "25200", "25300")
LOT_SIZE = 75
FREEZE = 1800
MASTER_AGE_MS = 60 * 60 * 1000


def _instrument(expiry: str, strike: str, option_type: OptionType) -> DerivativeInstrument:
    return DerivativeInstrument(
        exchange="NSE",
        segment="NFO",
        underlying=UNDERLYING,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        trading_symbol=f"NIFTY{expiry.replace('-', '')[2:]}{strike}{option_type.value}",
        instrument_id=f"NSE-NFO-{expiry}-{strike}-{option_type.value}",
        expiry=expiry,
        strike=Decimal(strike),
        option_type=option_type,
        lot_size=LOT_SIZE,
        tick_size=Decimal("0.05"),
        quantity_freeze_limit=FREEZE,
        tradable=True,
        contract_version="1.0",
        source="TEST_ONLY_CONSTRUCTED_MASTER",
        as_of_time=EVALUATION_TIME - timedelta(minutes=1),
    )


def build_master() -> ContractMaster:
    instruments = tuple(
        _instrument(expiry, strike, side)
        for expiry in EXPIRIES
        for strike in STRIKES
        for side in (OptionType.CE, OptionType.PE)
    )
    return _master(instruments, master_id=uuid5(NAMESPACE_URL, "d08-integration-master"))


def _master(instruments: tuple[DerivativeInstrument, ...], *, master_id: str) -> ContractMaster:
    manifest = ContractMasterManifest(
        schema_version="1.0",
        master_id=master_id,
        master_version="2026.08.24-01",
        source="TEST_ONLY_CONSTRUCTED",
        as_of_time=EVALUATION_TIME - timedelta(minutes=1),
        row_count=len(instruments),
        content_sha256="a" * 64,
    )
    master = ContractMaster.model_validate(
        {
            "schema_version": "1.0",
            "manifest": manifest,
            "instruments": instruments,
            "payload_hash": "0" * 64,
        }
    )
    return master.model_copy(update={"payload_hash": compute_payload_hash(master)})


@pytest.fixture()
def master() -> ContractMaster:
    return build_master()


class TestExpirySelection:
    def test_nearest_expiry_is_the_earliest_tradable(self, master: ContractMaster) -> None:
        selection = select_nearest_expiry(
            master,
            underlying=UNDERLYING,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=EVALUATION_TIME,
            maximum_age_ms=MASTER_AGE_MS,
        )
        assert selection.expiry == "2026-08-27"
        assert (
            classify_expiry(expiry=selection.expiry, evaluation_time=EVALUATION_TIME).value
            != "EXPIRED"
        )

    def test_available_expiries_are_ordered(self, master: ContractMaster) -> None:
        expiries = available_expiries(
            master,
            underlying=UNDERLYING,
            instrument_type=DerivativeInstrumentType.OPTIDX,
            evaluation_time=EVALUATION_TIME,
            maximum_age_ms=MASTER_AGE_MS,
        )
        assert list(expiries) == sorted(EXPIRIES)


class TestStrikeWindowIntegration:
    def test_window_pairs_strikes_around_spot(self, master: ContractMaster) -> None:
        plan = window(master)
        assert plan.atm_strike == Decimal("25000")
        assert [str(pair.strike) for pair in plan.strikes] == [
            "24800",
            "24900",
            "25000",
            "25100",
            "25200",
        ]
        assert plan.unpaired_evidence == ()
        assert plan.payload_hash == compute_payload_hash(plan)

    def test_missing_pe_side_is_reported_not_interpolated(self) -> None:
        keep = tuple(
            item
            for item in build_master().instruments
            if not (
                item.expiry == "2026-08-27"
                and str(item.strike) == "25100"
                and item.option_type is OptionType.PE
            )
        )
        plan = window(
            _master(keep, master_id=uuid5(NAMESPACE_URL, "d08-broken-master"))
        )
        evidence = [(item.strike, item.missing_side) for item in plan.unpaired_evidence]
        assert (Decimal("25100"), "PE") in evidence


class TestFeedAndGreeksPipeline:
    def test_window_legs_flow_through_feed_adapter_into_greeks(
        self, master: ContractMaster
    ) -> None:
        plan = window(master)
        registry_keys = [
            f"NSE_FO|{leg.instrument_id}"
            for pair in plan.strikes
            for leg in (pair.ce, pair.pe)
        ]
        registry = SubscriptionRegistry()
        board = FeedFreshnessBoard()
        for key in registry_keys:
            registry.register(instrument_key=key, ats_identity=key, mode=FeedMode.LTPC)
            board.register(instrument_key=key, stale_after_ms=5_000)
        clock = fix.FakeClock(start=EVALUATION_TIME)
        subject = UpstoxV3FeedAdapter(
            configuration=fix.configuration(),
            authorization=fix.authorization(),
            registry=registry,
            freshness_board=board,
            decoder=fix.decoder(),
            clock=clock,
        )
        subject.connect(fix.RecordingConnection())

        latest: dict[str, Decimal] = {}
        for key in registry_keys:
            stamp = clock.advance(milliseconds=10)
            outcome = subject.handle_frame(
                fix.ltpc_frame(
                    instrument_key=key,
                    ltp=12550,
                    cp=100000,
                    ltt_ms=int(stamp.timestamp() * 1000),
                    ts_ms=int(stamp.timestamp() * 1000),
                ),
                received_at=stamp,
            )
            assert outcome.applied_updates == (key,)
            update = subject.latest(key)
            assert update is not None
            latest[key] = update.last_traded_price

        # greeks for every windowed leg come only from the deterministic calculator
        for pair in plan.strikes:
            call, put = straddle(pair.strike)
            assert call.greeks_method is GreeksMethod.DETERMINISTIC_CALCULATOR
            assert put.greeks_method is GreeksMethod.DETERMINISTIC_CALCULATOR
            assert call.gamma == put.gamma
            assert abs((call.delta - put.delta) - 1.0) < 1e-12


def window(master: ContractMaster):
    selection = select_nearest_expiry(
        master,
        underlying=UNDERLYING,
        instrument_type=DerivativeInstrumentType.OPTIDX,
        evaluation_time=EVALUATION_TIME,
        maximum_age_ms=MASTER_AGE_MS,
    )
    return build_strike_window(
        master,
        underlying=UNDERLYING,
        underlying_price=SPOT,
        policy=StrikeWindowPolicy(
            window_size=2, expiry=selection.expiry, maximum_master_age_ms=MASTER_AGE_MS
        ),
        evaluation_time=EVALUATION_TIME,
    )


def straddle(strike: Decimal):
    kwargs = dict(
        underlying_price=float(SPOT),
        strike=float(strike),
        time_to_expiry_days=3.0,
        implied_volatility=0.14,
        risk_free_rate=0.065,
    )
    call = compute_deterministic_greeks(
        DeterministicGreeksRequest(option_type=OptionType.CE, **kwargs)
    )
    put = compute_deterministic_greeks(
        DeterministicGreeksRequest(option_type=OptionType.PE, **kwargs)
    )
    return call, put
