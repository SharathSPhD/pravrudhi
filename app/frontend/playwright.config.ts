import { defineConfig } from "@playwright/test";
import path from "node:path";

const localEngineHost: string = "127.0.0.1";
const localEnginePort: number = 8137;
const localEngineURL: string = `http://${localEngineHost}:${localEnginePort}`;
const localEngineObservationMs: number = 6_000;

// Which --project values this invocation asked for, so the local engine is only spun up when local-engine
// tests might actually run. Neither public-site nor deployed needs it, and deployed CI has no Python venv.
function requestedProjects(argv: readonly string[]): string[] {
  const projects: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--project" && argv[i + 1]) projects.push(argv[i + 1]);
    else if (arg.startsWith("--project=")) projects.push(arg.slice("--project=".length));
  }
  return projects;
}
const requested = requestedProjects(process.argv);
const needsLocalEngine = requested.length === 0 || requested.includes("local-engine");

/**
 * The deployed recording could pass while the engine served JSON in place of pages or called the wrong port.
 * The public-site project preserves that coverage; local-engine exercises the real CLI and static export;
 * deployed exercises the actual published GitHub Pages build. Build the frontend before running local-engine
 * so the engine has the actual pages to serve.
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
    {
      name: "deployed",
      testMatch: "deployed.spec.ts",
      // A trailing slash is load-bearing: goto() resolves a relative path against this base, and a bare
      // leading-slash path would resolve against the origin instead, dropping the GitHub Pages /pravrudhi/app
      // prefix entirely (the exact class of bug this suite exists to catch).
      use: { baseURL: `${(process.env.DEPLOYED_URL ?? "https://sharathsphd.github.io/pravrudhi/app").replace(/\/+$/, "")}/` },
    },
  ],
  webServer: needsLocalEngine
    ? {
        // `python` is not on PATH here; the venv interpreter is the one the engine is installed into.
        command: `.venv/bin/python -m pravrudhi app --no-browser --port ${localEnginePort} --host ${localEngineHost}`,
        cwd: path.resolve(__dirname, "../.."),
        url: `${localEngineURL}/api/health`,
        reuseExistingServer: false,
      }
    : undefined,
});
