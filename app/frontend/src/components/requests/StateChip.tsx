// The engine defines its own state vocabulary (open, in progress, done, blocked, ...); this chip only groups
// whatever string it sends into done / stuck / active so the page never hardcodes a state enum that could drift
// from the engine's.
function toneFor(state: string): "done" | "stuck" | "active" {
  const s = state.toLowerCase();
  if (/(done|resolved|closed|complete|shipped|merged)/.test(s)) return "done";
  if (/(block|stall|fail|reject|declin|stuck|abandon)/.test(s)) return "stuck";
  return "active";
}

const TONE_CLASS: Record<"done" | "stuck" | "active", string> = {
  done: "text-[var(--color-accent)]",
  stuck: "text-[var(--color-danger)]",
  active: "text-[var(--color-text-dim)]",
};

export function StateChip({ state }: { state: string }) {
  const tone = toneFor(state);
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${TONE_CLASS[tone]}`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
      {state}
    </span>
  );
}
