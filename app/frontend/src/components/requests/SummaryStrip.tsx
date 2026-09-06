import { fixed } from "@/lib/num";
import type { RequestsResponse } from "@/lib/requests";

export function SummaryStrip({ data }: { data: RequestsResponse }) {
  const states = Object.entries(data.by_state).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="text-2xl font-semibold text-[var(--color-text)]">{fixed(data.open, 0)}</div>
        <div className="text-xs text-[var(--color-text-dim)]">open of {fixed(data.total, 0)} asked</div>
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <div className="text-2xl font-semibold text-[var(--color-text)]">
          {data.oldest_open_days === null ? "—" : `${fixed(data.oldest_open_days, 0)}d`}
        </div>
        <div className="text-xs text-[var(--color-text-dim)]">oldest open ask</div>
      </div>
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        {states.length === 0 ? (
          <div className="text-xs text-[var(--color-text-dim)]">no asks recorded</div>
        ) : (
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--color-text-dim)]">
            {states.map(([state, n]) => (
              <span key={state}>
                <span className="text-[var(--color-text)]">{fixed(n, 0)}</span> {state}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
