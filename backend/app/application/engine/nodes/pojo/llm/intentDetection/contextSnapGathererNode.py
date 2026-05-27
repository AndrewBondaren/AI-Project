from dataclasses import dataclass, field
from typing import ClassVar

from app.application.contracts.contracts import ContextSnapContract
from app.application.engine.nodes.nodeRegistry import register_llm
from app.application.engine.nodes.pojo.llmNode import LLMNode
from app.application.engine.rules.rule import Rule
from app.application.engine.taskType import TaskType
from app.application.engine.validation.validators.contextSnapGathererValidator import ContextSnapGathererValidator


@register_llm()
@dataclass(frozen=True, kw_only=True)
class ContextSnapGathererNode(LLMNode):
    id: str = "context_snap_gatherer"
    name: str = "Context Snap Gatherer"
    context_fields: ClassVar[list[str]] = []

    validator: type = ContextSnapGathererValidator
    contract_json: type = ContextSnapContract
    dsl: str = "context_snap_gatherer/context_snap_gatherer"
    temperature: float = 0.2
    retry_policy: dict = field(default_factory=lambda: {"enabled": True})

    supported_tasks: list = field(default_factory=lambda: [TaskType.INTENT_DETECTION])
    rules: list = field(default_factory=lambda: [Rule(type="task", params={})])
    deps: list = field(default_factory=lambda: ["check_scene"])

    dsl_patches: dict = field(default_factory=lambda: {
        "missing_location":    "context_snap_gatherer/repair_location",
        "missing_situation":   "context_snap_gatherer/repair_situation",
        "missing_player_state": "context_snap_gatherer/repair_player_state",
        "invalid_actors":      "context_snap_gatherer/repair_actors",
    })