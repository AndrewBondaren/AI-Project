from dataclasses import dataclass, field
from typing import ClassVar

from app.application.contracts.contracts import IntentDetectionContract
from app.application.engine.nodes.nodeRegistry import register_llm
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.application.engine.validation.validators.intentDetectionValidator import IntentDetectionValidator


@register_llm()
@dataclass(frozen=True, kw_only=True)
class IntentDetectionNode(LLMNode):
    id: str = "intent_detection"
    name: str = "Intent Detection"
    context_fields: ClassVar[list[str]] = []

    validator: type = IntentDetectionValidator
    contract_json: type = IntentDetectionContract
    dsl: str = "intent_detection/intent_detection"
    temperature: float = 0.2
    retry_policy: dict = field(default_factory=lambda: {"enabled": True})

    supported_tasks: list = field(default_factory=lambda: [TaskType.INTENT_DETECTION])
    rules: list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps: list = field(default_factory=list)

    #Error_name: dsl_File_Name
    dsl_patches: dict = field(default_factory=lambda: {
        "tone_violation":   "intent_detection/repair_tone",
        "missing_intent":   "intent_detection/repair_missing_intent",
        "low_confidence":   "intent_detection/repair_confidence"
    })
