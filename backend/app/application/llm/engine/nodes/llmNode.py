from dataclasses import dataclass
from typing import Optional, Type

from .baseNode import BaseNode


@dataclass
class LLMNode(BaseNode):
    dsl: str = ""
    contract: Optional[Type] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 1024