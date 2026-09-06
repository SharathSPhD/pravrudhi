"use client";

import { useState } from "react";
import type { BenchmarkGroup, SeriesPoint } from "./groupExternal";

const W = 640;
const H = 220;
const MARGIN = { top: 14, right: 16, bottom: 26, left: 44 };
const PLOT_W = W - MARGIN.left - MARGIN.right;
const PLOT_H = H - MARGIN.top - MARGIN.bottom;

const BASE_COLOR = "var(--color-text-dim)";
const CANDIDATE_COLOR = "var(--color-accent)";

function formatPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export function BenchmarkChart({ group }: { group: BenchmarkGroup }) {
  const [hover, setHover] = useState<number | null>(null);
  const points = group.points;

  const seqs = points.map((p) => p.seq);
  const seqMin = Math.min(...seqs);
  const seqMax = Math.max(...seqs);

  const lo = points.map((p) => p.value - (p.err ?? 0));
  const hi = points.map((p) => p.value + (p.err ?? 0));
  const rawMin = Math.min(...lo);
  const rawMax = Math.max(...hi);
  const span = rawMax - rawMin || 0.1;
  const yMin = Math.max(0, rawMin - span * 0.15);
  const yMax = Math.min(1, rawMax + span * 0.15) || rawMax + 0.05;

  const x = (seq: number) => (seqMax === seqMin ? MARGIN.left + PLOT_W / 2 : MARGIN.left + ((seq - seqMin) / (seqMax - seqMin)) * PLOT_W);
  const y = (v: number) => (yMax === yMin ? MARGIN.top + PLOT_H / 2 : MARGIN.top + (1 - (v - yMin) / (yMax - yMin)) * PLOT_H);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((f) => yMin + f * (yMax - yMin));

  // One x-axis tick per night the series actually visited, placed at that night's first seq.
  const nightTicks: { seq: number; night: number }[] = [];
  const seenNights = new Set<number>();
  for (const p of [...points].sort((a, b) => a.seq - b.seq)) {
    if (!seenNights.has(p.night)) {
      seenNights.add(p.night);
      nightTicks.push({ seq: p.seq, night: p.night });
    }
  }

  const basePoints = points.filter((p) => p.isBase);
  const candidatePoints = points.filter((p) => !p.isBase);

  const linePath = (series: SeriesPoint[]) =>
    series.length < 2 ? "" : series.map((p, i) => `${i === 0 ? "M" : "L"} ${x(p.seq).toFixed(2)} ${y(p.value).toFixed(2)}`).join(" ");

  const hovered = hover !== null ? points[hover] : null;
  const hoverXPct = hovered ? (x(hovered.seq) / W) * 100 : 0;
  const hoverYPct = hovered ? (y(hovered.value) / H) * 100 : 0;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="flex items-baseline justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-[var(--color-text-dim)]">track {group.track}</p>
          <p className="font-mono text-sm text-[var(--color-text)]">{group.task}</p>
        </div>
        <p className="text-right text-[11px] text-[var(--color-text-dim)]">{group.metric}</p>
      </div>
      <div className="relative mt-3">
        <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
          {yTicks.map((t) => (
            <g key={t}>
              <line
                x1={MARGIN.left}
                x2={W - MARGIN.right}
                y1={y(t)}
                y2={y(t)}
                stroke="var(--color-border)"
                strokeWidth={1}
              />
              <text x={MARGIN.left - 6} y={y(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-text-dim)">
                {formatPct(t)}
              </text>
            </g>
          ))}
          {nightTicks.map((t) => (
            <text
              key={t.seq}
              x={x(t.seq)}
              y={H - MARGIN.bottom + 14}
              textAnchor="middle"
              fontSize={9}
              fill="var(--color-text-dim)"
            >
              N{t.night}
            </text>
          ))}
          {linePath(basePoints) && <path d={linePath(basePoints)} fill="none" stroke={BASE_COLOR} strokeWidth={1.5} />}
          {linePath(candidatePoints) && (
            <path d={linePath(candidatePoints)} fill="none" stroke={CANDIDATE_COLOR} strokeWidth={1.5} />
          )}
          {points.map((p, i) => {
            const color = p.isBase ? BASE_COLOR : CANDIDATE_COLOR;
            const cx = x(p.seq);
            const cy = y(p.value);
            return (
              <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover((h) => (h === i ? null : h))}>
                {p.err !== undefined && (
                  <g stroke={color} strokeWidth={1} opacity={0.6}>
                    <line x1={cx} x2={cx} y1={y(p.value - p.err)} y2={y(p.value + p.err)} />
                    <line x1={cx - 3} x2={cx + 3} y1={y(p.value - p.err)} y2={y(p.value - p.err)} />
                    <line x1={cx - 3} x2={cx + 3} y1={y(p.value + p.err)} y2={y(p.value + p.err)} />
                  </g>
                )}
                <circle cx={cx} cy={cy} r={hover === i ? 5 : 3.5} fill={color} />
                <circle cx={cx} cy={cy} r={9} fill="transparent" />
              </g>
            );
          })}
        </svg>
        {hovered && (
          <div
            className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1.5 text-[11px] leading-4 text-[var(--color-text)] shadow-lg"
            style={{ left: `${hoverXPct}%`, top: `${hoverYPct}%`, marginTop: -8 }}
          >
            <p className="font-mono">{hovered.model}</p>
            <p className="text-[var(--color-text-dim)]">
              {hovered.condition} · seq {hovered.seq} · n {hovered.n ?? "—"}
            </p>
            <p className="tabular-nums">{formatPct(hovered.value)}</p>
          </div>
        )}
      </div>
      <div className="mt-2 flex items-center gap-4 text-[11px] text-[var(--color-text-dim)]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: BASE_COLOR }} />
          base
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: CANDIDATE_COLOR }} />
          candidate
        </span>
      </div>
    </div>
  );
}
