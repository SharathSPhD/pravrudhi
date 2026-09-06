# Adversarial Review: Pravrudhi — Whole-Project Audit

**Reviewer role**: Adversarial, external to the builder's reasoning; evaluated against the project's own CHARTER.md, PRD.md, ROADMAP.md and prior gate evidence, not against aspiration.

**Date**: 2026-09-06

**Scope**: Four questions posed by the operator — (a) has pravrudhi met or exceeded DGM/HGM/GEAR/R-Zero-class baselines on measurable terms; (b) is the "installable desktop/web app anyone can download and adapt to their own objective" goal met; (c) how substantively has it leveraged prayoga/prabodha/MIabstraction/pramana/pranava; (d) is it still a raw scaffold with no demonstrated substance. Findings below are drawn from direct code/test/evidence inspection, not from the project's own narrative documents alone.

---

## Verdict at a glance

| Question | Verdict |
|---|---|
| (a) Beats DGM/HGM/GEAR/R-Zero/Agent0 on measurable terms | **No.** No head-to-head comparison against any of these systems has ever been executed. They appear only as literature framing. |
| (b) Installable desktop/web product like Claude Code Desktop / Orca | **Not met.** Researcher-grade CLI + Docker + NVIDIA GPU stack; no packaging; objectives gated behind pre-registered benchmarks; objective→execution wiring is an open roadmap item. |
| (c) Leverages prayoga/prabodha/MIabstraction/pramana/pranava | **Mixed, genuinely split.** Two statistics modules are literal vendored/ported code with parity-fixture tests. The six-layer closure contract is a faithful structural port of a *different*, real sibling project (prabhasa-samskrutam, not the four named). Everything else is vocabulary/pattern borrowing, which CHARTER.md itself discloses. |
| (d) Raw scaffold, no substance | **No — the engine layer is real; the evidence-approval layer is not independently verifiable here, and by the project's own numbers nothing has cleared confirm tier yet.** |

None of these four answers is a clean "yes" or "no" in the way a promotional summary would prefer. The most important thing this review can hand back is: **the code that runs is real; the claims that have been approved by gates are not yet independently checkable, and the external-beat claims have not been attempted.** Those are three different failure surfaces and should not be collapsed into one verdict.

---

## (a) Beating the pre-registered baselines (DGM / HGM / GEAR / R-Zero / Agent0 / SEAL / Bilevel)

CHARTER.md §2 pre-registers eight hypotheses (H1–H8), each with a phase gate and numeric kill criterion, specifically so that "beat SOTA" claims would be falsifiable rather than asserted. The actual state of each, from `docs/evidence/*.md` (the only evidence tracked in this worktree — `gates/`/`contracts/`/`research/` are gitignored and not independently checkable here):

| H | Status | Evidence |
|---|---|---|
| H1 (EFE controller vs greedy / GEAR-like / HGM-like) | Screen-tier only. No GEAR-like or HGM-like arm exists in the ledger at all. `H1_lora_7_8.md` / `_9_10.md`: EFE-vs-greedy only, cross-night, unpaired, and the file states its own target effect size is "not usable." `H1_harness_3_4_5_6.md` is titled by its own author **"VOID — this is not a comparison"** because the EFE arm never executed. |
| H2 (epistemic term ablation) | Not confirmed. Night 5 ends flagged `kind=decorative_controller` — the controller was flagged as *possibly decorative*, the opposite of a positive result. |
| H3 (sequential gating, needs n≥200 planted-null A/A trials) | Not run at required scale. `L4_night1.md`: `shares.planted 0.0` — zero planted nulls executed. |
| H4 (anti-gaming red-team battery) | No evidence file exists. |
| H5 (transfer across model tiers) | No evidence file exists. |
| H6 (interp sensors) | Screen only — the filename says so (`H6_sensor_screen.md`). |
| H7 (LoRA weight-level vs R-Zero/Agent0) | One real result exists — a single LoRA candidate (c-0045) with an externally-verified +0.081 exact-match gain on GSM8K over its *own unmodified base model*, at single seed, 400-item confirmation giving paired permutation p=0.111 ("not on its own a detection"). R-Zero and Agent0 are **never named or run as a comparison baseline anywhere in the repo.** No 10-iteration non-plateau/canary study exists. |
| H8 (prabhasa closure conversion rate) | No evidence file exists. |

The paper draft is candid about this: `paper/sections/limitations.tex` self-reports single-benchmark scope, container-not-process isolation, an unpinned stack, GRPO narrowed to fp32/group≤4 with "no claim comparable to published GRPO results," and single loop seed at screen tier. `results.tex` reports exactly one confirmed external gain and one promoted-then-**withdrawn** harness candidate that collapsed on external HumanEval+ (0.591 → 0.085) — framed honestly as a negative result illustrating evaluator-gaming risk, not a win.

