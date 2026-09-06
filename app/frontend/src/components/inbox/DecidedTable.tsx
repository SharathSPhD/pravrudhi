import type { InboxItem } from "@/lib/inbox";

export function DecidedTable({ items }: { items: InboxItem[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
            <th className="px-4 py-2 font-medium">Candidate</th>
            <th className="px-4 py-2 font-medium">Badge</th>
            <th className="px-4 py-2 font-medium">Night</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.pack} className="border-b border-[var(--color-border)] last:border-0">
              <td className="px-4 py-2 font-mono text-[13px] text-[var(--color-text)]">{item.candidate}</td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{item.badge ?? "—"}</td>
              <td className="px-4 py-2 text-[var(--color-text-dim)]">{item.night}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
