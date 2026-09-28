"""Statistical strategy evaluation with shrinkage and a minimum evidence bar.

The pre-audit rule was ``rotate if strat_losses >= 2 and strat_pnl < 0``. That
discards a strategy after two observations - before any statistical meaning
exists - while simultaneously having no mechanism to graduate a strategy on
evidence. It is a churn engine, not a learning engine.

This module replaces it with a Beta-Binomial posterior on win rate that shrinks
toward the portfolio prior, plus:

* a minimum sample size before any verdict is issued,
* net-of-cost expectations (a strategy that wins on price but loses after
  charges has no edge),
* explicit confidence intervals,
* deterministic graduation to a live allocation only on validated evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

#: Win rate prior across a new, unproven strategy. Deliberately pessimistic:
#: most strategies are unprofitable, so the prior should not assume otherwise.
PRIOR_WIN_RATE = 0.35

#: Prior strength in pseudo-trades. Equivalent to "we have seen this strategy
#: 20 times and it hit 35%". Small enough that real evidence dominates quickly.
PRIOR_STRENGTH = 20.0

#: Minimum closed trades before a strategy may be judged at all.
MIN_SAMPLE_FOR_VERDICT = 30

#: Minimum closed trades before a strategy may be granted a live allocation.
MIN_SAMPLE_FOR_GRADUATION = 100

#: Net expectancy per trade required to graduate, in currency units.
MIN_GRADUATION_EXPECTANCY = 0.0

#: Minimum probability that true win rate exceeds break-even, to graduate.
MIN_GRADUATION_POSTERIOR = 0.60


@dataclass
class StrategyEvidence:
    """Accumulated out-of-sample evidence for one strategy."""

    strategy_id: str
    wins: int = 0
    losses: int = 0
    scratches: int = 0
    net_pnl: float = 0.0
    gross_pnl: float = 0.0
    charges_paid: float = 0.0
    gross_win_rate: float = 0.0
    net_win_rate: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    max_drawdown: float = 0.0
    _peak: float = 0.0
    samples: list[float] = field(default_factory=list, repr=False)

    @property
    def total_trades(self) -> int:
        return self.wins + self.losses + self.scratches

    @property
    def decided_trades(self) -> int:
        """Trades that carry directional information (excludes scratches)."""
        return self.wins + self.losses

    def record(
        self,
        *,
        net_pnl: float,
        gross_pnl: float,
        charges: float,
    ) -> None:
        if net_pnl > 0:
            self.wins += 1
        elif net_pnl < 0:
            self.losses += 1
        else:
            self.scratches += 1

        self.net_pnl = round(self.net_pnl + net_pnl, 2)
        self.gross_pnl = round(self.gross_pnl + gross_pnl, 2)
        self.charges_paid = round(self.charges_paid + charges, 2)
        self.best_trade = max(self.best_trade, net_pnl)
        self.worst_trade = min(self.worst_trade, net_pnl)
        self.samples.append(net_pnl)

        self._peak = max(self._peak, self.net_pnl)
        self.max_drawdown = max(self.max_drawdown, self._peak - self.net_pnl)

        decided = self.decided_trades
        if decided > 0:
            self.gross_win_rate = round(
                sum(1 for s in self.samples if s > 0) / len(self.samples) * 100.0, 1
            )
            self.net_win_rate = round(self.wins / decided * 100.0, 1)

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "total_trades": self.total_trades,
            "decided_trades": self.decided_trades,
            "wins": self.wins,
            "losses": self.losses,
            "net_pnl": self.net_pnl,
            "gross_pnl": self.gross_pnl,
            "charges_paid": self.charges_paid,
            "net_win_rate": self.net_win_rate,
            "gross_win_rate": self.gross_win_rate,
            "avg_net_pnl": round(self.net_pnl / self.total_trades, 2)
            if self.total_trades
            else 0.0,
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2),
            "max_drawdown": round(self.max_drawdown, 2),
        }


@dataclass(frozen=True, slots=True)
class EdgeVerdict:
    """Statistical assessment of a strategy's live edge."""

    status: str
    posterior_win_rate: float
    ci_low: float
    ci_high: float
    prob_above_breakeven: float
    expected_net_per_trade: float
    sample_size: int
    sample_sufficient: bool
    rationale: str
    recommended_lot_multiplier: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "posterior_win_rate": round(self.posterior_win_rate * 100.0, 1),
            "ci_low": round(self.ci_low * 100.0, 1),
            "ci_high": round(self.ci_high * 100.0, 1),
            "prob_above_breakeven": round(self.prob_above_breakeven, 3),
            "expected_net_per_trade": round(self.expected_net_per_trade, 2),
            "sample_size": self.sample_size,
            "sample_sufficient": self.sample_sufficient,
            "rationale": self.rationale,
            "recommended_lot_multiplier": round(self.recommended_lot_multiplier, 2),
        }


