"""DAG execution identifiers, not world entity IDs. SoT: tz_engine_node_context §6."""

from typing import Annotated, NewType

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


NodeId = NewType("NodeId", str)
ExecutionId = NewType("ExecutionId", str)
InvocationId = NewType("InvocationId", str)
PlanInstanceId = NewType("PlanInstanceId", str)
CallKey = NewType("CallKey", str)
WaitId = NewType("WaitId", str)
ContractId = NewType("ContractId", str)
ContractVersion = NewType("ContractVersion", str)
PlanRevision = NewType("PlanRevision", str)
DomainRevision = NewType("DomainRevision", str)

_IDENTIFIER = StringConstraints(strict=True, min_length=1, pattern=r"^\S(?:.*\S)?$")
type InvocationIdValue = Annotated[InvocationId, _IDENTIFIER]
type PlanInstanceIdValue = Annotated[PlanInstanceId, _IDENTIFIER]
type CallKeyValue = Annotated[CallKey, _IDENTIFIER]
type WaitIdValue = Annotated[WaitId, _IDENTIFIER]
type Ordinal = Annotated[int, Field(strict=True, ge=0)]
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
    invocation_id: InvocationIdValue
    node_id: NodeIdValue
    attempt: Attempt
    plan_revision: PlanRevisionValue

    @property
    def result_key(self) -> tuple[ExecutionId, InvocationId, int]:
        """Plan revision is provenance, not part of the result's address."""
        return self.execution_id, self.invocation_id, self.attempt
