// Typed fetch client for the engine's swarm views: which agents exist, where each tier routes today, what has
// been dispatched, and what agent process is running right now. A new file rather than additions to api.ts, so
// pages built in parallel never contend for that one.

import { ApiError, apiBase, IS_DEMO } from "./api";

export interface SwarmAgent {
  name: string;
  available: boolean;
  reason: string;
}

export interface RoutingRecord {
  route_id: string;
  tier: string;
  trials: number;
  successes: number;
  rate: number;
  lo: number;
  hi: number;
  mean_wall_s: number;
  relative_cost: number;
}

export interface RoutingRow {
  tier: string;
  route: string | null;
  agent: string | null;
  model: string | null;
  relative_cost: number | null;
  reason: string | null;
  records: RoutingRecord[];
  error: string | null;
}

export interface SubagentRun {
  objective: string;
  step: string;
  task_id: string;
  route: string;
  accepted: boolean;
  wall_s: number;
  files: string[];
  reasons: string[];
  at: string;
}

export interface SelfBuildRun {
  task_id: string;
  route: string;
  accepted: boolean;
  wall_s: number;
  files: string[];
  reasons: string[];
  at: string;
}

export interface SwarmSnapshot {
  agents: SwarmAgent[];
  routing: RoutingRow[];
  subagent_runs: SubagentRun[];
  selfbuild_runs: SelfBuildRun[];
}

export interface LiveAgent {
  pid: number;
  elapsed_s: number;
  kind: string;
  worktree: string | null;
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

// `null` means the recorded snapshot predates the swarm view, not that the engine has no swarm to show.
export async function swarm(): Promise<SwarmSnapshot | null> {
  if (IS_DEMO) {
    const { demo } = await import("./demo");
    const bundle = (await demo()) as Awaited<ReturnType<typeof demo>> & { swarm?: SwarmSnapshot };
    return bundle.swarm ?? null;
  }
  return getJSON<SwarmSnapshot>("/api/swarm");
}

// Live process state is never part of a recording: it describes what is running on this machine right now.
export async function swarmLive(): Promise<LiveAgent[]> {
  if (IS_DEMO) return [];
  return getJSON<LiveAgent[]>("/api/swarm/live");
}
