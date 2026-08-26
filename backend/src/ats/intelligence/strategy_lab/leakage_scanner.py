"""Mandatory leakage scanner: purge, embargo, walk-forward, label overlap."""

from __future__ import annotations

from dataclasses import dataclass

from ats.contracts.common import UTCDateTime
from ats.contracts.intelligence.models import StrategyExperiment
from ats.contracts.intelligence.types import LeakageScanStatus
from ats.market.replay.models import ReplayBar, ReplayDataset

from .types import WalkForwardPlan


@dataclass(frozen=True, slots=True)
class LeakageScanResult:
    status: LeakageScanStatus
    reason_codes: tuple[str, ...]


def _last_index_at_or_before(bars: tuple[ReplayBar, ...], timestamp: UTCDateTime) -> int | None:
    for index in range(len(bars) - 1, -1, -1):
        if bars[index].bar_timestamp <= timestamp:
            return index
    return None


def _first_index_at_or_after(bars: tuple[ReplayBar, ...], timestamp: UTCDateTime) -> int | None:
    for index, bar in enumerate(bars):
        if bar.bar_timestamp >= timestamp:
            return index
    return None


def _window_indices(
    bars: tuple[ReplayBar, ...],
    start: UTCDateTime,
    end: UTCDateTime | None,
    *,
    start_code: str,
    end_code: str,
    reasons: list[str],
) -> tuple[int | None, int | None]:
    if start < bars[0].bar_timestamp or start > bars[-1].bar_timestamp:
        reasons.append(start_code)
        return None, None
    start_index = _first_index_at_or_after(bars, start)
    if start_index is None:
        reasons.append(start_code)
        return None, None
    if end is None:
        end_index = len(bars) - 1
    elif end < bars[0].bar_timestamp or end > bars[-1].bar_timestamp:
        reasons.append(end_code)
        return start_index, None
    else:
        end_index = _last_index_at_or_before(bars, end)  # type: ignore
    if end_index is None or end_index < start_index:
        reasons.append("test_window_inverted")
        return start_index, end_index
    return start_index, end_index


def _scan_plan(
    plan: WalkForwardPlan,
    dataset: ReplayDataset,
    reasons: list[str],
) -> None:
    if not plan.windows:
        reasons.append("empty_walk_forward_plan")
        return
    bars = dataset.bars
    previous_test_end: int | None = None
    previous_embargo = 0
    for window in plan.windows:
        if window.purge_bars < 0:
            reasons.append("bad_purge")
        if window.embargo_bars < 0:
            reasons.append("bad_embargo")
        if window.train_start is not None and window.train_end is not None:
            train_start, train_end = _window_indices(
                bars,
                window.train_start,
                window.train_end,
                start_code="train_start_not_in_dataset",
                end_code="train_end_not_in_dataset",
                reasons=reasons,
            )
        else:
            train_start, train_end = None, None
        test_start, test_end = _window_indices(
            bars,
            window.test_start,
            window.test_end,
            start_code="test_start_not_in_dataset",
            end_code="test_end_not_in_dataset",
            reasons=reasons,
        )
        if train_end is not None and test_start is not None:
            actual_purge = test_start - train_end - 1
            if actual_purge < window.purge_bars:
                reasons.append("insufficient_purge_gap")
            if actual_purge < 0:
                reasons.append("train_test_overlap")
        if previous_test_end is not None and train_start is not None:
            actual_embargo = train_start - previous_test_end - 1
            if actual_embargo < previous_embargo:
                reasons.append("insufficient_embargo_gap")
        if previous_test_end is not None and test_start is not None:
            if test_start <= previous_test_end:
                reasons.append("walk_forward_test_overlap")
        if test_start is not None and test_end is not None and test_end < test_start:
            reasons.append("walk_forward_window_inverted")
        previous_test_end = test_end
        previous_embargo = window.embargo_bars


def _overlapping_label_protection(
    train_end: int | None,
    test_start: int | None,
    label_horizon_bars: int,
    embargo_bars: int,
    reasons: list[str],
) -> None:
    """If labels overlap the purge gap, require extra embargo beyond horizon."""
    if train_end is None or test_start is None:
        return
    if label_horizon_bars <= 0:
        return
    gap = test_start - train_end - 1
    if label_horizon_bars > gap:
        required = label_horizon_bars - gap
        if embargo_bars < required:
            reasons.append("overlapping_label_protection_failed")


