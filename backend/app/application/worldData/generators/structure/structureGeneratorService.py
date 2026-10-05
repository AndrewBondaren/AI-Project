import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random

from pydantic import ValidationError

logger = logging.getLogger(__name__)

from app.dataModel.locations.context.locationContext import LocationContext
from app.dataModel.locations.structure.building.roomConnection import RoomConnection
from app.dataModel.locations.structure.building.staircaseSpec import StaircaseSpec
from app.dataModel.locations.structure.building.levelDef import LevelDef
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.locations.structure.enums.passageType import PassageType
from app.dataModel.spatial.facing import Facing
from app.application.worldData.generators.structure.structureOrientation import entry_orientation, validate_facing
from app.application.jsonValidation import materials
from app.application.worldData.context.locationScope import (
    debug_building_context,
)
from app.application.worldData.generators.utils.economicTierBands import band_of
from app.application.worldData.ids import UidKind, entity_rng, entity_uid
from app.application.worldData.settlementOutdoor.settlementOutdoorUids import (
    level_uid as _level_uid,
)
from app.application.worldData.generators.structure.cellBuilder import build_level_cells
from app.application.worldData.generators.structure.wallMaterials import (
    select_wall_materials,
)
from app.application.worldData.generators.structure.wallRegions import (
    classify_wall_regions,
)
from app.application.worldData.generators.structure.errors import GenerationError, UnsupportedShapeError
from app.application.worldData.generators.structure.layoutEngine import layout_level
from app.application.worldData.generators.structure.staircase.embeddedUpperLayout import prepare_embedded_upper
from app.application.worldData.generators.structure.passages import build_passages
from app.application.worldData.generators.structure.room.roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.shaftFactory import (
    instantiate_shaft_rooms,
)
from app.dataModel.locations.structure.enums.staircaseType import (
    requires_shaft,
)
from app.dataModel.economy.enums.economicTierBand import EconomicTierBand
from app.dataModel.economy.materialPolicies import BuildingEconomicContext
from app.application.worldData.generators.structure.staircase.shaftPlacer import make_shaft_placer
from app.application.worldData.generators.structure.passages.wallOpening import place_wall_openings
from app.application.worldData.generators.structure.passages.corridorTrimmer import trim_corridor_rooms
from app.application.worldData.generators.structure.passages.corridorConnector import connect_corridors
from app.application.worldData.generators.structure.structurePostProcess import run as _post_process
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

__all__ = [
    "StructureGeneratorService",
    "StructureLayout",
    "OccupiedFootprint",
    "compute_occupied_footprint",
    "UnsupportedShapeError",
    "GenerationError",
]


@dataclass(frozen=True)
class OccupiedFootprint:
    """Фактический bbox здания на ground_z (1 cell = 1 m), для bin-packing."""
    min_x:  int
    min_y:  int
    width:  int
    depth:  int


@dataclass
class StructureLayout:
    cells:               list[MapCell]
    levels:              list[LocationLevel]
    passages:            list[LocationPassage]
    rooms:               list[NamedLocation]
    occupied_footprint:  OccupiedFootprint | None = None


def compute_occupied_footprint(
    cells:    list[MapCell],
    ground_z: int,
) -> OccupiedFootprint | None:
    plane = [c for c in cells if c.z == ground_z]
    if not plane:
        plane = cells
    if not plane:
        return None
    xs = [c.x for c in plane]
    ys = [c.y for c in plane]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return OccupiedFootprint(
        min_x=min_x,
        min_y=min_y,
        width=max_x - min_x + 1,
        depth=max_y - min_y + 1,
    )


# ---------------------------------------------------------------------------
# z helpers

def _resolve_z_heights(template: StructureTemplate, definitions: list[LevelDef]) -> dict[int, int]:
    """z_offset → effective z_height."""
    default = template.default_z_height
    return {
        level_def.z_offset: level_def.z_height if level_def.z_height is not None else default
        for level_def in definitions
    }


def _resolve_template_z_heights(template: StructureTemplate, definitions: list[LevelDef]) -> dict[int, int | None]:
    """z_offset → explicit z_height from template (None if not specified at all)."""
    template_default = template.default_z_height
    return {
        level_def.z_offset: level_def.z_height if level_def.z_height is not None else template_default
        for level_def in definitions
    }


