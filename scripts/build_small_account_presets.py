"""Build evidence-linked observer presets. Does not activate broker execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ats.strategies.small_account_presets import SmallAccountPreset

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--broker-symbol", default="XAUUSD")
    options = parser.parse_args()
    source = ROOT / "reports/small-account-research/deployment-verification"
    evidence = json.loads((source / "selected.json").read_text())
    quality = json.loads((source / "quality.json").read_text())
    presets = []
    native = ROOT / "metatrader/Experts/ATSSmallAccount/presets"
    native.mkdir(parents=True, exist_ok=True)
    for result in evidence:
        strategy = result["strategy"]
        cfg = result["cfg"]
        if result["account"] != 1000 or result["status"] != "HISTORICAL_FORWARD_CANDIDATE":
            raise ValueError("NOT_A_SELECTED_1000_USD_RESEARCH_CANDIDATE")
        preset = SmallAccountPreset(
            preset_id=f"gold-triple-{strategy.lower()}-1000-v3",
            strategy_id="XAU-020" if strategy == "S3" else "XAU-019",
            strategy_version=1,
            research_initial_capital="1000",
            direction="LONG" if strategy == "S3" else "BOTH",
            structural_lookback=cfg["lookback"],
            risk_fraction=str(cfg["risk"]),
            target_r=str(cfg["rr"]),
            profit_protection=cfg["protect"],
            maximum_hold_minutes=cfg["hold"],
            weekdays_utc=(1, 2, 3) if strategy == "S3" else (0, 1, 2, 3, 4),
            parent_retest_level="H4_CLOSE" if strategy == "S3" else "M15_CLOSE",
            volume_provenance="NOT_REQUIRED" if strategy == "S3" else "UNKNOWN_SOURCE_VOLUME",
            dataset_bid_hash=quality["hashes"]["bid"],
            dataset_ask_hash=quality["hashes"]["ask"],
            selection_hash=quality["selection_hash"],
            grid_verification_hash=digest(source / "selected.json"),
        )
        presets.append(preset.model_dump(mode="json"))
        inputs = preset.native_inputs(options.account_id, options.broker_symbol)
        # Deployment is always proposal-only. The blank historical clock profile
        # is intentional: a present-time clock cannot certify past broker bars.
        (native / f"{preset.preset_id}.set").write_text(
            "; ATS V3 research observer preset; execution authority NONE\n"
            + "\n".join(f"{key}={value}" for key, value in inputs.items())
            + "\n",
            encoding="utf-8",
        )
        (native / f"{preset.preset_id}.json").write_text(
            preset.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
    target = ROOT / "docs/research/presets/gold-triple-small-account-v3.json"
    target.write_text(
        json.dumps(
            {
                "version": "GOLD-TRIPLE-SMALL-ACCOUNT-V3",
                "status": "RESEARCH_SETTINGS_IMPLEMENTED_EXECUTION_NOT_COMMISSIONED",
                "supersedes": "gold-triple-small-account-v2.json",
                "probability": None,
                "deployment_authority": "NONE",
                "unqualified": ["500_USD", "750_USD", "S1", "COMBINED_PORTFOLIO"],
                "presets": presets,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "presets": len(presets),
                "bundle_hash": digest(target),
                "output": str(target),
                "execution_enabled": False,
            }
        )
    )


if __name__ == "__main__":
    main()
