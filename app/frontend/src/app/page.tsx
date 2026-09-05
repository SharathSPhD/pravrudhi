"use client";

import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { ApiError, startRun, status, type StatusResponse } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { BadgeDot } from "@/components/BadgeDot";

const BENCHMARKS = ["gsm8k", "mbppplus"] as const;
const PROPOSERS = ["Qwen3-30B-A3B", "GLM-4.7-Flash"] as const;
const POLICIES = ["efe", "greedy", "thompson", "random"] as const;

type RunOutcome = { kind: "idle" } | { kind: "started"; id: string } | { kind: "unsupported" } | { kind: "error"; message: string };

function selectClass() {
  return "w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]";
}

function labelClass() {
  return "mb-1.5 block text-xs font-medium uppercase tracking-wide text-[var(--color-text-dim)]";
}

export default function ImprovePage() {
  const [target, setTarget] = useState<"model" | "harness">("model");
  const [model, setModel] = useState("");
  const [bench, setBench] = useState<(typeof BENCHMARKS)[number]>(BENCHMARKS[0]);
  const [budget, setBudget] = useState(2);
  const [proposer, setProposer] = useState<(typeof PROPOSERS)[number]>(PROPOSERS[0]);
  const [policy, setPolicy] = useState<(typeof POLICIES)[number]>(POLICIES[0]);
  const [running, setRunning] = useState(false);
  const [outcome, setOutcome] = useState<RunOutcome>({ kind: "idle" });

  const [live, setLive] = useState<StatusResponse | null>(null);
  const [liveError, setLiveError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const s = await status();
        if (!cancelled) {
          setLive(s);
          setLiveError(false);
        }
      } catch {
        if (!cancelled) setLiveError(true);
      }
    }

    poll();
    const id = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  async function handleRun() {
    setRunning(true);
    setOutcome({ kind: "idle" });
    try {
      const handle = await startRun({
        target,
        model,
        bench,
        budget_gpu_h: budget,
        proposer,
        policy,
      });
      setOutcome({ kind: "started", id: handle.id });
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setOutcome({ kind: "unsupported" });
      } else {
        setOutcome({ kind: "error", message: err instanceof Error ? err.message : "unknown error" });
      }
    } finally {
      setRunning(false);
    }
  }

  const nightEntries = live && live.initialised ? Object.entries(live.nights) : [];
  const lastNight = nightEntries.length
    ? nightEntries.reduce((a, b) => (Number(a[0]) > Number(b[0]) ? a : b))[1]
    : null;
  const gpuHoursSpent = nightEntries.reduce((sum, [, n]) => sum + (n.spent_gpu_h ?? 0), 0);

  return (
    <div>
      <PageHeader title="Improve" subtitle="Pick a target, a benchmark and a budget, then watch it run." />
      <div className="grid grid-cols-1 gap-6 p-8 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="space-y-4">
            <div>
              <span className={labelClass()}>Target</span>
              <div className="flex gap-2">
                {(["model", "harness"] as const).map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTarget(t)}
                    className={`flex-1 rounded-md border px-3 py-2 text-sm capitalize transition-colors ${
                      target === t
                        ? "border-[var(--color-accent)] bg-[var(--color-accent-dim)]/30 text-[var(--color-text)]"
                        : "border-[var(--color-border)] text-[var(--color-text-dim)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            <label className="block">
              <span className={labelClass()}>{target === "model" ? "Model name" : "Harness name"}</span>
              <input
                className={selectClass()}
                placeholder={target === "model" ? "e.g. qwen3-4b" : "e.g. claude-code"}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </label>

            <label className="block">
              <span className={labelClass()}>Benchmark</span>
              <select className={selectClass()} value={bench} onChange={(e) => setBench(e.target.value as (typeof BENCHMARKS)[number])}>
                {BENCHMARKS.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className={labelClass()}>Budget (GPU-hours)</span>
              <input
                type="number"
                min={0}
                step={0.5}
                className={selectClass()}
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </label>

            <label className="block">
              <span className={labelClass()}>Proposer model</span>
              <select
                className={selectClass()}
                value={proposer}
                onChange={(e) => setProposer(e.target.value as (typeof PROPOSERS)[number])}
              >
                {PROPOSERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className={labelClass()}>Selection policy</span>
              <select className={selectClass()} value={policy} onChange={(e) => setPolicy(e.target.value as (typeof POLICIES)[number])}>
                {POLICIES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>

            <button
              type="button"
              onClick={handleRun}
              disabled={running || !model}
              className="flex w-full items-center justify-center gap-2 rounded-md bg-[var(--color-accent)] px-4 py-2.5 text-sm font-medium text-[#06110c] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Play size={15} />
              {running ? "Starting…" : "Run"}
            </button>

            {outcome.kind === "started" && (
              <p className="text-xs text-[var(--color-accent)]">Run started: {outcome.id}</p>
            )}
            {outcome.kind === "unsupported" && (
              <p className="text-xs text-[var(--color-warn)]">engine does not support runs yet</p>
            )}
            {outcome.kind === "error" && (
              <p className="text-xs text-[var(--color-danger)]">{outcome.message}</p>
            )}
          </div>
        </div>

        <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-medium text-[var(--color-text-dim)]">Live</h2>
          {liveError && (
            <p className="mt-3 text-sm text-[var(--color-text-dim)]">No status yet — the engine isn&apos;t reachable.</p>
          )}
          {!liveError && live && !live.initialised && (
            <p className="mt-3 text-sm text-[var(--color-text-dim)]">
              No ledger yet. Run <code>pravrudhi init</code> to get started.
            </p>
          )}
          {!liveError && live && live.initialised && (
            <div className="mt-4 space-y-6">
              <div>
                <div className={labelClass()}>Current incumbent</div>
                <div className="text-2xl font-semibold text-[var(--color-text)]">
                  {lastNight?.incumbent ?? "none yet"}
                </div>
              </div>
              <div>
                <div className={labelClass()}>GPU-hours spent</div>
                <div className="text-2xl font-semibold text-[var(--color-text)]">{gpuHoursSpent.toFixed(1)}</div>
              </div>
              <div>
                <div className={labelClass()}>Candidates ({live.candidates})</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(Object.entries(live.badges) as [string, number][]).map(([b, c]) => (
                    <BadgeDot key={b} badge={b} count={c} />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
