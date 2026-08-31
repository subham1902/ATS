"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "../../components/system/SurfaceStates";
import { StatusBadge } from "../../components/system/SystemHealthIndicator";
import { PredictionPanel } from "../../components/overview/PredictionPanel";
import { ScannerFeed } from "../../components/overview/ScannerFeed";
import { PipelineJourney } from "../../components/overview/PipelineJourney";
import { RejectionFunnel } from "../../components/overview/RejectionFunnel";
import { formatTimeIST } from "../../lib/formatTime";

const pct = (value: number | null) => value === null ? "UNKNOWN" : `${(value * 100).toFixed(1)}%`;
const decimal = (value: number | null) => value === null ? "UNKNOWN" : value.toFixed(3);

export default function CandidatesPage() {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSnapshot(await getApiClient().getOperatorIntelligence());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Opportunity read model unavailable");
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const scanner = snapshot?.scanner;
  const predictions = useMemo(() => scanner?.predictions ? Object.values(scanner.predictions) : [], [scanner?.predictions]);
  const recentPredictions = useMemo(() => scanner?.recent_predictions ?? [], [scanner?.recent_predictions]);
  const entries = snapshot?.edge_ledger.entries ?? [];
  const qualified = entries.length;
  const rejected = scanner ? Object.values(scanner.rejections).reduce((sum, value) => sum + (value ?? 0), 0) : 0;

  return (
    <div className="ats-page">
      <div className="ats-page-heading">
        <div>
          <span className="eyebrow">ANALYTICAL PIPELINE</span>
          <h1>Opportunities</h1>
          <p>Every candidate from universe observation through Portfolio Brain and A04 evidence.</p>
        </div>
        {snapshot ? (
          <div className="page-provenance">
            <StatusBadge state={snapshot.provenance === "LIVE" ? "ACTIVE" : "READY"}>{snapshot.provenance}</StatusBadge>
            <span>Cutoff {formatTimeIST(snapshot.scanner.data_cutoff)}</span>
          </div>
        ) : null}
      </div>

      {error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}
      {!snapshot && !error ? <LoadingState rows={5} /> : null}

      {/* DECISION FUNNEL */}
      {scanner && (
        <Panel title="Decision Funnel" eyebrow="UNIVERSE → QUALIFIED CANDIDATE">
          <RejectionFunnel funnel={scanner.funnel} rejections={scanner.rejections} qualified={qualified} />
        </Panel>
      )}

      {/* LIVE PREDICTIONS */}
      {predictions.length > 0 && (
        <Panel title="Live Predictions" eyebrow="CHAMPION & CHALLENGERS">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 12 }}>
            {predictions.map((pred) => <PredictionPanel key={pred.underlying} prediction={pred} />)}
          </div>
        </Panel>
      )}

      {/* SCANNER FEED */}
      {recentPredictions.length > 0 && (
        <Panel title="Live Scanner Feed" eyebrow="SCANNER ACTIVITY" actions={<span className="panel-asof">{recentPredictions.length} recent</span>}>
          <ScannerFeed predictions={recentPredictions} />
        </Panel>
      )}

      {/* QUALIFIED CANDIDATES WITH PIPELINE JOURNEY */}
      {entries.length > 0 && (
        <Panel title="Qualified Candidates" eyebrow="PIPELINE JOURNEY" actions={<span className="panel-asof">{entries.length} candidates</span>}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {entries.map((entry) => <PipelineJourney key={entry.candidate_id} entry={entry} />)}
          </div>
        </Panel>
      )}

      {/* CANDIDATE EVIDENCE LEDGER */}
      <Panel title="Candidate Evidence Ledger" eyebrow="EXPAND FOR LINEAGE" actions={<span className="panel-asof">{qualified} CURRENT</span>}>
        {entries.length ? (
          <div className="compact-table-wrap">
            <table className="ats-table candidate-table">
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th>Class</th>
                  <th>Probability</th>
                  <th>Net EV</th>
                  <th>Spread</th>
                  <th>Liquidity</th>
                  <th>Portfolio Brain</th>
                  <th>A04</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.candidate_id}>
                    <th scope="row">
                      <span>{entry.instrument}</span>
                      <small>{entry.underlying} · {entry.strategy}</small>
                    </th>
                    <td><StatusBadge state={entry.candidate_class === "HIGH_CONVICTION" ? "ACTIVE" : "READY"}>{entry.candidate_class}</StatusBadge></td>
                    <td>{pct(entry.predicted_probability)}</td>
                    <td className={(entry.expected_net_value ?? 0) > 0 ? "ats-positive" : "ats-negative"}>{decimal(entry.expected_net_value)}</td>
                    <td>{entry.spread_cost === null ? "UNKNOWN" : entry.spread_cost.toFixed(3)}</td>
                    <td>{snapshot?.opportunity_map.find((p) => p.candidate_id === entry.candidate_id)?.liquidity_score?.toFixed(2) ?? "UNKNOWN"}</td>
                    <td><StatusBadge state={entry.portfolio_brain_outcome === "ALLOW" ? "READY" : entry.portfolio_brain_outcome === "DENY" ? "BLOCKED" : "DEGRADED"}>{entry.portfolio_brain_outcome}</StatusBadge></td>
                    <td><StatusBadge state={entry.a04_outcome === "ALLOW" ? "READY" : entry.a04_outcome === "DENY" ? "BLOCKED" : "UNKNOWN"}>{entry.a04_outcome}</StatusBadge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No qualifying live opportunities" detail="The current pipeline has not produced a candidate that clears all governed checks." metrics={<span>{scanner?.funnel.universe_observed ?? 0} instruments observed · {rejected} rejected</span>} />
        )}
      </Panel>

      {/* REJECTIONS SUMMARY */}
      {scanner && rejected > 0 && (
        <Panel title="Rejection Analysis" eyebrow="WHY CANDIDATES WERE REJECTED">
          <div className="rejection-grid">
            {Object.entries(scanner.rejections).filter(([, v]) => (v ?? 0) > 0).map(([reason, value]) => (
              <div key={reason}>
                <span>{reason.replaceAll("_", " ")}</span>
                <strong>{value}</strong>
                <i style={{ width: rejected ? `${Math.max(3, ((value ?? 0) / rejected) * 100)}%` : "0" }} />
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}
