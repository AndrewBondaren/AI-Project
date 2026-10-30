from dataclasses import dataclass
from typing import Generic, TypeVar, cast

from pydantic import BaseModel

from app.application.engine.contracts.nodeContract import NodeContract
from app.application.engine.contracts.pythonExecutor import PythonExecutor
from app.application.engine.nodeTypes.baseNode import BaseNode
from app.application.engine.nodeTypes.support.nodeKind import NodeKind
from app.dataModel.engine.dag.identity import NodeId

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True)
class NodeRegistration(Generic[I, O]):
    node_id: NodeId
    node_cls: type[BaseNode[I, O]]
    kind: NodeKind
    contract: NodeContract[I, O]
    executor_cls: type[PythonExecutor] | None = None

    def validate_node(self, node: object) -> BaseNode[I, O]:
        """Admission of a request-local factory result, without constructing it."""
        if not isinstance(node, self.node_cls):
            raise TypeError(f"factory returned a node outside binding '{self.node_id}'")
        # Generic erasure is confined to this checked admission boundary.
        admitted = cast(BaseNode[I, O], node)
        if admitted.id != self.node_id:
            raise TypeError(f"factory returned a node outside binding '{self.node_id}'")
        return admitted
