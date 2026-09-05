---
name: pravrudhi-inbox
description: Review what a Pravrudhi night wants promoted and record the operator's decision. Use when the user asks what improved, wants to approve or reject a promotion, or asks about the inbox.
---

# Review the inbox

1. `uv run pravrudhi inbox --root .` lists packs with the replayed badge (green = promoted and not since pruned; red = pruned or audited) and whether they are signed.
2. Open `<pack>/README.md` for the recipe, the paired delta, and the canary results. Cross-check the candidate's rows with `uv run pravrudhi serve` → `GET /candidates/<id>` if the user wants the raw evidence.
3. Only the operator decides. Record the decision as the operator, never as yourself: `curl -X POST localhost:8765/inbox/sign -H 'X-Pravrudhi-Operator: <operator name>' -d '{"pack":"<pack>","decision":"approve|reject|defer","note":"..."}'` while `pravrudhi serve` runs, or `uv run pravrudhi gate sign` for phase gates. The API refuses agent identities.
