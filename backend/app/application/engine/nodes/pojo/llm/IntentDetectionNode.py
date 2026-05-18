from dataclasses import dataclass, field
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.rules.Rule import Rule
from app.application.contracts.contracts import IntentDetectionContract
from app.application.engine.taskType import TaskType
from app.application.engine.validation.validators.IntentDetectionValidator import IntentDetectionValidator


@dataclass(frozen=True, kw_only=True)
class IntentDetectionNode(LLMNode):
    id: str = "intent_detection"
    name: str = "Intent Detection"

    validator: type = IntentDetectionValidator
    contract_json: type = IntentDetectionContract
    dsl: str = "intent_detection"
    temperature: float = 0.2
    retry_policy: dict = field(default_factory=lambda: {"enabled": True})

    supported_tasks: list = field(default_factory=lambda: [TaskType.CHAT])
    rules: list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps: list = field(default_factory=list)

    #Error_name: dsl_File_Name
    dsl_patches: dict = field(default_factory=lambda: {
        "tone_violation":   "intent_detection_repair_tone",
        "missing_intent":   "intent_detection_repair_missing_intent",
        "low_confidence":   "intent_detection_repair_confidence"
    })