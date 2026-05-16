from dataclasses import field
from typing import Callable, Awaitable, Any, Literal

from .baseNode import BaseNode


class PythonNode(BaseNode):

    handler: Callable[..., Awaitable[Any]] | None = None
    phase: Literal["pre_llm", "post_llm"] = field(default="pre_llm")