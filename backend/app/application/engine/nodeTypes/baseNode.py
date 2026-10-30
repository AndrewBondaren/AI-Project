"""Typed node interface, independent of production registration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.contracts.dagReadView import DAGReadView
from app.application.engine.nodeTypes.support.nodeCost import NodeCost
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.dataModel.engine.dag.identity import NodeId

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


@dataclass(frozen=True, kw_only=True)
class BaseNode(ABC, Generic[I, O, E]):
    id: NodeId
    name: str = ""
    supported_tasks: tuple[TaskType, ...] = ()
    rules: tuple[Rule, ...] = ()
    deps: tuple[NodeId, ...] = ()
    priority: int = 50
    cost: NodeCost = field(default_factory=NodeCost)

    @abstractmethod
    async def prepare_input(self, view: DAGReadView) -> I: ...
