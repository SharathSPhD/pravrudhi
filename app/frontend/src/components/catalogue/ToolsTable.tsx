import type { CatalogueTool } from "@/lib/catalogue";

function groupByCategory(tools: CatalogueTool[]): [string, CatalogueTool[]][] {
  const groups = new Map<string, CatalogueTool[]>();
  for (const t of tools) {
    const list = groups.get(t.category) ?? [];
    list.push(t);
    groups.set(t.category, list);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

export function ToolsTable({ tools }: { tools: CatalogueTool[] }) {
  if (tools.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No tools match this filter.</p>;
  }

  return (
    <div className="space-y-6">
      {groupByCategory(tools).map(([category, rows]) => (
        <div
          key={category}
          className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
        >
          <p className="border-b border-[var(--color-border)] px-4 py-2 text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            {category}
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
                <th className="px-4 py-2 font-medium">Tool</th>
                <th className="px-4 py-2 font-medium">Provides</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Reason</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id} className="border-b border-[var(--color-border)] align-top last:border-0">
                  <td className="px-4 py-2">
                    <div className="text-[var(--color-text)]">{t.title}</div>
                    <div className="font-mono text-[11px] text-[var(--color-text-dim)]">{t.id}</div>
                  </td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{t.provides || "—"}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-flex items-center gap-1.5 text-xs ${
                        t.available ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"
                      }`}
                    >
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
                      {t.available ? "available" : "unavailable"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
