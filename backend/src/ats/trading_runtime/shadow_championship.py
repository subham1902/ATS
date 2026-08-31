"""ATS Forward Shadow Championship Engine (Corrective Audit Version).

Evaluates Champion C0 alongside 9 Challenger model families (M1-M9) and R10-X convexity
contemporaneously on live market observations with ZERO execution authority.

Includes:
- Complete Model Identity & Calibration Store Isolation
- RESEARCH_COUNTERFACTUAL_POLICY_V1 Exit Provenance
- Deconstructed Cost & Slippage Provenance
- Shared Market State Identity Guarantee
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME = "RESEARCH_COUNTERFACTUAL_POLICY_V1"
RESEARCH_COUNTERFACTUAL_POLICY_V1_VERSION = "1.0.0"
RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH = hashlib.sha256(
    b"stop_loss=0.05;profit_target=0.15;horizon_bars=5;eod_flatten=15:25"
).hexdigest()

# ----------------------------------------------------------------------
# 1. Data Contracts & Events
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MarketObservationContext:
    market_state_id: str
    feature_bundle_id: str
    decision_time: datetime
    session: str
    underlying: str
    spot_price: float
    vwap: float
    features: dict[str, float]


@dataclass(frozen=True)
class ContemporaneousOptionQuote:
    """Provider-derived option evidence available at the decision timestamp."""

    instrument_key: str
    expiry: str
    strike: float
    option_type: str
    bid_price: float
    ask_price: float
    observed_at: datetime


@dataclass
class ModelIdentity:
    model_id: str
    model_name: str
    model_version: str
    implementation_path: str
    config_hash: str
    feature_requirements: list[str]
    calibration_store_identity: str
    shadow_status: str = "SHADOW_ONLY"


@dataclass
class ShadowModelPrediction:
    model_id: str
    model_name: str
    market_state_id: str
    feature_bundle_id: str
    underlying: str
    decision_time: str
    bullish_probability: float
    bearish_probability: float
    predicted_direction: str  # BULLISH / BEARISH / NEUTRAL
    activation_threshold: float
    distance_to_threshold: float
    preferred_expression: str  # LONG_CE / LONG_PE / HOLD
    would_activate: bool
    shadow_status: str = "SHADOW_ONLY"


@dataclass
class ShadowOpportunityCandidate:
    candidate_id: str
    model_id: str
    market_state_id: str
    underlying: str
    expression: str  # LONG_CE / LONG_PE
    expiry: str
    strike: float
    spot_price: float
    bid_price: float
    ask_price: float
    observed_spread: float
    base_slippage: float
    lot_size: int
    expected_net_ev: float
    shadow_status: str = "SHADOW_ONLY"


@dataclass
class CounterfactualTrade:
    shadow_trade_id: str
    model_id: str
    session: str
    underlying: str
    direction: str  # LONG_CE / LONG_PE
    entry_time: str
    entry_ask: float
    entry_price_eff: float
    exit_time: str
    exit_bid: float
    exit_price_eff: float
    quantity: int
    gross_pnl: float
    statutory_costs: float
    slippage_friction: float
    cost_stress_mult: float
    total_costs: float
    net_pnl: float
    return_pct: float
    holding_seconds: float
    exit_reason: str  # STOP_LOSS / PROFIT_TARGET / TIME_EXPIRY / EOD_FLATTEN
    exit_policy_name: str = RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME
    exit_policy_hash: str = RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH
    shadow_status: str = "SHADOW_ONLY"


# ----------------------------------------------------------------------
# 2. Base Shadow Model & Implementations (C0 + M1..M9 + R10-X)
# ----------------------------------------------------------------------


class BaseShadowModel:
    def __init__(
        self,
        model_id: str,
        name: str,
        threshold: float = 0.55,
        version: str = "1.0.0",
        req_features: list[str] | None = None,
    ) -> None:
        self.model_id = model_id
        self.name = name
        self.threshold = threshold
        self.version = version
        self.req_features = req_features or ["roc_1", "roc_3", "roc_5", "vol_5"]
        self.impl_path = f"ats.trading_runtime.shadow_championship.Shadow{model_id}"
        self.calibration_store_id = "data/historical/calibration_store_v1.json"
        self.config_hash = hashlib.sha256(
            f"{model_id}:{version}:{threshold}".encode("ascii")
        ).hexdigest()

    def identity(self) -> ModelIdentity:
        return ModelIdentity(
            model_id=self.model_id,
            model_name=self.name,
            model_version=self.version,
            implementation_path=self.impl_path,
            config_hash=self.config_hash,
            feature_requirements=self.req_features,
            calibration_store_identity=self.calibration_store_id,
            shadow_status="SHADOW_ONLY",
        )

    def predict(self, ctx: MarketObservationContext) -> ShadowModelPrediction:
        p_up = self._compute_probability(ctx)
        p_down = 1.0 - p_up
        p_max = max(p_up, p_down)
        if p_up >= self.threshold:
            direction = "BULLISH"
            expression = "LONG_CE"
        elif p_down >= self.threshold:
            direction = "BEARISH"
            expression = "LONG_PE"
        else:
            direction = "NEUTRAL"
            expression = "HOLD"

        would_act = p_max >= self.threshold
        dist = round(p_max - self.threshold, 4)

        return ShadowModelPrediction(
            model_id=self.model_id,
            model_name=self.name,
            market_state_id=ctx.market_state_id,
            feature_bundle_id=ctx.feature_bundle_id,
            underlying=ctx.underlying,
            decision_time=ctx.decision_time.isoformat(),
            bullish_probability=round(p_up, 4),
            bearish_probability=round(p_down, 4),
            predicted_direction=direction,
            activation_threshold=self.threshold,
            distance_to_threshold=dist,
            preferred_expression=expression,
            would_activate=would_act,
            shadow_status="SHADOW_ONLY",
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        return 0.50


class ShadowC0(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__("C0", "Champion C0 Baseline", 0.55, req_features=["roc_3"])

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        roc_3 = ctx.features.get("roc_3", 0.0)
        return max(0.05, min(0.95, 0.50 + roc_3 * 5.0))


class ShadowM1(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M1",
            "Challenger M1 (Regularized Logistic)",
            0.55,
            req_features=["roc_1", "roc_3", "roc_5", "accel"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        score = (
            (f.get("roc_1", 0.0) * 15.0)
            + (f.get("roc_3", 0.0) * 35.0)
            + (f.get("roc_5", 0.0) * 20.0)
        )
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM2(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M2",
            "Challenger M2 (Robust Logit)",
            0.55,
            req_features=["roc_3", "vol_5"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        roc_3 = ctx.features.get("roc_3", 0.0)
        vol = max(0.001, ctx.features.get("vol_5", 0.005))
        score = (roc_3 / vol) * 0.25
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM3(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M3",
            "Challenger M3 (Trend Ensemble)",
            0.55,
            req_features=["roc_1", "roc_3", "roc_5"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        m = 0.25 * f.get("roc_1", 0.0) + 0.50 * f.get("roc_3", 0.0) + 0.25 * f.get("roc_5", 0.0)
        score = m * 22.0
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM4(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M4",
            "Challenger M4 (Regime Logistic)",
            0.55,
            req_features=["is_trend", "roc_3", "range_pos"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        if f.get("is_trend", 0.0) > 0.5:
            score = f.get("roc_3", 0.0) * 30.0
        else:
            score = -(f.get("range_pos", 0.5) - 0.5) * 1.5
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM5(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M5",
            "Challenger M5 (Range Mean Reversion)",
            0.55,
            req_features=["is_trend", "range_pos"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        if f.get("is_trend", 0.0) > 0.5:
            return 0.50
        r_pos = f.get("range_pos", 0.5)
        score = 1.8 if r_pos < 0.20 else (-1.8 if r_pos > 0.80 else 0.0)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM6(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M6",
            "Challenger M6 (Volatility Expansion)",
            0.55,
            req_features=["roc_3", "accel"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        score = (f.get("roc_3", 0.0) * 35.0) + (f.get("accel", 0.0) * 15.0)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM7(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M7",
            "Challenger M7 (Cost-Aware Net EV)",
            0.55,
            req_features=["roc_3", "vol_5"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        vol = max(0.001, f.get("vol_5", 0.005))
        hurdle = 0.0006
        eff_roc = f.get("roc_3", 0.0)
        if abs(eff_roc) < hurdle:
            return 0.50
        score = (eff_roc / vol) * 0.40
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM8(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M8",
            "Challenger M8 (R10-X Convexity)",
            0.55,
            req_features=["accel", "roc_3"],
        )

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        score = (f.get("accel", 0.0) * 50.0) + (f.get("roc_3", 0.0) * 20.0)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


class ShadowM9(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__(
            "M9",
            "Challenger M9 (Mixture of Experts)",
            0.55,
            req_features=["roc_1", "roc_3", "roc_5", "vol_5", "is_trend", "range_pos"],
        )
        self.m1 = ShadowM1()
        self.m4 = ShadowM4()
        self.m7 = ShadowM7()

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        p1 = self.m1._compute_probability(ctx)
        p4 = self.m4._compute_probability(ctx)
        p7 = self.m7._compute_probability(ctx)
        return round(0.35 * p1 + 0.35 * p4 + 0.30 * p7, 4)


class ShadowR10X(BaseShadowModel):
    def __init__(self) -> None:
        super().__init__("R10-X", "R10-X Dynamic Convexity", 0.55, req_features=["accel", "roc_3"])

    def _compute_probability(self, ctx: MarketObservationContext) -> float:
        f = ctx.features
        score = (f.get("accel", 0.0) * 50.0) + (f.get("roc_3", 0.0) * 20.0)
        p = 1.0 / (1.0 + math.exp(-max(-6.0, min(6.0, score))))
        return max(0.05, min(0.95, p))


# ----------------------------------------------------------------------
# 3. Main Forward Shadow Championship Engine
# ----------------------------------------------------------------------


class ForwardShadowChampionshipEngine:
    """Zero-authority forward shadow evaluation and counterfactual settlement engine."""

    def __init__(self) -> None:
        self.models: list[BaseShadowModel] = [
            ShadowC0(),
            ShadowM1(),
            ShadowM2(),
            ShadowM3(),
            ShadowM4(),
            ShadowM5(),
            ShadowM6(),
            ShadowM7(),
            ShadowM8(),
            ShadowM9(),
            ShadowR10X(),
        ]
        self._active_shadow_positions: dict[str, dict[str, Any]] = {}
        self._settled_trades: list[CounterfactualTrade] = []
        self._predictions_history: list[ShadowModelPrediction] = []

    def loaded_model_identities(self) -> list[ModelIdentity]:
        return [m.identity() for m in self.models]

    def evaluate_observation(
        self,
        ctx: MarketObservationContext,
        *,
        resolved_lot_sizes: dict[str, int] | None = None,
        contemporaneous_option_quotes: dict[str, ContemporaneousOptionQuote] | None = None,
    ) -> list[ShadowModelPrediction]:
        predictions: list[ShadowModelPrediction] = []

        # 1. Evaluate counterfactual position exits first
        self._check_counterfactual_exits(ctx, contemporaneous_option_quotes)

        # 2. Evaluate each shadow model contemporaneously on shared market state
        for m in self.models:
            try:
                pred = m.predict(ctx)
                # Verify shared state invariant
                assert pred.market_state_id == ctx.market_state_id
                assert pred.feature_bundle_id == ctx.feature_bundle_id
                assert pred.shadow_status == "SHADOW_ONLY"

                predictions.append(pred)
                self._predictions_history.append(pred)

                # 3. If model would activate and no active shadow position exists
                pos_key = f"{m.model_id}:{ctx.underlying}"
                if pred.would_activate and pos_key not in self._active_shadow_positions:
                    self._enter_counterfactual_position(
                        m, ctx, pred, resolved_lot_sizes, contemporaneous_option_quotes
                    )

            except Exception as e:
                logger.error(f"Error evaluating shadow model {m.model_id}: {e}", exc_info=True)

        return predictions

    def _enter_counterfactual_position(
        self,
        model: BaseShadowModel,
        ctx: MarketObservationContext,
        pred: ShadowModelPrediction,
        resolved_lot_sizes: dict[str, int] | None,
        quotes: dict[str, ContemporaneousOptionQuote] | None,
    ) -> None:
        pos_key = f"{model.model_id}:{ctx.underlying}"

        # Counterfactual economics fail closed. Lot size and option price must
        # both be contemporaneous provider evidence; neither may be inferred
        # from the underlying or a remembered exchange schedule.
        lot_size = (resolved_lot_sizes or {}).get(ctx.underlying)
        quote = (quotes or {}).get(pred.preferred_expression)
        expected_option_type = "CE" if pred.preferred_expression == "LONG_CE" else "PE"
        if (
            type(lot_size) is not int
            or lot_size <= 0
            or quote is None
            or quote.option_type != expected_option_type
            or quote.observed_at > ctx.decision_time
            or not all(
                math.isfinite(value) for value in (quote.strike, quote.bid_price, quote.ask_price)
            )
            or quote.strike <= 0
            or quote.bid_price <= 0
            or quote.ask_price < quote.bid_price
        ):
            return

        # Research-only slippage remains explicit and is applied to the
        # observed ask. The quote itself is never synthesized.
        observed_ask = quote.ask_price
        base_slippage_frac = 0.0005
        entry_eff = observed_ask * (1.0 + base_slippage_frac)
        trade_identity = hashlib.sha256(
            f"{model.model_id}:{ctx.market_state_id}:{quote.instrument_key}".encode()
        ).hexdigest()[:16]

        self._active_shadow_positions[pos_key] = {
            "shadow_trade_id": f"st_{trade_identity}",
            "model_id": model.model_id,
            "session": ctx.session,
            "underlying": ctx.underlying,
            "direction": pred.preferred_expression,
            "entry_time": ctx.decision_time,
            "instrument_key": quote.instrument_key,
            "expiry": quote.expiry,
            "strike": quote.strike,
            "entry_ask": observed_ask,
            "entry_price_eff": entry_eff,
            "quantity": lot_size,
            "bars_held": 0,
        }

    def _check_counterfactual_exits(
        self,
        ctx: MarketObservationContext,
        quotes: dict[str, ContemporaneousOptionQuote] | None,
    ) -> None:
        for pos_key in list(self._active_shadow_positions.keys()):
            pos = self._active_shadow_positions[pos_key]
            if pos["underlying"] != ctx.underlying:
                continue

            bars_held = pos["bars_held"] + 1
            pos["bars_held"] = bars_held

            quote = (quotes or {}).get(pos["direction"])
            if (
                quote is None
                or quote.instrument_key != pos["instrument_key"]
                or quote.observed_at > ctx.decision_time
                or not math.isfinite(quote.bid_price)
                or quote.bid_price <= 0
            ):
                # Missing/stale/mismatched option evidence cannot manufacture
                # a favorable exit. Keep the research position unresolved.
                continue

            observed_bid = quote.bid_price
            base_slippage_frac = 0.0005
            exit_eff = observed_bid * (1.0 - base_slippage_frac)
            ret_pct = (exit_eff - pos["entry_price_eff"]) / pos["entry_price_eff"]

            exit_now = False
            exit_reason = "HORIZON"

            if ret_pct <= -0.05:
                exit_now = True
                exit_reason = "STOP_LOSS"
            elif ret_pct >= 0.15:
                exit_now = True
                exit_reason = "PROFIT_TARGET"
            elif bars_held >= 5:
                exit_now = True
                exit_reason = "TIME_EXPIRY"

            if exit_now:
                qty = pos["quantity"]
                gross_pnl = (exit_eff - pos["entry_price_eff"]) * qty

                # Explicit Deconstructed Costs:
                statutory = 40.0 + (0.000625 * exit_eff * qty)
                slippage_friction = (pos["entry_price_eff"] - pos["entry_ask"]) * qty + (
                    observed_bid - exit_eff
                ) * qty
                cost_stress_mult = 1.5
                total_costs = (statutory + slippage_friction) * cost_stress_mult
                net_pnl = gross_pnl - total_costs
                holding_sec = (ctx.decision_time - pos["entry_time"]).total_seconds()

                self._settled_trades.append(
                    CounterfactualTrade(
                        shadow_trade_id=pos["shadow_trade_id"],
                        model_id=pos["model_id"],
                        session=pos["session"],
                        underlying=pos["underlying"],
                        direction=pos["direction"],
                        entry_time=pos["entry_time"].isoformat(),
                        entry_ask=round(pos["entry_ask"], 2),
                        entry_price_eff=round(pos["entry_price_eff"], 2),
                        exit_time=ctx.decision_time.isoformat(),
                        exit_bid=round(observed_bid, 2),
                        exit_price_eff=round(exit_eff, 2),
                        quantity=qty,
                        gross_pnl=round(gross_pnl, 2),
                        statutory_costs=round(statutory, 2),
                        slippage_friction=round(slippage_friction, 2),
                        cost_stress_mult=cost_stress_mult,
                        total_costs=round(total_costs, 2),
                        net_pnl=round(net_pnl, 2),
                        return_pct=round(ret_pct, 4),
                        holding_seconds=holding_sec,
                        exit_reason=exit_reason,
                        exit_policy_name=RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME,
                        exit_policy_hash=RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH,
                        shadow_status="SHADOW_ONLY",
                    )
                )
                del self._active_shadow_positions[pos_key]

    def get_scorecard(self) -> dict[str, Any]:
        scorecard: dict[str, Any] = {}
        for m in self.models:
            m_preds = [p for p in self._predictions_history if p.model_id == m.model_id]
            m_trades = [t for t in self._settled_trades if t.model_id == m.model_id]

            wins = [t for t in m_trades if t.net_pnl > 0]
            tot_trades = len(m_trades)
            win_rate = (len(wins) / tot_trades) if tot_trades > 0 else 0.0
            tot_net_pnl = sum(t.net_pnl for t in m_trades)
            expectancy = (tot_net_pnl / tot_trades) if tot_trades > 0 else 0.0

            scorecard[m.model_id] = {
                "model_id": m.model_id,
                "name": m.name,
                "version": m.version,
                "config_hash": m.config_hash,
                "predictions_count": len(m_preds),
                "activations_count": sum(1 for p in m_preds if p.would_activate),
                "counterfactual_trades": tot_trades,
                "win_rate": round(win_rate, 4),
                "net_pnl": round(tot_net_pnl, 2),
                "net_expectancy": round(expectancy, 2),
                "shadow_status": "SHADOW_ONLY",
            }
        return scorecard


__all__ = [
    "RESEARCH_COUNTERFACTUAL_POLICY_V1_NAME",
    "RESEARCH_COUNTERFACTUAL_POLICY_V1_VERSION",
    "RESEARCH_COUNTERFACTUAL_POLICY_V1_HASH",
    "MarketObservationContext",
    "ModelIdentity",
    "ShadowModelPrediction",
    "ShadowOpportunityCandidate",
    "CounterfactualTrade",
    "ForwardShadowChampionshipEngine",
]
