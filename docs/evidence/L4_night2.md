# L4 first night (night 2) — rendered from research/ledger.jsonl

**Label: model-measured, screen tier, one loop seed, paired on the same rotation and sampling seed; isolation container.**

| candidate | strategy | family | selected | paired deltas | boundary | canary | outcome | hetvābhāsa | Brier |
|---|---|---|---|---|---|---|---|---|---|
| c-0024 | grpo_verifiable | grpo | yes |  |  |  | proposed |  |  |
| c-0025 | sft_rejection | data_mixture | yes |  |  |  | proposed |  |  |
| c-0026 | sft_rejection | adapter | yes |  |  |  | proposed |  |  |
| c-0027 | grpo_verifiable | grpo | yes |  |  |  | proposed |  |  |
| c-0028 | sft_rejection | template | yes |  |  |  | proposed |  |  |
| c-0029 | grpo_verifiable | grpo | yes |  |  |  | proposed |  |  |

Candidates proposed: 6; selected: 6; outcomes: proposed=6; GPU-hours charged (spend rows): 0.88.

Audits:

- kind=samples_verified, n_kept=940, kept_rate=0.91796875, run_id=n2-sample-75984914
- kind=strategy_switch_rate, switches=24, n=54, wilson=[0.3200225687559781, 0.5762458608863554]
- kind=night_end, spent_gpu_h=0.0, outcomes={'c-0009': 'skipped:bad_recipe', 'c-0021': 'skipped:bad_recipe', 'c-0002': 'skipped:bad_recipe', 'c-0007': 'skipped:pool_exhausted'}
