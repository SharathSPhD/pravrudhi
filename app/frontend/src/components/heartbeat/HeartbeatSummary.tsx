import type { HeartbeatBeat } from "@/lib/heartbeat";

function latestBeat(beats: HeartbeatBeat[]): HeartbeatBeat {
  return beats.reduce((latest, beat) => (beat.at > latest.at ? beat : latest), beats[0]);
}

export function HeartbeatSummary({ beats }: { beats: HeartbeatBeat[] }) {
  const latest = latestBeat(beats);
  const dispatched = beats.filter((b) => b.chose !== null).length;

  return (
    <section className="flex flex-wrap gap-6 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">Last beat</div>
        <div className="mt-1 font-mono text-sm text-[var(--color-text)]">{latest.at}</div>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">Beats recorded</div>
        <div className="mt-1 font-mono text-sm text-[var(--color-text)]">{beats.length}</div>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">Dispatched something</div>
        <div className="mt-1 font-mono text-sm text-[var(--color-text)]">{dispatched}</div>
      </div>
    </section>
  );
}