**Direct answer**: no head-to-head against GEAR, HGM, R-Zero, or Agent0 has been attempted, let alone won. The project's own tier discipline (screen vs confirm) is being followed honestly — nothing here is being oversold internally — but that also means the "goes head-to-head with 2026 SOTA" framing in CHARTER.md's mission statement is, as of this repo state, entirely aspirational. The one real, externally-verified number (+0.081 GSM8K, single seed) is a legitimate before/after result on the project's own trainee, not a beat of any named competitor.

---

## (b) The installable desktop/web app goal

Compared against the bar implied by "like Claude Code Desktop, Orca ADE" — one-command install, no required GPU/Docker, immediately usable on any user-stated goal with no pre-registered benchmark:

- **No packaging of any kind.** `app/frontend` is a Next.js dev-server web UI (`npm ci && npm run build`, then served by the Python engine via `pravrudhi app`), not an Electron/Tauri desktop bundle. There is no installer.
- **The documented path requires Linux + Docker + NVIDIA runtime + manual model downloads.** README's quickstart is explicit about this (`hf download Qwen/...`, `docker pull ghcr.io/ggml-org/llama.cpp:server-cuda`). There is no CPU-only or low-resource fallback.
- **Objectives are not free-form.** `src/pravrudhi/application/objectives.py` refuses to create an objective without a declared benchmark ("an unmeasurable goal is a wish, not an objective"). A user adapts their intent to the system's measurement machinery, not the reverse — the opposite of "state any goal and go."
- **The project's own docs already concede this scope.** `docs/PRD.md` non-goals: "Desktop packaging, shared multi-user engine operation and billing are outside the current release scope." `docs/ROADMAP.md` lists "connect objective selection to execution" as unfinished future work, and repeats "desktop packaging... have no commitment" under Undecided.
- **The Claude Code plugin (`plugin/`) is real but narrow** — four skills wrapping existing CLI subcommands (status/inbox/night/export), not a general-purpose agent.
- **Auth/hosting is real schema, deliberately inert by default.** Supabase-backed multi-user identity exists and is opt-in only; the public "hosted site" is explicitly a recording of past runs, not a live account-based service.

**Direct answer**: not met, and the project's own PRD is honest that it isn't a current goal. This is presently a researcher-grade CLI/API engine with a local dashboard, not a consumer product. If the operator's actual intent is parity with Claude Code Desktop / Orca, that is a different roadmap than what PRD.md and ROADMAP.md currently commit to, and the gap should be treated as a scoping decision to make explicitly, not a bug to silently close.

---

## (c) Leverage of prayoga / prabodha / MIabstraction / pramana / pranava

This is the most nuanced of the four findings — the answer is genuinely split by module, not uniform in either direction, and CHARTER.md itself flags the distinction (§1, C17: "the Sanskrit vocabulary is a naming and audit discipline inherited from the portfolio, not a claim in itself").

- **prayoga → REUSED-IN-CODE.** `pravrudhi_kernel/stats/label_shuffle.py` is docstringed "Ported from prayoga.shared.metrics.label_shuffle_null" and is checked against the real prayoga module via committed parity fixtures (`tests/parity/gen_fixtures.py`, `fixtures/label_shuffle_null.json`). This is real, verifiable reuse, not a naming gesture.
- **prabodha → REUSED-IN-CODE (statistics) + PATTERN-ADAPTED (closure).** `stats/core.py` states "Vendored verbatim from prabodha.stats.core (house rule: never a third statistics library)," also parity-fixture tested. Separately, prabodha's own closure contract is *thinner* than pravrudhi's six-layer `ClosureReport` — that six-layer shape actually traces to **prabhasa-samskrutam**, a different sibling project, not to prabodha. CHARTER §5's citation ("inherited from PSALM/prabhasa-samskrutam") is the accurate one here.
- **MIabstraction → NAME-ONLY-BORROWED.** Pravrudhi's "Loom" (`src/pravrudhi/application/loom.py`) is a from-scratch parser for a harness-scheduling DSL that lowers `IntentPlanProposal` objects. MIabstraction's `LOOM.md` describes an unrelated layered *model-building* compiler. No shared code; only the name and a general layered-IR aesthetic carry over.
- **pramana → PATTERN-ADAPTED-NOT-CODE-SHARED.** No `stats`/`closure`/`label_shuffle` files exist in pramana matching pravrudhi's. The Nyāya six-phase vocabulary (Saṃśaya/Pramāṇa/Pañca-avayava/Tarka/Hetvābhāsa/Nirṇaya) is prose-level shared discipline — `Hetvābhāsa` even appears as a literal field name in `gate_report.py` — but there is no vendored module.
- **pranava → PATTERN-ADAPTED-NOT-CODE-SHARED,** and itself only claims to reuse prabodha/pramana by prose assertion, with the same caveat applying transitively.
- **prabhasa-samskrutam (not one of the four named, but the actual source of the closure contract and the explicit "first product use" target) exists and is active** on this machine, with real ADRs and tests. Pravrudhi's `proposals/prabhasa-nyaya/` tree — baseline-evaluation, candidate-evaluation, corpus, finetune, retrieval, RL — is ~3,200 lines of real, non-trivial Python (LoRA SFT, GRPO RL, hybrid retrieval, ILDC/ILTUR legal-benchmark evaluators), aimed concretely at that target domain. This is the strongest evidence that the "first product use" framing in CHARTER.md is a real, existing target rather than vaporware.

