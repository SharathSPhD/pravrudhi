from typing import Annotated, Any

from pydantic import Field, StringConstraints, model_validator

from pravrudhi_kernel.schema.common import (
    Bucket,
    CandidateId,
    EventKind,
    KernelModel,
    Pramana,
    Sha256,
    Surface,
)

Rfc3339Ms = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")]
Actor = Annotated[
    str,
    StringConstraints(
        pattern=r"^(kernel|broker|controller|proposer|executor|auditor|human:[A-Za-z0-9_.-]+)$"
    ),
]

PROVENANCE_REQUIRED: frozenset[str] = frozenset({"propose", "predict", "observe", "sensor", "sublate"})


class LedgerEvent(KernelModel):
    """Envelope of one ledger line (02-design/08-memory-and-context.md §1.1).

    Payload typing per kind lands in L1.
    """

    seq: int = Field(ge=0)
    t: Rfc3339Ms
    epoch: int = Field(ge=0)
    night: int = Field(ge=0)
    cycle: int | None
    kind: EventKind
    actor: Actor
    candidate_id: CandidateId | None
    surface: Surface | None
    bucket: Bucket | None
    provenance: Pramana | None
    kernel_release: str
    payload: dict[str, Any]
    prev_hash: Sha256
    this_hash: Sha256

    @model_validator(mode="after")
    def _provenance_where_required(self) -> "LedgerEvent":
        if self.kind in PROVENANCE_REQUIRED and self.provenance is None:
            raise ValueError(f"kind {self.kind} requires provenance")
        if self.kind == "observe" and self.actor != "kernel":
            raise ValueError("observe rows are written by the kernel only")
        return self
