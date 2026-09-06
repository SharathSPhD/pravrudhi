"""Admit external-scorer results (lm-eval, EvalPlus) into the ledger and render them.

The Sākṣī rule: no number is stated that the ledger does not contain. External benchmarks are run by third-party
tooling outside the kernel, so their result files are admitted by hash as `audit{kind: external_eval}` rows with the
tier stated as `external`: the kernel did not execute them, the file hash makes them reproducible, and the evidence
document renders only from those rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger import LedgerWriter
from pravrudhi_kernel.ledger.verify import iter_events
from pravrudhi_kernel.sandbox.observe import sha256_file
from pravrudhi_kernel.stats import wilson_ci


def _lm_eval_items(r: dict[str, Any]) -> dict[str, int]:
    """Per-doc pass/fail for the first task's `exact_match`, when `--log_samples` wrote them.

    lm-eval only writes a `samples` section when invoked with `--log_samples`; most result files carry none, and
    `parse_lm_eval` must omit the `items` key entirely for those rather than store an empty dict.
    """
    samples = r.get("samples") or {}
    task = next(iter(r.get("results") or {}), None)
    if task is None:
        return {}
    out: dict[str, int] = {}
    for row in samples.get(task) or []:
        doc_id = row.get("doc_id")
        val = row.get("exact_match")
        if doc_id is None or val is None:
            continue
        out[str(doc_id)] = int(round(float(val)))
    return out


def parse_lm_eval(path: Path) -> dict[str, Any]:
    r = json.loads(path.read_text())
    metrics: dict[str, dict[str, float]] = {}
    for task, m in r["results"].items():
        metrics[task] = {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
    parsed: dict[str, Any] = {
        "tool": "lm-eval",
        "tool_version": r.get("lm_eval_version"),
        "transformers_version": r.get("transformers_version"),
        "n_samples": {t: v.get("effective") for t, v in (r.get("n-samples") or {}).items()},
        "n_shot": r.get("n-shot"),
        "model_args": (r.get("config") or {}).get("model_args"),
        "metrics": metrics,
    }
    items = _lm_eval_items(r)
    if items:
        parsed["items"] = items
    return parsed


def parse_evalplus(path: Path, dataset: str) -> dict[str, Any]:
    r = json.loads(path.read_text())
    rows = r["eval"]
    n = len(rows)
    base = sum(1 for v in rows.values() if v[0]["base_status"] == "pass")
    plus = sum(1 for v in rows.values() if v[0]["base_status"] == "pass" and v[0]["plus_status"] == "pass")
    items = {
        task_id: int(v[0]["base_status"] == "pass" and v[0]["plus_status"] == "pass") for task_id, v in rows.items()
    }
    return {
        "tool": "evalplus",
        "tool_version": "0.3.1",
        "dataset": dataset,
        "n_samples": {dataset: n},
        "metrics": {
            dataset: {"pass@1_base": base / n, "pass@1_plus": plus / n},
            f"{dataset}_counts": {"n": n, "base_pass": base, "plus_pass": plus},
        },
        "items": items,
    }


def record_external(
    root: Path,
    path: Path,
    *,
    tool: str,
    track: str,
    condition: str,
    model: str,
    night: int,
    dataset: str = "",
    seed: int | None = None,
) -> dict[str, Any]:
    parsed = parse_lm_eval(path) if tool == "lm-eval" else parse_evalplus(path, dataset)
    ledger = root / "research" / "ledger.jsonl"
    w = LedgerWriter.open(ledger, "0.1.0")
    payload = {
        "kind": "external_eval",
        "severity": "info",
        "tier": "external",
        "track": track,
        "condition": condition,
        "model": model,
        "seed": seed,
        "file": str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
        "sha256": sha256_file(path),
        **parsed,
    }
    ev = w.append("audit", "auditor", payload, epoch=0, night=night)
    return {"seq": ev.seq, **payload}


def external_rows(ledger: Path) -> list[dict[str, Any]]:
    out = []
    for ev in iter_events(ledger):
        if ev.kind == "audit" and ev.payload.get("kind") == "external_eval":
            out.append({"seq": ev.seq, "night": ev.night, **ev.payload})
    return out


def stderr_key(key: str) -> str:
    """lm-eval names a metric `<name>,<filter>` and its standard error `<name>_stderr,<filter>`.

    The earlier form of this substituted the literal string `exact_match`, which is correct for GSM8K and wrong for
    every other task: for `acc,none` the substitution matched nothing, the lookup fell back to the metric key
    itself, and the rendered ± column printed the value a second time. Any objective on a task that is not scored
    by exact match would have inherited that.
    """
    head, sep, tail = key.partition(",")
    return f"{head}_stderr{sep}{tail}"


def _headline(row: dict[str, Any]) -> tuple[str, float, float, int]:
    m = row["metrics"]
    if row["tool"] == "lm-eval":
        task = next(iter(m))
        key = "exact_match,strict-match" if "exact_match,strict-match" in m[task] else next(iter(m[task]))
        n = int((row.get("n_samples") or {}).get(task) or 0)
        return f"{task} {key}", m[task][key], m[task].get(stderr_key(key), 0.0), n
    ds = row["dataset"]
    n = m[f"{ds}_counts"]["n"]
    p = m[ds]["pass@1_plus"]
    lo, hi = wilson_ci(int(round(p * n)), n)
    return f"{ds}+ pass@1", p, (hi - lo) / 2, n


def render_external(ledger: Path) -> str:
    rows = external_rows(ledger)
    lines = [
        "# External proof tier",
        "",
        "Rendered from the ledger's `audit{kind: external_eval}` rows alone. Every row was scored by third-party "
        "tooling outside the kernel (tier: external); the result file is admitted by SHA-256. The kernel's own "
        "selection record is in the night documents.",
        "",
        "| seq | track | condition | model | scorer | metric | value | ±  | n | file sha256 |",  # noqa: E501
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        name, v, e, n = _headline(r)
        lines.append(
            f"| {r['seq']} | {r['track']} | {r['condition']} | {r['model']} | {r['tool']} {r.get('tool_version') or ''} "
            f"| {name} | {v:.4f} | {e:.4f} | {n} | {r['sha256'][:16]} |"
        )
    lines += ["", "## Paired differences", ""]
    by: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for r in rows:
        name, *_ = _headline(r)
        by.setdefault((r["track"], name), {})[r["condition"]] = r
    for (track, name), conds in sorted(by.items()):
        base = conds.get("base")
        if not base:
            continue
        _, bv, be, bn = _headline(base)
        for cond, r in conds.items():
            if cond == "base":
                continue
            _, v, e, n = _headline(r)
            lines.append(
                f"- {track} {name}: {cond} − base = {v - bv:+.4f} "
                f"(base {bv:.4f}±{be:.4f}, {cond} {v:.4f}±{e:.4f}, n={n})"
            )
    if len(lines) and lines[-1] == "":
        lines.append("- (no paired pair yet)")
    lines += [
        "",
        "## Tensions",
        "",
        "External rows are not kernel-executed: they carry tier `external`, not pratyakṣa in the kernel sense. "
        "Their standard errors are the scorer's own (lm-eval) or a Wilson half-width (EvalPlus), not the loop's σ_seed.",
        "",
    ]
    return "\n".join(lines)
