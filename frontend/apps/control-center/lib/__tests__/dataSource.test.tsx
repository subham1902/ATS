import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { DataSourceProvider, requestedSourceLabel, useDataSource } from "../dataSource";

function Reader() {
  const { requestedSource } = useDataSource();
  return <span data-testid="requested">{requestedSource}</span>;
}

function Writer() {
  const { setRequestedSource } = useDataSource();
  return <button onClick={() => setRequestedSource("OPEN_TERMINAL")}>switch</button>;
}

describe("data source request", () => {
  it("defaults to the broker feed and labels both options", () => {
    render(
      <DataSourceProvider>
        <Reader />
      </DataSourceProvider>,
    );
    expect(screen.getByTestId("requested").textContent).toBe("BROKER_LIVE");
    expect(requestedSourceLabel("BROKER_LIVE")).toBe("BROKER LIVE (Upstox)");
    expect(requestedSourceLabel("OPEN_TERMINAL")).toBe("OPEN TERMINAL (Ref)");
  });

  it("propagates an explicit request without claiming feed state", () => {
    render(
      <DataSourceProvider>
        <Reader />
        <Writer />
      </DataSourceProvider>,
    );
    fireEvent.click(screen.getByText("switch"));
    expect(screen.getByTestId("requested").textContent).toBe("OPEN_TERMINAL");
  });

  it("fails fast outside the provider instead of silently defaulting", () => {
    expect(() => render(<Reader />)).toThrow(/DataSourceProvider/);
  });
});
