import type { TourData } from "@/lib/tour";
import { meanDelta } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";
import { fixed, percent } from "@/lib/num";

function rationale(recipe: Record<string, unknown>): string | null {
  const r = recipe["rationale"];
  return typeof r === "string" ? r : null;
}

function metricRows(metrics: Record<string, Record<string, number>> | null): { key: string; value: number }[] {
  if (!metrics) return [];
  const rows: { key: string; value: number }[] = [];
  for (const [task, values] of Object.entries(metrics)) {
    if (task.endsWith("_counts")) continue;
    for (const [metric, value] of Object.entries(values)) {
      if (metric.includes("stderr")) continue;
      rows.push({ key: `${task}.${metric}`, value });
    }
  }
  return rows;
}

function formatMetric(key: string, value: number): string {
  return key.includes("pass@1") || key.includes("exact_match") || key.includes("acc,") ? percent(value, 1) : fixed(value, 3);
}

export function StepBoundary({ data }: { data: TourData }) {
  const { promoted, pruned } = data;

  if (!promoted && !pruned) {
    return <Empty>This recording has neither a promotion nor a prune to show.</Empty>;
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
        <div className="text-xs font-medium uppercase tracking-wide text-emerald-400">Promoted</div>
        {!promoted && <p className="mt-2 text-sm text-[var(--color-text-dim)]">Nothing was promoted in this recording.</p>}
        {promoted && (
          <div className="mt-2 space-y-2">
            <div className="font-mono text-sm text-[var(--color-text)]">
              {promoted.id} <span className="text-[var(--color-text-dim)]">· night {promoted.night}</span>
            </div>
            <div className="text-xs text-[var(--color-text-dim)]">track {promoted.track}</div>
            {rationale(promoted.recipe) && <p className="text-sm text-[var(--color-text)]">{rationale(promoted.recipe)}</p>}
            {promoted.external_before && promoted.external_after && (
              <div className="space-y-1 text-xs">
                {metricRows(promoted.external_before).map((row) => {
                  const after = metricRows(promoted.external_after).find((r) => r.key === row.key);
                  return (
                    <div key={row.key} className="flex items-center justify-between gap-2 font-mono">
                      <span className="text-[var(--color-text-dim)]">{row.key}</span>
                      <span>
                        {formatMetric(row.key, row.value)}
                        {after && <> → <span className="text-emerald-400">{formatMetric(row.key, after.value)}</span></>}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-dim)]">Pruned</div>
        {!pruned && <p className="mt-2 text-sm text-[var(--color-text-dim)]">Nothing was pruned in this recording.</p>}
        {pruned && (
          <div className="mt-2 space-y-2">
            <div className="font-mono text-sm text-[var(--color-text)]">
              {pruned.id} <span className="text-[var(--color-text-dim)]">· badge {pruned.badge}</span>
            </div>
            <div className="text-xs text-[var(--color-text-dim)]">
              proposed #{pruned.proposed_seq} · {pruned.edit_family ?? "unknown family"} · surface {pruned.surface ?? "—"}
            </div>
            <div className="text-sm text-[var(--color-text)]">
              boundary reason: <span className="font-mono">{pruned.pruned}</span>
            </div>
            <div className="text-xs text-[var(--color-text-dim)]">
              cost {fixed(pruned.cost_gpu_h, 2)} GPU-h over {pruned.n_obs} observation(s)
              {pruned.xs.length > 0 && <> · mean gain {percent(meanDelta(pruned.xs), 1)}</>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
