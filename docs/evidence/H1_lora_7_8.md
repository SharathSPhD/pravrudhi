# H1 screen: selection arms on lora nights 7, 8

Rendered from the ledger alone. Arms differ in selection only: pairing, the sequential boundary, the canaries and every row shape are identical across arms.

| arm | nights | proposed | selected | paired evals | mean Δ | best Δ | promoted | pruned | GPU-h | Δ per GPU-h |
|---|---|---|---|---|---|---|---|---|---|---|
| efe | 7 | 8 | 11 | 11 | -0.0305 | +0.0150 | 0 | 8 | 0.637 | +0.0235 |
| greedy | 8 | 8 | 12 | 12 | -0.0287 | +0.0450 | 0 | 8 | 0.685 | +0.0657 |

Δ\* (60th percentile of the greedy arm's gain distribution, CHARTER §2 H1, n=12): -0.0350.

**Δ\* is not usable on these nights.** It is defined from the greedy arm's gain distribution, and that distribution is centred below zero here because most candidates lose to the incumbent. A non-positive target is reached by proposing nothing, so regret-to-Δ\* cannot be computed and no claim about reaching it is made. Δ\* is meaningful while the incumbent is still weak; once it is strong the comparison needs a target defined some other way, which is an open pre-registration question rather than something to settle in a renderer.

## Tensions

Best Δ per GPU-hour is a screen-tier proxy, not the charter's regret-per-GPU-hour to Δ\*, which needs the arms run to a common target. Nights differ in their candidate sets because the proposer is re-run per night, so this is a randomised comparison across nights rather than a paired one.
