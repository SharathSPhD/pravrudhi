import type { RoutingRow } from "@/lib/swarm";
import { fixed, percent, secs } from "@/lib/num";

// What the routing table shows for a tier is either a measured choice — backed by trials this engine actually
// ran — or the reason it has none yet. Never a guess dressed up as one of those.
function describeWhy(row: RoutingRow): string {
  if (row.error) return row.error;
  if (row.reason) return row.reason;
  const record = row.records.find((r) => r.route_id === row.route) ?? row.records[0];
  if (!record) return "measured";
  return `${percent(record.rate)} success over ${record.trials} trials · mean ${secs(record.mean_wall_s)} · cost ×${fixed(record.relative_cost, 2)}`;
}

export function RoutingTable({ rows }: { rows: RoutingRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No routing decisions recorded yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            <th className="px-4 py-2 font-medium">Tier</th>
            <th className="px-4 py-2 font-medium">Route</th>
            <th className="px-4 py-2 font-medium">Agent</th>
            <th className="px-4 py-2 font-medium">Model</th>
            <th className="px-4 py-2 font-medium">Why</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.tier} className="border-b border-[var(--color-border)] align-top last:border-0">
              <td className="px-4 py-2 font-mono text-[13px] text-[var(--color-text)]">{row.tier}</td>
              <td className="px-4 py-2 font-mono text-[12px] text-[var(--color-text-dim)]">{row.route ?? "—"}</td>
              <td className="px-4 py-2 text-[var(--color-text)]">{row.agent ?? "—"}</td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{row.model ?? "—"}</td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{describeWhy(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
