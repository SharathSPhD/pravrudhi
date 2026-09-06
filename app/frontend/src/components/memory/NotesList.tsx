import type { MemoryNote } from "@/lib/memory";

export function NotesList({ notes, query }: { notes: MemoryNote[]; query: string }) {
  if (notes.length === 0) {
    return (
      <p className="text-sm text-[var(--color-text-dim)]">
        {query.trim() ? "No stored note matches that search." : "No notes remembered yet."}
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {notes.map((note) => (
        <div key={note.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-[10px] uppercase tracking-wide text-[var(--color-text-dim)]">{note.source}</span>
            <span className="ml-auto font-mono text-[11px] text-[var(--color-text-dim)]">{note.created}</span>
          </div>
          <p className="mt-1 text-sm leading-6 text-[var(--color-text)]">{note.text}</p>
        </div>
      ))}
    </div>
  );
}
