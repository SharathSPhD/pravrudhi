# Multi-Agent Coding / RSI Harness Research Brief
## Orca (onorca.dev) + Claude Code + Codex + OpenCode + Custom RSI Harness

**Prepared:** 5 September 2026  
**Purpose:** Hand this document to another agent for independent technical review, verification, and implementation planning.

---

## 1. Executive summary

The working recommendation is:

> Use **Orca as the execution/orchestration/worktree layer**, while building a **thin custom Python RSI/master controller above it**.

The target architecture is:

```text
                         YOUR RSI / MASTER HARNESS
                                  |
                 +----------------+----------------+
                 |                |                |
              Planner          Critic          Evaluator
                 |                |                |
                 +----------------+----------------+
                                  |
                           ORCA / WORKTREE LAYER
                                  |
              +-------------------+-------------------+
              |                   |                   |
         Claude Code            Codex             OpenCode
              |                   |                   |
         Claude Max         ChatGPT Plus/Pro       APIs/models
              |                   |
              +---------+---------+
                        |
                  isolated worktrees
                        |
                 tests / benchmarks
                        |
                   score results
                        |
                   merge / reject
                        |
                     iterate
```

The core idea is **heterogeneous agents competing/cooperating under an objective evaluator**, rather than simply running multiple copies of one coding agent.

Orca is not the model itself and is not intended to replace Claude Code or Codex. Its documented positioning is as an environment/orchestrator where users bring their own Claude, Codex, OpenCode, and other CLI agents.

---

# 2. User's original requirements/questions

The user wanted to know:

1. Review Orca at https://www.onorca.dev/
2. What similar tools/projects exist?
3. Can Claude Code and Codex run on the same Orca setup?
4. Can other/custom harnesses or CLI agents be used?
5. Can existing Claude Max and Codex/ChatGPT subscriptions be used?
6. Does Orca have its own subscription?
7. Which architecture is best for building an RSI / harness-of-harness system?
8. Compare Orca, OpenCode, Claude Code Agent Teams, and a custom harness.
9. Produce a detailed brief for another agent to independently review and continue the work.

---

# 3. Orca — current understanding

Website:

https://www.onorca.dev/

Orca is positioned as an **agent development environment / orchestration environment**, not a model provider.

Its important characteristics include:

- Multiple coding agents in one environment.
- Claude Code support.
- Codex support.
- OpenCode support.
- Support for many other CLI-based agents.
- Separate Git worktrees for tasks/agents.
- Parallel agent execution.
- Agent terminals/session management.
- Git/diff/review workflows.
- Browser/environment capabilities.
- Remote execution capabilities.
- Orca CLI.
- Cross-platform desktop application (documented for macOS, Windows, Linux).
- Bring-your-own agent/provider/subscription model.

The site's messaging includes the idea that users can "bring your own Claude, Codex, or OpenCode subscription" and that Orca is "not a model."

### Important interpretation

Orca should be thought of as:

```text
Execution environment
+ agent launcher
+ worktree manager
+ agent/session UI
+ orchestration substrate
```

rather than:

```text
LLM provider
```

---

# 4. Claude Code + Codex coexistence

Yes, the desired architecture is feasible.

The same overall repository/project can be exposed to multiple agents through **separate Git worktrees**.

Conceptually:

```text
                    Git repository
                         |
                        main
                         |
              +----------+----------+
              |          |          |
          WT-Claude  WT-Codex   WT-Other
              |          |          |
         Claude Code    Codex    Other agent
              |          |          |
            diff       diff       diff
              +----------+----------+
                         |
                   evaluate/review
                         |
                    merge/reject
```

This is preferable to allowing two agents to modify the exact same working tree simultaneously.

### Why worktrees matter

They provide:

- Isolation.
- Independent branches.
- Safe parallel experimentation.
- Easy comparison of diffs.
- Easy rollback/rejection.
- A natural mechanism for agent competition.

---

# 5. Claude Max subscription

Important distinction:

**Claude Max subscription != Anthropic API account.**

Claude Code can authenticate against a Claude subscription and use the subscription's included Claude Code usage.

For this proposed architecture, the preferred route is:

```text
Claude Max
    |
    v
Claude Code
    |
    v
Orca
```

