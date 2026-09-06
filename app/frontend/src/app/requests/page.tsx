"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { RequestsList } from "@/components/requests/RequestsList";
import { SummaryStrip } from "@/components/requests/SummaryStrip";
import { requests, type RequestsResponse } from "@/lib/requests";

export default function RequestsPage() {
  // `undefined` is "still loading"; `null` is "the engine/recording has nothing to show" — kept apart from a
  // failed fetch so the empty state reads as honest rather than broken.
  const [data, setData] = useState<RequestsResponse | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    requests()
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

  return (
    <div>
      <PageHeader
        title="Requests"
        subtitle="Every ask you have made of the engine, and how far each has got."
      />
      <div className="space-y-6 p-8">
        {failed && (
          <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s requests API.</p>
        )}
        {!failed && data === undefined && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!failed && data === null && (
          <p className="text-sm text-[var(--color-text-dim)]">
            This recording predates the requests log. Nothing to show.
          </p>
        )}
        {!failed && data && (
          <>
            <SummaryStrip data={data} />
            <RequestsList items={data.requests} />
          </>
        )}
      </div>
    </div>
  );
}
