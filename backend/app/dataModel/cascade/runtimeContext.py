"""Shared transient cascade state; domain contexts declare their own parameters."""

from typing import Generic, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

from app.dataModel.cascade.cascadeGraph import CascadeNode
from app.dataModel.cascade.cascadeSpec import Cascade, ScopeAxis
from app.dataModel.validation.immutableValue import _complete_record, validate_immutable

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


class ResolvedCascadeState(BaseModel, Generic[AxisT], frozen=True):
    """Immutable resolved values, without the resolver's world or working state."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid", revalidate_instances="always")

    level: AxisT
    provenance: tuple[tuple[str, tuple[AxisT, str]], ...]

    @model_validator(mode="after")
    def complete_provenance(self) -> Self:
        names = tuple(name for name, _ in self.provenance)
        parameters = set(type(self).model_fields) - set(ResolvedCascadeState.model_fields)
        if len(set(names)) != len(names) or names != tuple(sorted(names)) or set(names) != parameters:
            raise ValueError("resolved provenance must name each parameter once in sorted order")
        if any(type(scope) is not type(self.level) or not path.strip() for _, (scope, path) in self.provenance):
            raise ValueError("resolved provenance requires the same scope axis and a source path")
        return self


ResultT = TypeVar("ResultT", bound=ResolvedCascadeState)


def freeze_resolved_context(ctx: CascadeRuntimeContext, result_type: type[ResultT]) -> ResultT:
    """Project declared values; do not resolve defaults or copy private runtime data."""
    if not isinstance(ctx, CascadeRuntimeContext):
        raise TypeError("freeze requires a cascade runtime context")
    if not isinstance(result_type, type) or not issubclass(result_type, ResolvedCascadeState):
        raise TypeError("freeze requires a ResolvedCascadeState subtype")
    config = result_type.model_config
    if not (config.get("frozen") and config.get("strict") and config.get("extra") == "forbid"
            and config.get("revalidate_instances") == "always"):
        raise ValueError("resolved result must be strict, frozen, forbid extras and revalidate instances")
    if result_type.__private_attributes__ or result_type.model_computed_fields:
        raise ValueError("resolved result cannot contain private state or computed fields")
    if any(not field.is_required() for field in result_type.model_fields.values()):
        raise ValueError("resolved result fields must be required without defaults")
    _complete_record(ctx)
    if result_type.model_fields["level"].annotation is not type(ctx.level):
        raise ValueError("resolved result belongs to a different scope axis")
    parameters = {name for name, field in type(ctx).model_fields.items()
                  if any(isinstance(meta, Cascade) for meta in field.metadata)}
    if set(result_type.model_fields) - set(ResolvedCascadeState.model_fields) != parameters:
        raise ValueError("resolved result must contain exactly the declared cascade parameters")
    if set(ctx.provenance) != parameters:
        raise ValueError("runtime provenance must cover all declared parameters")
    values = {name: getattr(ctx, name) for name in result_type.model_fields}
    values["provenance"] = tuple(sorted(ctx.provenance.items()))
    result = result_type.model_validate(values)
    validate_immutable(result)
    return result
