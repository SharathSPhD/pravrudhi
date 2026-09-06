"""RL post-training entry point (recipe: rl-post-training).

Consumes: objective, finetune_candidate, prepared_corpus.
Produces: rl_candidate (a LoRA adapter on top of finetune_candidate).

This is a PROPOSAL: it defines the wiring (GRPO over TRL + PEFT, reward
from reward_function.py, config from configs/rl_grpo.yaml) but does not
run here, does not write to the ledger, and produces no numbers that should
be read as measured results.

    uv run python proposals/prabhasa-nyaya/rl/scripts/train_rl.py \\
        --config proposals/prabhasa-nyaya/rl/configs/rl_grpo.yaml \\
        --finetune-candidate path/to/finetune_candidate.json \\
        --prepared-corpus path/to/prepared_corpus.jsonl \\
        --objective path/to/objective.json \\
        --output-dir outputs/prabhasa-nyaya-rl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from data_contracts import FinetuneCandidateRef, GraphEdge, GraphNode, NyayaGraph, PreparedExample, RLCandidateRef
from reward_function import DEFAULT_WEIGHTS, RewardWeights, compute_reward


def load_config(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f)


def load_finetune_candidate(path: Path) -> FinetuneCandidateRef:
    obj = json.loads(path.read_text())
    return FinetuneCandidateRef(
        base_model=obj["base_model"],
        adapter_path=obj.get("adapter_path"),
        tokenizer_path=obj["tokenizer_path"],
    )


def load_prepared_corpus(path: Path, split: str) -> list[PreparedExample]:
    examples = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("split", "train") != split:
                continue
            graph = NyayaGraph(
                nodes=[GraphNode(**n) for n in obj["graph"]["nodes"]],
                edges=[GraphEdge(**e) for e in obj["graph"]["edges"]],
            )
            examples.append(
                PreparedExample(
                    id=obj["id"],
                    question=obj["question"],
                    graph=graph,
                    gold_citations=obj.get("gold_citations", []),
                    gold_answer=obj.get("gold_answer"),
                    answerable=obj["answerable"],
                )
            )
    return examples


def build_reward_weights(cfg: dict) -> RewardWeights:
    weights_cfg = cfg.get("reward", {}).get("weights", {})
    if not weights_cfg:
        return DEFAULT_WEIGHTS
    return RewardWeights(**weights_cfg)


def build_trainer(cfg: dict, finetune_candidate: FinetuneCandidateRef, train_examples: list[PreparedExample]):
    """Constructs the TRL GRPOTrainer. Imported lazily so this module still
    compiles and is importable in environments without trl/peft/torch
    installed (e.g. this proposal's own compileall check)."""
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from trl import GRPOConfig, GRPOTrainer

    lora_cfg = cfg["lora"]
    algo_cfg = cfg["algorithm"]

    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["alpha"],
        lora_dropout=lora_cfg["dropout"],
        target_modules=lora_cfg["target_modules"],
        task_type="CAUSAL_LM",
    )

    tokenizer = AutoTokenizer.from_pretrained(finetune_candidate.tokenizer_path)
    model = AutoModelForCausalLM.from_pretrained(finetune_candidate.base_model)
    if finetune_candidate.adapter_path:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, finetune_candidate.adapter_path, is_trainable=True)

    weights = build_reward_weights(cfg)
    examples_by_prompt = {ex.question: ex for ex in train_examples}

    def reward_fn(prompts: list[str], completions: list[str], **_: object) -> list[float]:
        from output_parser import parse_model_output  # see README: expected output schema

        scores = []
        for prompt, completion in zip(prompts, completions):
            example = examples_by_prompt.get(prompt)
            if example is None:
                scores.append(0.0)
                continue
            output = parse_model_output(completion)
            scores.append(compute_reward(output, example, weights))
        return scores

    grpo_config = GRPOConfig(
        output_dir=cfg["output"]["rl_candidate_adapter_dir"],
        learning_rate=algo_cfg["learning_rate"],
        num_generations=algo_cfg["group_size"],
        per_device_train_batch_size=algo_cfg["prompts_per_step"],
        max_steps=algo_cfg["total_steps"],
        beta=algo_cfg["kl_beta"],
        max_completion_length=algo_cfg["max_new_tokens"],
    )

    trainer = GRPOTrainer(
        model=model,
        args=grpo_config,
        reward_funcs=[reward_fn],
        train_dataset=[{"prompt": ex.question} for ex in train_examples],
        peft_config=peft_config if not finetune_candidate.adapter_path else None,
        processing_class=tokenizer,
    )
    return trainer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--finetune-candidate", required=True, type=Path)
    parser.add_argument("--prepared-corpus", required=True, type=Path)
    parser.add_argument("--objective", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    cfg = load_config(args.config)
    finetune_candidate = load_finetune_candidate(args.finetune_candidate)
    train_examples = load_prepared_corpus(args.prepared_corpus, cfg["data"]["train_split"])
    objective = json.loads(args.objective.read_text())

    print(f"Loaded objective: {objective.get('id', '<unnamed>')}")
    print(f"Training examples: {len(train_examples)}")
    print(
        "This script wires GRPO + LoRA + reward_function.py per configs/rl_grpo.yaml. "
        "It is a proposal: run reward audit first (audit_reward.py), and evaluate the "
        "resulting rl_candidate with held_out_eval.py, independently of the training reward."
    )

    trainer = build_trainer(cfg, finetune_candidate, train_examples)
    trainer.train()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    adapter_dir = args.output_dir / "adapter"
    trainer.save_model(str(adapter_dir))

    rl_candidate = RLCandidateRef(
        base_model=finetune_candidate.base_model,
        adapter_path=str(adapter_dir),
        parent_finetune_candidate=finetune_candidate,
        training_config_path=str(args.config),
    )
    (args.output_dir / "rl_candidate.json").write_text(
        json.dumps(rl_candidate.__dict__, default=lambda o: o.__dict__, indent=2)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
