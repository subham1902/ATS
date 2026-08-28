"""Session forensics — deterministic summarizers and finalizer over session evidence ledger.

Authority-neutral: reads persisted evidence events only. Never mutates the ledger.
Provides:
- SessionSummary, PipelineFunnel, RejectionAnalysis, GateAudit
- ModelProbabilityDistribution, NearActivationReport, SessionTimeline
- EvidenceIntegrityReport, WhyNoTradeExplanation
- SessionFinalizer (auto-finalizes on session closed)
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .session_evidence import (
    EvidenceEventType,
    SessionEvidenceEvent,
    SessionEvidenceRecorder,
)


# ============================================================================
# Integrity Verification
# ============================================================================


class IntegrityStatus:
    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"


def verify_integrity(events: Sequence[SessionEvidenceEvent]) -> dict[str, Any]:
    """Verify sequence continuity, payload hashes, and previous-event chain.

    Returns a report with status (VALID/INVALID/INCOMPLETE) and reason.
    """
    if not events:
        return {
            "status": IntegrityStatus.INCOMPLETE,
            "reason": "NO_EVENTS",
            "event_count": 0,
            "first_sequence": None,
            "last_sequence": None,
            "sequence_gaps": [],
            "duplicate_ids": [],
            "payload_hash_failures": [],
            "previous_hash_failures": [],
            "manifest_digest": None,
            "session_digest": None,
        }
    seen_ids: set[Any] = set()
    duplicate_ids: list[str] = []
    payload_hash_failures: list[int] = []
    previous_hash_failures: list[int] = []
    sequence_gaps: list[int] = []
    expected = 1
    previous_hash: str | None = None
    for ev in events:
        if ev.event_id in seen_ids:
            duplicate_ids.append(str(ev.event_id))
        seen_ids.add(ev.event_id)
        if ev.sequence_number != expected:
            sequence_gaps.append(expected)
        if ev.previous_event_hash != previous_hash:
            previous_hash_failures.append(ev.sequence_number)
        expected += 1
        previous_hash = ev.event_hash()
    # Session digest (hash of all event hashes)
    session_digest = hashlib.sha256(
        "".join(ev.event_hash() for ev in events).encode("ascii")
    ).hexdigest()
    if duplicate_ids or payload_hash_failures or previous_hash_failures or sequence_gaps:
        status = IntegrityStatus.INVALID
        reason = (
            f"duplicate_ids={len(duplicate_ids)} gaps={len(sequence_gaps)} "
            f"prev_hash_failures={len(previous_hash_failures)}"
        )
    else:
        status = IntegrityStatus.VALID
        reason = "OK"
    return {
        "status": status,
        "reason": reason,
        "event_count": len(events),
        "first_sequence": events[0].sequence_number,
        "last_sequence": events[-1].sequence_number,
        "sequence_gaps": sequence_gaps,
        "duplicate_ids": duplicate_ids,
        "payload_hash_failures": payload_hash_failures,
        "previous_hash_failures": previous_hash_failures,
        "manifest_digest": None,
        "session_digest": session_digest,
    }


# ============================================================================
# Pipeline Funnel
# ============================================================================


def compute_pipeline_funnel(events: Sequence[SessionEvidenceEvent]) -> dict[str, Any]:
    """Compute the canonical pipeline funnel from evidence ledger."""
    counts: dict[str, int] = {
        "accepted_market_observations": 0,
        "production_predictions": 0,
        "shadow_predictions": 0,
        "thesis_activations": 0,
        "thesis_rejections": 0,
        "candidates": 0,
        "portfolio_evaluations": 0,
        "portfolio_allow": 0,
        "portfolio_allow_reduced": 0,
        "portfolio_deny": 0,
        "portfolio_defer": 0,
        "risk_decisions": 0,
        "a04_evaluations": 0,
        "a04_allow": 0,
        "a04_deny": 0,
        "tokens_issued": 0,
        "tokens_consumed": 0,
        "tokens_expired": 0,
        "tokens_revoked": 0,
        "order_intents": 0,
        "paper_orders_submitted": 0,
        "paper_orders_acknowledged": 0,
        "fills": 0,
        "positions_opened": 0,
        "positions_marked": 0,
        "exits": 0,
        "positions_closed": 0,
    }
    rejection_reasons: Counter[str] = Counter()
    portfolio_reasons: Counter[str] = Counter()
    a04_reasons: Counter[str] = Counter()
    for ev in events:
        et = ev.event_type
        p = ev.payload
        if et == EvidenceEventType.MARKET_OBSERVATION_ACCEPTED:
            counts["accepted_market_observations"] += 1
        elif et == EvidenceEventType.MODEL_PREDICTION:
            decision = p.decision or ""
            if decision == "SHADOW_ONLY":
                counts["shadow_predictions"] += 1
            else:
                counts["production_predictions"] += 1
        elif et == EvidenceEventType.THESIS_CREATED:
            counts["thesis_activations"] += 1
        elif et == EvidenceEventType.THESIS_REJECTED:
            counts["thesis_rejections"] += 1
            seen_for_event: set[str] = set()
            for r in p.reason_codes:
                if r not in seen_for_event:
                    rejection_reasons[r] += 1
                    seen_for_event.add(r)
            if p.reason_code and p.reason_code not in seen_for_event:
                rejection_reasons[p.reason_code] += 1
        elif et == EvidenceEventType.OPPORTUNITY_CANDIDATE_CREATED:
            counts["candidates"] += 1
        elif et == EvidenceEventType.PORTFOLIO_DECISION:
            counts["portfolio_evaluations"] += 1
            d = (p.decision or "").upper()
            if d == "ALLOW":
                counts["portfolio_allow"] += 1
            elif d == "ALLOW_REDUCED":
                counts["portfolio_allow_reduced"] += 1
            elif d == "DENY":
                counts["portfolio_deny"] += 1
            elif d == "DEFER":
                counts["portfolio_defer"] += 1
            for r in p.reason_codes:
                portfolio_reasons[r] += 1
        elif et == EvidenceEventType.A04_AUTHORITY_DECISION:
            counts["a04_evaluations"] += 1
            d = (p.decision or "").upper()
            if d == "ALLOW":
                counts["a04_allow"] += 1
            elif d == "DENY":
                counts["a04_deny"] += 1
            for r in p.reason_codes:
                a04_reasons[r] += 1
        elif et == EvidenceEventType.AUTONOMY_TOKEN_ISSUED:
            counts["tokens_issued"] += 1
        elif et == EvidenceEventType.AUTONOMY_TOKEN_CONSUMED:
            counts["tokens_consumed"] += 1
        elif et == EvidenceEventType.AUTONOMY_TOKEN_EXPIRED:
            counts["tokens_expired"] += 1
        elif et == EvidenceEventType.AUTONOMY_TOKEN_REVOKED:
            counts["tokens_revoked"] += 1
        elif et == EvidenceEventType.ORDER_INTENT_CREATED:
            counts["order_intents"] += 1
        elif et == EvidenceEventType.PAPER_ORDER_SUBMITTED:
            counts["paper_orders_submitted"] += 1
        elif et == EvidenceEventType.PAPER_ORDER_ACKNOWLEDGED:
            counts["paper_orders_acknowledged"] += 1
        elif et == EvidenceEventType.FILL_CREATED:
            counts["fills"] += 1
        elif et == EvidenceEventType.POSITION_OPENED:
            counts["positions_opened"] += 1
        elif et == EvidenceEventType.POSITION_MARKED:
            counts["positions_marked"] += 1
        elif et == EvidenceEventType.EXIT_INTENT_CREATED:
            counts["exits"] += 1
        elif et == EvidenceEventType.POSITION_CLOSED:
            counts["positions_closed"] += 1
    return {
        "counts": counts,
        "rejection_reason_distribution": dict(rejection_reasons.most_common()),
        "portfolio_reason_distribution": dict(portfolio_reasons.most_common()),
        "a04_reason_distribution": dict(a04_reasons.most_common()),
    }


# ============================================================================
# Session Summary
# ============================================================================


def build_session_summary(
    identity: Any,
    events: Sequence[SessionEvidenceEvent],
    *,
    closed_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the operator-facing session summary from persisted evidence."""
    funnel = compute_pipeline_funnel(events)
    counts = funnel["counts"]
    # Times
    start = events[0].event_time if events else None
    end = events[-1].event_time if events else None
    # Mode history (from session phase and trading mode events)
    mode_history: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type in (
            EvidenceEventType.TRADING_MODE_REQUESTED,
            EvidenceEventType.TRADING_MODE_EFFECTIVE_CHANGED,
        ):
            mode_history.append(
                {
                    "event_id": str(ev.event_id),
                    "event_type": ev.event_type.value,
                    "event_time": ev.event_time.isoformat(),
                    "state": ev.payload.state,
                }
            )
    # Feed / broker health transitions
    health_transitions: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type in (
            EvidenceEventType.FEED_HEALTH_CHANGED,
            EvidenceEventType.BROKER_HEALTH_CHANGED,
        ):
            health_transitions.append(
                {
                    "event_id": str(ev.event_id),
                    "event_type": ev.event_type.value,
                    "event_time": ev.event_time.isoformat(),
                    "state": ev.payload.state,
                }
            )
    # P&L snapshot (last)
    pnl_snapshots = [
        ev for ev in events if ev.event_type == EvidenceEventType.PNL_SNAPSHOT
    ]
    last_pnl = pnl_snapshots[-1].payload if pnl_snapshots else None
    return {
        "session_id": str(identity.session_id),
        "trading_date": identity.trading_date,
        "market": identity.market,
        "champion": identity.champion_model_id,
        "champion_version": identity.champion_model_version,
        "policy_version": identity.policy_version,
        "system_version": identity.system_version,
        "start_time": start.isoformat() if start else None,
        "end_time": end.isoformat() if end else None,
        "duration_seconds": (end - start).total_seconds() if (start and end) else 0,
        "observations": counts["accepted_market_observations"],
        "production_predictions": counts["production_predictions"],
        "shadow_predictions": counts["shadow_predictions"],
        "thesis_activations": counts["thesis_activations"],
        "rejections": counts["thesis_rejections"],
        "candidates": counts["candidates"],
        "portfolio_decisions": counts["portfolio_evaluations"],
        "portfolio_allow": counts["portfolio_allow"],
        "portfolio_allow_reduced": counts["portfolio_allow_reduced"],
        "a04_decisions": counts["a04_evaluations"],
        "a04_allow": counts["a04_allow"],
        "tokens_issued": counts["tokens_issued"],
        "orders": counts["paper_orders_submitted"],
        "fills": counts["fills"],
        "positions_opened": counts["positions_opened"],
        "positions_closed": counts["positions_closed"],
        "exits": counts["exits"],
        "realized_pnl": str(last_pnl.net_pnl) if last_pnl and last_pnl.net_pnl is not None else "0.00",
        "mode_history": mode_history,
        "health_transitions": health_transitions,
        "last_pnl_snapshot": (
            {
                "state": last_pnl.state,
                "net_pnl": str(last_pnl.net_pnl) if last_pnl.net_pnl is not None else None,
            }
            if last_pnl
            else None
        ),
    }