rather than:

```text
Claude Max
    |
    v
OpenCode
    |
    v
Orca
```

Reason: OpenCode's provider documentation has indicated that use of Claude Pro/Max authentication through OpenCode is not officially supported by Anthropic, despite technical integrations existing.

Therefore, for the user's existing Claude Max subscription, **first-party Claude Code should be the preferred Claude execution path**.

The independent reviewing agent must re-check the current Anthropic terms/docs because this is a time-sensitive policy area.

---

# 6. Codex / ChatGPT subscription

OpenAI supports using Codex CLI with ChatGPT account authentication.

Conceptually:

```text
ChatGPT Plus/Pro
       |
       v
     Codex CLI
       |
       v
      Orca
```

The important distinction is again:

```text
ChatGPT subscription
       !=
OpenAI API billing
```

Using Codex through the supported ChatGPT/Codex subscription path can consume included plan usage rather than automatically requiring API credits.

However:

- Plan-specific limits apply.
- Usage limits can change.
- Additional usage/credits may be available depending on the current OpenAI plan/product rules.
- Exact current limits should be independently verified before implementation.

---

# 7. Does Orca have its own subscription?

Current understanding from the Orca documentation:

**Orca itself is free/open source rather than being another model subscription.**

Its documented model is effectively:

```text
Orca = orchestration/environment
Claude = your Claude subscription
Codex = your OpenAI/ChatGPT subscription
Other models = their respective provider/API/subscription
```

Therefore the proposed initial stack can be:

```text
Orca
+
Claude Max
+
ChatGPT Plus/Pro
```

without adding an Orca model subscription.

The reviewing agent should verify the latest licensing/pricing page before treating this as permanent.

---

# 8. Other similar systems worth evaluating

## 8.1 OpenCode

OpenCode is an open-source coding-agent environment/provider abstraction.

Strengths:

- Open source.
- Multiple model providers.
- Configurable agents.
- MCP support.
- Plugins.
- Broad model/provider ecosystem.
- Strong automation potential.

Weakness for this specific setup:

- It introduces an abstraction between the user and first-party Claude Code/Codex.
- Claude Max subscription usage through OpenCode is not the preferred official route.
- It is therefore better viewed as another agent/runtime that Orca can manage rather than necessarily the top-level controller.

Recommended position:

```text
Orca
 |
 +-- Claude Code
 +-- Codex
 +-- OpenCode
```

rather than:

```text
Orca
 |
 +-- OpenCode
       |
       +-- Claude
       +-- GPT
       +-- Gemini
```

---

# 8.2 Claude Code Agent Teams / native multi-agent capabilities

Claude Code is increasingly capable of multi-agent/subagent workflows.

Advantages:

- First-party Claude integration.
- Strong Claude-native tooling.
- Low configuration overhead.
- Good for Claude-centric tasks.

Disadvantages for the user's objective:

- It is primarily Claude-centric.
- The user's objective is heterogeneous agent competition/cooperation.
- Codex/Gemini/local models should be first-class participants.
- Therefore Claude Code should be an agent inside the larger architecture, not necessarily the master controller.

---

# 8.3 Codex subagents

Codex itself supports increasingly sophisticated subagent/task orchestration.

Advantages:

- First-party OpenAI ecosystem.
- Parallel work.
- Subagent/task delegation.
- Worktree-oriented workflows.

Again, for the user's objective, Codex is best treated as one strong agent/harness inside the broader system rather than the universal controller.

---

# 8.4 Custom Python harness

Maximum flexibility.

Potential components:

```text
rsi-harness/
|
+-- controller/
|   +-- planner.py
|   +-- router.py
|   +-- evaluator.py
|   +-- critic.py
|   +-- memory.py
|
+-- agents/
|   +-- claude.py
|   +-- codex.py
|   +-- gemini.py
|   +-- local.py
|
+-- evaluation/
|   +-- tests.py
|   +-- benchmark.py
|   +-- scoring.py
|
+-- memory/
|   +-- failures/
|   +-- successful_patterns/
|   +-- strategies/
|
+-- config.yaml
```

Advantages:

- Complete control.
- Arbitrary agents.
- Arbitrary routing.
- Objective evaluation.
- Self-improvement loops.
- Custom memory.
- Research experimentation.

