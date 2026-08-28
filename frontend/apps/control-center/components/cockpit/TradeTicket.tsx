"use client";

import { useMemo, useState } from "react";
import type { OperatorOrderResult, StreamEvent } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import type { CockpitInstrument } from "./cockpitModel";

type OptionEvidence = { eventId: string; instrumentKey: string; expiry: string; strike: number; optionType: "CE" | "PE"; lotSize: number; tickSize: number | null; ltp: number; ask: number | null; bid: number | null; occurredAt: string };
const number = (value: unknown) => value !== null && value !== undefined && Number.isFinite(Number(value)) ? Number(value) : null;
const string = (value: unknown) => typeof value === "string" && value.trim() ? value : null;

export function optionsFromEvents(events: StreamEvent[], underlying: CockpitInstrument): OptionEvidence[] {
  const byKey = new Map<string, OptionEvidence>();
  for (const event of events) {
    const p = event.payload;
    const instrumentKey = string(p.instrument_key) ?? string(p.instrument_id);
    const optionType = string(p.option_type)?.toUpperCase();
    const expiry = string(p.expiry), strike = number(p.strike), lotSize = number(p.lot_size);
    const rawUnderlying = string(p.underlying)?.toUpperCase();
    const ltp = number(p.ltp) ?? number(p.last_price) ?? number(p.price);
    if (!instrumentKey || !expiry || strike === null || lotSize === null || ltp === null || (optionType !== "CE" && optionType !== "PE") || rawUnderlying !== underlying) continue;
    byKey.set(instrumentKey, { eventId: event.stream_event_id, instrumentKey, expiry, strike, optionType, lotSize, tickSize: number(p.tick_size), ltp, ask: number(p.ask), bid: number(p.bid), occurredAt: event.occurred_at });
  }
  return [...byKey.values()].sort((a, b) => a.expiry.localeCompare(b.expiry) || a.strike - b.strike || a.optionType.localeCompare(b.optionType));
}

export function TradeTicket({ underlying, events, canEnter, onClose, onComplete }: { underlying: CockpitInstrument; events: StreamEvent[]; canEnter: boolean; onClose: () => void; onComplete: () => Promise<void> }) {
  const options = useMemo(() => optionsFromEvents(events, underlying), [events, underlying]);
  const [selectedKey, setSelectedKey] = useState(options[0]?.instrumentKey ?? "");
  const [lots, setLots] = useState(1);
  const [managed, setManaged] = useState<"MONITOR_ONLY" | "ATS_MANAGED_EXIT">("MONITOR_ONLY");
  const [confirmed, setConfirmed] = useState(false);
  const [result, setResult] = useState<OperatorOrderResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const option = options.find((item) => item.instrumentKey === selectedKey) ?? options[0];
  const price = option?.ask ?? option?.ltp ?? null;
  const quantity = option ? option.lotSize * lots : 0;
  const premium = price === null ? null : price * quantity;
  const ageMs = option ? Date.now() - Date.parse(option.occurredAt) : Infinity;
  const fresh = ageMs >= 0 && ageMs <= 5_000;
  const allowed = Boolean(option && canEnter && fresh && confirmed && lots > 0 && !submitting);

  const submit = async () => {
    if (!option || price === null || !allowed) return;
    setSubmitting(true); setError(null);
    try {
      const response = await getApiClient().submitOperatorOrder({ operator_action_id: crypto.randomUUID(), instrument_key: option.instrumentKey, underlying, expiry: option.expiry, strike: String(option.strike), option_type: option.optionType, side: "BUY", lots, quantity: String(quantity), order_type: "LIMIT", requested_price: String(price), origin: "OPERATOR_MANUAL", requested_at: new Date().toISOString(), managed_exit_mode: managed, reason: "Operator submitted from Cockpit V2" });
      setResult(response);
      await onComplete();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Governed order service unavailable"); }
    finally { setSubmitting(false); }
  };

  return <div className="ticket-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><section className="trade-ticket" role="dialog" aria-modal="true" aria-labelledby="ticket-title"><header><div><small>A2 PAPER ONLY</small><h2 id="ticket-title">Buy {underlying} option</h2></div><button type="button" onClick={onClose} aria-label="Close order ticket">×</button></header>{options.length ? <><label>Provider instrument<select value={option?.instrumentKey} onChange={(event) => setSelectedKey(event.target.value)}>{options.map((item) => <option key={item.instrumentKey} value={item.instrumentKey}>{item.expiry} · {item.strike} {item.optionType}</option>)}</select></label><div className="ticket-grid"><label>Lots<input type="number" min="1" step="1" value={lots} onChange={(event) => setLots(Math.max(1, Number(event.target.value)))} /></label><label>Exit management<select value={managed} onChange={(event) => setManaged(event.target.value as typeof managed)}><option value="MONITOR_ONLY">Monitor only</option><option value="ATS_MANAGED_EXIT">ATS managed exit</option></select></label></div><dl className="ticket-preview"><div><dt>Instrument</dt><dd>{option?.strike} {option?.optionType}</dd></div><div><dt>Expiry</dt><dd>{option?.expiry}</dd></div><div><dt>Quantity</dt><dd>{quantity} · lot {option?.lotSize}</dd></div><div><dt>Current ask</dt><dd>{option?.ask ?? "Unavailable — LTP used"}</dd></div><div><dt>Estimated premium</dt><dd>{premium === null ? "—" : `₹${premium.toLocaleString("en-IN")}`}</dd></div><div><dt>Maximum premium at risk</dt><dd>{premium === null ? "—" : `₹${premium.toLocaleString("en-IN")}`}</dd></div><div><dt>Spread</dt><dd>{option?.ask !== null && option?.bid !== null ? (option!.ask! - option!.bid!).toFixed(2) : "Unavailable"}</dd></div><div><dt>Freshness</dt><dd>{fresh ? "LIVE" : `STALE ${Math.max(0, ageMs / 1000).toFixed(1)}s`}</dd></div></dl><p className="ticket-safety">This intent is validated against InstrumentSpec, session, freshness, capital, Risk and deterministic A04 before PaperBroker. It can never place a live-money order.</p><label className="ticket-confirm"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /> I confirm this is a PAPER BUY order.</label><button type="button" className="ats-btn ats-btn-primary" disabled={!allowed} onClick={() => void submit()}>{submitting ? "Submitting to governance…" : `Submit PAPER BUY ${option?.optionType ?? ""}`}</button>{!canEnter ? <p className="ticket-blocked">Trade blocked: session does not allow new risk.</p> : !fresh ? <p className="ticket-blocked">Trade blocked: option quote is stale.</p> : null}</> : <div className="cockpit-empty"><strong>OPTION DATA UNAVAILABLE</strong><span>No provider-derived option InstrumentSpec and quote event is available for {underlying}. The ticket cannot guess expiry, strike, or lot size.</span></div>}{result ? <div className={result.accepted ? "ticket-result success" : "ticket-result blocked"}><strong>{result.accepted ? "PAPER POSITION FILLED" : "TRADE BLOCKED"}</strong><span>{result.reason_codes.join(" · ").replaceAll("_", " ")}</span></div> : null}{error ? <div className="ticket-result blocked"><strong>ORDER SERVICE UNAVAILABLE</strong><span>{error}</span></div> : null}</section></div>;
}
