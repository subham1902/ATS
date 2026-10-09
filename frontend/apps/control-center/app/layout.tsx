import type { ReactNode } from "react";
import type { Metadata } from "next";
import "./globals.css";
import { ShellWrapper } from "./ShellWrapper";

export const metadata: Metadata = {
  title: "ATS · XAUUSD Laboratory",
  description: "XAUUSD research, observed MetaTrader market data and deterministic paper authorization.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body style={{ margin: 0 }} suppressHydrationWarning>
        <ShellWrapper>{children}</ShellWrapper>
      </body>
    </html>
  );
}
