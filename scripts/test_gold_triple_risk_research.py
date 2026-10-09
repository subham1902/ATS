"""Fault checks for offline research; run with its isolated Python environment."""

import unittest

import numpy as np
import pandas as pd
from gold_triple_risk_research import metrics, replay, rma


class ResearchSemantics(unittest.TestCase):
    def run_case(
        self,
        quotes,
        capital=100000.0,
        risk=0.005,
        times=None,
        signal_kind=1,
        swap=0.0,
        second_signal=False,
    ):
        n = len(quotes)
        b = np.asarray(quotes, dtype=float)
        a = b + 0.2
        idx = (
            pd.date_range("2025-01-01", periods=n, freq="min", tz="UTC") if times is None else times
        )
        sec = idx.astype("int64").to_numpy() // 10**9
        sig = np.zeros((n, 3, 5))
        sig[0, signal_kind] = [1, 3, 96, 105, 100]
        if second_signal:
            sig[1, signal_kind] = sig[0, signal_kind]
        updates = np.full((n, 5), np.nan)
        result = replay(
            b,
            a,
            sec,
            sec // 86400,
            (idx.year * 12 + idx.month).to_numpy(),
            idx.dayofweek.to_numpy(),
            sig,
            updates,
            capital,
            risk,
            0.015,
            50.0,
            30.0,
            2.0,
            3.0,
            22.0,
            swap,
            1.0,
            np.ones(3),
        )
        return result, idx

    def test_wilder_sma_seed(self):
        result = rma(np.arange(1.0, 17.0), 14)
        self.assertTrue(np.isnan(result[12]))
        self.assertEqual(result[13], 7.5)
        self.assertAlmostEqual(result[14], (7.5 * 13 + 15) / 14)

    def test_adverse_gap_fills_at_observed_open(self):
        (t, e, r, rej, amb, p, booked), idx = self.run_case([[100, 101, 99, 100], [50, 51, 49, 50]])
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0, 5], 50.0)
        self.assertGreater(metrics(t, e, r, idx, 100000.0, booked)["daily_breaches"], 0)

    def test_same_minute_stop_target_is_stop_first(self):
        (t, e, r, rej, amb, p, booked), idx = self.run_case(
            [[100, 101, 99, 100], [100, 115, 90, 100]]
        )
        self.assertEqual(amb, 1)
        self.assertEqual(t[0, 8], 1)
        self.assertLess(t[0, 7], 0)

    def test_minimum_lot_does_not_override_risk(self):
        (t, e, r, rej, amb, p, booked), _ = self.run_case(
            [[100, 101, 99, 100], [100, 101, 99, 100]], capital=1000.0, risk=0.0025, signal_kind=2
        )
        self.assertEqual(len(t), 0)
        self.assertEqual(rej, 1)
        self.assertFalse(p[:, 0].any())

    def test_no_artificial_final_exit(self):
        (t, e, r, rej, amb, p, booked), _ = self.run_case(
            [[100, 101, 99, 100], [100, 101, 99, 100]], signal_kind=2
        )
        self.assertEqual(len(t), 0)
        self.assertEqual(p[2, 0], 1)

    def test_stop_is_active_in_entry_minute(self):
        (t, e, r, rej, amb, p, booked), _ = self.run_case([[100, 115, 90, 100]])
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0, 1], t[0, 2])
        self.assertEqual(t[0, 8], 1)

    def test_intrabar_close_cannot_allow_open_time_reentry(self):
        (t, e, r, rej, amb, p, booked), _ = self.run_case(
            [[100, 101, 99, 100], [100, 115, 90, 100]], second_signal=True
        )
        self.assertEqual(len(t), 1)
        self.assertEqual(t[0, 1], 0)
        self.assertFalse(p[:, 0].any())

    def test_month_rollover_keeps_financing_charge(self):
        idx = pd.DatetimeIndex(pd.to_datetime(["2025-01-31T23:59:00Z", "2025-02-01T00:00:00Z"]))
        (t, e, r, rej, amb, p, booked), _ = self.run_case(
            [[100, 101, 99, 100], [100, 101, 99, 100]], signal_kind=2, swap=15.0, times=idx
        )
        self.assertLess(booked[1, 1], 0)
        self.assertAlmostEqual(r[0] - r[1], p[2, 4] * 15.0)


if __name__ == "__main__":
    unittest.main()
