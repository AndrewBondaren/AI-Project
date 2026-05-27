from dataclasses import dataclass, field
from typing import Literal

from .baseNode import BaseNode


@dataclass(frozen=True, kw_only=True)
class PythonNode(BaseNode):
    phase: Literal["pre_llm", "post_llm"] = "pre_llm"
    skip_on_replan: bool = True  # False = всегда перезапускать на новом pass (gate-ноды с внешним состоянием)
    possible_errors: list[type] = field(default_factory=list)

    async def execute(self, state, context):
        raise NotImplementedError(f"PythonNode '{self.id}' must implement execute()")
