from dataclasses import dataclass, field
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.nodes.nodeRegistry import register
from app.application.engine.rules.Rule import Rule
from app.application.engine.execution.llmNodeExecutor import LLMNodeExecutor
from app.application.contracts.contracts import IntentDetectionContract
from app.application.engine.taskType import TaskType
from app.application.engine.validation.validators.IntentDetectionValidator import IntentDetectionValidator


@register(executor_cls=LLMNodeExecutor)
@dataclass(frozen=True)
class IntentDetectionNode(LLMNode):

    id: str = "intent_detection"
    name: str = "Intent Detection"

    dsl: str = "intent_detection"
    contract_json: type = IntentDetectionContract
    validator: type = IntentDetectionValidator
    temperature: float = 0.2
    retry_policy: dict = field(default_factory=lambda: {"enabled": True})

    supported_tasks: list = field(default_factory=lambda: [TaskType.CHAT])
    rules: list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps: list = field(default_factory=lambda: ["intent_detection"])