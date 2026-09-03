"""Generate-first building layout cache for one settlement assembly."""

from __future__ import annotations

from datetime import datetime, timezone

from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
from app.application.worldData.generators.assemblers.settlementAssembler.packingLog import packing_warning
from app.application.worldData.generators.assemblers.settlementAssembler.planner.buildingDefaults import (
    lookup_building_template,
    merge_building_registry,
)
from app.application.worldData.generators.assemblers.settlementAssembler.planner.economic import (
    building_tier_compatible,
)
from app.application.worldData.generators.assemblers import structureAssembler as _structure_assemblers  # noqa: F401
from app.application.worldData.generators.assemblers.structureAssembler.assemblerRegistry import (
    ASSEMBLER_REGISTRY,
)
from app.application.worldData.generators.structure.structureGeneratorService import (
    OccupiedFootprint,
    StructureGeneratorService,
    StructureLayout,
)
from app.dataModel.materials import DEFAULT_FLOOR_MATERIAL, DEFAULT_WALL_MATERIAL
from app.dataModel.spatial.facing import Facing
from app.dataModel.structure.building.buildingLayoutTemplate import BuildingLayoutTemplate
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

CACHE_PROBE_PREFIX = "__cache_probe__"


def collect_building_template_names(
    district_slots: list[DistrictSlot],
    world:          World,
    skeleton:       CitySkeleton,
) -> set[str]:
    names: set[str] = set()
    registry = merge_building_registry(world)

    for slot in district_slots:
        for req in slot.required_structures:
            name = req.building_template
            if name:
                names.add(name)

        allowed = slot.district_template.allowed_structure_types
        if not allowed:
            continue
        for bt in registry:
            st = bt.structure_type
            if st in allowed and building_tier_compatible(bt, skeleton, world):
                names.add(bt.system_name)

    return names


def _probe_building(world_uid: str, template_name: str, facing: Facing) -> NamedLocation:
    return NamedLocation(
        location_uid=f"{CACHE_PROBE_PREFIX}{template_name}_{facing.value}",
        world_uid=world_uid,
        display_name=f"[cache] {template_name}",
        system_location_type="building",
        created_at=datetime.now(timezone.utc).isoformat(),
        map_x=0,
        map_y=0,
        map_z=0,
        parent_wall_material=DEFAULT_WALL_MATERIAL,
        parent_floor_material=DEFAULT_FLOOR_MATERIAL,
    )


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
        layout = _generate_probe(world, template, name, facing)
        if layout is None:
            if district:
                packing_warning(district, "cache", system_name=name, facing=facing.value, hit=False)
            return None
        self._layouts[self._key(name, facing)] = layout
        return layout


def _generate_probe(
    world: World,
    template: BuildingLayoutTemplate,
    name: str,
    facing: Facing,
) -> StructureLayout | None:
    structure_type = template.structure_type
    if structure_type not in ASSEMBLER_REGISTRY.all():
        packing_warning("cache", "cache", system_name=name, reason="no_assembler")
        return None
    building = _probe_building(world.world_uid, name, facing)
    try:
        layout = StructureGeneratorService().generate_from_template(
            world, building, template, ground_z=0, foundation_depth=0,
        )
    except Exception as exc:
        packing_warning("cache", "cache", system_name=name, reason=str(exc))
        return None
    if layout.occupied_footprint is None:
        packing_warning("cache", "cache", system_name=name, reason="empty_footprint")
        return None
    return layout


def build_layout_cache(
    world:          World,
    skeleton:       CitySkeleton,
    district_slots: list[DistrictSlot],
    terrain_cells:  list[MapCell] | None = None,
) -> BuildingLayoutCache:
    """
    SOUTH envelope per template.system_name for packing (CONN-PACK-3).
    ``ensure(template, facing)`` after the street frame fills other keys.
    """
    _ = terrain_cells
    cache = BuildingLayoutCache()
    for name in sorted(collect_building_template_names(district_slots, world, skeleton)):
        template = lookup_building_template(world, name)
        if template is None:
            packing_warning("cache", "cache", system_name=name, reason="missing_template")
            continue
        cache.ensure(world, template, Facing.SOUTH)
    return cache
