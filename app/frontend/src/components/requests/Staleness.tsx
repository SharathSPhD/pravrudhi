import { fixed } from "@/lib/num";

// The whole point of this page is that an old open ask should not be easy to miss. Waiting longer earns a
// louder — brighter, bolder — treatment; a fresh ask stays quiet.
function classFor(days: number | null): string {
  if (days === null) return "text-[var(--color-text-dim)]";
  if (days >= 14) return "font-semibold text-[var(--color-danger)]";
  if (days >= 3) return "font-medium text-[var(--color-text)]";
  return "text-[var(--color-text-dim)]";
}

export function Staleness({ days }: { days: number | null }) {
  return <span className={`text-xs ${classFor(days)}`}>{fixed(days, 0)}d waiting</span>;
}
