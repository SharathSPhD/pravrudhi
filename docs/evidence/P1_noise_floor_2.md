# Noise floor study 2 — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, single model (unmodified Qwen/Qwen3-0.6B), A/A design, isolation container.**

Design: exposure_cap=4, k=200, max_new_tokens=512, rotations=5, seeds=3, temperature=0.7, template=gsm8k_v1.md

| seq | rotation | seed | pass_rate | n | model hash | isolation | tok/s |
|---|---|---|---|---|---|---|---|
| 548 | 878a995aeda301b9 | 0 | 0.6200 | 200 | df7e26d2bd92 | container | 826.9 |
| 550 | 878a995aeda301b9 | 1 | 0.6050 | 200 | df7e26d2bd92 | container | 743.3 |
| 552 | 878a995aeda301b9 | 2 | 0.5800 | 200 | df7e26d2bd92 | container | 803.3 |
| 554 | 702336776287dc7a | 0 | 0.5600 | 200 | df7e26d2bd92 | container | 888.7 |
| 556 | 702336776287dc7a | 1 | 0.5850 | 200 | df7e26d2bd92 | container | 935.6 |
| 558 | 702336776287dc7a | 2 | 0.5700 | 200 | df7e26d2bd92 | container | 829.1 |
| 560 | 88f00bfe18eeb80c | 0 | 0.5700 | 200 | df7e26d2bd92 | container | 805.3 |
| 562 | 88f00bfe18eeb80c | 1 | 0.5450 | 200 | df7e26d2bd92 | container | 817.3 |
| 564 | 88f00bfe18eeb80c | 2 | 0.5950 | 200 | df7e26d2bd92 | container | 876.9 |
| 566 | 56f6d111680b0d80 | 0 | 0.6500 | 200 | df7e26d2bd92 | container | 786.6 |
| 568 | 56f6d111680b0d80 | 1 | 0.6750 | 200 | df7e26d2bd92 | container | 799.7 |
| 570 | 56f6d111680b0d80 | 2 | 0.6200 | 200 | df7e26d2bd92 | container | 831.0 |
| 572 | c289d877e089d69e | 0 | 0.5950 | 200 | df7e26d2bd92 | container | 793.7 |
| 574 | c289d877e089d69e | 1 | 0.6350 | 200 | df7e26d2bd92 | container | 808.2 |
| 576 | c289d877e089d69e | 2 | 0.6350 | 200 | df7e26d2bd92 | container | 870.7 |

Runs: 15; items scored: 3000; pooled pass rate 0.6027, Wilson 95% [0.5850, 0.6200].

variance.json: sigma_seed=0.0223 sigma_rot=0.0334 sigma_total=0.0362 theta_surprise(|z| p99)=2.587571395550144
