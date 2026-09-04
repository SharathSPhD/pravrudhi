from pydantic import Field

from pravrudhi_kernel.schema.common import CandidateId, Isolation, KernelModel, Pramana, Sha256


class Observation(KernelModel):
    candidate_id: CandidateId
    per_item_scores_ref: str
    delta_in: float
    delta_out: float | None
    n_items: int = Field(ge=1)
    seeds: list[int] = Field(min_length=1)
    cost_gpu_h: float = Field(ge=0.0)
    sensor_reads: dict[str, float]
    provenance: Pramana
    run_hash: Sha256
    isolation: Isolation
