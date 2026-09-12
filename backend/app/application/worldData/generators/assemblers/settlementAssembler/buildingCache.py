"""C22 building-shell cache for one settlement assembly.

Target (tz_structure_connections.md §5.1.3): cache holds envelopes ``w×h``
for packing. Interior rooms / ``StructureGeneratorService`` are not this
scope (city TZ phase 3). Envelope SoT = ``BuildingLayoutTemplate.occupied_footprint``
on the plot drawing.

Tests may inject layouts via ``from_south_map``.
"""

from __future__ import annotations

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import (
    PackingReason,
    PackingStep,
    packing_warning,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    assemble_building_catalog,
)
from app.application.worldData.generators.coordinates.settlementCellRng import (
    SettlementCellRngRole,
    settlement_cell_rng,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureLayout,
)
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingCatalog import BuildingCatalog
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.db.models.mapCell import MapCell
from app.db.models.world import World


def collect_building_template_names(
    district_slots: list[DistrictSlot],
    world:          World,
    skeleton:       CitySkeleton,
    catalog:        BuildingCatalog | None = None,
    *,
    settlement_uid: str | None = None,
) -> set[str]:
    from app.application.worldData.generators.assemblers.districtAssembler.planner.tokens import (
        pick_layout_names,
    )

    catalog = catalog or assemble_building_catalog(world)
    names: set[str] = set()
    loc = settlement_uid or world.world_uid
    for slot in district_slots:
        rng = settlement_cell_rng(
            world.world_uid,
            loc,
            slot.cell_x,
            slot.cell_y,
            SettlementCellRngRole.BUILDINGS,
        )
        names.update(pick_layout_names(slot, world, skeleton, catalog, rng))
    return names


class BuildingLayoutCache:
    """Key ``(template, facing)``. Packing envelope is SOUTH (CONN-PACK-3)."""

    def __init__(self) -> None:
        self._layouts: dict[tuple[str, str], StructureLayout] = {}

    @classmethod
    def from_south_map(cls, layouts: dict[str, StructureLayout]) -> BuildingLayoutCache:
        cache = cls()
        for name, layout in layouts.items():
            cache._layouts[(name, Facing.SOUTH.value)] = layout
        return cache

    def _key(self, name: str, facing: Facing) -> tuple[str, str]:
        return (name, facing.value)

    def get(
        self,
        name: str,
        facing: Facing = Facing.SOUTH,
    ) -> StructureLayout | None:
        return self._layouts.get(self._key(name, facing))

    def envelope(self, name: str) -> OccupiedFootprint | None:
        layout = self.get(name, Facing.SOUTH)
        if layout is None or layout.occupied_footprint is None:
            return None
        return layout.occupied_footprint

    def template_names(self) -> list[str]:
        return sorted({name for name, _facing in self._layouts})

    def keys(self) -> list[str]:
        return self.template_names()

    def __len__(self) -> int:
        return len(self.template_names())

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return self.get(name, Facing.SOUTH) is not None

    def __getitem__(self, name: str) -> StructureLayout:
        layout = self.get(name, Facing.SOUTH)
        if layout is None:
            raise KeyError(name)
        return layout

    def ensure(
        self,
        world: World,
        template: BuildingLayoutTemplate,
        facing: Facing = Facing.SOUTH,
        *,
        district: str | None = None,
    ) -> StructureLayout | None:
        _ = world
        name = template.system_name
        if not name:
            return None
        cached = self.get(name, facing)
        if cached is not None:
            return cached
        layout = _envelope_layout(template, name, facing, district=district)
        if layout is None:
            return None
        self._layouts[self._key(name, facing)] = layout
        return layout


def build_layout_cache(
    world:          World,
    skeleton:       CitySkeleton,
    district_slots: list[DistrictSlot],
    terrain_cells:  list[MapCell] | None = None,
    catalog:        BuildingCatalog | None = None,
    *,
    settlement_uid: str | None = None,
) -> BuildingLayoutCache:
    """Pick drawings by ``system_name``; envelopes from declared plot footprint."""
    _ = terrain_cells
    catalog = catalog or assemble_building_catalog(world)
    cache = BuildingLayoutCache()
    for name in sorted(
        collect_building_template_names(
            district_slots, world, skeleton, catalog,
            settlement_uid=settlement_uid,
        ),
    ):
        template = catalog.by_system_name(name)
        if template is None:
            packing_warning(
                PackingStep.CACHE,
                district="cache",
                system_name=name,
                reason=PackingReason.MISSING_TEMPLATE,
            )
            continue
        cache.ensure(world, template, Facing.SOUTH)
    return cache


def _envelope_layout(
    template: BuildingLayoutTemplate,
    name: str,
    facing: Facing,
    *,
    district: str | None = None,
) -> StructureLayout | None:
    """Packing envelope from the plot drawing. Does not generate rooms."""
    spec = template.occupied_footprint
    if spec is None:
        packing_warning(
            district or "cache",
            PackingStep.CACHE,
            system_name=name,
            facing=facing.value,
            reason=PackingReason.STUB_NO_SHELL,
            structure_type=",".join(str(p) for p in template.structure_types),
        )
        return None
    footprint = OccupiedFootprint(
        min_x=spec.min_x,
        min_y=spec.min_y,
        width=spec.width,
        depth=spec.depth,
    )
    return StructureLayout(
        cells=[],
        levels=[],
        passages=[],
        rooms=[],
        occupied_footprint=footprint,
    )
