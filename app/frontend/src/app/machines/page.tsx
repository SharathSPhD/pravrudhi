"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { hosts, type HostRow } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

export default function MachinesPage() {
  const [rows, setRows] = useState<HostRow[] | null>(null);
  const [unsupported, setUnsupported] = useState(false);

  useEffect(() => {
    let cancelled = false;
    hosts()
      .then((data) => {
        if (!cancelled) setRows(data.hosts);
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
      <PageHeader title="Machines" subtitle="This machine, and any others enrolled to run work." />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">engine does not report machines yet.</p>
        )}
        {!unsupported && rows === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!unsupported && rows !== null && (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            {rows.map(({ host, capabilities: cap }) => (
              <div key={host.name} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-[var(--color-text)]">{host.name}</span>
                  {cap.reachable ? (
                    <CheckCircle2 size={16} className="text-[var(--color-accent)]" />
                  ) : (
                    <XCircle size={16} className="text-[var(--color-danger)]" />
                  )}
                </div>
                {!cap.reachable ? (
                  <p className="mt-2 text-xs text-[var(--color-danger)]">{cap.error || "unreachable"}</p>
                ) : (
                  <dl className="mt-3 space-y-1.5 text-xs text-[var(--color-text-dim)]">
                    <div className="flex justify-between">
                      <dt>OS / arch</dt>
                      <dd className="text-[var(--color-text)]">
                        {cap.os || "?"} / {cap.arch || "?"}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Accelerator</dt>
                      <dd className="text-[var(--color-text)]">
                        {cap.accelerator}
                        {cap.gpu_name ? ` — ${cap.gpu_name}` : ""}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Usable memory</dt>
                      <dd className="text-[var(--color-text)]">{cap.usable_model_gb} GB</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt>Can train</dt>
                      <dd className={cap.can_train ? "text-[var(--color-accent)]" : "text-[var(--color-text)]"}>
                        {cap.can_train ? "yes" : "no"}
                      </dd>
                    </div>
                  </dl>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
