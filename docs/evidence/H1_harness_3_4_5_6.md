# H1 screen: selection arms on harness nights 3, 4, 5, 6

Rendered from the ledger alone. Arms differ in selection only: pairing, the sequential boundary, the canaries and every row shape are identical across arms.

**VOID — this is not a comparison.**

Arms with no paired evaluation: efe. Arms absent from these nights: none.

An arm that never ran cannot lose. Re-run with a pool that can carry every arm before reading anything into the table below.

| arm | nights | proposed | selected | paired evals | mean Δ | best Δ | promoted | pruned | GPU-h | Δ per GPU-h |
|---|---|---|---|---|---|---|---|---|---|---|
| efe | 4,6 | 16 | 110 | 0 | +0.0000 | +0.0000 | 0 | 0 | 0.000 | +0.0000 |
| greedy | 3,5 | 15 | 105 | 15 | +0.0100 | +0.1300 | 1 | 3 | 0.317 | +0.4105 |

Δ\* (60th percentile of the greedy arm's gain distribution, CHARTER §2 H1, n=15): +0.0100.

## Tensions

Best Δ per GPU-hour is a screen-tier proxy, not the charter's regret-per-GPU-hour to Δ\*, which needs the arms run to a common target. Nights differ in their candidate sets because the proposer is re-run per night, so this is a randomised comparison across nights rather than a paired one.
