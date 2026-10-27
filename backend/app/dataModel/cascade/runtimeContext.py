"""Shared transient cascade state; domain contexts declare their own parameters."""

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from app.dataModel.cascade.cascadeGraph import CascadeNode
from app.dataModel.cascade.cascadeSpec import Cascade, ScopeAxis

AxisT = TypeVar("AxisT", bound=ScopeAxis)
type CascadeSource = tuple[ScopeAxis, str]
type CascadeNodeResult = tuple[object, CascadeSource | None]


class CascadeRuntimeContext(BaseModel, Generic[AxisT]):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: AxisT
    provenance: dict[str, tuple[AxisT, str]] = Field(default_factory=dict)

    _world: object | None = PrivateAttr(default=None)
    _links: dict[ScopeAxis, tuple[BaseModel, ...]] = PrivateAttr(default_factory=dict)
    _scope_path: tuple[ScopeAxis, ...] = PrivateAttr(default=())
    _node_results: dict[tuple[Cascade, CascadeNode], CascadeNodeResult] = PrivateAttr(default_factory=dict)
    _default_sources: tuple[BaseModel, ...] = PrivateAttr(default=())

    @classmethod
    def at_root(cls, level: AxisT, world: object, *, default_sources: tuple[BaseModel, ...] = ()) -> Self:
        """Capture terminal POJOs without resolving defaults, sources or RNG."""
        context = cls(level=level)
        context._world = world
        context._default_sources = tuple(source.model_copy(deep=True) for source in default_sources)
        return context
