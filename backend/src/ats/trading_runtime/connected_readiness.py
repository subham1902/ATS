"""Typed connected readiness truth; no constructor default can imply live health."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from ats.trading_runtime.session_reconciliation import ReconciliationResult, ReconciliationState


class ReadinessContext(StrEnum):
    OFFLINE_SYNTHETIC = "OFFLINE_SYNTHETIC"
    CONNECTED_PREMARKET = "CONNECTED_PREMARKET"
    CONNECTED_RUNNING_SESSION = "CONNECTED_RUNNING_SESSION"


class EvidenceType(StrEnum):
    REAL = "REAL"
    CONFIGURED = "CONFIGURED"
    DERIVED = "DERIVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class CheckResult(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TruthField:
    check: str
    value: Any
    source: str
    evidence_type: EvidenceType
    timestamp: str
    result: CheckResult
    blocking: bool


@dataclass(frozen=True)
class InstrumentSpecTruth:
    underlying: str
    underlying_key: str
    lot_size: int
    tick_size: str
    expiry: str
    option_keys: tuple[str, ...]


@dataclass(frozen=True)
class ConnectedReadinessInput:
    context: ReadinessContext
    checked_at: datetime
    trading_date: str
    market_phase: str
    session_can_enter: bool
    requested_mode: str
    effective_mode: str | None
    execution_target: str
    live_money_enabled: bool | None
    real_broker_enabled: bool | None
    configured_capital: Decimal
    runtime_capital: Decimal | None
    provider_auth: str
    provider_reference: str
    feed_connection: str
    decoder_status: str
    subscription_status: str
    specs: tuple[InstrumentSpecTruth, ...]
    duplicate_subscriptions: int
    invalid_subscriptions: int
    market_data_stage: str
    paperbroker_status: str
    recorder_status: str
    forensics_status: str
    a04_status: str
    reconciliation: ReconciliationResult


@dataclass(frozen=True)
class ConnectedPreMarketReadiness:
    context: ReadinessContext
    checked_at: str
    trading_date: str
    market_phase: str
    session_fsm: str
    can_enter_new_risk: bool
    stage1_configuration_ready: bool
    stage2_market_data_ready: bool
    ready_for_a2_paper_session: bool
    truth: tuple[TruthField, ...]
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def status_verdict(self) -> str:
        if self.context is ReadinessContext.OFFLINE_SYNTHETIC:
            return "SYNTHETIC_READINESS_PASS" if not self.blocking_reasons else "SYNTHETIC_BLOCKED"
        if self.ready_for_a2_paper_session:
            return "READY_FOR_A2_PAPER_SESSION"
        return f"BLOCKED_{self.blocking_reasons[0]}" if self.blocking_reasons else "BLOCKED_UNKNOWN"

    @property
    def exit_code(self) -> int:
        if self.ready_for_a2_paper_session:
            return 2 if self.warnings else 0
        if "RECONCILIATION_REQUIRED" in self.blocking_reasons:
            return 3
        return 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.value,
            "checked_at": self.checked_at,
            "trading_date": self.trading_date,
            "market_phase": self.market_phase,
            "session_fsm": self.session_fsm,
            "can_enter_new_risk": self.can_enter_new_risk,
            "stage1_configuration_ready": self.stage1_configuration_ready,
            "stage2_market_data_ready": self.stage2_market_data_ready,
            "ready_for_a2_paper_session": self.ready_for_a2_paper_session,
            "blocking_reasons": list(self.blocking_reasons),
            "warnings": list(self.warnings),
            "status_verdict": self.status_verdict,
            "exit_code": self.exit_code,
            "truth_table": [
                {
                    "check": item.check,
                    "value": item.value,
                    "source": item.source,
                    "evidence_type": item.evidence_type.value,
                    "timestamp": item.timestamp,
                    "result": item.result.value,
                    "blocking": item.blocking,
                }
                for item in self.truth
            ],
        }


def evaluate_connected_readiness(probe: ConnectedReadinessInput) -> ConnectedPreMarketReadiness:
    stamp = probe.checked_at.isoformat()
    truth: list[TruthField] = []
    blocks: list[str] = []
    warnings: list[str] = []

    def add(
        check: str,
        value: Any,
        source: str,
        evidence: EvidenceType,
        result: CheckResult,
        *,
        block_reason: str | None = None,
    ) -> None:
        blocking = result in (CheckResult.FAIL, CheckResult.UNKNOWN) and block_reason is not None
        truth.append(TruthField(check, value, source, evidence, stamp, result, blocking))
        if blocking and block_reason is not None and block_reason not in blocks:
            blocks.append(block_reason)

    add(
        "EXECUTION_TARGET",
        probe.execution_target,
        "A2PaperSessionConfig.execution_target",
        EvidenceType.CONFIGURED,
        CheckResult.PASS if probe.execution_target == "PAPER" else CheckResult.FAIL,
        block_reason="EXECUTION_AUTHORITY_UNKNOWN",
    )
    add(
        "LIVE_MONEY",
        probe.live_money_enabled,
        "A2PaperSessionConfig.live_money",
        EvidenceType.CONFIGURED if probe.live_money_enabled is not None else EvidenceType.UNKNOWN,
        CheckResult.PASS if probe.live_money_enabled is False else CheckResult.FAIL,
        block_reason="LIVE_MONEY_OR_AUTHORITY_UNKNOWN",
    )
    add(
        "REAL_BROKER",
        probe.real_broker_enabled,
        "Canonical launcher execution selection",
        EvidenceType.CONFIGURED if probe.real_broker_enabled is not None else EvidenceType.UNKNOWN,
        CheckResult.PASS if probe.real_broker_enabled is False else CheckResult.FAIL,
        block_reason="EXECUTION_AUTHORITY_UNKNOWN",
    )
    add(
        "REQUESTED_MODE",
        probe.requested_mode,
        "Operator CLI",
        EvidenceType.CONFIGURED,
        CheckResult.PASS,
    )
    add(
        "EFFECTIVE_MODE",
        probe.effective_mode,
        "RuntimeProviderState" if probe.effective_mode else "No running runtime",
        EvidenceType.REAL if probe.effective_mode else EvidenceType.NOT_APPLICABLE,
        CheckResult.PASS if probe.effective_mode else CheckResult.NOT_APPLICABLE,
    )
    add(
        "CONFIGURED_CAPITAL",
        str(probe.configured_capital),
        "A2PaperSessionConfig.capital_budget",
        EvidenceType.CONFIGURED,
        CheckResult.PASS if probe.configured_capital == Decimal("100000") else CheckResult.FAIL,
        block_reason="CAPITAL_MISMATCH",
    )
    add(
        "RUNTIME_CAPITAL",
        str(probe.runtime_capital) if probe.runtime_capital is not None else None,
        "Running RuntimeProviderState"
        if probe.runtime_capital is not None
        else "No running runtime",
        EvidenceType.REAL if probe.runtime_capital is not None else EvidenceType.NOT_APPLICABLE,
        CheckResult.PASS
        if probe.runtime_capital in (None, probe.configured_capital)
        else CheckResult.FAIL,
        block_reason="CAPITAL_MISMATCH" if probe.runtime_capital is not None else None,
    )
    for check, value, source, reason in (
        ("PROVIDER_AUTH", probe.provider_auth, "UpstoxReadOnlyClient LTP", "PROVIDER_AUTH_FAILED"),
        (
            "PROVIDER_REFERENCE",
            probe.provider_reference,
            "Upstox BOD reference authority",
            "PROVIDER_REFERENCE_FAILED",
        ),
        (
            "FEED_CONNECTION",
            probe.feed_connection,
            "Upstox V3 authorizer/transport",
            "PROVIDER_CONNECTION_FAILED",
        ),
        (
            "SUBSCRIPTION_PLAN",
            probe.subscription_status,
            "DynamicOptionUniverse",
            "SUBSCRIPTION_PLAN_INVALID",
        ),
    ):
        add(
            check,
            value,
            source,
            EvidenceType.REAL,
            CheckResult.PASS if value == "PASS" else CheckResult.FAIL,
            block_reason=reason,
        )
    add(
        "DECODER",
        probe.decoder_status,
        "Upstox V3 protobuf decoder construction",
        EvidenceType.CONFIGURED,
        CheckResult.PASS
        if probe.decoder_status == "CONFIGURED_DECODER_READY"
        else CheckResult.FAIL,
        block_reason="DECODER_UNAVAILABLE",
    )
    add(
        "INSTRUMENT_SPECS",
        [spec.__dict__ for spec in probe.specs],
        "ProviderReferenceAuthority",
        EvidenceType.REAL,
        CheckResult.PASS
        if {item.underlying for item in probe.specs} == {"NIFTY", "BANKNIFTY"}
        else CheckResult.FAIL,
        block_reason="CONTRACT_RESOLUTION_FAILED",
    )
    add(
        "SUBSCRIPTION_DUPLICATES",
        probe.duplicate_subscriptions,
        "DynamicOptionUniverse",
        EvidenceType.DERIVED,
        CheckResult.PASS if probe.duplicate_subscriptions == 0 else CheckResult.FAIL,
        block_reason="SUBSCRIPTION_PLAN_INVALID",
    )
    add(
        "SUBSCRIPTION_INVALID",
        probe.invalid_subscriptions,
        "DynamicOptionUniverse",
        EvidenceType.DERIVED,
        CheckResult.PASS if probe.invalid_subscriptions == 0 else CheckResult.FAIL,
        block_reason="SUBSCRIPTION_PLAN_INVALID",
    )
    for check, value, source, expected, reason in (
        (
            "PAPERBROKER",
            probe.paperbroker_status,
            "Configured broker adapter",
            "CONFIGURED_PAPERBROKER_READY",
            "PAPERBROKER_CONFIG_INVALID",
        ),
        (
            "RECORDER",
            probe.recorder_status,
            "SessionEvidenceRecorder storage probe",
            "RECORDER_CONFIG_READY",
            "RECORDER_CONFIG_UNUSABLE",
        ),
        (
            "FORENSICS",
            probe.forensics_status,
            "Prior evidence integrity probe",
            "FORENSICS_CONFIG_READY",
            "FORENSICS_UNAVAILABLE",
        ),
        (
            "A04",
            probe.a04_status,
            "A04 policy/config import probe",
            "CONFIGURED_READY",
            "A04_CONFIG_UNAVAILABLE",
        ),
    ):
        add(
            check,
            value,
            source,
            EvidenceType.CONFIGURED,
            CheckResult.PASS if value == expected else CheckResult.FAIL,
            block_reason=reason,
        )
    reconciled = probe.reconciliation.state in (
        ReconciliationState.CLEAN_NO_PRIOR_SESSION,
        ReconciliationState.STALE_LAUNCHER_STATE,
    ) and (
        probe.reconciliation.state is ReconciliationState.CLEAN_NO_PRIOR_SESSION
        or probe.reconciliation.archive_path is not None
    )
    add(
        "PRIOR_SESSION_RECONCILIATION",
        probe.reconciliation.state.value,
        "Launcher state + PIDs + ports + evidence + checkpoint",
        EvidenceType.REAL,
        CheckResult.PASS if reconciled else CheckResult.FAIL,
        block_reason="RECONCILIATION_REQUIRED",
    )
    preopen = probe.market_phase in {"PREOPEN", "WARMUP", "CLOSED"}
    stage2_ready = probe.market_data_stage == "MARKET_OPEN_DATA_READY"
    market_data_result = (
        CheckResult.NOT_APPLICABLE
        if preopen and probe.market_data_stage == "PRE_OPEN_NOT_APPLICABLE"
        else (CheckResult.PASS if stage2_ready else CheckResult.FAIL)
    )
    add(
        "MARKET_OPEN_DATA",
        probe.market_data_stage,
        "Instrument-specific feed freshness <=2000ms",
        EvidenceType.NOT_APPLICABLE
        if market_data_result is CheckResult.NOT_APPLICABLE
        else EvidenceType.REAL,
        market_data_result,
        block_reason=None
        if market_data_result is CheckResult.NOT_APPLICABLE
        else "MARKET_OPEN_DATA_NOT_READY",
    )
    if probe.context is ReadinessContext.OFFLINE_SYNTHETIC:
        blocks.append("CONNECTED_CONTEXT_REQUIRED")
    stage1 = not [reason for reason in blocks if reason != "MARKET_OPEN_DATA_NOT_READY"]
    ready = bool(stage1 and (preopen or stage2_ready))
    can_enter = bool(stage1 and stage2_ready and probe.session_can_enter)
    return ConnectedPreMarketReadiness(
        probe.context,
        stamp,
        probe.trading_date,
        probe.market_phase,
        probe.market_phase,
        can_enter,
        stage1,
        stage2_ready,
        ready,
        tuple(truth),
        tuple(blocks),
        tuple(warnings),
    )


__all__ = [
    "CheckResult",
    "ConnectedPreMarketReadiness",
    "ConnectedReadinessInput",
    "EvidenceType",
    "InstrumentSpecTruth",
    "ReadinessContext",
    "TruthField",
    "evaluate_connected_readiness",
]
