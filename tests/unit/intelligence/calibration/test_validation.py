from datetime import timedelta

from ats.intelligence.calibration import (
    CalibrationHealth,
    CalibrationValidationPolicy,
    validate_calibration_history,
)

from tests.unit.intelligence.calibration.helpers import observation
from tests.unit.intelligence.ensemble.helpers import context

T0 = context().data_cutoff


def _history(*, accurate: bool = True):
    return tuple(
        observation(
            index + 100,
            (index % 4 != 0) if accurate else (index % 4 == 0),
            probability="0.75",
            minutes_before=120 - index,
        )
        for index in range(60)
    )


def test_time_ordered_report_records_windows_metrics_and_reliability() -> None:
    report = validate_calibration_history(_history(), decision_time=T0)
    assert report.health is CalibrationHealth.HEALTHY
    assert (report.train_count, report.validation_count, report.oos_count) == (36, 12, 12)
    assert report.brier_score is not None
    assert report.log_loss is not None
    assert report.reliability[0].count == 12


def test_future_available_labels_are_excluded() -> None:
    history = _history()
    future = history[-1].model_copy(update={"available_to_strategy_time": T0 + timedelta(1)})
    report = validate_calibration_history(history[:-1] + (future,), decision_time=T0)
    assert report.health is CalibrationHealth.INVALID
    assert report.reason_codes == ("INSUFFICIENT_TIME_ORDERED_SUPPORT",)


def test_bad_oos_calibration_is_degraded() -> None:
    report = validate_calibration_history(
        _history(accurate=False),
        decision_time=T0,
        policy=CalibrationValidationPolicy(maximum_calibration_error=0.10),
    )
    assert report.health is CalibrationHealth.DEGRADED
    assert "RELIABILITY_DRIFT" in report.reason_codes


def test_observation_information_clock_cannot_precede_outcome() -> None:
    item = observation(999, True)
    try:
        item.model_copy(
            update={"available_to_strategy_time": item.observed_at - timedelta(seconds=1)}
        ).model_validate(
            item.model_dump()
            | {"available_to_strategy_time": item.observed_at - timedelta(seconds=1)}
        )
    except ValueError as error:
        assert "cannot be available" in str(error)
    else:
        raise AssertionError("invalid information clock accepted")
