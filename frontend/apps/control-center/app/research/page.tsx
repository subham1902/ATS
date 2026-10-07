import Link from "next/link";
export default function Research() {
  return (
    <>
      <h1>XAUUSD clean-room research</h1>
      <p>
        No clean-room backtest has been run. New claims require an immutable XAUUSD dataset, versioned strategy,
        documented costs and methodology.
      </p>
      <p>S5 Opening Range Breakout remains DESIGN / RESEARCH_ONLY. Its unresolved design questions remain open.</p>
      <Link href="/datasets">Import and inspect a dataset</Link>
      <p>
        Sealed holdout, point-in-time causality, cost stress and paper-forward evidence are required before promotion.
      </p>
    </>
  );
}
