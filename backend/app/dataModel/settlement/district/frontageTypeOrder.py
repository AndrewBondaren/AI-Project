"""Engine default `connection_type` order for C22 frontage — tz_structure_connections.md §5.1.3."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from app.dataModel.annotationPolicy import DefaultOnWire


class FrontageTypeOrder(BaseModel):
    """Resolve fallback when district and settlement omit `frontage_type_order`."""

    SCHEMA_ID: ClassVar[str] = "SCH-FRONTAGE-TYPE-ORDER"

    model_config = ConfigDict(extra="ignore", frozen=True)

    order: DefaultOnWire[list[str]] = Field(
        default_factory=lambda: ["highway", "road", "dirt_road", "alley", "trail"],
    )

    @classmethod
    def canonical_defaults(cls) -> FrontageTypeOrder:
        return cls()


def _filter_known(
    order: list[str],
    known_types: frozenset[str],
) -> tuple[list[str], list[str]]:
    kept: list[str] = []
    skipped: list[str] = []
    for key in order:
        if key in known_types:
            kept.append(key)
        else:
            skipped.append(key)
    return kept, skipped


def resolve_frontage_type_order(
    district_order: list[str] | None,
    settlement_order: list[str] | None,
    known_types: frozenset[str],
) -> tuple[list[str], list[str]]:
    """
    District → settlement → FrontageTypeOrder.canonical_defaults().
    Empty / null inherits. Unknown keys skipped; empty after skip inherits.
    Returns (resolved order, skipped unknown from the winning level).
    """
    engine = list(FrontageTypeOrder.canonical_defaults().order)
    for candidate in (district_order, settlement_order, engine):
        if not candidate:
            continue
        kept, skipped = _filter_known(list(candidate), known_types)
        if kept:
            return kept, skipped
    return engine, []
