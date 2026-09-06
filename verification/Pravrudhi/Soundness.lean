/- Soundness properties of the boundary rule in `Basic.lean`. -/
import Pravrudhi.Basic

namespace Pravrudhi

/-- `decide` is total: it always lands on one of the three decisions. -/
theorem decide_total (obs : Observation) (t : Threshold) :
    decide obs t = Decision.promote ∨ decide obs t = Decision.prune ∨
      decide obs t = Decision.continue_ := by
  unfold decide
  split
  · exact Or.inl rfl
  · split
    · exact Or.inr (Or.inl rfl)
    · exact Or.inr (Or.inr rfl)

/-- `decide` is deterministic: the same observation and threshold always
    produce the same decision. Immediate from `decide` being a function;
    stated explicitly so the property is machine-checked rather than
    assumed. -/
theorem decide_deterministic (obs : Observation) (t : Threshold) (d1 d2 : Decision)
    (h1 : decide obs t = d1) (h2 : decide obs t = d2) : d1 = d2 := by
  rw [← h1, ← h2]

/-- A `promote` decision certifies that wins strictly exceeded losses. -/
theorem promote_implies_wins_gt_losses (obs : Observation) (t : Threshold)
    (h : decide obs t = Decision.promote) : obs.wins > obs.losses := by
  unfold decide at h
  split at h
  · rename_i hc
    omega
  · split at h
    · exact absurd h (by decide)
    · exact absurd h (by decide)

/-- Swapping wins and losses maps a `promote` decision to `prune` and
    vice versa: the rule treats the two candidates symmetrically. -/
theorem decide_antisymmetric (obs : Observation) (t : Threshold) :
    decide { obs with wins := obs.losses, losses := obs.wins } t
      = Decision.promote ↔ decide obs t = Decision.prune := by
  unfold decide
  constructor
  · intro h
    split at h
    · split
      · omega
      · rename_i hc1 hc2
        exact absurd h (by decide)
    · split at h
      · exact absurd h (by decide)
      · exact absurd h (by decide)
  · intro h
    split at h
    · exact absurd h (by decide)
    · split at h
      · rename_i hc1 hc2
        split
        · omega
        · exact absurd h (by decide)
      · exact absurd h (by decide)

/-- Adding a tie to an observation changes no decision: `decide` never
    inspects `ties`. -/
theorem decide_ignores_ties (obs : Observation) (t : Threshold) (extra : Nat) :
    decide { obs with ties := obs.ties + extra } t = decide obs t := rfl

end Pravrudhi
