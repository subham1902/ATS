import Link from "next/link";
import { EmptyState, Panel } from "../../components/system/SurfaceStates";
export const metadata = { title: "Trades" };
export default function TradesPage() { return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">PAPER EXECUTION HISTORY</span><h1>Trades</h1><p>Recorded paper orders, fills, and exits appear in the unified activity feed.</p></div></div><Panel title="Trade ledger" eyebrow="PAPER ONLY"><EmptyState title="No standalone trade ledger endpoint" detail="Use the canonical Activity feed to inspect paper orders, fills, position changes, and exits without fabricating trade history." action={<Link className="ats-btn" href="/activity">Open Activity</Link>} /></Panel></div>; }
