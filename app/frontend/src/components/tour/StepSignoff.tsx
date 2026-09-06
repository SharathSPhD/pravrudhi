import type { TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";

const BADGE_COLOR: Record<string, string> = {
  grey: "#6b7280",
  amber: "#f2b84b",
  green: "#6ee7b7",
  red: "#f2707a",
};

const SHOWN = 12;

export function StepSignoff({ data }: { data: TourData }) {
  const items = data.inboxItems;

  if (items.length === 0) {
    return <Empty>This recording carries no inbox: nothing was waiting on a human decision.</Empty>;
  }

  const pending = items.filter((i) => !i.signed).length;

  return (
    <div className="space-y-3">
      <p className="text-sm text-[var(--color-text-dim)]">
        {pending} of {items.length} review pack(s) in this recording were still waiting on a human when the snapshot
        was taken. Nothing here is promoted on the strength of the engine&apos;s own scoring alone.
      </p>
      <div className="divide-y divide-[var(--color-border)] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
        {items.slice(0, SHOWN).map((item, i) => (
          <div key={`${item.pack}-${i}`} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <span className="font-mono text-sm text-[var(--color-text)]">{item.candidate}</span>
            <span className="text-xs text-[var(--color-text-dim)]">{item.night}</span>
            {item.badge && (
              <span className="inline-flex items-center gap-1.5 text-xs text-[var(--color-text-dim)]">
                <span className="h-2 w-2 rounded-full" style={{ background: BADGE_COLOR[item.badge] ?? "#6b7280" }} aria-hidden />
                {item.badge}
              </span>
            )}
            <span
              className={`ml-auto text-xs ${item.signed ? "text-[var(--color-text-dim)]" : "text-[var(--color-accent)]"}`}
            >
              {item.signed ? "signed" : "awaiting sign-off"}
            </span>
          </div>
        ))}
      </div>
      {items.length > SHOWN && (
        <p className="text-xs text-[var(--color-muted)]">+{items.length - SHOWN} more in this recording.</p>
      )}
    </div>
  );
}
