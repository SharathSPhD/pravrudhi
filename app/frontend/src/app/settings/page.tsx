"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { agents, type AgentStatus } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export default function SettingsPage() {
  const [rows, setRows] = useState<AgentStatus[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    agents()
      .then((data) => {
        if (!cancelled) setRows(data);
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
      <PageHeader title="Settings" subtitle="Coding agents available to this engine." />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">engine does not report agents yet.</p>
        )}
        {!unsupported && rows === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!unsupported && rows !== null && rows.length === 0 && (
          <p className="text-sm text-[var(--color-text-dim)]">No coding agents configured.</p>
        )}
        {!unsupported && rows !== null && rows.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--color-surface)] text-xs uppercase tracking-wide text-[var(--color-text-dim)]">
                <tr>
                  <th className="px-4 py-3 font-medium">Agent</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.name} className="border-t border-[var(--color-border)]">
                    <td className="px-4 py-3 font-medium text-[var(--color-text)]">{a.name}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1.5 ${
                          a.available ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"
                        }`}
                      >
                        {a.available ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                        {a.available ? "ready" : "unavailable"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-dim)]">{a.reason}</td>
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
