"use client";
import { ErrorState } from "../components/system/SurfaceStates";
export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) { return <div className="ats-page"><div className="ats-page-heading"><div><span className="eyebrow">RECOVERY</span><h1>Surface unavailable</h1><p>The global operator bar remains active while this page recovers.</p></div></div><ErrorState detail={error.message || "This route could not render."} onRetry={reset} /></div>; }
