// Typed fetch client for the Pravrudhi engine's JSON API.
//
// Every function here can fail — there may be no engine running, or an endpoint may not exist yet on an
// older engine build. Callers are expected to handle rejection; nothing here retries or hides a failure.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/+$/, "") || "http://localhost:8008";

// Whether this page is a recording rather than a live engine.
//
// Decided at runtime, from where the page is being served, because that is what actually determines it: a browser
// blocks a page on a public origin from reaching an engine on the visitor's machine, so a public page trying
// anyway produces nothing but console errors. A page served by the engine itself is on localhost and is live.
// NEXT_PUBLIC_DEMO forces the recording on for local preview of the public site.
function detectDemo(): boolean {
  if (process.env.NEXT_PUBLIC_DEMO === "1") return true;
  if (typeof window === "undefined") return false;
  if (process.env.NEXT_PUBLIC_API_BASE) return false;
  const host = window.location.hostname;
  return !(host === "localhost" || host === "127.0.0.1" || host === "[::1]" || host === "::1");
}

export const IS_DEMO = detectDemo();

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly path: string,
  ) {
    super(`${path}: HTTP ${status}`);
    this.name = "ApiError";
  }
}

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

// The engine refuses state-changing requests without its local token, so that no page a user happens to be
// visiting can start work on their GPU. The token is readable only by a same-origin caller, which this app is
// when the engine serves it. It is fetched once and kept in memory; it is never stored anywhere a script on
// another page could reach.
let cachedToken: string | null = null;

export async function localToken(): Promise<string | null> {
  if (cachedToken !== null) return cachedToken;
  try {
    const res = await fetch(`${API_BASE}/app-token`, { cache: "no-store" });
    if (!res.ok) return null;
    cachedToken = ((await res.json()) as { token: string }).token;
    return cachedToken;
  } catch {
    return null;
  }
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const token = await localToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { "x-pravrudhi-token": token } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, path);
  return (await res.json()) as T;
}

export interface HealthResponse {
  ok: boolean;
  version: string;
  kernel: string;
  ledger: boolean;
}

export interface BadgeCounts {
  grey: number;
  amber: number;
  green: number;
  red: number;
}

export interface NightSummary {
  spent_gpu_h: number | null;
  outcomes: unknown;
  incumbent: string | null;
}

export type StatusResponse =
  | { initialised: false }
  | {
      initialised: true;
      chain_ok: boolean;
      events: number;
      ledger_head: string | null;
      state_hash: string;
      candidates: number;
      badges: BadgeCounts;
      promoted: Record<string, string[]>;
      pruned: number;
      nights: Record<string, NightSummary>;
      inbox_pending: string[];
      locks: unknown;
    };

export interface Candidate {
  id: string;
  badge: "grey" | "amber" | "green" | "red";
  surface: string | null;
  bucket: Record<string, string> | null;
  proposed_seq: number;
  edit_family: string | null;
  xs: number[];
  n_obs: number;
  cost_gpu_h: number;
  last_boundary: string | null;
  promoted: boolean;
  pruned: string | null;
  audit_high: boolean;
  skipped: boolean;
  rebased: number;
  incumbent_hash: string | null;
}

export interface HostInfo {
  name: string;
  transport: string;
  address: string;
  user: string;
  workdir: string;
  orca_host_id: string;
}

export interface HostCapabilities {
  os: string;
  arch: string;
  cpu_count: number;
  ram_gb: number;
  gpu_name: string;
  gpu_vram_gb: number;
  accelerator: "cuda" | "metal" | "none" | string;
  accel_mem_gb: number;
  docker: boolean;
  python: string;
  agents: string[];
  local_models: string[];
  reachable: boolean;
  error: string;
  can_train: boolean;
  can_serve_open_models: boolean;
  usable_model_gb: number;
}

export interface HostRow {
  host: HostInfo;
  capabilities: HostCapabilities;
}

export interface HostsResponse {
  hosts: HostRow[];
}

export interface AgentStatus {
  name: string;
  available: boolean;
  reason: string;
}

export interface ExternalRow {
  seq: number;
  night: number;
  kind: string;
  severity: string;
  tier: string;
  track: string;
  condition: string;
  model: string;
  tool: string;
  tool_version?: string | null;
  dataset?: string;
  metrics: Record<string, Record<string, number>>;
  n_samples?: Record<string, number | null>;
  sha256: string;
  [extra: string]: unknown;
}

