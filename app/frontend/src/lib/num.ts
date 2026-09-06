// Formatting helpers that survive a missing number.
//
// A record written by an older engine build, or a run that failed before it timed anything, arrives with fields
// absent. Calling .toFixed() on one of those throws inside render, React unmounts the tree, and the page shows an
// error while the server still answers 200 — the heartbeat page served exactly that for hours. Every numeric
// field rendered from engine data goes through here.

export function secs(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(digits)}s` : "—";
}

export function fixed(v: number | null | undefined, digits = 1): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";
}

export function percent(v: number | null | undefined, digits = 0): string {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * 100).toFixed(digits)}%` : "—";
}
