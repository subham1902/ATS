import React from "react";

export default function CapitalShowdownPage() {
  const strategies = [
    { id: "BIN_S01", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S02", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S03", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S04", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S05", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S06", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S07", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S08", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "BIN_S09", origin: "IMPORTED", marginStatus: "MARGIN_UNKNOWN" },
    { id: "S17", origin: "NATIVE", marginStatus: "MARGIN_UNKNOWN" },
  ];

  return (
    <div style={{ padding: "40px", fontFamily: "sans-serif", maxWidth: "1400px", margin: "0 auto" }}>
      <header style={{ marginBottom: "30px", borderBottom: "1px solid #e5e7eb", paddingBottom: "20px" }}>
        <h1 style={{ margin: 0, fontSize: "28px", fontWeight: "800", color: "#111827" }}>
          ATS-CAP-01: ₹30,000 Capital-Constrained Showdown
        </h1>
        <p style={{ marginTop: "10px", color: "#4b5563", fontSize: "14px" }}>
          Combined view of Historical 15m Performance and 15m Live Observation under strict capital limits.
        </p>
      </header>

      <div style={{ display: "flex", gap: "20px", marginBottom: "30px" }}>
        <div
          style={{ padding: "15px", background: "#fef3c7", borderRadius: "8px", flex: 1, border: "1px solid #fde68a" }}
        >
          <h3 style={{ margin: "0 0 10px 0", color: "#92400e", fontSize: "14px" }}>Experiment Scope</h3>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "#b45309", fontSize: "13px" }}>
            <li>Timeframe: 15-Minute Base</li>
            <li>Capital Limit: ₹30,000.00</li>
            <li>Cost Regimen: PIT V3 (Brokerage, Taxes, Slippage)</li>
          </ul>
        </div>
        <div
          style={{ padding: "15px", background: "#fee2e2", borderRadius: "8px", flex: 1, border: "1px solid #fecaca" }}
        >
          <h3 style={{ margin: "0 0 10px 0", color: "#991b1b", fontSize: "14px" }}>System Blockers</h3>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "#b91c1c", fontSize: "13px" }}>
            <li>Data Blocker: MCX GOLDM 5m/1h and OI feeds unavailable in 15m CSV.</li>
            <li>Capital Blocker: Margin Unknown (requires &gt; ₹30,000 for standard MCX).</li>
            <li>Live Status: BLOCKED (Market Closed/Unconfigured)</li>
          </ul>
        </div>
      </div>

      <div style={{ overflowX: "auto", border: "1px solid #e5e7eb", borderRadius: "8px" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left" }}>
          <thead style={{ background: "#f9fafb", borderBottom: "1px solid #e5e7eb" }}>
            <tr>
              <th style={{ padding: "12px" }}>Strategy</th>
              <th style={{ padding: "12px" }}>Origin</th>
              <th style={{ padding: "12px", textAlign: "right" }}>Start Cap</th>
              <th style={{ padding: "12px", textAlign: "right" }}>End Cap</th>
              <th style={{ padding: "12px", textAlign: "right" }}>Return %</th>
              <th style={{ padding: "12px", textAlign: "right" }}>Trades</th>
              <th style={{ padding: "12px", textAlign: "right" }}>Win %</th>
              <th style={{ padding: "12px", textAlign: "right" }}>Net P&L</th>
              <th style={{ padding: "12px", textAlign: "center" }}>Margin Status</th>
              <th style={{ padding: "12px", textAlign: "center" }}>Live Signal</th>
              <th style={{ padding: "12px", textAlign: "center" }}>Evidence Status</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s, idx) => (
              <tr key={s.id} style={{ borderBottom: idx < strategies.length - 1 ? "1px solid #f3f4f6" : "none" }}>
                <td style={{ padding: "12px", fontWeight: "600", color: "#111827" }}>{s.id}</td>
                <td style={{ padding: "12px", color: "#6b7280" }}>{s.origin}</td>
                <td style={{ padding: "12px", textAlign: "right", fontFamily: "monospace" }}>₹30,000</td>
                <td style={{ padding: "12px", textAlign: "right", fontFamily: "monospace" }}>₹30,000</td>
                <td style={{ padding: "12px", textAlign: "right" }}>0.00%</td>
                <td style={{ padding: "12px", textAlign: "right" }}>0</td>
                <td style={{ padding: "12px", textAlign: "right" }}>0.00%</td>
                <td style={{ padding: "12px", textAlign: "right", fontFamily: "monospace" }}>₹0</td>
                <td style={{ padding: "12px", textAlign: "center" }}>
                  <span
                    style={{
                      background: "#fee2e2",
                      color: "#991b1b",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: "700",
                    }}
                  >
                    {s.marginStatus}
                  </span>
                </td>
                <td style={{ padding: "12px", textAlign: "center" }}>0</td>
                <td style={{ padding: "12px", textAlign: "center" }}>
                  <span
                    style={{
                      background: "#fef3c7",
                      color: "#92400e",
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontSize: "11px",
                      fontWeight: "700",
                    }}
                  >
                    DATA_BLOCKED
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
