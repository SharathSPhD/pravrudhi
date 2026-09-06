// Turns the flat `external` ledger rows into one series per (track, task, headline metric), the
// grouping the progress charts render one-per-benchmark from.
import type { ExternalRow } from "@/lib/api";

export interface SeriesPoint {
  seq: number;
  night: number;
  value: number;
  err?: number;
  condition: string;
  model: string;
  n?: number;
  tool: string;
  isBase: boolean;
}

export interface BenchmarkGroup {
  key: string;
  track: string;
  task: string;
  metric: string;
  points: SeriesPoint[];
}

function pickHeadline(metricsForTask: Record<string, number>): { metric: string; value: number } | null {
  const preferred = metricsForTask["exact_match,strict-match"];
  if (typeof preferred === "number" && Number.isFinite(preferred)) {
    return { metric: "exact_match,strict-match", value: preferred };
  }
  for (const [key, value] of Object.entries(metricsForTask)) {
    if (key.includes("stderr") || !Number.isFinite(value)) continue;
    return { metric: key, value };
  }
  return null;
}

function stderrKeyFor(metric: string): string {
  const [name, filter] = metric.split(",");
  return filter !== undefined ? `${name}_stderr,${filter}` : `${name}_stderr`;
}

function tasksFromRow(row: ExternalRow): { task: string; metric: string; value: number; err?: number; n?: number }[] {
  const dataset = row.dataset;
  if (dataset && row.metrics[dataset] && typeof row.metrics[dataset]["pass@1_plus"] === "number") {
    return [
      {
        task: dataset,
        metric: "pass@1_plus",
        value: row.metrics[dataset]["pass@1_plus"],
        n: row.n_samples?.[dataset] ?? undefined,
      },
    ];
  }
  const out: { task: string; metric: string; value: number; err?: number; n?: number }[] = [];
  for (const [task, metricsForTask] of Object.entries(row.metrics)) {
    if (task.endsWith("_counts")) continue;
    const headline = pickHeadline(metricsForTask);
    if (!headline) continue;
    const err = metricsForTask[stderrKeyFor(headline.metric)];
    out.push({
      task,
      metric: headline.metric,
      value: headline.value,
      err: typeof err === "number" && Number.isFinite(err) ? err : undefined,
      n: row.n_samples?.[task] ?? undefined,
    });
  }
  return out;
}

// "base-replicate" is a rerun of the base condition (same model, no candidate change), so it is
// coloured with the base series rather than read as a candidate.
function isBaseCondition(condition: string): boolean {
  return condition === "base" || condition.startsWith("base-");
}

export function groupBenchmarkSeries(external: ExternalRow[]): BenchmarkGroup[] {
  const groups = new Map<string, BenchmarkGroup>();
  for (const row of external) {
    for (const t of tasksFromRow(row)) {
      const key = `${row.track}::${t.task}::${t.metric}`;
      let group = groups.get(key);
      if (!group) {
        group = { key, track: row.track, task: t.task, metric: t.metric, points: [] };
        groups.set(key, group);
      }
      group.points.push({
        seq: row.seq,
        night: row.night,
        value: t.value,
        err: t.err,
        condition: row.condition,
        model: row.model,
        n: t.n,
        tool: row.tool,
        isBase: isBaseCondition(row.condition),
      });
    }
  }
  const result = [...groups.values()];
  for (const g of result) g.points.sort((a, b) => a.seq - b.seq);
  result.sort((a, b) => a.track.localeCompare(b.track) || a.task.localeCompare(b.task) || a.metric.localeCompare(b.metric));
  return result;
}
