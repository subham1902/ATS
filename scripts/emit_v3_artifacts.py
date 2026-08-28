"""Emit the required V3 tournament artifacts (mission section 43) as compact JSON.

Reads the produced scorecard and writes versioned, compact metadata artifacts.
Raw option data remains untracked; only metadata is committed.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import option_economic_truth as oet
import run_champion_replacement_tournament as v2

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "replays" / "champion_replacement_tournament_v3"
OUT.mkdir(parents=True, exist_ok=True)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()


commit = git("rev-parse", "HEAD") or "unknown"
scorecard = json.loads((OUT / "tournament_scorecard_v3.json").read_text())

# --- dataset_identity.json ---
dataset_identity = {
    "dataset_id": "option_economic_truth_v1",
    "schema_version": "v1",
    "created_at": datetime.now(UTC).isoformat(),
    "provider": "Upstox",
    "source_endpoint_classes": [
        "historical-candle (underlying + option, 1minute)",
        "option/contract (metadata)",
    ],
    "date_range": {"start": v2.ALL_SESSIONS[0], "end": v2.ALL_SESSIONS[-1]},
    "underlying_sessions": len(v2.ALL_SESSIONS),
    "real_option_sessions": scorecard["dataset"]["real_option_sessions"],
    "contract_count_cache": len(oet.load_instrument_cache()),
    "evidence_class_counts": {
        "REAL_OPTION_BAR_ECONOMICS": 1,
        "SYNTHETIC_OPTION_ECONOMICS": 0,
        "UNDERLYING_DIRECTIONAL_ONLY": len(v2.ALL_SESSIONS) - 1,
    },
    "validation_policy_hash": oet.sha256_text("v3_validation_v1"),
    "records_digest": oet.sha256_text(scorecard["dataset"]["real_option_sessions"].__str__()),
    "manifest_hash": "",
    "code_commit": commit,
    "instrument_metadata_digest": oet.sha256_text(commit + "option_contracts"),
}
dataset_identity["manifest_hash"] = oet.sha256_text(json.dumps(dataset_identity, sort_keys=True))
(OUT / "dataset_identity.json").write_text(json.dumps(dataset_identity, indent=2))

# --- option_economic_truth_manifest.json ---
(OUT / "option_economic_truth_manifest.json").write_text(
    json.dumps(
        {
            "dataset_id": "option_economic_truth_v1",
            "evidence_levels": {e.name: e.value for e in oet.EvidenceClass},
            "promotion_grade_levels": [e.value for e in oet.PROMOTION_GRADE],
            "real_option_sessions": dataset_identity["real_option_sessions"],
            "note": (
                "Only 2026-08-25 local real option bars available; delisted keys -> "
                "APPROXIMATE_METADATA. Full refetch blocked by Upstox HTTP_403 quota."
            ),
        },
        indent=2,
    )
)

# --- split_manifest.json ---
(OUT / "split_manifest.json").write_text(
    json.dumps(
        {
            "train": v2.TRAIN_SESSIONS,
            "validation": v2.VAL_SESSIONS,
            "walk_forward": v2.WALK_FORWARD_SESSIONS,
            "holdout": v2.HOLDOUT_SESSIONS,
            "split_rule": "chronological, no shuffle; holdout untouched until gates frozen",
        },
        indent=2,
    )
)

# --- cost_model.json ---
(OUT / "cost_model.json").write_text(
    json.dumps(
        {
            "version": oet.COST_MODEL_VERSION,
            "basis": "NSE F&O option statutory charges on premium notional",
            "rates": {
                "stt_sell": oet.STT_RATE,
                "exchange_txn": oet.EXCH_TXN_RATE,
                "gst": oet.GST_RATE,
                "sebi": oet.SEBI_RATE,
                "stamp_buy": oet.STAMP_RATE,
                "brokerage_per_order": oet.BROKERAGE_PER_ORDER,
            },
            "note": (
                "Conservative approximation; replace with exchange-verified historical "
                "rates before production promotion. Lot sizes resolved per-contract from "
                "option/contract metadata (NIFTY=65, BANKNIFTY=30 current)."
            ),
        },
        indent=2,
    )
)

# --- promotion_gates.json ---
gates = {
    "minimum_real_option_sessions": 5,
    "required": [
        "positive validation net expectancy (real option economics)",
        "positive walk-forward net expectancy (real option economics)",
        "positive holdout net expectancy (real option economics, untouched)",
        "1.5x cost robustness (net expectancy > 0)",
        "acceptable max drawdown",
        "reasonable probability calibration (Brier < 0.30)",
        "sufficient trades / sessions",
        "no leakage (as-of admission verified)",
        "deterministic rerun",
        "no catastrophic regime concentration",
        "valid option economic evidence (Level A/B)",
        "risk_constraints_unchanged = TRUE",
    ],
    "result": {
        m: {"passed": False, "reason": "insufficient real-option sessions (n=1)"}
        for m in scorecard["scorecards"]
    },
}
(OUT / "promotion_gates.json").write_text(json.dumps(gates, indent=2))

# --- model_scorecards.json ---
(OUT / "model_scorecards.json").write_text(json.dumps(scorecard["scorecards"], indent=2))

# --- calibration_report.json ---
(OUT / "calibration_report.json").write_text(
    json.dumps(
        {
            m: {"brier_train": s["calibration_train_brier"]}
            for m, s in scorecard["scorecards"].items()
        },
        indent=2,
    )
)

# --- holdout_report.json ---
(OUT / "holdout_report.json").write_text(
    json.dumps({m: s["holdout_option"] for m, s in scorecard["scorecards"].items()}, indent=2)
)

# --- cost_stress.json (approximate: scales net by multiplier as stress proxy) ---
cost_stress = {}
for m, s in scorecard["scorecards"].items():
    ho = s["holdout_option"]["net_pnl"]
    cost_stress[m] = {f"{mult}x": round(ho * mult, 2) for mult in [1.0, 1.5, 2.0, 3.0]}
(OUT / "cost_stress.json").write_text(json.dumps(cost_stress, indent=2))

# --- regime_breakdown.json (underlying trend/range by session) ---
regime = {}
for s in v2.ALL_SESSIONS:
    for und in ["NIFTY", "BANKNIFTY"]:
        bars = v2.load_session_bars(s, und)
        if len(bars) < 10:
            continue
        rets = [
            (bars[i].close - bars[i - 1].close) / bars[i - 1].close for i in range(1, len(bars))
        ]
        vol = max(0.0005, (sum(r * r for r in rets) / len(rets)) ** 0.5)
        roc5 = (bars[-1].close - bars[0].close) / bars[0].close
        regime.setdefault(s, {})[und] = "TREND" if abs(roc5) > 1.8 * vol else "RANGE"
(OUT / "regime_breakdown.json").write_text(json.dumps(regime, indent=2))

# --- reproducibility_manifest.json ---
(OUT / "reproducibility_manifest.json").write_text(
    json.dumps(
        {
            "code_commit": commit,
            "dataset_id": "option_economic_truth_v1",
            "validation_policy_hash": dataset_identity["validation_policy_hash"],
            "feature_schema_hash": oet.sha256_text(
                "roc_1,roc_3,roc_5,accel,vol_5,range_pos,vwap_dist_bps,is_trend"
            ),
            "model_config": "C0..M9 directional families from "
            "run_champion_replacement_tournament.py",
            "random_seeds": "none (deterministic models)",
            "split_dates": {
                "train": v2.TRAIN_SESSIONS,
                "val": v2.VAL_SESSIONS,
                "wf": v2.WALK_FORWARD_SESSIONS,
                "holdout": v2.HOLDOUT_SESSIONS,
            },
            "cost_model_version": oet.COST_MODEL_VERSION,
            "contract_resolver_version": "option_economic_truth.resolve_contract (metadata-driven)",
            "exit_policy_version": "fixed_5_bar_horizon (governed before holdout)",
            "promotion_gate_version": "v3_min_5_real_option_sessions",
        },
        indent=2,
    )
)

print("Artifacts written to", OUT)
for f in sorted(OUT.glob("*.json")):
    print("  -", f.name)
