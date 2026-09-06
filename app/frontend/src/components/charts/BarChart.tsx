"use client";

import { useState } from "react";

export interface BarSeries {
  label: string;
  color: string;
  values: number[];
}

const W = 640;
const H = 180;
const MARGIN = { top: 10, right: 12, bottom: 22, left: 34 };
const PLOT_W = W - MARGIN.left - MARGIN.right;
const PLOT_H = H - MARGIN.top - MARGIN.bottom;

export function BarChart({
  categories,
  series,
  valueFormatter = (v: number) => v.toString(),
}: {
  categories: string[];
  series: BarSeries[];
  valueFormatter?: (v: number) => string;
}) {
  const [hover, setHover] = useState<{ cat: number; s: number } | null>(null);

  const max = Math.max(1e-9, ...series.flatMap((s) => s.values));
  const yMax = max * 1.15;
  const y = (v: number) => MARGIN.top + PLOT_H - (v / yMax) * PLOT_H;

  const groupW = PLOT_W / Math.max(1, categories.length);
  const barW = Math.min(22, (groupW * 0.7) / Math.max(1, series.length));
  const groupGap = groupW * 0.15;

  const yTicks = [0, 0.5, 1].map((f) => f * yMax);

  const hoveredValue = hover ? series[hover.s].values[hover.cat] : null;
  const hoveredX = hover
    ? MARGIN.left + hover.cat * groupW + groupGap + hover.s * barW + barW / 2
    : 0;
  const hoveredY = hover ? y(hoveredValue ?? 0) : 0;

  return (
    <div className="relative">
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={MARGIN.left} x2={W - MARGIN.right} y1={y(t)} y2={y(t)} stroke="var(--color-border)" strokeWidth={1} />
            <text x={MARGIN.left - 6} y={y(t) + 3} textAnchor="end" fontSize={9} fill="var(--color-text-dim)">
              {valueFormatter(t)}
            </text>
          </g>
        ))}
        {categories.map((cat, ci) => (
          <text
            key={cat}
            x={MARGIN.left + ci * groupW + groupW / 2}
            y={H - MARGIN.bottom + 14}
            textAnchor="middle"
            fontSize={9}
            fill="var(--color-text-dim)"
          >
            {cat}
          </text>
        ))}
        {series.map((s, si) =>
          s.values.map((v, ci) => {
            const bx = MARGIN.left + ci * groupW + groupGap + si * barW;
            const by = y(v);
            const isHover = hover?.cat === ci && hover?.s === si;
            return (
              <rect
                key={`${si}-${ci}`}
                x={bx}
                y={by}
                width={barW - 2}
                height={Math.max(0, MARGIN.top + PLOT_H - by)}
                fill={s.color}
                opacity={isHover ? 1 : 0.85}
                onMouseEnter={() => setHover({ cat: ci, s: si })}
                onMouseLeave={() => setHover((h) => (h?.cat === ci && h?.s === si ? null : h))}
              />
            );
          }),
        )}
      </svg>
      {hover && hoveredValue !== null && (
        <div
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1.5 text-[11px] leading-4 text-[var(--color-text)] shadow-lg"
          style={{ left: `${(hoveredX / W) * 100}%`, top: `${(hoveredY / H) * 100}%`, marginTop: -6 }}
        >
          <p>
            {series[hover.s].label} · {categories[hover.cat]}
          </p>
          <p className="tabular-nums">{valueFormatter(hoveredValue)}</p>
        </div>
      )}
      <div className="mt-1 flex flex-wrap items-center gap-4 text-[11px] text-[var(--color-text-dim)]">
        {series.map((s) => (
          <span key={s.label} className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: s.color }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}
