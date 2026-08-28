"use client";

import { useOperatorState } from "../system/OperatorStateProvider";
import { Panel, LoadingState } from "../system/SurfaceStates";
import { StatusBadge } from "../system/SystemHealthIndicator";

function age(iso: string | undefined) {
  if (!iso) return "UNKNOWN";
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  return seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ago`;
}
export function MarketPanel({ detailed = false }: { detailed?: boolean }) {
  const { runtime, pipeline, loading } = useOperatorState();
  const markets = [
    {
      symbol: "NIFTY",
      value: pipeline?.nifty_last,
      atm: pipeline?.nifty_atm ?? "UNKNOWN",
      regime: pipeline?.nifty_regime ?? "UNKNOWN",
      volatility: pipeline?.nifty_volatility ?? "UNKNOWN",
    },
    {
      symbol: "BANKNIFTY",
      value: pipeline?.banknifty_last,
      atm: pipeline?.banknifty_atm ?? "UNKNOWN",
      regime: pipeline?.banknifty_regime ?? "UNKNOWN",
      volatility: pipeline?.banknifty_volatility ?? "UNKNOWN",
    },
  ];
  return <Panel title="Live market" eyebrow="NSE UNDERLYINGS" actions={<span className="panel-asof">AS OF {age(runtime?.updated_at)}</span>} className={detailed ? "market-panel market-panel-wide" : "market-panel"}>{loading && !runtime ? <LoadingState rows={2} /> : <div className="market-list">{markets.map((market) => <article className="market-row" key={market.symbol}><div className="market-symbol"><strong>{market.symbol}</strong><StatusBadge state={runtime?.feed_healthy ? "HEALTHY" : runtime ? "STALE" : "UNKNOWN"}>FEED</StatusBadge></div><div className="market-price"><strong>{market.value ?? "—"}</strong><span>Change unavailable</span></div><dl><div><dt>ATM</dt><dd>{market.atm}</dd></div><div><dt>OPTION WINDOW</dt><dd>{pipeline?.attached ? "ACTIVE" : "UNKNOWN"}</dd></div><div><dt>REGIME</dt><dd>{market.regime}</dd></div><div><dt>VOLATILITY</dt><dd>{market.volatility}</dd></div></dl></article>)}</div>}</Panel>;
}
