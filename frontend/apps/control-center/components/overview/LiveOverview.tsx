"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useOperatorState } from "../system/OperatorStateProvider";
import { useOperatorIntelligence } from "../../hooks/useOperatorIntelligence";
import { StatusBadge } from "../system/SystemHealthIndicator";
import { EmptyState, ErrorState, LoadingState, Panel } from "../system/SurfaceStates";
import { MetricStrip } from "../system/MetricStrip";
import { StatusStrip } from "./StatusStrip";
import { MarketCard } from "./MarketCard";
import { LiveChart } from "./LiveChart";
import { PredictionPanel } from "./PredictionPanel";
import { ScannerFeed } from "./ScannerFeed";
import { PipelineJourney } from "./PipelineJourney";
import { RejectionFunnel } from "./RejectionFunnel";
import { ActivityStream } from "./ActivityStream";
import { PositionPanel } from "./PositionPanel";
import { CapitalPanel } from "./CapitalPanel";
import { WatchlistPanel } from "./WatchlistPanel";
import { formatTimeIST } from "../../lib/formatTime";

const pnl = (value: number) => `${value >= 0 ? "+" : "−"}₹${Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
const amount = (value: string | undefined) => value === undefined ? "—" : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export function LiveOverview() {
  const state = useOperatorState();
  const { runtime, pipeline, harness, activity, events, sseStatus, loading, error, refresh } = state;
  const { snapshot: oi, loading: oiLoading } = useOperatorIntelligence(5000);

  const totalPnl = useMemo(() => Number(runtime?.pnl.realized ?? 0) + Number(runtime?.pnl.unrealized ?? 0), [runtime?.pnl.realized, runtime?.pnl.unrealized]);

  const predictions = useMemo(() => {
    if (oi?.scanner.predictions) return Object.values(oi.scanner.predictions);
    return [];
  }, [oi?.scanner.predictions]);

  const recentPredictions = useMemo(() => oi?.scanner.recent_predictions ?? [], [oi?.scanner.recent_predictions]);

  const harnessState = harness?.harness.state;
  const harnessView = harnessState === "HEALTHY" ? "READY" : harnessState === "DEGRADED" ? "DEGRADED" : harnessState === "STOPPED" ? "OFFLINE" : "UNKNOWN";
  const activeAgents = (harness?.agents ?? []).map((a) => a.agent_type);

  return (
    <div className="ats-page dashboard-page">
      {/* Page heading */}
      <div className="ats-page-heading">
        <div>
          <span className="eyebrow">LIVE OPERATIONS CONSOLE</span>
          <h1>ATS Dashboard</h1>
          <p>Market state, predictions, scanner activity, and paper positions in real time.</p>
        </div>
        <div className="page-provenance">
          <StatusBadge state={sseStatus === "connected" ? "ACTIVE" : sseStatus === "connecting" ? "DEGRADED" : "OFFLINE"}>
            {sseStatus === "connected" ? "LIVE STREAM" : sseStatus.toUpperCase()}
          </StatusBadge>
          <span>A2_PAPER · no live authority</span>
        </div>
      </div>

      {error ? <ErrorState detail={error} onRetry={() => void refresh()} /> : null}

      {/* TOP STATUS STRIP */}
      <StatusStrip />

      {/* KEY METRICS */}
      <MetricStrip items={[
        { label: "Session P&L", value: runtime ? pnl(totalPnl) : "—", tone: totalPnl > 0 ? "positive" : totalPnl < 0 ? "negative" : "neutral" },
        { label: "Available", value: amount(runtime?.capital.available) },
        { label: "Committed", value: amount(runtime?.capital.used) },
        { label: "Drawdown", value: runtime ? `${(Number(runtime.pnl.drawdown_fraction) * 100).toFixed(2)}%` : "—", tone: Number(runtime?.pnl.drawdown_fraction ?? 0) > 0 ? "negative" : "neutral" },
        { label: "Positions", value: String(runtime?.open_positions.length ?? 0) },
        { label: "Qualified", value: String(pipeline?.candidates_qualified ?? 0) },
      ]} />

      {/* MARKET CARDS ROW */}
      <div className="dash-market-row">
        {predictions.length > 0 ? predictions.map((pred) => (
          <MarketCard key={pred.underlying} symbol={pred.underlying as "NIFTY" | "BANKNIFTY"} prediction={pred} />
        )) : (
          <>
            <MarketCard symbol="NIFTY" />
            <MarketCard symbol="BANKNIFTY" />
          </>
        )}
      </div>

      {/* ACTIVE WATCHLIST */}
      <WatchlistPanel predictions={predictions} />

      {/* LIVE CHARTS ROW */}
      <div className="dash-charts-row">
        <LiveChart symbol="NIFTY" events={events} />
        <LiveChart symbol="BANKNIFTY" events={events} />
      </div>

      {/* PREDICTION PANELS */}
      {predictions.length > 0 && (
        <Panel title="Live Predictions" eyebrow="CHAMPION & CHALLENGERS">
          <div className="dash-predictions-row">
            {predictions.map((pred) => (
              <PredictionPanel key={pred.underlying} prediction={pred} />
            ))}
          </div>
        </Panel>
      )}

      {/* DECISION PIPELINE / FUNNEL */}
      {oi?.scanner && (
        <Panel title="Decision Funnel" eyebrow="UNIVERSE → QUALIFIED CANDIDATE">
          <RejectionFunnel
            funnel={oi.scanner.funnel}
            rejections={oi.scanner.rejections}
            qualified={oi.edge_ledger.entries.length}
          />
        </Panel>
      )}

      {/* PIPELINE JOURNEY - show latest candidates */}
      {oi?.edge_ledger.entries && oi.edge_ledger.entries.length > 0 && (
        <Panel title="Pipeline Journey" eyebrow="CANDIDATE STAGE PROGRESSION" actions={<Link className="panel-link" href="/candidates">Full ledger →</Link>}>
          <div className="dash-pipeline-list">
            {oi.edge_ledger.entries.slice(0, 5).map((entry) => (
              <PipelineJourney key={entry.candidate_id} entry={entry} />
            ))}
          </div>
        </Panel>
      )}

      {/* LIVE SCANNER FEED */}
      {recentPredictions.length > 0 && (
        <Panel title="Live Scanner" eyebrow="SCANNER ACTIVITY FEED" actions={<span className="panel-asof">{recentPredictions.length} recent</span>}>
          <ScannerFeed predictions={recentPredictions} />
        </Panel>
      )}

      {/* TWO-COLUMN: POSITIONS + CAPITAL */}
      <div className="dash-bottom-row">
        <PositionPanel />
        <CapitalPanel />
      </div>

      {/* ACTIVITY STREAM */}
      <Panel title="Activity Stream" eyebrow="OPERATIONAL EVENTS" actions={<span className="panel-asof">{events.length} events</span>}>
        <ActivityStream events={events} />
      </Panel>

      {/* HARNESS & AGENTS */}
      <Panel title="Harness & Agents" eyebrow="ADVISORY_ONLY" actions={<Link className="panel-link" href="/harness">Console →</Link>}>
        <div className="dash-harness">
          <div className="dash-harness-status">
            <StatusBadge state={harnessView === "READY" ? "HEALTHY" : harnessView === "DEGRADED" ? "DEGRADED" : harnessView === "OFFLINE" ? "OFFLINE" : "UNKNOWN"}>
              HARNESS
            </StatusBadge>
            <strong>{harness?.llm?.primary_model ?? "Model unavailable"}</strong>
            <span>{harness?.harness.active_sessions ?? 0} sessions · {harness?.agents.length ?? 0} agents</span>
          </div>
          {activeAgents.length > 0 && (
            <div className="dash-agent-list">
              {harness?.agents.map((a) => (
                <div key={a.agent_type} className="dash-agent-item">
                  <span className={`dash-agent-dot ${a.status === "ACTIVE" ? "dot-active" : ""}`} />
                  <strong>{a.agent_type}</strong>
                  <span>{a.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Panel>

      {/* RECENT ACTIVITY */}
      <Panel title="Recent Activity" eyebrow="MATERIAL EVENTS">
        {activity.length > 0 ? (
          <ul className="dash-activity-list">
            {activity.slice(0, 10).map((a) => (
              <li key={a.activity_id}>
                <time>{formatTimeIST(a.occurred_at)}</time>
                <strong>{a.event_kind.replaceAll("_", " ")}</strong>
                <span>{a.summary}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No recent activity" detail="Material events appear as the ATS processes market data." />
        )}
      </Panel>
    </div>
  );
}
