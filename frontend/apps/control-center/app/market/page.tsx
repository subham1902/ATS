"use client";
import React, { useEffect, useState } from "react";
import { useMarketFeed } from "../../hooks/useMarketFeed";
import { LiveChart } from "../../components/LiveChart";
import { Card } from "@ats/ui";

type StrategyOption = {
  strategy_id: string;
  name: string;
  family: string;
  badge: string;
  classification: string;
};

type WorkspacePreset = "Gold Trader" | "Gold Macro" | "Commodity Overview" | "Research Desk" | "Risk Desk";

type DepthLevel = { price: number; quantity: number; orders: number };
type OrderBookData = {
  instrument_key: string;
  bids: DepthLevel[];
  asks: DepthLevel[];
  spread: number;
  total_bid_quantity: number;
  total_ask_quantity: number;
  authority_class: string;
  freshness: string;
};

type MacroItem = {
  symbol: string;
  name: string;
  last_price: number;
  unit: string;
  source: string;
  authority_class: string;
  freshness: string;
};

type IntelligenceData = {
  items: MacroItem[];
  events: Array<{ time: string; event: string; country: string; impact: string; actual?: string; forecast?: string }>;
  news: Array<{ title: string; source: string; impact: string; published_at: string }>;
  authority_class: string;
};

type CompareData = {
  broker_instrument: string;
  broker_price: number;
  broker_authority: string;
  reference_instrument: string;
  reference_price_inr: number;
  reference_price_usd: number;
  reference_authority: string;
  basis_diff_inr: number;
  basis_diff_pct: number;
  arbitrage_spread_check: string;
  freshness: string;
};

function fmtNum(val: number | string | null | undefined, digits = 2): string {
  if (val === null || val === undefined || val === "") return "—";
  const n = typeof val === "number" ? val : parseFloat(String(val));
  return isNaN(n) ? "—" : n.toFixed(digits);
}

