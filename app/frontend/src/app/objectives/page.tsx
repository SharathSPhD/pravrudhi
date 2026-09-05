"use client";

// The surface the whole product is for: state what you want, and see whether it is happening.
//
// Three states are kept visibly distinct because they mean different things. An objective with no baseline has not
// been measured; an objective with a baseline and nothing to compare against has been measured once; only the third
// carries a difference. Rendering the first two as a zero would tell the user the loop had failed when in fact it
// has not yet run.

import { useCallback, useEffect, useState } from "react";
import { Target, Plus, CircleDashed, Minus, TrendingUp, TrendingDown, Package } from "lucide-react";
import {
  objectives as fetchObjectives,
  recipeLibrary,
  type BenchmarkProgress,
  type Objective,
  type Recipe,
  IS_DEMO,
  postObjective,
} from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function Verdict({ p }: { p: BenchmarkProgress }) {
  if (p.state !== "measured" || p.delta === null) return null;
  if (!p.significant) {
    return (
      <span className="inline-flex items-center gap-1.5 text-[var(--color-text-dim)]">
        <Minus size={14} /> not distinguishable from no change
      </span>
    );
  }
  const up = p.delta > 0;
  return (
    <span
      className={`inline-flex items-center gap-1.5 ${up ? "text-[var(--color-accent)]" : "text-[var(--color-danger)]"}`}
    >
      {up ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
      {up ? "improvement" : "regression"}
    </span>
  );
}

function Bar({ p }: { p: BenchmarkProgress }) {
  if (p.state === "unmeasured" || !p.baseline) return null;
  const base = p.baseline.value;
  const now = p.latest ? p.latest.value : base;
  const top = Math.max(base, now, 0.0001);
  const scale = (v: number) => `${Math.max(2, (v / top) * 100)}%`;
  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-3 text-xs">
        <span className="w-16 shrink-0 text-[var(--color-text-dim)]">baseline</span>
        <div className="h-2 flex-1 rounded-full bg-[var(--color-surface-raised)]">
          <div className="h-2 rounded-full bg-[var(--color-text-dim)]" style={{ width: scale(base) }} />
        </div>
        <span className="w-16 shrink-0 text-right tabular-nums text-[var(--color-text)]">{pct(base)}</span>
      </div>
      {p.latest && (
        <div className="flex items-center gap-3 text-xs">
          <span className="w-16 shrink-0 text-[var(--color-text-dim)]">current</span>
          <div className="h-2 flex-1 rounded-full bg-[var(--color-surface-raised)]">
            <div
              className={`h-2 rounded-full ${
                p.significant && p.delta !== null && p.delta > 0
                  ? "bg-[var(--color-accent)]"
                  : p.significant
                    ? "bg-[var(--color-danger)]"
                    : "bg-[var(--color-text-dim)]"
              }`}
              style={{ width: scale(now) }}
            />
          </div>
          <span className="w-16 shrink-0 text-right tabular-nums text-[var(--color-text)]">{pct(now)}</span>
        </div>
      )}
    </div>
  );
}