def _compute_level_z(building_map_z: int, z_offset: int, z_heights: dict[int, int], foundation_depth: int = 0) -> int:
    if z_offset == 0:
        return building_map_z
    if z_offset > 0:
        return building_map_z + sum(z_heights[k] for k in range(0, z_offset))
    return building_map_z - foundation_depth - sum(z_heights[k] for k in range(z_offset, 0))


def _build_levels(definitions: list[LevelDef], building: NamedLocation,
                  z_heights: dict[int, int], foundation_depth: int = 0) -> dict[int, LocationLevel]:
    return {
        level_def.z_offset: LocationLevel(
            level_uid=_level_uid(
                building.world_uid, building.location_uid, level_def.z_offset),
            location_uid=building.location_uid,
            z=_compute_level_z(building.map_z, level_def.z_offset, z_heights, foundation_depth),
            z_height=z_heights[level_def.z_offset],
            display_name=level_def.display_name,
            isolated=level_def.isolated,
            access_mechanic=level_def.access_mechanic,
        )
        for level_def in definitions
    }


# ---------------------------------------------------------------------------
# Level layout ordering — propagate staircase anchors across levels

def _staircase_layout_order(
    definitions: list[LevelDef],
    staircases: list[StaircaseSpec],
    room_z_offsets: dict[str, int],
) -> list[int]:
    """
    BFS from z_offset=0 through staircase stops.
    Ensures each level is laid out only after its staircase-connected neighbour,
    so we can propagate anchor positions.
    Unreachable levels are appended at the end in template order.
    """
    all_z = [level_def.z_offset for level_def in definitions]
    adj: dict[int, list[int]] = {z: [] for z in all_z}
    for sc in staircases:
        stops = sc.stops
        for i in range(len(stops) - 1):
            fr_z = room_z_offsets.get(stops[i])
            to_z = room_z_offsets.get(stops[i + 1])
            if fr_z is not None and to_z is not None and fr_z != to_z:
                adj[fr_z].append(to_z)
                adj[to_z].append(fr_z)

    start = 0 if 0 in adj else (all_z[0] if all_z else 0)
    visited: set[int] = {start}
    order: list[int] = [start]
    queue: deque[int] = deque([start])
    while queue:
        z = queue.popleft()
        for nz in adj.get(z, []):
            if nz not in visited:
                visited.add(nz)
                order.append(nz)
                queue.append(nz)
    for z in all_z:
        if z not in visited:
            order.append(z)
    # Embedded hosts must exist before their aligned upper stops (also cellar -> ground).
    dependencies: dict[int, set[int]] = {z: set() for z in order}
    for sc in staircases:
        if sc.in_a_room:
            for source, target in zip(sc.stops, sc.stops[1:]):
                fr_z, to_z = room_z_offsets.get(source), room_z_offsets.get(target)
                if fr_z in dependencies and to_z in dependencies and fr_z != to_z:
                    dependencies[to_z].add(fr_z)
    pending = list(order)
    ordered = []
    while pending:
        ready = next((z for z in pending if dependencies[z] <= set(ordered)), None)
        if ready is None:
            # A cyclic authored contract will be diagnosed per room by upper placement.
            ordered.extend(pending)
            break
        ordered.append(ready)
        pending.remove(ready)
    return ordered


# ---------------------------------------------------------------------------
# Room → NamedLocation

def _room_to_named_location(
    room: _RoomInstance,
    building: NamedLocation,
    level: LocationLevel,
    room_uid: str,
) -> NamedLocation:
    return NamedLocation(
        location_uid=room_uid,
        world_uid=building.world_uid,
        display_name=room.display_name,
        system_location_type="room",
        system_location_subtype=room.room_type,
        created_at=datetime.now(timezone.utc).isoformat(),
        parent_location_uid=building.location_uid,
        is_accessible=True,
        is_discovered=False,
        is_public=room.is_public,
        is_forbidden=room.is_forbidden,
        map_x=room.origin_x,
        map_y=room.origin_y,
        map_z=level.z,
        parent_wall_material=room.wall_material,
        parent_floor_material=room.floor_material,
        system_economic_tier=room.economic_tier,
    )


# ---------------------------------------------------------------------------
# Service

