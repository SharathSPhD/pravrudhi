import type { TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";
import { DispatchesTable } from "@/components/swarm/DispatchesTable";

export function StepSwarm({ data }: { data: TourData }) {
  const { swarm } = data;

  if (!swarm) {
    return <Empty>This recording predates the swarm view. Nothing to show.</Empty>;
  }

  const all = [...swarm.subagent_runs, ...swarm.selfbuild_runs];
  if (all.length === 0) {
    return <Empty>No dispatches are recorded in this run.</Empty>;
  }

  const accepted = all.filter((r) => r.accepted).length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 divide-x divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-center">
        <div className="px-3 py-3">
          <div className="text-xl font-semibold tabular-nums">{all.length}</div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">dispatched</div>
        </div>
        <div className="px-3 py-3">
          <div className="text-xl font-semibold tabular-nums text-emerald-400">{accepted}</div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">accepted</div>
        </div>
        <div className="px-3 py-3">
          <div className="text-xl font-semibold tabular-nums">{all.length - accepted}</div>
          <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">rejected</div>
        </div>
      </div>
      <div className="max-h-96 space-y-2 overflow-y-auto">
        <DispatchesTable subagentRuns={swarm.subagent_runs} selfbuildRuns={swarm.selfbuild_runs} />
      </div>
    </div>
  );
}