function BenchmarkCard({ p }: { p: BenchmarkProgress }) {
  return (
    <div className="rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-mono text-xs text-[var(--color-text)]">{p.benchmark}</span>
        <Verdict p={p} />
      </div>

      {p.state === "unmeasured" && (
        <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-[var(--color-text-dim)]">
          <CircleDashed size={14} className="mt-0.5 shrink-0" />
          {p.reason}
        </p>
      )}

      <Bar p={p} />

      {p.state === "baseline_only" && (
        <p className="mt-2 text-xs text-[var(--color-text-dim)]">{p.reason}</p>
      )}

      {p.state === "measured" && p.delta !== null && (
        <div className="mt-3 border-t border-[var(--color-border)] pt-3">
          <div className="flex items-baseline justify-between text-xs">
            <span className="text-[var(--color-text-dim)]">change</span>
            <span className="tabular-nums text-[var(--color-text)]">
              {p.delta >= 0 ? "+" : ""}
              {pct(p.delta)}
              {p.delta_lo !== null && p.delta_hi !== null && (
                <span className="ml-2 text-[var(--color-text-dim)]">
                  [{p.delta_lo >= 0 ? "+" : ""}
                  {pct(p.delta_lo)}, {p.delta_hi >= 0 ? "+" : ""}
                  {pct(p.delta_hi)}]
                </span>
              )}
            </span>
          </div>
          {p.target_delta !== null && (
            <div className="mt-1 flex items-baseline justify-between text-xs">
              <span className="text-[var(--color-text-dim)]">target</span>
              <span className="tabular-nums text-[var(--color-text)]">
                +{pct(p.target_delta)}
                <span className={`ml-2 ${p.met ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"}`}>
                  {p.met ? "met" : "not met"}
                </span>
              </span>
            </div>
          )}
          {p.baseline && p.latest && (
            <p className="mt-2 text-[11px] leading-4 text-[var(--color-text-dim)]">
              Scored outside the engine on {p.baseline.n} items. Baseline model {p.baseline.model}. Admitted to the
              ledger as rows {p.baseline.seq} and {p.latest.seq}.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function ObjectiveCard({ o }: { o: Objective }) {
  return (
    <article className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Target size={16} className="text-[var(--color-text-dim)]" />
        <h2 className="text-sm font-medium text-[var(--color-text)]">{o.id}</h2>
        {o.domain && (
          <span className="rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[11px] text-[var(--color-text-dim)]">
            {o.domain}
          </span>
        )}
        <span className="ml-auto font-mono text-[11px] text-[var(--color-text-dim)]">track {o.track}</span>
      </div>

      <p className="mt-3 text-sm leading-6 text-[var(--color-text)]">{o.intent}</p>

      <div className="mt-4 grid gap-3">
        {o.progress.map((p) => (
          <BenchmarkCard key={p.benchmark} p={p} />
        ))}
      </div>

      {o.notes && (
        <p className="mt-4 border-t border-[var(--color-border)] pt-3 text-xs leading-5 text-[var(--color-text-dim)]">
          {o.notes}
        </p>
      )}

      {o.recipes.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-[var(--color-text-dim)]">recipes</span>
          {o.recipes.map((r) => (
            <span
              key={r}
              className="rounded border border-[var(--color-border)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-text-dim)]"
            >
              {r}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function NewObjective({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [id, setId] = useState("");
  const [intent, setIntent] = useState("");
  const [track, setTrack] = useState("");
  const [metric, setMetric] = useState("");
  const [domain, setDomain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        disabled={IS_DEMO}
        className="flex items-center gap-2 rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2.5 text-sm text-[var(--color-text)] transition-colors hover:bg-[var(--color-surface-raised)] disabled:cursor-not-allowed disabled:opacity-50"
        title={IS_DEMO ? "This is a recording. Run the engine on your own machine to state an objective." : undefined}
      >
        <Plus size={16} />
        State an objective
      </button>
    );
  }

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await postObjective({
        id,
        intent,
        track,
        domain,
        benchmarks: [{ id: "", tool: "lm-eval", metric, direction: "up" }],
        recipes: [],
        target_delta: null,
        notes: "",
      });
      setOpen(false);
      setId("");
      setIntent("");
      setTrack("");
      setMetric("");
      setDomain("");
      onCreated();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const field =
    "w-full rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]";

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <h2 className="text-sm font-medium text-[var(--color-text)]">What do you want the loop to achieve?</h2>
      <p className="mt-1 text-xs leading-5 text-[var(--color-text-dim)]">
        Write it in your own words. It is recorded verbatim and never interpreted. An objective needs a benchmark:
        without one there is nothing that could tell you whether it worked.
      </p>

      <div className="mt-4 grid gap-3">
        <label className="grid gap-1.5">
          <span className="text-xs text-[var(--color-text-dim)]">Intent</span>
          <textarea
            className={`${field} min-h-24 resize-y leading-6`}
            placeholder="A legal-reasoning assistant that answers a question of law with the statute it relied on, and says it does not know rather than inventing a citation."
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1.5">
            <span className="text-xs text-[var(--color-text-dim)]">Short name</span>
            <input className={field} placeholder="legal-mvp" value={id} onChange={(e) => setId(e.target.value)} />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs text-[var(--color-text-dim)]">Domain</span>
            <input className={field} placeholder="legal" value={domain} onChange={(e) => setDomain(e.target.value)} />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs text-[var(--color-text-dim)]">Track</span>
            <input className={field} placeholder="nyaya" value={track} onChange={(e) => setTrack(e.target.value)} />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs text-[var(--color-text-dim)]">Benchmark metric</span>
            <input
              className={field}
              placeholder="mmlu_professional_law acc,none"
              value={metric}
              onChange={(e) => setMetric(e.target.value)}
            />
          </label>
        </div>
      </div>

      {error && <p className="mt-3 text-xs text-[var(--color-danger)]">{error}</p>}

      <div className="mt-4 flex gap-2">
        <button
          onClick={submit}
          disabled={busy || !id || !intent || !track || !metric}
          className="rounded-md bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-bg)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Saving…" : "Record it"}
        </button>
        <button
          onClick={() => setOpen(false)}
          className="rounded-md border border-[var(--color-border)] px-4 py-2 text-sm text-[var(--color-text-dim)]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function RecipeShelf({ rows }: { rows: Recipe[] }) {
  const byCapability = rows.reduce<Record<string, Recipe[]>>((acc, r) => {
    (acc[r.capability] ||= []).push(r);
    return acc;
  }, {});
  return (
    <section className="mt-10">
      <div className="flex items-center gap-2">
        <Package size={16} className="text-[var(--color-text-dim)]" />
        <h2 className="text-sm font-medium text-[var(--color-text)]">Recipes an objective can draw on</h2>
      </div>
      <p className="mt-1 max-w-3xl text-xs leading-5 text-[var(--color-text-dim)]">
        Published training and evaluation recipes. Listing one here does not claim it has been run: a recipe becomes
        evidence only when a run executes it and the result is recorded.
      </p>
      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(byCapability).map(([capability, list]) => (
          <div key={capability} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
            <h3 className="text-xs font-medium uppercase tracking-wide text-[var(--color-text-dim)]">{capability}</h3>
            <ul className="mt-3 space-y-2.5">
              {list.map((r) => (
                <li key={r.id}>
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm text-[var(--color-text)]">{r.title}</span>
                    <span
                      className={`text-[11px] ${r.available ? "text-[var(--color-accent)]" : "text-[var(--color-text-dim)]"}`}
                    >
                      {r.available ? "available" : "not installed"}
                    </span>
                  </div>
                  <p className="text-[11px] leading-4 text-[var(--color-text-dim)]">{r.summary}</p>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function ObjectivesPage() {
  const [rows, setRows] = useState<Objective[] | null>(null);
  const [broken, setBroken] = useState<{ file: string; reason: string }[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [unsupported, setUnsupported] = useState(false);

  const load = useCallback(() => {
    fetchObjectives()
      .then((d) => {
        setRows(d.objectives);
        setBroken(d.problems);
      })
      .catch(() => setUnsupported(true));
    recipeLibrary()
      .then(setRecipes)
      .catch(() => setRecipes([]));
  }, []);

  useEffect(load, [load]);

  return (
    <div>
      <PageHeader
        title="Objectives"
        subtitle="What you want, and whether it is happening. Every number here comes from a benchmark scored outside the engine."
      />
      <div className="p-8">
        {unsupported && (
          <p className="text-sm text-[var(--color-text-dim)]">This engine build does not report objectives yet.</p>
        )}

        {!unsupported && (
          <>
            <NewObjective onCreated={load} />

            {broken.length > 0 && (
              <div className="mt-6 rounded-md border border-[var(--color-danger)] bg-[var(--color-surface)] p-4">
                {broken.map((b) => (
                  <p key={b.file} className="text-xs text-[var(--color-danger)]">
                    {b.file} will not load: {b.reason}
                  </p>
                ))}
              </div>
            )}

            {rows === null && <p className="mt-6 text-sm text-[var(--color-text-dim)]">Loading…</p>}

            {rows !== null && rows.length === 0 && (
              <p className="mt-6 max-w-2xl text-sm leading-6 text-[var(--color-text-dim)]">
                No objectives yet. An objective is what you want the loop to achieve, plus the benchmark that would
                tell you whether it did.
              </p>
            )}

            {rows !== null && rows.length > 0 && (
              <div className="mt-6 grid gap-5 xl:grid-cols-2">
                {rows.map((o) => (
                  <ObjectiveCard key={o.id} o={o} />
                ))}
              </div>
            )}

            {recipes.length > 0 && <RecipeShelf rows={recipes} />}
          </>
        )}
      </div>
    </div>
  );
}
