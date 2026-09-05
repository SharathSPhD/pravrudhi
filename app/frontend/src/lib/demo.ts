// The recorded demo the public site runs on.
//
// A visitor has no engine, and a browser will not let a public page reach one on their machine: Chrome blocks the
// loopback address space from public origins outright. So the site does not pretend to be connected. It plays a
// real run that this project actually performed, from a snapshot exported by the engine, and tells the visitor
// plainly that it is recorded.

import type {
  AgentStatus,
  Candidate,
  ExternalRow,
  HostsResponse,
  NightSummary,
  PromotedModel,
  RunEvent,
  RunHandle,
  StatusResponse,
} from "./api";

export interface DemoRun extends RunHandle {
  policy: string | null;
  spent_gpu_h: number;
  candidates: number;
  pruned: number;
}

export interface DemoBundle {
  recorded: true;
  engine: { version: string; candidates: number };
  status: StatusResponse;
  models: PromotedModel[];
  external: ExternalRow[];
  nights: NightSummary[];
  runs: DemoRun[];
  featured_run: { id: string; night: number; track: string; events: RunEvent[] };
}

export { IS_DEMO as DEMO } from "./api";

let cache: Promise<DemoBundle> | null = null;

export function demo(): Promise<DemoBundle> {
  if (!cache) {
    cache = fetch("/demo.json", { cache: "force-cache" }).then((r) => {
      if (!r.ok) throw new Error("demo snapshot missing");
      return r.json() as Promise<DemoBundle>;
    });
  }
  return cache;
}

export async function demoCandidates(): Promise<Candidate[]> {
  return [];
}

export async function demoHosts(): Promise<HostsResponse> {
  return {
    hosts: [
      {
        host: { name: "the author's workstation", transport: "local", address: "", user: "", workdir: "", orca_host_id: "" },
        capabilities: {
          os: "Linux", arch: "x86_64", cpu_count: 32, ram_gb: 128, gpu_name: "NVIDIA GeForce RTX 5090",
          gpu_vram_gb: 31.8, accel_mem_gb: 31.8, accelerator: "cuda", docker: true, python: "3.13", agents: [], local_models: [],
          reachable: true, error: "", can_train: true, can_serve_open_models: true, usable_model_gb: 31.8,
        },
      },
      {
        host: { name: "a Mac mini", transport: "ssh", address: "", user: "", workdir: "", orca_host_id: "" },
        capabilities: {
          os: "Darwin", arch: "arm64", cpu_count: 10, ram_gb: 24, gpu_name: "Apple M4", gpu_vram_gb: 0,
          accelerator: "metal", accel_mem_gb: 17.8, docker: false, python: "3.9", agents: [], local_models: [], reachable: true,
          error: "", can_train: false, can_serve_open_models: true, usable_model_gb: 17.8,
        },
      },
    ],
  };
}

export async function demoAgents(): Promise<AgentStatus[]> {
  return [
    { name: "claude-code", available: true, reason: "ready" },
    { name: "codex", available: true, reason: "ready" },
    { name: "local (GLM-4.7-Flash)", available: true, reason: "ready" },
  ];
}
