from typing import Callable, Awaitable, Any

from .baseNode import BaseNode


class PythonNode(BaseNode):

    handler: Callable[..., Awaitable[Any]] | None = None