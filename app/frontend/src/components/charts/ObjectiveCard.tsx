import type { Objective } from "@/lib/api";

function stateColor(state: string): string {
  switch (state) {
    case "measured":
      return "var(--color-accent)";
    case "baseline_only":
      return "var(--color-warn)";
    default:
      return "var(--color-text-dim)";
  }
}

function formatPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function ObjectiveCard({ objective }: { objective: Objective }) {
  return (
    <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-sm text-[var(--color-text)]">{objective.id}</span>
        <span className="ml-auto text-[11px] text-[var(--color-text-dim)]">
          track {objective.track} · {objective.domain}
        </span>
      </div>
      <p className="mt-2 text-xs leading-5 text-[var(--color-text-dim)]">{objective.intent}</p>
      <div className="mt-3 divide-y divide-[var(--color-border)] border-t border-[var(--color-border)]">
        {objective.benchmarks.map((b) => {
          const progress = objective.progress.find((p) => p.benchmark === b.metric);
          return (
            <div key={b.id} className="flex items-center gap-3 py-2 text-xs">
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: stateColor(progress?.state ?? "unmeasured") }}
              />
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-[var(--color-text-dim)]">
                {b.metric}
              </span>
              {progress?.baseline ? (
                <span className="shrink-0 tabular-nums text-[var(--color-text)]">
                  {formatPct(progress.baseline.value)}
                  {progress.latest ? ` → ${formatPct(progress.latest.value)}` : ""}
                </span>
              ) : (
                <span className="shrink-0 text-[var(--color-text-dim)]">unmeasured</span>
              )}
            </div>
          );
        })}
      </div>
    </article>
  );
}
