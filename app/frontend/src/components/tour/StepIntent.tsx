import type { TourData } from "@/lib/tour";
import { Empty } from "@/components/tour/Empty";

const AVAILABILITY_LABEL: Record<string, string> = {
  available: "recipe installed",
  uninstalled: "recipe not installed",
  no_recipe: "no recipe yet",
};

export function StepIntent({ data }: { data: TourData }) {
  const { objective, plan, planError, recipeTitles } = data;

  if (!objective) {
    return <Empty>This recording has no objective captured.</Empty>;
  }

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
          <span>{objective.domain}</span>
          <span>·</span>
          <span>track {objective.track}</span>
        </div>
        <h3 className="mt-1 text-sm font-medium text-[var(--color-text)]">{objective.id}</h3>
        <p className="mt-2 text-sm text-[var(--color-text)]">{objective.intent}</p>
        {objective.notes && <p className="mt-2 text-xs text-[var(--color-muted)]">{objective.notes}</p>}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {objective.benchmarks.map((b) => (
            <span
              key={b.id}
              className="rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2 py-0.5 font-mono text-[11px] text-[var(--color-text-dim)]"
            >
              {b.metric}
            </span>
          ))}
        </div>
        {objective.recipes.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {objective.recipes.map((id) => (
              <span
                key={id}
                className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-dim)]"
                title={recipeTitles.get(id)?.summary ?? id}
              >
                {recipeTitles.get(id)?.title ?? id}
              </span>
            ))}
          </div>
        )}
      </div>

      <div>
        <h4 className="mb-2 text-sm font-medium text-[var(--color-text)]">What that compiled to</h4>
        {planError && <Empty>{planError}</Empty>}
        {!planError && plan && plan.steps.length === 0 && <Empty>The compiled plan has no steps.</Empty>}
        {!planError && plan && plan.steps.length > 0 && (
          <ol className="space-y-2">
            {plan.steps.map((step, i) => (
              <li key={step.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-mono text-[11px] text-[var(--color-muted)]">{i + 1}.</span>
                  <span className="font-mono text-[13px] text-[var(--color-text)]">{step.id}</span>
                  <span className="text-xs text-[var(--color-text-dim)]">{step.capability}</span>
                  <span
                    className={`ml-auto text-[11px] ${
                      step.availability === "available" ? "text-[var(--color-accent)]" : "text-[var(--color-warn)]"
                    }`}
                  >
                    {AVAILABILITY_LABEL[step.availability] ?? step.availability}
                  </span>
                </div>
                <p className="mt-1 text-xs text-[var(--color-text-dim)]">{step.check.criterion}</p>
                <p className="mt-1 text-[11px] text-[var(--color-muted)]">{step.reason}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