def _beta_posterior(wins: int, losses: int) -> tuple[float, float]:
    """Beta(a, b) parameters with a Jeffreys prior plus a pessimistic base rate."""
    a = PRIOR_STRENGTH * PRIOR_WIN_RATE + wins + 0.5
    b = PRIOR_STRENGTH * (1.0 - PRIOR_WIN_RATE) + losses + 0.5
    return a, b


def _beta_mean(a: float, b: float) -> float:
    return a / (a + b)


def _beta_cdf(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta via the continued fraction (Lentz)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    ln_beta = (
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log(1.0 - x)
    )
    front = math.exp(ln_beta)

    if x < (a + 1.0) / (a + b + 2.0):
        return _beta_cf(x, a, b) * front / a

    return 1.0 - math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + b * math.log(1.0 - x)
        + a * math.log(x)
    ) * _beta_cf(1.0 - x, b, a) / b


def _beta_cf(x: float, a: float, b: float, *, itmax: int = 300, eps: float = 3e-12) -> float:
    """Continued fraction for the incomplete beta function."""
    tiny = 1e-30
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def probability_win_rate_exceeds(
    wins: int, losses: int, threshold: float
) -> float:
    """P(true win rate > threshold) under the Beta posterior."""
    a, b = _beta_posterior(wins, losses)
    if threshold <= 0.0:
        return 1.0
    if threshold >= 1.0:
        return 0.0
    return 1.0 - _beta_cdf(threshold, a, b)


