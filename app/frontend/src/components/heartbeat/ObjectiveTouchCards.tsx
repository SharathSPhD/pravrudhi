import type { HeartbeatBeat } from "@/lib/heartbeat";

interface ObjectiveTouch {
  objective: string;
  at: string;
  chosen: boolean;
  step: string | null;
  reason: string;
  accepted: boolean | null;
}

// "Last touched" means the most recent beat in which the objective either showed up in `looked_at` or was
// the one `chose`. Iteration order need not be sorted: each candidate is only kept when it is strictly newer
// than what is already recorded for that objective.
function lastTouchedByObjective(beats: HeartbeatBeat[]): ObjectiveTouch[] {
  const map = new Map<string, ObjectiveTouch>();
  for (const beat of beats) {
    const chose = beat.chose;
    const objectives = new Set(beat.looked_at);
    if (chose) objectives.add(chose.objective);
    for (const objective of objectives) {
      const existing = map.get(objective);
      if (existing && existing.at >= beat.at) continue;
      const chosen = chose !== null && chose.objective === objective;
      map.set(objective, {
        objective,
        at: beat.at,
        chosen,
        step: chosen && chose ? chose.step : null,
        reason: beat.reason,
        accepted: chosen ? (beat.result?.accepted ?? null) : null,
      });
    }
  }
  return [...map.values()].sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
}

export function ObjectiveTouchCards({ beats }: { beats: HeartbeatBeat[] }) {
  const touches = lastTouchedByObjective(beats);
  if (touches.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No objectives touched yet.</p>;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {touches.map((t) => (
        <div
          key={t.objective}
          className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono text-sm text-[var(--color-text)]">{t.objective}</span>
            {t.chosen && t.accepted !== null && (
              <span
                className={`inline-flex items-center gap-1.5 text-xs ${
                  t.accepted ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"
                }`}
              >
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
                {t.accepted ? "accepted" : "rejected"}
              </span>
            )}
          </div>
          <div className="mt-1 text-[11px] text-[var(--color-text-dim)]">{t.at}</div>
          {t.chosen ? (
            <div className="mt-1 font-mono text-[12px] text-[var(--color-text)]">{t.step}</div>
          ) : (
            <div className="mt-1 text-[10px] uppercase tracking-wide text-[var(--color-text-dim)]">
              looked at, not chosen
            </div>
          )}
          <div className="mt-1 text-[11px] text-[var(--color-text-dim)]">{t.reason}</div>
        </div>
      ))}
    </div>
  );
}
