from typing import Literal

from pydantic import Field

from pravrudhi_kernel.schema.common import KernelModel


class BeliefKeys(KernelModel):
    """Where a candidate sits in the hierarchy: surface > strategy > bucket > candidate (ADR-0005)."""

    surface: str
    strategy: str | None
    bucket: str  # "task_family|target_model|corpus|edit_family"
    candidate_id: str

    @property
    def strategy_key(self) -> str | None:
        return None if self.strategy is None else f"{self.surface}|{self.strategy}"

    @property
    def bucket_key(self) -> str:
        return f"{self.surface}|{self.strategy or '-'}|{self.bucket}"


class Precision(KernelModel):
    epi: float = Field(gt=0.0, le=1.0)
    prag: float = Field(gt=0.0, le=1.0)


class PrecisionView(KernelModel):
    """What infer_precision reads: the live pool's posterior predictive variances and the predictor's reliability."""

    pool_post_var: list[float]
    sigma2_eval: float = Field(gt=0.0)
    rho_pred: float = Field(ge=0.0, le=1.0)
    f_epi: float = Field(gt=0.0, lt=1.0)
    rho_floor: float = Field(gt=0.0, lt=1.0)


class EFETerms(KernelModel):
    candidate_id: str
    G: float
    EIG: float
    pragmatic: float
    cost_term: float
    gamma: Precision
    kappa: float


class Shares(KernelModel):
    planted: float = Field(ge=0.0, lt=1.0)
    sensors: float = Field(ge=0.0, lt=1.0)
    f_epi: float = Field(gt=0.0, lt=1.0)


class SelectionBatch(KernelModel):
    deliberation: list[str]
    execution: list[str]
    exclusive: list[str]
    spent_gpu_h: float
    budget_effective: float
    epistemic_ids: list[str]


class DecorativeVerdict(KernelModel):
    verdict: Literal["pass", "fail"]
    cv_G: float
    mi_bits: float
    reason: str | None
