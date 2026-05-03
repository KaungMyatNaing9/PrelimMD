import type { Metadata } from "next";
import { Fraunces, Inter } from "next/font/google";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD - Patient Check-In",
  description: "Self check-in kiosk for patients",
};

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-display",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${inter.variable}`}>
        <div className="shell">
          <header className="site-header">
            <div className="header-inner">
              <div className="brand">
                <div className="brand-mark">PM</div>
                <div>
                  <div className="brand-name">PrelimMD</div>
                  <div className="brand-sub">Patient Check-In</div>
                </div>
              </div>
              <div style={{ fontSize: "0.86rem", color: "var(--text-soft)" }}>
                Need help? Ask a staff member.
              </div>
            </div>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
