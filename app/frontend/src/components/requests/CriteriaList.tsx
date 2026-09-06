import type { RequestCriterion } from "@/lib/requests";

const SOURCE_LABEL: Record<RequestCriterion["source"], string> = {
  operator: "OPERATOR",
  engine: "ENGINE",
};

const SOURCE_CLASS: Record<RequestCriterion["source"], string> = {
  operator: "text-[var(--color-text)]",
  engine: "text-[var(--color-text-dim)]",
};

export function CriteriaList({ criteria }: { criteria: RequestCriterion[] }) {
  if (criteria.length === 0) {
    return <p className="text-xs text-[var(--color-text-dim)]">No criteria recorded for this ask yet.</p>;
  }

  return (
    <ul className="space-y-2">
      {criteria.map((c, i) => (
        <li key={i} className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface-raised)] p-2.5">
          <div className="flex flex-wrap items-start gap-2">
            <span
              className={`mt-0.5 inline-flex items-center gap-1.5 text-xs font-medium ${
                c.met ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"
              }`}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
              {c.met ? "met" : "open"}
            </span>
            <span className={`rounded border border-[var(--color-border)] px-1.5 py-0.5 text-[10px] font-medium tracking-wide ${SOURCE_CLASS[c.source]}`}>
              {SOURCE_LABEL[c.source]}
            </span>
            <span className="flex-1 text-sm text-[var(--color-text)]">{c.text}</span>
          </div>
          {c.evidence.length > 0 && (
            <ul className="mt-2 space-y-1 pl-5">
              {c.evidence.map((e, j) => (
                <li key={j} className="text-[11px] text-[var(--color-text-dim)]">
                  <span className="font-mono">{e.kind}</span>
                  {e.ref && <span className="font-mono"> · {e.ref}</span>}
                  {e.note && <span> — {e.note}</span>}
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}
