import type { ReactNode } from "react";

export function LoadingState({ rows = 3, label = "Loading current state" }: { rows?: number; label?: string }) {
  return <div role="status" aria-label={label} style={{ display: "grid", gap: 8 }}>{Array.from({ length: rows }, (_, index) => <div className="ats-skeleton" key={index} style={{ width: `${96 - index * 8}%` }} />)}<span className="sr-only">{label}</span></div>;
}
export function EmptyState({ title, detail, metrics, action }: { title: string; detail: string; metrics?: ReactNode; action?: ReactNode }) {
  return <div className="surface-empty" role="status"><span className="surface-empty-icon" aria-hidden="true">◇</span><strong>{title}</strong><p>{detail}</p>{metrics ? <div>{metrics}</div> : null}{action}</div>;
}
export function ErrorState({ title = "Unable to load current state", detail, onRetry }: { title?: string; detail: string; onRetry?: () => void }) {
  return <div className="surface-error" role="alert"><span aria-hidden="true">!</span><div><strong>{title}</strong><p>{detail}</p></div>{onRetry ? <button type="button" className="ats-btn" onClick={onRetry}>Retry</button> : null}</div>;
}
export function Panel({ title, eyebrow, actions, children, className = "" }: { title: string; eyebrow?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={`ats-panel ${className}`}><header className="ats-panel-header"><div>{eyebrow ? <span className="panel-eyebrow">{eyebrow}</span> : null}<h2>{title}</h2></div>{actions}</header><div className="ats-panel-body">{children}</div></section>;
}
