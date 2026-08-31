from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal

import pytest
from ats.contracts.domain import compute_payload_hash
from ats.market.features import (
    V1_FEATURE_CODES,
    FeatureInputError,
    FeatureNumericError,
    compute_feature_bundle,
)

from tests.unit.market.features.helpers import four_bars, snapshot


@pytest.mark.parametrize("cutoff", [1, 2, 3, 4])
def test_repeated_computation_is_byte_deterministic(cutoff: int) -> None:
    bars = four_bars()
    first = compute_feature_bundle(bars, cutoff_sequence=cutoff)
    second = compute_feature_bundle(bars, cutoff_sequence=cutoff)
    assert first.model_dump_json() == second.model_dump_json()
    assert first.feature_bundle_id == second.feature_bundle_id
    assert first.input_hash == second.input_hash


def test_future_suffix_is_structurally_unread() -> None:
    prefix = four_bars()
    suffix_a = (snapshot(5, close="105", high="108"),)
    unsafe_suffix_b = (
        snapshot(5).model_copy(update={"instrument_id": "TCS", "close": Decimal("NaN")}),
        object(),
    )
    expected = compute_feature_bundle(prefix, cutoff_sequence=4)
    with_a = compute_feature_bundle(prefix + suffix_a, cutoff_sequence=4)
    with_b = compute_feature_bundle(prefix + unsafe_suffix_b, cutoff_sequence=4)  # type: ignore[arg-type]
    assert expected.model_dump_json() == with_a.model_dump_json() == with_b.model_dump_json()


def test_warmup_never_fabricates_rolling_values() -> None:
    bars = four_bars()
    expected_codes = {
        1: V1_FEATURE_CODES[2:6],
        2: V1_FEATURE_CODES[:6],
        3: V1_FEATURE_CODES[:6] + V1_FEATURE_CODES[9:],
        4: V1_FEATURE_CODES,
    }
    for cutoff, codes in expected_codes.items():
        bundle = compute_feature_bundle(bars, cutoff_sequence=cutoff)
        assert tuple(bundle.features) == codes
        assert all(math.isfinite(value) for value in bundle.features.values())


@pytest.mark.parametrize(
    "bad_value",
    [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), float("nan"), float("inf")],
)
def test_non_finite_or_wrong_boundary_values_are_rejected(bad_value: object) -> None:
    bad = snapshot(1).model_copy(update={"close": bad_value})
    with pytest.raises(FeatureInputError, match="finite Decimal"):
        compute_feature_bundle((bad,), cutoff_sequence=1)


def test_extreme_but_finite_values_remain_finite() -> None:
    bars = tuple(
        snapshot(
            sequence,
            open_="1e300",
            high="1.0000000002e300",
            low="9.999999999e299",
            close="1.0000000001e300",
            volume="1e300",
        )
        for sequence in range(1, 5)
    )
    bundle = compute_feature_bundle(bars, cutoff_sequence=4)
    assert len(bundle.features) == 12
    assert all(math.isfinite(value) for value in bundle.features.values())


def test_finite_decimal_outside_binary64_range_fails_closed() -> None:
    huge = snapshot(1).model_copy(
        update={
            "open": Decimal("1e9999"),
            "high": Decimal("2e9999"),
            "low": Decimal("1e9999"),
            "close": Decimal("2e9999"),
        }
    )
    huge = huge.model_copy(update={"payload_hash": compute_payload_hash(huge)})
    with pytest.raises(FeatureNumericError, match="finite-float range"):
        compute_feature_bundle((huge,), cutoff_sequence=1)


@pytest.mark.parametrize(
    "mutation",
    [
        {"sequence": 1},
        {"sequence": 4},
        {"bar_timestamp": snapshot(1).bar_timestamp},
        {"bar_timestamp": snapshot(2).bar_timestamp + timedelta(minutes=10)},
    ],
)
def test_duplicate_out_of_order_and_gapped_bars_are_rejected(
    mutation: dict[str, object],
) -> None:
    first, second = snapshot(1), snapshot(2)
    changed = second.model_copy(update=mutation)
    changed = changed.model_copy(update={"payload_hash": compute_payload_hash(changed)})
    cutoff = changed.sequence
    if cutoff == 1:
        bars = (first, changed, snapshot(2))
        cutoff = 2
    else:
        bars = (first, changed)
    with pytest.raises(FeatureInputError, match="sequences|timestamps"):
        compute_feature_bundle(bars, cutoff_sequence=cutoff)


def test_cutoff_progression_preserves_snapshot_binding_and_changes_input_hash() -> None:
    bars = four_bars()
    bundles = [compute_feature_bundle(bars, cutoff_sequence=value) for value in range(1, 5)]
    assert [bundle.snapshot_id for bundle in bundles] == [bar.snapshot_id for bar in bars]
    assert len({bundle.input_hash for bundle in bundles}) == 4
    assert len({bundle.feature_bundle_id for bundle in bundles}) == 4
