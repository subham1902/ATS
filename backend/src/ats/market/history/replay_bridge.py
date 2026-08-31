"""History-truth bridge over the existing B01 deterministic replay.

The bridge converts approved replay bars into canonical historical
observations with explicit availability times, then gates their visibility by
the AS_OF_INFORMATION_MODEL while the underlying :class:`DeterministicReplay`
keeps its own cursor semantics untouched. Determinism of B01 is preserved:
this module only reads its public surface and never mutates it. Derivative
and event records may be attached as gated sidecar observations so option,
contract-master and news information obey the same admission rule as bars,
and every advance records an attribution digest of exactly what was visible.
"""

from __future__ import annotations

from datetime import timedelta

from ats.contracts.common import (
    ATSBaseModel,
    ClockProtocol,
    FiniteDecimal,
    SchemaVersion,
    UTCDateTime,
)
from ats.contracts.domain.models import MarketSnapshot
from ats.contracts.domain.types import (
    DataQualityState,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveDecimal,
    PositiveInt,
    QualityFlag,
    Sha256,
)
from ats.contracts.hashing import canonical_sha256
from ats.market.replay.engine import DeterministicReplay
from ats.market.replay.models import ReplayBar, ReplayConfiguration, ReplayDataset, ReplayState

from .as_of import AsOfTimeline
from .builder import build_market_observation
from .errors import HistoricalTruthError, HistoricalTruthErrorCode
from .models import (
    ContractMetadataPayload,
    HistoricalEventClass,
    HistoricalOptionType,
    MarketBarPayload,
    MarketEventPayload,
    MarketObservation,
    ObservationKind,
    ObservationTimes,
    OptionChainQuotePayload,
    RawRecordReference,
)


class HistoryTimeSemantics(ATSBaseModel):
    """Deterministic delays separating the four clocks in replay bridges."""

    source_publication_delay_ms: NonNegativeInt = 0
    ingestion_delay_ms: NonNegativeInt = 0
    strategy_visibility_delay_ms: NonNegativeInt = 0


DEFAULT_HISTORY_TIME_SEMANTICS = HistoryTimeSemantics(
    source_publication_delay_ms=100,
    ingestion_delay_ms=100,
    strategy_visibility_delay_ms=50,
)


class AttributionRecord(ATSBaseModel):
    """One decision instant bound to an immutable visible-window digest.

    ``window_sha256`` covers the sorted observation identities legitimately
    observable when the replay clock stood at ``decision_time``, giving every
    later PnL event a tamper-evident link back to exactly the information set
    behind the decision.
    """

    schema_version: SchemaVersion = "1.0"
    decision_time: UTCDateTime
    sequence: PositiveInt
    visible_count: NonNegativeInt
    window_sha256: Sha256


def historical_bar_observations(
    dataset: ReplayDataset,
    *,
    semantics: HistoryTimeSemantics | None = None,
) -> tuple[MarketObservation, ...]:
    """Convert replay bars into canonical observations with availability times."""

    active_semantics = semantics or DEFAULT_HISTORY_TIME_SEMANTICS
    manifest = dataset.manifest
    observations: list[MarketObservation] = []
    for bar in dataset.bars:
        event_time = bar.bar_timestamp
        source_time = event_time + timedelta(
            milliseconds=active_semantics.source_publication_delay_ms
        )
        ingest_time = source_time + timedelta(milliseconds=active_semantics.ingestion_delay_ms)
        available_to_strategy_time = ingest_time + timedelta(
            milliseconds=active_semantics.strategy_visibility_delay_ms
        )
        observations.append(
            build_market_observation(
                instrument=bar.instrument_id,
                times=ObservationTimes(
                    event_time=event_time,
                    source_time=source_time,
                    ingest_time=ingest_time,
                    available_to_strategy_time=available_to_strategy_time,
                ),
                payload=MarketBarPayload(
                    payload_kind=ObservationKind.MARKET_BAR,
                    timeframe=bar.timeframe,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                ),
                provenance=RawRecordReference(
                    source_id=manifest.source_description,
                    raw_record_sha256=_raw_bar_digest(bar),
                    raw_location=f"{manifest.dataset_id}:{bar.source_sequence}",
                ),
                quality_state=bar.quality_state,
                quality_flags=bar.quality_flags,
            )
        )
    return tuple(observations)


