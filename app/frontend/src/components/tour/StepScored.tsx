import type { Candidate } from "@/lib/api";
import type { TourData } from "@/lib/tour";
import { meanDelta } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";
import { fixed, percent } from "@/lib/num";

const BADGE_COLOR: Record<string, string> = {
  grey: "#6b7280",
  amber: "#f2b84b",
  green: "#6ee7b7",
  red: "#f2707a",
};

const WIDTH = 680;
const HEIGHT = 300;
const PAD_LEFT = 48;
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 32;

interface Point {
  candidate: Candidate;
  delta: number;
}

export function StepScored({ data }: { data: TourData }) {
  const scored: Point[] = data.candidates
    .filter((c) => c.n_obs > 0 && c.xs.length > 0)
    .map((c) => ({ candidate: c, delta: meanDelta(c.xs) ?? 0 }));

  const unscored = data.candidates.length - scored.length;

  if (scored.length === 0) {
    return <Empty>No candidate in this recording has a paired observation to plot.</Empty>;
  }

  const seqs = scored.map((p) => p.candidate.proposed_seq);
  const deltas = scored.map((p) => p.delta * 100);
  const xMin = Math.min(...seqs);
  const xMax = Math.max(...seqs);
  const yMin = Math.min(0, ...deltas);
  const yMax = Math.max(0, ...deltas);

  const sx = (seq: number) => PAD_LEFT + ((seq - xMin) / (xMax - xMin || 1)) * (WIDTH - PAD_LEFT - PAD_RIGHT);
  const sy = (v: number) => HEIGHT - PAD_BOTTOM - ((v - yMin) / (yMax - yMin || 1)) * (HEIGHT - PAD_TOP - PAD_BOTTOM);

  const zeroY = sy(0);

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--color-text-dim)]">
        Each point is a candidate this loop actually trained: its position on the y-axis is its mean measured gain
        or loss against whichever candidate was the incumbent at the time it was scored.
        {unscored > 0 && ` ${unscored} candidate(s) in this recording never reached a paired comparison and are not plotted.`}
      </p>
      <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
        <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full min-w-[480px]" role="img" aria-label="Candidates scored against the incumbent">
          <line x1={PAD_LEFT} y1={zeroY} x2={WIDTH - PAD_RIGHT} y2={zeroY} stroke="var(--color-border)" strokeDasharray="4 3" />
          <text x={PAD_LEFT} y={zeroY - 4} fontSize="10" fill="var(--color-text-dim)">
            incumbent (0%)
          </text>
          <line x1={PAD_LEFT} y1={PAD_TOP} x2={PAD_LEFT} y2={HEIGHT - PAD_BOTTOM} stroke="var(--color-border)" />
          <line x1={PAD_LEFT} y1={HEIGHT - PAD_BOTTOM} x2={WIDTH - PAD_RIGHT} y2={HEIGHT - PAD_BOTTOM} stroke="var(--color-border)" />
          <text x={PAD_LEFT} y={HEIGHT - 8} fontSize="10" fill="var(--color-text-dim)">
            proposed #{xMin}
          </text>
          <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 8} fontSize="10" fill="var(--color-text-dim)" textAnchor="end">
            proposed #{xMax}
          </text>
          <text x={4} y={sy(yMax)} fontSize="10" fill="var(--color-text-dim)">
            {fixed(yMax, 1)}%
          </text>
          <text x={4} y={sy(yMin)} fontSize="10" fill="var(--color-text-dim)">
            {fixed(yMin, 1)}%
          </text>
          {scored.map((p) => {
            const isIncumbent = p.candidate.id === data.incumbentId;
            return (
              <circle
                key={p.candidate.id}
                cx={sx(p.candidate.proposed_seq)}
                cy={sy(p.delta * 100)}
                r={isIncumbent ? 6 : 3.5}
                fill={BADGE_COLOR[p.candidate.badge] ?? "#6b7280"}
                stroke={isIncumbent ? "var(--color-text)" : "none"}
                strokeWidth={isIncumbent ? 1.5 : 0}
                opacity={isIncumbent ? 1 : 0.75}
              >
                <title>
                  {p.candidate.id} · {p.candidate.badge}
                  {isIncumbent ? " · current incumbent" : ""}
                  {"\n"}mean gain {percent(p.delta, 1)} over {p.candidate.n_obs} observation(s)
                  {"\n"}cost {fixed(p.candidate.cost_gpu_h, 2)} GPU-h · {p.candidate.edit_family ?? "unknown family"}
                </title>
              </circle>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-[var(--color-text-dim)]">
        {Object.entries(BADGE_COLOR).map(([badge, color]) => (
          <span key={badge} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
            {badge}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-full border border-[var(--color-text)]" aria-hidden />
          current incumbent
        </span>
      </div>
    </div>
  );
}