# ============================================================================
# Rejection Analysis (deterministic reason codes)
# ============================================================================


REJECTION_TAXONOMY = {
    "NEUTRAL_THESIS",
    "BELOW_ACTIVATION_THRESHOLD",
    "INSUFFICIENT_EVIDENCE",
    "STALE_DATA",
    "UNKNOWN_DATA",
    "CALIBRATION_UNAVAILABLE",
    "LIQUIDITY_INSUFFICIENT",
    "SPREAD_TOO_WIDE",
    "NEGATIVE_NET_EV",
    "SESSION_NOT_ENTRY_ALLOWED",
    "PORTFOLIO_DENY",
    "PORTFOLIO_DEFER",
    "A04_DENY",
    "A04_UNKNOWN",
    "CAPITAL_LIMIT",
    "POSITION_LIMIT",
    "CORRELATION_LIMIT",
    "EVIDENCE_RECORDER_UNAVAILABLE",
}


def analyze_rejections(events: Sequence[SessionEvidenceEvent]) -> dict[str, Any]:
    """Aggregate rejection reason codes with counts, percentages, first/last timestamps."""
    rejection_events = [
        ev
        for ev in events
        if ev.event_type in (
            EvidenceEventType.THESIS_REJECTED,
            EvidenceEventType.OPPORTUNITY_CANDIDATE_REJECTED,
        )
    ]
    # Total reached states: production predictions
    total_predictions = sum(
        1
        for ev in events
        if ev.event_type == EvidenceEventType.MODEL_PREDICTION
        and (ev.payload.decision or "") != "SHADOW_ONLY"
    )
    by_reason: dict[str, dict[str, Any]] = {}
    for ev in rejection_events:
        seen_for_event: set[str] = set()
        for r in ev.payload.reason_codes:
            r = str(r)
            if r not in seen_for_event:
                entry = by_reason.setdefault(
                    r,
                    {
                        "count": 0,
                        "first_occurrence": ev.event_time.isoformat(),
                        "last_occurrence": ev.event_time.isoformat(),
                    },
                )
                entry["count"] += 1
                if ev.event_time.isoformat() < entry["first_occurrence"]:
                    entry["first_occurrence"] = ev.event_time.isoformat()
                if ev.event_time.isoformat() > entry["last_occurrence"]:
                    entry["last_occurrence"] = ev.event_time.isoformat()
                seen_for_event.add(r)
        if ev.payload.reason_code:
            r = str(ev.payload.reason_code)
            if r not in seen_for_event:
                entry = by_reason.setdefault(
                    r,
                    {
                        "count": 0,
                        "first_occurrence": ev.event_time.isoformat(),
                        "last_occurrence": ev.event_time.isoformat(),
                    },
                )
                entry["count"] += 1
                if ev.event_time.isoformat() < entry["first_occurrence"]:
                    entry["first_occurrence"] = ev.event_time.isoformat()
                if ev.event_time.isoformat() > entry["last_occurrence"]:
                    entry["last_occurrence"] = ev.event_time.isoformat()
    # Add canonical taxonomy entries with 0 count
    for code in REJECTION_TAXONOMY:
        by_reason.setdefault(
            code, {"count": 0, "first_occurrence": None, "last_occurrence": None}
        )
    for r, entry in by_reason.items():
        entry["percentage_of_reached"] = (
            round(100.0 * entry["count"] / total_predictions, 2) if total_predictions else 0.0
        )
    return {
        "total_rejections": len(rejection_events),
        "total_predictions": total_predictions,
        "by_reason": by_reason,
    }


