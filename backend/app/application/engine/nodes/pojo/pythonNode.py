from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal

from .baseNode import BaseNode


@dataclass(frozen=True, kw_only=True)
class PythonNode(BaseNode):
    handler: Callable[..., Awaitable[Any]] | None = None
    phase: Literal["pre_llm", "post_llm"] = "pre_llm"