"""Plot drawing for packing (5o split). ``main_building`` is a body+structure ref.

Root identity = ``DrawingKey`` (plot). Interior geometry lives in
``StructureTemplate`` behind ``main_building.structure`` — the plot carries
no ``levels`` / ``staircases`` / ``connections`` of its own.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.dataModel.annotationPolicy import DefaultOnWire, StrictOnWire
from app.dataModel.locations.context.scopeLevel import ScopeLevel
from app.dataModel.locations.context.cascadeParams import ECONOMIC_TIER
from app.dataModel.cascade.cascadeSpec import (
    CascadeChannel,
    CascadeLink,
    ChannelKind,
)
from app.dataModel.flora.enums.cropKind import CropKind
from app.dataModel.livestock.enums.livestockKind import LivestockKind
from app.dataModel.registryKey import RegistryKey
from app.dataModel.resources.enums.resourceKind import ResourceKind
from app.dataModel.settlement.area.perimeterBarrier import PerimeterBarrier
from app.dataModel.economy.economyTier.worldEconomyTierRegistry import EconomyTierKey
from app.dataModel.shared.ranges import EconomicTierRange
from app.dataModel.structure.building.buildingBodyTemplate import BuildingBodyTemplate
from app.dataModel.structure.building.occupiedFootprint import OccupiedFootprintSpec
from app.dataModel.structure.building.structureTemplate import StructureKey
from app.dataModel.structure.enums.buildingPurpose import BuildingPurposeFamily

_LEGACY_BODY_KEYS = (
    "levels",
    "staircases",
    "connections",
    "structure_types",
    "structure_type",
    "default_structure_context",
    "building",
)


class PlotLayoutTemplate(BaseModel):
    """Plot drawing (packing) with optional building body. tz_building_generator.md (lock)."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    system_name: StrictOnWire[RegistryKey[PlotLayoutTemplate]]
    display_name: StrictOnWire[str]
    plot_type: DefaultOnWire[BuildingPurposeFamily] = BuildingPurposeFamily.DWELLING
    # Area-level cascade channels for `economic_tier`, chained by edges
    # tier → band → range; `model=None` — self-links (tz_cascade_context
    # §2). Outer neighbours (building NL above, district NL below) are
    # declared on the NL side — this module may not import NamedLocation.
    economic_tier: Annotated[
        DefaultOnWire[EconomyTierKey | None],
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.AREA,
            below=CascadeLink(None, "economic_tier_band", ScopeLevel.AREA),
        ),
    ] = None
    economic_tier_band: Annotated[
        DefaultOnWire[str | None],
        CascadeChannel(
            ECONOMIC_TIER, ScopeLevel.AREA, kind=ChannelKind.BAND,
            below=CascadeLink(None, "economic_tier_range", ScopeLevel.AREA),
        ),
    ] = None
    economic_tier_range: Annotated[
        DefaultOnWire[EconomicTierRange | None],
        CascadeChannel(ECONOMIC_TIER, ScopeLevel.AREA, kind=ChannelKind.RANGE),
    ] = None
    perimeter_barrier: DefaultOnWire[PerimeterBarrier] = Field(
        default_factory=PerimeterBarrier,
    )
    occupied_footprint: DefaultOnWire[OccupiedFootprintSpec | None] = None
    main_building: DefaultOnWire[BuildingBodyTemplate | None] = None
    secondary_buildings: DefaultOnWire[list[BuildingBodyTemplate]] = Field(
        default_factory=list,
    )
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
    def _reject_legacy_body_wire(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        hits = [key for key in _LEGACY_BODY_KEYS if key in data]
        if hits:
            raise ValueError(
                "PlotLayoutTemplate: inline building body removed (5o) — "
                f"use main_building.structure ref; got keys: {hits}"
            )
        return data


type DrawingKey = RegistryKey[PlotLayoutTemplate]
PlotLayoutTemplate.model_rebuild()


def plot_has_building(plot: PlotLayoutTemplate) -> bool:
    return plot.main_building is not None


def structure_ref_of(plot: PlotLayoutTemplate) -> StructureKey | None:
    """Uid ref to the shared ``StructureTemplate`` of ``main_building`` (or None)."""
    if plot.main_building is None:
        return None
    return plot.main_building.structure


def plot_type_defaulted(plot: PlotLayoutTemplate) -> bool:
    """True when ``plot_type`` was omitted on the wire (family default applied)."""
    return "plot_type" not in plot.model_fields_set