def _times_from_lags(
    event_time: UTCDateTime,
    *,
    semantics: HistoryTimeSemantics,
) -> ObservationTimes:
    source_time = event_time + timedelta(milliseconds=semantics.source_publication_delay_ms)
    ingest_time = source_time + timedelta(milliseconds=semantics.ingestion_delay_ms)
    return ObservationTimes(
        event_time=event_time,
        source_time=source_time,
        ingest_time=ingest_time,
        available_to_strategy_time=ingest_time
        + timedelta(milliseconds=semantics.strategy_visibility_delay_ms),
    )


def historical_option_quote_observation(
    *,
    instrument: str,
    event_time: UTCDateTime,
    underlying: str,
    trading_symbol: str,
    expiry_date: str,
    strike: PositiveDecimal,
    option_type: str | HistoricalOptionType,
    bid: FiniteDecimal | None = None,
    ask: FiniteDecimal | None = None,
    last_trade_price: FiniteDecimal | None = None,
    volume: NonNegativeDecimal | None = None,
    open_interest: NonNegativeDecimal | None = None,
    provenance: RawRecordReference,
    semantics: HistoryTimeSemantics | None = None,
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[QualityFlag, ...] = (),
) -> MarketObservation:
    """Build one gated option-chain quote observation."""

    active_semantics = semantics or DEFAULT_HISTORY_TIME_SEMANTICS
    return build_market_observation(
        instrument=instrument,
        times=_times_from_lags(event_time, semantics=active_semantics),
        payload=OptionChainQuotePayload(
            payload_kind=ObservationKind.OPTION_CHAIN_QUOTE,
            underlying=underlying,
            trading_symbol=trading_symbol,
            expiry_date=expiry_date,
            strike=strike,
            option_type=_option_type(option_type),
            bid=bid,
            ask=ask,
            last_trade_price=last_trade_price,
            volume=volume,
            open_interest=open_interest,
        ),
        provenance=provenance,
        quality_state=quality_state,
        quality_flags=quality_flags,
    )


def historical_contract_metadata_observation(
    *,
    instrument: str,
    event_time: UTCDateTime,
    contract_master_id: str,
    trading_symbol: str,
    underlying: str,
    instrument_type: str,
    expiry_date: str,
    strike: PositiveDecimal | None = None,
    option_type: str | HistoricalOptionType | None = None,
    lot_size: PositiveInt | None = None,
    provenance: RawRecordReference,
    semantics: HistoryTimeSemantics | None = None,
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[QualityFlag, ...] = (),
) -> MarketObservation:
    """Build one gated contract-master row observation."""

    active_semantics = semantics or DEFAULT_HISTORY_TIME_SEMANTICS
    return build_market_observation(
        instrument=instrument,
        times=_times_from_lags(event_time, semantics=active_semantics),
        payload=ContractMetadataPayload(
            payload_kind=ObservationKind.CONTRACT_METADATA,
            contract_master_id=contract_master_id,
            trading_symbol=trading_symbol,
            underlying=underlying,
            instrument_type=instrument_type,
            expiry_date=expiry_date,
            strike=strike,
            option_type=_option_type(option_type) if option_type is not None else None,
            lot_size=lot_size,
        ),
        provenance=provenance,
        quality_state=quality_state,
        quality_flags=quality_flags,
    )


def historical_event_observation(
    *,
    instrument: str,
    event_time: UTCDateTime,
    event_class: str | HistoricalEventClass,
    headline: str,
    summary: str | None = None,
    provenance: RawRecordReference,
    semantics: HistoryTimeSemantics | None = None,
    quality_state: DataQualityState = DataQualityState.GOOD,
    quality_flags: tuple[QualityFlag, ...] = (),
) -> MarketObservation:
    """Build one gated news / corporate-action observation."""

    active_semantics = semantics or DEFAULT_HISTORY_TIME_SEMANTICS
    return build_market_observation(
        instrument=instrument,
        times=_times_from_lags(event_time, semantics=active_semantics),
        payload=MarketEventPayload(
            payload_kind=ObservationKind.MARKET_EVENT,
            event_class=_event_class(event_class),
            headline=headline,
            summary=summary,
        ),
        provenance=provenance,
        quality_state=quality_state,
        quality_flags=quality_flags,
    )


