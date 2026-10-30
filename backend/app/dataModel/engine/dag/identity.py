"""DAG execution identifiers, not world entity IDs. SoT: tz_engine_node_context §6."""

from typing import Annotated, NewType

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NodeId = NewType("NodeId", str)
ExecutionId = NewType("ExecutionId", str)
ContractId = NewType("ContractId", str)
ContractVersion = NewType("ContractVersion", str)
PlanRevision = NewType("PlanRevision", str)
DomainRevision = NewType("DomainRevision", str)

_IDENTIFIER = StringConstraints(strict=True, min_length=1, pattern=r"^\S(?:.*\S)?$")
type NodeIdValue = Annotated[NodeId, _IDENTIFIER]
type ExecutionIdValue = Annotated[ExecutionId, _IDENTIFIER]
type ContractIdValue = Annotated[ContractId, _IDENTIFIER]
type ContractVersionValue = Annotated[ContractVersion, _IDENTIFIER]
type PlanRevisionValue = Annotated[PlanRevision, _IDENTIFIER]
type DomainRevisionValue = Annotated[DomainRevision, _IDENTIFIER]
type Attempt = Annotated[int, Field(strict=True, gt=0)]


class ExecutionIdentity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, revalidate_instances="always")

    execution_id: ExecutionIdValue
    node_id: NodeIdValue
    attempt: Attempt
    plan_revision: PlanRevisionValue

    @property
    def result_key(self) -> tuple[ExecutionId, NodeId, int]:
        """Plan revision is provenance, not part of the result's address."""
        return self.execution_id, self.node_id, self.attempt
