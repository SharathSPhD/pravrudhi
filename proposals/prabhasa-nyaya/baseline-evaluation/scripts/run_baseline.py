"""Orchestrator for the baseline-evaluation proposal.

Reads configs/eval_config.yaml, runs each enabled declared external tool,
and writes one JSON record per tool to the given --out path. A tool that
fails to run is recorded with its error rather than omitted, so the output
always reflects "tried all N tools," never a silent subset.

This script writes only to paths passed via --out (expected: this proposal's
own output/ directory). It never touches the ledger, research/, gates/, or
pravrudhi_kernel/.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

import citation_grounding_eval
import ildc_cjpe_eval
import iltur_eval
from common import ToolResult, write_results


def _run_il_tur(tool_cfg: dict[str, Any], cfg: dict[str, Any]) -> ToolResult:
    return iltur_eval.run(
        tasks=tool_cfg["tasks"],
        base_model=cfg["base_model"],
        sample_count=cfg["sample_count"],
        dataset_cache_dir=Path(cfg["dataset_cache_dir"]),
        seed=cfg["seed"],
    )


def _run_ildc_cjpe(tool_cfg: dict[str, Any], cfg: dict[str, Any]) -> ToolResult:
    return ildc_cjpe_eval.run(
        tasks=tool_cfg["tasks"],
        base_model=cfg["base_model"],
        sample_count=cfg["sample_count"],
        dataset_cache_dir=Path(cfg["dataset_cache_dir"]),
        seed=cfg["seed"],
    )


def _run_citation_grounding(tool_cfg: dict[str, Any], cfg: dict[str, Any]) -> ToolResult:
    def _unwired_generate(prompt: str) -> str:
        raise NotImplementedError(
            "Wire citation_grounding_eval's generate() to base_model before running."
        )

    return citation_grounding_eval.run(
        questions_path=Path(tool_cfg["questions_path"]),
        generate=_unwired_generate,
        abstain_phrases=tool_cfg["abstain_phrases"],
        sample_count=cfg["sample_count"],
        base_model=cfg["base_model"],
    )


_RUNNERS = {
    "il_tur": _run_il_tur,
    "ildc_cjpe": _run_ildc_cjpe,
    "citation_grounding": _run_citation_grounding,
}


def load_config(config_path: Path) -> dict[str, Any]:
    return yaml.safe_load(config_path.read_text())


def run_all(cfg: dict[str, Any]) -> list[ToolResult]:
    results: list[ToolResult] = []
    for tool_cfg in cfg.get("tools", []):
        if not tool_cfg.get("enabled", True):
            continue
        name = tool_cfg["name"]
        runner = _RUNNERS.get(name)
        if runner is None:
            results.append(
                ToolResult.failed(
                    tool_name=name,
                    tool_version="unknown",
                    base_model=cfg["base_model"],
                    sample_count=cfg["sample_count"],
                    error=f"no runner registered for declared tool '{name}'",
                )
            )
            continue
        try:
            results.append(runner(tool_cfg, cfg))
        except Exception as exc:  # noqa: BLE001 - one tool's failure must not block the others
            results.append(
                ToolResult.failed(
                    tool_name=name,
                    tool_version=tool_cfg.get("package_version", "unknown"),
                    base_model=cfg["base_model"],
                    sample_count=cfg["sample_count"],
                    error=str(exc),
                )
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    results = run_all(cfg)
    write_results(results, args.out)


if __name__ == "__main__":
    main()
