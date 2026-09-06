"use client";

import { useState } from "react";
import { SignError, signInboxItem, type SignDecision, type SignResult } from "@/lib/inbox";

const LABELS: Record<SignDecision, string> = { approve: "Approve", reject: "Reject", defer: "Defer" };
const PENDING_LABELS: Record<SignDecision, string> = { approve: "Approving…", reject: "Rejecting…", defer: "Deferring…" };

export function SignControls({ pack, onSigned }: { pack: string; onSigned: () => void }) {
  const [operator, setOperator] = useState("");
  const [note, setNote] = useState("");
  const [pending, setPending] = useState<SignDecision | null>(null);
  const [result, setResult] = useState<SignResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function decide(decision: SignDecision) {
    setPending(decision);
    setResult(null);
    setError(null);
    try {
      const r = await signInboxItem(pack, decision, operator.trim(), note.trim());
      setResult(r);
      onSigned();
    } catch (e) {
      setError(e instanceof SignError ? e.message : "could not reach the engine");
    } finally {
      setPending(null);
    }
  }

  const disabled = !operator.trim() || pending !== null;

  return (
    <div className="mt-4 border-t border-[var(--color-border)] pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Your name"
          value={operator}
          onChange={(e) => setOperator(e.target.value)}
          className="w-40 rounded-md border border-[var(--color-border)] bg-transparent px-2 py-1 text-sm"
        />
        <input
          type="text"
          placeholder="Note (optional)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="min-w-[10rem] flex-1 rounded-md border border-[var(--color-border)] bg-transparent px-2 py-1 text-sm"
        />
      </div>
      <div className="mt-3 flex gap-2">
        {(["approve", "reject", "defer"] as const).map((decision) => (
          <button
            key={decision}
            type="button"
            disabled={disabled}
            onClick={() => decide(decision)}
            className={`rounded-md border border-[var(--color-border)] px-3 py-1 text-sm disabled:opacity-50 ${
              decision === "approve"
                ? "text-[var(--color-accent)]"
                : decision === "reject"
                  ? "text-[var(--color-danger)]"
                  : "text-[var(--color-text)]"
            }`}
          >
            {pending === decision ? PENDING_LABELS[decision] : LABELS[decision]}
          </button>
        ))}
      </div>
      {result && (
        <p className="mt-2 text-xs text-[var(--color-text-dim)]">
          Recorded: {result.decision} by {result.by} (seq {result.seq}, hash {result.this_hash.slice(0, 12)}…)
        </p>
      )}
      {error && <p className="mt-2 text-xs text-[var(--color-danger)]">{error}</p>}
    </div>
  );
}
