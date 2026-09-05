"use client";

// What the loop actually produced, and what an external scorer said about it.
//
// This page read `candidates()` until now, which is the engine's internal selection record and returns nothing at
// all on the recorded site. So the page that exists to show the result showed an empty list. It reads `models()`
// instead: promotions, each carrying the before and after that a third-party scorer measured.

import { useEffect, useState } from "react";
import { Package, ArrowRight } from "lucide-react";
import { models, type PromotedModel } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

function headline(m: Record<string, Record<string, number>> | null): { name: string; value: number } | null {
  if (!m) return null;
  for (const [task, metrics] of Object.entries(m)) {
    for (const [metric, value] of Object.entries(metrics)) {
      if (metric.includes("stderr") || !Number.isFinite(value)) continue;
      return { name: `${task} ${metric}`, value };
    }
  }
  return null;
}

function Delta({ model }: { model: PromotedModel }) {
  const before = headline(model.external_before);
  const after = headline(model.external_after);

  if (!before || !after) {
    return (
      <p className="mt-3 text-xs leading-5 text-[var(--color-text-dim)]">
        No external score has been recorded for this promotion yet. The engine&apos;s own selection is not shown here
        as if it were one.
      </p>
    );
  }

  const delta = after.value - before.value;
  const up = delta > 0;
  return (
    <div className="mt-3 border-t border-[var(--color-border)] pt-3">
      <p className="font-mono text-[11px] text-[var(--color-text-dim)]">{after.name}</p>
      <div className="mt-2 flex items-center gap-3 text-sm">
        <span className="tabular-nums text-[var(--color-text-dim)]">{(before.value * 100).toFixed(1)}%</span>
        <ArrowRight size={14} className="text-[var(--color-text-dim)]" />
        <span className="tabular-nums text-[var(--color-text)]">{(after.value * 100).toFixed(1)}%</span>
        <span
          className={`ml-auto tabular-nums ${up ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"}`}
        >
          {up ? "+" : ""}
          {(delta * 100).toFixed(1)}%
        </span>
      </div>
    </div>
  );
}

export default function ModelsPage() {
  const [rows, setRows] = useState<PromotedModel[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    models()
      .then((data) => {
        if (!cancelled) setRows(data);
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
      <PageHeader
        title="Models"
        subtitle="What the loop promoted, and what an external scorer measured before and after."
      />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">This engine build does not report promotions yet.</p>
        )}
        {!unsupported && rows === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!unsupported && rows !== null && rows.length === 0 && (
          <p className="max-w-2xl text-sm leading-6 text-[var(--color-text-dim)]">
            Nothing has been promoted yet. A promotion happens when a change survives the loop&apos;s own gate and is
            then scored by a benchmark outside the engine.
          </p>
        )}
        {!unsupported && rows !== null && rows.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map((m) => (
              <article
                key={m.id}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
              >
                <div className="flex items-center gap-2">
                  <Package size={16} className="text-[var(--color-text-dim)]" />
                  <span className="font-mono text-sm text-[var(--color-text)]">{m.id}</span>
                  <span className="ml-auto text-[11px] text-[var(--color-text-dim)]">
                    {m.track} · night {m.night}
                  </span>
                </div>
                <Delta model={m} />
                {m.artefact && (
                  <p className="mt-3 truncate font-mono text-[11px] text-[var(--color-text-dim)]" title={m.artefact}>
                    {m.artefact}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
