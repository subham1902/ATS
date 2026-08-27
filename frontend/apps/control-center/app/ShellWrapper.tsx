"use client";
import { Shell } from "../components/Shell";
import { OperatorStateProvider } from "../components/system/OperatorStateProvider";

export function ShellWrapper({ children }: { children: React.ReactNode }) {
  return <OperatorStateProvider><Shell>{children}</Shell></OperatorStateProvider>;
}
