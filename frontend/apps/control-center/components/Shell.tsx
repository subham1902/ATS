"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import type { SseStatus, SystemState } from "@ats/api-client";
import { CommandPalette } from "./system/CommandPalette";
import { GlobalAlerts } from "./system/GlobalAlerts";
import { GlobalOperatorBar } from "./system/GlobalOperatorBar";
import { QuickNavigation } from "./system/QuickNavigation";

export function Shell({ children, systemState: _legacySystemState, sseStatus: _legacySseStatus }: { children: ReactNode; systemState?: SystemState | null; sseStatus?: SseStatus }) {
  const [collapsed, setCollapsed] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const openPalette = useCallback(() => setPaletteOpen(true), []);
  const closePalette = useCallback(() => setPaletteOpen(false), []);
  useEffect(() => {
    try {
      const stored = typeof window !== "undefined" && window.localStorage ? window.localStorage.getItem("ats.sidebar.collapsed") : null;
      if (stored !== null && stored !== undefined) setCollapsed(stored === "true");
    } catch {
      // Ignore storage access errors in test/headless environments
    }
    const onKeyDown = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen(true); } };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);
  const toggle = () => setCollapsed((value) => {
    const next = !value;
    try {
      if (typeof window !== "undefined" && window.localStorage) window.localStorage.setItem("ats.sidebar.collapsed", String(next));
    } catch {
      // Ignore
    }
    return next;
  });
  return <div className="ats-shell" data-collapsed={collapsed}>
    <a href="#main" className="ats-skip">Skip to content</a>
    <GlobalOperatorBar onOpenPalette={openPalette} />
    <GlobalAlerts />
    <div className="ats-workspace"><QuickNavigation collapsed={collapsed} onToggle={toggle} /><main id="main" tabIndex={-1} className="ats-main">{children}</main></div>
    <CommandPalette open={paletteOpen} onClose={closePalette} />
  </div>;
}
