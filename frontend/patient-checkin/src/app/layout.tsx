import type { Metadata } from "next";
import Image from "next/image";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD - Patient Check-In",
  description: "Self check-in kiosk for patients",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="site-header">
            <div className="header-inner">
              <div className="brand">
                <div className="brand-mark image-mark">
                  <Image src="/logo.png" alt="PrelimMD logo" width={40} height={40} priority />
                </div>
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
