#!/usr/bin/env bash
# scripts/ralph/loop.sh L<N> — open (or resume) the worktree for one contract card and print the loop steps.
set -euo pipefail
CARD="${1:?usage: loop.sh L<N>}"
ROOT="$(git rev-parse --show-toplevel)"
WT="$ROOT/.worktrees/$CARD"
BR="loop/$CARD"
if [[ ! -d "$WT" ]]; then
  git -C "$ROOT" worktree add "$WT" -b "$BR" main
fi
CARDFILE="$(ls "$ROOT"/contracts/"$CARD"_*.md 2>/dev/null | head -1 || true)"
cat <<EOT
worktree: $WT  branch: $BR  card: ${CARDFILE:-<missing>}
1 read the card; restate domain_gate in one sentence
2 PLAN.md in the worktree (deleted before merge)
3 build with TDD in the worktree
4 make smoke + the card's tests
5 validate at tier; state measure_class
6 pravrudhi gate emit $CARD --evidence gates/$CARD.evidence.yaml && pravrudhi gate check gates/gate_$CARD.json
7 journal entry + docs/spec.md evolution line + HANDOFF §7
8 buddhi checklist, then: git merge --squash $BR ; commit "$CARD: <title> [gate:<status>]" ; git worktree remove $WT
completion promise: gate JSON exists, gate check passes, make smoke green
EOT
