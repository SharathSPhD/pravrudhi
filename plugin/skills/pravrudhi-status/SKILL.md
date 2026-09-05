---
name: pravrudhi-status
description: Report the state of a Pravrudhi project from its ledger. Use when the user asks how the loop is doing, what the current incumbent is, or whether the ledger is intact.
---

# Status

Run `uv run pravrudhi status --root .` and, if the user wants detail, `uv run pravrudhi replay --verify --root .`. Report chain integrity, event count, candidate badges, nights closed with GPU-hours spent, and the current incumbent. Every number you say must appear in that output.
