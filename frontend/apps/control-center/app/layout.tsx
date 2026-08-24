import type { ReactNode } from "react";
import { ShellWrapper } from "./ShellWrapper";

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body style={{ margin: 0 }}>
        <ShellWrapper>{children}</ShellWrapper>
      </body>
    </html>
  );
}
