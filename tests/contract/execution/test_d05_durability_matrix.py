from ats.execution.durability import (
    DurabilityRequirement,
    RuntimeTransition,
    execution_durability_matrix,
)


def test_every_runtime_transition_has_one_explicit_durability_classification() -> None:
    matrix = execution_durability_matrix()
    assert {item.transition for item in matrix} == set(RuntimeTransition)
    assert len(matrix) == len(RuntimeTransition)


def test_every_financial_or_safety_transition_requires_minimal_durability() -> None:
    memory_only = {
        RuntimeTransition.MARKET_STATE_UPDATE,
        RuntimeTransition.CANDIDATE,
    }
    for item in execution_durability_matrix():
        expected = (
            DurabilityRequirement.HOT_MEMORY_ONLY_ALLOWED
            if item.transition in memory_only
            else DurabilityRequirement.MINIMAL_DURABILITY_REQUIRED_BEFORE_EXTERNAL_ACTION
        )
        assert item.requirement is expected
        assert item.reconstruction_source
