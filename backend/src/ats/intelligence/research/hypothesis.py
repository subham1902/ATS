"""Deterministic ResearchHypothesis builder with strict R13 AST validation."""

from __future__ import annotations

from uuid import UUID, uuid4

from ats.contracts.common import UTCDateTime
from ats.contracts.domain.hashing import compute_payload_hash
from ats.contracts.intelligence.models import FormulaDefinition, StrategyDefinition
from ats.contracts.intelligence.types import FormulaNodeKind

from .models import ResearchHypothesis


def validate_safe_formula_ast(formula: FormulaDefinition) -> None:
    """Validate that the formula AST uses strictly safe AST nodes without executable code."""
    stack = [formula.ast]
    while stack:
        node = stack.pop()
        if node.node_kind not in (
            FormulaNodeKind.LITERAL,
            FormulaNodeKind.FEATURE,
            FormulaNodeKind.OPERATOR,
        ):
            raise ValueError(f"Invalid or unsafe formula node kind: {node.node_kind}")
        for arg in node.arguments:
            stack.append(arg)


def build_research_hypothesis(
    *,
    hypothesis_id: UUID | None = None,
    question: str,
    rationale: str,
    evidence_refs: tuple[UUID, ...],
    market_regime_scope: tuple[str, ...],
    proposed_formula: FormulaDefinition | None = None,
    proposed_strategy: StrategyDefinition | None = None,
    dataset_scope: str,
    created_at: UTCDateTime,
    data_cutoff: UTCDateTime,
) -> ResearchHypothesis:
    """Build and validate a tamper-evident ResearchHypothesis."""
    if proposed_formula is not None:
        validate_safe_formula_ast(proposed_formula)

    hid = hypothesis_id or uuid4()
    draft = ResearchHypothesis(
        hypothesis_id=hid,
        question=question,
        rationale=rationale,
        evidence_refs=evidence_refs,
        market_regime_scope=market_regime_scope,
        proposed_formula=proposed_formula,
        proposed_strategy=proposed_strategy,
        dataset_scope=dataset_scope,
        created_at=created_at,
        data_cutoff=data_cutoff,
        input_hash="0" * 64,
        payload_hash="0" * 64,
    )
    # Compute input hash and payload hash
    input_hash = compute_payload_hash(draft, hash_field="input_hash")
    with_input = draft.model_copy(update={"input_hash": input_hash})
    return with_input.model_copy(update={"payload_hash": compute_payload_hash(with_input)})


__all__ = ["build_research_hypothesis", "validate_safe_formula_ast"]
