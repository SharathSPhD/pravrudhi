import type { Recipe } from "@/lib/catalogue";

function groupByCapability(recipes: Recipe[]): [string, Recipe[]][] {
  const groups = new Map<string, Recipe[]>();
  for (const r of recipes) {
    const list = groups.get(r.capability) ?? [];
    list.push(r);
    groups.set(r.capability, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function RecipesTable({ recipes }: { recipes: Recipe[] }) {
  if (recipes.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No recipes match this filter.</p>;
  }

  return (
    <div className="space-y-6">
      {groupByCapability(recipes).map(([capability, rows]) => (
        <div
          key={capability}
          className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
        >
          <p className="border-b border-[var(--color-border)] px-4 py-2 text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            {capability}
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
                <th className="px-4 py-2 font-medium">Recipe</th>
                <th className="px-4 py-2 font-medium">Skill</th>
                <th className="px-4 py-2 font-medium">Summary</th>
                <th className="px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-[var(--color-border)] align-top last:border-0">
                  <td className="px-4 py-2">
                    <div className="text-[var(--color-text)]">{r.title}</div>
                    <div className="font-mono text-[11px] text-[var(--color-text-dim)]">{r.id}</div>
                  </td>
                  <td className="px-4 py-2 font-mono text-[12px] text-[var(--color-text-dim)]">{r.skill}</td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{r.summary || "—"}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs ${
                        r.available ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"
                      }`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
                      {r.available ? "skill installed" : "skill not installed"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
