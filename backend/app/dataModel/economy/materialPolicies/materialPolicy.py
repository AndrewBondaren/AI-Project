"""Typed contract for material policy consumers — tz_economic_tier.md §11.

Independent economics / NPC-behaviour decision layer. The wall generator is
the first caller; future player/NPC construction reuses the same contract.
Consumers receive prepared data only — no geometry, no registry/DB lookups,
no RNG.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.economy.economyTier.worldEconomyTierRegistry import (
    EconomyTierKey,
)
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand


class MaterialPolicy(StrEnum):
    """Explicit selection policy — §11.3 first policies compare strength."""

    MAX_STRENGTH = "max_strength"
    MIN_STRENGTH = "min_strength"


class MaterialCandidate(BaseModel):
    """Resolved material source prepared by the caller (MAT-T-1 boundary).

    `structural_strength` comes from the material registry; `None` is a real
    state (never equate to zero — §11.5). `source_area` is the source room's
    footprint area used for the §11.3 tie-break — the consumer computes no
    geometry itself.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    system_material: str
    structural_strength: float | None = Field(default=None, ge=0.0, le=1.0)
    source_key: str
    source_area: int = Field(ge=0)


class BuildingEconomicContext(BaseModel):
    """Building context resolved by the caller via the full §4 cascade.

    Required — absence after the cascade is a caller bug and a reason for an
    error, not a silent band inside the consumer (§11.2). `band` is resolved
    via the existing §3 registry mapping.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    economic_tier: EconomyTierKey
    band: EconomicTierBand


class MaterialPolicyRequest(BaseModel):
    """Consumer input — §11.2. `candidates` order must be deterministic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[MaterialCandidate, ...]
    # Stub contract: no authored policy source exists in this slice — callers
    # always pass None. Where an authored policy will live and how it reaches
    # callers remains an open question: tz_economic_tier.md §11.5.
    policy: MaterialPolicy | None = None
    context: BuildingEconomicContext


class MaterialPolicyFailure(StrEnum):
    """Structured cause when no candidate can be chosen — §11.2."""

    NO_CANDIDATES = "no_candidates"
    # MAT-T-1: a resolved key does not guarantee numeric structural_strength.
    MISSING_STRENGTH = "missing_strength"


class MaterialPolicyDecision(BaseModel):
    """Consumer output: chosen candidate + reason, or a structured failure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: MaterialCandidate | None = None
    policy: MaterialPolicy
    failure: MaterialPolicyFailure | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _exactly_one_outcome(self) -> "MaterialPolicyDecision":
        if (self.candidate is None) == (self.failure is None):
            raise ValueError("exactly one of candidate/failure is required")
        return self
