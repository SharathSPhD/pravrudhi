import type { SelfBuildRun, SubagentRun } from "@/lib/swarm";
import { secs } from "@/lib/num";

interface Dispatch {
  key: string;
  kind: "objective" | "self-build";
  label: string;
  at: string;
  accepted: boolean;
  route: string;
  wall_s: number;
  files: string[];
  reasons: string[];
}

function mergeDispatches(subagentRuns: SubagentRun[], selfbuildRuns: SelfBuildRun[]): Dispatch[] {
  const fromSubagents: Dispatch[] = subagentRuns.map((r, i) => ({
    key: `subagent-${i}-${r.task_id}`,
    kind: "objective",
    label: `${r.objective} · ${r.step}`,
    at: r.at,
    accepted: r.accepted,
    route: r.route,
    wall_s: r.wall_s,
    files: r.files,
    reasons: r.reasons,
  }));
  const fromSelfbuild: Dispatch[] = selfbuildRuns.map((r, i) => ({
    key: `selfbuild-${i}-${r.task_id}`,
    kind: "self-build",
    label: r.task_id,
    at: r.at,
    accepted: r.accepted,
    route: r.route,
    wall_s: r.wall_s,
    files: r.files,
    reasons: r.reasons,
  }));
  // Both run logs are already newest-last (see server.py's `reversed(...runs(root)[-100:])`), so a plain
  // string comparison on the ISO timestamp puts the merged list newest-first without assuming either input
  // was sorted on its own.
  return [...fromSubagents, ...fromSelfbuild].sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
}

export function DispatchesTable({
  subagentRuns,
  selfbuildRuns,
}: {
  subagentRuns: SubagentRun[];
  selfbuildRuns: SelfBuildRun[];
}) {
  const dispatches = mergeDispatches(subagentRuns, selfbuildRuns);
  if (dispatches.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No dispatches recorded yet.</p>;
  }

  return (
    <div className="space-y-2">
      {dispatches.map((d) => (
        <div key={d.key} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span
              className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                d.accepted ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"
              }`}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
              {d.accepted ? "accepted" : "rejected"}
            </span>
            <span className="text-[10px] uppercase tracking-wide text-[var(--color-text-dim)]">{d.kind}</span>
            <span className="font-mono text-[13px] text-[var(--color-text)]">{d.label}</span>
            <span className="ml-auto font-mono text-[11px] text-[var(--color-text-dim)]">{d.route}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-[var(--color-text-dim)]">
            <span>{secs(d.wall_s)}</span>
            <span>{d.at}</span>
            {d.files.length > 0 && <span className="truncate font-mono">{d.files.join(", ")}</span>}
          </div>
          {d.reasons.length > 0 && (
            <ul className="mt-1 list-inside list-disc text-[11px] text-[var(--color-text-dim)]">
              {d.reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