class HistoricalReplaySession:
    """B01 replay with an independent as-of gate over canonical history.

    ``advance`` emits exactly one replay snapshot (unchanged B01 behavior) and
    re-derives the visible observation window from availability times at the
    current replay instant, verifying that both layers describe identical
    facts for the emitted bar. Sidecar observations (option quotes, contract
    metadata, events) join the same gate without affecting bar alignment, and
    every advance appends an :class:`AttributionRecord` binding the decision
    instant to its exact visible-window digest.
    """

    __slots__ = ("_advances", "_bars", "_ledger", "_replay", "_timeline")

    def __init__(
        self,
        replay: DeterministicReplay,
        observations: tuple[MarketObservation, ...],
        *,
        extra_observations: tuple[MarketObservation, ...] = (),
    ) -> None:
        if len(observations) != replay.state.total_bars:
            raise HistoricalTruthError(
                HistoricalTruthErrorCode.HISTORY_REPLAY_MISALIGNED,
                "history observation count does not match replay bar count",
            )
        self._replay = replay
        self._bars = observations
        self._timeline = AsOfTimeline((*observations, *extra_observations))
        self._ledger: tuple[AttributionRecord, ...] = ()
        self._advances = 0

    @property
    def clock(self) -> ClockProtocol:
        return self._replay.clock

    @property
    def state(self) -> ReplayState:
        return self._replay.state

    def advance(self) -> MarketSnapshot:
        index = self._advances
        snapshot = self._replay.advance()
        _verify_alignment(snapshot, self._bars[index])
        self._advances += 1
        now = self._replay.clock.now()
        visible = self._timeline.visible(now)
        self._ledger = (
            *self._ledger,
            AttributionRecord(
                decision_time=now,
                sequence=self._advances,
                visible_count=len(visible),
                window_sha256=_window_digest(visible),
            ),
        )
        return snapshot

    def current(self) -> MarketSnapshot:
        return self._replay.current()

    def snapshot_at(self, sequence: int) -> MarketSnapshot:
        return self._replay.snapshot_at(sequence)

    def visible_snapshots(self) -> tuple[MarketSnapshot, ...]:
        return self._replay.visible_snapshots()

    def visible_observations(self) -> tuple[MarketObservation, ...]:
        """Return observations whose availability precedes the replay instant."""

        return self._timeline.visible(self._replay.clock.now())

    def attribution_ledger(self) -> tuple[AttributionRecord, ...]:
        """Return the per-decision visible-window digests recorded so far."""

        return self._ledger


def create_history_gated_replay(
    dataset: ReplayDataset,
    configuration: ReplayConfiguration,
    *,
    semantics: HistoryTimeSemantics | None = None,
    extra_observations: tuple[MarketObservation, ...] = (),
) -> HistoricalReplaySession:
    """Create a B01 replay together with its gated historical window."""

    replay = DeterministicReplay(dataset, configuration)
    return HistoricalReplaySession(
        replay,
        historical_bar_observations(dataset, semantics=semantics),
        extra_observations=extra_observations,
    )


def _raw_bar_digest(bar: ReplayBar) -> str:
    return canonical_sha256(bar)


def _option_type(value: str | HistoricalOptionType) -> HistoricalOptionType:
    return value if isinstance(value, HistoricalOptionType) else HistoricalOptionType(value)


def _event_class(value: str | HistoricalEventClass) -> HistoricalEventClass:
    return value if isinstance(value, HistoricalEventClass) else HistoricalEventClass(value)


def _window_digest(visible: tuple[MarketObservation, ...]) -> str:
    identities = sorted(str(item.observation_id) for item in visible)
    return canonical_sha256(identities)


def _verify_alignment(snapshot: MarketSnapshot, observation: MarketObservation) -> None:
    payload = observation.payload
    mismatch = (
        observation.times.event_time != snapshot.bar_timestamp
        or observation.instrument != snapshot.instrument_id
        or payload.payload_kind is not ObservationKind.MARKET_BAR
        or payload.open != snapshot.open
        or payload.high != snapshot.high
        or payload.low != snapshot.low
        or payload.close != snapshot.close
        or payload.volume != snapshot.volume
    )
    if mismatch:
        raise HistoricalTruthError(
            HistoricalTruthErrorCode.HISTORY_REPLAY_MISALIGNED,
            f"snapshot {snapshot.snapshot_id} does not match its historical "
            f"observation {observation.observation_id}",
        )


__all__ = [
    "DEFAULT_HISTORY_TIME_SEMANTICS",
    "AttributionRecord",
    "HistoricalReplaySession",
    "HistoryTimeSemantics",
    "create_history_gated_replay",
    "historical_bar_observations",
    "historical_contract_metadata_observation",
    "historical_event_observation",
    "historical_option_quote_observation",
]
