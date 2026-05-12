from dataclasses import dataclass
from typing import Callable

from .baseNode import BaseNode


@dataclass
class PythonNode(BaseNode):

    handler: Callable = None