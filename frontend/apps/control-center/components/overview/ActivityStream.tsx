"use client";

import { useMemo, useState } from "react";
import type { StreamEvent } from "@ats/api-client";
import { formatTimeIST } from "../../lib/formatTime";

type Category = "ALL" | "MARKET" | "MODEL" | "SCANNER" | "PORTFOLIO" | "RISK" | "EXECUTION" | "SYSTEM" | "AGENT";

function categorize(kind: string): Category {
  const k = kind.toUpperCase();
  if (k.includes("TICK") || k.includes("PRICE") || k.includes("MARKET") || k.includes("FEED") || k.includes("REGIME")) return "MARKET";
  if (k.includes("PREDICT") || k.includes("MODEL") || k.includes("CHAMPION") || k.includes("CHALLENGER")) return "MODEL";
  if (k.includes("SCAN") || k.includes("CANDIDATE") || k.includes("OPPORTUNITY") || k.includes("THESIS")) return "SCANNER";
  if (k.includes("PORTFOLIO") || k.includes("BRAIN")) return "PORTFOLIO";
  if (k.includes("RISK") || k.includes("LOSS") || k.includes("DRAWDOWN") || k.includes("DENY")) return "RISK";
  if (k.includes("ORDER") || k.includes("FILL") || k.includes("EXECUT") || k.includes("POSITION")) return "EXECUTION";
  if (k.includes("AGENT") || k.includes("HARNESS") || k.includes("ADVISORY")) return "AGENT";
  return "SYSTEM";
}

const CATEGORIES: Category[] = ["ALL", "MARKET", "MODEL", "SCANNER", "PORTFOLIO", "RISK", "EXECUTION", "AGENT", "SYSTEM"];

export function ActivityStream({ events, maxRows = 100 }: { events: StreamEvent[]; maxRows?: number }) {
  const [filter, setFilter] = useState<Category>("ALL");
  const filtered = useMemo(() => {
    const base = events.slice(-maxRows).reverse();
    if (filter === "ALL") return base;
    return base.filter((e) => categorize(e.event_kind) === filter);
  }, [events, filter, maxRows]);

  return (
    <div className="as-container">
      <div className="as-filters">
        {CATEGORIES.map((cat) => (
          <button key={cat} type="button" aria-pressed={filter === cat} onClick={() => setFilter(cat)}>{cat}</button>
        ))}
      </div>
      <div className="as-feed">
        {filtered.length === 0 ? (
          <div className="as-empty">No events{filter !== "ALL" ? ` in ${filter}` : ""}. Waiting for activity.</div>
        ) : (
          <ul>
            {filtered.map((event) => {
              const cat = categorize(event.event_kind);
              return (
                <li key={event.stream_event_id} className={`as-item as-cat-${cat.toLowerCase()}`}>
                  <time>{formatTimeIST(event.occurred_at)}</time>
                  <span className={`as-badge as-badge-${cat.toLowerCase()}`}>{cat}</span>
                  <span className="as-kind">{event.event_kind.replaceAll("_", " ")}</span>
                  {event.payload.summary != null && <span className="as-summary">{String(event.payload.summary)}</span>}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
