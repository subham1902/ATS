"""Deterministic long CE/PE selection from normalized option-chain evidence."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.intelligence.models import CalibratedOutcomeDistribution, MarketThesis
from ats.contracts.intelligence.types import MarketThesisStatus, ThesisStance
from ats.market.derivatives.contract_master import (
    ContractMaster,
    DerivativeInstrument,
    DerivativeInstrumentType,
    OptionType,
)
from ats.market.derivatives.option_chain import OptionChainState, OptionQuote

from .errors import InstrumentSelectionError
from .models import (
    InstrumentCandidate,
    InstrumentRejection,
    InstrumentSelectionConfiguration,
    InstrumentSelectionResult,
    InstrumentSelectionStatus,
)

_CANDIDATE_NAMESPACE = UUID("38fa0203-480c-5fb8-a4d8-66fe11037c76")


def select_derivative_instruments(
    *,
    contract_master: ContractMaster,
    option_chain: OptionChainState,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    evaluation_time: UTCDateTime,
    configuration: InstrumentSelectionConfiguration,
    expected_option_payoff_per_unit: Decimal | None = None,
) -> InstrumentSelectionResult:
    """Rank one-lot long options and suppress equivalent thesis expressions."""

    _validate_inputs(
        contract_master=contract_master,
        option_chain=option_chain,
        thesis=thesis,
        distribution=distribution,
        evaluation_time=evaluation_time,
        configuration=configuration,
    )
    option_type = _option_type(thesis, distribution)
    if option_type is None:
        return _empty("THESIS_NOT_DIRECTIONALLY_ACTIONABLE")
    if configuration.require_observed_option_payoff and expected_option_payoff_per_unit is None:
        return _empty("ECONOMIC_PAYOFF_EVIDENCE_UNAVAILABLE")

    instruments = {
        item.instrument_id: item
        for item in contract_master.instruments
        if item.instrument_type is DerivativeInstrumentType.OPTIDX
        and item.underlying is option_chain.underlying
        and item.expiry == option_chain.expiry
        and item.option_type is option_type
    }
    candidates: list[InstrumentCandidate] = []
    rejections: list[InstrumentRejection] = []
    for quote in option_chain.quotes:
        if quote.option_type is not option_type:
            continue
        instrument = instruments.get(quote.instrument_id)
        if instrument is None:
            rejections.append(_rejection(quote.instrument_id, "CONTRACT_NOT_IN_MASTER"))
            continue
        reasons = _quote_reasons(
            quote,
            instrument=instrument,
            evaluation_time=evaluation_time,
            configuration=configuration,
        )
        if reasons:
            rejections.append(
                InstrumentRejection(instrument_id=quote.instrument_id, reason_codes=reasons)
            )
            continue
        candidate = _candidate(
            instrument=instrument,
            quote=quote,
            chain=option_chain,
            thesis=thesis,
            distribution=distribution,
            configuration=configuration,
            expected_option_payoff_per_unit=expected_option_payoff_per_unit,
        )
        if candidate.premium_required > configuration.maximum_premium_per_candidate:
            rejections.append(_rejection(quote.instrument_id, "PREMIUM_BUDGET_EXCEEDED"))
        elif candidate.expected_net_pnl <= 0:
            rejections.append(_rejection(quote.instrument_id, "EXPECTED_NET_PNL_NON_POSITIVE"))
        else:
            candidates.append(candidate)

    # One expression per underlying/expiry/direction prevents adjacent strikes from
    # consuming independent risk slots before portfolio-level correlation checks.
    selected = tuple(
        sorted(candidates, key=lambda item: (-item.expected_net_pnl, item.instrument_id))[:1]
    )
    if not selected:
        return InstrumentSelectionResult(
            status=InstrumentSelectionStatus.NO_ELIGIBLE_INSTRUMENT,
            candidates=(),
            rejections=tuple(sorted(rejections, key=lambda item: item.instrument_id)),
            reason_codes=("NO_ELIGIBLE_LONG_OPTION",),
        )
    suppressed_ids = {item.instrument_candidate_id for item in selected}
    for item in candidates:
        if item.instrument_candidate_id not in suppressed_ids:
            rejections.append(_rejection(item.instrument_id, "ECONOMIC_DUPLICATE_SUPPRESSED"))
    return InstrumentSelectionResult(
        status=InstrumentSelectionStatus.CANDIDATES_AVAILABLE,
        candidates=selected,
        rejections=tuple(sorted(rejections, key=lambda item: item.instrument_id)),
        reason_codes=("LONG_OPTION_CANDIDATE_SELECTED",),
    )


def _validate_inputs(
    *,
    contract_master: ContractMaster,
    option_chain: OptionChainState,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    evaluation_time: datetime,
    configuration: InstrumentSelectionConfiguration,
) -> None:
    for name, value in (
        ("contract master", contract_master),
        ("option chain", option_chain),
        ("thesis", thesis),
        ("distribution", distribution),
    ):
        if compute_payload_hash(value) != value.payload_hash:
            raise InstrumentSelectionError(f"{name} payload hash mismatch")
    if thesis.status is not MarketThesisStatus.ACTIVE or thesis.expires_at <= evaluation_time:
        raise InstrumentSelectionError("market thesis is not current and ACTIVE")
    if distribution.valid_until <= evaluation_time:
        raise InstrumentSelectionError("calibrated distribution is expired")
    if thesis.distribution_id != distribution.distribution_id:
        raise InstrumentSelectionError("thesis/distribution lineage mismatch")
    if thesis.instrument_id != option_chain.underlying:
        raise InstrumentSelectionError("thesis underlying mismatch")
    if option_chain.as_of_time != thesis.as_of_time or option_chain.data_cutoff > thesis.as_of_time:
        raise InstrumentSelectionError("option chain/thesis time mismatch")
    if option_chain.quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED):
        raise InstrumentSelectionError("option chain quality is unacceptable")
    if (
        _age_ms(contract_master.manifest.as_of_time, evaluation_time)
        > configuration.maximum_master_age_ms
    ):
        raise InstrumentSelectionError("contract master is stale")
    if _age_ms(option_chain.data_cutoff, evaluation_time) > configuration.maximum_chain_age_ms:
        raise InstrumentSelectionError("option chain is stale")
    if (
        contract_master.manifest.as_of_time > evaluation_time
        or option_chain.data_cutoff > evaluation_time
    ):
        raise InstrumentSelectionError("future evidence supplied")


def _option_type(
    thesis: MarketThesis, distribution: CalibratedOutcomeDistribution
) -> OptionType | None:
    expected = Decimal(str(distribution.expected_return_fraction))
    if thesis.stance is ThesisStance.BULLISH and expected > 0:
        return OptionType.CE
    if thesis.stance is ThesisStance.BEARISH and expected < 0:
        return OptionType.PE
    return None


def _quote_reasons(
    quote: OptionQuote,
    *,
    instrument: DerivativeInstrument,
    evaluation_time: datetime,
    configuration: InstrumentSelectionConfiguration,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not instrument.tradable:
        reasons.append("CONTRACT_NOT_TRADABLE")
    if quote.quality_state not in (DataQualityState.GOOD, DataQualityState.DEGRADED):
        reasons.append("QUOTE_QUALITY_UNACCEPTABLE")
    if quote.bid is None or quote.bid <= 0:
        reasons.append("ZERO_OR_MISSING_BID")
    if quote.ask is None or quote.ask <= 0:
        reasons.append("ZERO_OR_MISSING_ASK")
    if quote.spread is None or quote.spread_fraction is None:
        reasons.append("SPREAD_UNAVAILABLE")
    elif quote.spread_fraction > configuration.maximum_spread_fraction:
        reasons.append("SPREAD_TOO_WIDE")
    if quote.ask_qty is None or quote.ask_qty < max(
        configuration.minimum_top_quantity, instrument.lot_size
    ):
        reasons.append("INSUFFICIENT_ASK_DEPTH")
    if quote.volume is None or quote.volume < configuration.minimum_volume:
        reasons.append("INSUFFICIENT_VOLUME")
    if quote.open_interest is None or quote.open_interest < configuration.minimum_open_interest:
        reasons.append("INSUFFICIENT_OPEN_INTEREST")
    if quote.implied_volatility is None:
        reasons.append("IMPLIED_VOLATILITY_UNAVAILABLE")
    if quote.delta is None or quote.theta is None:
        reasons.append("REQUIRED_GREEKS_UNAVAILABLE")
    if _age_ms(quote.quote_time, evaluation_time) > configuration.maximum_quote_age_ms:
        reasons.append("QUOTE_STALE")
    if quote.quote_time > evaluation_time:
        reasons.append("QUOTE_FROM_FUTURE")
    if Decimal(str(quote.time_to_expiry)) <= 0:
        reasons.append("CONTRACT_EXPIRED")
    return tuple(reasons)


def _candidate(
    *,
    instrument: DerivativeInstrument,
    quote: OptionQuote,
    chain: OptionChainState,
    thesis: MarketThesis,
    distribution: CalibratedOutcomeDistribution,
    configuration: InstrumentSelectionConfiguration,
    expected_option_payoff_per_unit: Decimal | None,
) -> InstrumentCandidate:
    assert instrument.strike is not None and instrument.option_type is not None
    assert quote.ask is not None and quote.spread is not None
    assert quote.delta is not None and quote.theta is not None
    assert quote.implied_volatility is not None
    quantity = instrument.lot_size
    quantity_decimal = Decimal(quantity)
    premium = quote.ask * quantity_decimal
    if expected_option_payoff_per_unit is None:
        # Replay/research compatibility only. Production live-paper configuration
        # requires an explicitly observed option-payoff estimate and never reaches
        # this delta proxy.
        expected_move = abs(
            chain.underlying_price * Decimal(str(distribution.expected_return_fraction))
        )
        gross = expected_move * Decimal(str(abs(quote.delta))) * quantity_decimal
    else:
        gross = expected_option_payoff_per_unit * quantity_decimal
    spread = quote.spread * quantity_decimal
    slippage = premium * configuration.slippage_fraction
    transaction = premium * configuration.transaction_cost_fraction
    theta_days = Decimal(distribution.horizon_bars * configuration.bar_duration_minutes) / Decimal(
        24 * 60
    )
    theta = Decimal(str(abs(quote.theta))) * theta_days * quantity_decimal
    iv_penalty = premium * Decimal(str(quote.implied_volatility)) * configuration.iv_penalty_factor
    liquidity = (
        premium * configuration.degraded_liquidity_penalty_fraction
        if quote.quality_state is DataQualityState.DEGRADED
        else Decimal(0)
    )
    time_to_expiry_hours = Decimal(str(quote.time_to_expiry)) / Decimal(3600)
    expiry = (
        premium * configuration.near_expiry_penalty_fraction
        if time_to_expiry_hours <= configuration.near_expiry_threshold_hours
        else Decimal(0)
    )
    net = gross - spread - slippage - transaction - theta - iv_penalty - liquidity - expiry
    identity = ":".join(
        (
            str(thesis.thesis_id),
            str(distribution.distribution_id),
            str(chain.chain_id),
            instrument.instrument_id,
            configuration.selector_version,
        )
    )
    value = InstrumentCandidate(
        schema_version="1.0",
        instrument_candidate_id=uuid5(_CANDIDATE_NAMESPACE, identity),
        instrument_id=instrument.instrument_id,
        trading_symbol=instrument.trading_symbol,
        underlying=instrument.underlying,
        option_type=instrument.option_type,
        expiry=instrument.expiry,
        strike=instrument.strike,
        thesis_id=thesis.thesis_id,
        thesis_version=thesis.thesis_version,
        distribution_id=distribution.distribution_id,
        option_chain_id=chain.chain_id,
        lot_size=instrument.lot_size,
        lot_count=1,
        quantity=quantity,
        entry_ask=quote.ask,
        premium_required=premium,
        expected_gross_pnl=gross,
        estimated_spread_cost=spread,
        estimated_slippage=slippage,
        estimated_transaction_cost=transaction,
        estimated_theta_cost=theta,
        estimated_iv_penalty=iv_penalty,
        estimated_liquidity_penalty=liquidity,
        estimated_expiry_penalty=expiry,
        expected_net_pnl=net,
        as_of_time=thesis.as_of_time,
        data_cutoff=max(thesis.data_cutoff, chain.data_cutoff),
        method_version=configuration.selector_version,
        payload_hash="0" * 64,
    )
    return value.model_copy(update={"payload_hash": compute_payload_hash(value)})


def _age_ms(earlier: datetime, later: datetime) -> int:
    return int((later - earlier).total_seconds() * 1000)


def _rejection(instrument_id: str, reason: str) -> InstrumentRejection:
    return InstrumentRejection(instrument_id=instrument_id, reason_codes=(reason,))


def _empty(reason: str) -> InstrumentSelectionResult:
    return InstrumentSelectionResult(
        status=InstrumentSelectionStatus.NO_ELIGIBLE_INSTRUMENT,
        candidates=(),
        rejections=(),
        reason_codes=(reason,),
    )


__all__ = ["select_derivative_instruments"]
