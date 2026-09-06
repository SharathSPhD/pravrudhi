"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { DecidedTable } from "@/components/inbox/DecidedTable";
import { InboxCard } from "@/components/inbox/InboxCard";
import { IS_DEMO } from "@/lib/api";
import { inbox, type InboxItem } from "@/lib/inbox";

export default function InboxPage() {
  const [items, setItems] = useState<InboxItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    inbox()
      .then(setItems)
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const pending = items?.filter((i) => !i.signed) ?? [];
  const decided = items?.filter((i) => i.signed) ?? [];

  return (
    <div>
      <PageHeader
        title="Inbox"
        subtitle="Candidates the engine wants promoted, waiting for a human sign-off."
      />
      <div className="space-y-8 p-8">
        {failed && <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s inbox.</p>}
        {!failed && items === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
        {!failed && items !== null && items.length === 0 && (
          <p className="text-sm text-[var(--color-text-dim)]">Nothing is waiting for sign-off.</p>
        )}
        {!failed && items !== null && items.length > 0 && (
          <>
            {IS_DEMO && (
              <p className="text-sm text-[var(--color-text-dim)]">
                This is a recorded run: these items are shown read-only. Signing needs a local engine.
              </p>
            )}
            {pending.length === 0 ? (
              <p className="text-sm text-[var(--color-text-dim)]">Nothing is waiting for sign-off.</p>
            ) : (
              <section className="space-y-4">
                {pending.map((item) => (
                  <InboxCard key={item.pack} item={item} onSigned={load} />
                ))}
              </section>
            )}

            {decided.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-medium text-[var(--color-text)]">Already decided</h2>
                <DecidedTable items={decided} />
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
