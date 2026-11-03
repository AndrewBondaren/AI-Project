from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Collection, Mapping

from app.dataModel.engine.dag.identity import InvocationId, NodeId, PlanInstanceId


@dataclass(frozen=True)
class PlanInstance:
    id: PlanInstanceId
    bindings: Mapping[NodeId, InvocationId]

    @classmethod
    def bind(cls, instance: PlanInstanceId, nodes: Collection[NodeId]) -> "PlanInstance":
        return cls(instance, MappingProxyType({node: InvocationId(f"{instance}/{node}") for node in nodes}))
