import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import type { TourStepMeta } from "@/lib/tour";

export function TourNav({
  steps,
  current,
  playing,
  onSelect,
  onPrev,
  onNext,
  onTogglePlay,
}: {
  steps: TourStepMeta[];
  current: number;
  playing: boolean;
  onSelect: (n: number) => void;
  onPrev: () => void;
  onNext: () => void;
  onTogglePlay: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrev}
          disabled={current === 1}
          className="flex items-center gap-1 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ChevronLeft size={14} />
          Previous
        </button>
        <button
          type="button"
          onClick={onTogglePlay}
          className="flex items-center gap-1.5 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-white/5"
        >
          {playing ? <Pause size={13} /> : <Play size={13} />}
          {playing ? "Pause" : "Play through"}
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={current === steps.length}
          className="flex items-center gap-1 rounded-md border border-[var(--color-border)] px-3 py-1.5 text-xs hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
          <ChevronRight size={14} />
        </button>
      </div>
      <div className="flex items-center gap-1.5">
        {steps.map((step) => (
          <button
            key={step.n}
            type="button"
            onClick={() => onSelect(step.n)}
            title={step.title}
            aria-label={`Step ${step.n}: ${step.title}`}
            aria-current={step.n === current}
            className={`h-2 w-2 rounded-full transition-colors ${
              step.n === current ? "bg-[var(--color-accent)]" : "bg-[var(--color-border)] hover:bg-[var(--color-text-dim)]"
            }`}
          />
        ))}
      </div>
      <span className="text-xs text-[var(--color-text-dim)]">
        Step {current} of {steps.length}
      </span>
    </div>
  );
}
