import type { Metadata } from "next";
import Link from "next/link";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "PrelimMD",
  description: "AI-powered medical pre-screening assistant",
};

const navigation = [
  { href: "/", label: "Home" },
  { href: "/interview", label: "Interview" },
  { href: "/report", label: "Report" },
  { href: "/booking", label: "Booking" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="site-shell">
          <header className="site-header">
            <div className="header-inner">
              <Link href="/" className="brand">
                <span className="brand-mark" aria-hidden="true">
                  PM
                </span>
                <span className="brand-copy">
                  <strong>PrelimMD</strong>
                  <span>Frontend prototype</span>
                </span>
              </Link>
              <nav className="nav">
                {navigation.map((item) => (
                  <Link key={item.href} href={item.href} className="nav-link">
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
