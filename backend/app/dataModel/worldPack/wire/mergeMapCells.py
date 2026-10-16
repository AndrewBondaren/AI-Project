"""Merge pack layers at read — WP-20 field-wise overlay by priority."""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from app.dataModel.worldPack.layerPriority import LAYER_PRIORITY_ORDER, MapLayerKind

_MERGE_FIELDS: tuple[str, ...] = (
    "system_terrain",
    "system_material",
    "system_building_element",
    "temperature_base",
    "rainfall",
    "location_uid",
    "hydrology",
    "travel_modifier_override",
)


class CellContribution(BaseModel):
    """Partial cell fields from one layer."""

    model_config = ConfigDict(extra="ignore")

    x: int
    y: int
    z: int
    system_terrain: str | None = None
    system_material: str | None = None
    system_building_element: str | None = None
    temperature_base: int | None = None
    rainfall: int | None = None
    location_uid: str | None = None
    hydrology: dict | None = None
    is_structural: bool | None = None
    travel_modifier_override: float | None = None

    def has_data(self) -> bool:
        return any(
            v is not None
            for v in (
                self.system_terrain,
                self.system_material,
                self.system_building_element,
                self.temperature_base,
                self.rainfall,
                self.location_uid,
                self.hydrology,
            )
        )


class LayerSlice(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    kind: MapLayerKind
    cell: CellContribution | None = None


class MergedCellView(BaseModel):
    """Gameplay/debug read model after merge."""

    SCHEMA_ID: ClassVar[str] = "SCH-MERGED-CELL-VIEW"

    model_config = ConfigDict(extra="ignore")

    x: int
    y: int
    z: int
    field_sources: dict[str, MapLayerKind] = {}
    system_terrain: str | None = None
    system_material: str | None = None
    system_building_element: str | None = None
    temperature_base: int | None = None
    rainfall: int | None = None
    location_uid: str | None = None
    hydrology: dict | None = None
    is_structural: bool = False
    travel_modifier_override: float | None = None

    @property
    def source_layer(self) -> MapLayerKind | None:
        """Highest-priority layer among field contributors (debug shorthand)."""
        if not self.field_sources:
            return None
        for kind in LAYER_PRIORITY_ORDER:
            if kind in self.field_sources.values():
                return kind
        return None

    @classmethod
    def empty(cls, x: int, y: int, z: int) -> MergedCellView:
        return cls(x=x, y=y, z=z)

    def has_any_data(self) -> bool:
        return any(
            v is not None
            for v in (
                self.system_terrain,
                self.system_material,
                self.system_building_element,
                self.temperature_base,
                self.rainfall,
                self.location_uid,
                self.hydrology,
            )
        ) or self.is_structural

    @classmethod
    def from_contribution(
        cls,
        cell: CellContribution,
        *,
        source_layer: MapLayerKind,
    ) -> MergedCellView:
        field_sources = {
            field: source_layer
            for field in _MERGE_FIELDS
            if getattr(cell, field) is not None
        }
        if cell.is_structural:
            field_sources["is_structural"] = source_layer
        return cls(
            x=cell.x,
            y=cell.y,
            z=cell.z,
            field_sources=field_sources,
            system_terrain=cell.system_terrain,
            system_material=cell.system_material,
            system_building_element=cell.system_building_element,
            temperature_base=cell.temperature_base,
            rainfall=cell.rainfall,
            location_uid=cell.location_uid,
            hydrology=cell.hydrology,
            is_structural=bool(cell.is_structural),
            travel_modifier_override=cell.travel_modifier_override,
        )


def merge_layers(
    x: int,
    y: int,
    z: int,
    layers: list[LayerSlice],
) -> MergedCellView:
    """Field-wise merge: higher-priority layers override individual fields (WP-20)."""
    by_kind = {layer.kind: layer for layer in layers}
    merged = MergedCellView.empty(x, y, z)
    field_sources: dict[str, MapLayerKind] = {}

    for kind in reversed(LAYER_PRIORITY_ORDER):
        layer = by_kind.get(kind)
        if layer is None or layer.cell is None:
            continue
        cell = layer.cell
        if cell.x != x or cell.y != y or cell.z != z:
            continue
        for field in _MERGE_FIELDS:
            value = getattr(cell, field)
            if value is not None:
                setattr(merged, field, value)
                field_sources[field] = kind
        if cell.is_structural:
            merged.is_structural = True
            field_sources["is_structural"] = kind

    merged.field_sources = field_sources if merged.has_any_data() else {}
    return merged
