"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";
import type { RunEvent } from "@/lib/api";
import { demo } from "@/lib/demo";

/**
 * A real night, replayed at a watchable speed.
 *
 * This is the demonstration that matters: a visitor sees candidates proposed, each one measured against the
 * current best on the same held-out problems, most of them rejected, and occasionally one kept. Nothing here is
 * simulated; the events are the engine's own record of a run that happened.
 */
export function RecordedRun() {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [shown, setShown] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [night, setNight] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    demo().then((d) => {
      setEvents(d.featured_run.events);
      setNight(d.featured_run.night);
      setPlaying(true);
    });
  }, []);

  useEffect(() => {
    if (!playing || events.length === 0) return;
    timer.current = setInterval(() => {
      setShown((n) => {
        if (n >= events.length) {
          setPlaying(false);
          return n;
        }
        return n + 1;
      });
    }, 420);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing, events.length]);

  const restart = useCallback(() => {
    setShown(0);
    setPlaying(true);
  }, []);

  const visible = events.slice(0, shown);
  const paired = visible.filter((e) => e.type === "paired");
  const best = paired.reduce<number | null>((b, e) => (e.delta != null && (b === null || e.delta > b) ? e.delta : b), null);
  const kept = visible.filter((e) => e.type === "promoted").length;
  const rejected = visible.filter((e) => e.type === "pruned").length;
  const done = shown >= events.length && events.length > 0;

  return (
    <section className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-medium">A real run, replayed</h2>
          <p className="text-xs text-[var(--color-muted)]">
            Night {night} on this project&apos;s own machine. Every line is from the engine&apos;s record.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPlaying((p) => !p)}
            disabled={done}
            className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-white/5 disabled:opacity-40"
          >
            {playing ? <Pause size={13} /> : <Play size={13} />}
            {playing ? "Pause" : "Play"}
          </button>
          <button
            onClick={restart}
            className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-white/5"
          >
            <RotateCcw size={13} />
            Replay
          </button>
        </div>
      </header>

      <div className="grid grid-cols-3 divide-x divide-[var(--color-border)] border-b border-[var(--color-border)] text-center">
        <Stat label="tried" value={String(paired.length)} />
        <Stat label="best gain" value={best === null ? "—" : `${best > 0 ? "+" : ""}${(best * 100).toFixed(1)}%`} good={(best ?? 0) > 0} />
        <Stat label="kept / rejected" value={`${kept} / ${rejected}`} />
      </div>

      <ol className="max-h-80 overflow-y-auto p-3 font-mono text-xs">
        {visible.length === 0 && <li className="p-3 text-[var(--color-muted)]">Loading the recording…</li>}
        {visible.map((e, i) => (
          <li key={i} className="flex items-baseline gap-2 border-b border-white/5 px-2 py-1.5 last:border-0">
            <EventRow event={e} />
          </li>
        ))}
        {done && (
          <li className="px-2 py-3 text-center font-sans text-xs text-[var(--color-muted)]">
            End of the recording. {kept > 0 ? "One candidate was kept and became the new best." : "Nothing beat the current best."}
          </li>
        )}
      </ol>
    </section>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="px-3 py-3">
      <div className={`text-xl font-semibold tabular-nums ${good ? "text-emerald-400" : ""}`}>{value}</div>
      <div className="text-[11px] uppercase tracking-wide text-[var(--color-muted)]">{label}</div>
    </div>
  );
}

function EventRow({ event }: { event: RunEvent }) {
  if (event.type === "proposed_one") {
    return (
      <>
        <span className="text-[var(--color-muted)]">proposed</span>
        <span>{event.candidate}</span>
      </>
    );
  }
  if (event.type === "paired") {
    const d = event.delta ?? 0;
    return (
      <>
        <span className="text-[var(--color-muted)]">measured</span>
        <span>{event.candidate}</span>
        <span className="text-[var(--color-muted)]">
          {((event.incumbent ?? 0) * 100).toFixed(1)}% → {((event.candidate_score ?? 0) * 100).toFixed(1)}%
        </span>
        <span className={d > 0 ? "text-emerald-400" : d < 0 ? "text-red-400" : "text-[var(--color-muted)]"}>
          {d > 0 ? "+" : ""}
          {(d * 100).toFixed(1)}%
        </span>
      </>
    );
  }
  if (event.type === "promoted") {
    return <span className="text-emerald-400">kept {event.candidate} — this is the new best</span>;
  }
  if (event.type === "pruned") {
    return <span className="text-[var(--color-muted)]">rejected {event.candidate}</span>;
  }
  if (event.type === "closed") return <span className="text-[var(--color-muted)]">run finished</span>;
  return <span className="text-[var(--color-muted)]">{event.text ?? event.type}</span>;
}
