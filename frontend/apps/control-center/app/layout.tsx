import type { ReactNode } from "react";
import { ShellWrapper } from "./ShellWrapper";

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body style={{ margin: 0 }} suppressHydrationWarning>
        <ShellWrapper>{children}</ShellWrapper>
      </body>
    </html>
  );
}
