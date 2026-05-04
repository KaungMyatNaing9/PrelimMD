"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/patients", label: "Patients" },
  { href: "/calls", label: "Intake Progress" },
  { href: "/forms-library", label: "Forms Library" },
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
    subtitle: "Today’s schedule, intake readiness, and patient check-in status.",
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
          className={`hidden border-r border-white/10 bg-navy text-white lg:flex lg:flex-col ${
            collapsed ? "lg:w-24" : "lg:w-72"
          } transition-all duration-300`}
        >
          <div className="flex h-full flex-col px-4 py-6">
            <div className="mb-8 flex items-center justify-between gap-3">
              <Link href="/" className="flex min-w-0 items-center gap-3 overflow-hidden">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white p-2 shadow-clinical">
                  <Image src="/logo.png" alt="PrelimMD logo" width={36} height={36} priority />
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
                onClick={() => setCollapsed((value) => !value)}
                className="rounded-xl px-3 py-2 text-sm font-semibold text-white/80 transition hover:bg-white/10 hover:text-white"
                aria-label="Toggle sidebar"
              >
                {collapsed ? "→" : "←"}
              </button>
            </div>

            <nav className="space-y-2">
              {navItems.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center rounded-2xl px-4 py-3 text-sm font-medium transition ${
                      active ? "bg-white text-navy shadow-clinical" : "text-white/75 hover:bg-white/10 hover:text-white"
                    }`}
                  >
                    {collapsed ? item.label[0] : item.label}
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto rounded-3xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-teal text-sm font-semibold text-white">
                  SM
                </div>
                {!collapsed ? (
                  <div>
                    <div className="text-sm font-semibold">Sarah Mitchell, RN</div>
                    <div className="text-xs text-white/60">Pre-Visit Intake Nurse</div>
                  </div>
                ) : null}
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
