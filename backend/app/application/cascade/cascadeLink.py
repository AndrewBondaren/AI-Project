"""Scope-boundary link — tz_cascade_context §2, §4.

A link is ``{level, obj}``: the caller converts its runtime/persistence
object into the source POJO that declares cascade channels, and passes
it at the boundary where a new scope level appears. ``EmptyLink`` marks
a deliberately empty level (no object) — the level is declared, never
skipped silently.
"""

from dataclasses import dataclass

from pydantic import BaseModel

from app.dataModel.cascade.cascadeSpec import ScopeAxis


@dataclass(frozen=True)
class Link:
    """One provided source object at a scope level."""

    level: ScopeAxis
    obj: BaseModel | None


class EmptyLink(Link):
    """Explicit empty link — the level exists, the object does not."""

    def __init__(self, level: ScopeAxis):
        super().__init__(level, None)
