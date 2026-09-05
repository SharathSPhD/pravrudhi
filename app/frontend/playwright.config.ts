import { defineConfig } from "@playwright/test";

/**
 * End-to-end tests run against a deployed site, not a mock.
 *
 * BASE_URL defaults to the public deployment, so `npx playwright test` checks what a visitor actually receives.
 * Point it at http://127.0.0.1:8008 to test a local engine serving the same build.
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
});
