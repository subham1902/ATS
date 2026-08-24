"""Walk-forward deterministic plans and splitter."""

from __future__ import annotations

from uuid import uuid5

from ats.market.replay.models import ReplayDataset

from .types import WalkForwardPlan, WalkForwardWindow


def build_rolling_plan(
    *,
    dataset: ReplayDataset,
    train_bars: int,
    test_bars: int,
    purge_bars: int,
    embargo_bars: int,
    plan_id_seed: str = "plan",
    mode: str = "rolling",
) -> WalkForwardPlan:
    """Build deterministic rolling walk-forward plan over ReplayDataset bars.

    No random shuffle. Chronological windows with purge/embargo gaps.
    """
    bars = dataset.bars
    windows: list[WalkForwardWindow] = []
    step = test_bars  # rolling step = test length
    # Need at least train+purge+test bars to create a window
    idx = 0
    while idx + train_bars + purge_bars + test_bars <= len(bars):
        train_start_bar = bars[idx]
        train_end_bar = bars[idx + train_bars - 1]
        test_start_bar = bars[idx + train_bars + purge_bars]
        test_end_bar = bars[idx + train_bars + purge_bars + test_bars - 1]
        # Embargo after test: skip embargo before next train window
        # For rolling, next train starts after test+embargo
        window = WalkForwardWindow(
            window_id=uuid5(dataset.manifest.dataset_id, f"{plan_id_seed}-{idx}"),
            train_start=train_start_bar.bar_timestamp,
            train_end=train_end_bar.bar_timestamp,
            test_start=test_start_bar.bar_timestamp,
            test_end=test_end_bar.bar_timestamp,
            purge_bars=purge_bars,
            embargo_bars=embargo_bars,
        )
        windows.append(window)
        idx += step + embargo_bars
        if mode == "expanding":
            # Expanding: train_start fixed at 0, grow window.
            # For v1 keep rolling; expanding not required now.
            # Keep deterministic step; train_bars would grow.
            pass
        if len(windows) > 100:
            break  # safety bound
    plan = WalkForwardPlan(
        plan_id=uuid5(dataset.manifest.dataset_id, plan_id_seed),
        windows=tuple(windows),
        mode=mode,
    )
    plan.validate_chronology()
    return plan


def split_for_experiment(
    plan: WalkForwardPlan,
    window_index: int,
) -> WalkForwardWindow:
    if window_index < 0 or window_index >= len(plan.windows):
        raise IndexError("window_index out of range")
    return plan.windows[window_index]


__all__ = ["build_rolling_plan", "split_for_experiment"]
