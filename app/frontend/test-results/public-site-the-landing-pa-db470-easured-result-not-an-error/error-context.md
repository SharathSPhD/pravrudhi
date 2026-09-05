# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: public-site.spec.ts >> the landing page leads with the measured result, not an error
- Location: e2e/public-site.spec.ts:11:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText(/Recorded demo/i)
Expected: visible
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText(/Recorded demo/i) with timeout 15000ms
  - waiting for getByText(/Recorded demo/i)

```

```yaml
- complementary:
  - text: Pravrudhi
  - paragraph: Improve your model or your agent harness, on your hardware, while you watch.
  - navigation:
    - link "Improve":
      - /url: /
    - link "Runs":
      - /url: /runs
    - link "Models":
      - /url: /models
    - link "Machines":
      - /url: /machines
    - link "Settings":
      - /url: /settings
- text: No engine reachable at http://localhost:8008. Start one with
- code: pravrudhi app
- text: .
- main:
  - heading "Improve" [level=1]
  - paragraph: Pick a target, a benchmark and a budget, then watch it run.
  - text: Target
  - button "model"
  - button "harness"
  - text: Model name
  - textbox "Model name":
    - /placeholder: e.g. qwen3-4b
  - text: Benchmark
  - combobox "Benchmark":
    - option "gsm8k" [selected]
    - option "mbppplus"
  - text: Budget (GPU-hours)
  - spinbutton "Budget (GPU-hours)": "2"
  - text: Proposer model
  - combobox "Proposer model":
    - option "Qwen3-30B-A3B" [selected]
    - option "GLM-4.7-Flash"
  - text: Selection policy
  - combobox "Selection policy":
    - option "efe" [selected]
    - option "greedy"
    - option "thompson"
    - option "random"
  - button "Run" [disabled]
  - heading "Live" [level=2]
  - paragraph: No status yet — the engine isn't reachable.
- alert
```

# Test source

```ts
  1  | import { expect, test } from "@playwright/test";
  2  | 
  3  | /**
  4  |  * What a visitor to the public site receives.
  5  |  *
  6  |  * These assert usefulness, not merely that a page loaded: a visitor must see the actual result, be able to watch a
  7  |  * real run, and reach the instructions. The console-error test exists because an earlier version of this site
  8  |  * loaded perfectly while emitting a growing stream of failed requests to an address it could never reach.
  9  |  */
  10 | 
  11 | test("the landing page leads with the measured result, not an error", async ({ page }) => {
  12 |   await page.goto("/");
  13 |   await expect(page).toHaveTitle(/Pravrudhi/);
> 14 |   await expect(page.getByText(/Recorded demo/i)).toBeVisible();
     |                                                  ^ Error: expect(locator).toBeVisible() failed
  15 |   await expect(page.getByText(/No engine reachable/i)).toHaveCount(0);
  16 | 
  17 |   // the headline improvement, read from the engine's own external-benchmark record
  18 |   await expect(page.getByText(/scored by an independent benchmark tool/i)).toBeVisible();
  19 |   const gain = page.getByText(/^\+\d+\.\d+ points$/);
  20 |   await expect(gain).toBeVisible();
  21 |   expect(parseFloat((await gain.innerText()).replace(/[^\d.]/g, ""))).toBeGreaterThan(0);
  22 | });
  23 | 
  24 | test("a real run replays, and its numbers move", async ({ page }) => {
  25 |   await page.goto("/");
  26 |   const panel = page.getByText(/A real run, replayed/i);
  27 |   await expect(panel).toBeVisible();
  28 |   await expect(page.getByText(/Every line is from the engine's record/i)).toBeVisible();
  29 | 
  30 |   // the replay advances on its own: the "tried" counter must climb without any interaction
  31 |   const tried = page.locator("text=tried").locator("xpath=preceding-sibling::div[1]");
  32 |   await expect.poll(async () => parseInt((await tried.innerText()) || "0", 10), { timeout: 30_000 }).toBeGreaterThan(0);
  33 |   await expect(page.getByRole("button", { name: /replay/i })).toBeVisible();
  34 | });
  35 | 
  36 | test("the site does not call an address it cannot reach", async ({ page }) => {
  37 |   const failures: string[] = [];
  38 |   page.on("console", (m) => {
  39 |     if (m.type() === "error") failures.push(m.text());
  40 |   });
  41 |   page.on("requestfailed", (r) => failures.push(`requestfailed ${r.url()}`));
  42 |   await page.goto("/");
  43 |   await page.waitForTimeout(6000);
  44 |   const loopback = failures.filter((f) => /localhost|127\.0\.0\.1|loopback/i.test(f));
  45 |   expect(loopback, `the public build must not call a local engine:\n${loopback.join("\n")}`).toHaveLength(0);
  46 | });
  47 | 
  48 | test("every page in the navigation opens and renders content", async ({ page }) => {
  49 |   for (const [name, path] of [
  50 |     ["Improve", "/"],
  51 |     ["Runs", "/runs"],
  52 |     ["Models", "/models"],
  53 |     ["Machines", "/machines"],
  54 |     ["Settings", "/settings"],
  55 |   ] as const) {
  56 |     await page.goto(path);
  57 |     await expect(page.getByRole("link", { name })).toBeVisible();
  58 |     const body = await page.locator("main").innerText();
  59 |     expect(body.trim().length, `${path} rendered an empty main region`).toBeGreaterThan(20);
  60 |   }
  61 | });
  62 | 
  63 | test("what the loop produced is shown with a real before and after", async ({ page }) => {
  64 |   await page.goto("/models");
  65 |   const text = await page.locator("main").innerText();
  66 |   expect(text).toMatch(/c-0045|adapter|harness/i);
  67 | });
  68 | 
  69 | test("the machines page shows measured hardware", async ({ page }) => {
  70 |   await page.goto("/machines");
  71 |   const text = await page.locator("main").innerText();
  72 |   expect(text).toMatch(/cuda|metal/i);
  73 | });
  74 | 
```