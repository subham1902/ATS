"""Deterministic Champion / Challenger strategy lifecycle registry and gating."""

from __future__ import annotations

from uuid import UUID

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import PromotionDecision, StrategyScorecard

from .models import ChampionRecord, StrategyLifecycleStatus


class ChampionChallengerRegistry:
    """Registry maintaining active champions and shadow challengers."""

    def __init__(self) -> None:
        self._champions: dict[str, ChampionRecord] = {}  # family -> ChampionRecord
        self._strategies: dict[UUID, ChampionRecord] = {}  # strategy_id -> ChampionRecord

    def register_challenger(
        self,
        *,
        family: str,
        strategy_id: UUID,
        strategy_version: int,
        scorecard: StrategyScorecard | None = None,
        notes: str = "Registered research challenger",
    ) -> ChampionRecord:
        """Register a new candidate strategy as a shadow Challenger."""
        rec = ChampionRecord(
            family=family,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            lifecycle_status=StrategyLifecycleStatus.CHALLENGER,
            scorecard=scorecard,
            promoted_at=None,
            retired_at=None,
            notes=notes,
        )
        self._strategies[strategy_id] = rec
        return rec

    def promote_to_champion(
        self,
        *,
        strategy_id: UUID,
        promotion_decision: PromotionDecision,
        promoted_at: UTCDateTime,
    ) -> ChampionRecord:
        """Promote a challenger to champion via deterministic PromotionDecision."""
        if promotion_decision.candidate_strategy_ref.strategy_definition_id != strategy_id:
            raise ValueError("Promotion decision does not match strategy ID")

        rec = self._strategies.get(strategy_id)
        if rec is None:
            raise KeyError(f"Strategy {strategy_id} is not registered")
        if rec.lifecycle_status is StrategyLifecycleStatus.RETIRED:
            raise ValueError("Cannot promote a retired strategy")

        family = rec.family
        # If there is an existing active champion for this family, retire it
        if family in self._champions:
            old_champ = self._champions[family]
            retired_old = old_champ.model_copy(
                update={
                    "lifecycle_status": StrategyLifecycleStatus.RETIRED,
                    "retired_at": promoted_at,
                    "notes": f"Retired in favor of champion {strategy_id}",
                }
            )
            self._champions[family] = retired_old
            self._strategies[old_champ.strategy_id] = retired_old

        promoted = rec.model_copy(
            update={
                "lifecycle_status": StrategyLifecycleStatus.CHAMPION,
                "promoted_at": promoted_at,
                "notes": f"Promoted via decision {promotion_decision.promotion_decision_id}",
            }
        )
        self._champions[family] = promoted
        self._strategies[strategy_id] = promoted
        return promoted

    def reject_challenger(
        self,
        *,
        strategy_id: UUID,
        reason: str,
    ) -> ChampionRecord:
        """Mark a challenger as rejected."""
        rec = self._strategies.get(strategy_id)
        if rec is None:
            raise KeyError(f"Strategy {strategy_id} is not registered")
        rejected = rec.model_copy(
            update={
                "lifecycle_status": StrategyLifecycleStatus.REJECTED,
                "notes": f"Rejected: {reason}",
            }
        )
        self._strategies[strategy_id] = rejected
        return rejected

    def get_champion(self, family: str) -> ChampionRecord | None:
        """Return the active champion for the strategy family, if any."""
        champ = self._champions.get(family)
        if champ and champ.lifecycle_status is StrategyLifecycleStatus.CHAMPION:
            return champ
        return None

    def get_record(self, strategy_id: UUID) -> ChampionRecord | None:
        """Return the record for the given strategy ID."""
        return self._strategies.get(strategy_id)

    def is_execution_eligible(self, strategy_id: UUID) -> bool:
        """Infallible gate: Only active Champions may be executed."""
        rec = self._strategies.get(strategy_id)
        if rec is None:
            return False
        return rec.lifecycle_status is StrategyLifecycleStatus.CHAMPION


__all__ = ["ChampionChallengerRegistry"]
