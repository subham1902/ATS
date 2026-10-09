"""Semantic fault tests for the isolated small-account research engine."""

import unittest

import numpy as np
import pandas as pd
from gold_triple_small_account import replay, tactical


class SmallAccountSemantics(unittest.TestCase):
    def run_case(
        self,
        bid,
        *,
        entries=None,
        capital=1000.0,
        risk=0.01,
        protect=False,
        rr=4.0,
        leverage=100.0,
        updates=None,
        times=None,
        snap_target=False,
    ):
        b = np.asarray(bid, dtype=float)
        a = b + 0.2
        n = len(b)
        idx = (
            pd.date_range("2025-01-01T06:00:00Z", periods=n, freq="min") if times is None else times
        )
        seconds = idx.astype("int64").to_numpy() // 10**9
        signals = np.zeros((n, 3, 5))
        for minute, strategy, side, stop, parent in entries or [(0, 0, 1, 95.0, 1)]:
            signals[minute, strategy] = [side, stop, 3.0, parent, 100.0]
        u = np.full((n, 4), np.nan) if updates is None else updates
        return replay(
            b,
            a,
            seconds,
            seconds // 86400,
            (idx.year * 12 + idx.month).to_numpy(),
            signals,
            u,
            capital,
            risk,
            rr,
            protect,
            240,
            22.0,
            1.0,
            leverage,
            0.01,
            0.01,
            100.0,
            0.01,
            np.ones(3),
            snap_target,
        )

    def test_grid_target_is_conservative_for_both_sides(self):
        for side, stop, high, low in ((1, 95.0, 111.0, 99.0), (-1, 105.2, 101.0, 89.0)):
            with self.subTest(side=side):
                quotes = [[100.003, high, low, 100.003]]
                exact = self.run_case(quotes, entries=[(0, 0, side, stop, 1)], rr=2.0)[0][0]
                native = self.run_case(
                    quotes, entries=[(0, 0, side, stop, 1)], rr=2.0, snap_target=True
                )[0][0]
                self.assertAlmostEqual(native[5] / 0.01, round(native[5] / 0.01))
                self.assertLessEqual(side * (native[5] - native[4]), side * (exact[5] - exact[4]))
                self.assertLess(abs(native[5] - exact[5]), 0.01 + 1e-9)

    def test_default_replay_preserves_frozen_non_grid_target(self):
        trade = self.run_case([[100.003, 111, 99, 100.003]], rr=2.0)[0][0]
        self.assertNotAlmostEqual(trade[5] / 0.01, round(trade[5] / 0.01))

    def test_long_first_minute_peak_protects_only_next_minute(self):
        result = self.run_case([[100, 112, 99, 110], [110, 111, 99, 109]], protect=True)
        trades = result[0]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0, 1], 0)
        self.assertEqual(trades[0, 2], 1)
        self.assertAlmostEqual(trades[0, 5], 100.2 + 0.1 * 5.2)
        self.assertGreater(trades[0, 7], 0)

    def test_short_first_minute_peak_protects_only_next_minute(self):
        result = self.run_case(
            [[100, 101, 90, 90], [90, 101, 89, 92]],
            entries=[(0, 0, -1, 105.2, 1)],
            protect=True,
        )
        trades = result[0]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0, 2], 1)
        self.assertAlmostEqual(trades[0, 5], 100 - 0.1 * 5.2)
        self.assertGreater(trades[0, 7], 0)

    def test_entry_minute_ambiguous_stop_target_fills_stop_first(self):
        result = self.run_case([[100, 125, 90, 110]])
        trades = result[0]
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0, 1], trades[0, 2])
        self.assertAlmostEqual(trades[0, 5], 95.0)
        self.assertEqual(trades[0, 8], 1)
        self.assertEqual(trades[0, 12], 1)

    def test_minimum_lot_never_overrides_planned_risk(self):
        result = self.run_case([[100, 101, 99, 100]], capital=500.0, risk=0.005)
        trades, _, balance, _, rejects, position, _ = result
        self.assertEqual(len(trades), 0)
        self.assertEqual(rejects[1], 1)
        self.assertEqual(position[0], -1)
        self.assertEqual(balance[-1], 500.0)

    def test_adverse_long_gap_fills_executable_open_and_reports_breach(self):
        result = self.run_case([[100, 101, 99, 100], [50, 51, 49, 50]])
        trades, _, _, booked, _, _, _ = result
        self.assertEqual(len(trades), 1)
        self.assertAlmostEqual(trades[0, 5], 50.0)
        self.assertLess(booked[1, 0], -0.03)

    def test_adverse_short_gap_uses_ask_open(self):
        result = self.run_case(
            [[100, 101, 99, 100], [110, 111, 109, 110]],
            entries=[(0, 0, -1, 105.2, 1)],
        )
        self.assertEqual(len(result[0]), 1)
        self.assertAlmostEqual(result[0][0, 5], 110.2)
        self.assertLess(result[0][0, 7], 0)

    def test_intrabar_profit_cannot_fund_same_open_reentry(self):
        result = self.run_case(
            [[100, 101, 99, 100], [100, 125, 99, 120]],
            entries=[(0, 0, 1, 95.0, 1), (1, 1, 1, 95.0, 2)],
        )
        trades, _, _, _, _, position, _ = result
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0, 0], 1)
        self.assertEqual(position[0], -1)

    def test_two_booked_losses_stop_new_trades_for_day(self):
        b = np.tile([100.0, 101.0, 99.0, 100.0], (33, 1))
        b[[0, 16], 2] = 95.0
        result = self.run_case(
            b,
            entries=[(0, 0, 1, 96.0, 1), (16, 0, 1, 96.0, 2), (32, 0, 1, 96.0, 3)],
        )
        self.assertEqual(len(result[0]), 2)
        self.assertTrue((result[0][:, 7] < 0).all())
        self.assertEqual(result[5][0], -1)

    def test_gap_exhausted_daily_budget_blocks_later_signal(self):
        b = np.tile([100.0, 101.0, 99.0, 100.0], (17, 1))
        b[1] = [70.0, 71.0, 69.0, 70.0]
        result = self.run_case(b, entries=[(0, 0, 1, 96.0, 1), (16, 0, 1, 96.0, 2)])
        self.assertEqual(len(result[0]), 1)
        self.assertGreater(result[4][3], 0)
        self.assertLess(result[3][1, 0], -0.03)
        self.assertEqual(result[5][0], -1)

    def test_two_percent_second_entry_uses_remaining_daily_budget(self):
        b = np.tile([100.0, 101.0, 99.0, 100.0], (17, 1))
        b[[0, 16], 2] = 95.0
        result = self.run_case(
            b,
            entries=[(0, 0, 1, 96.0, 1), (16, 0, 1, 96.0, 2)],
            risk=0.02,
        )
        trades = result[0]
        self.assertEqual(len(trades), 2)
        remaining_daily_budget = 0.025 * 1000.0 + trades[0, 7]
        self.assertGreater(remaining_daily_budget, 0)
        self.assertLess(trades[1, 6], trades[0, 6])
        self.assertLessEqual(trades[1, 9], remaining_daily_budget + 1e-9)
        self.assertAlmostEqual(trades[1, 4] - trades[1, 5], trades[0, 4] - trades[0, 5])
        self.assertGreaterEqual(result[3][:, 0].min(), -0.025 - 1e-9)

    def test_two_percent_daily_remainder_cannot_force_minimum_lot(self):
        b = np.tile([100.0, 101.0, 99.0, 100.0], (17, 1))
        b[[0, 16], 2] = 90.0
        result = self.run_case(
            b,
            entries=[(0, 0, 1, 91.4, 1), (16, 0, 1, 91.4, 2)],
            risk=0.02,
        )
        trades = result[0]
        self.assertEqual(len(trades), 1)
        remaining_daily_budget = 0.025 * 1000.0 + trades[0, 7]
        minimum_lot_risk = trades[0, 9] / trades[0, 6] * 0.01
        self.assertGreater(remaining_daily_budget, 0)
        self.assertLess(remaining_daily_budget, minimum_lot_risk)
        self.assertEqual(result[4][1], 1)
        self.assertEqual(result[5][0], -1)

    def test_new_day_does_not_reset_exhausted_monthly_budget(self):
        idx = pd.DatetimeIndex(
            pd.to_datetime(["2025-01-01T06:00:00Z", "2025-01-01T06:01:00Z", "2025-01-02T06:00:00Z"])
        )
        result = self.run_case(
            [[100, 101, 99, 100], [84.5, 85, 84, 84.5], [100, 101, 99, 100]],
            entries=[(0, 0, 1, 96.0, 1), (2, 0, 1, 96.0, 2)],
            risk=0.02,
            times=idx,
        )
        self.assertEqual(len(result[0]), 1)
        self.assertLess(result[3][1, 1], -0.06)
        self.assertEqual(result[3][2, 0], 0)
        self.assertLess(result[3][2, 1], -0.06)
        self.assertEqual(result[4][3], 1)
        self.assertEqual(result[5][0], -1)

    def test_no_artificial_last_bar_exit(self):
        result = self.run_case([[100, 101, 99, 100], [100, 101, 99, 100]])
        self.assertEqual(len(result[0]), 0)
        self.assertEqual(result[5][0], 0)
        self.assertLess(result[2][-1], 1000.0)
        self.assertLess(result[1][-1], result[2][-1])

    def test_margin_limit_rejects_otherwise_risk_feasible_entry(self):
        result = self.run_case([[100, 101, 99, 100]], leverage=0.1)
        self.assertEqual(len(result[0]), 0)
        self.assertEqual(result[4][2], 1)
        self.assertEqual(result[5][0], -1)

    def test_completed_tactical_signals_are_invariant_to_future_prices(self):
        idx = pd.date_range("2025-01-01T06:00:00Z", periods=180, freq="min")
        frame = pd.DataFrame(
            {
                "open": np.tile([100.0] * 5, 36),
                "high": 102.0,
                "low": 99.0,
                "close": np.tile([100.5] * 4 + [101.0], 36),
                "volume": 1.0,
            },
            index=idx,
        )
        parents = np.zeros((len(frame), 3, 5))
        parents[75, 0] = [1, 3, 95, 105, 100]
        first, _ = tactical(frame, parents, 1)
        changed = frame.copy()
        changed.loc[idx[100] :, ["open", "high", "low", "close"]] *= 3
        second, _ = tactical(changed, parents, 1)
        self.assertTrue((first[:101, 0, 0] != 0).any())
        np.testing.assert_equal(first[:101], second[:101])

    def test_m1_tactical_stop_excludes_entry_extrema_and_future_suffix(self):
        idx = pd.date_range("2025-01-01T06:00:00Z", periods=180, freq="min")
        frame = pd.DataFrame(
            {"open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1.0},
            index=idx,
        )
        parents = np.zeros((len(frame), 3, 5))
        parents[75, 0] = [1, 3, 95, 105, 100]
        first, first_updates = tactical(frame, parents, 1, bar_seconds=60)
        changed = frame.copy()
        changed.loc[idx[100] :, ["open", "high", "low", "close"]] = [200, 300, 0.1, 250]
        second, second_updates = tactical(changed, parents, 1, bar_seconds=60)
        self.assertEqual(first[100, 0, 0], 1)
        self.assertAlmostEqual(first[100, 0, 1], 99.0 - 0.1 * 3.0)
        np.testing.assert_equal(first[:101], second[:101])
        np.testing.assert_equal(first_updates[:101], second_updates[:101])
        self.assertNotEqual(first[101, 0, 1], second[101, 0, 1])

    def test_protected_long_and_short_exits_are_on_broker_tick_grid(self):
        for side, quotes, stop, expected in (
            (1, [[100, 112, 99, 110], [110, 111, 99, 109]], 94.97, 100.72),
            (-1, [[100, 101, 90, 90], [90, 101, 89, 92]], 105.23, 99.48),
        ):
            with self.subTest(side=side):
                result = self.run_case(quotes, entries=[(0, 0, side, stop, 1)], protect=True)
                self.assertEqual(len(result[0]), 1)
                exit_price = result[0][0, 5]
                self.assertAlmostEqual(exit_price, expected)
                self.assertAlmostEqual(exit_price / 0.01, round(exit_price / 0.01))


if __name__ == "__main__":
    unittest.main()
