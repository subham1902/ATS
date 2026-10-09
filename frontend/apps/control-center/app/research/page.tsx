import Link from "next/link";
export default function Research() {
  return (
    <>
      <h1>XAUUSD clean-room research</h1>
      <p>New claims require an immutable XAUUSD dataset, versioned strategy, documented costs and methodology.</p>
      <p>
        Standalone GoldTriple small-account experiments are documented in the repository research reports. Their results
        have not been integrated into production strategy evidence and do not grant promotion or execution authority.
      </p>
      <Link href="/agents/managed">Open Agent Playground and bounded quote research</Link>
      <p>S5 Opening Range Breakout remains DESIGN / RESEARCH_ONLY. Its unresolved design questions remain open.</p>
      <Link href="/datasets">Import and inspect a dataset</Link>
      <p>
        Sealed holdout, point-in-time causality, cost stress and paper-forward evidence are required before promotion.
      </p>
    </>
  );
}