def scan_leakage(
    experiment: StrategyExperiment,
    dataset: ReplayDataset | None = None,
    walk_forward_plan: WalkForwardPlan | None = None,
    *,
    label_horizon_bars: int = 0,
) -> LeakageScanResult:
    reasons: list[str] = []
    horizon_end = experiment.test_end or experiment.test_start
    if horizon_end > experiment.dataset_cutoff:
        reasons.append("dataset_cutoff_violation")
    if experiment.train_start is not None and experiment.train_end is not None:
        if not (experiment.train_start < experiment.train_end <= experiment.test_start):
            reasons.append("train_test_overlap")
    if experiment.purge_bars < 0:
        reasons.append("bad_purge")
    if experiment.embargo_bars < 0:
        reasons.append("bad_embargo")
    if experiment.dataset_cutoff < experiment.test_start:
        reasons.append("dataset_cutoff_before_test_start")
    if experiment.train_end is not None and experiment.dataset_cutoff < experiment.train_end:
        reasons.append("dataset_cutoff_before_train_end")
    if dataset is not None and not reasons:
        bars = dataset.bars
        manifest = dataset.manifest
        if manifest.dataset_id != experiment.dataset_manifest_id:
            reasons.append("dataset_manifest_mismatch")
        if manifest.dataset_version != experiment.dataset_version:
            reasons.append("dataset_version_mismatch")
        if experiment.train_start is not None and experiment.train_end is not None:
            train_start, train_end = _window_indices(
                bars,
                experiment.train_start,
                experiment.train_end,
                start_code="train_start_not_in_dataset",
                end_code="train_end_not_in_dataset",
                reasons=reasons,
            )
        else:
            train_start, train_end = None, None
        test_start, test_end = _window_indices(
            bars,
            experiment.test_start,
            experiment.test_end,
            start_code="test_start_not_in_dataset",
            end_code="test_end_not_in_dataset",
            reasons=reasons,
        )
        used_indices = [
            index
            for start_index, end_index in (
                (train_start, train_end),
                (test_start, test_end),
            )
            if start_index is not None and end_index is not None
            for index in range(start_index, end_index + 1)
        ]
        if any(bars[index].bar_timestamp > experiment.dataset_cutoff for index in used_indices):
            reasons.append("dataset_cutoff_violation")
        if train_end is not None and test_start is not None:
            actual_purge = test_start - train_end - 1
            if actual_purge < experiment.purge_bars:
                reasons.append("insufficient_purge_gap")
            _overlapping_label_protection(
                train_end, test_start, label_horizon_bars, experiment.embargo_bars, reasons
            )
        elif label_horizon_bars > 0 and train_end is None:
            pass
        if walk_forward_plan is not None:
            _scan_plan(walk_forward_plan, dataset, reasons)
            if label_horizon_bars > 0:
                for window in walk_forward_plan.windows:
                    if window.train_end is not None and window.test_start is not None:
                        tr_e = _last_index_at_or_before(bars, window.train_end)
                        te_s = _first_index_at_or_after(bars, window.test_start)
                        if tr_e is not None and te_s is not None:
                            _overlapping_label_protection(
                                tr_e, te_s, label_horizon_bars, window.embargo_bars, reasons
                            )
    elif walk_forward_plan is not None and dataset is None:
        reasons.append("dataset_required_for_walk_forward_scan")
    status = LeakageScanStatus.PASS if not reasons else LeakageScanStatus.FAIL
    return LeakageScanResult(status=status, reason_codes=tuple(dict.fromkeys(reasons)))


def assert_leakage_pass(
    experiment: StrategyExperiment,
    dataset: ReplayDataset | None = None,
    walk_forward_plan: WalkForwardPlan | None = None,
    *,
    label_horizon_bars: int = 0,
) -> None:
    result = scan_leakage(
        experiment, dataset, walk_forward_plan, label_horizon_bars=label_horizon_bars
    )
    if result.status is not LeakageScanStatus.PASS:
        raise ValueError(f"leakage scan failed: {result.reason_codes}")


__all__ = ["LeakageScanResult", "assert_leakage_pass", "scan_leakage"]
