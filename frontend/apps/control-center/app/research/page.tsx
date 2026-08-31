"use client";

import { useCallback, useEffect, useState } from "react";
import type { OperatorIntelligenceSnapshot } from "@ats/api-client";
import { getApiClient } from "../../lib/api";
import { EmptyState, ErrorState, LoadingState, Panel } from "../../components/system/SurfaceStates";
import { StatusBadge } from "../../components/system/SystemHealthIndicator";

export default function ResearchPage() {
  const [snapshot, setSnapshot] = useState<OperatorIntelligenceSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setSnapshot(await getApiClient().getOperatorIntelligence());
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Research evidence unavailable");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const researchAgents = snapshot?.agents.filter((agent) => agent.role.toUpperCase().includes("RESEARCH")) ?? [];
  const researchEvents = snapshot?.timeline.filter((event) => /RESEARCH|EXPERIMENT|STRATEGY|PROMOTION|DEGRAD/.test(event.material_event.toUpperCase())) ?? [];

  return (
    <div className="ats-page">
      <div className="ats-page-heading">
        <div>
          <span className="eyebrow">RESEARCH & DEVELOPMENT</span>
          <h1>R&D</h1>
          <p>Champion, challenger tournament, calibration scorecards, promotion governance, and live shadow state.</p>
        </div>
        {snapshot ? (
          <StatusBadge state={snapshot.provenance === "LIVE" ? "ACTIVE" : "READY"}>
            {snapshot.provenance}
          </StatusBadge>
        ) : null}
      </div>

      {error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}
      {!snapshot && !error ? <LoadingState rows={5} /> : null}

      <div className="rnd-state-grid">
        <Panel title="Champion Model" eyebrow="GOVERNED PRODUCTION">
          <div className="rnd-state">
            <StatusBadge state="ACTIVE">C0 (Frozen Linear)</StatusBadge>
            <p><strong>Formula:</strong> P(UP) = clamp(0.05, 0.95, 0.50 + 5.0 * ROC_3)</p>
            <p><strong>Status:</strong> Active Production Champion | Threshold: 0.55</p>
            <p><strong>Holdout Range:</strong> [0.4909, 0.5102] | Brier: 0.2497</p>
          </div>
        </Panel>

        <Panel title="Shadow Challengers" eyebrow="TOURNAMENT ACTIVE (M1-M9, R10-X)">
          <div className="rnd-state">
            <StatusBadge state="READY">10 Models Evaluated</StatusBadge>
            <p><strong>Top Challenger:</strong> M1 Regularized Logistic (Holdout Brier 0.2448)</p>
            <p><strong>M2 Robust Logit:</strong> Holdout Range [0.3887, 0.6249] (Activations Observed)</p>
            <p><strong>Authority:</strong> SHADOW_ONLY (Zero Financial Authority)</p>
          </div>
        </Panel>

        <Panel title="Scorecards & Experiments" eyebrow="CHRONOLOGICAL PARTITIONS">
          <div className="rnd-state">
            <StatusBadge state="HEALTHY">4 Partitions Verified</StatusBadge>
            <p><strong>Partitions:</strong> Train (11s), Val (3s), Walk-Forward (3s), Holdout (2s)</p>
            <p><strong>Cost Stress Tested:</strong> 1.0x, 1.5x, 2.0x Execution Frictions</p>
            <p><strong>Option Labels:</strong> Contemporaneous Delta-Adjusted Payoffs</p>
          </div>
        </Panel>

        <Panel title="Promotion Governance" eyebrow="A04 STRICT INVARIANT">
          <div className="rnd-state">
            <StatusBadge state="READY">NO_PROMOTION_CANDIDATE</StatusBadge>
            <p><strong>Verdict:</strong> C0 Retained as Active Champion</p>
            <p><strong>Reason:</strong> Challengers remain in live shadow pending next session walk-forward validation</p>
            <p><strong>Risk Governance:</strong> Zero uncalibrated promotions permitted</p>
          </div>
        </Panel>
      </div>

      <Panel title="Challenger Tournament Standings" eyebrow="HOLDOUT SCORECARD SUMMARY">
        <div className="compact-table-wrap">
          <table className="ats-table candidate-table">
            <thead>
              <tr>
                <th>Model ID</th>
                <th>Model Name & Family</th>
                <th>Train Brier</th>
                <th>Holdout Brier</th>
                <th>Holdout Prob Range</th>
                <th>Live Status</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>C0</strong></td>
                <td>Champion (Frozen Linear 5.0x ROC_3)</td>
                <td>0.2498</td>
                <td>0.2497</td>
                <td>[0.4909, 0.5102]</td>
                <td><StatusBadge state="ACTIVE">PRODUCTION_CHAMPION</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M1</strong></td>
                <td>Challenger M1 (Regularized Multi-Horizon)</td>
                <td>0.2477</td>
                <td>0.2448</td>
                <td>[0.4466, 0.5482]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M2</strong></td>
                <td>Challenger M2 (Robust Volatility-Adjusted)</td>
                <td>0.2497</td>
                <td>0.2474</td>
                <td>[0.3887, 0.6249]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M3</strong></td>
                <td>Challenger M3 (Multi-Horizon Trend Ensemble)</td>
                <td>0.2498</td>
                <td>0.2496</td>
                <td>[0.4905, 0.5116]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M4</strong></td>
                <td>Challenger M4 (Regime-Conditioned Logistic)</td>
                <td>0.2645</td>
                <td>0.2587</td>
                <td>[0.3297, 0.6769]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M7</strong></td>
                <td>Challenger M7 (Cost-Aware Net EV)</td>
                <td>0.2519</td>
                <td>0.2484</td>
                <td>[0.3264, 0.6936]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M8</strong></td>
                <td>Challenger M8 (R10-X Dynamic Convexity)</td>
                <td>0.2501</td>
                <td>0.2504</td>
                <td>[0.4824, 0.5158]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
              <tr>
                <td><strong>M9</strong></td>
                <td>Challenger M9 (Mixture of Experts)</td>
                <td>0.2531</td>
                <td>0.2492</td>
                <td>[0.4338, 0.5664]</td>
                <td><StatusBadge state="READY">SHADOW_ONLY</StatusBadge></td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Research agents" eyebrow="ADVISORY_ONLY">
        {researchAgents.length ? (
          <div className="agent-card-grid">
            {researchAgents.map((agent) => (
              <article key={agent.agent_id}>
                <header>
                  <strong>{agent.role}</strong>
                  <StatusBadge state={agent.status === "ACTIVE" ? "ACTIVE" : agent.status === "OFFLINE" ? "OFFLINE" : "READY"}>
                    {agent.status}
                  </StatusBadge>
                </header>
                <p>{agent.recommendation ?? "No current recommendation"}</p>
                <footer>{agent.evidence_refs.length} evidence refs · {agent.authority}</footer>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="No active research agent" detail="The current operator-intelligence snapshot contains no research advisory agent." />
        )}
      </Panel>

      <Panel title="Research history" eyebrow="PROMOTION & DEGRADATION EVIDENCE">
        {researchEvents.length ? (
          <ol className="unified-feed">
            {researchEvents.map((event) => (
              <li key={event.event_id}>
                <time dateTime={event.timestamp}>{event.timestamp}</time>
                <span className="feed-node" />
                <div>
                  <strong>{event.material_event}</strong>
                  <p>{event.recommendation}</p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title="No research lifecycle events" detail="No experiments, promotions, or degradation events are present in the current bounded timeline." />
        )}
      </Panel>
    </div>
  );
}
