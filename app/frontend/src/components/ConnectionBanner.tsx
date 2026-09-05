"use client";

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { API_BASE, health } from "@/lib/api";

export function ConnectionBanner() {
  const [reachable, setReachable] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      try {
        await health();
        if (!cancelled) setReachable(true);
      } catch {
        if (!cancelled) setReachable(false);
      }
    }

    check();
    const id = setInterval(check, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (reachable) return null;

  return (
    <div className="flex items-center gap-2 border-b border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 px-5 py-2 text-sm text-[var(--color-danger)]">
      <AlertTriangle size={14} />
      <span>
        No engine reachable at {API_BASE}. Start one with <code>pravrudhi app</code>.
      </span>
    </div>
  );
}
