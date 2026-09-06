"use client";

import { useMemo, useState } from "react";
import type { CandidatesSnapshot, ObservationPoint } from "@/lib/candidates";
import { signedDelta } from "@/lib/candidates";

const W = 880;
const H = 260;
const MARGIN = { top: 14, right: 16, bottom: 26, left: 48 };
const PLOT_W = W - MARGIN.left - MARGIN.right;
const PLOT_H = H - MARGIN.top - MARGIN.bottom;

// Mirrors components/BadgeDot.tsx's palette so a point's colour always means the same badge everywhere on the
// page. BadgeDot does not export its map, so it is repeated here rather than editing a file outside this
// feature's scope.
const BADGE_COLOR: Record<string, string> = {
  grey: "#6b7280",
  amber: "#f2b84b",
  green: "#6ee7b7",
  red: "#f2707a",
};
const BADGE_ORDER = ["grey", "amber", "green", "red"] as const;

export function CandidatesChart({
  snapshot,
  onSelect,
}: {
  snapshot: CandidatesSnapshot;
  onSelect: (id: string) => void;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const points = snapshot.obsPoints;

  const { x, y, nightTicks, yTicks } = useMemo(() => {
    if (points.length === 0) {
      return {
        x: (_n: number) => MARGIN.left,
        y: (_v: number) => MARGIN.top,
        nightTicks: [] as number[],
        yTicks: [] as number[],
      };
    }
    const nights = points.map((p) => p.night);
    const nMin = Math.min(...nights);
    const nMax = Math.max(...nights);
    const deltas = points.map((p) => p.delta);
    // 0 is always in range: it is the incumbent's own line (see lib/candidates.ts), not just another data point.
    const dMin = Math.min(0, ...deltas);
    const dMax = Math.max(0, ...deltas);
    const span = dMax - dMin || 0.1;
    const yMin = dMin - span * 0.15;
    const yMax = dMax + span * 0.15;
    const xFn = (n: number) =>
      nMax === nMin ? MARGIN.left + PLOT_W / 2 : MARGIN.left + ((n - nMin) / (nMax - nMin)) * PLOT_W;
    const yFn = (v: number) => (yMax === yMin ? MARGIN.top + PLOT_H / 2 : MARGIN.top + (1 - (v - yMin) / (yMax - yMin)) * PLOT_H);
    const nTicks: number[] = [];
    for (let n = nMin; n <= nMax; n++) nTicks.push(n);
    return { x: xFn, y: yFn, nightTicks: nTicks, yTicks: [yMin, (yMin + yMax) / 2, yMax] };
  }, [points]);

  if (points.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
        <p className="text-sm text-[var(--color-text-dim)]">No candidate has been observed yet — nothing to plot.</p>
      </div>
    );
  }

  const hovered: ObservationPoint | null = hover !== null ? points[hover] : null;
  const hoverXPct = hovered ? (x(hovered.night) / W) * 100 : 0;
  const hoverYPct = hovered ? (y(hovered.delta) / H) * 100 : 0;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-baseline justify-between gap-2">
        <p className="text-xs uppercase tracking-wide text-[var(--color-text-dim)]">every observed candidate</p>
        <p className="text-right text-[11px] text-[var(--color-text-dim)]">Δ against the incumbent at time of observation</p>
      </div>
      <div className="relative mt-3">
        <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          {yTicks.map((t) => (
            <g key={t}>
              <line x1={MARGIN.left} x2={W - MARGIN.right} y1={y(t)} y2={y(t)} stroke="var(--color-border)" strokeWidth={1} />
              <text x={MARGIN.left - 6} y={y(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-text-dim)">
                {signedDelta(t, 2)}
              </text>
            </g>
          ))}
          {/* xs is already a delta against whoever was incumbent at the time (see lib/candidates.ts), so 0 is
              the incumbent's own line — not an invented reference. */}
          <line
            x1={MARGIN.left}
            x2={W - MARGIN.right}
            y1={y(0)}
            y2={y(0)}
            stroke="var(--color-text-dim)"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
          {nightTicks.map((n) => (
            <text key={n} x={x(n)} y={H - MARGIN.bottom + 14} textAnchor="middle" fontSize={9} fill="var(--color-text-dim)">
              N{n}
            </text>
          ))}
          {points.map((p, i) => (
            <g
              key={`${p.candidateId}-${p.seq}`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover((h) => (h === i ? null : h))}
              onClick={() => onSelect(p.candidateId)}
              style={{ cursor: "pointer" }}
            >
              <circle cx={x(p.night)} cy={y(p.delta)} r={hover === i ? 5 : 3.5} fill={BADGE_COLOR[p.badge] ?? BADGE_COLOR.grey} />
              <circle cx={x(p.night)} cy={y(p.delta)} r={9} fill="transparent" />
            </g>
          ))}
        </svg>
        {hovered && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1.5 text-[11px] leading-4 text-[var(--color-text)] shadow-lg"
            style={{ left: `${hoverXPct}%`, top: `${hoverYPct}%`, marginTop: -8 }}
          >
            <p className="font-mono">{hovered.candidateId}</p>
            <p className="text-[var(--color-text-dim)]">
              night {hovered.night} · {hovered.badge}
            </p>
            <p className="tabular-nums">{signedDelta(hovered.delta)}</p>
          </div>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-[var(--color-text-dim)]">
        {BADGE_ORDER.map((b) => (
          <span key={b} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: BADGE_COLOR[b] }} />
            {b}
          </span>
        ))}
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-px w-3" style={{ borderTop: "1px dashed var(--color-text-dim)" }} />
          incumbent (Δ=0)
        </span>
      </div>
    </div>
  );
}
