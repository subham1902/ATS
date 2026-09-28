"use client";
import React, { useEffect, useState } from "react";
import { Card } from "@ats/ui";
import { getApiClient } from "../../lib/api";
import type { FeedHealthView } from "@ats/api-client";

export default function HealthPage() {
  const [health, setHealth] = useState<FeedHealthView | null>(null);

  useEffect(() => {
    getApiClient()
      .getMarketHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const isLive = health?.state === "LIVE";
  const isStale = health?.state === "STALE";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 }}>
      <div>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 800 }}>Data & Ingress Health</h1>
        <p style={{ margin: "4px 0 0", fontSize: 13, color: "#6b7280" }}>
          Real-time FeedFreshnessBoard telemetry, deduplication counters, and monotonic sequence integrity.
        </p>
      </div>

      {/* Feed Status Banner */}
      <div
        style={{
          background: isLive ? "#f0fdf4" : isStale ? "#fefce8" : "#fef2f2",
          border: `1px solid ${isLive ? "#bbf7d0" : isStale ? "#fef08a" : "#fecaca"}`,
          borderRadius: 12,
          padding: 16,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 18, fontWeight: 800, color: isLive ? "#166534" : isStale ? "#854d0e" : "#991b1b" }}>
              STATE: {health?.state || "NO_FEED"}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: "2px 8px",
                borderRadius: 999,
                background: isLive ? "#dcfce7" : isStale ? "#fef9c3" : "#fee2e2",
                color: isLive ? "#15803d" : isStale ? "#a16207" : "#b91c1c",
              }}
            >
              {health?.authority_class || "NO_FEED_ATTACHED"}
            </span>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: 12, color: "#4b5563" }}>
            Provider: <strong>{health?.source || "UPSTOX_V3"}</strong> · Ingress attached:{" "}
            <strong>{health?.attached ? "YES" : "NO"}</strong>
          </p>
        </div>

        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 12, color: "#6b7280" }}>Last Update Age</div>
          <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "monospace" }}>
            {health?.last_update_age_ms !== null && health?.last_update_age_ms !== undefined
              ? `${(health.last_update_age_ms / 1000).toFixed(1)}s`
              : "No ticks received"}
          </div>
        </div>
      </div>

      {/* Telemetry Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        <Card title="Ingress Telemetry Counters">
          <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Accepted Updates</span>
              <span style={{ fontFamily: "monospace", fontWeight: 700, color: "#16a34a" }}>
                {health?.accepted_updates ?? 0}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Dropped (Duplicate)</span>
              <span style={{ fontFamily: "monospace" }}>{health?.dropped_duplicate ?? 0}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Dropped (Out of Order)</span>
              <span style={{ fontFamily: "monospace" }}>{health?.dropped_out_of_order ?? 0}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Dropped (Stale)</span>
              <span style={{ fontFamily: "monospace" }}>{health?.dropped_stale ?? 0}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Active Subscribers</span>
              <span style={{ fontFamily: "monospace" }}>{health?.subscriber_count ?? 0}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "#6b7280" }}>Stale Threshold</span>
              <span style={{ fontFamily: "monospace" }}>{health ? health.stale_after_ms / 1000 : 30}s</span>
            </div>
          </div>
        </Card>

        <Card title="Dependent Strategy Status">
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600 }}>S17 (State Machine)</span>
              <span style={{ color: isLive ? "#16a34a" : "#dc2626", fontWeight: 700 }}>
                {isLive ? "MONITORING_LIVE" : "FEED_WAITING"}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600 }}>S01-S04 (OHLCV Families)</span>
              <span style={{ color: "#6b7280" }}>REJECTED (historical)</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600 }}>S34 (Regime Router)</span>
              <span style={{ color: "#6b7280" }}>REJECTED (historical)</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ fontWeight: 600 }}>B00 (No Trade)</span>
              <span style={{ color: "#16a34a", fontWeight: 700 }}>ACTIVE</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Reason Codes */}
      {health?.reason_codes && health.reason_codes.length > 0 && (
        <Card title="Active Reason Codes">
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "#b91c1c" }}>
            {health.reason_codes.map((code) => (
              <li key={code} style={{ fontFamily: "monospace" }}>
                {code}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
