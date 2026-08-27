"use client";

import Link from "next/link";
import { useOperatorState } from "./OperatorStateProvider";

export function GlobalAlerts() {
  const { alerts, dismissAlert } = useOperatorState();
  if (!alerts.length) return null;
  return <aside className="alert-rail" aria-label="System alerts">{alerts.map((alert) => <div key={alert.id} className={`global-alert alert-${alert.severity}`} role={alert.severity === "critical" ? "alert" : "status"}><span className="alert-icon" aria-hidden="true">{alert.severity === "critical" ? "!" : alert.severity === "warning" ? "▲" : "i"}</span><div><strong>{alert.title}</strong><span>{alert.detail}</span></div><Link href={alert.href}>View<span className="sr-only"> {alert.title}</span></Link>{alert.dismissible ? <button type="button" onClick={() => dismissAlert(alert.id)} aria-label={`Dismiss ${alert.title}`}>×</button> : null}</div>)}</aside>;
}
