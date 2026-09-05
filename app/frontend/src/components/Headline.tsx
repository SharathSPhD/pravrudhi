"use client";

import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";
import { demo } from "@/lib/demo";

/** The result, stated first: what the loop actually achieved on a public benchmark. */
export function Headline() {
  const [row, setRow] = useState<{ before: number; after: number; label: string; model: string } | null>(null);

  useEffect(() => {
    demo().then((d) => {
      const base = d.external.find((r) => r.condition === "base" && r.track === "M");
      const after = d.external.find((r) => r.condition.startsWith("adapter:") && r.track === "M");
      if (!base || !after) return;
      const pick = (m: Record<string, Record<string, number>>) => {
        const task = Object.keys(m)[0];
        const key = Object.keys(m[task]).find((k) => !k.includes("stderr")) ?? "";
        return { value: m[task][key], task };
      };
      const b = pick(base.metrics as Record<string, Record<string, number>>);
      const a = pick(after.metrics as Record<string, Record<string, number>>);
      setRow({ before: b.value, after: a.value, label: b.task.toUpperCase(), model: String(after.model ?? "") });
    });
  }, []);

  if (!row) {
    return <div className="h-32 animate-pulse rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]" />;
  }

  const gain = row.after - row.before;
  return (
    <section className="rounded-lg border border-emerald-500/30 bg-gradient-to-br from-emerald-500/10 to-transparent p-5">
      <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
        {row.model.split("/").pop()} on {row.label}, scored by an independent benchmark tool
      </p>
      <div className="mt-3 flex flex-wrap items-baseline gap-3">
        <span className="text-3xl font-semibold tabular-nums text-[var(--color-muted)]">{(row.before * 100).toFixed(1)}%</span>
        <ArrowRight size={22} className="text-[var(--color-muted)]" />
        <span className="text-5xl font-bold tabular-nums text-emerald-400">{(row.after * 100).toFixed(1)}%</span>
        <span className="rounded-full bg-emerald-500/15 px-3 py-1 text-sm font-medium text-emerald-300">
          +{(gain * 100).toFixed(1)} points
        </span>
      </div>
      <p className="mt-3 max-w-2xl text-sm text-[var(--color-muted)]">
        The engine proposed changes, trained each one, measured it against the current best on problems it had never
        seen, and kept only what won. It ran unattended on a single desktop GPU.
      </p>
    </section>
  );
}
