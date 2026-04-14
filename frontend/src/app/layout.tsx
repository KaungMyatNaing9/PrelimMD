// src/app/layout.tsx
// Root layout — wraps every page with shared HTML shell, fonts, and global styles.
//
// TODO: Frontend - add global navigation bar component
// TODO: Frontend - add global error boundary / toast notifications

import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD",
  description: "AI-powered medical pre-screening assistant",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
