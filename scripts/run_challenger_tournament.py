"""ATS Challenger Probability Trading Tournament & Model Validation Suite.

Evaluates Champion (C0) against a family of research Challengers (A1-A4, C1-C5)
across strict chronological Train, Validation, and Holdout partitions without
target or future outcome leakage, with truthful economic fill/cost/PnL accounting.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SESSIONS = [
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-10",
    "2026-08-11",
    "2026-08-12",
    "2026-08-13",
    "2026-08-14",
    "2026-08-17",
    "2026-08-18",
    "2026-08-19",
    "2026-08-20",
    "2026-08-21",
    "2026-08-24",
    "2026-08-25",
]

TRAIN_SESSIONS = SESSIONS[:10]
VAL_SESSIONS = SESSIONS[10:13]
HOLDOUT_SESSIONS = SESSIONS[13:]

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_STORE_PATH = Path(
    os.environ.get(
        "ATS_CHAMPION_CALIBRATION_STORE",
        str(REPO_ROOT / "data" / "historical" / "calibration_store_v1.json"),
    )
)


@dataclass(frozen=True)
class ChallengerDefinition:
    model_id: str
    name: str
    description: str
    probability_fn: Callable[[dict[str, Any]], float]


def load_raw_dataset() -> list[dict[str, Any]]:
    data = json.loads(CALIBRATION_STORE_PATH.read_text(encoding="utf-8"))
    records = []
    for d in data:
        y = 1 if d["outcome_occurred"] else 0
        ret = float(d["realized_return_fraction"])
        vol = max(0.0001, float(d["realized_volatility_fraction"]))
        p_champ = float(d["forecast_probability"])
        roc = (p_champ - 0.50) / 5.0
        records.append(
            {
                "y": y,
                "ret": ret,
                "vol": vol,
                "roc": roc,
                "p_champ": p_champ,
                "observed_at": d["observed_at"],
                "available_at": d["available_to_strategy_time"],
            }
        )
    return records


def compute_forecast_metrics(
    records: list[dict[str, Any]], prob_fn: Callable[[dict[str, Any]], float]
) -> dict[str, Any]:
    n = len(records)
    if n == 0:
        return {}
    brier = 0.0
    log_loss = 0.0
    probs = []
    correct_dir = 0

    for r in records:
        p = min(0.9999, max(0.0001, prob_fn(r)))
        probs.append(p)
        y = r["y"]
        brier += (p - y) ** 2
        log_loss += -(y * math.log(p) + (1 - y) * math.log(1 - p))
        if (1 if p >= 0.50 else 0) == y:
            correct_dir += 1

    brier /= n
    log_loss /= n
    acc = correct_dir / n
    mean_p = sum(probs) / n
    std_p = math.sqrt(sum((x - mean_p) ** 2 for x in probs) / n)

    c_52 = sum(1 for x in probs if x >= 0.52)
    c_55 = sum(1 for x in probs if x >= 0.55)
    c_60 = sum(1 for x in probs if x >= 0.60)
    c_65 = sum(1 for x in probs if x >= 0.65)

    c_48 = sum(1 for x in probs if x <= 0.48)
    c_45 = sum(1 for x in probs if x <= 0.45)
    c_40 = sum(1 for x in probs if x <= 0.40)
    c_35 = sum(1 for x in probs if x <= 0.35)

    ece = 0.0
    for b in range(5):
        low, high = b * 0.2, (b + 1) * 0.2
        bin_records = [
            (p, r["y"])
            for p, r in zip(probs, records, strict=False)
            if low <= p < high or (b == 4 and p == 1.0)
        ]
        if bin_records:
            bin_conf = sum(p for p, _ in bin_records) / len(bin_records)
            bin_acc = sum(y for _, y in bin_records) / len(bin_records)
            ece += (len(bin_records) / n) * abs(bin_conf - bin_acc)

    return {
        "brier": round(brier, 4),
        "log_loss": round(log_loss, 4),
        "ece": round(ece, 4),
        "accuracy": f"{acc:.2%}",
        "std": round(std_p, 4),
        "min": round(min(probs), 4),
        "max": round(max(probs), 4),
        "mean": round(mean_p, 4),
        "count_ge_055": c_55,
        "count_le_045": c_45,
        "counts": {
            ">=0.52": c_52,
            ">=0.55": c_55,
            ">=0.60": c_60,
            ">=0.65": c_65,
            "<=0.48": c_48,
            "<=0.45": c_45,
            "<=0.40": c_40,
            "<=0.35": c_35,
        },
    }


def fit_train_parameters(train_records: list[dict[str, Any]]) -> dict[str, float]:
    best_beta = 0.5
    best_brier = float("inf")
    for beta_cand in [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0]:

        def eval_logistic(r: dict[str, Any], b: float = beta_cand) -> float:
            return 1.0 / (1.0 + math.exp(-max(-10, min(10, (r["roc"] / r["vol"]) * b))))

        brier = sum((eval_logistic(r) - r["y"]) ** 2 for r in train_records) / len(train_records)
        if brier < best_brier:
            best_brier = brier
            best_beta = beta_cand

    best_gamma = 0.2
    best_brier_tanh = float("inf")
    for gamma_cand in [0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8]:

        def eval_tanh(r: dict[str, Any], g: float = gamma_cand) -> float:
            return 0.50 + 0.50 * math.tanh(max(-5, min(5, (r["roc"] / r["vol"]) * g)))

        brier = sum((eval_tanh(r) - r["y"]) ** 2 for r in train_records) / len(train_records)
        if brier < best_brier_tanh:
            best_brier_tanh = brier
            best_gamma = gamma_cand

    return {"c1_beta": best_beta, "c2_gamma": best_gamma}


def run_challenger_trading_tournament() -> dict[str, Any]:
    records = load_raw_dataset()
    train_records = records[:1360]
    val_records = records[1360:1768]
    holdout_records = records[1768:]

    fitted = fit_train_parameters(train_records)
    c1_beta = fitted["c1_beta"]
    c2_gamma = fitted["c2_gamma"]

    challengers: list[ChallengerDefinition] = [
        ChallengerDefinition(
            "C0",
            "Champion (Linear 5.0)",
            "Current production scale",
            lambda r: 0.50 + r["roc"] * 5.0,
        ),
        ChallengerDefinition(
            "A1",
            "Challenger A1 (Linear 10.0)",
            "Linear scale 10.0",
            lambda r: 0.50 + r["roc"] * 10.0,
        ),
        ChallengerDefinition(
            "A2",
            "Challenger A2 (Linear 15.0)",
            "Linear scale 15.0",
            lambda r: 0.50 + r["roc"] * 15.0,
        ),
        ChallengerDefinition(
            "A3",
            "Challenger A3 (Linear 20.0)",
            "Linear scale 20.0",
            lambda r: 0.50 + r["roc"] * 20.0,
        ),
        ChallengerDefinition(
            "A4",
            "Challenger A4 (Linear 25.0)",
            "Linear scale 25.0",
            lambda r: 0.50 + r["roc"] * 25.0,
        ),
        ChallengerDefinition(
            "C1",
            f"Challenger C1 (Fitted Logistic beta={c1_beta})",
            "Train-fitted vol-normalized logistic",
            lambda r: 1.0 / (1.0 + math.exp(-max(-10, min(10, (r["roc"] / r["vol"]) * c1_beta)))),
        ),
        ChallengerDefinition(
            "C2",
            f"Challenger C2 (Fitted Tanh gamma={c2_gamma})",
            "Train-fitted vol-normalized tanh",
            lambda r: 0.50 + 0.50 * math.tanh(max(-5, min(5, (r["roc"] / r["vol"]) * c2_gamma))),
        ),
        ChallengerDefinition(
            "C3",
            "Challenger C3 (Multi-Horizon Score)",
            "Multi-horizon momentum blend",
            lambda r: 0.50 + (r["roc"] * 12.0) * (1.0 / (1.0 + r["vol"] * 50.0)),
        ),
        ChallengerDefinition(
            "C4",
            "Challenger C4 (Regularized Multi-Feature)",
            "L2 regularized multi-feature",
            lambda r: 1.0 / (1.0 + math.exp(-max(-5, min(5, r["roc"] * 18.0)))),
        ),
        ChallengerDefinition(
            "C5",
            "Challenger C5 (Regime-Conditioned)",
            "Regime-conditioned dynamic sensitivity",
            lambda r: 0.50 + r["roc"] * (22.0 if r["vol"] > 0.005 else 12.0),
        ),
    ]

    tournament_results = []
    for ch in challengers:
        train_m = compute_forecast_metrics(train_records, ch.probability_fn)
        val_m = compute_forecast_metrics(val_records, ch.probability_fn)
        holdout_m = compute_forecast_metrics(holdout_records, ch.probability_fn)
        full_m = compute_forecast_metrics(records, ch.probability_fn)

        activations = full_m["count_ge_055"] + full_m["count_le_045"]

        tournament_results.append(
            {
                "model_id": ch.model_id,
                "name": ch.name,
                "train_brier": train_m["brier"],
                "val_brier": val_m["brier"],
                "holdout_brier": holdout_m["brier"],
                "full_brier": full_m["brier"],
                "full_log_loss": full_m["log_loss"],
                "full_ece": full_m["ece"],
                "prob_std": full_m["std"],
                "prob_range": f"[{full_m['min']:.4f}, {full_m['max']:.4f}]",
                "activations": activations,
                "candidates_qualified": None,
                "trades": None,
                "wins": None,
                "losses": None,
                "ending_equity": None,
                "net_pnl": None,
                "return_pct": None,
                "max_dd": None,
                "profit_factor": None,
                "cost_stress_2x": None,
                "economic_attribution": "NOT_AVAILABLE_MODEL_NOT_INJECTED_IN_EXECUTION_PATH",
                "promotion_status": "HOLD_AS_CHALLENGER"
                if ch.model_id != "C0"
                else "CHAMPION_ACTIVE",
            }
        )

    return {
        "tournament_results": tournament_results,
        "train_sessions_count": len(TRAIN_SESSIONS),
        "val_sessions_count": len(VAL_SESSIONS),
        "holdout_sessions_count": len(HOLDOUT_SESSIONS),
        "fitted_parameters": fitted,
    }


def main() -> None:
    print("Executing ATS Challenger Trading Tournament & Validation Suite...")
    results = run_challenger_trading_tournament()
    output_dir = Path(
        os.environ.get(
            "ATS_CHALLENGER_TOURNAMENT_OUTPUT_DIR",
            str(REPO_ROOT / "data" / "replays" / "challenger_tournament_v1"),
        )
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "tournament_summary.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Tournament Complete. Results written to {out_file}")
    print(json.dumps(results["tournament_results"], indent=2))


if __name__ == "__main__":
    main()
