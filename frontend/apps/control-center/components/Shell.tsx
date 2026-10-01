"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ConnectionIndicator, SystemStateBadge } from "@ats/ui";
import { requestedSourceLabel, useDataSource, type RequestedSource } from "../lib/dataSource";
import type { SystemState, SseStatus } from "@ats/api-client";
import { AICopilotPanel } from "./AICopilotPanel";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  badge?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    title: "TRADING & EXECUTION",
    items: [
      { href: "/", label: "Command Center", icon: "📊" },
      { href: "/market", label: "Live Market", icon: "📈" },
      { href: "/strategies", label: "Strategies & Board", icon: "🏆" },
      { href: "/optimizations", label: "Live Optimizations", icon: "🧬", badge: "AI" },
      { href: "/agents", label: "Agents Playground", icon: "🤖", badge: "₹1L / ₹2L" },
      { href: "/agents/managed", label: "Managed Agents", icon: "🧠", badge: "Proposal-only" },
      { href: "/upstox-ledger", label: "Upstox Trade Ledger", icon: "⚡", badge: "1,000 Live" },
      { href: "/paper", label: "Paper Trading", icon: "⚡" },
      { href: "/shadow", label: "Shadow Lab", icon: "🔬" },
    ],
  },
  {
    title: "DATA & ASSETS",
    items: [
      { href: "/survivors", label: "Survivors", icon: "⭐" },
      { href: "/datasets", label: "Datasets", icon: "💾" },
      { href: "/research", label: "Research", icon: "📚" },
      { href: "/health", label: "Data & Health", icon: "🛡️" },
      { href: "/broker", label: "Broker", icon: "🏦" },
    ],
  },
  {
    title: "GOVERNANCE & WORKFLOW",
    items: [
      { href: "/governance", label: "Governance Hub", icon: "🏛️", badge: "A2" },
      { href: "/policies", label: "Policies", icon: "📋" },
      { href: "/candidates", label: "Candidates", icon: "🎯" },
      { href: "/advisories", label: "Advisories", icon: "💡" },
      { href: "/tokens", label: "Autonomy", icon: "🔑" },
      { href: "/risk", label: "Risk Engine", icon: "⚖️" },
    ],
  },
  {
    title: "SYSTEM",
    items: [
      { href: "/activity", label: "Activity Log", icon: "📝" },
      { href: "/settings", label: "Settings", icon: "⚙️" },
    ],
  },
];