class StructureGeneratorService:
    """
    Pure utility — no repositories, no async.
    Deterministic: same world_uid + same building_uid → same layout.
    Generates interior box: rooms, walls, passages.
    Foundation + roof + porch — BuildingAssembler (layer above).
    """

    def generate_from_template(
        self,
        world: World,
        building: NamedLocation,
        structure: StructureTemplate,
        *,
        ground_z: int | None = None,
        foundation_depth: int = 0,
        ctx: LocationContext | None = None,
        facing: Facing | None = None,
    ) -> StructureLayout:
        validate_facing(facing, structure.system_name)
        logger.info(
            "generate_from_template | start building=%s template=%s",
            building.location_uid, structure.system_name,
        )

        ground_z = ground_z if ground_z is not None else building.map_z

        rng = entity_rng(
            world.world_uid, UidKind.STRUCTURE, building=building.location_uid)
        # Callers without a real chain still honor the building NL's own
        # authored tier — the NL is the building-scope link (§8.4).
        ctx = ctx or debug_building_context(world, building)

        definitions = self._resolve_levels(structure, building.location_uid)
        z_heights = _resolve_z_heights(structure, definitions)
        template_z_heights = _resolve_template_z_heights(structure, definitions)
        levels    = _build_levels(definitions, building, z_heights, foundation_depth)
        logger.info("levels resolved: %s", {z: (l.z, l.z_height) for z, l in levels.items()})

        staircases = self._resolve_staircases(structure)
        all_rooms, room_z_offsets, shaft_by_staircase = self._instantiate_rooms(
            structure, building, levels, world, rng, staircases, template_z_heights, definitions=definitions,
            ctx=ctx,
        )
        connections = self._resolve_connections(structure)
        self._layout_rooms(
            structure, building, all_rooms, room_z_offsets, shaft_by_staircase,
            connections, staircases, definitions=definitions,
        )

        cells_dict, room_uids = self._generate_cells(
            structure, building, levels, all_rooms, world, connections, definitions,
            rng=rng, ctx=ctx,
        )

        passages = self._run_passages(
            structure, building, levels, all_rooms, room_z_offsets, cells_dict, world, rng,
            connections, staircases, ground_z=ground_z, ctx=ctx,
        )

        connect_corridors(
            all_rooms, cells_dict, levels,
            world.world_uid, building.location_uid,
            ctx.wall_material,
            world.default_passage_height,
        )

        self._place_wall_openings(
            structure, building, levels, all_rooms, cells_dict, world, rng,
            ground_z=ground_z, definitions=definitions,
        )

        _post_process(cells_dict)

        if facing is not None:
            orientation = entry_orientation(all_rooms, passages, structure.system_name, facing)
            orientation.apply(cells_dict, passages, all_rooms)

        result = self._assemble_result(building, levels, all_rooms, room_uids, cells_dict, passages)
        logger.info(
            "generate_from_template | done building=%s rooms=%d cells=%d passages=%d",
            building.location_uid, len(result.rooms), len(result.cells), len(result.passages),
        )
        return result

    # ------------------------------------------------------------------
    # Phase: instantiate rooms

    def _instantiate_rooms(
        self,
        template: StructureTemplate,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        world: World,
        rng: Random,
        staircases: list[StaircaseSpec],
        template_z_heights: dict[int, int | None] | None = None,
        *,
        definitions: list[LevelDef],
        ctx: LocationContext | None = None,
    ) -> tuple[list[_RoomInstance], dict[str, int], dict[str, list[_RoomInstance]]]:
        """Steps 2-3: instantiate template rooms + shaft rooms per level."""
        logger.info("=== PHASE: instantiate rooms ===")
        template_z_heights = template_z_heights or {}
        all_rooms: list[_RoomInstance] = []
        room_z_offsets: dict[str, int] = {}

        for level_def in definitions:
            z_offset    = level_def.z_offset
            level       = levels[z_offset]
            level_rooms = instantiate_level_rooms(
                level_def, template, level.z_height, z_offset, world, rng,
                ctx=ctx,
                building_uid=building.location_uid,
                template_z_height=template_z_heights.get(z_offset),
            )
            for room in level_rooms:
                room_z_offsets[room.room_id] = z_offset
                if room.staircase_type:
                    logger.info("post-instantiate: %r staircase_type=%r", room.room_id, room.staircase_type)
            all_rooms.extend(level_rooms)
            logger.info("instantiate | z_offset=%d rooms=%d", z_offset, len(level_rooms))

        shaft_rooms = instantiate_shaft_rooms(
            template, staircases, room_z_offsets, levels, world, rng,
            ctx=ctx,
        )
        for sr in shaft_rooms:
            room_z_offsets[sr.room_id] = sr.z_offset
        all_rooms.extend(shaft_rooms)

        shaft_by_staircase: dict[str, list[_RoomInstance]] = {}
        for sr in shaft_rooms:
            if sr.staircase_id:
                shaft_by_staircase.setdefault(sr.staircase_id, []).append(sr)
        for lst in shaft_by_staircase.values():
            lst.sort(key=lambda r: r.instance_idx)

        logger.info(
            "instantiate | shaft_rooms=%d across %d staircases",
            len(shaft_rooms), len(shaft_by_staircase),
        )
        return all_rooms, room_z_offsets, shaft_by_staircase

    @staticmethod
    def _resolve_levels(template: StructureTemplate, building_uid: str | None = None) -> list[LevelDef]:
        """Runtime boundary: parse again; broken attachment references degrade with ERROR."""
        resolved: list[LevelDef] = []
        seen: set[str] = set()
        for index, raw in enumerate(template.levels):
            try:
                level = LevelDef.model_validate(raw)
            except ValidationError as exc:
                raise GenerationError(
                    f"Structure '{template.system_name}' building '{building_uid}' levels[{index}]: {exc}"
                ) from exc
            if level.height_substitution is not None:
                logger.error(
                    "Structure '%s' building '%s' level %s: z_height=%s — fallback to template default %s",
                    template.system_name, building_uid, level.z_offset,
                    level.height_substitution, template.default_z_height,
                )
            for room in level.rooms:
                if room.room_id in seen:
                    raise GenerationError(f"Structure '{template.system_name}': duplicate room_id '{room.room_id}'")
                seen.add(room.room_id)
                for field, original in room.substitutions:
                    logger.error(
                        "Structure '%s' building '%s' room '%s': %s=%s — fallback to %r",
                        template.system_name, building_uid, room.room_id,
                        field, original, getattr(room, field).value,
                    )
            rooms = list(level.rooms)
            # Repeat to remove dependent attachments whose host was skipped as well.
            while True:
                local_ids = {room.room_id for room in rooms}
                invalid = [room for room in rooms if room.attach_to is not None and room.attach_to not in local_ids]
                if not invalid:
                    break
                for room in invalid:
                    logger.error(
                        "Structure '%s' building '%s' room '%s': attach_to=%r missing on level %s — skipping room",
                        template.system_name, building_uid, room.room_id, room.attach_to, level.z_offset,
                    )
                invalid_ids = {room.room_id for room in invalid}
                rooms = [room for room in rooms if room.room_id not in invalid_ids]
            resolved.append(level.model_copy(update={"rooms": rooms}))
        return resolved

    @staticmethod
    def _resolve_connections(template: StructureTemplate) -> list[RoomConnection]:
        """Runtime boundary: wire dicts → RoomConnection (GenerationError on bad wire)."""
        resolved: list[RoomConnection] = []
        for index, raw in enumerate(template.connections):
            if isinstance(raw, dict) and "passage_type" in raw:
                parsed = PassageType.from_wire(raw["passage_type"])
                if parsed not in (PassageType.DOORWAY, PassageType.ARCHWAY):
                    logger.error(
                        "Structure '%s' connections[%d]: passage_type %r is not "
                        "doorway/archway — fallback to doorway "
                        "(stairs belong in staircases[])",
                        template.system_name, index, raw["passage_type"],
                    )
            try:
                resolved.append(RoomConnection.model_validate(raw))
            except ValidationError as exc:
                raise GenerationError(
                    f"Structure '{template.system_name}' connections[{index}]: {exc}"
                ) from exc
        return resolved

    @staticmethod
    def _resolve_staircases(template: StructureTemplate) -> list[StaircaseSpec]:
        """Runtime boundary: wire dicts → StaircaseSpec (GenerationError on bad wire)."""
        resolved: list[StaircaseSpec] = []
        for index, raw in enumerate(template.staircases):
            try:
                resolved.append(StaircaseSpec.model_validate(raw))
            except ValidationError as exc:
                raise GenerationError(
                    f"Structure '{template.system_name}' staircases[{index}]: {exc}"
                ) from exc
        return resolved

    # ------------------------------------------------------------------
    # Phase: layout

    def _layout_rooms(
        self,
        template: StructureTemplate,
        building: NamedLocation,
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
        connections: list[RoomConnection],
        staircases: list[StaircaseSpec],
        definitions: list[LevelDef],
    ) -> None:
        """Steps 4-5: place rooms on XY per level; mutates all_rooms in-place."""
        logger.info("=== PHASE: layout (order propagation) ===")
        bx = building.map_x or 0
        by = building.map_y or 0

        layout_order = _staircase_layout_order(definitions, staircases, room_z_offsets)
        level_start: dict[int, tuple[int, int]] = {layout_order[0]: (bx, by)}
        all_placed_by_id: dict[str, _RoomInstance] = {}
        level_footprint_bounds: dict[int, tuple[int, int, int, int]] = {}

        for z_offset in layout_order:
            start_x, start_y = level_start.get(z_offset, (bx, by))
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset]

            synth_conns = self._build_synth_conns(
                connections, staircases, z_offset, room_z_offsets, shaft_by_staircase,
            )

            parent_bounds = level_footprint_bounds.get(z_offset - 1) if z_offset > 0 else None
            prepare_embedded_upper(
                z_offset, all_rooms, staircases, shaft_by_staircase,
                parent_bounds, building.location_uid,
            )
            layout_level(
                level_rooms, synth_conns, start_x, start_y, bounds=parent_bounds,
                staircases=staircases, building_uid=building.location_uid,
                world_uid=building.world_uid,
            )

            for r in level_rooms:
                if r.placed:
                    all_placed_by_id[r.room_id] = r

            self._place_level_shafts(
                z_offset, staircases, all_rooms, room_z_offsets,
                shaft_by_staircase, all_placed_by_id, level_start,
                building_uid=building.location_uid,
                world_uid=building.world_uid,
            )
            self._propagate_trapdoor_starts(
                z_offset, staircases, room_z_offsets, all_placed_by_id, level_start,
            )

            trim_corridor_rooms(all_rooms, staircases)

            placed_rooms_this = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            if placed_rooms_this:
                all_fp: set[tuple[int, int]] = set()
                for r in placed_rooms_this:
                    all_fp |= r.get_footprint()
                level_footprint_bounds[z_offset] = (
                    min(x for x, y in all_fp),
                    min(y for x, y in all_fp),
                    max(x for x, y in all_fp),
                    max(y for x, y in all_fp),
                )
                logger.info("layout | z_offset=%d footprint_bounds=%s",
                            z_offset, level_footprint_bounds[z_offset])

            placed_count = len(placed_rooms_this)
            skipped = len(level_rooms) - placed_count
            logger.info("layout | z_offset=%d start=(%d,%d) placed=%d skipped=%d",
                        z_offset, start_x, start_y, placed_count, skipped)
            for r in level_rooms:
                if r.placed:
                    logger.info(
                        "layout | z_offset=%d  room=%-20s  origin=(%d,%d)  size=%dx%d  extra_cells=%d",
                        z_offset, r.room_id, r.origin_x, r.origin_y, r.width, r.depth, len(r.extra_cells),
                    )
                else:
                    logger.warning("layout | z_offset=%d  room=%s NOT PLACED", z_offset, r.room_id)
            if skipped:
                logger.warning("layout | z_offset=%d rooms not placed: %s",
                               z_offset, [r.room_id for r in level_rooms if not r.placed])

            for r in all_rooms:
                if r.z_offset == z_offset and r.placed and r.room_id not in all_placed_by_id:
                    all_placed_by_id[r.room_id] = r

    def _build_synth_conns(
        self,
        connections: list[RoomConnection],
        staircases: list[StaircaseSpec],
        z_offset: int,
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
    ) -> list[RoomConnection]:
        """Synthetic archway connections: shaft ↔ to_room for the current level."""
        synth = list(connections)
        for sc in staircases:
            if not requires_shaft(sc.staircase_type):
                continue
            sc_id      = sc.staircase_id
            stops      = sc.stops
            shaft_list = shaft_by_staircase.get(sc_id, [])
            for i, stop_id in enumerate(stops):
                if i == 0:
                    continue
                if room_z_offsets.get(stop_id) != z_offset:
                    continue
                if i < len(shaft_list):
                    synth.append(RoomConnection(
                        from_room=shaft_list[i].room_id,
                        to_room=stop_id,
                        passage_type=PassageType.ARCHWAY,
                    ))
        return synth

    def _place_level_shafts(
        self,
        z_offset: int,
        staircases: list[StaircaseSpec],
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
        all_placed_by_id: dict[str, _RoomInstance],
        level_start: dict[int, tuple[int, int]],
        *,
        building_uid: str,
        world_uid: str,
    ) -> None:
        """Place fr_z shafts using their strategy; propagate origins to upper levels."""
        for sc in staircases:
            if not requires_shaft(sc.staircase_type):
                continue
            sc_id  = sc.staircase_id
            stops  = sc.stops
            if not stops or room_z_offsets.get(stops[0]) != z_offset:
                continue

            fr_room    = all_placed_by_id.get(stops[0])
            shaft_list = shaft_by_staircase.get(sc_id, [])
            if fr_room is None or not shaft_list:
                continue

            shaft_fr        = shaft_list[0]
            placed_on_level = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            placer          = make_shaft_placer(
                sc, building_uid=building_uid, world_uid=world_uid)
            success         = placer.place(shaft_fr, fr_room, placed_on_level)

            if success:
                for shaft_other in shaft_list[1:]:
                    if shaft_other.layout_excluded:
                        continue
                    shaft_other.origin_x = shaft_fr.origin_x
                    shaft_other.origin_y = shaft_fr.origin_y
                    if shaft_fr.embedded_entry is not None:
                        shaft_other.facing = shaft_fr.facing
                for i in range(1, len(stops)):
                    to_stop_z = room_z_offsets.get(stops[i])
                    if to_stop_z is not None and to_stop_z not in level_start:
                        level_start[to_stop_z] = (shaft_fr.origin_x, shaft_fr.origin_y)
                logger.info(
                    "layout | staircase=%r shaft at (%d,%d), level_start propagated to %s",
                    sc_id, shaft_fr.origin_x, shaft_fr.origin_y,
                    [room_z_offsets.get(s) for s in stops[1:]],
                )
            else:
                logger.error("layout | staircase=%r shaft placement failed on z=%d", sc_id, z_offset)

    def _propagate_trapdoor_starts(
        self,
        z_offset: int,
        staircases: list[StaircaseSpec],
        room_z_offsets: dict[str, int],
        all_placed_by_id: dict[str, _RoomInstance],
        level_start: dict[int, tuple[int, int]],
    ) -> None:
        """No-shaft staircases (trapdoor): align target level to the placed anchor room."""
        for sc in staircases:
            if requires_shaft(sc.staircase_type):
                continue
            sc_id = sc.staircase_id
            stops = sc.stops
            for i in range(len(stops) - 1):
                for anchor_id, target_id in ((stops[i], stops[i + 1]),
                                              (stops[i + 1], stops[i])):
                    if room_z_offsets.get(anchor_id) != z_offset:
                        continue
                    target_z = room_z_offsets.get(target_id)
                    if target_z is None or target_z in level_start:
                        continue
                    anchor_room = all_placed_by_id.get(anchor_id)
                    if anchor_room:
                        level_start[target_z] = (anchor_room.origin_x, anchor_room.origin_y)
                        logger.info(
                            "layout | trapdoor=%r propagated level_start z=%d → (%d,%d) from %r",
                            sc_id, target_z, anchor_room.origin_x, anchor_room.origin_y, anchor_id,
                        )

    # ------------------------------------------------------------------
    # Phase: cell generation

    def _generate_cells(
        self,
        template: StructureTemplate,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        world: World,
        connections: list[RoomConnection],
        definitions: list[LevelDef],
        rng: Random | None = None,
        ctx: LocationContext | None = None,
    ) -> tuple[dict[tuple, MapCell], dict[str, str]]:
        """Steps 6-8: assign UIDs, generate cells per level."""
        logger.info("=== PHASE: cell generation ===")
        wall_mat    = ctx.wall_material

        # §8.7.1 — building economic context for the wall material selector.
        economic_tier = ctx.economic_tier if ctx is not None else None
        band = EconomicTierBand.from_wire(band_of(world, economic_tier))
        if economic_tier is None or band is None:
            raise GenerationError(
                f"Structure '{template.system_name}': wall material policy "
                f"requires a resolved economic context "
                f"(tier={economic_tier!r}, band={band})")
        wall_context = BuildingEconomicContext(
            economic_tier=economic_tier, band=band)
        material_strengths = {
            e.system_material: e.structural_strength
            for e in materials(world).root
        }

        room_uids: dict[str, str] = {
            room.uid_key: entity_uid(
                world.world_uid, UidKind.ROOM,
                parent=building.location_uid, key=room.uid_key,
            )
            for room in all_rooms
            if room.placed and not room.is_shaft
        }

        cells_dict: dict[tuple, MapCell] = {}
        for level_def in definitions:
            z_offset    = level_def.z_offset
            level       = levels[z_offset]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            regions = classify_wall_regions(
                level_rooms, level.z, level.z + level.z_height - 1)
            plan = select_wall_materials(
                regions, {r.uid_key: r for r in level_rooms},
                wall_mat, material_strengths, wall_context)
            for failure in plan.failures:
                logger.warning(
                    "wall_material | z_offset=%d cells=%d failure=%s: %s"
                    " — using building material",
                    z_offset, len(failure.region.cells),
                    failure.failure.value, failure.reason,
                )
            cell_materials = {
                (x, y): choice.system_material
                for choice in plan.choices for x, y in choice.region.cells
            }
            before      = len(cells_dict)
            for cell in build_level_cells(
                level_rooms, connections, level.z, level.z_height,
                world.world_uid, building.location_uid, wall_mat, room_uids,
                cell_materials,
            ):
                cells_dict[(cell.x, cell.y, cell.z)] = cell
            logger.info("cells | z_offset=%d generated=%d", z_offset, len(cells_dict) - before)

        return cells_dict, room_uids

    # ------------------------------------------------------------------
    # Phase: passages

    def _run_passages(
        self,
        template: StructureTemplate,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        cells_dict: dict[tuple, MapCell],
        world: World,
        rng: Random,
        connections: list[RoomConnection],
        staircases: list[StaircaseSpec],
        ground_z: int,
        ctx: LocationContext | None = None,
    ) -> list[LocationPassage]:
        """Steps 9-11: build passages (mutates cells_dict for door/staircase cells)."""
        for r in all_rooms:
            if r.staircase_type:
                logger.info("pre-passages room staircase_type: %r  %r", r.room_id, r.staircase_type)
        passages = build_passages(
            cells_dict, all_rooms, connections,
            levels, room_z_offsets,
            world.world_uid, building.location_uid, rng,
            world=world, template=template, staircases=staircases,
            building_tier=ctx.economic_tier if ctx is not None else None,
            ground_z=ground_z,
        )
        logger.info("passages | count=%d  total_cells=%d", len(passages), len(cells_dict))
        return passages

    # ------------------------------------------------------------------
    # Phase: wall openings

    def _place_wall_openings(
        self,
        template: StructureTemplate,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        cells_dict: dict[tuple, MapCell],
        world: World,
        rng: Random,
        ground_z: int,
        *,
        definitions: list[LevelDef],
    ) -> None:
        logger.info("=== PHASE: wall openings ===")

        for level_def in definitions:
            z_offset    = level_def.z_offset
            level       = levels[z_offset]
            level_rooms = [
                r for r in all_rooms
                if r.z_offset == z_offset and r.placed
            ]
            level_fp: set[tuple[int, int]] = set()
            for r in level_rooms:
                level_fp |= r.get_footprint()
            place_wall_openings(
                level_rooms, level_fp, cells_dict, level,
                world, building.location_uid, rng,
                ground_z=ground_z,
            )

    # ------------------------------------------------------------------
    # Phase: assemble result

    def _assemble_result(
        self,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        room_uids: dict[str, str],
        cells_dict: dict[tuple, MapCell],
        passages: list[LocationPassage],
    ) -> StructureLayout:
        logger.info("=== PHASE: assemble result ===")
        named_locations = [
            _room_to_named_location(
                room, building,
                levels[room.z_offset],
                room_uids[room.uid_key],
            )
            for room in all_rooms
            if room.placed and not room.is_shaft
        ]
        cell_list = list(cells_dict.values())
        ground_z = building.map_z or 0
        return StructureLayout(
            cells=cell_list,
            levels=list(levels.values()),
            passages=passages,
            rooms=named_locations,
            occupied_footprint=compute_occupied_footprint(cell_list, ground_z),
        )

    def validate_template(self, data: dict) -> list[str]:
        return []