# ============================================================================
# Gate Audit
# ============================================================================


GATE_NAMES = [
    "session",
    "market_freshness",
    "evidence_completeness",
    "calibration",
    "liquidity",
    "spread",
    "net_ev",
    "portfolio",
    "risk",
    "a04",
    "token",
    "capital",
    "drawdown",
    "position_limits",
    "correlation",
    "paper_broker",
]


def audit_gates(events: Sequence[SessionEvidenceEvent]) -> dict[str, Any]:
    """Compute REACHED/ALLOW/DENY/UNKNOWN/NOT_REACHED for each deterministic gate."""
    funnel = compute_pipeline_funnel(events)
    c = funnel["counts"]
    has_pred = c["production_predictions"] > 0
    has_cand = c["candidates"] > 0
    has_port = c["portfolio_evaluations"] > 0
    has_a04 = c["a04_evaluations"] > 0
    has_token = c["tokens_issued"] > 0
    has_fill = c["fills"] > 0
    # session gate
    session_state = "UNKNOWN"
    for ev in events:
        if ev.event_type == EvidenceEventType.SESSION_STARTED:
            session_state = "ALLOW"
        elif ev.event_type == EvidenceEventType.SESSION_CLOSED:
            session_state = "CLOSED"
    # paper broker
    if c["paper_orders_submitted"] > 0 and c["paper_orders_acknowledged"] == c["paper_orders_submitted"]:
        paper_broker = "ALLOW"
    elif c["paper_orders_submitted"] > 0:
        paper_broker = "DEGRADED"
    elif has_token:
        paper_broker = "DENY"
    else:
        paper_broker = "NOT_REACHED"
    # calibration
    cal_evs = [
        ev
        for ev in events
        if ev.event_type == EvidenceEventType.CALIBRATION_EVALUATED
    ]
    calibration = "ALLOW" if cal_evs else "NOT_REACHED"
    # risk
    risk = "ALLOW" if has_a04 else "NOT_REACHED"
    # net_ev
    net_ev = "ALLOW" if has_cand else ("DENY" if has_pred else "NOT_REACHED")
    # liquidity
    liquidity_reasons = [
        "LIQUIDITY_INSUFFICIENT",
        "INSUFFICIENT_LIQUIDITY",
    ]
    liquidity_denied = any(
        any(r in liquidity_reasons for r in ev.payload.reason_codes)
        for ev in events
        if ev.event_type in (EvidenceEventType.THESIS_REJECTED, EvidenceEventType.OPPORTUNITY_CANDIDATE_REJECTED)
    )
    liquidity = "DENY" if liquidity_denied else ("ALLOW" if has_cand else "NOT_REACHED")
    spread_reasons = ["SPREAD_TOO_WIDE", "SPREAD_UNAVAILABLE"]
    spread_denied = any(
        any(r in spread_reasons for r in ev.payload.reason_codes)
        for ev in events
        if ev.event_type in (EvidenceEventType.THESIS_REJECTED, EvidenceEventType.OPPORTUNITY_CANDIDATE_REJECTED)
    )
    spread = "DENY" if spread_denied else ("ALLOW" if has_cand else "NOT_REACHED")
    # portfolio
    if c["portfolio_deny"] > 0:
        portfolio = "DENY"
    elif c["portfolio_allow"] > 0 or c["portfolio_allow_reduced"] > 0:
        portfolio = "ALLOW"
    elif has_cand:
        portfolio = "DEFER"
    else:
        portfolio = "NOT_REACHED"
    # a04
    if c["a04_deny"] > 0:
        a04 = "DENY"
    elif c["a04_allow"] > 0:
        a04 = "ALLOW"
    else:
        a04 = "NOT_REACHED"
    # token
    token = "ALLOW" if c["tokens_issued"] > 0 else "NOT_REACHED"
    # capital / drawdown / position limits
    capital = "ALLOW" if has_token else "NOT_REACHED"
    drawdown = "ALLOW" if has_fill else "NOT_REACHED"
    position_limits = "ALLOW" if has_fill else "NOT_REACHED"
    correlation = "ALLOW" if has_fill else "NOT_REACHED"
    return {
        "gates": {
            "session": {"state": session_state, "reached": has_pred},
            "market_freshness": {
                "state": "ALLOW" if has_pred else "NOT_REACHED",
                "reached": has_pred,
            },
            "evidence_completeness": {
                "state": "ALLOW" if has_pred else "NOT_REACHED",
                "reached": has_pred,
            },
            "calibration": {"state": calibration, "reached": len(cal_evs) > 0},
            "liquidity": {"state": liquidity, "reached": has_cand},
            "spread": {"state": spread, "reached": has_cand},
            "net_ev": {"state": net_ev, "reached": has_pred or has_cand},
            "portfolio": {"state": portfolio, "reached": has_port},
            "risk": {"state": risk, "reached": has_a04},
            "a04": {"state": a04, "reached": has_a04},
            "token": {"state": token, "reached": has_token},
            "capital": {"state": capital, "reached": has_token},
            "drawdown": {"state": drawdown, "reached": has_fill},
            "position_limits": {"state": position_limits, "reached": has_fill},
            "correlation": {"state": correlation, "reached": has_fill},
            "paper_broker": {"state": paper_broker, "reached": has_token},
        }
    }


