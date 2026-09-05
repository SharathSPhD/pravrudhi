# L3 noise floor — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, single model (unmodified Qwen/Qwen3-4B), A/A design, isolation container.**

Design: exposure_cap=3, k=100, max_new_tokens=512, rotations=10, seeds=3, temperature=0.7, template=gsm8k_v1.md

| seq | rotation | seed | pass_rate | n | model hash | isolation | tok/s |
|---|---|---|---|---|---|---|---|
| 4 | 5d6fbcfa3f9000b3 | 0 | 0.9200 | 100 | fabef443d29b | container | 450.9 |
| 6 | 5d6fbcfa3f9000b3 | 1 | 0.9100 | 100 | fabef443d29b | container | 436.5 |
| 8 | 5d6fbcfa3f9000b3 | 2 | 0.9400 | 100 | fabef443d29b | container | 469.4 |
| 10 | de4b70dce4f19717 | 0 | 0.9300 | 100 | fabef443d29b | container | 458.7 |
| 12 | de4b70dce4f19717 | 1 | 0.9100 | 100 | fabef443d29b | container | 455.4 |
| 14 | de4b70dce4f19717 | 2 | 0.9100 | 100 | fabef443d29b | container | 430.9 |
| 16 | a0d2ade593885b02 | 0 | 0.9000 | 100 | fabef443d29b | container | 464.2 |
| 18 | a0d2ade593885b02 | 1 | 0.8200 | 100 | fabef443d29b | container | 480.7 |
| 20 | a0d2ade593885b02 | 2 | 0.8800 | 100 | fabef443d29b | container | 467.0 |
| 22 | b6e5261003bb23b1 | 0 | 0.8500 | 100 | fabef443d29b | container | 442.6 |
| 24 | b6e5261003bb23b1 | 1 | 0.8500 | 100 | fabef443d29b | container | 437.1 |
| 26 | b6e5261003bb23b1 | 2 | 0.8900 | 100 | fabef443d29b | container | 402.3 |
| 28 | 68a85398df5e66c5 | 0 | 0.8500 | 100 | fabef443d29b | container | 444.9 |
| 30 | 68a85398df5e66c5 | 1 | 0.9000 | 100 | fabef443d29b | container | 458.7 |
| 32 | 68a85398df5e66c5 | 2 | 0.8700 | 100 | fabef443d29b | container | 489.8 |
| 34 | 40062953fe01de7b | 0 | 0.8600 | 100 | fabef443d29b | container | 444.4 |
| 36 | 40062953fe01de7b | 1 | 0.8600 | 100 | fabef443d29b | container | 459.8 |
| 38 | 40062953fe01de7b | 2 | 0.8500 | 100 | fabef443d29b | container | 436.7 |
| 40 | 428817ceed4524e0 | 0 | 0.9100 | 100 | fabef443d29b | container | 495.6 |
| 42 | 428817ceed4524e0 | 1 | 0.9300 | 100 | fabef443d29b | container | 488.6 |
| 44 | 428817ceed4524e0 | 2 | 0.9300 | 100 | fabef443d29b | container | 443.7 |
| 46 | 8221733173696a1e | 0 | 0.9300 | 100 | fabef443d29b | container | 496.2 |
| 48 | 8221733173696a1e | 1 | 0.9100 | 100 | fabef443d29b | container | 480.1 |
| 50 | 8221733173696a1e | 2 | 0.9100 | 100 | fabef443d29b | container | 493.3 |
| 52 | a3ab5c6e90d23018 | 0 | 0.9500 | 100 | fabef443d29b | container | 463.9 |
| 54 | a3ab5c6e90d23018 | 1 | 0.9000 | 100 | fabef443d29b | container | 440.7 |
| 56 | a3ab5c6e90d23018 | 2 | 0.9300 | 100 | fabef443d29b | container | 469.0 |
| 58 | 917b2341effc71a0 | 0 | 0.9500 | 100 | fabef443d29b | container | 479.7 |
| 60 | 917b2341effc71a0 | 1 | 0.9200 | 100 | fabef443d29b | container | 465.8 |
| 62 | 917b2341effc71a0 | 2 | 0.9200 | 100 | fabef443d29b | container | 520.0 |

Runs: 30; items scored: 3000; pooled pass rate 0.8997, Wilson 95% [0.8884, 0.9099].

variance.json: sigma_seed=0.0212 sigma_rot=0.0304 sigma_total=0.0342 theta_surprise(|z| p99)=2.372736087981521
