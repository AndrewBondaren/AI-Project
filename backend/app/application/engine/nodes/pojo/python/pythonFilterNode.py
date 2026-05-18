from dataclasses import dataclass
from typing import Callable, Awaitable, Any, Optional
from app.application.engine.nodes.pojo.baseNode import BaseNode
from app.application.engine.execution.pythonNodeExecutor import PythonNodeExecutor
from app.application.engine.nodes.nodeRegistry import register


@dataclass(frozen=True)
class PythonNode(BaseNode):
    handler: Optional[Callable[..., Awaitable[Any]]] = None


@register(executor_cls=PythonNodeExecutor)
@dataclass(frozen=True)
class PythonFilterNode(PythonNode):
    id: str = "python_filter_node"
    name: str = "Python Filter"