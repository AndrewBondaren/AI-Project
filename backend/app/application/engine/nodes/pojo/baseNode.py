from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional, Type

from app.application.engine.taskType import TaskType
from app.application.engine.nodes.pojo.nodeCost import NodeCost
from app.application.engine.rules.Rule import Rule

@dataclass(frozen=True, kw_only=True)
class BaseNode:
    id: str
    name: str
    supported_tasks: list[TaskType]
    rules: list[Rule]
    deps: list[str] = field(default_factory=list)

#    executor: Optional[type] = None
    retry_policy: Optional[dict] = None
    validator: type | None = None
    possible_errors: list[type] = field(default_factory=list)

    priority: int = 50
    cost: NodeCost = field(default_factory=NodeCost)
#    repair_policy: RepairPolicy | None = None

    context_fields: ClassVar[list[str]] = []

#    tags: list[str] = field(default_factory=list)