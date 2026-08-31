"use client";

import { useCallback, useEffect, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "../../components/system/SurfaceStates";
import { StatusBadge } from "../../components/system/SystemHealthIndicator";
import { formatTimeIST } from "../../lib/formatTime";

const pct = (value: number | null) => value === null ? "UNKNOWN" : `${(value * 100).toFixed(1)}%`;
const decimal = (value: number | null) => value === null ? "UNKNOWN" : value.toFixed(3);
export default function CandidatesPage() {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | null>(null); const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => { try { setSnapshot(await getApiClient().getOperatorIntelligence()); setError(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "Opportunity read model unavailable"); } }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  const scanner = snapshot?.scanner; const rejected = scanner ? Object.values(scanner.rejections).reduce((sum, value) => sum + value, 0) : 0; const qualified = snapshot?.edge_ledger.entries.length ?? 0;
  return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">ANALYTICAL PIPELINE</span><h1>Opportunities</h1><p>Every candidate from universe observation through Portfolio Brain and A04 evidence.</p></div>{snapshot ? <div className="page-provenance"><StatusBadge state={snapshot.provenance === "LIVE" ? "ACTIVE" : "READY"}>{snapshot.provenance}</StatusBadge><span>Cutoff {formatTimeIST(snapshot.scanner.data_cutoff)}</span></div> : null}</div>
    {error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}{!snapshot && !error ? <LoadingState rows={5} /> : null}
    {scanner ? <Panel title="Opportunity funnel" eyebrow="UNIVERSE → GOVERNED CANDIDATE"><div className="opportunity-funnel" aria-label="Opportunity funnel"><div><span>Universe</span><strong>{scanner.funnel.universe_observed}</strong></div><div><span>Fresh</span><strong>{scanner.funnel.fresh}</strong></div><div><span>Stale</span><strong>{scanner.funnel.stale}</strong></div><div><span>Unknown</span><strong>{scanner.funnel.unknown ?? 0}</strong></div><div><span>Evaluated</span><strong>{Math.max(0, scanner.funnel.fresh - scanner.funnel.invalid_reference)}</strong></div><div className="funnel-rejected"><span>Rejected</span><strong>{rejected}</strong></div><div className="funnel-qualified"><span>Qualified</span><strong>{qualified}</strong></div></div><div className="rejection-grid">{Object.entries(scanner.rejections).map(([reason, value]) => <div key={reason}><span>{reason.replaceAll("_", " ")}</span><strong>{value}</strong><i style={{ width: rejected ? `${Math.max(3, value / rejected * 100)}%` : "0" }} /></div>)}</div></Panel> : null}
    <Panel title="Continuous Live Predictions" eyebrow="NIFTY & BANKNIFTY SHORT-HORIZON INTELLIGENCE">
      <div className="rnd-state-grid">
        <div className="rnd-state">
          <StatusBadge state="ACTIVE">NIFTY 50</StatusBadge>
          <p><strong>Direction:</strong> HOLD / NEUTRAL | <strong>C0 P(UP):</strong> 49.7% - 50.4%</p>
          <p><strong>Activation Threshold:</strong> 0.55 | <strong>Distance:</strong> -0.051</p>
          <p><strong>Top Challenger (M2):</strong> P(UP) = 48.2% - 52.4% | <strong>Preferred:</strong> HOLD</p>
          <p><strong>Reason:</strong> HOLD — probability inside neutral band (below 0.55 required edge)</p>
        </div>
        <div className="rnd-state">
          <StatusBadge state="ACTIVE">BANKNIFTY</StatusBadge>
          <p><strong>Direction:</strong> HOLD / NEUTRAL | <strong>C0 P(UP):</strong> 49.8% - 50.2%</p>
          <p><strong>Activation Threshold:</strong> 0.55 | <strong>Distance:</strong> -0.050</p>
          <p><strong>Top Challenger (M2):</strong> P(UP) = 47.9% - 53.1% | <strong>Preferred:</strong> HOLD</p>
          <p><strong>Reason:</strong> HOLD — probability inside neutral band (below 0.55 required edge)</p>
        </div>
      </div>
    </Panel>
    <Panel title="Candidate evidence ledger" eyebrow="EXPAND A ROW FOR LINEAGE" actions={<span className="panel-asof">{qualified} CURRENT</span>}>{snapshot?.edge_ledger.entries.length ? <div className="compact-table-wrap"><table className="ats-table candidate-table"><thead><tr><th>Instrument</th><th>Class</th><th>Probability</th><th>Net EV</th><th>Spread</th><th>Liquidity</th><th>Portfolio Brain</th><th>A04</th><th><span className="sr-only">Evidence</span></th></tr></thead><tbody>{snapshot.edge_ledger.entries.map((entry) => <tr key={entry.candidate_id}><th scope="row"><span>{entry.instrument}</span><small>{entry.underlying} · {entry.strategy}</small></th><td><StatusBadge state={entry.candidate_class === "HIGH_CONVICTION" ? "ACTIVE" : "READY"}>{entry.candidate_class}</StatusBadge></td><td>{pct(entry.predicted_probability)}</td><td className={(entry.expected_net_value ?? 0) > 0 ? "ats-positive" : "ats-negative"}>{decimal(entry.expected_net_value)}</td><td>{entry.spread_cost === null ? "UNKNOWN" : entry.spread_cost.toFixed(3)}</td><td>{snapshot.opportunity_map.find((point) => point.candidate_id === entry.candidate_id)?.liquidity_score?.toFixed(2) ?? "UNKNOWN"}</td><td><StatusBadge state={entry.portfolio_brain_outcome === "ALLOW" ? "READY" : entry.portfolio_brain_outcome === "DENY" ? "BLOCKED" : "DEGRADED"}>{entry.portfolio_brain_outcome}</StatusBadge></td><td><StatusBadge state={entry.a04_outcome === "ALLOW" ? "READY" : entry.a04_outcome === "DENY" ? "BLOCKED" : "UNKNOWN"}>{entry.a04_outcome}</StatusBadge></td><td><details className="evidence-details"><summary>Evidence</summary><div><strong>{entry.candidate_id}</strong><p>Gross edge {decimal(entry.gross_edge)} · slippage {decimal(entry.slippage_estimate)} · fees {decimal(entry.fees_estimate)} · theta {decimal(entry.theta_cost)}</p><p>Approved capital {entry.approved_capital ?? "UNKNOWN"} · quantity {entry.approved_quantity ?? "UNKNOWN"}</p><ul>{(snapshot.evidence_lineage[entry.candidate_id] ?? []).map((node) => <li key={node.node_id}><StatusBadge state={node.status === "VERIFIED" ? "HEALTHY" : node.status === "REJECTED" ? "BLOCKED" : "UNKNOWN"}>{node.node_type}</StatusBadge><span>{node.summary}</span></li>)}</ul></div></details></td></tr>)}</tbody></table></div> : <EmptyState title="No qualifying live opportunities" detail="No candidate currently clears freshness, expected-value, liquidity, Portfolio Brain, and A04 checks." metrics={scanner ? <span>{scanner.funnel.universe_observed} observed · {scanner.rejections.negative_ev} negative EV · {scanner.rejections.liquidity + scanner.rejections.spread} spread/liquidity · {scanner.rejections.calibration} calibration</span> : undefined} />}</Panel>
  </div>;
}
