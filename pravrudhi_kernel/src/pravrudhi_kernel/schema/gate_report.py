from typing import Literal

from pydantic import model_validator

from pravrudhi_kernel.schema.common import Hetvabhasa, KernelModel, MeasureClass, Stage

Verdict = Literal["pass", "fail", "pruned", "pending"]


class GateSide(KernelModel):
    verdict: Verdict
    evidence: list[str]


class Layer(KernelModel):
    verdict: Verdict
    evidence: list[str]


class ClosureReport(KernelModel):
    technical: Layer
    empirical: Layer
    integrity: Layer
    artifacts: Layer
    memory: Layer
    signoff: Layer


class Deviation(KernelModel):
    what: str
    why: str
    adr: str | None


class Signoff(KernelModel):
    by: str | None
    at: str | None
    note: str | None


class GateReport(KernelModel):
    """Loop / hypothesis / phase gate (02-design/06-evaluation-and-statistics.md §12)."""

    id: str
    kind: Literal["loop", "hypothesis", "phase", "epoch"]
    status: Literal["pass", "fail", "pruned", "in_progress"]
    tier: Stage
    measure_class: MeasureClass
    code_gate: GateSide
    domain_gate: GateSide
    closure: ClosureReport
    hetvabhasa: Hetvabhasa | None
    deviations: list[Deviation]
    signoff: Signoff
    ledger_head: str | None
    kernel_release: str

    @model_validator(mode="after")
    def _dual_closure(self) -> "GateReport":
        if self.status == "pruned" and self.hetvabhasa is None:
            raise ValueError("pruned closure requires a hetvabhasa label")
        if self.status == "pass":
            if not (self.code_gate.verdict == "pass" and self.domain_gate.verdict == "pass"):
                raise ValueError("status pass requires code_gate and domain_gate both pass")
            for name in ("technical", "empirical", "integrity", "artifacts", "memory"):
                if getattr(self.closure, name).verdict != "pass":
                    raise ValueError(f"status pass requires closure.{name} == pass")
            if self.closure.signoff.verdict not in ("pass", "pending"):
                raise ValueError("closure.signoff must be pass or pending")
        return self
