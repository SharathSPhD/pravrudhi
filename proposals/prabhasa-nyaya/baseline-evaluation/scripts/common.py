"""Shared types and result-writing helpers for the baseline-evaluation proposal.

Nothing in this module writes outside the proposal's own output/ directory.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
from pathlib import Path
from typing import Any


@dataclasses.dataclass
class ToolResult:
    """One declared external tool's baseline result.

    `metrics` must use the tool's own native metric names, unmodified —
    this record is a pass-through, not a reinterpretation.
    """

    tool_name: str
    tool_version: str
    base_model: str
    sample_count: int
    metrics: dict[str, float]
    timestamp: str
    error: str | None = None

    @classmethod
    def failed(
        cls,
        tool_name: str,
        tool_version: str,
        base_model: str,
        sample_count: int,
        error: str,
    ) -> "ToolResult":
        return cls(
            tool_name=tool_name,
            tool_version=tool_version,
            base_model=base_model,
            sample_count=sample_count,
            metrics={},
            timestamp=now_iso(),
            error=error,
        )


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def write_results(results: list[ToolResult], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "step": "baseline-evaluation",
        "capability": "evaluate",
        "generated_at": now_iso(),
        "note": "PROPOSAL OUTPUT ONLY — not a ledger entry, not a measured result claim.",
        "results": [dataclasses.asdict(r) for r in results],
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
