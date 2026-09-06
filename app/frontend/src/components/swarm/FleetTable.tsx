import type { SwarmAgent } from "@/lib/swarm";

export function FleetTable({ agents }: { agents: SwarmAgent[] }) {
  if (agents.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No agents surveyed.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            <th className="px-4 py-2 font-medium">Agent</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2 font-medium">Reason</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => (
            <tr key={a.name} className="border-b border-[var(--color-border)] last:border-0">
              <td className="px-4 py-2 font-mono text-[13px] text-[var(--color-text)]">{a.name}</td>
              <td className="px-4 py-2">
                <span
                  className={`inline-flex items-center gap-1.5 text-xs ${
                    a.available ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"
                  }`}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: "currentColor" }} />
                  {a.available ? "available" : "unavailable"}
                </span>
              </td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{a.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
