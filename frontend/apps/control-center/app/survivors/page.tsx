"use client";
import React from "react";
import { Card } from "@ats/ui";

export default function SurvivorsPage() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Survivor Portfolio V1</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
          Empirical survivors passing the 10-point gate across walk-forward and sealed holdout evaluations.
        </p>
      </div>

      {/* Primary Verdict Card */}
      <div
        style={{
          background: "#fef2f2",
          border: "1px solid #fecaca",
          borderRadius: 12,
          padding: 20,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20, fontWeight: 900, color: "#991b1b" }}>VERDICT: NO_SURVIVORS (0 / 5)</span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: "#fee2e2",
                color: "#991b1b",
                padding: "3px 8px",
                borderRadius: 999,
                border: "1px solid #fca5a5",
              }}
            >
              COUNT NEVER FORCED
            </span>
          </div>
          <span style={{ fontSize: 12, fontFamily: "monospace", color: "#6b7280" }}>
            Generated: 2026-09-20T14:45:00Z
          </span>
        </div>

        <p style={{ margin: 0, fontSize: 13, color: "#7f1d1d", lineHeight: 1.5 }}>
          Every legitimate OHLCV-evaluable strategy family (S01, S02, S03, S04, S30, S34 plus baselines B01–B04)
          produced negative net expectancy at base cost (2.5 bps) and under 1.5x / 2.0x cost stress across 5m, 15m, and
          1h reference gold series. Several families also failed on sealed holdout after passing dev. This independently
          reproduces the platform’s own STRAT-02 verdict (20 strategies REJECTED under MCX PIT V3 costs) on a different
          dataset.
        </p>

        <div style={{ fontSize: 12, color: "#991b1b", fontWeight: 600 }}>
          Per mission rules, the survivor count was NOT inflated to reach 3–5. Zero is the honest result. No strategy is
          handed to shadow collection on the strength of reference-data results.
        </div>
      </div>

      {/* 10-Point Gate Rules */}
      <Card title="10-Point Survivor Selection Gate">
        <ol
          style={{
            margin: 0,
            paddingLeft: 20,
            fontSize: 13,
            color: "#374151",
            display: "flex",
            flexDirection: "column",
            gap: 6,
          }}
        >
          <li>Dev net expectancy &gt; 0 after PIT transaction costs (base 2.5 bps round trip)</li>
          <li>Net expectancy &gt; 0 at 2.0x cost stress (5.0 bps round trip)</li>
          <li>Walk-forward net expectancy &gt; 0 across out-of-sample folds</li>
          <li>At least 3 of 4 walk-forward folds positive (temporal stability)</li>
          <li>Worst parameter-perturbation (±20%) net expectancy &gt; 0</li>
          <li>+1 bar execution delay net expectancy &gt; 0 (latency robustness)</li>
          <li>Profit factor &gt; 1.05 after all costs</li>
          <li>Sealed holdout net expectancy &ge; 0 (evaluated strictly once)</li>
          <li>Net expectancy excluding single best trade &gt; 0 (no outlier reliance)</li>
          <li>Minimum 20 trades in development split</li>
        </ol>
      </Card>

      {/* Governed Next Actions */}
      <Card title="Governed Next Action & Data Unlocks">
        <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.6 }}>
          <p style={{ margin: "0 0 8px" }}>
            <strong>Blocker:</strong> MCX GOLDM canonical historical intraday data with Open Interest (OI) is currently
            absent locally. All local reference series (5m Yahoo, 15m/1h RefB) lack Open Interest.
          </p>
          <p style={{ margin: "0 0 8px" }}>
            <strong>Action:</strong> Admit S34 (regime router) plus S01/S02/S03 to a governed development loop ONLY
            after MCX GOLDM historical intraday data with Volume and OI is ingested; re-run the pipeline unchanged on
            GOLDM truth with the sealed holdout intact.
          </p>
          <p style={{ margin: 0 }}>
            <strong>S17 Status:</strong> S17 (Price x OI x Volume State Machine) remains VALIDATED in registry;
            evaluated live-only via Upstox V3 stream; prospective evidence collection sequence untouched.
          </p>
        </div>
      </Card>
    </div>
  );
}
