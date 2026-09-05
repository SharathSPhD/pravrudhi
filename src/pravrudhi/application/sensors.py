"""Internal sensors: does anything the loop already observes predict whether a candidate will win?

CHARTER §2 H6 asks whether an internal signal predicts the held-out outcome of a self-modification better than
chance, and whether using it improves the predictor's calibrated reliability. It has never been examined here. The
charter's own examples are interpretability sensors, which need model internals; this module starts with the
signals the loop already records for free on every candidate it trains, because a sensor that costs nothing and
predicts nothing is worth knowing about before one that costs a GPU-hour.

The features are the training run's own footprint: final loss, step count, wall cost, peak memory, and the shape of
the recipe that produced it. The label is whether the candidate beat the incumbent on held-out problems it had
never seen. Nothing here touches the model's activations; that is the next sensor, not this one.

Every reported score is checked against a label-shuffle null, ported from prayoga, because a discriminative score
computed on eighty-odd points will look impressive by accident often enough to matter. A score that does not clear
its own shuffled distribution is reported as not clearing it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pravrudhi_kernel.ledger.verify import iter_events
from pravrudhi_kernel.stats.label_shuffle import label_shuffle_null

FEATURES = ("train_loss", "steps", "gpu_h", "peak_gib", "n_kept", "epochs", "lora_r", "is_grpo")

# Below this many candidates a stratum's AUROC is not worth reading, so the verdict is "undetermined" rather than
# a quiet failure: too little evidence and evidence against are different answers and must not look alike.
MIN_STRATUM = 20


@dataclass(frozen=True)
class SensorReport:
    n: int
    positives: int
    auroc: float
    null_mean: float
    null_p: float
    clears_null: bool
    beats_charter_floor: bool
    per_feature: dict[str, float]
    stratified: dict[str, dict[str, float]]

    @property
    def stratification_verdict(self) -> str:
        """Whether the best feature still predicts inside each recipe family.

        A sensor that scores well across the pool but at chance within families is not sensing anything about the
        candidate; it is rediscovering which family wins, which the controller already conditions on. That is the
        difference between a new source of evidence and a restatement of an old one. A family with too few
        candidates to judge yields "undetermined", never "no": absence of evidence is reported as such.
        """
        judged = [v for v in self.stratified.values() if v["n"] >= MIN_STRATUM]
        if not judged or len(judged) < len(self.stratified):
            return "undetermined"
        return "yes" if min(v["auroc"] for v in judged) > 0.6 else "no"

    @property
    def survives_stratification(self) -> bool:
        return self.stratification_verdict == "yes"

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n, "positives": self.positives, "auroc": round(self.auroc, 4),
            "null_mean": round(self.null_mean, 4), "null_p": round(self.null_p, 4),
            "clears_null": self.clears_null, "beats_charter_floor": self.beats_charter_floor,
            "per_feature_auroc": {k: round(v, 4) for k, v in sorted(self.per_feature.items())},
            "stratified": self.stratified, "survives_stratification": self.survives_stratification,
            "stratification_verdict": self.stratification_verdict,
        }


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Rank-based area under the ROC curve, ties averaged. 0.5 is chance."""
    pos, neg = labels == 1, labels == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1, dtype=float)
    # average ranks within ties so a constant feature scores exactly chance
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = ranks[order[i : j + 1]].mean()
        i = j + 1
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def collect(ledger: Path) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """One row per candidate that was both trained and measured: its training footprint and whether it won."""
    train: dict[str, dict[str, Any]] = {}
    recipe: dict[str, dict[str, Any]] = {}
    deltas: dict[str, list[float]] = {}
    for ev in iter_events(Path(ledger)):
        cid, p = ev.candidate_id, ev.payload
        if not cid:
            continue
        if ev.kind == "propose":
            recipe[cid] = p.get("recipe") or {}
        elif ev.kind == "spend" and p.get("phase") == "train" and p.get("steps"):
            train[cid] = p
        elif ev.kind == "observe" and p.get("arm") == "candidate":
            deltas.setdefault(cid, []).append(float(p["observed"]["delta_in"]))
    rows, labels, ids = [], [], []
    for cid, t in train.items():
        if cid not in deltas:
            continue
        r = recipe.get(cid, {})
        sft = r.get("sft") or {}
        lora = r.get("lora") or {}
        rows.append([
            float(t.get("train_loss") or 0.0),
            float(t.get("steps") or 0),
            float(t.get("gpu_h") or 0.0),
            float(t.get("peak_gib") or 0.0),
            float(sft.get("n_kept") or 0),
            float(sft.get("epochs") or 0),
            float(lora.get("r") or 0),
            1.0 if str(r.get("strategy", "")).startswith("grpo") else 0.0,
        ])
        labels.append(1 if max(deltas[cid]) > 0 else 0)
        ids.append(cid)
    return np.array(rows, dtype=float), np.array(labels, dtype=int), ids


