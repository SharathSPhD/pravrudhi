# H6 screen: does the training footprint predict whether a candidate wins?

CHARTER §2 H6 asks whether an internal sensor predicts the held-out outcome of a self-modification better than chance. This is the cheapest possible sensor: the signals the loop already records when it trains a candidate, with no extra computation at all. Model-internal sensors are a later and more expensive test.

Candidates with both a training record and a measured outcome: **82** (28 of them beat the incumbent at least once).

| quantity | value |
|---|---|
| best single-feature AUROC | 0.7011 |
| label-shuffle null mean | 0.6003 |
| p against that null | 0.0060 |
| clears its own shuffled null | yes |
| clears the charter's 0.6 floor | yes |

Per feature, oriented so a predictor of failure counts as much as one of success:

| feature | AUROC |
|---|---|
| steps | 0.7011 |
| epochs | 0.6905 |
| is_grpo | 0.6812 |
| train_loss | 0.6250 |
| gpu_h | 0.5635 |
| n_kept | 0.5427 |
| peak_gib | 0.5407 |
| lora_r | 0.5394 |

## The confound, checked

The best feature is scored again inside each recipe family, because a sensor that predicts across the pool but not within it is rediscovering which family wins rather than sensing anything about the candidate.

| family | n | win rate | AUROC of the best feature |
|---|---|---|---|
| grpo_verifiable | 43 | 0.186 | 0.6929 |
| sft_rejection | 39 | 0.513 | 0.5579 |

**Survives stratification: no.** The signal does not hold inside each family. The pooled score is largely the family effect, which the controller already conditions on through the edit family, so this sensor adds little beyond what the loop already knows. A model-internal sensor is the test that would settle H6.

## Tensions

The charter's kill criterion for H6 is stated at 200 labelled cycles and this screen has 82, so no hypothesis is settled here in either direction. A single feature is scored rather than a fitted model because at this sample size a multi-feature fit would mostly measure its own capacity to overfit. The label is whether a candidate ever beat the incumbent, which is the loop's own decision variable and inherits its noise.

