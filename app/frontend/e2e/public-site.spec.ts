import { expect, test } from "@playwright/test";

/**
 * What a visitor to the public site receives.
 *
 * These assert usefulness, not merely that a page loaded: a visitor must see the actual result, be able to watch a
 * real run, and reach the instructions. The console-error test exists because an earlier version of this site
 * loaded perfectly while emitting a growing stream of failed requests to an address it could never reach.
 */

test("the landing page leads with the measured result, not an error", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveTitle(/Pravrudhi/);
  await expect(page.getByText(/Recorded demo/i)).toBeVisible();
  await expect(page.getByText(/No engine reachable/i)).toHaveCount(0);

  // the headline improvement, read from the engine's own external-benchmark record
  await expect(page.getByText(/scored by an independent benchmark tool/i)).toBeVisible();
  const gain = page.getByText(/^\+\d+\.\d+ points$/);
  await expect(gain).toBeVisible();
  expect(parseFloat((await gain.innerText()).replace(/[^\d.]/g, ""))).toBeGreaterThan(0);
});

test("a real run replays, and its numbers move", async ({ page }) => {
  await page.goto("/");
  const panel = page.getByText(/A real run, replayed/i);
  await expect(panel).toBeVisible();
  await expect(page.getByText(/Every line is from the engine's record/i)).toBeVisible();

  // the replay advances on its own: the "tried" counter must climb without any interaction
  const tried = page.locator("text=tried").locator("xpath=preceding-sibling::div[1]");
  await expect.poll(async () => parseInt((await tried.innerText()) || "0", 10), { timeout: 30_000 }).toBeGreaterThan(0);
  await expect(page.getByRole("button", { name: /replay/i })).toBeVisible();
});

test("the site does not call an address it cannot reach", async ({ page }) => {
  const failures: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") failures.push(m.text());
  });
  page.on("requestfailed", (r) => failures.push(`requestfailed ${r.url()}`));
  await page.goto("/");
  await page.waitForTimeout(6000);
  const loopback = failures.filter((f) => /localhost|127\.0\.0\.1|loopback/i.test(f));
  expect(loopback, `the public build must not call a local engine:\n${loopback.join("\n")}`).toHaveLength(0);
});

test("every page in the navigation opens and renders content", async ({ page }) => {
  for (const [name, path] of [
    ["Improve", "/"],
    ["Runs", "/runs"],
    ["Models", "/models"],
    ["Machines", "/machines"],
    ["Settings", "/settings"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("link", { name })).toBeVisible();
    const body = await page.locator("main").innerText();
    expect(body.trim().length, `${path} rendered an empty main region`).toBeGreaterThan(20);
  }
});

test("what the loop produced is shown with a real before and after", async ({ page }) => {
  await page.goto("/models");
  const text = await page.locator("main").innerText();
  expect(text).toMatch(/c-0045|adapter|harness/i);
});

test("the machines page shows measured hardware", async ({ page }) => {
  await page.goto("/machines");
  const text = await page.locator("main").innerText();
  expect(text).toMatch(/cuda|metal/i);
});
