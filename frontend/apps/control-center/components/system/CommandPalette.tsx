"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { RuntimeCommandRequest } from "@ats/api-client";
import { NAV_GROUPS } from "./QuickNavigation";
import { useOperatorState } from "./OperatorStateProvider";

type Item = { id: string; label: string; group: string; hint: string; href?: string; command?: RuntimeCommandRequest; confirm?: boolean };
export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter(); const { command } = useOperatorState(); const [query, setQuery] = useState(""); const input = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) { setQuery(""); window.setTimeout(() => input.current?.focus(), 0); } }, [open]);
  useEffect(() => { const key = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); }; window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key); }, [onClose]);
  const items = useMemo<Item[]>(() => [
    ...NAV_GROUPS.flatMap((group) => group.items.map(([href, label]) => ({ id: `${group.label}-${label}`, label: `Go to ${label}`, group: "Navigation", hint: group.label, href }))),
    { id: "safe", label: "Set SAFE mode", group: "Safe actions", hint: "Bounded runtime command", command: { command: "SET_MODE", mode: "SAFE" } },
    { id: "normal", label: "Set NORMAL mode", group: "Safe actions", hint: "Bounded runtime command", command: { command: "SET_MODE", mode: "NORMAL" } },
    { id: "pause", label: "Pause new entries", group: "Safe actions", hint: "No position changes", command: { command: "PAUSE_NEW_ENTRIES" } },
    { id: "resume", label: "Resume new entries", group: "Safe actions", hint: "Runtime rules still apply", command: { command: "RESUME_NEW_ENTRIES" } },
    { id: "flatten", label: "Flatten portfolio…", group: "Emergency", hint: "Confirmation required", command: { command: "FLATTEN_PORTFOLIO" }, confirm: true },
    { id: "halt", label: "Halt system…", group: "Emergency", hint: "Confirmation required", command: { command: "HALT_SYSTEM" }, confirm: true },
  ], []);
  const visible = items.filter((item) => `${item.label} ${item.group} ${item.hint}`.toLowerCase().includes(query.toLowerCase())).slice(0, 12);
  const select = async (item: Item) => { if (item.href) { router.push(item.href); onClose(); return; } if (item.confirm && !window.confirm(`${item.label.replace("…", "")}? This request will be sent to bounded runtime authority.`)) return; if (item.command) { await command(item.command); onClose(); } };
  if (!open) return null;
  return <div className="palette-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette"><div className="palette-search"><span aria-hidden="true">⌕</span><input ref={input} aria-label="Search navigation and safe actions" placeholder="Navigate or run a bounded action…" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && visible[0]) void select(visible[0]); }} /><kbd>ESC</kbd></div><div className="palette-results">{visible.length ? visible.map((item) => <button key={item.id} type="button" onClick={() => void select(item)}><span><strong>{item.label}</strong><small>{item.hint}</small></span><em>{item.group}</em></button>) : <p>No matching destination or safe action.</p>}</div><footer><span>↑↓ Browse</span><span>↵ Open</span><strong>No order entry · A2 paper</strong></footer></section></div>;
}
