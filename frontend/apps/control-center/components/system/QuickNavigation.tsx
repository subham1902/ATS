"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export const NAV_GROUPS = [
  { label: "DESK", items: [["/", "Overview", "⌂"], ["/markets", "Markets", "⌁"], ["/trades", "Trade Desk", "⇄"], ["/positions", "Positions", "▤"], ["/candidates", "Opportunities", "◇"]] },
  { label: "INTELLIGENCE", items: [["/operator-intelligence", "Operator Intel", "◉"], ["/harness", "Agents", "✦"], ["/research", "Research", "⚗"], ["/activity", "Session Review", "↺"]] },
  { label: "SYSTEM", items: [["/settings", "System", "⚙"]] },
] as const;

export function QuickNavigation({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const pathname = usePathname();
  return <aside className="quick-nav"><div className="nav-heading"><span>{collapsed ? "NAV" : "WORKSPACE"}</span><button type="button" onClick={onToggle} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-expanded={!collapsed}>{collapsed ? "›" : "‹"}</button></div><nav aria-label="Primary">{NAV_GROUPS.map((group) => <div className="nav-group" key={group.label}><h2>{group.label}</h2>{group.items.map(([href, label, icon]) => { const route = href.split("?")[0]; const active = pathname === route || (route !== "/" && pathname.startsWith(route)); return <Link key={`${href}-${label}`} href={href} aria-current={active ? "page" : undefined} title={collapsed ? label : undefined}><span className="nav-icon" aria-hidden="true">{icon}</span><span className="nav-label">{label}</span></Link>; })}</div>)}</nav><div className="nav-safety"><span aria-hidden="true">◈</span><div><strong>PAPER ONLY</strong><small>Live money disabled</small></div></div></aside>;
}
