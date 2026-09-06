import type { BenchmarkMove, TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";
import { fixed, percent } from "@/lib/num";

function looksFractional(move: BenchmarkMove): boolean {
  return move.baseline.value <= 1 && move.latest.value <= 1;
}

export function StepBenchmark({ data }: { data: TourData }) {
  const moves = data.benchmarkMoves;

  if (moves.length === 0) {
    return <Empty>No objective in this recording has both a baseline and a later measurement yet.</Empty>;
  }

  return (
    <div className="space-y-3">
      {moves.map((move) => {
        const fmt = (v: number) => (looksFractional(move) ? percent(v, 1) : fixed(v, 2));
        const gained = (move.delta ?? 0) > 0;
        return (
          <div key={`${move.objectiveId}-${move.benchmark}`} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <div className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              {move.objectiveId} · {move.benchmark}
            </div>
            <div className="mt-2 flex flex-wrap items-baseline gap-3">
              <span className="text-2xl font-semibold tabular-nums text-[var(--color-muted)]">{fmt(move.baseline.value)}</span>
              <span className="text-[var(--color-muted)]">→</span>
              <span className={`text-3xl font-bold tabular-nums ${gained ? "text-emerald-400" : "text-[var(--color-danger)]"}`}>
                {fmt(move.latest.value)}
              </span>
              {move.delta !== null && (
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    gained ? "bg-emerald-500/15 text-emerald-300" : "bg-red-500/15 text-red-300"
                  }`}
                >
                  {gained ? "+" : ""}
                  {fmt(move.delta)}
                </span>
              )}
            </div>
            <div className="mt-2 text-xs text-[var(--color-text-dim)]">
              {move.baseline.model} · baseline from night {move.baseline.night} (n={move.baseline.n}), latest from night{" "}
              {move.latest.night} (n={move.latest.n})
              {move.significant ? " · statistically significant" : " · not yet significant"}
              {move.targetDelta !== null && (
                <> · target {fmt(move.targetDelta)}{move.met === null ? "" : move.met ? ", met" : ", not met"}</>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
