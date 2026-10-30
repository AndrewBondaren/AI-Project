"""Version and attempt metadata for memory resume. SoT: tz_engine_node_context §9."""

from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.engine.dag.identity import (
    Attempt,
    ContractIdValue,
    ContractVersionValue,
    ExecutionIdValue,
    NodeIdValue,
    PlanRevisionValue,
)


class SnapshotMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    format_version: Annotated[int, Field(strict=True, gt=0)]
    execution_id: ExecutionIdValue
    plan_revision: PlanRevisionValue
    pass_number: Annotated[int, Field(strict=True, ge=0)]
    contract_versions: tuple[tuple[ContractIdValue, ContractVersionValue], ...]
    attempt_counters: tuple[tuple[NodeIdValue, Attempt], ...]

    @model_validator(mode="after")
    def check_unique_keys(self) -> Self:
        contracts = [key for key, _ in self.contract_versions]
        nodes = [key for key, _ in self.attempt_counters]
        if len(contracts) != len(set(contracts)):
            raise ValueError("duplicate contract version entry")
        if len(nodes) != len(set(nodes)):
            raise ValueError("duplicate node attempt counter")
        return self
