"use client";

import { useEffect, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { DiffViewer } from "@/components/diffs/DiffViewer";
import { TaskList } from "@/components/diffs/TaskList";
import { diffFor, recentDiffs, type TaskSummary, type WorktreeDiff } from "@/lib/diffs";

export default function DiffsPage() {
  const [tasks, setTasks] = useState<TaskSummary[] | null>(null);
  const [tasksFailed, setTasksFailed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  // Keyed by task id rather than one `diff`/`failed` pair, so switching back to an already-loaded task shows
  // it instantly instead of re-fetching, and a stale diff never flashes under a newly selected task's label.
  const [diffByTask, setDiffByTask] = useState<Record<string, WorktreeDiff>>({});
  const [failedTasks, setFailedTasks] = useState<Record<string, boolean>>({});
  const [loadingTask, setLoadingTask] = useState<string | null>(null);

  function loadDiff(taskId: string) {
    setLoadingTask(taskId);
    diffFor(taskId)
      .then((d) => {
        setDiffByTask((prev) => ({ ...prev, [taskId]: d }));
        setLoadingTask((prev) => (prev === taskId ? null : prev));
      })
      .catch(() => {
        setFailedTasks((prev) => ({ ...prev, [taskId]: true }));
        setLoadingTask((prev) => (prev === taskId ? null : prev));
      });
  }

  useEffect(() => {
    let cancelled = false;
    recentDiffs()
      .then((rows) => {
        if (cancelled) return;
        setTasks(rows);
        const first = rows[0]?.task_id;
        if (first) {
          setSelected(first);
          loadDiff(first);
        }
      })
      .catch(() => {
        if (!cancelled) setTasksFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelect(taskId: string) {
    setSelected(taskId);
    if (!diffByTask[taskId] && !failedTasks[taskId]) loadDiff(taskId);
  }

  const diff = selected ? diffByTask[selected] : undefined;
  const failed = selected ? !!failedTasks[selected] : false;
  const loading = selected !== null && selected === loadingTask;

  return (
    <div>
      <PageHeader
        title="Diffs"
        subtitle="What the swarm has actually changed, per dispatched task -- a real unified diff, not a summary of one."
      />
      <div className="flex gap-6 p-8">
        <div className="w-72 shrink-0 space-y-3">
          <h2 className="text-sm font-medium text-[var(--color-text)]">Dispatched tasks</h2>
          {tasksFailed && (
            <p className="text-sm text-[var(--color-text-dim)]">Could not reach the engine&apos;s diff API.</p>
          )}
          {!tasksFailed && tasks === null && <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>}
          {!tasksFailed && tasks !== null && <TaskList tasks={tasks} selected={selected} onSelect={handleSelect} />}
        </div>
        <div className="min-w-0 flex-1">
          {!selected && (
            <p className="text-sm text-[var(--color-text-dim)]">Select a dispatched task to see its diff.</p>
          )}
          {selected && failed && (
            <p className="text-sm text-[var(--color-text-dim)]">Could not load this task&apos;s diff.</p>
          )}
          {selected && !failed && loading && diff === undefined && (
            <p className="text-sm text-[var(--color-text-dim)]">Loading…</p>
          )}
          {selected && !failed && diff !== undefined && <DiffViewer diff={diff} />}
        </div>
      </div>
    </div>
  );
}
