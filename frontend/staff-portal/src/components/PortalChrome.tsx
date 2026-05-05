"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const navItems = [
  { href: "/", label: "Dashboard", icon: "🏠" },
  { href: "/patients", label: "Patients", icon: "👥" },
  { href: "/calls", label: "Intake Progress", icon: "📊" },
  { href: "/forms-library", label: "Forms Library", icon: "📋" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

function headerCopy(pathname: string) {
  if (pathname.startsWith("/patients")) {
    return {
      title: "Patients",
      subtitle: "Create patient records, schedule visits, and open the intake workspace.",
    };
  }
  if (pathname.startsWith("/calls")) {
    return {
      title: "Intake Progress",
      subtitle: "Monitor intake completion, remaining questions, and patients who are ready for kiosk review.",
    };
  }
  if (pathname.startsWith("/forms-library")) {
    return {
      title: "Forms Library",
      subtitle: "Review reusable templates and upload new PDFs or photos for AI parsing.",
    };
  }
  if (pathname.startsWith("/visits/")) {
    return {
      title: "Visit Workspace",
      subtitle: "Assign forms, generate AI prefill, and hand off to patient check-in.",
    };
  }
  return {
    title: "Dashboard",
    subtitle: "Today's schedule, intake readiness, and patient check-in status.",
  };
}

function formatTodayLabel() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date());
}

export function PortalChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [todayLabel, setTodayLabel] = useState("");
  const header = useMemo(() => headerCopy(pathname), [pathname]);

  useEffect(() => {
    setTodayLabel(formatTodayLabel());
  }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="flex min-h-screen">
        <aside
          className={`hidden border-r border-white/10 bg-navy text-white lg:flex lg:flex-col sticky top-0 h-screen ${
            collapsed ? "lg:w-16" : "lg:w-72"
          } transition-all duration-300 shrink-0`}
        >
          <div className="flex h-full flex-col py-6 overflow-y-auto">
            {/* Logo + collapse button */}
            <div className={`mb-8 ${collapsed ? "flex flex-col items-center gap-3 px-2" : "flex items-center justify-between gap-3 px-4"}`}>
              <Link href="/" className="flex items-center gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white p-1.5 shadow-clinical">
                  <Image src="/logo.png" alt="PrelimMD logo" width={32} height={32} priority />
                </div>
                {!collapsed ? (
                  <div className="min-w-0">
                    <div className="truncate text-lg font-semibold tracking-tight">PrelimMD</div>
                    <div className="text-xs uppercase tracking-[0.18em] text-white/60">Nurse Portal</div>
                  </div>
                ) : null}
              </Link>
              <button
                type="button"
                onClick={() => setCollapsed((v) => !v)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white/70 transition hover:bg-white/10 hover:text-white"
                aria-label="Toggle sidebar"
              >
                {collapsed ? "›" : "‹"}
              </button>
            </div>

            {/* Nav items */}
            <nav className={`space-y-1 ${collapsed ? "px-2" : "px-3"}`}>
              {navItems.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={collapsed ? item.label : undefined}
                    className={`flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition ${
                      collapsed ? "justify-center px-2" : "px-3"
                    } ${
                      active
                        ? "bg-white text-navy shadow-clinical"
                        : "text-white/75 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    <span className="text-base leading-none">{item.icon}</span>
                    {!collapsed ? <span>{item.label}</span> : null}
                  </Link>
                );
              })}
            </nav>

            {/* User badge */}
            <div className={`mt-auto ${collapsed ? "px-2" : "px-3"}`}>
              <div
                className={`rounded-2xl border border-white/10 bg-white/5 p-3 ${
                  collapsed ? "flex justify-center" : ""
                }`}
              >
                <div className={`flex items-center gap-3 ${collapsed ? "justify-center" : ""}`}>
                  <div
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal text-xs font-semibold text-white"
                    title={collapsed ? "Sarah Mitchell, RN" : undefined}
                  >
                    SM
                  </div>
                  {!collapsed ? (
                    <div className="min-w-0">
                      <div className="truncate text-sm font-semibold">Sarah Mitchell, RN</div>
                      <div className="truncate text-xs text-white/60">Pre-Visit Intake Nurse</div>
                    </div>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur">
            <div className="flex flex-col gap-4 px-5 py-5 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate">
                  {todayLabel || " "}
                </div>
                <h1 className="mt-1 text-3xl font-semibold tracking-tight text-navy">{header.title}</h1>
                <p className="mt-1 max-w-3xl text-sm text-slate">{header.subtitle}</p>
              </div>
              <div className="w-full max-w-md">
                <input
                  className="field-input"
                  placeholder="Search patients, visits, or forms"
                  aria-label="Search"
                />
              </div>
            </div>
            <div className="flex gap-2 overflow-x-auto px-5 pb-4 lg:hidden">
              {navItems.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`whitespace-nowrap rounded-full px-4 py-2 text-sm font-semibold transition ${
                      active ? "bg-navy text-white" : "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </header>

          <main className="flex-1 px-5 py-6 sm:px-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
