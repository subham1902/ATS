from __future__ import annotations

from ats.contracts.governance.types import ActionKind
from ats.kernel.action_risk import classify_action
from ats.kernel.autonomy import build_decision_binding
from ats.kernel.governance import validate_probability_economics

from tests.unit.kernel.fixtures import make_kernel_fixture


def test_repeated_gate_outputs_are_identical() -> None:
    x = make_kernel_fixture()
    first = validate_probability_economics(x["candidate"], x["distribution"], x["constraints"])
    second = validate_probability_economics(x["candidate"], x["distribution"], x["constraints"])
    assert first == second


def test_repeated_binding_is_identical() -> None:
    x = make_kernel_fixture()
    args = (
        x["candidate"],
        x["context"],
        x["campaign"],
        x["thesis"],
        x["distribution"],
        x["strategy"],
    )
    assert build_decision_binding(*args) == build_decision_binding(*args)


def test_unknown_context_action_never_defaults_allow() -> None:
    assert classify_action(ActionKind.CANCEL_ORDER).direction is None
    assert classify_action(ActionKind.MODIFY_PROTECTIVE_EXIT).direction is None
