import type { SandboxPolicy } from "@/lib/catalogue";
import { secs } from "@/lib/num";

export function PoliciesTable({ policies }: { policies: SandboxPolicy[] }) {
  if (policies.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">No sandbox policies declared.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            <th className="px-4 py-2 font-medium">Policy</th>
            <th className="px-4 py-2 font-medium">May write</th>
            <th className="px-4 py-2 font-medium">Never write</th>
            <th className="px-4 py-2 font-medium">Network</th>
            <th className="px-4 py-2 font-medium">Tools</th>
            <th className="px-4 py-2 font-medium">Wall-clock cap</th>
          </tr>
        </thead>
        <tbody>
          {policies.map((p) => (
            <tr key={p.id} className="border-b border-[var(--color-border)] align-top last:border-0">
              <td className="px-4 py-2 font-mono text-[13px] text-[var(--color-text)]">{p.id}</td>
              <td className="px-4 py-2 font-mono text-[11px] text-[var(--color-text-dim)]">
                {p.allowed_paths.length > 0 ? p.allowed_paths.join(", ") : "nowhere"}
              </td>
              <td className="px-4 py-2 font-mono text-[11px] text-[var(--color-text-dim)]">
                {p.denied_paths.join(", ")}
              </td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{p.network}</td>
              <td className="px-4 py-2 font-mono text-[11px] text-[var(--color-text-dim)]">
                {p.tools.length > 0 ? p.tools.join(", ") : "none declared"}
              </td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{secs(p.max_wall_s, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
