"use client";
import { createContext, useContext, useState, type ReactNode } from "react";

/**
 * The data source the operator asked for. This is a request label, not a
 * claim: it never implies the feed is actually serving from that source.
 * What the feed is really doing is reported separately by chart provenance.
 */
export type RequestedSource = "BROKER_LIVE" | "OPEN_TERMINAL";

const LABEL: Record<RequestedSource, string> = {
  BROKER_LIVE: "BROKER LIVE (Upstox)",
  OPEN_TERMINAL: "OPEN TERMINAL (Ref)",
};

export function requestedSourceLabel(source: RequestedSource): string {
  return LABEL[source];
}

interface DataSourceContextValue {
  requestedSource: RequestedSource;
  setRequestedSource: (source: RequestedSource) => void;
}

const DataSourceContext = createContext<DataSourceContextValue | null>(null);

export function DataSourceProvider({
  children,
  initial = "BROKER_LIVE",
}: {
  children: ReactNode;
  initial?: RequestedSource;
}) {
  const [requestedSource, setRequestedSource] = useState<RequestedSource>(initial);
  return (
    <DataSourceContext.Provider value={{ requestedSource, setRequestedSource }}>{children}</DataSourceContext.Provider>
  );
}

export function useDataSource(): DataSourceContextValue {
  const ctx = useContext(DataSourceContext);
  if (!ctx) throw new Error("useDataSource must be used inside DataSourceProvider");
  return ctx;
}
