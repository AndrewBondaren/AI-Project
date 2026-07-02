"""Generate-first building layout cache for one settlement assembly."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.application.worldData.generators.assemblers.areaAssembler.areaSlot import AreaSlot
from app.application.worldData.generators.assemblers.areaAssembler.structureAreaAssembler import (
    derive_structure_context,
)
from app.application.worldData.generators.assemblers.citySkeleton import CitySkeleton
from app.application.worldData.generators.assemblers.districtAssembler.districtSlot import DistrictSlot
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
from app.application.worldData.generators.structure.structureGeneratorService import StructureLayout
from app.dataModel.spatial.facing import Facing
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

logger = logging.getLogger(__name__)

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
            st = bt.get("structure_type") or bt.get("system_type")
            if st in allowed and building_tier_compatible(bt, skeleton, world):
                names.add(bt["system_name"])

    return names


def _probe_building(world_uid: str, template_name: str) -> NamedLocation:
    return NamedLocation(
        location_uid=f"{CACHE_PROBE_PREFIX}{template_name}",
        world_uid=world_uid,
        display_name=f"[cache] {template_name}",
        system_location_type="building",
        created_at=datetime.now(timezone.utc).isoformat(),
        map_x=0,
        map_y=0,
        map_z=0,
        parent_wall_material="stone",
        parent_floor_material="wood",
    )


def build_layout_cache(
    world:          World,
    skeleton:       CitySkeleton,
    district_slots: list[DistrictSlot],
    terrain_cells:  list[MapCell] | None = None,
) -> dict[str, StructureLayout]:
    """
    Одна генерация на template.system_name за сборку поселения.
    Probe-building at (0,0) — реальный bbox в occupied_footprint.
    """
    cache: dict[str, StructureLayout] = {}
    probe_slot = AreaSlot(cells=[(0, 0)], ground_z=0, facing=Facing.SOUTH)

    for name in sorted(collect_building_template_names(district_slots, world, skeleton)):
        if name in cache:
            continue

        template = lookup_building_template(world, name)
        if template is None:
            logger.warning(
                "building cache | template=%s не найден в building_template_registry",
                name,
            )
            continue

        structure_type = template.get("structure_type", "building")
        if structure_type not in ASSEMBLER_REGISTRY.all():
            logger.warning(
                "building cache | template=%s structure_type=%s — нет assembler",
                name,
                structure_type,
            )
            continue

        building = _probe_building(world.world_uid, name)
        context  = derive_structure_context(template, skeleton, probe_slot, terrain_cells)

        try:
            assembler = ASSEMBLER_REGISTRY.get(structure_type)
            layout = assembler.assemble(world, building, template, context, terrain_cells)
        except Exception as exc:
            logger.warning(
                "building cache | template=%s генерация не удалась: %s",
                name,
                exc,
            )
            continue

        if layout.occupied_footprint is None:
            logger.warning(
                "building cache | template=%s occupied_footprint пуст",
                name,
            )
            continue

        cache[name] = layout
        fp = layout.occupied_footprint
        logger.info(
            "building cache | template=%s footprint=%dx%d cells=%d",
            name,
            fp.width,
            fp.depth,
            len(layout.cells),
        )

    return cache
