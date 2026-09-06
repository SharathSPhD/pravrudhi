import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { Recipe } from "@/lib/api";

const PAGES = [
  { href: "/", label: "Improve" },
  { href: "/objectives", label: "Objectives" },
  { href: "/chat", label: "Chat" },
  { href: "/runs", label: "Runs" },
  { href: "/models", label: "Models" },
  { href: "/machines", label: "Machines" },
  { href: "/settings", label: "Settings" },
  { href: "/install", label: "Install" },
  { href: "/progress", label: "Progress" },
];

export function CapabilitiesPanel({
  engineVersion,
  recipes,
  modelsWithAdapters,
}: {
  engineVersion: string;
  recipes: Recipe[];
  modelsWithAdapters: string[];
}) {
  const skills = [...new Set(recipes.map((r) => r.skill))].sort();

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--color-text-dim)]">capabilities</p>
      <div className="mt-3 grid gap-4 sm:grid-cols-3">
        <div>
          <p className="text-2xl font-semibold tabular-nums text-[var(--color-text)]">{recipes.length}</p>
          <p className="text-[11px] text-[var(--color-text-dim)]">recipes across {skills.length} skills</p>
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-[var(--color-text)]">{modelsWithAdapters.length}</p>
          <p className="text-[11px] text-[var(--color-text-dim)]">models with adapters</p>
        </div>
        <div>
          <p className="font-mono text-2xl font-semibold text-[var(--color-text)]">v{engineVersion}</p>
          <p className="text-[11px] text-[var(--color-text-dim)]">engine version</p>
        </div>
      </div>
      {skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {skills.map((s) => (
            <span
              key={s}
              className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2 py-0.5 font-mono text-[10px] text-[var(--color-text-dim)]"
            >
              {s}
            </span>
          ))}
        </div>
      )}
      {modelsWithAdapters.length > 0 && (
        <p className="mt-3 truncate font-mono text-[11px] text-[var(--color-text-dim)]">
          {modelsWithAdapters.join(", ")}
        </p>
      )}
      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-[var(--color-border)] pt-3">
        {PAGES.map((p) => (
          <Link
            key={p.href}
            href={p.href}
            className="flex items-center gap-1 text-[11px] text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
          >
            {p.label}
            <ArrowRight size={11} />
          </Link>
        ))}
      </div>
    </div>
  );
}
