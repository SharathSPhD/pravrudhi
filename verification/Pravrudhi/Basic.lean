/- Core types for the promotion boundary rule.

   `Observation` is a paired win/loss/tie count from comparing a candidate
   against the incumbent on shared items (see discordance.py: wins, losses,
   concordant). `decide` is the boundary rule itself: a margin comparison of
   wins against losses, total and deterministic by construction because it
   is a plain Lean function. Ties never enter the comparison — they are
   carried on `Observation` only so a certificate can state the full paired
   count it was computed from. -/
namespace Pravrudhi

/-- A paired comparison: candidate wins, candidate losses, and ties, all
    non-negative by construction. -/
structure Observation where
  wins : Nat
  losses : Nat
  ties : Nat
deriving DecidableEq, Repr

/-- The margin the boundary rule requires before it will move off `continue`. -/
structure Threshold where
  margin : Nat
deriving DecidableEq, Repr

/-- What the boundary rule can decide. -/
inductive Decision where
  | promote
  | prune
  | continue_
deriving DecidableEq, Repr

/-- The boundary rule: promote when wins clear losses by more than the
    margin, prune when losses clear wins by more than the margin, otherwise
    continue collecting evidence. -/
def decide (obs : Observation) (t : Threshold) : Decision :=
  if obs.wins > obs.losses + t.margin then
    Decision.promote
  else if obs.losses > obs.wins + t.margin then
    Decision.prune
  else
    Decision.continue_

end Pravrudhi
