"use client";

import { useEffect, useState } from "react";
import { fixed } from "@/lib/num";
import { IS_DEMO } from "@/lib/api";
import { candidateEvidence, type Badge, type CandidateEvidence, type InboxItem } from "@/lib/inbox";
import { SignControls } from "./SignControls";

// Same mapping as BadgeDot.tsx, inlined here because that component's "label count" layout doesn't fit a single
// candidate's badge.
const BADGE_COLOR: Record<Badge, string> = {
  grey: "#6b7280",
  amber: "#f2b84b",
  green: "#6ee7b7",
  red: "#f2707a",
};

export function InboxCard({ item, onSigned }: { item: InboxItem; onSigned: () => void }) {
  const [evidence, setEvidence] = useState<CandidateEvidence | null | undefined>(undefined);

  useEffect(() => {
    if (IS_DEMO) return;
    let cancelled = false;
    candidateEvidence(item.candidate)
      .then((e) => {
        if (!cancelled) setEvidence(e);
      })
      .catch(() => {
        if (!cancelled) setEvidence(null);
      });
    return () => {
      cancelled = true;
    };
  }, [item.candidate]);

  const badge = item.badge ?? evidence?.badge ?? null;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm text-[var(--color-text)]">
            Promote candidate <span className="font-mono">{item.candidate}</span> to T2
          </p>
          <p className="mt-1 text-xs text-[var(--color-text-dim)]">
            Night {item.night} · pack <span className="font-mono">{item.pack}</span>
          </p>
        </div>
        {badge && (
          <span
            className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-raised)] px-2.5 py-1 text-xs uppercase tracking-wide text-[var(--color-text-dim)]"
          >
            <span className="h-2 w-2 rounded-full" style={{ background: BADGE_COLOR[badge] }} aria-hidden />
            {badge}
          </span>
        )}
      </div>

      <div className="mt-4 text-sm">
        {IS_DEMO && (
          <p className="text-[var(--color-text-dim)]">Recorded run: this candidate&apos;s measurements are not replayed here.</p>
        )}
        {!IS_DEMO && evidence === undefined && <p className="text-[var(--color-text-dim)]">Loading evidence…</p>}
        {!IS_DEMO && evidence === null && (
          <p className="text-[var(--color-text-dim)]">Could not load this candidate&apos;s measurements.</p>
        )}
        {!IS_DEMO && evidence && (
          <p className="text-[var(--color-text-dim)]">
            n={evidence.n_obs} paired observations: [{evidence.xs.map((x) => fixed(x, 3)).join(", ")}]
          </p>
        )}
      </div>

      {!IS_DEMO && <SignControls pack={item.pack} onSigned={onSigned} />}
    </div>
  );
}
