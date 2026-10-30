"""Small immutable test contracts; never production node schemas."""

from pydantic import BaseModel, ConfigDict

from app.dataModel.engine.dag.identity import (
    ExecutionId, ExecutionIdentity, NodeId, PlanRevision,
)


class LeafOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    value: int


class CompositeOutput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", revalidate_instances="always")
    leaves: tuple[LeafOutput, ...]


def identity(node: str = "producer", attempt: int = 1) -> ExecutionIdentity:
    return ExecutionIdentity(
        execution_id=ExecutionId("execution-1"), node_id=NodeId(node),
        attempt=attempt, plan_revision=PlanRevision("plan-1"),
    )
