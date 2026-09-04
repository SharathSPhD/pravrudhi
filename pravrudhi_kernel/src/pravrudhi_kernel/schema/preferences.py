from typing import Literal

from pydantic import ConfigDict, Field

from pravrudhi_kernel.schema.candidate import Candidate
from pravrudhi_kernel.schema.common import KernelModel, Surface


class Preferences(KernelModel):
    """Prior preferences C. The −∞ term for T0 is a validator, not a float."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True, populate_by_name=True)

    beta: float = Field(gt=0.0)
    lambda_: float = Field(ge=0.0, alias="lambda")
    eta: float = Field(ge=0.0)
    t0_forbidden: Literal[True] = True

    def admits(self, cand: Candidate) -> bool:
        return cand.surface != Surface.T0_kernel
