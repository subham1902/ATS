from __future__ import annotations

from decimal import Decimal

from ats.contracts.domain.types import Predicate, PredicateOperator
from ats.contracts.intelligence.types import PriceLevel, PriceLevelKind
from ats.intelligence.calibration import calibrate_outcome_distribution
from ats.intelligence.thesis import ThesisSynthesisConfiguration, ThesisSynthesisFacts

from tests.unit.intelligence.calibration.helpers import (
    calibration_config,
    ensemble,
    observations,
)
from tests.unit.intelligence.ensemble.helpers import context


def distribution():
    result = calibrate_outcome_distribution(
        ensemble=ensemble(),
        market_context=context(),
        target_outcome_code="ABOVE",
        observations=observations(),
        configuration=calibration_config(),
        regime_evidence=None,
    )
    assert result.distribution is not None
    return result.distribution


def configuration() -> ThesisSynthesisConfiguration:
    return ThesisSynthesisConfiguration(
        synthesizer_id="R07_DETERMINISTIC_V1",
        synthesizer_version="1.0.0",
        bullish_outcome_code="ABOVE",
        bearish_outcome_code="NOT_ABOVE",
        activation_probability=Decimal("0.6"),
        validity_ms=120_000,
    )


def facts() -> ThesisSynthesisFacts:
    source = context().market_context_id
    return ThesisSynthesisFacts(
        support_levels=(
            PriceLevel(kind=PriceLevelKind.SUPPORT, price=Decimal("24500"), source_ref=source),
        ),
        resistance_levels=(
            PriceLevel(
                kind=PriceLevelKind.RESISTANCE,
                price=Decimal("24700"),
                source_ref=source,
            ),
        ),
        opportunity_conditions=(
            Predicate(field="market.close", operator=PredicateOperator.GT, value="24500"),
        ),
        invalidation_conditions=(
            Predicate(field="market.close", operator=PredicateOperator.LT, value="24450"),
        ),
    )
