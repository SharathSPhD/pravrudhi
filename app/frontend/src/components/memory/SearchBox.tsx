"use client";

const field =
  "w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]";

export function SearchBox({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  return (
    <input
      className={field}
      placeholder="Search stored notes…"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