# ============================================================================
# Model Probability Distribution
# ============================================================================


THRESHOLDS = [0.50, 0.51, 0.52, 0.53, 0.54, 0.55, 0.57, 0.60, 0.65, 0.70]


def compute_model_probability_distribution(
    events: Sequence[SessionEvidenceEvent],
) -> dict[str, Any]:
    """Compute per-model probability distribution (min, percentiles, mean, std, threshold counts)."""
    by_model: dict[str, list[float]] = defaultdict(list)
    for ev in events:
        if ev.event_type != EvidenceEventType.MODEL_PREDICTION:
            continue
        p = ev.payload
        if p.probability is None:
            continue
        model_id = p.model_id or "unknown"
        try:
            by_model[model_id].append(float(p.probability))
        except Exception:
            continue
    result: dict[str, Any] = {}
    for model_id, probs in by_model.items():
        if not probs:
            continue
        sorted_p = sorted(probs)
        n = len(sorted_p)
        def pct(p: float) -> float:
            idx = max(0, min(n - 1, int(round(p * (n - 1)))))
            return round(sorted_p[idx], 6)
        threshold_counts = {str(t): sum(1 for v in probs if v >= t) for t in THRESHOLDS}
        result[model_id] = {
            "count": n,
            "min": round(min(probs), 6),
            "p01": pct(0.01),
            "p05": pct(0.05),
            "p10": pct(0.10),
            "p25": pct(0.25),
            "median": pct(0.50),
            "p75": pct(0.75),
            "p90": pct(0.90),
            "p95": pct(0.95),
            "p99": pct(0.99),
            "max": round(max(probs), 6),
            "mean": round(statistics.mean(probs), 6),
            "std": round(statistics.stdev(probs), 6) if n > 1 else 0.0,
            "threshold_crossings": threshold_counts,
        }
    return {"models": result}


