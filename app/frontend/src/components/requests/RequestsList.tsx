import type { RequestItem } from "@/lib/requests";
import { RequestRow } from "./RequestRow";

export function RequestsList({ items }: { items: RequestItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-[var(--color-text-dim)]">Nothing asked yet.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <RequestRow key={item.id} item={item} />
      ))}
    </div>
  );
}
