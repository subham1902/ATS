"use client";

import React, { useState } from "react";

type AIMode =
  | "Market Analyst"
  | "Gold Analyst"
  | "Capital Advisor"
  | "Live Coach"
  | "Strategy Analyst"
  | "Risk Analyst"
  | "Operations";

export function AICopilotPanel({ onClose }: { onClose?: () => void }) {
  const [mode, setMode] = useState<AIMode>("Gold Analyst");
  const [query, setQuery] = useState("");
  const [capitalInput, setCapitalInput] = useState("30000");
  const [riskProfile, setRiskProfile] = useState("Balanced");
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<any | null>(null);

  const quickPrompts = [
    {
      label: "💰 USD 30k Capital Feasibility",
      q: "I have USD 30,000. Show me available opportunities.",
      m: "Capital Advisor" as AIMode,
    },
    {
      label: "⚡ Live Coach: What is happening?",
      q: "What is happening right now with my trades?",
      m: "Live Coach" as AIMode,
    },
    { label: "🛑 Why aren't we trading?", q: "Why aren't we trading right now?", m: "Live Coach" as AIMode },
    { label: "🏆 What supports this Gold move?", q: "What supports this Gold move?", m: "Gold Analyst" as AIMode },
    { label: "🛡️ What is my current risk?", q: "What is my current risk?", m: "Live Coach" as AIMode },
  ];

  async function handleSend(customQuery?: string, customMode?: AIMode) {
    const q = customQuery || query;
    const m = customMode || mode;
    if (!q) return;

    setLoading(true);
    try {
      const res = await fetch("/v1/ai/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          mode: m,
          capital_input: parseFloat(capitalInput) || 30000.0,
          risk_profile: riskProfile,
        }),
      });
      const data = await res.json();
      setResponse(data);
    } catch (err: any) {
      setResponse({
        answer: `Error contacting ATS AI Service: ${err.message}`,
        model_used: "offline",
        provider: "none",
        deterministic_tools_invoked: [],
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      style={{
        background: "#0f172a",
        color: "#f8fafc",
        borderRadius: 12,
        border: "1px solid #1e293b",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 16,
        boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.4)",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: "1px solid #334155",
          paddingBottom: 12,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>🤖</span>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800 }}>ATS AI Copilot & Live Coach</h3>
            <span style={{ fontSize: 11, color: "#94a3b8" }}>
              Deterministic Read-Only Authority • Model: Local Ollama / ATS Calibration
            </span>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#94a3b8",
              cursor: "pointer",
              fontSize: 18,
              padding: "4px 8px",
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Mode Selector */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {(["Gold Analyst", "Capital Advisor", "Live Coach", "Market Analyst", "Risk Analyst"] as AIMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: "5px 12px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              border: mode === m ? "1px solid #38bdf8" : "1px solid #334155",
              background: mode === m ? "#0284c7" : "#1e293b",
              color: mode === m ? "#ffffff" : "#cbd5e1",
              transition: "all 0.15s ease",
            }}
          >
            {m}
          </button>
        ))}
      </div>

      {/* Capital Advisor Controls */}
      {mode === "Capital Advisor" && (
        <div
          style={{
            display: "flex",
            gap: 12,
            alignItems: "center",
            background: "#1e293b",
            padding: 12,
            borderRadius: 8,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700 }}>ACCOUNT CAPITAL (USD )</span>
            <input
              type="number"
              value={capitalInput}
              onChange={(e) => setCapitalInput(e.target.value)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                color: "#f8fafc",
                borderRadius: 6,
                padding: "4px 8px",
                fontSize: 13,
                width: 130,
              }}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 700 }}>RISK PROFILE</span>
            <select
              value={riskProfile}
              onChange={(e) => setRiskProfile(e.target.value)}
              style={{
                background: "#0f172a",
                border: "1px solid #334155",
                color: "#f8fafc",
                borderRadius: 6,
                padding: "4px 8px",
                fontSize: 13,
              }}
            >
              <option value="Capital Preservation">Capital Preservation (0.5%)</option>
              <option value="Conservative">Conservative (1.0%)</option>
              <option value="Balanced">Balanced (1.5%)</option>
              <option value="Aggressive Research">Aggressive Research (2.5%)</option>
            </select>
          </div>
        </div>
      )}

      {/* Quick Prompts */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {quickPrompts.map((p) => (
          <button
            key={p.label}
            onClick={() => {
              setMode(p.m);
              setQuery(p.q);
              handleSend(p.q, p.m);
            }}
            style={{
              background: "#1e293b",
              border: "1px solid #334155",
              color: "#94a3b8",
              borderRadius: 6,
              padding: "4px 10px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Query Input Box */}
      <div style={{ display: "flex", gap: 8 }}>
        <input
          type="text"
          placeholder={`Ask ${mode}...`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          style={{
            flex: 1,
            background: "#1e293b",
            border: "1px solid #334155",
            color: "#f8fafc",
            borderRadius: 8,
            padding: "8px 14px",
            fontSize: 13,
          }}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading}
          style={{
            background: loading ? "#475569" : "#0284c7",
            color: "white",
            border: "none",
            borderRadius: 8,
            padding: "8px 18px",
            fontWeight: 700,
            fontSize: 13,
            cursor: loading ? "wait" : "pointer",
          }}
        >
          {loading ? "Analyzing..." : "Ask AI"}
        </button>
      </div>

      {/* Response Box */}
      {response && (
        <div
          style={{
            background: "#090d16",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: 16,
            display: "flex",
            flexDirection: "column",
            gap: 12,
            maxHeight: 400,
            overflowY: "auto",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "#64748b" }}>
            <span>Provider: {response.provider}</span>
            <span>Tools: {response.deterministic_tools_invoked?.join(", ") || "None"}</span>
          </div>

          <div
            style={{
              fontSize: 13,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              color: "#e2e8f0",
            }}
          >
            {response.answer}
          </div>

          {/* Capital Advisory Candidates Visual Breakdown */}
          {response.capital_advisory && (
            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: "#38bdf8" }}>Deterministic Sizing Matrix:</span>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
                {response.capital_advisory.eligible_candidates.map((c: any) => (
                  <div
                    key={c.instrument}
                    style={{ background: "#132338", border: "1px solid #0369a1", borderRadius: 6, padding: 10 }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 4,
                      }}
                    >
                      <span style={{ fontWeight: 700, fontSize: 12, color: "#4ade80" }}>{c.symbol_name}</span>
                      <span
                        style={{
                          fontSize: 10,
                          background: "#064e3b",
                          color: "#6ee7b7",
                          padding: "1px 5px",
                          borderRadius: 4,
                        }}
                      >
                        FEASIBLE
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: "#94a3b8", display: "flex", flexDirection: "column", gap: 2 }}>
                      <span>Req Margin: USD {c.required_capital.toLocaleString()}</span>
                      <span>
                        Calibrated Prob: <strong>{(c.calibrated_win_prob * 100).toFixed(1)}%</strong>
                      </span>
                      <span>Max Est Loss: USD {c.estimated_max_loss.toLocaleString()}</span>
                      <span>R:R: {c.risk_reward_ratio}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
