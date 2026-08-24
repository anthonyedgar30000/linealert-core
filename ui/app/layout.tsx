import type { Metadata } from "next";

import InvestigationHandoff from "./investigation-handoff";
import "./globals.css";

export const metadata: Metadata = {
  title: "LineAlert Operator View",
  description: "Role-focused industrial recovery guidance built on one shared machine-evidence core.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <InvestigationHandoff />
        {children}
      </body>
    </html>
  );
}
