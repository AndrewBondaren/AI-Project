from typing import Optional, Type

from .baseNode import BaseNode


class LLMNode(BaseNode):

    dsl: str = ""
    temperature: float = 0.0
    contract_json: Optional[Type] = None