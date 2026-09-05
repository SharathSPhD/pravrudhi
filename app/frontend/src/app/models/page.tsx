"use client";

import { useEffect, useState } from "react";
import { candidates, type Candidate } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export default function ModelsPage() {
  const [promoted, setPromoted] = useState<Candidate[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    candidates()
      .then((rows) => {
        if (!cancelled) setPromoted(rows.filter((c) => c.badge === "green"));
      })
      .catch(() => {
        if (!cancelled) setUnsupported(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <PageHeader title="Models" subtitle="What the loop has promoted so far." />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">engine does not report candidates yet.</p>
        )}
        {!unsupported && promoted === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!unsupported && promoted !== null && promoted.length === 0 && (
          <p className="text-sm text-[var(--color-text-dim)]">
            Nothing promoted yet. Start a run from Improve and it will land here.
          </p>
        )}
        {!unsupported && promoted !== null && promoted.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {promoted.map((c) => (
              <div key={c.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <div className="truncate text-sm font-medium text-[var(--color-text)]">{c.id}</div>
                <div className="mt-1 text-xs text-[var(--color-text-dim)]">
                  {c.bucket?.task_family ?? "unknown benchmark"}
                </div>
                <div className="mt-3 text-xs text-[var(--color-text-dim)]">
                  cost {c.cost_gpu_h.toFixed(2)} GPU-h · {c.n_obs} observations
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
