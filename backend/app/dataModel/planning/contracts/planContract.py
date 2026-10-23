"""Provider declaration metadata, with no current world state or executable codec."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.registryKey import RegistryKey

class PlanContractRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    entries: tuple[PlanContractMetadata, ...]

    @model_validator(mode="after")
    def unique_ids(self) -> PlanContractRegistry:
        if len({entry.id for entry in self.entries}) != len(self.entries):
            raise ValueError("duplicate plan contract id")
        return self


type PlanContractId = RegistryKey[PlanContractRegistry]

# Keep the nominal registry available while the identity module imports its id.
from app.dataModel.planning.identity.planKey import AlgorithmVersion, SchemaVersion


class PlanContractMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    id: PlanContractId
    schema_version: SchemaVersion = Field(strict=True, gt=0)
    algorithm_version: AlgorithmVersion = Field(strict=True, gt=0)


PlanContractRegistry.model_rebuild()
