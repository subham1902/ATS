import React from "react";
import { describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { SurvivalTelemetry, resolveSurvivalState } from "../SurvivalTelemetry";
import type { SurvivalTelemetryReadModel, RuntimeStatusReadModel, SystemReadModel } from "@ats/api-client";

describe("SurvivalTelemetry (OI3)", () => {
  it("renders truthful unknown / empty state when telemetry is null", () => {
    render(<SurvivalTelemetry telemetry={null} />);
    expect(
      screen.getByText(/No survival telemetry available · state unknown · not healthy/i)
    ).toBeInTheDocument();
  });

  it("renders canonical survival states, reason codes, and financial metrics", () => {
    const mockTelemetry: SurvivalTelemetryReadModel = {
      effective_survival_state: "SAFE",
      user_selected_mode: "NORMAL",
      effective_mode: "SAFE",
      reason_codes: ["SESSION_DRAWDOWN", "CALIBRATION_DEGRADED"],
      session_equity: "985000.00",
      hwm: "1000000.00",
      drawdown_fraction: "0.015",
      available_risk: "20000.00",
      open_positions: 1,
      new_entry_permission: false,
      reduction_permission: true,
      feed_healthy: true,
      broker_healthy: true,
      reconciliation_active: false,
      loss_state: "CAUTION",
      last_state_at: "2026-08-27T10:00:00Z",
    };

    render(<SurvivalTelemetry telemetry={mockTelemetry} />);

    expect(screen.getByText(/SAFE · Tightened Risk Envelopes/i)).toBeInTheDocument();
    expect(screen.getByText("SESSION_DRAWDOWN")).toBeInTheDocument();
    expect(screen.getByText("CALIBRATION_DEGRADED")).toBeInTheDocument();
    expect(screen.getByText(/₹9.*85.*000/)).toBeInTheDocument();
    expect(screen.getByText(/₹10?.*00.*000/)).toBeInTheDocument();
    expect(screen.getByText("-1.50%")).toBeInTheDocument();
    expect(screen.getByText("PROHIBITED")).toBeInTheDocument(); // new entry prohibited
  });

  it("resolveSurvivalState maps runtime states safely without inventing risk", () => {
    // 1. Halted state
    const haltedRuntime = {
      halted: true,
      session: { is_halted: true },
      trading_mode: { effective: "HALTED" },
    } as unknown as RuntimeStatusReadModel;
    expect(resolveSurvivalState(haltedRuntime, null)).toBe("HALTED");

    // 2. Normal state
    const normalRuntime = {
      halted: false,
      feed_healthy: true,
      broker_healthy: true,
      trading_mode: { effective: "NORMAL" },
      session: { can_enter: true, can_reduce: true },
    } as unknown as RuntimeStatusReadModel;
    const readySystem = {
      system_state: "READY",
      halted: false,
    } as unknown as SystemReadModel;
    expect(resolveSurvivalState(normalRuntime, readySystem)).toBe("NORMAL");

    // 3. Degraded / Safe state
    const degradedRuntime = {
      halted: false,
      feed_healthy: false,
      broker_healthy: true,
      trading_mode: { effective: "SAFE" },
    } as unknown as RuntimeStatusReadModel;
    expect(resolveSurvivalState(degradedRuntime, readySystem)).toBe("SAFE");

    // 4. Null state returns UNKNOWN
    expect(resolveSurvivalState(null, null)).toBe("UNKNOWN");
  });
});
