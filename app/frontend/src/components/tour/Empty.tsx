import type { ReactNode } from "react";

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-[var(--color-border)] p-4 text-sm text-[var(--color-text-dim)]">
      {children}
    </p>
  );
}
