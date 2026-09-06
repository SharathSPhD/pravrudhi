"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { BenchmarkChart } from "@/components/charts/BenchmarkChart";
import { NightsPanel } from "@/components/charts/NightsPanel";
import { ObjectiveCard } from "@/components/charts/ObjectiveCard";
import { CapabilitiesPanel } from "@/components/charts/CapabilitiesPanel";
import { groupBenchmarkSeries } from "@/components/charts/groupExternal";
import type { DemoSnapshot } from "@/components/charts/types";

const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

export default function ProgressPage() {
  const [data, setData] = useState<DemoSnapshot | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(`${basePath}/demo.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`demo.json: HTTP ${res.status}`);
        return res.json() as Promise<DemoSnapshot>;
      })
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <PageHeader
        title="Progress"
        subtitle="Every benchmark the engine has measured, re-rendered on every push from the recorded ledger."
      />
      <div className="space-y-8 p-8">
        {failed && (
          <p className="text-sm text-[var(--color-text-dim)]">Could not load the recorded snapshot (demo.json).</p>
        )}
        {!failed && !data && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {data && <ProgressBody data={data} />}
      </div>
    </div>
  );
}

function ProgressBody({ data }: { data: DemoSnapshot }) {
  const benchmarkGroups = groupBenchmarkSeries(data.external);
  const nightsByTrack = new Map<string, typeof data.nights>();
  for (const n of data.nights) {
    const arr = nightsByTrack.get(n.track) ?? [];
    arr.push(n);
    nightsByTrack.set(n.track, arr);
  }
  const modelsWithAdapters = [
    ...new Set(data.external.filter((r) => r.condition.startsWith("adapter:")).map((r) => r.model)),
  ].sort();

  return (
    <>
      <div className="inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1 text-[11px] text-[var(--color-text-dim)]">
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--color-accent)" }} />
        recorded snapshot · engine v{data.engine.version}
      </div>

      <section>
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Objectives</h2>
        {data.objectives.objectives.length === 0 ? (
          <p className="text-sm text-[var(--color-text-dim)]">No objectives recorded yet.</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {data.objectives.objectives.map((o) => (
              <ObjectiveCard key={o.id} objective={o} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Benchmarks</h2>
        {benchmarkGroups.length === 0 ? (
          <p className="text-sm text-[var(--color-text-dim)]">No external evaluations recorded yet.</p>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {benchmarkGroups.map((g) => (
              <BenchmarkChart key={g.key} group={g} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Nights</h2>
        <div className="grid gap-4">
          {[...nightsByTrack.entries()].map(([track, rows]) => (
            <NightsPanel key={track} track={track} nights={rows} />
          ))}
        </div>
      </section>

      <section>
        <CapabilitiesPanel engineVersion={data.engine.version} recipes={data.recipes} modelsWithAdapters={modelsWithAdapters} />
      </section>
    </>
  );
}
