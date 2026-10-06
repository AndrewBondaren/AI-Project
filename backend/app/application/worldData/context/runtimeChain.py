"""Bind declared field links to runtime POJOs — tz_cascade_context §4."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.dataModel.cascade.cascadeGraph import ordered_chain
from app.dataModel.cascade.cascadeSpec import (
    Cascade, CascadeChannel, CascadeLink, ScopeAxis,
)


@dataclass(frozen=True)
class BoundChannel:
    node: CascadeLink
    channel: CascadeChannel
    obj: BaseModel | None

    @property
    def source(self) -> tuple[ScopeAxis, str]:
        return self.node.level, f"{self.node.model.__name__}.{self.node.field}"


def bind_chain(
    param: Cascade,
    sources: Mapping[ScopeAxis, tuple[BaseModel, ...]],
) -> Iterator[BoundChannel]:
    """One iterator in declared priority order, including empty nodes."""
    for owner, node, channel in ordered_chain(param):
        matches = [obj for obj in sources.get(node.level, ())
                   if isinstance(obj, owner)]
        if len(matches) > 1:
            raise ValueError(
                f"ambiguous source objects for {owner.__name__}"
                f".{node.field}@{node.level.value}"
            )
        yield BoundChannel(node, channel, matches[0] if matches else None)
