"""Anti-overfit evidence: lineage, PSR, DSR, PBO/CSCV/CPCV interfaces.

When sample requirements are not met, returns UNKNOWN/INSUFFICIENT_EVIDENCE
rather than fabricating a metric.
"""

from __future__ import annotations

import math
from uuid import UUID, uuid4

from ats.contracts.common import UTCDateTime

from .types import ExperimentLineage, OverfitEvidence

MIN_TRADES_FOR_PSR = 30
MIN_TRIALS_FOR_DSR = 5
MIN_FOLDS_FOR_PBO = 4


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def probabilistic_sharpe_ratio(
    sharpe: float,
    n: int,
    benchmark_sharpe: float = 0.0,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float | str:
    if n < MIN_TRADES_FOR_PSR:
        return "INSUFFICIENT_EVIDENCE"
    if not all(math.isfinite(v) for v in (sharpe, benchmark_sharpe, skewness, kurtosis)):
        return "UNKNOWN"
    if n <= 1:
        return "INSUFFICIENT_EVIDENCE"
    try:
        sr_diff = sharpe - benchmark_sharpe
        var_term = (1 - skewness * sharpe + (kurtosis - 1) / 4 * sharpe * sharpe) / (n - 1)
        if var_term <= 0:
            return "UNKNOWN"
        z = sr_diff / math.sqrt(var_term)
        psr = _norm_cdf(z)
        if not math.isfinite(psr) or not 0 <= psr <= 1:
            return "UNKNOWN"
        return float(psr)
    except Exception:
        return "UNKNOWN"


def expected_max_sharpe(n_trials: int, n_obs: int) -> float | str:
    if n_trials < MIN_TRIALS_FOR_DSR or n_obs < MIN_TRADES_FOR_PSR:
        return "INSUFFICIENT_EVIDENCE"
    try:
        euler_gamma = 0.5772156649
        log_k = math.log(n_trials)
        z_max = math.sqrt(2 * log_k) + (euler_gamma / math.sqrt(2 * log_k))
        sigma_sr = 1.0 / math.sqrt(n_obs - 1)
        val = z_max * sigma_sr
        if not math.isfinite(val):
            return "UNKNOWN"
        return float(val)
    except Exception:
        return "UNKNOWN"


def deflated_sharpe_ratio(
    sharpe: float,
    n: int,
    n_trials: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> float | str:
    emax = expected_max_sharpe(n_trials, n)
    if isinstance(emax, str):
        return emax
    assert isinstance(emax, float)
    return probabilistic_sharpe_ratio(
        sharpe, n, benchmark_sharpe=emax, skewness=skewness, kurtosis=kurtosis
    )


def pbo_evidence(
    is_returns: list[float],
    oos_returns: list[float],
) -> float | str:
    if len(is_returns) < MIN_FOLDS_FOR_PBO or len(oos_returns) < MIN_FOLDS_FOR_PBO:
        return "INSUFFICIENT_EVIDENCE"
    if len(is_returns) != len(oos_returns):
        return "UNKNOWN"
    try:
        degraded = sum(1 for a, b in zip(is_returns, oos_returns, strict=False) if b < a)
        pbo = degraded / len(is_returns)
        if not math.isfinite(pbo):
            return "UNKNOWN"
        return float(pbo)
    except Exception:
        return "UNKNOWN"


def cscv_evidence(fold_sharpes: list[float]) -> float | str:
    if len(fold_sharpes) < MIN_FOLDS_FOR_PBO:
        return "INSUFFICIENT_EVIDENCE"
    try:
        vals = [v for v in fold_sharpes if math.isfinite(v)]
        if len(vals) < MIN_FOLDS_FOR_PBO:
            return "INSUFFICIENT_EVIDENCE"
        mean = sum(vals) / len(vals)
        if not math.isfinite(mean):
            return "UNKNOWN"
        return float(mean)
    except Exception:
        return "UNKNOWN"


def build_lineage(
    *,
    strategy_definition_id: UUID,
    strategy_definition_version: int,
    parent_strategy_ref: tuple[UUID, int] | None,
    origin: str,
    dataset_manifest_id: UUID,
    dataset_version: str,
    trial_count: int,
    parameter_search_count: int,
    seed: int,
    cost_model_version: str,
    created_at: UTCDateTime,
) -> ExperimentLineage:
    return ExperimentLineage(
        lineage_id=uuid4(),
        strategy_definition_id=strategy_definition_id,
        strategy_definition_version=strategy_definition_version,
        parent_strategy_ref=parent_strategy_ref,
        origin=origin,
        dataset_manifest_id=dataset_manifest_id,
        dataset_version=dataset_version,
        trial_count=trial_count,
        parameter_search_count=parameter_search_count,
        seed=seed,
        cost_model_version=cost_model_version,
        created_at=created_at,
    )


def build_overfit_evidence(
    *,
    strategy_definition_id: UUID,
    experiment_ids: tuple[UUID, ...],
    sample_count: int,
    trial_count: int,
    sharpe: float | None,
    n_trials: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    pbo_is: list[float] | None = None,
    pbo_oos: list[float] | None = None,
    cscv_folds: list[float] | None = None,
    created_at: UTCDateTime,
) -> OverfitEvidence:
    reasons: list[str] = []
    if sample_count < MIN_TRADES_FOR_PSR:
        reasons.append("INSUFFICIENT_SAMPLES_FOR_PSR")
    if n_trials < MIN_TRIALS_FOR_DSR:
        reasons.append("INSUFFICIENT_TRIALS_FOR_DSR")

    if sharpe is not None and math.isfinite(sharpe):
        psr_val = probabilistic_sharpe_ratio(
            sharpe, sample_count, skewness=skewness, kurtosis=kurtosis
        )
        dsr_val = deflated_sharpe_ratio(
            sharpe, sample_count, n_trials, skewness=skewness, kurtosis=kurtosis
        )
        emax = expected_max_sharpe(n_trials, sample_count)
    else:
        psr_val = "UNKNOWN"
        dsr_val = "UNKNOWN"
        emax = "UNKNOWN"
        reasons.append("SHARPE_UNKNOWN")

    if pbo_is is not None and pbo_oos is not None:
        pbo_val = pbo_evidence(pbo_is, pbo_oos)
        pbo_method = "PBO"
    else:
        pbo_val = "INSUFFICIENT_EVIDENCE"
        pbo_method = None
        if pbo_is is None:
            reasons.append("PBO_REQUIRES_IS_OOS_RETURNS")

    if cscv_folds is not None:
        cscv_val = cscv_evidence(cscv_folds)
    else:
        cscv_val = "INSUFFICIENT_EVIDENCE"
        reasons.append("CSCV_REQUIRES_FOLD_SHARPES")

    cpcv_label = None
    if sample_count >= MIN_TRADES_FOR_PSR and n_trials >= MIN_TRIALS_FOR_DSR:
        cpcv_label = "CPCV_AVAILABLE_VIA_WALK_FORWARD"
    else:
        cpcv_label = "CPCV_INSUFFICIENT_EVIDENCE"

    psr_bm = 0.0 if isinstance(psr_val, float) else None
    emax_f = emax if isinstance(emax, float) else None
    cscv_f = cscv_val if isinstance(cscv_val, float) else None

    return OverfitEvidence(
        evidence_id=uuid4(),
        strategy_definition_id=strategy_definition_id,
        experiment_ids=experiment_ids,
        sample_count=sample_count,
        trial_count=trial_count,
        psr=psr_val,  # type: ignore[arg-type]
        psr_benchmark_sharpe=psr_bm,
        dsr=dsr_val,  # type: ignore[arg-type]
        dsr_expected_max_sharpe=emax_f,
        pbo=pbo_val,  # type: ignore[arg-type]
        pbo_method=pbo_method,
        cscv_mean_sharpe=cscv_f,
        cpcv_evidence=cpcv_label,
        reason_codes=tuple(reasons),
        created_at=created_at,
    )


__all__ = [
    "build_lineage",
    "build_overfit_evidence",
    "cscv_evidence",
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "pbo_evidence",
    "probabilistic_sharpe_ratio",
]
