from dataclasses import dataclass, field
from typing import Optional, Type

from .baseNode import BaseNode

@dataclass(frozen=True, kw_only=True)
class LLMNode(BaseNode):

    dsl: str = field(default="")
    temperature: float = field(default=0.0)
    contract_json: Optional[Type] = field(default=None)
    dsl_patches: dict = field(default_factory=dict)