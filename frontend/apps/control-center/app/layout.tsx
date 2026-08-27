import type { ReactNode } from "react";
import { ShellWrapper } from "./ShellWrapper";
import "./globals.css";

export const metadata = {
  title: { default: "ATS Control Center", template: "%s · ATS" },
  description: "A2 paper trading operator control center",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <ShellWrapper>{children}</ShellWrapper>
      </body>
    </html>
  );
}
