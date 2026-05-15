from typing import Optional, Type

from .baseNode import BaseNode


class LLMNode(BaseNode):

    dsl: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout: Optional[int] = None
    contract_json: Optional[Type] = None