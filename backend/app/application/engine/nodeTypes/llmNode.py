from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Generic, TypeVar

from pydantic import BaseModel, FiniteFloat, TypeAdapter

from app.dataModel.engine.dag.errors.nodeError import NodeError

from app.application.engine.nodeTypes.baseNode import BaseNode

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)
E = TypeVar("E", bound=NodeError)


@dataclass(frozen=True, kw_only=True)
class LLMNode(BaseNode[I, O, E], Generic[I, O, E]):
    dsl: str = ""
    temperature: FiniteFloat = 0.0
    enable_thinking: bool = False
    dsl_patches: Mapping[str, str] = field(default_factory=lambda: MappingProxyType[str, str]({}))

    def __post_init__(self) -> None:
        TypeAdapter(FiniteFloat).validate_python(self.temperature, strict=True)
        patches = TypeAdapter(dict[str, str]).validate_python(dict(self.dsl_patches), strict=True)
        object.__setattr__(self, "dsl_patches", MappingProxyType(patches))
