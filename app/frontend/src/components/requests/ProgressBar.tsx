import { fixed } from "@/lib/num";

export function ProgressBar({ met, total }: { met: number; total: number }) {
  const pct = total > 0 ? Math.round((met / total) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-[var(--color-surface-raised)]">
        <div
          className="h-full rounded-full bg-[var(--color-accent)]"
          style={{ width: `${total > 0 ? pct : 0}%` }}
        />
      </div>
      <span className="whitespace-nowrap font-mono text-[11px] text-[var(--color-text-dim)]">
        {fixed(met, 0)}/{fixed(total, 0)}
      </span>
    </div>
  );
}
