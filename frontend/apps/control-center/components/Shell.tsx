"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { ConnectionIndicator } from "@ats/ui";
import { SystemStateBadge } from "@ats/ui";
import type { SystemState, SseStatus } from "@ats/api-client";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/policies", label: "Policies" },
  { href: "/candidates", label: "Candidates" },
  { href: "/governance", label: "Governance" },
  { href: "/risk", label: "Risk" },
  { href: "/advisories", label: "Advisories" },
  { href: "/tokens", label: "Autonomy" },
  { href: "/activity", label: "Activity" },
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
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", background: "#f8fafc", color: "#111827", fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <a href="#main" style={{ position: "absolute", left: -9999, top: 0, background: "black", color: "white", padding: 8 }}>
        Skip to content
      </a>
      <header
        style={{
          position: "sticky",
          top: 0,
          zIndex: 10,
          background: "white",
          borderBottom: "1px solid #e5e7eb",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 20px",
          gap: 16,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontWeight: 800, letterSpacing: "0.06em", fontSize: 14, border: "1px solid #111827", padding: "4px 8px", borderRadius: 6 }}>
            ATS CONTROL CENTER
          </div>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", color: "#6b7280", border: "1px solid #e5e7eb", padding: "2px 6px", borderRadius: 999 }}>
            A2_PAPER
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {systemState ? <SystemStateBadge state={systemState} /> : <span style={{ fontSize: 12, color: "#6b7280", border: "1px dashed #d1d5db", borderRadius: 999, padding: "2px 8px" }}>system: unknown — not healthy</span>}
          <ConnectionIndicator status={sseStatus} />
        </div>
      </header>
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <nav
          aria-label="Primary"
          style={{
            width: 200,
            flexShrink: 0,
            background: "white",
            borderRight: "1px solid #e5e7eb",
            padding: "16px 12px",
            display: "flex",
            flexDirection: "column",
            gap: 4,
          }}
        >
          {NAV.map((n) => {
            const active = pathname === n.href || (n.href !== "/" && pathname?.startsWith(n.href));
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                style={{
                  display: "block",
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: active ? 700 : 500,
                  background: active ? "#111827" : "transparent",
                  color: active ? "white" : "#374151",
                  textDecoration: "none",
                  outlineOffset: 2,
                }}
              >
                {n.label}
              </Link>
            );
          })}
          <div style={{ marginTop: 16, padding: 10, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb", fontSize: 11, color: "#6b7280", lineHeight: 1.4 }}>
            Read-only A2 paper surface.<br />
            No live execution controls.<br />
            SSE replay unsupported.
          </div>
        </nav>
        <main id="main" tabIndex={-1} style={{ flex: 1, padding: 20, minWidth: 0, outline: "none" }}>
          {children}
        </main>
      </div>
      <style>{`a:focus-visible, button:focus-visible, [tabindex]:focus-visible { outline: 2px solid #111827; outline-offset: 2px; }`}</style>
    </div>
  );
}