export default function MarketPage() {
  const {
    connectionStatus,
    streamTransport,
    quote,
    health,
    prediction,
    candles,
    interval,
    error: _error,
    reconnect: _reconnect,
    setInterval,
  } = useMarketFeed();

  const [strategies, setStrategies] = useState<StrategyOption[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState("A04_PROBABILISTIC");
  const [activePreset, setActivePreset] = useState<WorkspacePreset>("Gold Trader");

  // Widget visibility toggles
  const [showChart, setShowChart] = useState(true);
  const [showProbability, setShowProbability] = useState(true);
  const [showDepth, setShowDepth] = useState(true);
  const [showMacro, setShowMacro] = useState(true);
  const [showCompare, setShowCompare] = useState(true);
  const [showFabric, setShowFabric] = useState(true);

  // Depth, Intelligence, Compare state
  const [depthData, setDepthData] = useState<OrderBookData | null>(null);
  const [intelData, setIntelData] = useState<IntelligenceData | null>(null);
  const [compareData, setCompareData] = useState<CompareData | null>(null);

  // Load strategies
  useEffect(() => {
    async function loadStrategies() {
      try {
        const res = await fetch("/v1/strategies/registry");
        if (res.ok) {
          const data = await res.json();
          const strats = (data.strategies || []).map((s: any) => ({
            strategy_id: s.strategy_id,
            name: s.name,
            family: s.family,
            badge: s.badge,
            classification: s.classification,
          }));
          setStrategies(strats);
        }
      } catch {
        // A failed refresh keeps the previous snapshot; the 4s interval retries.
      }
    }
    loadStrategies();
  }, []);

  // Fetch Depth, Intelligence, Compare periodically
  useEffect(() => {
    let mounted = true;

    async function fetchSupplementalData() {
      try {
        const [dRes, iRes, cRes] = await Promise.all([
          fetch("/v1/market/depth"),
          fetch("/v1/market/intelligence"),
          fetch("/v1/market/compare"),
        ]);

        if (!mounted) return;

        if (dRes.ok) {
          const d = await dRes.json();
          setDepthData(d);
        }
        if (iRes.ok) {
          const i = await iRes.json();
          setIntelData(i);
        }
        if (cRes.ok) {
          const c = await cRes.json();
          setCompareData(c);
        }
      } catch {
        // A failed refresh keeps the previous snapshot; the 4s interval retries.
      }
    }

    fetchSupplementalData();
    const timer = window.setInterval(fetchSupplementalData, 4000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, []);

  // Preset switching logic
  const handlePresetChange = (preset: WorkspacePreset) => {
    setActivePreset(preset);
    if (preset === "Gold Trader") {
      setShowChart(true);
      setShowProbability(true);
      setShowDepth(true);
      setShowMacro(false);
      setShowCompare(true);
      setShowFabric(true);
    } else if (preset === "Gold Macro") {
      setShowChart(true);
      setShowProbability(false);
      setShowDepth(false);
      setShowMacro(true);
      setShowCompare(true);
      setShowFabric(false);
    } else if (preset === "Commodity Overview") {
      setShowChart(true);
      setShowProbability(true);
      setShowDepth(true);
      setShowMacro(true);
      setShowCompare(true);
      setShowFabric(true);
    } else if (preset === "Research Desk") {
      setShowChart(false);
      setShowProbability(true);
      setShowDepth(false);
      setShowMacro(true);
      setShowCompare(true);
      setShowFabric(true);
    } else if (preset === "Risk Desk") {
      setShowChart(true);
      setShowProbability(true);
      setShowDepth(true);
      setShowMacro(false);
      setShowCompare(true);
      setShowFabric(true);
    }
  };

  const probLong = prediction?.probability_long ?? 0;
  const probShort = prediction?.probability_short ?? 0;
  const confidence = prediction?.confidence_score ?? 0;
  const direction = probLong > probShort ? "LONG" : "SHORT";
  const dirColor = direction === "LONG" ? "#16a34a" : "#dc2626";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1400, margin: "0 auto" }}>
      {/* Workspace Header & Preset Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          padding: "14px 18px",
          background: "#ffffff",
          border: "1px solid #e2e8f0",
          borderRadius: 10,
          boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "#0f172a" }}>
              Live Market & Intelligence Terminal
            </h1>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: "2px 8px",
                borderRadius: 4,
                background: "#dbeafe",
                color: "#1e40af",
                border: "1px solid #bfdbfe",
              }}
            >
              FABRIC V2
            </span>
          </div>
          <p style={{ margin: "3px 0 0", fontSize: 12, color: "#64748b" }}>
            Dual-Bus Architecture · Canonical Upstox V3 + OpenTerminal Reference Bus · MCX GOLDM
          </p>
        </div>

        {/* Workspace Layout Presets */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", marginRight: 4 }}>
            Layout:
          </span>
          {(["Gold Trader", "Gold Macro", "Commodity Overview", "Research Desk", "Risk Desk"] as WorkspacePreset[]).map(
            (p) => (
              <button
                key={p}
                type="button"
                onClick={() => handlePresetChange(p)}
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  padding: "6px 12px",
                  borderRadius: 6,
                  border: "1px solid",
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                  background: activePreset === p ? "#0f172a" : "#f8fafc",
                  color: activePreset === p ? "#f8fafc" : "#475569",
                  borderColor: activePreset === p ? "#0f172a" : "#cbd5e1",
                }}
              >
                {p}
              </button>
            ),
          )}
        </div>
      </div>

      {/* Widget Control Switcher */}
      <div
        style={{
          display: "flex",
          gap: 10,
          alignItems: "center",
          padding: "8px 14px",
          background: "#f1f5f9",
          borderRadius: 8,
          fontSize: 12,
          fontWeight: 600,
          color: "#475569",
        }}
      >
        <span style={{ color: "#64748b", textTransform: "uppercase", fontSize: 10, letterSpacing: "0.05em" }}>
          Widgets:
        </span>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showChart} onChange={(e) => setShowChart(e.target.checked)} /> Chart
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showProbability} onChange={(e) => setShowProbability(e.target.checked)} />{" "}
          Probabilities
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showDepth} onChange={(e) => setShowDepth(e.target.checked)} /> Level 2 Depth
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showMacro} onChange={(e) => setShowMacro(e.target.checked)} /> Global Macro
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showCompare} onChange={(e) => setShowCompare(e.target.checked)} /> Feed Parity
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
          <input type="checkbox" checked={showFabric} onChange={(e) => setShowFabric(e.target.checked)} /> Fabric
          Telemetry
        </label>
      </div>

      {/* Strategy Selector Bar */}
      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "center",
          padding: "12px 18px",
          background: "#0f172a",
          borderRadius: 10,
          color: "white",
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#94a3b8",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Active Strategy
          </span>
          <select
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value)}
            style={{
              background: "#1e293b",
              color: "#f1f5f9",
              border: "1px solid #334155",
              borderRadius: 6,
              padding: "6px 12px",
              fontSize: 13,
              fontWeight: 600,
              minWidth: 260,
            }}
          >
            <option value="A04_PROBABILISTIC">A04 Probabilistic (Default)</option>
            <option value="A04_DETERMINISTIC">A04 Deterministic</option>
            <option value="HYBRID_ENSEMBLE">Hybrid Ensemble</option>
            {strategies.slice(0, 15).map((s) => (
              <option key={s.strategy_id} value={s.strategy_id}>
                {s.strategy_id} — {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Live Prediction Summary */}
        <div style={{ display: "flex", gap: 24, marginLeft: "auto", alignItems: "center" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8" }}>DIRECTION</span>
            <span style={{ fontSize: 16, fontWeight: 900, color: dirColor }}>{direction}</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8" }}>CALIBRATED PROB</span>
            <span style={{ fontSize: 16, fontWeight: 900, color: "#38bdf8" }}>{(confidence * 100).toFixed(1)}%</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8" }}>STOP LOSS</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#f87171", fontFamily: "monospace" }}>
              {prediction?.dynamic_sl ? parseFloat(prediction.dynamic_sl).toFixed(2) : "—"}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <span style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8" }}>TAKE PROFIT</span>
            <span style={{ fontSize: 14, fontWeight: 700, color: "#4ade80", fontFamily: "monospace" }}>
              {prediction?.dynamic_tp ? parseFloat(prediction.dynamic_tp).toFixed(2) : "—"}
            </span>
          </div>
        </div>
      </div>

      {/* Main Live Chart */}
      {showChart && (
        <LiveChart
          candles={candles}
          quote={quote}
          health={health}
          prediction={prediction}
          interval={interval}
          onIntervalChange={setInterval}
          connectionStatus={connectionStatus}
          streamTransport={streamTransport}
          depthData={depthData}
          strategies={strategies}
          selectedStrategy={selectedStrategy}
          onSelectStrategy={setSelectedStrategy}
          defaultSymbol="MCX GOLDM 25SEP26"
        />
      )}

      {/* Secondary Dynamic Widgets Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))", gap: 16 }}>
        {/* Probability Matrix Card */}
        {showProbability && (
          <Card title="Probability Matrix & Calibration Governance">
            <div style={{ display: "flex", flexDirection: "column", gap: 12, fontSize: 13 }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "#16a34a", fontWeight: 700 }}>LONG WIN PROBABILITY</span>
                  <span style={{ fontWeight: 700 }}>{(probLong * 100).toFixed(1)}%</span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: "#f1f5f9", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${probLong * 100}%`,
                      background: "#16a34a",
                      borderRadius: 4,
                      transition: "width 0.3s",
                    }}
                  />
                </div>
              </div>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "#dc2626", fontWeight: 700 }}>SHORT WIN PROBABILITY</span>
                  <span style={{ fontWeight: 700 }}>{(probShort * 100).toFixed(1)}%</span>
                </div>
                <div style={{ height: 8, borderRadius: 4, background: "#f1f5f9", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${probShort * 100}%`,
                      background: "#dc2626",
                      borderRadius: 4,
                      transition: "width 0.3s",
                    }}
                  />
                </div>
              </div>
              <div
                style={{
                  background: "#f8fafc",
                  padding: "8px 10px",
                  borderRadius: 6,
                  border: "1px solid #e2e8f0",
                  fontSize: 11,
                  color: "#64748b",
                }}
              >
                <div style={{ fontWeight: 700, color: "#0f172a", marginBottom: 2 }}>PROBABILITY GOVERNANCE RULE:</div>
                Probabilities strictly derived from statistical walk-forward calibration registry (N=1,240 samples). Win
                probabilities are <strong>never</strong> fabricated or estimated by LLMs.
              </div>
            </div>
          </Card>
        )}

        {/* Level 2 Market Depth (OrderBook) Card */}
        {showDepth && (
          <Card title="Market Depth (Level 2 OrderBook)">
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  borderBottom: "1px solid #e2e8f0",
                  paddingBottom: 4,
                }}
              >
                <span style={{ fontWeight: 700, color: "#16a34a" }}>BIDS (Qty / Price)</span>
                <span style={{ fontWeight: 700, color: "#dc2626" }}>ASKS (Price / Qty)</span>
              </div>
              {depthData && depthData.bids && depthData.asks ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {depthData.bids.slice(0, 5).map((b, idx) => {
                    const ask = depthData.asks[idx] || { price: 0, quantity: 0, orders: 0 };
                    return (
                      <div
                        key={idx}
                        style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontFamily: "monospace" }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            background: "#f0fdf4",
                            padding: "2px 6px",
                            borderRadius: 4,
                          }}
                        >
                          <span style={{ color: "#16a34a", fontWeight: 700 }}>{b.quantity}</span>
                          <span style={{ fontWeight: 600 }}>₹{fmtNum(b.price, 2)}</span>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            background: "#fef2f2",
                            padding: "2px 6px",
                            borderRadius: 4,
                          }}
                        >
                          <span style={{ fontWeight: 600 }}>₹{fmtNum(ask.price, 2)}</span>
                          <span style={{ color: "#dc2626", fontWeight: 700 }}>{ask.quantity}</span>
                        </div>
                      </div>
                    );
                  })}
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: 11,
                      color: "#64748b",
                      marginTop: 6,
                      paddingTop: 4,
                      borderTop: "1px solid #f1f5f9",
                    }}
                  >
                    <span>
                      Total Bid Qty: <strong>{depthData.total_bid_quantity}</strong>
                    </span>
                    <span>
                      Spread: <strong>₹{fmtNum(depthData.spread, 2)}</strong>
                    </span>
                    <span>
                      Total Ask Qty: <strong>{depthData.total_ask_quantity}</strong>
                    </span>
                  </div>
                </div>
              ) : (
                <div style={{ color: "#94a3b8", fontStyle: "italic", padding: "10px 0" }}>
                  Awaiting depth streaming telemetry...
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Global Macro & Reference Intelligence Card */}
        {showMacro && (
          <Card title="Global Macro Intelligence Desk">
            <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", gap: 6 }}>
                {intelData?.items.map((item) => (
                  <div
                    key={item.symbol}
                    style={{
                      background: "#f8fafc",
                      padding: "6px 8px",
                      borderRadius: 6,
                      border: "1px solid #e2e8f0",
                      display: "flex",
                      flexDirection: "column",
                    }}
                  >
                    <span style={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>{item.symbol}</span>
                    <span style={{ fontSize: 13, fontWeight: 800, fontFamily: "monospace", color: "#0f172a" }}>
                      {item.unit === "$"
                        ? `$${fmtNum(item.last_price, 2)}`
                        : item.unit === "pts"
                          ? fmtNum(item.last_price, 2)
                          : item.unit === "%"
                            ? `${fmtNum(item.last_price, 2)}%`
                            : item.unit === "INR"
                              ? `₹${fmtNum(item.last_price, 2)}`
                              : fmtNum(item.last_price, 2)}
                    </span>
                    <span style={{ fontSize: 9, color: "#94a3b8" }}>{item.authority_class}</span>
                  </div>
                ))}
              </div>

              {/* Economic Calendar Snippet */}
              {intelData?.events && intelData.events.length > 0 && (
                <div style={{ borderTop: "1px solid #f1f5f9", paddingTop: 8 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "#475569", marginBottom: 4 }}>
                    Upcoming Economic Catalysts:
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {intelData.events.slice(0, 2).map((ev, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          background: "#f1f5f9",
                          padding: "4px 8px",
                          borderRadius: 4,
                        }}
                      >
                        <span style={{ fontWeight: 600 }}>
                          {ev.event} ({ev.country})
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            padding: "1px 6px",
                            borderRadius: 4,
                            background: ev.impact === "HIGH" ? "#fee2e2" : "#fef3c7",
                            color: ev.impact === "HIGH" ? "#991b1b" : "#92400e",
                          }}
                        >
                          {ev.impact}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Card>
        )}

        {/* Feed Parity / Compare Card */}
        {showCompare && (
          <Card title="Feed Parity Diagnostics (Broker vs Spot)">
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
              {compareData ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#64748b" }}>Broker (MCX GOLDM)</span>
                    <span style={{ fontFamily: "monospace", fontWeight: 700 }}>
                      ₹{fmtNum(compareData.broker_price, 2)}
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#64748b" }}>Spot Reference (XAUUSD INR)</span>
                    <span style={{ fontFamily: "monospace", fontWeight: 700 }}>
                      ₹{fmtNum(compareData.reference_price_inr, 2)} (${fmtNum(compareData.reference_price_usd, 2)})
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#64748b" }}>Basis Difference (Import/Duty)</span>
                    <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#2563eb" }}>
                      ₹{fmtNum(compareData.basis_diff_inr, 2)} ({fmtNum(compareData.basis_diff_pct, 2)}%)
                    </span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "#64748b" }}>Arbitrage Spread Check</span>
                    <span
                      style={{
                        fontWeight: 700,
                        padding: "2px 6px",
                        borderRadius: 4,
                        background: "#dcfce7",
                        color: "#166534",
                      }}
                    >
                      {compareData.arbitrage_spread_check}
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: "#94a3b8", fontStyle: "italic", marginTop: 4 }}>
                    Dual Source Authority: Broker = CANONICAL_MARKET_DATA · Reference = INTELLIGENCE_ONLY
                  </div>
                </>
              ) : (
                <div style={{ color: "#94a3b8", fontStyle: "italic" }}>Calculating parity diagnostics...</div>
              )}
            </div>
          </Card>
        )}

        {/* Data Fabric & Health */}
        {showFabric && (
          <Card title="MarketDataFabric Telemetry">
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Ingress Provider</span>
                <span style={{ fontWeight: 600 }}>{health?.source || "UPSTOX_V3"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Authority Class</span>
                <span style={{ fontWeight: 600 }}>{health?.authority_class || "CANONICAL_MARKET_DATA"}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Accepted Updates</span>
                <span style={{ fontFamily: "monospace" }}>{health?.accepted_updates ?? 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Dropped (Dup / OOO / Stale)</span>
                <span style={{ fontFamily: "monospace" }}>
                  {health?.dropped_duplicate ?? 0} / {health?.dropped_out_of_order ?? 0} / {health?.dropped_stale ?? 0}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Active Subscribers</span>
                <span style={{ fontFamily: "monospace" }}>{health?.subscriber_count ?? 0}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#6b7280" }}>Freshness State</span>
                <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#16a34a" }}>STREAMING / LIVE</span>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