Disadvantages:

- Must build process management.
- Must build worktree management unless delegating to Orca.
- Must build agent lifecycle management.
- Must build monitoring.
- Must handle failures/timeouts.
- More engineering.

Therefore:

> Do not rebuild everything if Orca can be used as the execution substrate.

---

# 9. Recommended architecture

## Layer 1 — Models

Examples:

- Claude Opus/Sonnet through Claude Code.
- GPT/Codex through Codex.
- Gemini through an appropriate agent.
- Qwen/local models.
- Other specialized models.

## Layer 2 — Agents

Examples:

- Claude Code.
- Codex.
- OpenCode.
- Gemini CLI.
- Other CLI agents.
- User's own Python agent.

## Layer 3 — Orca

Responsible for:

- Worktrees.
- Agent terminals.
- Session lifecycle.
- Parallel execution.
- Git integration.
- Agent environment.
- Potential remote execution.
- Human supervision.

## Layer 4 — RSI/master harness

Responsible for:

- Goal definition.
- Task decomposition.
- Agent selection.
- Parallelization.
- Critique.
- Evaluation.
- Scoring.
- Retry.
- Strategy selection.
- Memory.
- Iteration.
- Potential self-modification.

---

# 10. Proposed RSI control loop

A first implementation could be:

```text
                    USER GOAL
                       |
                       v
                    PLANNER
                       |
                       v
                TASK DECOMPOSER
                       |
          +------------+------------+
          |            |            |
          v            v            v
       Claude        Codex       Other
          |            |            |
          v            v            v
      worktree      worktree     worktree
          |            |            |
          +------------+------------+
                       |
                       v
                  TEST SUITE
                       |
                       v
                OBJECTIVE METRICS
                       |
                       v
                    CRITIC
                       |
                       v
                   SCORER
                       |
                +------+------+
                |             |
              winner       failure
                |             |
                v             v
              merge       revise/retry
                |             |
                +------+------+
                       |
                       v
                   MEMORY
                       |
                       v
                 NEXT ITERATION
```

---

# 11. Critical design principle: objective evaluation

Do not rely solely on an LLM to decide which agent's answer is best.

Prefer:

```text
Agent A
   |
   +--> tests
   +--> benchmark
   +--> lint/type checks
   +--> performance
   +--> reproducibility
   |
Agent B
   |
   +--> same objective evaluation
   |
Agent C
   |
   +--> same objective evaluation
   |
   v
Objective score
   |
   v
LLM critic
   |
   v
Final selection
```

The evaluator should be as deterministic/objective as possible.

For research projects, this could include:

- Unit tests.
- Statistical tests.
- Benchmark metrics.
- Reproducibility.
- Runtime.
- Memory.
- Accuracy.
- Scientific consistency checks.
- Ablation results.
- Code quality.
- Documentation completeness.

---

# 12. Why this is relevant to RSI

The user's broader interest is recursive/self-improving LLM/harness systems.

The distinction is:

### Ordinary coding agent

```text
prompt -> agent -> code
```

### Multi-agent system

```text
prompt -> agents -> code
```

### Harness-of-harnesses

```text
goal
 |
 +--> Claude harness
 +--> Codex harness
 +--> OpenCode harness
 +--> custom agents
 |
 v
evaluation
 |
 v
select/revise
```

### RSI-oriented system

```text
goal
 |
 v
plan
 |
 v
generate strategies
 |
 v
run heterogeneous agents
 |
 v
evaluate
 |
 v
learn which strategies work
 |
 v
modify orchestration strategy
 |
 v
repeat
```

The fourth architecture is the user's actual target.

---

# 13. Orca's role in RSI

Orca should NOT own the intelligence of the RSI system.

Instead:

```text
                RSI controller
                     |
                     v
                    Orca
             /       |               Claude     Codex    Other
```

Orca becomes infrastructure.

This is desirable because if Orca changes or disappears:

```text
RSI controller
     |
     +-- Orca adapter
     +-- direct Claude adapter
     +-- direct Codex adapter
     +-- direct OpenCode adapter
```

can preserve portability.

Therefore the custom controller should maintain a provider-neutral internal representation.

---