class StrategyEdgeRegistry:
    """Central, per-strategy evidence store with statistical verdicts."""

    def __init__(
        self,
        *,
        min_sample: int = MIN_SAMPLE_FOR_VERDICT,
        min_graduation_sample: int = MIN_SAMPLE_FOR_GRADUATION,
    ) -> None:
        self._evidence: dict[str, StrategyEvidence] = {}
        self._min_sample = min_sample
        self._min_graduation = min_graduation_sample

    def evidence_for(self, strategy_id: str) -> StrategyEvidence:
        ev = self._evidence.get(strategy_id)
        if ev is None:
            ev = StrategyEvidence(strategy_id=strategy_id)
            self._evidence[strategy_id] = ev
        return ev

    def record_trade(
        self,
        strategy_id: str,
        *,
        net_pnl: float,
        gross_pnl: float,
        charges: float,
    ) -> StrategyEvidence:
        ev = self.evidence_for(strategy_id)
        ev.record(net_pnl=net_pnl, gross_pnl=gross_pnl, charges=charges)
        return ev

    def evaluate(
        self,
        strategy_id: str,
        *,
        required_win_rate: float,
        net_if_win: float,
        net_if_loss: float,
    ) -> EdgeVerdict:
        """Produce a calibrated verdict for a strategy at a given trade geometry.

        ``required_win_rate`` is the cost-adjusted win rate the strategy must
        clear to break even at this target/stop pair. Graduating a strategy that
        is merely "profitable" is not enough - it must clear the bar its own
        costs impose.
        """
        ev = self.evidence_for(strategy_id)
        a, b = _beta_posterior(ev.wins, ev.losses)
        mean_wr = _beta_mean(a, b)

        # Central 68% credible interval from the posterior, via beta quantiles.
        ci_low = _beta_quantile(0.16, a, b)
        ci_high = _beta_quantile(0.84, a, b)

        prob_above = probability_win_rate_exceeds(
            ev.wins, ev.losses, required_win_rate
        )

        expected_net = mean_wr * net_if_win + (1.0 - mean_wr) * net_if_loss

        n = ev.decided_trades
        if n < self._min_sample:
            return EdgeVerdict(
                status="INSUFFICIENT_EVIDENCE",
                posterior_win_rate=mean_wr,
                ci_low=ci_low,
                ci_high=ci_high,
                prob_above_breakeven=prob_above,
                expected_net_per_trade=expected_net,
                sample_size=n,
                sample_sufficient=False,
                rationale=(
                    f"{n}/{self._min_sample} trades. No verdict issued - "
                    f"posterior shrunk to prior {mean_wr * 100:.1f}%."
                ),
                recommended_lot_multiplier=0.0,
            )

        if prob_above >= MIN_GRADUATION_POSTERIOR and expected_net > MIN_GRADUATION_EXPECTANCY:
            if n >= self._min_graduation:
                status = "GRADUATED"
                lot_mult = 1.5 if expected_net > 0 else 1.0
                rationale = (
                    f"{n} trades, posterior WR {mean_wr * 100:.1f}% vs required "
                    f"{required_win_rate * 100:.1f}% (P={prob_above:.2f}), "
                    f"expectancy Rs.{expected_net:,.2f}/trade. Cleared graduation bar."
                )
            else:
                status = "PROMISING"
                lot_mult = 1.0
                rationale = (
                    f"{n} trades show positive edge (P={prob_above:.2f}) but "
                    f"{self._min_graduation - n} more needed for live allocation."
                )
            return EdgeVerdict(
                status=status,
                posterior_win_rate=mean_wr,
                ci_low=ci_low,
                ci_high=ci_high,
                prob_above_breakeven=prob_above,
                expected_net_per_trade=expected_net,
                sample_size=n,
                sample_sufficient=True,
                rationale=rationale,
                recommended_lot_multiplier=lot_mult,
            )

        if expected_net < 0:
            status = "NEGATIVE_EXPECTANCY"
            rationale = (
                f"{n} trades, expectancy Rs.{expected_net:,.2f}/trade at posterior "
                f"WR {mean_wr * 100:.1f}%. Retiring candidate."
            )
        else:
            status = "UNPROVEN"
            rationale = (
                f"{n} trades, expectancy positive (Rs.{expected_net:,.2f}) but only "
                f"P={prob_above:.2f} of clearing the {required_win_rate * 100:.1f}% bar."
            )

        return EdgeVerdict(
            status=status,
            posterior_win_rate=mean_wr,
            ci_low=ci_low,
            ci_high=ci_high,
            prob_above_breakeven=prob_above,
            expected_net_per_trade=expected_net,
            sample_size=n,
            sample_sufficient=True,
            rationale=rationale,
            recommended_lot_multiplier=0.0,
        )

    def should_retire(self, strategy_id: str) -> tuple[bool, str]:
        """Retire a strategy only on evidence, never on a loss count."""
        ev = self.evidence_for(strategy_id)
        if ev.decided_trades < self._min_sample:
            return (
                False,
                f"Retain: only {ev.decided_trades}/{self._min_sample} trades - "
                f"insufficient evidence to retire.",
            )
        if ev.net_pnl < 0 and ev.decided_trades >= self._min_sample:
            return (
                True,
                f"Retire: Rs.{ev.net_pnl:,.2f} net over {ev.decided_trades} trades "
                f"with Rs.{ev.charges_paid:,.2f} in charges.",
            )
        return False, f"Retain: Rs.{ev.net_pnl:,.2f} net over {ev.decided_trades} trades."

    def ranked(self) -> list[dict[str, Any]]:
        """Strategies ordered by net P&L, most profitable first."""
        return sorted(
            (ev.as_dict() for ev in self._evidence.values()),
            key=lambda d: d["net_pnl"],
            reverse=True,
        )

    def summary(self) -> dict[str, Any]:
        return {
            "strategies_tracked": len(self._evidence),
            "min_sample_for_verdict": self._min_sample,
            "min_sample_for_graduation": self._min_graduation,
            "prior_win_rate": PRIOR_WIN_RATE,
            "prior_strength": PRIOR_STRENGTH,
            "ranked": self.ranked(),
        }


def _beta_quantile(prob: float, a: float, b: float, *, itmax: int = 200) -> float:
    """Beta quantile by bisection on the CDF. Adequate and robust for reporting."""
    if prob <= 0.0:
        return 0.0
    if prob >= 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(itmax):
        mid = (lo + hi) / 2.0
        if _beta_cdf(mid, a, b) < prob:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


__all__ = [
    "EdgeVerdict",
    "MIN_SAMPLE_FOR_GRADUATION",
    "MIN_SAMPLE_FOR_VERDICT",
    "PRIOR_STRENGTH",
    "PRIOR_WIN_RATE",
    "StrategyEdgeRegistry",
    "StrategyEvidence",
    "probability_win_rate_exceeds",
]
