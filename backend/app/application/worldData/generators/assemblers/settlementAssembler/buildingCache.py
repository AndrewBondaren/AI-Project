"""C22 building-shell cache for one settlement assembly.

Target (tz_structure_connections.md §5.1.3): cache holds envelopes ``w×h``
for packing. Interior rooms / ``StructureGeneratorService`` are not this
scope (city TZ phase 3). Envelope SoT on the drawing is not wired yet.

Stub: pick ``system_name``s (axis 3), do not generate interiors or shells.
Packing sees an empty cache until a shell pass exists. Tests may inject
layouts via ``from_south_map``.
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
        name = template.system_name
        if not name:
            return None
        cached = self.get(name, facing)
        if cached is not None:
            return cached
        layout = _generate_probe(world, template, name, facing, district=district)
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
    """Pick drawings by ``system_name``; shells are stubbed (no interiors)."""
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


def _generate_probe(
    world: World,
    template: BuildingLayoutTemplate,
    name: str,
    facing: Facing,
    *,
    district: str | None = None,
) -> StructureLayout | None:
    """Envelope probe for the already-picked drawing (``template.system_name``).

    ``structure_type`` is purpose (tavern, mine, …), not an ``ASSEMBLER_REGISTRY``
    key (building / ruins / resourceExtraction / vastHull). Do not gate the
    drawing on that registry — packing must use this чертёж as-is.
    """
    _ = world
    packing_warning(
        district or "cache",
        PackingStep.CACHE,
        system_name=name,
        facing=facing.value,
        reason=PackingReason.STUB_NO_SHELL,
        structure_type=template.structure_type,
    )
    return None

    # City packing cache is shells w×h (connections §5.1.3). Interior rooms are
    # phase 3 and not implemented — do not derive envelopes from interiors.
    #
    # from datetime import datetime, timezone
    # from app.application.worldData.generators.assemblers import structureAssembler as _structure_assemblers  # noqa: F401
    # from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
    # from app.dataModel.materials import DEFAULT_FLOOR_MATERIAL, DEFAULT_WALL_MATERIAL
    # from app.db.models.namedLocation import NamedLocation
    #
    # CACHE_PROBE_PREFIX = "__cache_probe__"
    #
    # def _probe_building(world_uid: str, template_name: str, facing: Facing) -> NamedLocation:
    #     return NamedLocation(
    #         location_uid=f"{CACHE_PROBE_PREFIX}{template_name}_{facing.value}",
    #         world_uid=world_uid,
    #         display_name=f"[cache] {template_name}",
    #         system_location_type="building",
    #         created_at=datetime.now(timezone.utc).isoformat(),
    #         map_x=0,
    #         map_y=0,
    #         map_z=0,
    #         parent_wall_material=DEFAULT_WALL_MATERIAL,
    #         parent_floor_material=DEFAULT_FLOOR_MATERIAL,
    #     )
    #
    # building = _probe_building(world.world_uid, name, facing)
    # try:
    #     layout = StructureGeneratorService().generate_from_template(
    #         world, building, template, ground_z=0, foundation_depth=0,
    #     )
    # except Exception as exc:
    #     packing_warning("cache", "cache", system_name=name, reason=str(exc))
    #     return None
    # if layout.occupied_footprint is None:
    #     packing_warning(
    #         PackingStep.CACHE,
    #         district="cache",
    #         system_name=name,
    #         reason=PackingReason.EMPTY_FOOTPRINT,
    #     )
    #     return None
    # return layout
