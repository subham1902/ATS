"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation = [
  ["/", "Dashboard"],
  ["/market", "Market"],
  ["/research", "Research"],
  ["/strategies", "Strategies"],
  ["/agents/managed", "Agents"],
  ["/accounts", "Accounts"],
  ["/paper", "Paper Trading"],
  ["/datasets", "Datasets"],
  ["/system", "System"],
];
export function Shell({ children }: { children: ReactNode }) {
  const path = usePathname();
  return (
    <div style={{ minHeight: "100vh", background: "#f7f8fa", color: "#142331", fontFamily: "system-ui,sans-serif" }}>
      <header style={{ padding: "20px 28px", background: "#142331", color: "white" }}>
        <strong>ATS · XAUUSD Laboratory</strong>
        <span style={{ marginLeft: 24 }}>Paper only · AI proposes; deterministic ATS authorizes</span>
      </header>
      <nav
        aria-label="Primary navigation"
        style={{ display: "flex", flexWrap: "wrap", gap: 20, padding: "18px 28px", borderBottom: "1px solid #ddd" }}
      >
        {navigation.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            aria-current={path === href ? "page" : undefined}
            style={{ color: path === href ? "#8a6115" : "#142331" }}
          >
            {label}
          </Link>
        ))}
      </nav>
      <main style={{ maxWidth: 1440, margin: "0 auto", padding: 28 }}>{children}</main>
    </div>
  );
}
