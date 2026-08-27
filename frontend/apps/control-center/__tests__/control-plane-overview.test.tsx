import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ControlPlaneOverview, UNKNOWN_CONTROL_PLANE } from "../components/ControlPlaneOverview";

describe("Control Plane 2.0", () => {
  it("renders truthful unknown and offline intelligence state", () => {
    render(<ControlPlaneOverview state={UNKNOWN_CONTROL_PLANE} />);
    expect(screen.getByText("System / Session / Feed")).toBeInTheDocument();
    expect(screen.getAllByText("UNKNOWN").length).toBeGreaterThan(3);
    expect(screen.getByText(/CHAMPION NOT PROMOTED/)).toBeInTheDocument();
    expect(screen.getByText(/UNKNOWN is never treated as healthy/)).toBeInTheDocument();
  });

  it("separates user and effective mode and exposes no live authority", () => {
    const state = { ...UNKNOWN_CONTROL_PLANE, user_mode: "AGGRESSIVE" as const, effective_mode: "SAFE" as const, mode_reason: "HWM_DRAWDOWN" };
    const { container } = render(<ControlPlaneOverview state={state} />);
    expect(screen.getAllByText("AGGRESSIVE").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SAFE").length).toBeGreaterThan(0);
    expect(screen.getByText("HWM_DRAWDOWN")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/ENABLE LIVE|PLACE REAL ORDER/);
    expect(screen.queryByRole("button", { name: "FLATTEN" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "HALT" })).not.toBeInTheDocument();
  });

  it("states that chat changes are governed proposals", () => {
    render(<ControlPlaneOverview state={UNKNOWN_CONTROL_PLANE} />);
    expect(screen.getByText(/create a RuntimeChangeProposal/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Question" })).toBeDisabled();
  });
});
