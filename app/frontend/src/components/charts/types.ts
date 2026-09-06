// Shapes read straight off the recorded snapshot (public/demo.json). Reuses the engine's own
// wire types from lib/api.ts wherever the shape matches, rather than re-declaring them.
import type { ExternalRow, Objective, PromotedModel, Recipe } from "@/lib/api";

export interface DemoNightRow {
  candidates: number;
  night: number;
  promoted: string[];
  pruned: number;
  selection_policy: string | null;
  spent_gpu_h: number;
  track: string;
}

export interface DemoObjectives {
  objectives: Objective[];
  problems: { file: string; reason: string }[];
}

export interface DemoEngine {
  candidates: number;
  version: string;
}

export interface DemoSnapshot {
  engine: DemoEngine;
  external: ExternalRow[];
  models: PromotedModel[];
  nights: DemoNightRow[];
  objectives: DemoObjectives;
  recipes: Recipe[];
}
