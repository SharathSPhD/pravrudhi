---
name: pravrudhi-export
description: Export the promoted adapter (or harness diff) from a Pravrudhi project. Use when the user wants to use, ship, or share what the loop improved.
---

# Export

`uv run pravrudhi export <dest> --root .` copies the green adapter and writes `pravrudhi_export.json` with the candidate id, ledger head and adapter hash. Export refuses anything that is not green. Merging the adapter into base weights is not done by the loop; if the user wants a merged checkpoint, do it explicitly with PEFT after the operator has signed the gate, and say so.
