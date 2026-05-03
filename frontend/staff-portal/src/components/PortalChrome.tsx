"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/", label: "Dashboard", short: "Overview" },
  { href: "/patients", label: "Patients", short: "Roster" },
  { href: "/followups", label: "Follow-Ups", short: "Calls" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/";
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

function titleForPath(pathname: string) {
  if (pathname.startsWith("/patients")) {
    return {
      title: "Patient Roster",
      subtitle: "Review demographics, upcoming visits, and intake readiness.",
    };
  }

  if (pathname.startsWith("/followups")) {
    return {
      title: "Follow-Up Operations",
      subtitle: "Track post-discharge calls, question sets, and patient outreach.",
    };
  }

  if (pathname.startsWith("/visits/")) {
    return {
      title: "Visit Workflow",
      subtitle: "Prepare forms, run prefill, and launch the patient-facing check-in flow.",
    };
  }

  return {
    title: "Nurse Portal",
    subtitle: "Pre-visit intake, scheduling, and readiness at a glance.",
  };
}

export function PortalChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const header = titleForPath(pathname);

  return (
    <div className="portal-shell">
      <aside className="portal-sidebar">
        <Link href="/" className="portal-brand">
          <div className="portal-brand-mark">PM</div>
          <div>
            <div className="portal-brand-name">PrelimMD</div>
            <div className="portal-brand-sub">Clinical Staff Portal</div>
          </div>
        </Link>

        <div className="portal-section-label">Workspace</div>
        <nav className="portal-nav">
          {navItems.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`portal-nav-item${active ? " active" : ""}`}
              >
                <span className="portal-nav-title">{item.label}</span>
                <span className="portal-nav-sub">{item.short}</span>
              </Link>
            );
          })}
        </nav>

        <div className="portal-sidebar-card">
          <div className="portal-section-label">Today</div>
          <h3>AI-assisted intake</h3>
          <p>
            Route patients into prefill, kiosk review, and follow-up scheduling from one place.
          </p>
        </div>
      </aside>

      <div className="portal-main">
        <header className="portal-topbar">
          <div>
            <div className="portal-topbar-label">Pre-Visit Operations</div>
            <h1>{header.title}</h1>
            <p>{header.subtitle}</p>
          </div>
          <div className="portal-user-pill">
            <span className="portal-user-dot" />
            Nurse / Doctor
          </div>
        </header>

        <main className="portal-content">{children}</main>
      </div>
    </div>
  );
}
