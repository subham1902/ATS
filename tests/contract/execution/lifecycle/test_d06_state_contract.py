from ats.execution.lifecycle import ExecutionState


def test_execution_state_inventory_contains_unknown_submit_and_reconciliation() -> None:
    assert {item.value for item in ExecutionState} == {
        "DRAFT",
        "AUTHORIZED",
        "RESERVED",
        "SUBMITTING",
        "SUBMITTED_UNACKNOWLEDGED",
        "ACKNOWLEDGED",
        "PARTIALLY_FILLED",
        "FILLED",
        "CANCEL_PENDING",
        "CANCELLED",
        "REJECTED",
        "RECONCILING",
        "CLOSED",
    }
