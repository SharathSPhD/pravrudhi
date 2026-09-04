from pydantic import Field

from pravrudhi_kernel.schema.common import KernelModel


class NormalBelief(KernelModel):
    mu: float
    tau2: float = Field(gt=0.0)
    n: int = Field(ge=0)


class CandidateBelief(KernelModel):
    mu: float
    sigma2: float = Field(gt=0.0)
    n_obs: int = Field(ge=0)


class Citta(KernelModel):
    """Hierarchical posterior keyed by surface, by (surface, bucket) and by candidate.

    Replayed from the ledger, never edited.
    """

    version: int = Field(ge=0)
    surfaces: dict[str, NormalBelief]
    buckets: dict[str, NormalBelief]
    candidates: dict[str, CandidateBelief]
    rho_pred: dict[str, float]
