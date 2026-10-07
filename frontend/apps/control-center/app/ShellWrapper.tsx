"use client";
import type { ReactNode } from "react";
import { Shell } from "../components/Shell";
export function ShellWrapper({ children }: { children: ReactNode }) {
  return <Shell>{children}</Shell>;
}
