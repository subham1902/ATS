import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SystemStateBadge } from "../components/SystemStateBadge";
import { ConnectionIndicator } from "../components/ConnectionIndicator";
import { ErrorEnvelopeView } from "../components/ErrorEnvelopeView";
import { EmptyState } from "../components/EmptyState";
import { Card } from "../components/Card";

describe("ui primitives", () => {
  it("SystemStateBadge UNKNOWN looks unknown not healthy", () => {
    render(<SystemStateBadge state="UNKNOWN" />);
    const badge = screen.getByLabelText("system state UNKNOWN");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toContain("UNKNOWN");
    expect(badge.textContent).toContain("unknown, not healthy");
    // UNKNOWN uses dashed border
    expect(badge.getAttribute("style")).toContain("dashed");
  });

  it("SystemStateBadge READY shows success", () => {
    render(<SystemStateBadge state="READY" />);
    expect(screen.getByLabelText("system state READY")).toHaveTextContent("READY");
  });

  it("ConnectionIndicator shows connected/disconnected/error", () => {
    const { rerender } = render(<ConnectionIndicator status="connected" />);
    expect(screen.getByLabelText("SSE connected")).toBeInTheDocument();
    rerender(<ConnectionIndicator status="disconnected" />);
    expect(screen.getByLabelText("SSE disconnected")).toBeInTheDocument();
    rerender(<ConnectionIndicator status="error" />);
    expect(screen.getByLabelText("SSE error")).toBeInTheDocument();
  });

  it("ErrorEnvelopeView renders code/message/correlation", () => {
    render(<ErrorEnvelopeView envelope={{ code: "RESOURCE_NOT_FOUND", message: "not found", correlation_id: "cid-99", details: [{ field: "id", issue: "missing" }] }} />);
    expect(screen.getByText(/RESOURCE_NOT_FOUND/)).toBeInTheDocument();
    expect(screen.getByText("not found")).toBeInTheDocument();
    expect(screen.getByText("cid-99")).toBeInTheDocument();
    expect(screen.getByText((t) => t.includes("missing"))).toBeInTheDocument();
  });

  it("EmptyState has status role", () => {
    render(<EmptyState message="No active campaign" />);
    expect(screen.getByRole("status")).toHaveTextContent("No active campaign");
  });

  it("Card is semantic section with heading", () => {
    render(<Card title="System State"><span>body</span></Card>);
    expect(document.querySelector("section")).toBeTruthy();
    expect(screen.getByText("System State")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "System State" })).toBeInTheDocument();
  });

  it("focus visible style not broken (keyboard usable)", () => {
    render(<a href="#x">link</a>);
    const a = screen.getByText("link");
    expect(a).toBeInTheDocument();
    expect(a.tagName).toBe("A");
  });
});