def _fit_score(X: np.ndarray, y: np.ndarray) -> float:
    """Best single-feature AUROC, oriented so that a feature predicting failure counts as much as one predicting
    success. A single feature is used deliberately: with this many points, a fitted multi-feature model would be
    measuring its own capacity to overfit."""
    best = 0.5
    for j in range(X.shape[1]):
        a = auroc(X[:, j], y)
        best = max(best, a, 1.0 - a)
    return best


def evaluate(ledger: Path, *, n_shuffle: int = 1000, seed: int = 42) -> SensorReport:
    X, y, _ = collect(ledger)
    if len(y) == 0 or len(set(y.tolist())) < 2:
        return SensorReport(len(y), int(y.sum()) if len(y) else 0, 0.5, 0.5, 1.0, False, False, {}, {})
    null = label_shuffle_null(_fit_score, X, y, n_shuffle=n_shuffle, random_state=seed)
    per = {}
    for j, name in enumerate(FEATURES):
        a = auroc(X[:, j], y)
        per[name] = max(a, 1.0 - a)
    score = float(null["true_score"])
    p = float(null.get("p_value", 1.0))
    best_name = max(per, key=lambda k: per[k])
    best_col = FEATURES.index(best_name)
    grpo = X[:, FEATURES.index("is_grpo")]
    strat: dict[str, dict[str, float]] = {}
    for label, mask in (("grpo_verifiable", grpo == 1), ("sft_rejection", grpo == 0)):
        yy, xx = y[mask], X[mask, best_col]
        if len(yy) and len(set(yy.tolist())) > 1:
            a = auroc(xx, yy)
            strat[label] = {"n": int(len(yy)), "positives": int(yy.sum()),
                            "win_rate": round(float(yy.mean()), 4), "auroc": round(max(a, 1 - a), 4)}
        else:
            strat[label] = {"n": int(len(yy)), "positives": int(yy.sum()) if len(yy) else 0,
                            "win_rate": round(float(yy.mean()), 4) if len(yy) else 0.0, "auroc": 0.5}
    return SensorReport(
        n=len(y), positives=int(y.sum()), auroc=score, null_mean=float(null.get("null_mean", 0.5)),
        null_p=p, clears_null=p < 0.05, beats_charter_floor=score > 0.6 and p < 0.05, per_feature=per,
        stratified=strat,
    )


def render_sensors(ledger: Path) -> str:
    r = evaluate(ledger)
    lines = [
        "# H6 screen: does the training footprint predict whether a candidate wins?",
        "",
        "CHARTER §2 H6 asks whether an internal sensor predicts the held-out outcome of a self-modification better "
        "than chance. This is the cheapest possible sensor: the signals the loop already records when it trains a "
        "candidate, with no extra computation at all. Model-internal sensors are a later and more expensive test.",
        "",
        f"Candidates with both a training record and a measured outcome: **{r.n}** "
        f"({r.positives} of them beat the incumbent at least once).",
        "",
        "| quantity | value |",
        "|---|---|",
        f"| best single-feature AUROC | {r.auroc:.4f} |",
        f"| label-shuffle null mean | {r.null_mean:.4f} |",
        f"| p against that null | {r.null_p:.4f} |",
        f"| clears its own shuffled null | {'yes' if r.clears_null else 'no'} |",
        f"| clears the charter's 0.6 floor | {'yes' if r.beats_charter_floor else 'no'} |",
        "",
        "Per feature, oriented so a predictor of failure counts as much as one of success:",
        "",
        "| feature | AUROC |",
        "|---|---|",
    ]
    for feature, score in sorted(r.per_feature.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {feature} | {score:.4f} |")
    lines += [
        "",
        "## The confound, checked",
        "",
        "The best feature is scored again inside each recipe family, because a sensor that predicts across the pool "
        "but not within it is rediscovering which family wins rather than sensing anything about the candidate.",
        "",
        "| family | n | win rate | AUROC of the best feature |",
        "|---|---|---|---|",
    ]
    for fam, stats in sorted(r.stratified.items()):
        lines.append(f"| {fam} | {int(stats['n'])} | {stats['win_rate']:.3f} | {stats['auroc']:.4f} |")
    lines += [
        "",
        f"**Survives stratification: {r.stratification_verdict}.** "
        + {
            "yes": "The signal holds inside each family, so it is not merely the family effect.",
            "no": "The signal does not hold inside each family. The pooled score is largely the family effect, "
                  "which the controller already conditions on through the edit family, so this sensor adds little "
                  "beyond what the loop already knows. A model-internal sensor is the test that would settle H6.",
            "undetermined": f"At least one family has fewer than {MIN_STRATUM} candidates, which is too few to "
                            "judge the signal inside it. This is absence of evidence, not evidence of absence.",
        }[r.stratification_verdict],
        "",
        "## Tensions",
        "",
        f"The charter's kill criterion for H6 is stated at 200 labelled cycles and this screen has {r.n}, so no "
        "hypothesis is settled here in either direction. A single feature is scored rather than a fitted model "
        "because at this sample size a multi-feature fit would mostly measure its own capacity to overfit. The "
        "label is whether a candidate ever beat the incumbent, which is the loop's own decision variable and "
        "inherits its noise.",
        "",
    ]
    return "\n".join(lines) + "\n"
