export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="border-b border-[var(--color-border)] px-8 py-6">
      <h1 className="text-xl font-semibold text-[var(--color-text)]">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-[var(--color-text-dim)]">{subtitle}</p>}
    </div>
  );
}
