"""`pravrudhi export`: hand back the improved artefact. The adapter is copied as-is; merging into base weights is a
human act that requires a signed gate and is performed by an explicit flag."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from pravrudhi_kernel.ledger import replay
from pravrudhi_kernel.ledger.verify import iter_events


def current_incumbent(root: Path) -> dict[str, Any] | None:
    """The latest promoted candidate with its adapter path, from the ledger alone."""
    last = None
    for ev in iter_events(root / "research" / "ledger.jsonl"):
        if ev.kind == "promote" and ev.candidate_id:
            last = {
                "candidate_id": ev.candidate_id,
                "adapter": ev.payload.get("from_worktree"),
                "night": ev.night,
                "merge_commit": ev.payload.get("merge_commit"),
                "seq": ev.seq,
            }
    return last


def export_adapter(root: Path, dest: Path, *, candidate_id: str | None = None) -> dict[str, Any]:
    st = replay(root / "research" / "ledger.jsonl")
    inc = current_incumbent(root)
    if candidate_id:
        chosen = None
        for ev in iter_events(root / "research" / "ledger.jsonl"):
            if ev.kind == "promote" and ev.candidate_id == candidate_id:
                chosen = {
                    "candidate_id": candidate_id,
                    "adapter": ev.payload.get("from_worktree"),
                    "night": ev.night,
                    "merge_commit": ev.payload.get("merge_commit"),
                    "seq": ev.seq,
                }
        inc = chosen
    if inc is None or not inc.get("adapter"):
        raise FileNotFoundError("nothing promoted yet: the ledger has no promote row with an adapter")
    if st.badges.get(inc["candidate_id"]) != "green":
        raise PermissionError(
            f"{inc['candidate_id']} is not green (badge {st.badges.get(inc['candidate_id'])}); refusing to export"
        )
    src = Path(inc["adapter"])
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for p in src.iterdir():
        if p.is_file():
            shutil.copy2(p, dest / p.name)
    manifest = {
        "candidate_id": inc["candidate_id"],
        "night": inc["night"],
        "promote_seq": inc["seq"],
        "adapter_sha256": inc["merge_commit"],
        "ledger_head": st.ledger_head,
        "state_hash": st.state_hash,
        "badge": st.badges.get(inc["candidate_id"]),
        "note": "LoRA adapter; apply with PEFT on the base model named in the ledger's bucket",
    }
    (dest / "pravrudhi_export.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest
