from pydantic import Field

from pravrudhi_kernel.schema.common import KernelModel, Stage


class EvidencePlan(KernelModel):
    seeds: list[int] = Field(min_length=1)
    heldout_rotation_id: str | None
    sensors_to_read: list[str]
    stage: Stage
    sequential_stage: int = Field(ge=0)
