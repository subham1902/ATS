"""Deterministic validation and quality classification of market history.

The engine re-verifies every structural guarantee independently of model-level
construction validators, producing sorted, reproducible findings. Findings
induce canonical data-quality states; ``INVALID`` findings make a dataset
unusable for historical replay.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from uuid import UUID

from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.market.calendar.models import _INDIA_STANDARD_TIME, SessionCalendar

from .errors import HistoricalTruthErrorCode
from .models import (
    DEFAULT_VALIDATION_POLICY,
    ContractMetadataPayload,
    HistoryFinding,
    HistoryValidationPolicy,
    HistoryValidationReport,
    InstrumentPolicyOverride,
    MarketBarPayload,
    MarketObservation,
    ObservationKind,
    OptionChainQuotePayload,
    milliseconds_between,
)

_STATE_RANK: dict[DataQualityState, int] = {
    DataQualityState.GOOD: 0,
    DataQualityState.DEGRADED: 1,
    DataQualityState.UNKNOWN: 2,
    DataQualityState.INVALID: 3,
}

_MINIMUM_AVAILABILITY_FIELD = {
    ObservationKind.MARKET_BAR: "bar_minimum_availability_delay_ms",
    ObservationKind.OPTION_CHAIN_QUOTE: "quote_minimum_availability_delay_ms",
    ObservationKind.CONTRACT_METADATA: "metadata_minimum_availability_delay_ms",
    ObservationKind.MARKET_EVENT: "event_minimum_availability_delay_ms",
}

_MAXIMUM_SOURCE_LAG_FIELD = {
    ObservationKind.MARKET_BAR: "bar_maximum_source_lag_ms",
    ObservationKind.OPTION_CHAIN_QUOTE: "quote_maximum_source_lag_ms",
    ObservationKind.CONTRACT_METADATA: "metadata_maximum_source_lag_ms",
    ObservationKind.MARKET_EVENT: "event_maximum_source_lag_ms",
}


def worst_state(left: DataQualityState, right: DataQualityState) -> DataQualityState:
    """Return the more severe of two canonical quality states."""

    return left if _STATE_RANK[left] >= _STATE_RANK[right] else right


def finding_sort_key(finding: HistoryFinding) -> tuple[str, str, str, str]:
    return (
        finding.code.value,
        str(finding.observation_id) if finding.observation_id else "",
        str(finding.related_observation_id) if finding.related_observation_id else "",
        finding.message,
    )


def _matching_override(
    overrides: tuple[InstrumentPolicyOverride, ...], observation: MarketObservation
) -> InstrumentPolicyOverride | None:
    payload = observation.payload
    for override in reversed(overrides):
        if override.instrument != observation.instrument:
            continue
        if override.timeframe is not None:
            if not isinstance(payload, MarketBarPayload):
                continue
            if str(payload.timeframe) != str(override.timeframe):
                continue
        return override
    return None


def _bar_thresholds(
    policy: HistoryValidationPolicy, observation: MarketObservation
) -> tuple[int, int]:
    """Resolve effective (minimum availability, maximum lag) for one record."""

    minimum_field = _MINIMUM_AVAILABILITY_FIELD[observation.kind]
    maximum_field = _MAXIMUM_SOURCE_LAG_FIELD[observation.kind]
    minimum_delay: int = getattr(policy, minimum_field)
    maximum_lag: int = getattr(policy, maximum_field)
    if observation.kind is ObservationKind.MARKET_BAR:
        override = _matching_override(policy.instrument_overrides, observation)
        if override is not None:
            if override.bar_minimum_availability_delay_ms is not None:
                minimum_delay = override.bar_minimum_availability_delay_ms
            if override.bar_maximum_source_lag_ms is not None:
                maximum_lag = override.bar_maximum_source_lag_ms
    return minimum_delay, maximum_lag


def validate_market_history(
    observations: Sequence[MarketObservation],
    *,
    policy: HistoryValidationPolicy | None = None,
) -> HistoryValidationReport:
    """Validate observations deterministically and classify their quality."""

    if not observations:
        raise ValueError("observations must be non-empty")
    active_policy = policy or DEFAULT_VALIDATION_POLICY
    findings: list[HistoryFinding] = []
    findings.extend(_integrity_findings(observations))
    findings.extend(_time_semantics_findings(observations, active_policy))
    findings.extend(_payload_findings(observations))
    findings.extend(_duplicate_identity_findings(observations))
    findings.extend(
        _revision_and_conflict_findings(observations)
    )
    findings.extend(_missing_interval_findings(observations, active_policy))
    findings.extend(_contract_universe_findings(observations, active_policy))
    ordered = tuple(sorted(findings, key=finding_sort_key))
    effective = compute_effective_states(observations, ordered)
    overall = DataQualityState.GOOD
    for state in effective.values():
        overall = worst_state(overall, state)
    return HistoryValidationReport(
        evaluated_count=len(observations),
        findings=ordered,
        overall_quality_state=overall,
    )


def compute_effective_states(
    observations: Sequence[MarketObservation],
    findings: Sequence[HistoryFinding],
) -> dict[str, DataQualityState]:
    """Map observation id to its declared state degraded by induced findings."""

    states = {
        str(observation.observation_id): observation.quality_state
        for observation in observations
    }
    for finding in findings:
        if finding.observation_id is None:
            continue
        key = str(finding.observation_id)
        states[key] = worst_state(states[key], finding.quality_state)
    return states


def _integrity_findings(
    observations: Sequence[MarketObservation],
) -> list[HistoryFinding]:
    findings: list[HistoryFinding] = []
    for observation in observations:
        if compute_payload_hash(observation) != observation.payload_hash:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.PAYLOAD_HASH_MISMATCH,
                    message=f"observation {observation.observation_id} payload hash mismatch",
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                )
            )
    return findings


def _time_semantics_findings(
    observations: Sequence[MarketObservation],
    policy: HistoryValidationPolicy,
) -> list[HistoryFinding]:
    findings: list[HistoryFinding] = []
    for observation in observations:
        times = observation.times
        if not (
            times.event_time
            <= times.source_time
            <= times.ingest_time
            <= times.available_to_strategy_time
        ):
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.BAD_TIME_SEMANTICS,
                    message=(
                        f"observation {observation.observation_id} violates the "
                        "four-clock ordering invariant"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                )
            )
            continue
        lag_ms = milliseconds_between(times.event_time, times.available_to_strategy_time)
        minimum_delay, maximum_lag = _bar_thresholds(policy, observation)
        if lag_ms < minimum_delay:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.UNREALISTIC_SAME_BAR_AVAILABILITY,
                    message=(
                        f"observation {observation.observation_id} became available "
                        f"{lag_ms} ms after event_time, below the required {minimum_delay} ms"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                )
            )
        if lag_ms > maximum_lag:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.STALE_OBSERVATION,
                    message=(
                        f"observation {observation.observation_id} availability lags "
                        f"event_time by {lag_ms} ms beyond the allowed {maximum_lag} ms"
                    ),
                    quality_state=DataQualityState.DEGRADED,
                    observation_id=observation.observation_id,
                )
            )
    return findings


def _payload_findings(
    observations: Sequence[MarketObservation],
) -> list[HistoryFinding]:
    findings: list[HistoryFinding] = []
    for observation in observations:
        payload = observation.payload
        if isinstance(payload, MarketBarPayload):
            if (
                payload.low > payload.open
                or payload.low > payload.close
                or payload.high < payload.open
                or payload.high < payload.close
            ):
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.INVALID_OHLC,
                        message=(
                            f"observation {observation.observation_id} has OHLC "
                            "outside low/high bounds"
                        ),
                        quality_state=DataQualityState.INVALID,
                        observation_id=observation.observation_id,
                    )
                )
        elif isinstance(payload, OptionChainQuotePayload):
            if payload.bid is not None and payload.ask is not None:
                if payload.bid > payload.ask:
                    findings.append(
                        HistoryFinding(
                            code=HistoricalTruthErrorCode.CROSSED_QUOTE,
                            message=(
                                f"observation {observation.observation_id} has bid "
                                f"{payload.bid} above ask {payload.ask}"
                            ),
                            quality_state=DataQualityState.INVALID,
                            observation_id=observation.observation_id,
                        )
                    )
                elif payload.bid == payload.ask:
                    findings.append(
                        HistoryFinding(
                            code=HistoricalTruthErrorCode.LOCKED_QUOTE,
                            message=(
                                f"observation {observation.observation_id} has a "
                                "locked quote (bid equals ask)"
                            ),
                            quality_state=DataQualityState.GOOD,
                            observation_id=observation.observation_id,
                        )
                    )
            expiry_is_past = _expiry_precedes_event(payload.expiry_date, observation)
            if expiry_is_past:
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.INVALID_EXPIRY_RELATIONSHIP,
                        message=(
                            f"observation {observation.observation_id} quotes expiry "
                            f"{payload.expiry_date} before its event date"
                        ),
                        quality_state=DataQualityState.INVALID,
                        observation_id=observation.observation_id,
                    )
                )
        elif isinstance(payload, ContractMetadataPayload):
            if _expiry_precedes_event(payload.expiry_date, observation):
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.INVALID_EXPIRY_RELATIONSHIP,
                        message=(
                            f"observation {observation.observation_id} lists expired "
                            f"contract expiry {payload.expiry_date}"
                        ),
                        quality_state=DataQualityState.INVALID,
                        observation_id=observation.observation_id,
                    )
                )
    return findings


def _expiry_precedes_event(expiry_date: str, observation: MarketObservation) -> bool:
    event_day = observation.times.event_time.date()
    return date.fromisoformat(expiry_date) < event_day


def _duplicate_identity_findings(
    observations: Sequence[MarketObservation],
) -> list[HistoryFinding]:
    first_seen: dict[UUID, MarketObservation] = {}
    duplicates: set[UUID] = set()
    for observation in observations:
        identity = observation.observation_id
        if identity in first_seen:
            duplicates.add(identity)
        else:
            first_seen[identity] = observation
    findings: list[HistoryFinding] = []
    for observation in observations:
        if observation.observation_id in duplicates:
            original = first_seen[observation.observation_id]
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.DUPLICATE_OBSERVATION_IDENTITY,
                    message=(
                        f"observation {observation.observation_id} repeats an "
                        "earlier identical record"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                    related_observation_id=original.observation_id,
                )
            )
    return findings


def _revision_and_conflict_findings(
    observations: Sequence[MarketObservation],
) -> list[HistoryFinding]:
    unique: dict[UUID, MarketObservation] = {}
    for observation in observations:
        unique.setdefault(observation.observation_id, observation)
    records = list(unique.values())
    by_id = {item.observation_id: item for item in records}
    findings: list[HistoryFinding] = []

    for observation in records:
        target_id = observation.supersedes
        if target_id is None:
            continue
        target = by_id.get(target_id)
        if target is None:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.SUPERSEDED_TARGET_MISSING,
                    message=(
                        f"observation {observation.observation_id} supersedes unknown "
                        f"record {target_id}"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                )
            )
            continue
        if (
            target.kind != observation.kind
            or target.instrument != observation.instrument
            or target.times.event_time != observation.times.event_time
        ):
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.REVISION_IDENTITY_MISMATCH,
                    message=(
                        f"observation {observation.observation_id} revises a record "
                        "with a different business identity"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                    related_observation_id=target.observation_id,
                )
            )
        if observation.times.available_to_strategy_time < target.times.available_to_strategy_time:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.REVISION_ORDER_INVALID,
                    message=(
                        f"observation {observation.observation_id} becomes available "
                        "before the record it supersedes"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                    related_observation_id=target.observation_id,
                )
            )

    for observation in records:
        visited: set[UUID] = set()
        current: MarketObservation | None = observation
        while current is not None and current.supersedes is not None:
            if current.observation_id in visited:
                break
            visited.add(current.observation_id)
            nxt = by_id.get(current.supersedes)
            if nxt is None:
                break
            if nxt.observation_id in visited:
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.REVISION_CYCLE,
                        message=(
                            f"observation {observation.observation_id} participates in "
                            "a supersede cycle"
                        ),
                        quality_state=DataQualityState.INVALID,
                        observation_id=observation.observation_id,
                    )
                )
                break
            current = nxt

    groups: dict[tuple[str, str, str], list[MarketObservation]] = {}
    for observation in records:
        key = (
            observation.kind.value,
            observation.instrument,
            observation.times.event_time.isoformat(),
        )
        groups.setdefault(key, []).append(observation)
    for members in groups.values():
        if len(members) == 1:
            continue
        ordered_members = sorted(
            members,
            key=lambda item: (item.times.available_to_strategy_time, item.observation_id),
        )
        head = ordered_members[0]
        chain_valid = head.supersedes is None
        for index in range(1, len(ordered_members)):
            previous = ordered_members[index - 1]
            member = ordered_members[index]
            if member.supersedes != previous.observation_id:
                chain_valid = False
        if not chain_valid:
            for member in ordered_members[1:]:
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.CONFLICTING_OBSERVATION_KEYS,
                        message=(
                            f"observation {member.observation_id} conflicts with "
                            f"{head.observation_id} on an identical business key without "
                            "a valid revision chain"
                        ),
                        quality_state=DataQualityState.INVALID,
                        observation_id=member.observation_id,
                        related_observation_id=head.observation_id,
                    )
                )
    return findings


def _missing_interval_findings(
    observations: Sequence[MarketObservation],
    policy: HistoryValidationPolicy,
) -> list[HistoryFinding]:
    bars: dict[tuple[str, str], list[MarketObservation]] = {}
    for observation in observations:
        if not isinstance(observation.payload, MarketBarPayload):
            continue
        key = (observation.instrument, str(observation.payload.timeframe))
        bars.setdefault(key, []).append(observation)
    findings: list[HistoryFinding] = []
    for (_instrument, _timeframe), group in bars.items():
        ordered_bars = sorted(group, key=lambda item: item.times.event_time)
        for earlier, later in zip(ordered_bars, ordered_bars[1:], strict=False):
            gap_ms = milliseconds_between(
                earlier.times.event_time, later.times.event_time
            )
            interval = policy.expected_bar_interval_ms
            if gap_ms <= 0:
                continue
            if policy.session_calendar is not None:
                missing_close = _calendar_gap_has_missing_close(
                    policy.session_calendar,
                    earlier.times.event_time,
                    later.times.event_time,
                    interval,
                )
            else:
                missing_close = gap_ms % interval != 0 or gap_ms > interval
            if missing_close:
                findings.append(
                    HistoryFinding(
                        code=HistoricalTruthErrorCode.MISSING_INTERVAL,
                        message=(
                            f"bar gap of {gap_ms} ms between "
                            f"{earlier.times.event_time.isoformat()} and "
                            f"{later.times.event_time.isoformat()} for "
                            f"{earlier.instrument}"
                        ),
                        quality_state=DataQualityState.DEGRADED,
                        observation_id=later.observation_id,
                        related_observation_id=earlier.observation_id,
                    )
                )
    return findings


def _calendar_gap_has_missing_close(
    calendar: SessionCalendar,
    earlier: datetime,
    later: datetime,
    interval_ms: int,
) -> bool:
    """Return whether any eligible session close is absent between two bars.

    A close timestamp is eligible when the calendar declares the instant
    PREOPEN or OPEN and it aligns to the anchored interval grid exactly as
    :meth:`SessionCalendar.validate_bar_close` requires. Gaps that span only
    closed or halted time are therefore never flagged.
    """

    step = timedelta(milliseconds=interval_ms)
    candidate = earlier + step
    while candidate < later:
        state = calendar.state_at(candidate)
        if state in (SessionState.PREOPEN, SessionState.OPEN):
            local = candidate.astimezone(_INDIA_STANDARD_TIME)
            if not (local.second or local.microsecond):
                anchor_time = (
                    calendar.preopen_start
                    if state is SessionState.PREOPEN
                    else calendar.market_open
                )
                anchor = datetime.combine(local.date(), anchor_time, tzinfo=local.tzinfo)
                elapsed_seconds = int((local - anchor).total_seconds())
                expected_seconds = interval_ms // 1000
                if elapsed_seconds > 0 and elapsed_seconds % expected_seconds == 0:
                    return True
        candidate += step
    return False


def _contract_universe_findings(
    observations: Sequence[MarketObservation],
    policy: HistoryValidationPolicy,
) -> list[HistoryFinding]:
    if not policy.contract_universe:
        return []
    universe = frozenset(policy.contract_universe)
    derivative_kinds = frozenset(
        {ObservationKind.OPTION_CHAIN_QUOTE, ObservationKind.CONTRACT_METADATA}
    )
    findings: list[HistoryFinding] = []
    for observation in observations:
        if observation.kind not in derivative_kinds:
            continue
        if observation.instrument not in universe:
            findings.append(
                HistoryFinding(
                    code=HistoricalTruthErrorCode.CONTRACT_MISMATCH,
                    message=(
                        f"observation {observation.observation_id} references instrument "
                        f"{observation.instrument} outside the contract universe"
                    ),
                    quality_state=DataQualityState.INVALID,
                    observation_id=observation.observation_id,
                )
            )
    return findings


__all__ = [
    "compute_effective_states",
    "finding_sort_key",
    "validate_market_history",
    "worst_state",
]
