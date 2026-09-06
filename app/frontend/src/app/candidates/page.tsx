"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { CandidatesChart } from "@/components/candidates/CandidatesChart";
import { CandidatesTable } from "@/components/candidates/CandidatesTable";
import { CandidateDetailPanel } from "@/components/candidates/CandidateDetailPanel";
import { candidatesSnapshot, type CandidatesSnapshot } from "@/lib/candidates";

export default function CandidatesPage() {
  const [data, setData] = useState<CandidatesSnapshot | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    candidatesSnapshot()
      .then((snapshot) => {
        if (!cancelled) setData(snapshot);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedRow = data?.rows.find((r) => r.candidate.id === selectedId) ?? null;

  return (
    <div>
      <PageHeader
        title="Candidates"
        subtitle="Every candidate the engine has ever scored: its kernel vector, badge, lineage, and outcome."
      />
      <div className="space-y-6 p-8">
        {failed && (
          <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s candidates API.</p>
        )}
        {!failed && data === undefined && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!failed && data !== undefined && data.candidates.length === 0 && (
          <p className="text-sm text-[var(--color-text-dim)]">
            No candidates recorded yet — nothing has been proposed to the ledger.
          </p>
        )}
        {!failed && data && data.candidates.length > 0 && (
          <>
            <CandidatesChart snapshot={data} onSelect={setSelectedId} />
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
              <CandidatesTable rows={data.rows} tracks={data.tracks} selectedId={selectedId} onSelect={setSelectedId} />
              {selectedRow && <CandidateDetailPanel row={selectedRow} onClose={() => setSelectedId(null)} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
