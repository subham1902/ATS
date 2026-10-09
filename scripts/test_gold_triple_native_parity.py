"""Execute the native shared numerical core; no terminal or order calls.

Requires isolated ziglang==0.13.0. This tests compiled native rule fixtures,
not broker tick fills, historical clock correctness or end-to-end EA parity.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from gold_triple_small_account import base, tactical

HARNESS = r"""
#include <iostream>
#include <iomanip>
#include "SmallAccountRules.mqh"
int main() {
  std::cout << std::setprecision(17);
  char mode; std::cin >> mode;
  if (mode == 'T') {
    int side,seconds,lookback,n;long parent,decision;double level;
    std::cin >> side >> seconds >> lookback >> parent >> decision >> level >> n;
    std::vector<S1Bar> bars(n);
    for (auto &bar:bars) std::cin >> bar.t >> bar.o >> bar.h >> bar.l >> bar.c >> bar.count;
    ATSTacticalResult result{};
    bool valid=ATSTacticalCalculate(bars,n-1,seconds,lookback,side,parent,decision,level,result);
    std::cout << valid << ' ' << result.atr << ' ' << result.lower << ' ' << result.upper;
  } else if (mode == 'S') {
    double price,tick;int side;std::cin >> price >> side >> tick;
    std::cout << ATSSnapStop(price,side,tick) << ' ' << ATSSnapTarget(price,side,tick);
  } else if (mode == 'L') {
    double budget,loss,cost,step,minimum,maximum;
    std::cin >> budget >> loss >> cost >> step >> minimum >> maximum;
    std::cout << ATSProposalLots(budget,loss,cost,step,minimum,maximum);
  } else if (mode == 'W') {
    long utc;int strategy,begin,end,mask;std::cin >> utc >> strategy >> begin >> end >> mask;
    std::cout << ATSEntryWindow(utc,strategy,begin,end,mask);
  } else if (mode == 'P') {
    long candidate,previous;std::cin >> candidate >> previous;
    std::cout << ATSParentIsNewer(candidate,previous);
  } else if (mode == 'R') {
    S3Signal signal{};std::cin >> signal.level >> signal.close;
    std::cout << ATSS3RetestLevel(signal);
  } else if (mode == 'H') {
    int n;std::cin >> n;std::vector<S1Bar> bars(n);
    for (auto &bar:bars) std::cin >> bar.t >> bar.o >> bar.h >> bar.l >> bar.c >> bar.count;
    S3Signal signal{};
    bool valid=S3Calculate(bars,n-1,bars[n-1].t+14400,signal);
    std::cout << valid << ' ' << signal.side << ' ' << signal.atr
              << ' ' << ATSS3RetestLevel(signal);
  } else return 2;
  return std::cin.fail()?3:0;
}
"""


class NativeRuleParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="ats-native-parity-")
        folder = Path(cls.temporary.name)
        source = folder / "fixture.cpp"
        source.write_text(HARNESS, encoding="utf-8")
        cls.binary = folder / ("fixture.exe" if sys.platform == "win32" else "fixture")
        native = Path(__file__).resolve().parents[1] / "metatrader/Experts/ATSSmallAccount"
        command = [
            sys.executable,
            "-m",
            "ziglang",
            "c++",
            "-std=c++17",
            "-O0",
            "-I",
            str(native),
            str(source),
            "-o",
            str(cls.binary),
        ]
        if sys.platform == "win32":
            command.extend(["-target", "x86_64-windows-gnu"])
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            raise RuntimeError(f"Native fixture compilation failed: {result.stderr}")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def native(self, payload):
        result = subprocess.run(
            [str(self.binary)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        return [float(value) for value in result.stdout.split()]

    def test_shared_m1_m5_tactical_prices_and_wilder_atr_match_python(self):
        for seconds in (60, 300):
            for lookback in (1, 3):
                for side in (1, -1):
                    with self.subTest(seconds=seconds, lookback=lookback, side=side):
                        minutes = seconds // 60
                        idx = pd.date_range(
                            "2025-01-07T12:00:00Z", periods=21 * minutes + 1, freq="min"
                        )
                        bar = np.arange(len(idx)) // minutes
                        opening = 100.0 + 0.01 * (bar % 3)
                        close = opening + side * 0.5
                        frame = pd.DataFrame(
                            {
                                "open": opening,
                                "high": 102.0 + 0.05 * (bar % 5),
                                "low": 98.0 - 0.03 * (bar % 4),
                                "close": close,
                                "volume": 1.0,
                            },
                            index=idx,
                        )
                        parent_index = 18 * minutes
                        parents = np.zeros((len(frame), 3, 5))
                        parents[parent_index, 2] = [side, 3, 90, 110, 100]
                        signals, _ = tactical(frame, parents, lookback, seconds)
                        target = 21 * minutes
                        self.assertEqual(signals[target, 2, 0], side)
                        rows = []
                        for j in range(21):
                            chunk = frame.iloc[j * minutes : (j + 1) * minutes]
                            rows.append(
                                f"{int(chunk.index[0].timestamp())} {chunk.open.iloc[0]} "
                                f"{chunk.high.max()} {chunk.low.min()} {chunk.close.iloc[-1]} "
                                f"{minutes}"
                            )
                        payload = (
                            f"T {side} {seconds} {lookback} "
                            f"{int(idx[parent_index].timestamp())} {int(idx[target].timestamp())} "
                            "100 21\n" + "\n".join(rows)
                        )
                        valid, atr, lower, upper = self.native(payload)
                        self.assertEqual(valid, 1)
                        self.assertAlmostEqual(atr, signals[target, 2, 2], places=10)
                        self.assertAlmostEqual(
                            lower if side == 1 else upper, signals[target, 2, 1], places=10
                        )

    def test_incomplete_tactical_bar_and_missing_window_fail_closed(self):
        start = int(pd.Timestamp("2025-01-07T12:00:00Z").timestamp())
        for missing, last_count in ((False, 4), (True, 5)):
            with self.subTest(missing=missing, last_count=last_count):
                rows = []
                for j in range(21):
                    stamp = start + j * 300 - (300 if missing and j == 19 else 0)
                    rows.append(f"{stamp} 100 102 98 101 {last_count if j == 20 else 5}")
                result = self.native(
                    f"T 1 300 3 {start + 18 * 300} {start + 21 * 300} 100 21\n" + "\n".join(rows)
                )
                self.assertEqual(result[0], 0)

    def test_s3_retest_level_is_completed_close_not_prior_high(self):
        self.assertEqual(self.native("R 99.0 101.5"), [101.5])

    def test_shared_s3_h4_parent_gate_atr_and_retest_level_match_python(self):
        idx = pd.date_range("2025-01-01T00:00:00Z", periods=42 * 240 + 1, freq="min")
        bar = np.arange(len(idx)) // 240
        opening = 100.0 + 0.5 * bar
        close = np.where(bar == 41, 125.0, opening + 0.25)
        frame = pd.DataFrame(
            {
                "open": opening,
                "high": np.maximum(opening + 0.5, close + 0.1),
                "low": opening - 0.5,
                "close": close,
                "volume": 1.0,
            },
            index=idx,
        )
        parents, _ = base.signals(frame)
        self.assertEqual(parents[-1, 2, 0], 1)
        rows = []
        for j in range(42):
            chunk = frame.iloc[j * 240 : (j + 1) * 240]
            rows.append(
                f"{int(chunk.index[0].timestamp())} {chunk.open.iloc[0]} "
                f"{chunk.high.max()} {chunk.low.min()} {chunk.close.iloc[-1]} 240"
            )
        valid, side, atr, level = self.native("H 42\n" + "\n".join(rows))
        self.assertEqual(valid, 1)
        self.assertEqual(side, parents[-1, 2, 0])
        self.assertAlmostEqual(atr, parents[-1, 2, 1], places=10)
        self.assertEqual(level, parents[-1, 2, 4])
        self.assertEqual(level, 125.0)

    def test_latest_parent_order_rejects_older_and_duplicate_publication(self):
        self.assertEqual(self.native("P 200 100"), [1])
        self.assertEqual(self.native("P 100 100"), [0])
        self.assertEqual(self.native("P 99 100"), [0])

    def test_native_utc_session_weekday_and_strategy_close_boundaries(self):
        # Bit mask 28 is Tuesday/Wednesday/Thursday in MQL Sunday-first numbering.
        for stamp, strategy, expected in (
            ("2025-01-07T11:59:59Z", 2, 0),
            ("2025-01-07T12:00:00Z", 2, 1),
            ("2025-01-09T16:59:59Z", 2, 1),
            ("2025-01-09T17:00:00Z", 2, 0),
            ("2025-01-10T12:00:00Z", 2, 0),
        ):
            with self.subTest(stamp=stamp):
                epoch = int(pd.Timestamp(stamp).timestamp())
                self.assertEqual(self.native(f"W {epoch} {strategy} 12 17 28"), [expected])
        for stamp, expected in (("2025-01-07T17:14:59Z", 1), ("2025-01-07T17:15:00Z", 0)):
            epoch = int(pd.Timestamp(stamp).timestamp())
            self.assertEqual(self.native(f"W {epoch} 1 6 20 127"), [expected])

    def test_outward_stops_and_conservative_targets_use_exact_tick_grid(self):
        self.assertEqual(self.native("S 99.477 1 0.01"), [99.47, 99.47])
        self.assertEqual(self.native("S 100.723 -1 0.01"), [100.73, 100.73])
        self.assertEqual(self.native("S 100.72 1 0.01"), [100.72, 100.72])

    def test_minimum_lot_risk_and_nondivisor_volume_cap(self):
        self.assertEqual(self.native("L 2.5 520 22 0.01 0.01 100"), [0])
        self.assertAlmostEqual(self.native("L 1000 100 22 0.03 0.03 100")[0], 0.09)
        self.assertEqual(self.native("L 100 100 22 0.01 0.11 100"), [0])


if __name__ == "__main__":
    unittest.main()