export interface RunRequest {
  target: "model" | "harness";
  model: string;
  bench: string;
  budget_gpu_h: number;
  proposer: string;
  policy: string;
}

export interface RunHandle {
  id: string;
  [extra: string]: unknown;
}

export async function health(): Promise<HealthResponse> {
  if (IS_DEMO) {
    const d = await (await import("./demo")).demo();
    return { ok: true, version: d.engine.version, kernel: d.engine.version, ledger: true };
  }
  return getJSON<HealthResponse>("/health");
}

export async function status(): Promise<StatusResponse> {
  if (IS_DEMO) return (await (await import("./demo")).demo()).status;
  return getJSON<StatusResponse>("/status");
}

export async function candidates(): Promise<Candidate[]> {
  if (IS_DEMO) return [];
  return getJSON<Candidate[]>("/candidates");
}

export async function nights(): Promise<NightSummary[]> {
  if (IS_DEMO) return (await (await import("./demo")).demo()).nights;
  return getJSON<NightSummary[]>("/nights");
}

export async function hosts(): Promise<HostsResponse> {
  if (IS_DEMO) return (await import("./demo")).demoHosts();
  return getJSON<HostsResponse>("/hosts");
}

export async function agents(): Promise<AgentStatus[]> {
  if (IS_DEMO) return (await import("./demo")).demoAgents();
  return getJSON<AgentStatus[]>("/agents");
}

export async function external(): Promise<ExternalRow[]> {
  if (IS_DEMO) return (await (await import("./demo")).demo()).external;
  return getJSON<ExternalRow[]>("/external");
}

export async function startRun(req: RunRequest): Promise<RunHandle> {
  if (IS_DEMO) throw new ApiError(501, "/runs");
  return postJSON<RunHandle>("/runs", req);
}

export async function stopRun(runId: string): Promise<RunHandle> {
  return postJSON<RunHandle>(`/runs/${encodeURIComponent(runId)}/stop`, {});
}

// Everything a page needs to show a run as it happens, or what the loop produced. Added centrally so that pages
// built in parallel never contend for this file.

export interface RunEvent {
  // "proposed_one" and "pruned" appear in a recorded run, which is replayed from the engine's own record
  // rather than from the live log, so it carries per-candidate detail the live stream summarises.
  type: "paired" | "promoted" | "proposed" | "proposed_one" | "pruned" | "round" | "closed" | "log" | "end";
  t?: number;
  candidate?: string;
  seed?: number;
  incumbent?: number;
  candidate_score?: number;
  delta?: number;
  decision?: string;
  n?: number;
  raw?: number;
  accepted?: number;
  round?: number;
  selected?: number;
  remaining_gpu_h?: number;
  night?: number;
  status?: string;
  exit_code?: number;
  text?: string;
  strategy?: string | null;
  family?: string | null;
}

export interface RunDetail extends RunHandle {
  recent: RunEvent[];
}

export interface PromotedModel {
  id: string;
  track: "model" | "harness";
  night: number;
  recipe: Record<string, unknown>;
  artefact: string | null;
  external_before: Record<string, Record<string, number>> | null;
  external_after: Record<string, Record<string, number>> | null;
}

export async function runs(): Promise<RunHandle[]> {
  if (IS_DEMO) return (await (await import("./demo")).demo()).runs;
  return getJSON<RunHandle[]>("/runs");
}

export async function run(runId: string): Promise<RunDetail> {
  return getJSON<RunDetail>(`/runs/${encodeURIComponent(runId)}`);
}

export async function models(): Promise<PromotedModel[]> {
  if (IS_DEMO) return (await (await import("./demo")).demo()).models;
  return getJSON<PromotedModel[]>("/models");
}

/**
 * Subscribe to a run's live events. Returns a function that closes the stream.
 * The engine sends server-sent events; a closed or failed stream is reported through onError rather than thrown,
 * because a page showing a long run must survive a dropped connection.
 */
export function streamRun(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError?: (error: Event) => void,
): () => void {
  const source = new EventSource(`${API_BASE}/runs/${encodeURIComponent(runId)}/events`);
  source.onmessage = (message) => {
    try {
      onEvent(JSON.parse(message.data) as RunEvent);
    } catch {
      /* a malformed frame is skipped rather than killing the stream */
    }
  };
  source.onerror = (error) => {
    onError?.(error);
    source.close();
  };
  return () => source.close();
}
