"""Build empirical calibration store from prior completed NSE sessions."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from ats.contracts.domain import MarketSnapshot
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.domain.types import DataQualityState, SessionState
from ats.intelligence.calibration.models import CalibrationObservation
from ats.market.features.engine import compute_feature_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(
    os.environ.get(
        "ATS_SESSION_DATA_ROOT",
        str(REPO_ROOT / "data" / "raw" / "upstox" / "sessions"),
    )
)
CALIBRATION_STORE_PATH = Path(
    os.environ.get(
        "ATS_CHAMPION_CALIBRATION_STORE",
        str(REPO_ROOT / "data" / "historical" / "calibration_store_v1.json"),
    )
)

PRIOR_SESSIONS = [
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
]

CandleTuple = tuple[datetime, Decimal, Decimal, Decimal, Decimal, Decimal]


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _load_session_candles(session_date: str, instrument: str) -> list[CandleTuple]:
    filename = f"{instrument}_underlying.json"
    file_path = DATA_ROOT / session_date / filename
    data = json.loads(file_path.read_text(encoding="utf-8"))
    candles_raw = data.get("data", {}).get("candles", [])
    parsed: list[CandleTuple] = []
    for row in reversed(candles_raw):
        t = _parse_ts(row[0])
        op = Decimal(str(row[1]))
        hi = Decimal(str(row[2]))
        lo = Decimal(str(row[3]))
        cl = Decimal(str(row[4]))
        vol = Decimal(str(row[5]))
        parsed.append((t, op, hi, lo, cl, vol))
    return parsed


def _build_5m_snapshots_for_session(session_date: str, instrument_id: str) -> list[MarketSnapshot]:
    candles_1m = _load_session_candles(session_date, instrument_id)
    snapshots: list[MarketSnapshot] = []
    current_5m: list[CandleTuple] = []

    for c in candles_1m:
        t = c[0]
        current_5m.append(c)
        if (t.minute + 1) % 5 == 0:
            bar_close_ts = t + timedelta(minutes=1)
            bar_close_ts = bar_close_ts.replace(second=0, microsecond=0)
            op = current_5m[0][1]
            hi = max(x[2] for x in current_5m)
            lo = min(x[3] for x in current_5m)
            cl = current_5m[-1][4]
            vol = sum(x[5] for x in current_5m)
            seq = len(snapshots) + 1
            snap = MarketSnapshot(
                schema_version="1.0",
                snapshot_id=uuid4(),
                instrument_id=instrument_id,
                exchange="NSE",
                segment="CASH",
                timeframe="5m",
                sequence=seq,
                bar_timestamp=bar_close_ts,
                received_at=bar_close_ts + timedelta(seconds=2),
                open=op,
                high=hi,
                low=lo,
                close=cl,
                volume=vol,
                quality_state=DataQualityState.GOOD,
                quality_flags=(),
                source="UPSTOX_V3",
                source_version="1.0.0",
                session_state=SessionState.OPEN,
                payload_hash="0" * 64,
            )
            snapshots.append(snap.model_copy(update={"payload_hash": compute_payload_hash(snap)}))
            current_5m = []
    return snapshots


def build_real_calibration_history() -> list[CalibrationObservation]:
    observations: list[CalibrationObservation] = []

    for session_date in PRIOR_SESSIONS:
        for und in ["NIFTY", "BANKNIFTY"]:
            snaps = _build_5m_snapshots_for_session(session_date, und)
            for i in range(4, len(snaps) - 3):
                visible_snaps = tuple(snaps[: i + 1])
                bundle = compute_feature_bundle(visible_snaps, cutoff_sequence=len(visible_snaps))

                roc = bundle.features.get("roc_3_fraction", 0.0)
                prob_up = Decimal(str(round(min(0.95, max(0.05, 0.50 + roc * 5.0)), 4)))

                entry_close = snaps[i].close
                exit_close = snaps[i + 3].close
                realized_return = (exit_close - entry_close) / entry_close
                outcome_occurred = bool(realized_return > 0)

                horizon_bars = snaps[i + 1 : i + 4]
                highs = [b.high for b in horizon_bars]
                lows = [b.low for b in horizon_bars]
                mfe = (max(highs) - entry_close) / entry_close
                mae = (min(lows) - entry_close) / entry_close
                vol = (max(highs) - min(lows)) / entry_close

                obs_time = snaps[i + 3].bar_timestamp + timedelta(seconds=2)
                avail_time = obs_time + timedelta(seconds=1)

                cal_obs = CalibrationObservation(
                    observation_id=uuid4(),
                    forecast_probability=prob_up,
                    outcome_occurred=outcome_occurred,
                    observed_at=obs_time,
                    available_to_strategy_time=avail_time,
                    regime_evidence_id=None,
                    realized_return_fraction=float(realized_return),
                    realized_volatility_fraction=float(vol),
                    realized_mfe_fraction=float(mfe),
                    realized_mae_fraction=float(mae),
                )
                observations.append(cal_obs)

    observations.sort(key=lambda o: (o.available_to_strategy_time, o.observation_id))
    return observations


def main() -> None:
    print(f"Building real calibration history from {len(PRIOR_SESSIONS)} completed sessions...")
    obs = build_real_calibration_history()
    print(f"Generated {len(obs)} genuine CalibrationObservation records.")

    CALIBRATION_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    serialized = [o.model_dump(mode="json") for o in obs]
    CALIBRATION_STORE_PATH.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
    print(f"Persisted to {CALIBRATION_STORE_PATH}")


if __name__ == "__main__":
    main()
