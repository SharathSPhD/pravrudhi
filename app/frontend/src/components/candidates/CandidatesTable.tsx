"use client";

import { useMemo, useState } from "react";
import type { CandidateRow } from "@/lib/candidates";
import { signedDelta } from "@/lib/candidates";

type SortKey = "id" | "night" | "track" | "badge" | "score" | "delta";
type SortDir = "asc" | "desc";

const BADGE_ORDER = ["grey", "amber", "green", "red"] as const;

// Returns 0 for "both absent" and NaN for "exactly one absent", so the caller can sink the absent row without
// the sort direction flipping it back up. Sorting by night descending put every never-observed candidate at the
// top of the table, so the first screen was nothing but dashes while 150 candidates with real measurements sat
// below the fold.
function compareValues(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) return 0;
  if (a === null || b === null) return NaN;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

function compareWithAbsentLast(
  a: string | number | null,
  b: string | number | null,
  dir: number,
): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return dir * compareValues(a, b);
}

export function CandidatesTable({
  rows,
  tracks,
  selectedId,
  onSelect,
}: {
  rows: CandidateRow[];
  tracks: string[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [badgeFilter, setBadgeFilter] = useState<Set<string>>(new Set());
  const [trackFilter, setTrackFilter] = useState("");
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("night");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  function toggleBadge(b: string) {
    setBadgeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(b)) next.delete(b);
      else next.add(b);
      return next;
    });
  }

  function sortBy(key: SortKey) {
    if (key === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const filtered = useMemo(
    () =>
      rows.filter((r) => {
        if (badgeFilter.size > 0 && !badgeFilter.has(r.candidate.badge)) return false;
        if (trackFilter && !r.tracks.includes(trackFilter)) return false;
        if (query && !r.candidate.id.toLowerCase().includes(query.toLowerCase())) return false;
        return true;
      }),
    [rows, badgeFilter, trackFilter, query],
  );

  const sorted = useMemo(() => {
    const keyOf = (r: CandidateRow): string | number | null => {
      switch (sortKey) {
        case "id":
          return r.candidate.id;
        case "night":
          return r.night;
        case "track":
          return r.tracks.join("/") || null;
        case "badge":
          return BADGE_ORDER.indexOf(r.candidate.badge as (typeof BADGE_ORDER)[number]);
        case "score":
          return r.score;
        case "delta":
          return r.candidate.n_obs > 0 ? r.pairedDelta : null;
      }
    };
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => compareWithAbsentLast(keyOf(a), keyOf(b), dir));
  }, [filtered, sortKey, sortDir]);

  function headerButton(key: SortKey, label: string) {
    const active = sortKey === key;
    return (
      <button
        type="button"
        onClick={() => sortBy(key)}
        className={`flex items-center gap-1 font-medium ${active ? "text-[var(--color-text)]" : ""}`}
      >
        {label}
        {active && <span aria-hidden>{sortDir === "asc" ? "▲" : "▼"}</span>}
      </button>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex flex-wrap gap-1.5">
          {BADGE_ORDER.map((b) => (
            <button
              key={b}
              type="button"
              onClick={() => toggleBadge(b)}
              className={`rounded-full border px-2.5 py-1 text-[11px] ${
                badgeFilter.has(b)
                  ? "border-[var(--color-accent)] text-[var(--color-text)]"
                  : "border-[var(--color-border)] text-[var(--color-text-dim)]"
              }`}
            >
              {b}
            </button>
          ))}
        </div>
        {tracks.length > 0 && (
          <select
            value={trackFilter}
            onChange={(e) => setTrackFilter(e.target.value)}
            className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[11px] text-[var(--color-text)]"
          >
            <option value="">all tracks</option>
            {tracks.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        )}
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="filter by id…"
          className="rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1 text-[11px] text-[var(--color-text)] placeholder:text-[var(--color-text-dim)]"
        />
        <span className="text-[11px] text-[var(--color-text-dim)]">
          {sorted.length} of {rows.length}
        </span>
      </div>

      {sorted.length === 0 ? (
        <p className="text-sm text-[var(--color-text-dim)]">No candidates match this filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[11px] uppercase tracking-wide text-[var(--color-text-dim)]">
                <th className="px-4 py-2">{headerButton("id", "ID")}</th>
                <th className="px-4 py-2">{headerButton("night", "Night")}</th>
                <th className="px-4 py-2">{headerButton("track", "Track")}</th>
                <th className="px-4 py-2">{headerButton("badge", "Badge")}</th>
                <th className="px-4 py-2">{headerButton("score", "Score")}</th>
                <th className="px-4 py-2">{headerButton("delta", "Paired Δ vs incumbent")}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((r) => (
                <tr
                  key={r.candidate.id}
                  onClick={() => onSelect(r.candidate.id)}
                  className={`cursor-pointer border-b border-[var(--color-border)] last:border-0 hover:bg-[var(--color-surface-raised)] ${
                    selectedId === r.candidate.id ? "bg-[var(--color-surface-raised)]" : ""
                  }`}
                >
                  <td className="px-4 py-2 font-mono text-[13px] text-[var(--color-text)]">{r.candidate.id}</td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{r.night ?? "—"}</td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{r.tracks.length > 0 ? r.tracks.join("/") : "—"}</td>
                  <td className="px-4 py-2 text-[var(--color-text-dim)]">{r.candidate.badge}</td>
                  <td className="px-4 py-2 tabular-nums text-[var(--color-text)]">{signedDelta(r.score)}</td>
                  <td className="px-4 py-2 tabular-nums text-[var(--color-text-dim)]">
                    {r.candidate.n_obs > 0 ? signedDelta(r.pairedDelta) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