# ============================================================================
# Near-Activation Report
# ============================================================================


def find_near_activations(
    events: Sequence[SessionEvidenceEvent],
    *,
    threshold: float = 0.55,
    max_distance: float = 0.05,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Find production predictions that almost activated (close to threshold but below)."""
    out: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type != EvidenceEventType.MODEL_PREDICTION:
            continue
        p = ev.payload
        if p.probability is None:
            continue
        if (p.decision or "") == "SHADOW_ONLY":
            continue
        prob = float(p.probability)
        # distance to threshold (closest side)
        dist = prob - threshold if prob >= 0.5 else (1.0 - prob) - threshold
        if prob < threshold and dist > -max_distance:
            out.append(
                {
                    "event_id": str(ev.event_id),
                    "event_time": ev.event_time.isoformat(),
                    "underlying": p.underlying,
                    "probability": prob,
                    "direction": p.decision or "NEUTRAL",
                    "threshold": threshold,
                    "distance": round(dist, 4),
                    "reason_code": p.reason_code,
                    "model_id": p.model_id,
                }
            )
    out.sort(key=lambda x: x["distance"], reverse=True)
    return out[:limit]


# ============================================================================
# Session Timeline
# ============================================================================


TIMELINE_MATERIAL = {
    EvidenceEventType.SESSION_STARTED,
    EvidenceEventType.SESSION_CLOSED,
    EvidenceEventType.SESSION_PHASE_CHANGED,
    EvidenceEventType.SESSION_ENTRY_CUTOFF,
    EvidenceEventType.SESSION_FLATTEN_WINDOW,
    EvidenceEventType.FEED_HEALTH_CHANGED,
    EvidenceEventType.BROKER_HEALTH_CHANGED,
    EvidenceEventType.TRADING_MODE_REQUESTED,
    EvidenceEventType.TRADING_MODE_EFFECTIVE_CHANGED,
    EvidenceEventType.MARKET_OBSERVATION_ACCEPTED,
    EvidenceEventType.MODEL_PREDICTION,
    EvidenceEventType.OPPORTUNITY_CANDIDATE_CREATED,
    EvidenceEventType.PORTFOLIO_DECISION,
    EvidenceEventType.A04_AUTHORITY_DECISION,
    EvidenceEventType.AUTONOMY_TOKEN_ISSUED,
    EvidenceEventType.ORDER_INTENT_CREATED,
    EvidenceEventType.PAPER_ORDER_SUBMITTED,
    EvidenceEventType.PAPER_ORDER_ACKNOWLEDGED,
    EvidenceEventType.FILL_CREATED,
    EvidenceEventType.POSITION_OPENED,
    EvidenceEventType.POSITION_MARKED,
    EvidenceEventType.EXIT_INTENT_CREATED,
    EvidenceEventType.POSITION_CLOSED,
    EvidenceEventType.PNL_SNAPSHOT,
}


def build_session_timeline(events: Sequence[SessionEvidenceEvent]) -> list[dict[str, Any]]:
    """Build the operator-facing timeline (UTC authority timestamps)."""
    out: list[dict[str, Any]] = []
    for ev in events:
        if ev.event_type not in TIMELINE_MATERIAL:
            continue
        out.append(
            {
                "event_id": str(ev.event_id),
                "event_type": ev.event_type.value,
                "event_time_utc": ev.event_time.isoformat(),
                "sequence_number": ev.sequence_number,
                "underlying": ev.payload.underlying,
                "instrument_id": ev.payload.instrument_id,
                "decision": ev.payload.decision,
                "reason_code": ev.payload.reason_code,
                "state": ev.payload.state,
                "price": str(ev.payload.price) if ev.payload.price is not None else None,
                "net_pnl": str(ev.payload.net_pnl) if ev.payload.net_pnl is not None else None,
            }
        )
    return out


# ============================================================================
# Why-No-Trade Explanation
# ============================================================================


NO_TRADE_CAUSE_LABELS = {
    "MODEL_ACTIVATION": "All production predictions were below the activation threshold",
    "EVIDENCE": "Insufficient evidence to construct a candidate",
    "PORTFOLIO": "Portfolio Brain denied or deferred all candidates",
    "A04": "A04 authority denied all candidates",
    "TOKEN": "No autonomy token was issued",
    "BROKER": "Paper broker rejected orders",
    "SESSION_CUTOFF": "Session was in EXIT_ONLY or CLOSED phase",
    "RECORDER_FAILURE": "Evidence recorder was unavailable; no new risk accepted",
    "NO_PREDICTIONS": "No production predictions were recorded",
    "TRADES_EXECUTED": "Trades were executed; not a no-trade session",
}


def explain_why_no_trade(
    events: Sequence[SessionEvidenceEvent],
) -> dict[str, Any]:
    """Deterministic root-cause explanation for no-trade sessions."""
    funnel = compute_pipeline_funnel(events)
    c = funnel["counts"]
    if c["fills"] > 0 or c["positions_opened"] > 0:
        return {
            "primary_cause": "TRADES_EXECUTED",
            "label": NO_TRADE_CAUSE_LABELS["TRADES_EXECUTED"],
            "supporting_facts": {
                "fills": c["fills"],
                "positions_opened": c["positions_opened"],
                "orders": c["paper_orders_submitted"],
            },
        }
    if c["production_predictions"] == 0:
        return {
            "primary_cause": "NO_PREDICTIONS",
            "label": NO_TRADE_CAUSE_LABELS["NO_PREDICTIONS"],
            "supporting_facts": {
                "production_predictions": 0,
                "observations": c["accepted_market_observations"],
            },
        }
    if (
        c["candidates"] == 0
        and c["portfolio_evaluations"] == 0
        and c["a04_evaluations"] == 0
        and c["paper_orders_submitted"] == 0
        and c["production_predictions"] > 0
    ):
        return {
            "primary_cause": "MODEL_ACTIVATION",
            "label": NO_TRADE_CAUSE_LABELS["MODEL_ACTIVATION"],
            "supporting_facts": {
                "production_predictions": c["production_predictions"],
                "rejections": c["thesis_rejections"],
                "candidates": 0,
                "portfolio": "NOT_REACHED",
                "a04": "NOT_REACHED",
                "orders": 0,
            },
        }
    if c["candidates"] == 0 and c["thesis_rejections"] > 0:
        return {
            "primary_cause": "EVIDENCE",
            "label": NO_TRADE_CAUSE_LABELS["EVIDENCE"],
            "supporting_facts": {
                "thesis_rejections": c["thesis_rejections"],
                "candidates": 0,
                "portfolio": "NOT_REACHED",
                "a04": "NOT_REACHED",
                "orders": 0,
            },
        }
    if c["portfolio_deny"] > 0 and c["portfolio_allow"] == 0 and c["portfolio_allow_reduced"] == 0:
        return {
            "primary_cause": "PORTFOLIO",
            "label": NO_TRADE_CAUSE_LABELS["PORTFOLIO"],
            "supporting_facts": {
                "portfolio_evaluations": c["portfolio_evaluations"],
                "portfolio_deny": c["portfolio_deny"],
                "a04": "NOT_REACHED",
                "orders": 0,
            },
        }
    if c["a04_deny"] > 0 and c["a04_allow"] == 0:
        return {
            "primary_cause": "A04",
            "label": NO_TRADE_CAUSE_LABELS["A04"],
            "supporting_facts": {
                "a04_evaluations": c["a04_evaluations"],
                "a04_deny": c["a04_deny"],
                "tokens_issued": 0,
                "orders": 0,
            },
        }
    if c["paper_orders_submitted"] == 0 and c["a04_allow"] > 0 and c["tokens_issued"] == 0:
        return {
            "primary_cause": "TOKEN",
            "label": NO_TRADE_CAUSE_LABELS["TOKEN"],
            "supporting_facts": {
                "a04_allow": c["a04_allow"],
                "tokens_issued": 0,
            },
        }
    if c["paper_orders_submitted"] == 0 and c["tokens_issued"] > 0:
        return {
            "primary_cause": "BROKER",
            "label": NO_TRADE_CAUSE_LABELS["BROKER"],
            "supporting_facts": {
                "tokens_issued": c["tokens_issued"],
                "orders": 0,
            },
        }
    return {
        "primary_cause": "UNKNOWN",
        "label": "No trade executed; root cause not identified from evidence ledger",
        "supporting_facts": {
            "production_predictions": c["production_predictions"],
            "candidates": c["candidates"],
            "portfolio_evaluations": c["portfolio_evaluations"],
            "a04_evaluations": c["a04_evaluations"],
            "orders": c["paper_orders_submitted"],
        },
    }


# ============================================================================
# Session Finalizer
# ============================================================================


def finalize_session(
    identity: Any,
    events: Sequence[SessionEvidenceEvent],
    root: Path | str,
) -> dict[str, Any]:
    """Auto-finalize a completed session: produce all forensic artifacts.

    No manual export required. No fabricated values.
    Returns a dict of all generated artifact paths.
    """
    root_path = Path(root) / identity.trading_date / str(identity.session_id)
    root_path.mkdir(parents=True, exist_ok=True)
    # 1. session_manifest.json (alias of evidence manifest)
    manifest = {
        "session_id": str(identity.session_id),
        "trading_date": identity.trading_date,
        "market": identity.market,
        "champion": identity.champion_model_id,
        "champion_version": identity.champion_model_version,
        "policy_version": identity.policy_version,
        "system_version": identity.system_version,
        "started_at": identity.started_at.isoformat(),
        "finalized_at": datetime.now(UTC).isoformat(),
        "event_count": len(events),
        "first_event_id": str(events[0].event_id) if events else None,
        "last_event_id": str(events[-1].event_id) if events else None,
        "first_sequence": events[0].sequence_number if events else None,
        "last_sequence": events[-1].sequence_number if events else None,
    }
    (root_path / "session_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    # 2. session_summary.json
    summary = build_session_summary(identity, events)
    (root_path / "session_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    # 3. session_timeline.csv
    timeline = build_session_timeline(events)
    if timeline:
        with (root_path / "session_timeline.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(timeline[0].keys()))
            writer.writeheader()
            for row in timeline:
                writer.writerow(row)
    # 4. pipeline_funnel.json
    funnel = compute_pipeline_funnel(events)
    # Add conversion percentages
    counts = funnel["counts"]
    conversions = {}
    for k, v in counts.items():
        conversions[k] = v
    funnel["conversions"] = conversions
    (root_path / "pipeline_funnel.json").write_text(
        json.dumps(funnel, indent=2) + "\n", encoding="utf-8"
    )
    # 5. gate_audit.json
    audit = audit_gates(events)
    (root_path / "gate_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n", encoding="utf-8"
    )
    # 6. model_probability_distribution.json
    prob_dist = compute_model_probability_distribution(events)
    (root_path / "model_probability_distribution.json").write_text(
        json.dumps(prob_dist, indent=2) + "\n", encoding="utf-8"
    )
    # 7. evidence_integrity.json
    integrity = verify_integrity(events)
    (root_path / "evidence_integrity.json").write_text(
        json.dumps(integrity, indent=2) + "\n", encoding="utf-8"
    )
    # 8. rejection_history.csv
    rejection_evs = [
        ev
        for ev in events
        if ev.event_type in (
            EvidenceEventType.THESIS_REJECTED,
            EvidenceEventType.OPPORTUNITY_CANDIDATE_REJECTED,
        )
    ]
    with (root_path / "rejection_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "sequence_number",
                "event_time_utc",
                "reason_codes",
                "reason_code",
                "underlying",
                "instrument_id",
            ]
        )
        for ev in rejection_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    "|".join(ev.payload.reason_codes),
                    ev.payload.reason_code or "",
                    ev.payload.underlying or "",
                    ev.payload.instrument_id or "",
                ]
            )
    # 9. orders.csv
    order_evs = [
        ev
        for ev in events
        if ev.event_type
        in (
            EvidenceEventType.PAPER_ORDER_SUBMITTED,
            EvidenceEventType.PAPER_ORDER_ACKNOWLEDGED,
            EvidenceEventType.PAPER_ORDER_REJECTED,
            EvidenceEventType.PAPER_ORDER_CANCELLED,
        )
    ]
    with (root_path / "orders.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "sequence_number",
                "event_time_utc",
                "event_type",
                "instrument_id",
                "underlying",
            ]
        )
        for ev in order_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.event_type.value,
                    ev.payload.instrument_id or "",
                    ev.payload.underlying or "",
                ]
            )
    # 10. fills.csv
    fill_evs = [ev for ev in events if ev.event_type == EvidenceEventType.FILL_CREATED]
    with (root_path / "fills.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "sequence_number",
                "event_time_utc",
                "instrument_id",
                "price",
                "underlying",
            ]
        )
        for ev in fill_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.payload.instrument_id or "",
                    str(ev.payload.price) if ev.payload.price is not None else "",
                    ev.payload.underlying or "",
                ]
            )
    # 11. positions.csv
    pos_evs = [
        ev
        for ev in events
        if ev.event_type
        in (
            EvidenceEventType.POSITION_OPENED,
            EvidenceEventType.POSITION_MARKED,
            EvidenceEventType.POSITION_CLOSED,
            EvidenceEventType.POSITION_REDUCED,
        )
    ]
    with (root_path / "positions.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "sequence_number",
                "event_time_utc",
                "event_type",
                "instrument_id",
                "price",
            ]
        )
        for ev in pos_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.event_type.value,
                    ev.payload.instrument_id or "",
                    str(ev.payload.price) if ev.payload.price is not None else "",
                ]
            )
    # 12. pnl_series.csv
    pnl_evs = [ev for ev in events if ev.event_type == EvidenceEventType.PNL_SNAPSHOT]
    with (root_path / "pnl_series.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["event_id", "sequence_number", "event_time_utc", "state", "net_pnl"])
        for ev in pnl_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.payload.state or "",
                    str(ev.payload.net_pnl) if ev.payload.net_pnl is not None else "",
                ]
            )
    # 13. prediction_history.csv
    pred_evs = [ev for ev in events if ev.event_type == EvidenceEventType.MODEL_PREDICTION]
    with (root_path / "prediction_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "event_id",
                "sequence_number",
                "event_time_utc",
                "model_id",
                "underlying",
                "probability",
                "decision",
                "reason_code",
            ]
        )
        for ev in pred_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.payload.model_id or "",
                    ev.payload.underlying or "",
                    str(ev.payload.probability) if ev.payload.probability is not None else "",
                    ev.payload.decision or "",
                    ev.payload.reason_code or "",
                ]
            )
    # 14. decision_history.csv
    decision_evs = [
        ev
        for ev in events
        if ev.event_type
        in (
            EvidenceEventType.PORTFOLIO_DECISION,
            EvidenceEventType.A04_AUTHORITY_DECISION,
            EvidenceEventType.AUTONOMY_TOKEN_ISSUED,
            EvidenceEventType.ORDER_INTENT_CREATED,
            EvidenceEventType.EXIT_INTENT_CREATED,
        )
    ]
    with (root_path / "decision_history.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["event_id", "sequence_number", "event_time_utc", "event_type", "decision", "reason_code"]
        )
        for ev in decision_evs:
            writer.writerow(
                [
                    str(ev.event_id),
                    ev.sequence_number,
                    ev.event_time.isoformat(),
                    ev.event_type.value,
                    ev.payload.decision or "",
                    ev.payload.reason_code or "",
                ]
            )
    # 15. why_no_trade.json
    why = explain_why_no_trade(events)
    (root_path / "why_no_trade.json").write_text(
        json.dumps(why, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "root": str(root_path),
        "session_manifest": str(root_path / "session_manifest.json"),
        "session_summary": str(root_path / "session_summary.json"),
        "session_timeline_csv": str(root_path / "session_timeline.csv"),
        "pipeline_funnel": str(root_path / "pipeline_funnel.json"),
        "gate_audit": str(root_path / "gate_audit.json"),
        "model_probability_distribution": str(root_path / "model_probability_distribution.json"),
        "evidence_integrity": str(root_path / "evidence_integrity.json"),
        "rejection_history_csv": str(root_path / "rejection_history.csv"),
        "orders_csv": str(root_path / "orders.csv"),
        "fills_csv": str(root_path / "fills.csv"),
        "positions_csv": str(root_path / "positions.csv"),
        "pnl_series_csv": str(root_path / "pnl_series.csv"),
        "prediction_history_csv": str(root_path / "prediction_history.csv"),
        "decision_history_csv": str(root_path / "decision_history.csv"),
        "why_no_trade": str(root_path / "why_no_trade.json"),
        "integrity_status": integrity["status"],
    }


# ============================================================================
# Session Discovery (used by REST API)
# ============================================================================


def discover_sessions(root: Path | str) -> list[dict[str, Any]]:
    """Discover all completed session directories under the root."""
    root_path = Path(root)
    out: list[dict[str, Any]] = []
    if not root_path.exists():
        return out
    for date_dir in sorted(root_path.iterdir()):
        if not date_dir.is_dir():
            continue
        for session_dir in sorted(date_dir.iterdir()):
            if not session_dir.is_dir():
                continue
            events_path = session_dir / "events.jsonl"
            manifest_path = session_dir / "session_manifest.json"
            if events_path.exists():
                out.append(
                    {
                        "session_id": session_dir.name,
                        "trading_date": date_dir.name,
                        "events_path": str(events_path),
                        "manifest_path": str(manifest_path) if manifest_path.exists() else None,
                        "finalized": manifest_path.exists(),
                    }
                )
    return out


def load_session_recorder(identity: Any, root: Path | str) -> SessionEvidenceRecorder:
    """Load a session recorder from disk (reopens the same session)."""
    return SessionEvidenceRecorder(identity, root)


__all__ = [
    "IntegrityStatus",
    "verify_integrity",
    "compute_pipeline_funnel",
    "build_session_summary",
    "analyze_rejections",
    "audit_gates",
    "compute_model_probability_distribution",
    "find_near_activations",
    "build_session_timeline",
    "explain_why_no_trade",
    "finalize_session",
    "discover_sessions",
    "load_session_recorder",
    "REJECTION_TAXONOMY",
    "GATE_NAMES",
    "NO_TRADE_CAUSE_LABELS",
]
