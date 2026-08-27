import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SystemHealthIndicator } from "../SystemHealthIndicator";

describe("canonical system indicators", () => {
  it.each(["HEALTHY", "READY", "ACTIVE", "DEGRADED", "STALE", "UNKNOWN", "BLOCKED", "HALTED", "OFFLINE"] as const)("renders %s with text and an accessible label", (state) => {
    render(<SystemHealthIndicator state={state} label="FEED" detail="Canonical state" />);
    expect(screen.getByText(state)).toBeInTheDocument();
    expect(screen.getByLabelText(new RegExp(`FEED ${state}`))).toBeInTheDocument();
  });
});
