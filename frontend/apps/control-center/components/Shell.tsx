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
    <div className="operator-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <header className="operator-header">
        <Link href="/" className="brand">
          <span className="brand-mark">A</span>
          <span>
            ATS<small>XAUUSD LABORATORY</small>
          </span>
        </Link>
        <span className="authority-note">Paper only / AI proposes; deterministic ATS authorizes</span>
      </header>
      <nav aria-label="Primary navigation" className="operator-navigation">
        {navigation.map(([href, label]) => (
          <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>
            {label}
          </Link>
        ))}
      </nav>
      <main id="workspace" className="operator-workspace">
        {children}
      </main>
    </div>
  );
}
