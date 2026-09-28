"use client";
import React, { useState } from "react";
import { Card } from "@ats/ui";

export default function ShadowPage() {
  const [recorderActive, setRecorderActive] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);

  const toggleRecorder = () => {
    setRecorderActive(!recorderActive);
    setNotice(
      !recorderActive
        ? "Shadow recorder enabled in research observation mode. (No paper execution authority granted)."
        : "Shadow recorder paused. Background telemetry intake suspended.",
    );
  };

  const requestReview = () => {
    setNotice(
      "Promotion review requested: S17 requires 20 resolved valid trades with Open Interest. Current support is 0/20. Promotion gate fails closed.",
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Shadow Calibration & Prospective Evaluation</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
          Safe observation of prospective strategy signals against live feeds without execution authority.
        </p>
      </div>

      {notice && (
        <div
          style={{
            padding: "10px 14px",
            background: "#eff6ff",
            color: "#1d4ed8",
            borderRadius: 8,
            border: "1px solid #bfdbfe",
            fontSize: 13,
          }}
        >
          {notice}
        </div>
      )}

      {/* S17 Calibration Progress Card (Phase 13) */}
      <Card title="S17 Price × OI × Volume State Machine — Prospective Calibration Status">
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 16, fontWeight: 800 }}>Calibration Progress</span>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: 999,
                  background: "#fee2e2",
                  color: "#991b1b",
                }}
              >
                0 / 20 Target Trades (0%)
              </span>
            </div>
            <span style={{ fontSize: 12, color: "#6b7280" }}>
              Registry Status: <strong>VALIDATED</strong>
            </span>
          </div>

          {/* Progress Bar */}
          <div style={{ width: "100%", height: 12, background: "#f3f4f6", borderRadius: 6, overflow: "hidden" }}>
            <div style={{ width: "0%", height: "100%", background: "#2563eb" }} />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 12,
              fontSize: 13,
            }}
          >
            <div>
              <div style={{ color: "#6b7280" }}>Resolved Valid</div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>0</div>
            </div>
            <div>
              <div style={{ color: "#6b7280" }}>Open Trades</div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>0</div>
            </div>
            <div>
              <div style={{ color: "#6b7280" }}>Invalid / Rejected</div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>0</div>
            </div>
            <div>
              <div style={{ color: "#6b7280" }}>Target Calibration Support</div>
              <div style={{ fontWeight: 700, fontSize: 16 }}>20 trades</div>
            </div>
            <div>
              <div style={{ color: "#6b7280" }}>Promotion State</div>
              <div style={{ fontWeight: 700, color: "#b91c1c" }}>FAILS_CLOSED_FOR_PAPER</div>
            </div>
            <div>
              <div style={{ color: "#6b7280" }}>A04 Governor State</div>
              <div style={{ fontWeight: 700, color: "#15803d" }}>ACTIVE</div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button
              type="button"
              onClick={toggleRecorder}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                background: recorderActive ? "#ef4444" : "#111827",
                color: "white",
                border: "none",
                cursor: "pointer",
              }}
            >
              {recorderActive ? "Pause Shadow Recorder" : "Enable Shadow Recorder"}
            </button>
            <button
              type="button"
              onClick={requestReview}
              style={{
                padding: "6px 12px",
                borderRadius: 6,
                fontSize: 12,
                fontWeight: 600,
                background: "white",
                color: "#374151",
                border: "1px solid #d1d5db",
                cursor: "pointer",
              }}
            >
              Request Promotion Review
            </button>
          </div>
        </div>
      </Card>

      {/* Shadow Invariant Rules */}
      <Card title="Shadow Governance Invariants">
        <div style={{ fontSize: 13, color: "#4b5563", lineHeight: 1.6 }}>
          <p style={{ margin: "0 0 6px" }}>
            1. <strong>ZERO Financial Authority:</strong> Shadow strategies cannot place orders, allocate capital, or
            mutate paper ledger state.
          </p>
          <p style={{ margin: "0 0 6px" }}>
            2. <strong>Fails Closed:</strong> A strategy remains in shadow calibration until N &ge; 20 verified
            out-of-sample forward trades are resolved with positive expectancy.
          </p>
          <p style={{ margin: 0 }}>
            3. <strong>Open Interest Prerequisite:</strong> Live signals require continuous Upstox V3 tick feed with
            Open Interest. When feed is disconnected, shadow recorder enters idle hold.
          </p>
        </div>
      </Card>
    </div>
  );
}
