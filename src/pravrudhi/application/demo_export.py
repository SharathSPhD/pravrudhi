"""Export a recorded snapshot of this engine for the hosted site.

A visitor to the public site has no engine and, since browsers began blocking the loopback address space from
public origins, cannot be given one by pointing the page at their own machine. The site must therefore stand on
its own: it shows what this engine actually did, recorded, so that someone deciding whether to install it can see
the product working rather than an error message.

The snapshot is a static bundle of the same JSON shapes the live API serves, so every page renders from it
unchanged. It carries results, not machinery: what was improved, by how much, on which public benchmark, and the
sequence of a real run as it happened.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pravrudhi.api.runs import models_listing
from pravrudhi.application.external import external_rows
from pravrudhi.application.intent import compile_intent
from pravrudhi.application.objectives import load_all
from pravrudhi.application.objectives import problems as objective_problems
from pravrudhi.application.objectives import summary as objective_summary
from pravrudhi.application.recipes import availability, library
from pravrudhi.application.recipes import installed as installed_skills
from pravrudhi.application.status import status
from pravrudhi_kernel.ledger import replay
from pravrudhi_kernel.ledger.verify import iter_events

MAX_EVENTS = 400


def _nights(ledger: Path) -> list[dict[str, Any]]:
    starts: dict[tuple[int, str], dict[str, Any]] = {}
    out: list[dict[str, Any]] = []
    for ev in iter_events(ledger):
        p = ev.payload
        if ev.kind != "audit":
            continue
        track = str(p.get("track") or "lora")
        if p.get("kind") == "night_start":
            starts[(ev.night, track)] = {"policy": p.get("selection_policy"), "incumbent": p.get("incumbent")}
        elif p.get("kind") == "night_end":
            s = starts.get((ev.night, track), {})
            outcomes = p.get("outcomes") or {}
            out.append({
                "night": ev.night, "track": track, "selection_policy": s.get("policy"),
                "spent_gpu_h": round(float(p.get("spent_gpu_h") or 0.0), 3),
                "promoted": [c for c, o in outcomes.items() if o == "promoted"],
                "pruned": sum(1 for o in outcomes.values() if o == "pruned"),
                "candidates": len(outcomes),
            })
    return out


def _replay_run(ledger: Path, night: int, track: str) -> list[dict[str, Any]]:
    """One real night as the sequence of events the app's live view would have shown."""
    events: list[dict[str, Any]] = []
    inside = False
    for ev in iter_events(ledger):
        p = ev.payload
        is_track = (p.get("track") or ("harness" if ev.surface == "H3.prompt" else "lora")) == track
        if ev.kind == "audit" and p.get("kind") == "night_start" and ev.night == night and is_track:
            inside = True
            continue
        if not inside:
            continue
        if ev.kind == "audit" and p.get("kind") == "night_end" and ev.night == night:
            events.append({"type": "closed", "night": night, "status": "closed"})
            break
        if ev.kind == "propose" and ev.candidate_id:
            events.append({"type": "proposed_one", "candidate": ev.candidate_id,
                           "strategy": p.get("strategy"), "family": p.get("edit_family")})
        elif ev.kind == "observe" and p.get("arm") == "candidate" and ev.candidate_id:
            o = p["observed"]
            events.append({
                "type": "paired", "candidate": ev.candidate_id, "seed": p.get("seed_index", 0),
                "incumbent": round(float(o.get("value_ref") or 0.0), 4),
                "candidate_score": round(float(o["value"]), 4),
                "delta": round(float(o["delta_in"]), 4),
                "decision": ((p.get("stats") or {}).get("boundary")) or "",
                "n": int((p.get("stats") or {}).get("n") or 0),
            })
        elif ev.kind == "promote" and ev.candidate_id:
            events.append({"type": "promoted", "candidate": ev.candidate_id})
        elif ev.kind == "prune" and ev.candidate_id:
            events.append({"type": "pruned", "candidate": ev.candidate_id})
    return events[:MAX_EVENTS]


def build_demo(root: Path) -> dict[str, Any]:
    root = Path(root)
    ledger = root / "research" / "ledger.jsonl"
    st = replay(ledger)
    nights = _nights(ledger)
    featured = next((n for n in nights if n["promoted"]), nights[-1] if nights else None)
    runs: list[dict[str, Any]] = []
    for n in reversed(nights[-8:]):
        runs.append({
            "id": f"n{n['night']}-{n['track']}",
            "target": "model" if n["track"] == "lora" else "harness",
            "night": n["night"], "status": "finished", "policy": n["selection_policy"],
            "spent_gpu_h": n["spent_gpu_h"], "candidates": n["candidates"],
            "promoted": n["promoted"], "pruned": n["pruned"],
        })
    return {
        "recorded": True,
        "engine": {"version": "0.1.0", "candidates": len(st.candidates)},
        "status": status(root),
        "models": models_listing(root),
        "external": external_rows(ledger),
        "nights": nights,
        "runs": runs,
        "objectives": {
            "objectives": [objective_summary(root, o) for o in load_all(root)],
            "problems": [{"file": f, "reason": r} for f, r in objective_problems(root)],
        },
        "recipes": availability(),
        "plans": {
            o.id: {
                "objective": o.id,
                **{k: v for k, v in asdict(
                    compile_intent(o, tuple(library()), installed_skills=frozenset(installed_skills()))
                ).items() if k != "objective"},
            }
            for o in load_all(root)
        },
        "featured_run": {
            "id": f"n{featured['night']}-{featured['track']}" if featured else "",
            "night": featured["night"] if featured else 0,
            "track": featured["track"] if featured else "lora",
            "events": _replay_run(ledger, featured["night"], featured["track"]) if featured else [],
        },
    }


def write_demo(root: Path, dest: Path) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(build_demo(root), indent=2, sort_keys=True, default=str) + "\n")
    return dest
