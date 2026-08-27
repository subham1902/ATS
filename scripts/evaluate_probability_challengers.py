"""Statistical evaluation of Champion vs Challenger probability models."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

CALIBRATION_STORE_PATH = Path(r"D:\Projects\ATS\ats\data\historical\calibration_store_v1.json")


def evaluate_challenger_models() -> list[dict[str, Any]]:
    data = json.loads(CALIBRATION_STORE_PATH.read_text(encoding="utf-8"))
    records = []
    for d in data:
        y = 1 if d["outcome_occurred"] else 0
        ret = float(d["realized_return_fraction"])
        vol = max(0.0001, float(d["realized_volatility_fraction"]))
        p_champ = float(d["forecast_probability"])
        roc = (p_champ - 0.50) / 5.0
        records.append({"y": y, "ret": ret, "vol": vol, "roc": roc, "p_champ": p_champ})

    n = len(records)
    models = [
        ("Champion (Linear 5.0)", lambda r: 0.50 + r["roc"] * 5.0),
        ("Challenger A1 (Linear 10.0)", lambda r: 0.50 + r["roc"] * 10.0),
        ("Challenger A2 (Linear 15.0)", lambda r: 0.50 + r["roc"] * 15.0),
        ("Challenger A3 (Linear 20.0)", lambda r: 0.50 + r["roc"] * 20.0),
        (
            "Challenger B1 (Vol-Norm Logistic)",
            lambda r: 1.0 / (1.0 + math.exp(-(r["roc"] / r["vol"]) * 1.5)),
        ),
        (
            "Challenger B2 (Vol-Norm Tanh)",
            lambda r: 0.50 + 0.50 * math.tanh((r["roc"] / r["vol"]) * 0.8),
        ),
    ]

    results = []
    for name, fn in models:
        brier = 0.0
        log_loss = 0.0
        probs = []
        correct_dir = 0
        for r in records:
            p = min(0.9999, max(0.0001, fn(r)))
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
        c_55 = sum(1 for x in probs if x >= 0.55)

        results.append(
            {
                "model": name,
                "brier": round(brier, 4),
                "log_loss": round(log_loss, 4),
                "accuracy": f"{acc:.2%}",
                "std": round(std_p, 4),
                "min": round(min(probs), 4),
                "max": round(max(probs), 4),
                "count_ge_055": c_55,
                "promotion_status": "HOLD_AS_CHALLENGER"
                if "Challenger" in name
                else "CHAMPION_ACTIVE",
            }
        )

    return results


def main() -> None:
    res = evaluate_challenger_models()
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