export function Shell({
  children,
  systemState,
  sseStatus,
}: {
  children: ReactNode;
  systemState: SystemState | null;
  sseStatus: SseStatus;
}) {
  const pathname = usePathname();
  const { requestedSource, setRequestedSource } = useDataSource();
  const [showCopilot, setShowCopilot] = useState(false);

  // The feed pill reports the conjunction of control-plane state and stream
  // state. Either one missing means the operator is not looking at a live
  // system, so the pill must not say otherwise.
  const feedPill =
    systemState === null
      ? { text: "CHECKING", background: "#f1f5f9", color: "#475569", border: "#cbd5e1", dot: "#94a3b8" }
      : systemState === "READY" && sseStatus === "connected"
        ? { text: "LIVE READY", background: "#ecfdf5", color: "#047857", border: "#a7f3d0", dot: "#10b981" }
        : systemState === "READY"
          ? {
              text: "READY · FEED DOWN",
              background: "#fffbeb",
              color: "#92400e",
              border: "#fde68a",
              dot: "#f59e0b",
            }
          : { text: "NOT LIVE", background: "#fef2f2", color: "#991b1b", border: "#fecaca", dot: "#ef4444" };

  function handleSourceChange(next: string) {
    if (next === "BROKER_LIVE" || next === "OPEN_TERMINAL") {
      const value: RequestedSource = next;
      setRequestedSource(value);
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#f8fafc",
        color: "#0f172a",
        fontFamily: "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      }}
    >
      <a
        href="#main"
        style={{ position: "absolute", left: -9999, top: 0, background: "#0f172a", color: "white", padding: 8 }}
      >
        Skip to content
      </a>

      {/* Modern Frosted Header */}
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "rgba(255, 255, 255, 0.92)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid #e2e8f0",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 20px",
          gap: 16,
          boxShadow: "0 1px 2px 0 rgba(0, 0, 0, 0.03)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              fontWeight: 800,
              letterSpacing: "0.04em",
              fontSize: 13,
              background: "#0f172a",
              color: "#f8fafc",
              padding: "5px 12px",
              borderRadius: 8,
              boxShadow: "0 1px 3px rgba(15, 23, 42, 0.2)",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: "#38bdf8",
                boxShadow: "0 0 8px #38bdf8",
              }}
            />
            ATS CONTROL CENTER
          </div>

          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              padding: "3px 8px",
              borderRadius: 999,
              background: "#f1f5f9",
              color: "#475569",
              border: "1px solid #cbd5e1",
            }}
          >
            A2_PAPER
          </span>

          <span
            aria-label={`feed ${feedPill.text}`}
            style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              padding: "3px 9px",
              borderRadius: 999,
              background: feedPill.background,
              color: feedPill.color,
              border: `1px solid ${feedPill.border}`,
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: feedPill.dot }} />
            {feedPill.text}
          </span>
        </div>

        {/* Dual Data-Source & Copilot Controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {/* Top-Right Global Data Source Control */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "#f1f5f9",
              padding: "3px 8px",
              borderRadius: 8,
              border: "1px solid #cbd5e1",
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 700, color: "#64748b" }}>DATA SOURCE:</span>
            <select
              aria-label="Requested data source"
              value={requestedSource}
              onChange={(e) => handleSourceChange(e.target.value)}
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: "#0f172a",
                color: "#38bdf8",
                border: "1px solid #334155",
                borderRadius: 6,
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              <option value="BROKER_LIVE">{requestedSourceLabel("BROKER_LIVE")}</option>
              <option value="OPEN_TERMINAL">{requestedSourceLabel("OPEN_TERMINAL")}</option>
            </select>
            <span
              style={{ fontSize: 10, fontWeight: 500, color: "#64748b" }}
              title="A request label, not a status claim. What the feed is actually serving is reported next to the chart."
            >
              requested — see chart provenance
            </span>
          </div>

          {/* Explicit Authority Separation Badges */}
          <div style={{ display: "flex", gap: 6, fontSize: 10, fontWeight: 700 }}>
            <span
              style={{
                background: "#e0f2fe",
                color: "#0369a1",
                padding: "3px 8px",
                borderRadius: 6,
                border: "1px solid #bae6fd",
              }}
            >
              EXEC: PaperBroker
            </span>
            <span
              style={{
                background: "#fef3c7",
                color: "#92400e",
                padding: "3px 8px",
                borderRadius: 6,
                border: "1px solid #fde68a",
              }}
            >
              AUTH: A04
            </span>
          </div>

          {/* AI Copilot Button */}
          <button
            onClick={() => setShowCopilot(!showCopilot)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              background: showCopilot ? "#0284c7" : "#0f172a",
              color: "#f8fafc",
              border: "1px solid #334155",
              borderRadius: 8,
              padding: "4px 10px",
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
              boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
            }}
          >
            <span>🤖</span>
            <span>AI Copilot</span>
          </button>

          {systemState ? (
            <SystemStateBadge state={systemState} />
          ) : (
            <span
              style={{
                fontSize: 12,
                color: "#64748b",
                background: "#f1f5f9",
                border: "1px solid #cbd5e1",
                borderRadius: 999,
                padding: "3px 10px",
                fontWeight: 500,
              }}
            >
              system: connecting...
            </span>
          )}

          <ConnectionIndicator status={sseStatus} />
        </div>
      </header>

      {/* Floating AI Copilot Drawer */}
      {showCopilot && (
        <div
          style={{
            position: "fixed",
            top: 60,
            right: 20,
            width: 480,
            maxWidth: "90vw",
            zIndex: 999,
          }}
        >
          <AICopilotPanel onClose={() => setShowCopilot(false)} />
        </div>
      )}

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Sleek Sidebar Navigation */}
        <nav
          aria-label="Primary"
          style={{
            width: 220,
            flexShrink: 0,
            background: "#ffffff",
            borderRight: "1px solid #e2e8f0",
            padding: "16px 10px",
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          {NAV_SECTIONS.map((section, sIdx) => (
            <div key={section.title} style={{ marginBottom: sIdx === NAV_SECTIONS.length - 1 ? 0 : 12 }}>
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: "0.08em",
                  color: "#94a3b8",
                  padding: "4px 10px 2px",
                  textTransform: "uppercase",
                }}
              >
                {section.title}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
                {section.items.map((n) => {
                  const matches = (href: string) => pathname === href || (href !== "/" && !!pathname?.startsWith(href));
                  // Most specific nav entry wins, so /agents/managed does not also light up /agents.
                  const active =
                    matches(n.href) &&
                    !NAV_SECTIONS.some((sec) =>
                      sec.items.some((o) => o.href.length > n.href.length && matches(o.href)),
                    );
                  return (
                    <Link
                      key={n.href}
                      href={n.href}
                      aria-current={active ? "page" : undefined}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "6px 10px",
                        borderRadius: 6,
                        fontSize: 12.5,
                        fontWeight: active ? 700 : 500,
                        background: active ? "#0f172a" : "transparent",
                        color: active ? "#ffffff" : "#475569",
                        textDecoration: "none",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 13 }}>{n.icon}</span>
                        <span>{n.label}</span>
                      </div>
                      {n.badge && (
                        <span
                          style={{
                            fontSize: 9,
                            fontWeight: 800,
                            padding: "1px 5px",
                            borderRadius: 4,
                            background: active ? "rgba(255, 255, 255, 0.2)" : "rgba(99, 102, 241, 0.15)",
                            color: active ? "#ffffff" : "#6366f1",
                          }}
                        >
                          {n.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}

          <div
            style={{
              marginTop: "auto",
              padding: "12px",
              background: "#f8fafc",
              borderRadius: 8,
              border: "1px solid #e2e8f0",
              fontSize: 11,
              color: "#64748b",
              lineHeight: 1.5,
            }}
          >
            <div style={{ fontWeight: 700, color: "#0f172a", marginBottom: 2 }}>Platform v2.0</div>
            Strategy Registry Active
            <br />
            PaperBroker Guarded
          </div>
        </nav>

        {/* Main Content Viewport */}
        <main id="main" tabIndex={-1} style={{ flex: 1, padding: "24px 28px", minWidth: 0, outline: "none" }}>
          {children}
        </main>
      </div>

      <style>{`
        a:focus-visible, button:focus-visible, [tabindex]:focus-visible { outline: 2px solid #0f172a; outline-offset: 2px; }
        @keyframes pulse-dot {
          0% { transform: scale(0.95); opacity: 0.8; }
          50% { transform: scale(1.15); opacity: 1; }
          100% { transform: scale(0.95); opacity: 0.8; }
        }
        @media (max-width: 768px) {
          nav[aria-label="Primary"] {
            display: none !important;
          }
          main#main {
            padding: 10px 12px !important;
          }
        }
      `}</style>
    </div>
  );
}