# 14. Suggested internal interface

Define a generic agent interface such as:

```python
class Agent:
    name: str

    def create_workspace(self, task):
        ...

    def run(self, prompt, workspace):
        ...

    def status(self):
        ...

    def collect_changes(self):
        ...

    def stop(self):
        ...
```

Then implement:

```text
ClaudeCodeAgent
CodexAgent
OpenCodeAgent
GeminiAgent
LocalAgent
OrcaAgent
```

Potentially Orca itself can become an adapter:

```text
RSI Controller
      |
 Agent interface
      |
 Orca adapter
      |
 +----+---------+
 |              |
Claude        Codex
```

This avoids hard-coding the RSI logic to Orca.

---

# 15. Suggested task representation

Use structured tasks:

```yaml
id: task-001
goal: "Improve activation patching experiment"
parent: research-001

constraints:
  language: python
  tests_required: true
  preserve_api: true

agents:
  - claude
  - codex
  - gemini

evaluation:
  - unit_tests
  - benchmark
  - statistical_validation

max_iterations: 5
```

Each agent returns:

```yaml
status: completed
commit: abc123
tests:
  passed: 42
  failed: 0

metrics:
  accuracy: 0.91
  runtime_seconds: 23

summary: ...
known_risks:
  - ...
```

---

# 16. Parallel-agent strategy

For difficult tasks, don't necessarily ask every agent to solve the same thing.

Possible modes:

## Competition

```text
same task -> Claude
          -> Codex
          -> Gemini
             |
             v
          compare
```

Best for discovering alternative implementations.

## Specialization

```text
Claude -> architecture
Codex  -> implementation
Gemini -> critique
Local  -> tests
```

Best when roles can be separated.

## Sequential refinement

```text
Claude -> initial solution
   |
Codex -> review/refactor
   |
Gemini -> critique
   |
Claude -> final revision
```

Best for complex research/code.

## Evolutionary

```text
Population of solutions
        |
      tests
        |
      ranking
        |
    mutate/revise
        |
      repeat
```

This is particularly relevant to RSI.

---

# 17. Potential research experiment

A strong first experiment would be to test whether heterogeneous agents actually outperform a single strong agent.

For a fixed benchmark:

```text
Baseline A:
Claude only

Baseline B:
Codex only

Baseline C:
Claude + self-review

System D:
Claude + Codex competition

System E:
Claude + Codex + Gemini

System F:
Claude + Codex + evaluator + iterative refinement

System G:
Full RSI controller
```

Measure:

- Pass rate.
- Number of iterations.
- Cost.
- Wall-clock time.
- Human intervention.
- Regression rate.
- Solution quality.
- Reproducibility.

This would give empirical evidence for whether the harness is genuinely improving performance.

---

# 18. Cost model

The desired initial model is:

```text
Orca                     = free/open source
Claude Code              = Claude Max subscription
Codex                    = ChatGPT Plus/Pro subscription
Other APIs               = optional
Local models             = hardware cost only
```

However, the exact included usage and terms should be rechecked at implementation time.

Do not assume:

```text
subscription = unlimited autonomous use
```

A large autonomous RSI loop can consume included quotas quickly.

Potential future architecture:

```text
cheap/local model
     |
     +-- planning
     +-- routing
     +-- simple critique

premium Claude/Codex
     |
     +-- difficult reasoning
     +-- final implementation
     +-- difficult debugging

objective evaluator
     |
     +-- deterministic validation
```

This could significantly reduce subscription/API consumption.

---

# 19. Important subscription/compliance issue

The independent reviewer must verify the current terms for:

### Anthropic

- Claude Max + Claude Code usage.
- Agent SDK subscription authentication.
- Third-party orchestration.
- Automation limits.
- Whether unattended use is permitted.
- Current subscription terms.

### OpenAI

- ChatGPT subscription + Codex CLI.
- Codex CLI automation.
- Included usage.
- Additional credits.
- Rate/usage limits.
- Terms for autonomous agent workloads.

### OpenCode

- Current provider authentication rules.
- Whether subscription authentication is officially supported by the upstream provider.

These policies are changing rapidly and should not be inferred from old documentation.

---

# 20. Remote execution

Orca documents remote agent/server functionality.

