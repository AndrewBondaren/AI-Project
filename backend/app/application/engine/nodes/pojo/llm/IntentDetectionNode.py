from dataclasses import dataclass, field
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.nodes.nodeRegistry import register
from app.application.engine.rules.Rule import Rule
from app.application.engine.execution.llmNodeExecutor import LLMNodeExecutor
from app.application.contracts.contracts import NarrationContract
from app.application.engine.taskType import TaskType


@register(executor_cls=LLMNodeExecutor)
@dataclass(frozen=True)
class ResponseGenerationNode(LLMNode):

    id: str = "response_generation"
    name: str = "Response Generation"

    dsl: str = "chat_response"
    contract: type = NarrationContract
    temperature: float = 0.5

    supported_tasks: list = field(default_factory=lambda: [TaskType.CHAT])
    rules: list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps: list = field(default_factory=lambda: ["intent_detection"])