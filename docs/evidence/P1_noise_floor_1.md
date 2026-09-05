# Noise floor study 1 — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, single model (unmodified Qwen/Qwen3-1.7B), A/A design, isolation container.**

Design: exposure_cap=4, k=100, max_new_tokens=512, rotations=5, seeds=3, temperature=0.7, template=gsm8k_v1.md

| seq | rotation | seed | pass_rate | n | model hash | isolation | tok/s |
|---|---|---|---|---|---|---|---|
| 351 | 42cc91fb87bacfca | 0 | 0.8800 | 100 | 620a825b8efe | container | 704.8 |
| 353 | 42cc91fb87bacfca | 1 | 0.8600 | 100 | 620a825b8efe | container | 653.4 |
| 355 | 42cc91fb87bacfca | 2 | 0.8900 | 100 | 620a825b8efe | container | 697.3 |
| 357 | f09726642e04a43f | 0 | 0.8200 | 100 | 620a825b8efe | container | 610.0 |
| 359 | f09726642e04a43f | 1 | 0.8300 | 100 | 620a825b8efe | container | 646.0 |
| 361 | f09726642e04a43f | 2 | 0.8200 | 100 | 620a825b8efe | container | 581.0 |
| 363 | cc4abe399f843967 | 0 | 0.8700 | 100 | 620a825b8efe | container | 622.3 |
| 365 | cc4abe399f843967 | 1 | 0.8800 | 100 | 620a825b8efe | container | 668.8 |
| 367 | cc4abe399f843967 | 2 | 0.9100 | 100 | 620a825b8efe | container | 656.7 |
| 369 | 93a4e91233aa922a | 0 | 0.8600 | 100 | 620a825b8efe | container | 692.8 |
| 371 | 93a4e91233aa922a | 1 | 0.8200 | 100 | 620a825b8efe | container | 678.3 |
| 373 | 93a4e91233aa922a | 2 | 0.8400 | 100 | 620a825b8efe | container | 652.9 |
| 375 | abf383824998c2a0 | 0 | 0.8400 | 100 | 620a825b8efe | container | 694.1 |
| 377 | abf383824998c2a0 | 1 | 0.8600 | 100 | 620a825b8efe | container | 741.5 |
| 379 | abf383824998c2a0 | 2 | 0.8700 | 100 | 620a825b8efe | container | 744.1 |

Runs: 15; items scored: 1500; pooled pass rate 0.8567, Wilson 95% [0.8380, 0.8735].

variance.json: sigma_seed=0.0163 sigma_rot=0.0259 sigma_total=0.0277 theta_surprise(|z| p99)=2.245365597551249
