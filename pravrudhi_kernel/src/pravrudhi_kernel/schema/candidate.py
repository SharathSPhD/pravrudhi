from pydantic import Field, field_validator

from pravrudhi_kernel.schema.common import (
    AbstractionLevel,
    Bucket,
    CandidateId,
    KernelModel,
    Pramana,
    Residency,
    Sha256,
    Surface,
)


class Prediction(KernelModel):
    delta_in: float
    delta_out: float | None
    conf: float = Field(ge=0.0, le=1.0)
    hash: Sha256


class Candidate(KernelModel):
    id: CandidateId
    surface: Surface
    bucket: Bucket
    edit_family: str
    strategy: str | None = None  # ADR-0005: strategy-level family (e.g. sft_rejection, grpo_verifiable)
    lineage: list[CandidateId]
    diff_ref: Sha256
    cost_est_gpu_h: float = Field(ge=0.0)
    residency_need: Residency
    predicted: Prediction
    abstraction_level: AbstractionLevel
    provenance: Pramana = Pramana.agama

    @field_validator("provenance")
    @classmethod
    def _born_as_agama(cls, v: Pramana) -> Pramana:
        if v != Pramana.agama:
            raise ValueError("a Candidate is agama until executed; observations carry other provenance")
        return v
