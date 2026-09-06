"use client";

import { useEffect, useState } from "react";
import { IS_DEMO } from "@/lib/api";
import { swarmLive, type LiveAgent } from "@/lib/swarm";

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// Recorded state can only ever show what a run once did; a live process table describing "right now" has no
// honest recorded form, so this panel is not part of the demo snapshot at all.
export function LivePanel() {
  const [live, setLive] = useState<LiveAgent[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (IS_DEMO) return;
    let cancelled = false;
    const poll = () => {
      swarmLive()
        .then((rows) => {
          if (!cancelled) {
            setLive(rows);
            setFailed(false);
          }
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Live</h2>
      {IS_DEMO && (
        <p className="text-sm text-[var(--color-text-dim)]">Live process state is not part of a recording.</p>
      )}
      {!IS_DEMO && failed && (
        <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s live process view.</p>
      )}
      {!IS_DEMO && !failed && live.length === 0 && (
        <p className="text-sm text-[var(--color-text-dim)]">No agent process is running right now.</p>
      )}
      {!IS_DEMO && !failed && live.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {live.map((p) => (
            <div key={p.pid} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-sm text-[var(--color-text)]">{p.kind}</span>
                <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-accent)]">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full" style={{ background: "currentColor" }} />
                  pid {p.pid}
                </span>
              </div>
              <div className="mt-1 text-[11px] text-[var(--color-text-dim)]">{formatElapsed(p.elapsed_s)} elapsed</div>
              {p.worktree && (
                <div className="mt-1 truncate font-mono text-[11px] text-[var(--color-text-dim)]" title={p.worktree}>
                  {p.worktree}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
