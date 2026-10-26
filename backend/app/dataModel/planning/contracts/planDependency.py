"""Declared and resolved dependencies; slots have one canonical UTF-8 order."""

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.planning.contracts.planContract import PlanContractId
from app.dataModel.planning.identity.planKey import AlgorithmVersion, PlanSlot, SchemaVersion
from app.dataModel.planning.identity.planRef import PlanRef


class PlanDependency(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    slot: PlanSlot = Field(strict=True, min_length=1)
    ref: PlanRef


class PlanDependencyContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, revalidate_instances="always")

    slot: PlanSlot = Field(strict=True, min_length=1)
    contract_id: PlanContractId
    schema_version: SchemaVersion = Field(strict=True, gt=0)
    algorithm_version: AlgorithmVersion = Field(strict=True, gt=0)

    def accepts(self, dependency: PlanDependency) -> bool:
        """Compare declaration metadata only; payload admission belongs to application."""
        key = dependency.ref.key
        return (self.slot == dependency.slot and self.contract_id == key.contract_id
                and self.schema_version == key.schema_version
                and self.algorithm_version == key.algorithm_version)


def require_canonical_dependencies(dependencies: tuple[PlanDependency, ...]) -> tuple[PlanDependency, ...]:
    slots = tuple(dependency.slot for dependency in dependencies)
    if len(set(slots)) != len(slots):
        raise ValueError("duplicate dependency slot")
    if slots != tuple(sorted(slots, key=lambda slot: slot.encode("utf-8"))):
        raise ValueError("dependency slots must be in canonical UTF-8 order")
    return dependencies
