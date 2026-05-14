from dataclasses import dataclass, field
from typing import Any, Optional, Type

from app.application.engine.taskType import TaskType
from app.application.engine.nodes.pojo.nodeCost import NodeCost
from app.application.engine.rules.Rule import Rule

@dataclass(frozen=True)
class BaseNode:
    id: str
    supported_tasks: list[TaskType]
    name: str
    priority: int = 50
    cost: NodeCost = field(default_factory=NodeCost)

    deps: list[str] = field(default_factory=list)
    executor: Optional[type] = None
    contract: Optional[Type] = None
    rules: list[Rule]
    
    validator: type | None = None
    retry_policy: Optional[dict] = None
#    repair_policy: RepairPolicy | None = None

    possible_errors: list[type] = field(default_factory=list)
#    tags: list[str] = field(default_factory=list)