**Direct answer**: the leverage is real where it's claimed to be vendored (two statistics modules, checked by parity tests) and structurally derived where it's claimed to be a contract pattern (closure/gate shape, from prabhasa-samskrutam specifically, not the four names as listed). Everything else — most of the Sanskrit epistemic vocabulary, the "Loom" name, pramana/pranava's apparatus — is conceptual framing carried by naming discipline and prose, not shared code. This is not concealment; CHARTER.md discloses the distinction. But a reader taking "darśana-derived epistemology inherited from the portfolio" at face value would overestimate how much of the actual engine is portfolio-derived versus independently written for this project.

---

## (d) Is it still a raw scaffold with no substance?

**No, not at the engine layer — but the evidence-approval layer cannot be independently verified from this worktree, which is itself a finding.**

- **Real, tested, working code**: the hash-chained ledger (SHA-256 chain, `fcntl`-locked concurrent-writer resync per ADR-0013), the variance-adaptive Gaussian-mixture sequential e-process (with a documented overflow guard, ADR-0017), the EFE softmax/knapsack selection, the night orchestrator's real deliberation→selection→train→evaluate→close loop calling a real local llama.cpp or remote OpenAI-compatible endpoint (no mocking in the production path), the Docker-sandboxed execution with `--network none` isolation and live VRAM polling, and the harness track's genuine `evalplus`-based hidden-test scoring. 907 tests pass repo-wide; zero TODO/FIXME/NotImplementedError hits inside `src/pravrudhi` or `pravrudhi_kernel` (the only three such hits anywhere are in the unrelated `proposals/prabhasa-nyaya/` tree). This is not a scaffold in the pejorative sense — it is a legitimately engineered evaluator kernel and orchestrator.
- **Not independently verifiable here**: `gates/`, `contracts/`, and `research/` (which hold the actual gate JSONs and the ledger itself) are gitignored and untracked in this worktree — they exist only on the operator's main checkout. The prior in-repo adversarial review (`docs/evidence/review_L4_adversarial.md`) already found that every substantive numeric claim in `gate_L4.json` lacked a file path or re-derivable command, an "ACCEPT-WITH-FIXES" verdict with 11 blocking findings that, as far as this review can tell, remain open. By contrast, the tracked `docs/evidence/L4_summary.json` *does* cite concrete traceable artifacts (ledger sequence ranges, SHA-256 prereg hashes, non-round statistics), suggesting the summary documents are more faithfully ledger-derived than the gate prose that approved them.
- **Net effect**: "the kernel works" and "the gates that approved past nights were rigorously evidenced" are two separate claims. The first is substantiated by direct inspection. The second remains open, and the honest state — by the project's own tier discipline — is that nothing has cleared confirm tier: H1/H2/H6 are screen-only or null, H3/H4/H5/H8 have no evidence at all, and the one solid external result (H7's GSM8K gain) is single-seed with an explicitly non-decisive statistical test.

---

## What this review recommends checking next (not itself a finding)

1. Bring `gates/`, `contracts/`, and `research/ledger.jsonl` under version control (or a separate audited mirror) so gate evidence can be re-derived by someone who isn't the operator's own main checkout — the single biggest blocker to trusting any "pass" verdict.
2. Resolve the 11 blocking findings in `docs/evidence/review_L4_adversarial.md` before treating any L4-derived claim (including the H7 LoRA result) as confirm-tier.
3. Decide explicitly whether "installable desktop app like Claude Code Desktop" is actually in scope — right now PRD.md and ROADMAP.md say it isn't, which is internally consistent but may not match the operator's stated ambition; that's a scoping conversation, not an engineering gap.
4. If a DGM/HGM/GEAR/R-Zero head-to-head is a real near-term goal, it needs its own contract and gate — none of the eight existing hypotheses currently produce one, and P0's own precondition (deriving Δ* from the pilot) gates every confirm-tier claim that would follow.
