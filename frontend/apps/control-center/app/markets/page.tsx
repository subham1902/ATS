import { MarketPanel } from "../../components/overview/MarketPanel";

export const metadata = { title: "Markets" };
export default function MarketsPage() { return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">LIVE MARKET</span><h1>Markets</h1><p>NIFTY and BANKNIFTY feed truth. Missing analytical fields remain explicitly unknown.</p></div></div><MarketPanel detailed /></div>; }
