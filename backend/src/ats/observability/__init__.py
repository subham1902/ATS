"""Observability namespace."""

from . import operator_intelligence
from .session_evidence import (
    EvidenceEventType,
    EvidenceManifest,
    EvidencePayload,
    SessionEvidenceEvent,
    SessionEvidenceRecorder,
    SessionIdentity,
)
from .session_forensics import (
    IntegrityStatus,
    analyze_rejections,
    audit_gates,
    build_session_summary,
    build_session_timeline,
    compute_model_probability_distribution,
    compute_pipeline_funnel,
    discover_sessions,
    explain_why_no_trade,
    finalize_session,
    find_near_activations,
    verify_integrity,
)

__all__ = [
    "operator_intelligence",
    "EvidenceEventType",
    "EvidenceManifest",
    "EvidencePayload",
    "SessionEvidenceEvent",
    "SessionEvidenceRecorder",
    "SessionIdentity",
    "IntegrityStatus",
    "audit_gates",
    "analyze_rejections",
    "build_session_summary",
    "build_session_timeline",
    "compute_model_probability_distribution",
    "compute_pipeline_funnel",
    "discover_sessions",
    "explain_why_no_trade",
    "finalize_session",
    "find_near_activations",
    "verify_integrity",
]
