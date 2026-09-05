import { defineConfig } from "@playwright/test";
import path from "node:path";

const localEngineHost: string = "127.0.0.1";
const localEnginePort: number = 8137;
const localEngineURL: string = `http://${localEngineHost}:${localEnginePort}`;
const localEngineObservationMs: number = 6_000;

/**
 * The deployed recording could pass while the engine served JSON in place of pages or called the wrong port.
 * The public-site project preserves that coverage; local-engine exercises the real CLI and static export.
 * Build the frontend before running local-engine so the engine has the actual pages to serve.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 15_000 },
  retries: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.BASE_URL ?? "https://pravrudhi.vercel.app",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "public-site",
      testMatch: "public-site.spec.ts",
    },
    {
      name: "local-engine",
      testMatch: "local-engine.spec.ts",
      use: { baseURL: localEngineURL },
      metadata: { localEngineObservationMs },
    },
  ],
  webServer: {
    // `python` is not on PATH here; the venv interpreter is the one the engine is installed into.
    command: `.venv/bin/python -m pravrudhi app --no-browser --port ${localEnginePort} --host ${localEngineHost}`,
    cwd: path.resolve(__dirname, "../.."),
    url: `${localEngineURL}/api/health`,
    reuseExistingServer: false,
  },
});
