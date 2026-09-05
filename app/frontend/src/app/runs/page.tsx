"use client";

import { useEffect, useState } from "react";
import { nights, type NightSummary } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

type Row = NightSummary & { night: string };

export default function RunsPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    nights()
      .then((data) => {
        if (cancelled) return;
        const withKeys = data.map((n, i) => ({ ...n, night: String((n as { night?: number }).night ?? i) }));
        setRows(withKeys);
      })
      .catch(() => {
        if (!cancelled) setUnsupported(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <PageHeader title="Runs" subtitle="Every night the engine has run, in order." />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">
            engine does not report run history yet.
          </p>
        )}
        {!unsupported && rows === null && (
          <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>
        )}
        {!unsupported && rows !== null && rows.length === 0 && (
          <p className="text-sm text-[var(--color-text-dim)]">No runs yet — start one from Improve.</p>
        )}
        {!unsupported && rows !== null && rows.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--color-surface)] text-xs uppercase tracking-wide text-[var(--color-text-dim)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Night</th>
                  <th className="px-4 py-3 font-medium">GPU-hours</th>
                  <th className="px-4 py-3 font-medium">Incumbent</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.night} className="border-t border-[var(--color-border)]">
                    <td className="px-4 py-3">{r.night}</td>
                    <td className="px-4 py-3">{r.spent_gpu_h ?? "—"}</td>
                    <td className="px-4 py-3">{r.incumbent ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
