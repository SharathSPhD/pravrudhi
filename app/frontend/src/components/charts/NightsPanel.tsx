import { BarChart } from "./BarChart";
import type { DemoNightRow } from "./types";

export function NightsPanel({ track, nights }: { track: string; nights: DemoNightRow[] }) {
  const sorted = [...nights].sort((a, b) => a.night - b.night);
  const categories = sorted.map((n) => `N${n.night}`);

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <p className="text-xs uppercase tracking-wide text-[var(--color-text-dim)]">track {track}</p>
      <div className="mt-3 grid gap-6 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[11px] text-[var(--color-text-dim)]">GPU-hours per night</p>
          <BarChart
            categories={categories}
            series={[{ label: "GPU-h", color: "var(--color-accent)", values: sorted.map((n) => n.spent_gpu_h) }]}
            valueFormatter={(v) => v.toFixed(2)}
          />
        </div>
        <div>
          <p className="mb-2 text-[11px] text-[var(--color-text-dim)]">candidates / promoted / pruned per night</p>
          <BarChart
            categories={categories}
            series={[
              { label: "candidates", color: "var(--color-text-dim)", values: sorted.map((n) => n.candidates) },
              { label: "promoted", color: "var(--color-accent)", values: sorted.map((n) => n.promoted.length) },
              { label: "pruned", color: "var(--color-danger)", values: sorted.map((n) => n.pruned) },
            ]}
            valueFormatter={(v) => v.toFixed(0)}
          />
        </div>
      </div>
    </div>
  );
}
