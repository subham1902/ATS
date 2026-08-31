"""Pure cutoff-bounded computation of frozen A02 FeatureBundle evidence."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from uuid import UUID, uuid5

from ats.contracts.domain import FeatureBundle, MarketSnapshot, compute_payload_hash
from ats.contracts.domain.types import DataQualityState
from ats.contracts.hashing import canonical_sha256

from .errors import FeatureInputError, FeatureNumericError
from .registry import V1_FEATURE_CODES, FeatureConfiguration

_FEATURE_BUNDLE_NAMESPACE = UUID("de912867-70c0-5ca4-851b-4d43a622391e")
_DECIMAL_CONTEXT = Context(prec=50, rounding=ROUND_HALF_EVEN)
_BAR_INTERVAL = timedelta(minutes=5)
_WARMUP_FLAG = "INSUFFICIENT_WARMUP"


def _finite_float(value: Decimal) -> float:
    if not value.is_finite():
        raise FeatureNumericError("feature intermediate must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise FeatureNumericError("feature result exceeds finite-float range")
    return result


def _bounded_prefix(
    snapshots: Sequence[MarketSnapshot], cutoff_sequence: int
) -> tuple[MarketSnapshot, ...]:
    if type(cutoff_sequence) is not int or cutoff_sequence <= 0:
        raise FeatureInputError("cutoff_sequence must be a positive integer")
    prefix: list[MarketSnapshot] = []
    for snapshot in snapshots:
        if not isinstance(snapshot, MarketSnapshot):
            raise FeatureInputError("history must contain MarketSnapshot values")
        prefix.append(snapshot)
        if snapshot.sequence == cutoff_sequence:
            return tuple(prefix)
    raise FeatureInputError("cutoff_sequence is not present in the supplied history")


def _validate_snapshot_numbers(snapshot: MarketSnapshot) -> None:
    financial = (snapshot.open, snapshot.high, snapshot.low, snapshot.close, snapshot.volume)
    if any(type(value) is not Decimal or not value.is_finite() for value in financial):
        raise FeatureInputError("snapshot financial values must be finite Decimal values")
    if min(snapshot.open, snapshot.high, snapshot.low, snapshot.close) <= 0:
        raise FeatureInputError("snapshot prices must be positive")
    if snapshot.volume < 0:
        raise FeatureInputError("snapshot volume must be non-negative")
    if not snapshot.low <= snapshot.open <= snapshot.high:
        raise FeatureInputError("snapshot open must be within low/high")
    if not snapshot.low <= snapshot.close <= snapshot.high:
        raise FeatureInputError("snapshot close must be within low/high")


def _validate_prefix(prefix: tuple[MarketSnapshot, ...]) -> None:
    first = prefix[0]
    for index, snapshot in enumerate(prefix):
        _validate_snapshot_numbers(snapshot)
        if snapshot.instrument_id != first.instrument_id:
            raise FeatureInputError("mixed instruments are not permitted")
        if snapshot.timeframe != first.timeframe:
            raise FeatureInputError("mixed timeframes are not permitted")
        if snapshot.quality_state is not DataQualityState.GOOD or snapshot.quality_flags:
            raise FeatureInputError("only GOOD snapshots without quality flags are safe")
        if compute_payload_hash(snapshot) != snapshot.payload_hash:
            raise FeatureInputError("snapshot payload hash is invalid")
        if index:
            previous = prefix[index - 1]
            if snapshot.sequence != previous.sequence + 1:
                raise FeatureInputError("snapshot sequences must be contiguous and increasing")
            if snapshot.bar_timestamp != previous.bar_timestamp + _BAR_INTERVAL:
                raise FeatureInputError("snapshot timestamps must be contiguous five-minute bars")


def _input_hash(prefix: tuple[MarketSnapshot, ...], configuration: FeatureConfiguration) -> str:
    return canonical_sha256(
        {
            "registry_version": configuration.registry_version,
            "cutoff_snapshot_id": str(prefix[-1].snapshot_id),
            "snapshot_payload_hashes": [snapshot.payload_hash for snapshot in prefix],
        }
    )


def _compute_base_features(prefix: tuple[MarketSnapshot, ...]) -> dict[str, float]:
    current = prefix[-1]
    values: dict[str, float] = {}
    if len(prefix) >= 2:
        previous = prefix[-2]
        with localcontext(_DECIMAL_CONTEXT) as context:
            ratio = context.divide(current.close, previous.close)
            values["simple_return"] = _finite_float(context.subtract(ratio, Decimal(1)))
            values["log_return"] = _finite_float(context.ln(ratio))
    values["candle_body"] = _finite_float(current.close - current.open)
    values["candle_range"] = _finite_float(current.high - current.low)
    values["upper_wick"] = _finite_float(current.high - max(current.open, current.close))
    values["lower_wick"] = _finite_float(min(current.open, current.close) - current.low)
    return values


def _compute_rolling_features(prefix: tuple[MarketSnapshot, ...]) -> dict[str, float]:
    values: dict[str, float] = {}
    with localcontext(_DECIMAL_CONTEXT) as context:
        if len(prefix) >= 3:
            window = prefix[-3:]
            volume_sum = sum((bar.volume for bar in window), Decimal(0))
            volume_mean = context.divide(volume_sum, Decimal(3))
            values["rolling_volume_mean_3"] = _finite_float(volume_mean)
            values["relative_volume_3"] = (
                0.0
                if volume_mean == 0
                else _finite_float(context.divide(window[-1].volume, volume_mean))
            )
            trailing_high = max(bar.high for bar in window)
            trailing_low = min(bar.low for bar in window)
            price_range = trailing_high - trailing_low
            values["rolling_price_position_3"] = (
                0.5
                if price_range == 0
                else _finite_float(context.divide(window[-1].close - trailing_low, price_range))
            )
        if len(prefix) >= 4:
            true_ranges: list[Decimal] = []
            returns: list[Decimal] = []
            for index in range(len(prefix) - 3, len(prefix)):
                bar = prefix[index]
                previous_close = prefix[index - 1].close
                true_ranges.append(
                    max(
                        bar.high - bar.low,
                        abs(bar.high - previous_close),
                        abs(bar.low - previous_close),
                    )
                )
                returns.append(
                    context.subtract(context.divide(bar.close, previous_close), Decimal(1))
                )
            atr = context.divide(sum(true_ranges, Decimal(0)), Decimal(3))
            values["atr_3_sma"] = _finite_float(atr)
            return_mean = context.divide(sum(returns, Decimal(0)), Decimal(3))
            squared_deviations = (
                context.multiply(
                    context.subtract(value, return_mean),
                    context.subtract(value, return_mean),
                )
                for value in returns
            )
            variance = context.divide(sum(squared_deviations, Decimal(0)), Decimal(3))
            values["realized_volatility_3_population"] = _finite_float(context.sqrt(variance))
            values["roc_3_fraction"] = _finite_float(
                context.subtract(context.divide(prefix[-1].close, prefix[-4].close), Decimal(1))
            )
    return values


def compute_feature_bundle(
    snapshots: Sequence[MarketSnapshot],
    *,
    cutoff_sequence: int,
    configuration: FeatureConfiguration | None = None,
) -> FeatureBundle:
    """Compute evidence using only the prefix ending at ``cutoff_sequence``.

    Iteration stops at the cutoff snapshot. Later suffix values are never
    validated, hashed, or read by feature calculations.
    """

    resolved_configuration = configuration or FeatureConfiguration()
    prefix = _bounded_prefix(snapshots, cutoff_sequence)
    _validate_prefix(prefix)
    input_hash = _input_hash(prefix, resolved_configuration)
    feature_values = _compute_base_features(prefix)
    feature_values.update(_compute_rolling_features(prefix))
    ordered_values = {
        code: feature_values[code] for code in V1_FEATURE_CODES if code in feature_values
    }
    cutoff = prefix[-1]
    bundle = FeatureBundle(
        schema_version="1.0",
        feature_bundle_id=uuid5(
            _FEATURE_BUNDLE_NAMESPACE,
            f"{resolved_configuration.registry_version}:{cutoff.snapshot_id}:{input_hash}",
        ),
        snapshot_id=cutoff.snapshot_id,
        feature_version=resolved_configuration.registry_version,
        features=ordered_values,
        quality_flags=() if len(ordered_values) == len(V1_FEATURE_CODES) else (_WARMUP_FLAG,),
        computed_at=cutoff.received_at,
        input_hash=input_hash,
    )
    return bundle


__all__ = ["compute_feature_bundle"]