This may be useful for the user's existing compute environment.

Potential topology:

```text
Laptop/Desktop
      |
     Orca
      |
+-----+------------------+
|                        |
local agents        remote machine
                         |
                    local models
                    GPU workloads
```

The RSI controller could remain on one machine while computationally expensive agents/models execute remotely.

This should be tested experimentally rather than assumed to work for every agent.

---

# 21. Recommended implementation phases

## Phase 0 — verify current APIs

Before coding:

- Verify Orca repository and license.
- Verify Orca CLI/API.
- Verify supported agent list.
- Verify worktree commands.
- Verify remote execution.
- Verify Claude integration.
- Verify Codex integration.
- Verify current subscription authentication rules.

## Phase 1 — manual multi-agent experiment

Install:

```text
Orca
Claude Code
Codex
```

Create one repository.

Run the same task through both.

Compare:

- setup friction
- worktrees
- diffs
- agent output
- resource use
- subscription consumption

## Phase 2 — simple controller

Build:

```text
Python
  |
Orca/agent adapter
  |
Claude + Codex
  |
test
  |
choose winner
```

No self-modification yet.

## Phase 3 — evaluator

Add:

- objective tests
- scoring
- automatic comparison
- retry

## Phase 4 — memory

Store:

- successful strategies
- failures
- agent performance
- task classes
- routing decisions

## Phase 5 — adaptive routing

Learn:

```text
task type -> agent most likely to succeed
```

## Phase 6 — recursive improvement

Allow the harness to propose changes to:

- planner
- routing policy
- prompts
- evaluator
- retry policy
- agent allocation

But require tests and rollback.

---

# 22. Safety/control architecture for self-improvement

A fully autonomous RSI system should not be allowed to freely modify its own controller and deploy changes without validation.

Use:

```text
current harness
       |
       v
proposed modification
       |
       v
isolated worktree
       |
       v
test harness
       |
       v
benchmark
       |
       v
compare against baseline
       |
    +--+--+
    |     |
  better  worse
    |     |
 accept  reject
```

Maintain:

- Versioned controller.
- Git commits.
- Reproducible benchmarks.
- Rollback.
- Human approval for major architecture changes.
- Resource/time budgets.

---

# 23. Preliminary comparison

| Capability | Orca | OpenCode | Claude Code Teams | Custom Harness |
|---|---|---|---|---|
| Claude Code | Excellent | Via integration/alternative route | Native | Yes |
| Codex | Excellent | Supported ecosystem | No | Yes |
| Other agents | Excellent | Excellent | Limited | Unlimited |
| Parallel agents | Excellent | Good | Excellent | Yes |
| Git worktrees | Native | Good | Good | Build/use tool |
| Agent UI | Excellent | Good | Excellent | Build |
| Diff comparison | Excellent | Good | Good | Build |
| Remote execution | Yes/documented | Depends | Depends | Build |
| Subscription integration | Strong | Provider-dependent | Claude-focused | Build |
| Custom orchestration | Good | Good | Limited | Excellent |
| RSI experimentation | Good substrate | Good substrate | Less suitable | Excellent |
| Engineering effort | Low | Low | Very low | High |

This table is a working assessment and must be revalidated against current versions.

---

# 24. Preliminary ranking for the user's use case

### 1. Orca + custom RSI controller

Best balance.

Reason:

- Reuses worktree/session infrastructure.
- Supports Claude + Codex.
- Allows heterogeneous agents.
- Keeps RSI logic independent.
- Low initial engineering effort.

### 2. Custom harness directly on Claude Code + Codex

Best for maximum control, but substantially more work.

### 3. OpenCode as central environment

Very capable, especially if model/provider abstraction is the priority.

But not ideal as the primary route for Claude Max because of the subscription/provider support distinction.

### 4. Claude Code Agent Teams alone

Strong Claude-centric option, but too narrow for a heterogeneous RSI system.

---

# 25. Key technical question for the next agent

The most important unresolved question is:

> **How programmable is Orca from an external master controller?**

The reviewing agent should determine exactly:

