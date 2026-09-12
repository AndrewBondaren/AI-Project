"""Plot drawing for packing. Nested ``building`` is the interior template (TZ §3).

Root identity = ``DrawingKey`` (plot). Not the library Outline
(``BuildingTemplateOutline.levels`` is IntMinMax).

Nested ``levels`` / ``staircases`` / ``connections`` are still ``list[dict]``
(**POJO-D-16** / JV-4b). Do not reuse ``BuildingTemplateRoomSlot`` as a generate room.
Small outbuildings (``AreaLayout.small_layouts``) are not on this drawing.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.constrainedField import constrained_field
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.registryKey import RegistryKey
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.shared.ranges import EconomicTierRange
from app.dataModel.structure.building.defaultStructureContext import DefaultStructureContext
from app.dataModel.structure.building.occupiedFootprint import OccupiedFootprintSpec
from app.dataModel.structure.enums.buildingPurpose import (
    BuildingPurpose,
    coerce_purpose_list,
    primary_purpose,
)

DEFAULT_Z_HEIGHT = 3


def _is_generate_levels(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and isinstance(value[0], dict)


def _looks_like_plot_or_interior(raw: dict[str, Any]) -> bool:
    if _is_generate_levels(raw.get("levels")):
        return True
    nested = raw.get("building")
    if isinstance(nested, dict) and _is_generate_levels(nested.get("levels")):
        return True
    footprint = raw.get("occupied_footprint")
    return isinstance(footprint, dict) and footprint.get("width") is not None and footprint.get("depth") is not None


class BuildingLayoutTemplate(BaseModel):
    """Plot drawing (packing) with optional nested building body. tz_building_generator.md §3.1."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[RegistryKey[BuildingLayoutTemplate]]
    structure_types: DefaultOnWire[list[BuildingPurpose]] = Field(
        default_factory=lambda: coerce_purpose_list(None),
    )
    display_name: StrictOnWire[str]
    default_z_height: DefaultOnWire[int] = constrained_field(
        default=DEFAULT_Z_HEIGHT, greater_equals=1,
    )
    economic_tier: DefaultOnWire[EconomyTierKey | None] = None
    economic_tier_band: DefaultOnWire[str | None] = None
    economic_tier_range: DefaultOnWire[EconomicTierRange | None] = None
    perimeter_barrier: DefaultOnWire[PerimeterBarrier] = Field(
        default_factory=PerimeterBarrier,
    )
    default_structure_context: DefaultOnWire[DefaultStructureContext] = Field(
        default_factory=DefaultStructureContext,
    )
    occupied_footprint: DefaultOnWire[OccupiedFootprintSpec | None] = None
    building: DefaultOnWire[BuildingLayoutTemplate | None] = None
    levels: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    staircases: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    connections: DefaultOnWire[list[dict[str, Any]]] = Field(default_factory=list)
    # Extract drawings: ENUM-E class of resource this layout extracts (ore mine vs timber camp).
    resource_kind: DefaultOnWire[ResourceKind | None] = None
    # Farm drawings: ENUM-E how this farm grows (grain field vs orchard).
    crop_kind: DefaultOnWire[CropKind | None] = None
    # Livestock drawings: ENUM-E husbandry purpose (meat vs dairy vs mount). Not a structure_type.
    livestock_kind: DefaultOnWire[LivestockKind | None] = None
    # N+1 tags: iron_ore, wheat, cow, religion, knowledge, … Filter when the settlement names subjects.
    # If resource_kind is set, extract tags must be keys in worlds.resource_type_registry of that kind.
    # If crop_kind is set, farm tags must be keys in worlds.crops_registry of that kind.
    # If livestock_kind is set, livestock tags must be keys in worlds.livestock_registry of that kind.
    subjects: DefaultOnWire[list[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_structure_types(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        raw = payload.get("structure_types")
        if raw is None:
            raw = payload.get("structure_type")
        payload["structure_types"] = coerce_purpose_list(raw, empty_as_house=True)
        return payload

    @property
    def structure_type(self) -> str:
        """Primary purpose (first tag). Leftover scalar wire — use ``structure_types``."""
        return str(primary_purpose(self.structure_types))


type DrawingKey = RegistryKey[BuildingLayoutTemplate]
BuildingLayoutTemplate.model_rebuild()


def interior_of(plot: BuildingLayoutTemplate) -> BuildingLayoutTemplate | None:
    """Building body on the plot. Nested ``building`` wins; leftover root ``levels`` = this JSON is the body."""
    nested = plot.building
    if nested is not None:
        return nested
    if plot.levels:
        return plot
    return None


def plot_has_building(plot: BuildingLayoutTemplate) -> bool:
    """NamedLocation on the plot iff the drawing describes a building with generate levels."""
    interior = interior_of(plot)
    return interior is not None and bool(interior.levels)


def coerce_building_layout(raw: BuildingLayoutTemplate | dict[str, Any]) -> BuildingLayoutTemplate:
    if isinstance(raw, BuildingLayoutTemplate):
        return raw
    return BuildingLayoutTemplate.model_validate(raw)


def try_building_layout(raw: dict[str, Any]) -> BuildingLayoutTemplate | None:
    if not isinstance(raw, dict):
        return None
    if not _looks_like_plot_or_interior(raw):
        return None
    try:
        return BuildingLayoutTemplate.model_validate(raw)
    except ValidationError:
        return None
