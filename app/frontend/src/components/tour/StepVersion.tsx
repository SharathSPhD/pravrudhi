import type { TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";

export function StepVersion({ data }: { data: TourData }) {
  const { version, capabilities } = data;

  if (!version && !capabilities) {
    return <Empty>This recording carries no version or capability block.</Empty>;
  }

  const availableTools = capabilities?.tools.filter((t) => t.available).length ?? 0;
  const availableAgents = capabilities?.agents.filter((a) => a.available).length ?? 0;

  return (
    <div className="space-y-4">
      {version && (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">engine</div>
              <div className="font-mono text-sm text-[var(--color-text)]">{version.engine}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">kernel</div>
              <div className="font-mono text-sm text-[var(--color-text)]">{version.kernel}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">commit</div>
              <div className="font-mono text-sm text-[var(--color-text)]">{version.commit}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">exported</div>
              <div className="font-mono text-sm text-[var(--color-text)]">{version.exported_at}</div>
            </div>
          </div>
        </div>
      )}

      {capabilities && (
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">agents</div>
              <div className="text-xl font-semibold tabular-nums text-[var(--color-text)]">
                {availableAgents}/{capabilities.agents.length}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">tools</div>
              <div className="text-xl font-semibold tabular-nums text-[var(--color-text)]">
                {availableTools}/{capabilities.tools.length}
              </div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">recipes</div>
              <div className="text-xl font-semibold tabular-nums text-[var(--color-text)]">{capabilities.recipes}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">policies</div>
              <div className="text-xl font-semibold tabular-nums text-[var(--color-text)]">{capabilities.policies.length}</div>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {capabilities.policies.map((p) => (
              <span key={p} className="rounded-full border border-[var(--color-border)] px-2 py-0.5 font-mono text-[11px] text-[var(--color-text-dim)]">
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-[var(--color-muted)]">
        This snapshot carries what shipped as of this export, not a diff against the version before it — there is no
        changelog recorded here.
      </p>
    </div>
  );
}
