"""Pure CampaignState lifecycle and accounting transitions."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from ats.contracts.common import FiniteDecimal, UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import NonNegativeDecimal
from ats.contracts.governance.models import CampaignState, TradingCampaign
from ats.contracts.governance.types import CampaignStatus
from ats.kernel.types import KernelOutcome, KernelResult

from .errors import CampaignRuntimeError
from .models import CampaignRuntimeConfiguration

_STATE_NAMESPACE = UUID("5872d7ef-1d43-55d7-9697-e248d27c2c16")

_TRANSITIONS: dict[CampaignStatus, frozenset[CampaignStatus]] = {
    CampaignStatus.DRAFT: frozenset((CampaignStatus.VALIDATED, CampaignStatus.REJECTED)),
    CampaignStatus.VALIDATED: frozenset((CampaignStatus.ACTIVE, CampaignStatus.EXPIRED)),
    CampaignStatus.ACTIVE: frozenset(
        (
            CampaignStatus.PAUSED,
            CampaignStatus.COMPLETED,
            CampaignStatus.HALTED,
            CampaignStatus.EXPIRED,
        )
    ),
    CampaignStatus.PAUSED: frozenset(
        (
            CampaignStatus.ACTIVE,
            CampaignStatus.COMPLETED,
            CampaignStatus.HALTED,
            CampaignStatus.EXPIRED,
        )
    ),
    CampaignStatus.REJECTED: frozenset(),
    CampaignStatus.COMPLETED: frozenset(),
    CampaignStatus.HALTED: frozenset(),
    CampaignStatus.EXPIRED: frozenset(),
}


def initialize_campaign_state(
    campaign: TradingCampaign, *, as_of_time: UTCDateTime
) -> CampaignState:
    _validate_campaign(campaign)
    if campaign.status not in (
        CampaignStatus.VALIDATED,
        CampaignStatus.ACTIVE,
        CampaignStatus.PAUSED,
    ):
        raise CampaignRuntimeError("campaign status cannot initialize runtime state")
    return _build(
        campaign=campaign,
        state_version=1,
        status=campaign.status,
        trades_started=0,
        trades_completed=0,
        open_positions=0,
        capital_committed=Decimal(0),
        realized_pnl=Decimal(0),
        unrealized_pnl=Decimal(0),
        maximum_drawdown_observed=Decimal(0),
        consecutive_losses=0,
        last_trade_at=None,
        cooldown_until=None,
        stop_reason_codes=(),
        as_of_time=as_of_time,
    )


def transition_campaign(
    campaign: TradingCampaign,
    state: CampaignState,
    *,
    target: CampaignStatus,
    occurred_at: UTCDateTime,
    reason_codes: tuple[str, ...] = (),
) -> CampaignState:
    _validate_binding(campaign, state, occurred_at)
    if target not in _TRANSITIONS[state.status]:
        raise CampaignRuntimeError("campaign transition is not registered")
    if target is CampaignStatus.HALTED and not reason_codes:
        raise CampaignRuntimeError("HALTED transition requires reason codes")
    return _copy(
        campaign,
        state,
        occurred_at=occurred_at,
        status=target,
        stop_reason_codes=reason_codes if target is CampaignStatus.HALTED else (),
    )


def record_trade_started(
    campaign: TradingCampaign,
    state: CampaignState,
    *,
    authorization: KernelResult,
    committed_capital: NonNegativeDecimal,
    occurred_at: UTCDateTime,
) -> CampaignState:
    _validate_binding(campaign, state, occurred_at)
    if authorization.outcome is not KernelOutcome.ALLOW:
        raise CampaignRuntimeError("A04 ALLOW is required to start a trade")
    if state.status is not CampaignStatus.ACTIVE:
        raise CampaignRuntimeError("campaign is not ACTIVE")
    if not campaign.start_at <= occurred_at < campaign.expires_at:
        raise CampaignRuntimeError("trade time is outside campaign window")
    if state.cooldown_until is not None and occurred_at < state.cooldown_until:
        raise CampaignRuntimeError("campaign cooldown is active")
    if state.trades_started >= campaign.max_trades:
        raise CampaignRuntimeError("maximum trade ceiling reached")
    if state.open_positions >= campaign.max_concurrent_positions:
        raise CampaignRuntimeError("maximum concurrent positions reached")
    if state.capital_committed + committed_capital > campaign.capital_budget:
        raise CampaignRuntimeError("campaign capital budget exceeded")
    return _copy(
        campaign,
        state,
        occurred_at=occurred_at,
        trades_started=state.trades_started + 1,
        open_positions=state.open_positions + 1,
        capital_committed=state.capital_committed + committed_capital,
        last_trade_at=occurred_at,
    )


def record_trade_completed(
    campaign: TradingCampaign,
    state: CampaignState,
    *,
    released_capital: NonNegativeDecimal,
    realized_trade_pnl: FiniteDecimal,
    occurred_at: UTCDateTime,
    configuration: CampaignRuntimeConfiguration,
) -> CampaignState:
    _validate_binding(campaign, state, occurred_at)
    if state.open_positions <= 0:
        raise CampaignRuntimeError("campaign has no open position to complete")
    if released_capital > state.capital_committed:
        raise CampaignRuntimeError("released capital exceeds campaign commitment")
    losses = state.consecutive_losses + 1 if realized_trade_pnl < 0 else 0
    cooldown = state.cooldown_until
    if losses >= campaign.cooldown_rule.after_consecutive_losses:
        cooldown = occurred_at + timedelta(
            milliseconds=campaign.cooldown_rule.duration_bars * configuration.bar_duration_ms
        )
    return _copy(
        campaign,
        state,
        occurred_at=occurred_at,
        trades_completed=state.trades_completed + 1,
        open_positions=state.open_positions - 1,
        capital_committed=state.capital_committed - released_capital,
        realized_pnl=state.realized_pnl + realized_trade_pnl,
        consecutive_losses=losses,
        last_trade_at=occurred_at,
        cooldown_until=cooldown,
    )


def mark_campaign_to_market(
    campaign: TradingCampaign,
    state: CampaignState,
    *,
    unrealized_pnl: FiniteDecimal,
    drawdown: Decimal,
    occurred_at: UTCDateTime,
) -> CampaignState:
    _validate_binding(campaign, state, occurred_at)
    if drawdown < 0 or drawdown > 1:
        raise CampaignRuntimeError("drawdown must be in [0,1]")
    return _copy(
        campaign,
        state,
        occurred_at=occurred_at,
        unrealized_pnl=unrealized_pnl,
        maximum_drawdown_observed=max(state.maximum_drawdown_observed, drawdown),
    )


def _validate_campaign(campaign: TradingCampaign) -> None:
    if compute_payload_hash(campaign) != campaign.payload_hash:
        raise CampaignRuntimeError("campaign payload hash mismatch")


def _validate_binding(
    campaign: TradingCampaign, state: CampaignState, occurred_at: UTCDateTime
) -> None:
    _validate_campaign(campaign)
    if compute_payload_hash(state) != state.payload_hash:
        raise CampaignRuntimeError("campaign state payload hash mismatch")
    if (
        state.campaign_id != campaign.campaign_id
        or state.campaign_version != campaign.campaign_version
    ):
        raise CampaignRuntimeError("campaign state binding mismatch")
    if occurred_at < state.as_of_time:
        raise CampaignRuntimeError("campaign state time moved backwards")


def _copy(
    campaign: TradingCampaign,
    state: CampaignState,
    *,
    occurred_at: UTCDateTime,
    **updates: object,
) -> CampaignState:
    values = state.model_dump(mode="python")
    values.update(updates)
    values["state_version"] = state.state_version + 1
    values["as_of_time"] = occurred_at
    values["payload_hash"] = "0" * 64
    return _rehash(CampaignState.model_validate(values))


def _build(*, campaign: TradingCampaign, **values: object) -> CampaignState:
    state_values = {
        "schema_version": "1.0",
        "campaign_state_id": uuid5(
            _STATE_NAMESPACE, f"{campaign.campaign_id}:{campaign.campaign_version}"
        ),
        "campaign_id": campaign.campaign_id,
        "campaign_version": campaign.campaign_version,
        "payload_hash": "0" * 64,
        **values,
    }
    state = CampaignState.model_validate(state_values)
    return _rehash(state)


def _rehash(state: CampaignState) -> CampaignState:
    return state.model_copy(update={"payload_hash": compute_payload_hash(state)})


def registered_campaign_transitions() -> dict[CampaignStatus, frozenset[CampaignStatus]]:
    return dict(_TRANSITIONS)


__all__ = [
    "initialize_campaign_state",
    "mark_campaign_to_market",
    "record_trade_completed",
    "record_trade_started",
    "registered_campaign_transitions",
    "transition_campaign",
]
