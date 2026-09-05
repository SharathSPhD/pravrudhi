const COLORS: Record<string, string> = {
  grey: "#6b7280",
  amber: "#f2b84b",
  green: "#6ee7b7",
  red: "#f2707a",
};

export function BadgeDot({ badge, count }: { badge: string; count: number }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1 text-xs text-[var(--color-text-dim)]">
      <span
        className="h-2 w-2 rounded-full"
        style={{ background: COLORS[badge] ?? "#6b7280" }}
        aria-hidden
      />
      {badge} {count}
    </span>
  );
}
