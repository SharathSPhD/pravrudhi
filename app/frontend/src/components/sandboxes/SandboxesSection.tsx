"use client";

import { useEffect, useState } from "react";
import { IS_DEMO } from "@/lib/api";
import { fixed, percent, secs } from "@/lib/num";
import { sandboxes, type LiveSandbox, type SandboxViolation } from "@/lib/sandboxes";

function formatBytes(n: number | null | undefined): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${fixed(n / 1024, 1)} KB`;
  return `${fixed(n / (1024 * 1024), 1)} MB`;
}

// A budget bar's width is a layout value, not rendered text; it is still clamped defensively so a missing or
// out-of-range fraction draws an empty bar instead of an invalid style.
function budgetWidthPct(fraction: number | null): number {
  if (typeof fraction !== "number" || !Number.isFinite(fraction)) return 0;
  return Math.min(100, Math.max(0, fraction * 100));
}

function SandboxCard({ sandbox }: { sandbox: LiveSandbox }) {
  const obs = sandbox.observation;
  const violated = obs.violations.length > 0;
  const touchedCount = obs.created.length + obs.modified.length + obs.deleted.length;
  const widthPct = budgetWidthPct(sandbox.budget_fraction);
  const overBudget = sandbox.budget_fraction !== null && sandbox.budget_fraction >= 1;

  return (
    <div
      className={`rounded-lg border p-3 ${
        violated
          ? "border-[var(--color-danger)] bg-[var(--color-danger)]/5"
          : "border-[var(--color-border)] bg-[var(--color-surface)]"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="truncate font-mono text-sm text-[var(--color-text)]" title={sandbox.task_id}>
          {sandbox.task_id}
        </span>
        <span className="shrink-0 text-[11px] text-[var(--color-text-dim)]">pid {sandbox.pid}</span>
      </div>
      <div className="mt-1 truncate font-mono text-[11px] text-[var(--color-text-dim)]" title={sandbox.worktree}>
        {sandbox.worktree}
      </div>
      <div className="mt-1 truncate text-[11px] text-[var(--color-text-dim)]">
        policy:{" "}
        {sandbox.allowed_paths.length > 0 ? (
          <span className="font-mono">{sandbox.allowed_paths.join(", ")}</span>
        ) : (
          "none declared"
        )}
      </div>

      <div className="mt-2">
        <div className="flex items-center justify-between text-[11px] text-[var(--color-text-dim)]">
          <span>{secs(sandbox.elapsed_s, 0)} elapsed</span>
          <span>{percent(sandbox.budget_fraction)} of budget</span>
        </div>
        <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--color-border)]">
          <div
            className={`h-full ${overBudget ? "bg-[var(--color-danger)]" : "bg-[var(--color-accent)]"}`}
            style={{ width: `${widthPct}%` }}
          />
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[var(--color-text-dim)]">
        <span>{obs.created.length} created</span>
        <span>{obs.modified.length} modified</span>
        <span>{obs.deleted.length} deleted</span>
        <span>{formatBytes(obs.bytes_written)} written</span>
        <span>
          {obs.allowed_count}/{touchedCount} within policy
        </span>
      </div>

      {violated && (
        <ul className="mt-2 list-inside list-disc text-[11px] text-[var(--color-danger)]">
          {obs.violations.map((v, i) => (
            <li key={i} className="truncate" title={v.path}>
              wrote outside policy: <span className="font-mono">{v.path}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ViolationRow({ violation }: { violation: SandboxViolation }) {
  return (
    <li>
      <span className="font-mono">{violation.task_id}</span> wrote <span className="font-mono">{violation.path}</span>{" "}
      outside{" "}
      {violation.allowed_paths.length > 0 ? (
        <span className="font-mono">{violation.allowed_paths.join(", ")}</span>
      ) : (
        "its declared policy"
      )}
    </li>
  );
}

// Recorded state can only ever show what a run once did; a live sandbox view describing "right now" has no
// honest recorded form, so this section is not part of the demo snapshot at all -- the same reasoning LivePanel
// applies to the process table it shares a mechanism with.
export function SandboxesSection() {
  const [live, setLive] = useState<LiveSandbox[]>([]);
  const [recentViolations, setRecentViolations] = useState<SandboxViolation[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (IS_DEMO) return;
    let cancelled = false;
    const poll = () => {
      sandboxes()
        .then((snapshot) => {
          if (!cancelled) {
            setLive(snapshot.live);
            setRecentViolations(snapshot.recent_violations);
            setFailed(false);
          }
        })
        .catch(() => {
          if (!cancelled) setFailed(true);
        });
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <section>
      <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Sandboxes</h2>
      {IS_DEMO && (
        <p className="text-sm text-[var(--color-text-dim)]">Live sandbox state is not part of a recording.</p>
      )}
      {!IS_DEMO && failed && (
        <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s sandbox monitor.</p>
      )}
      {!IS_DEMO && !failed && live.length === 0 && (
        <p className="text-sm text-[var(--color-text-dim)]">No agent worktree is running right now.</p>
      )}
      {!IS_DEMO && !failed && live.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {live.map((s) => (
            <SandboxCard key={s.pid} sandbox={s} />
          ))}
        </div>
      )}
      {!IS_DEMO && !failed && recentViolations.length > 0 && (
        <div className="mt-3">
          <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[var(--color-text-dim)]">
            Recent violations
          </h3>
          <ul className="space-y-1 text-[11px] text-[var(--color-danger)]">
            {recentViolations.map((v, i) => (
              <ViolationRow key={i} violation={v} />
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