1. Is there a stable CLI API?
2. Can external programs create worktrees?
3. Can external programs launch agents?
4. Can external programs send prompts?
5. Can external programs read agent status?
6. Can external programs retrieve output?
7. Can external programs stop/restart agents?
8. Can external programs access Git/diffs?
9. Can the controller run without the GUI?
10. Can Orca be used headlessly?
11. Can arbitrary CLI agents be registered programmatically?
12. Can agents be run remotely?
13. What IPC/API does Orca expose?
14. Is there an SDK?
15. Is the CLI stable enough for production automation?
16. Can an external process subscribe to agent lifecycle events?

If these answers are strong, Orca is an excellent execution substrate for the RSI controller.

---

# 26. Key technical question about Claude

Verify:

```text
Claude Max
    |
Claude Code
    |
external orchestrator/Orca
```

Specifically:

- Is this officially permitted?
- What automation limits apply?
- Does launching Claude Code through Orca change anything?
- Does Claude Code Agent SDK offer a supported subscription-auth path?
- What happens when subscription limits are reached?

---

# 27. Key technical question about Codex

Verify:

```text
ChatGPT Plus/Pro
      |
   Codex CLI
      |
     Orca
```

Specifically:

- Current supported login mechanism.
- Current included usage.
- Automation limitations.
- Rate limits.
- Additional credit rules.
- Whether Orca's invocation changes account usage classification.

---

# 28. Important conclusion

The strongest architectural insight is:

> **Do not choose between Claude Code and Codex. Put them beside each other.**

And:

> **Do not make Orca the RSI brain. Make it the infrastructure layer.**

The desired system is:

```text
                     RSI MASTER
                         |
              +----------+----------+
              |          |          |
           planner     critic    evaluator
                         |
                         v
                        ORCA
                  /      |                       /       |                 Claude Code  Codex   Other agents
              |          |          |
          Claude Max  ChatGPT     APIs/local
              |          |          |
              +----------+----------+
                         |
                    worktrees
                         |
                    benchmarks
                         |
                      scoring
                         |
                     memory
                         |
                     iterate
```

This allows the user to leverage existing Claude Max and ChatGPT/Codex subscriptions while retaining the ability to add other models and a custom RSI layer.

---

# 29. References to verify

Primary sources that should be checked during the next research pass:

### Orca
https://www.onorca.dev/

### Orca documentation
https://www.onorca.dev/docs

### OpenCode
https://opencode.ai/

### OpenCode provider documentation
https://opencode.ai/docs/providers/

### Anthropic Claude Code
https://docs.anthropic.com/

### OpenAI Codex
https://developers.openai.com/codex/

### OpenAI Codex help
https://help.openai.com/

### Orca GitHub
Identify and verify the official repository from the Orca website rather than assuming a third-party repository.

---

# 30. Deliverable requested from the next agent

Perform an **independent current technical review** of this architecture.

Do not simply accept the conclusions above.

Specifically produce:

1. Exact current Orca architecture.
2. Official Orca GitHub repository.
3. License.
4. Current pricing/business model.
5. Current supported agents.
6. Exact Orca CLI/API capabilities.
7. Whether Orca can be controlled programmatically/headlessly.
8. Exact Claude Max integration path.
9. Exact Codex/ChatGPT subscription integration path.
10. Current subscription/automation restrictions.
11. Orca vs OpenCode comparison.
12. Orca vs Claude Code Agent Teams.
13. Orca vs Codex native orchestration.
14. Existing open-source "harness-of-harness" projects.
15. Existing RSI/self-improving coding-agent projects.
16. Recommended implementation architecture.
17. Minimal proof-of-concept code structure.
18. Whether Orca should be used at all for the proposed RSI project.
19. Alternative architecture if Orca's API is insufficient.
20. Estimated implementation complexity.
21. Recommended first experiment.

Use current primary documentation wherever possible, and explicitly flag anything that cannot be verified.

---

## Bottom line

**Working hypothesis:**

```text
Orca = excellent multi-agent execution/worktree layer
Claude Code = first-party Claude agent
Codex = first-party OpenAI coding agent
OpenCode = useful additional provider/agent layer
Custom Python controller = RSI/master intelligence
Objective evaluator = mechanism that determines whether improvement actually occurred
```

The next agent should now **verify rather than assume** this architecture, especially the exact Orca CLI/API and current Claude/OpenAI subscription terms.
