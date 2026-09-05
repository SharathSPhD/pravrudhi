"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Sparkles, History, Package, Server, Settings, Download } from "lucide-react";
import type { ComponentType } from "react";

interface NavItem {
  href: string;
  label: string;
  icon: ComponentType<{ size?: number; className?: string }>;
}

const NAV: NavItem[] = [
  { href: "/", label: "Improve", icon: Sparkles },
  { href: "/runs", label: "Runs", icon: History },
  { href: "/models", label: "Models", icon: Package },
  { href: "/machines", label: "Machines", icon: Server },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/install", label: "Install", icon: Download },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="border-b border-[var(--color-border)] px-5 py-5">
        <div className="text-lg font-semibold tracking-tight text-[var(--color-text)]">Pravrudhi</div>
        <p className="mt-1 text-xs leading-snug text-[var(--color-text-dim)]">
          Improve your model or your agent harness, on your hardware, while you watch.
        </p>
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-[var(--color-surface-raised)] text-[var(--color-text)]"
                  : "text-[var(--color-text-dim)] hover:bg-[var(--color-surface-raised)] hover:text-[var(--color-text)]"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
