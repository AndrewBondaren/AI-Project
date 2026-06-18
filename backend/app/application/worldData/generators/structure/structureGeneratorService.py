import hashlib
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random

logger = logging.getLogger(__name__)

from app.application.worldData.generators.structure.cellBuilder import build_level_cells
from app.application.worldData.generators.structure.errors import GenerationError, UnsupportedShapeError
from app.application.worldData.generators.structure.layoutEngine import layout_level
from app.application.worldData.generators.structure.passages import build_passages
from app.application.worldData.generators.structure.roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase.shaftFactory import (
    instantiate_shaft_rooms, _NO_SHAFT_TYPES,
)
from app.application.worldData.generators.structure.staircase.shaftPlacer import make_shaft_placer
from app.application.worldData.generators.structure.structurePostProcess import run as _post_process
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

__all__ = ["StructureGeneratorService", "StructureLayout", "UnsupportedShapeError", "GenerationError"]


@dataclass
class StructureLayout:
    cells:    list[MapCell]
    levels:   list[LocationLevel]
    passages: list[LocationPassage]
    rooms:    list[NamedLocation]


# ---------------------------------------------------------------------------
# Seed + z helpers

def _det_uuid(namespace: str, *parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, namespace + "|" + "|".join(parts)))


def _make_seed(world_uid: str, building_uid: str) -> int:
    raw = (world_uid + building_uid).encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _resolve_z_heights(template: dict) -> dict[int, int]:
    """z_offset → effective z_height."""
    default = template.get("default_z_height", 3)
    return {
        level_def["z_offset"]: level_def.get("z_height") or default
        for level_def in template["levels"]
    }


def _compute_level_z(building_map_z: int, z_offset: int, z_heights: dict[int, int]) -> int:
    if z_offset == 0:
        return building_map_z
    if z_offset > 0:
        return building_map_z + sum(z_heights[k] for k in range(0, z_offset))
    return building_map_z - sum(z_heights[k] for k in range(z_offset, 0))


def _build_levels(template: dict, building: NamedLocation,
                  z_heights: dict[int, int]) -> dict[int, LocationLevel]:
    return {
        level_def["z_offset"]: LocationLevel(
            level_uid=_det_uuid(building.location_uid, f"level_{level_def['z_offset']}"),
            location_uid=building.location_uid,
            z=_compute_level_z(building.map_z, level_def["z_offset"], z_heights),
            z_height=z_heights[level_def["z_offset"]],
            display_name=level_def["display_name"],
            isolated=level_def.get("isolated", False),
            access_mechanic=level_def.get("access_mechanic", []),
        )
        for level_def in template["levels"]
    }


# ---------------------------------------------------------------------------
# Level layout ordering — propagate staircase anchors across levels

def _staircase_layout_order(
    template: dict,
    room_z_offsets: dict[str, int],
) -> list[int]:
    """
    BFS from z_offset=0 through staircase stops.
    Ensures each level is laid out only after its staircase-connected neighbour,
    so we can propagate anchor positions.
    Unreachable levels are appended at the end in template order.
    """
    all_z = [level_def["z_offset"] for level_def in template["levels"]]
    adj: dict[int, list[int]] = {z: [] for z in all_z}
    for sc in template.get("staircases", []):
        stops = sc.get("stops", [])
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
    return order


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
    )


# ---------------------------------------------------------------------------
# Service

class StructureGeneratorService:
    """
    Pure utility — no repositories, no async.
    Deterministic: same world_uid + same building_uid → same layout.
    Generates interior box: rooms, walls, passages.
    Foundation + roof + porch — StructureAssembler (layer above).
    """

    def generate_from_template(
        self,
        world: World,
        building: NamedLocation,
        template: dict,
    ) -> StructureLayout:
        logger.info(
            "generate_from_template | start building=%s template=%s",
            building.location_uid, template.get("system_name", "?"),
        )

        rng = Random(_make_seed(world.world_uid, building.location_uid))

        z_heights = _resolve_z_heights(template)
        levels    = _build_levels(template, building, z_heights)
        logger.info("levels resolved: %s", {z: (l.z, l.z_height) for z, l in levels.items()})

        all_rooms, room_z_offsets, shaft_by_staircase = self._instantiate_rooms(
            template, building, levels, world, rng,
        )
        self._layout_rooms(template, building, all_rooms, room_z_offsets, shaft_by_staircase)

        cells_dict, room_uids = self._generate_cells(template, building, levels, all_rooms, world)

        passages = self._run_passages(
            template, building, levels, all_rooms, room_z_offsets, cells_dict, world, rng,
        )

        _post_process(cells_dict)

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
        template: dict,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        world: World,
        rng: Random,
    ) -> tuple[list[_RoomInstance], dict[str, int], dict[str, list[_RoomInstance]]]:
        """Steps 2-3: instantiate template rooms + shaft rooms per level."""
        logger.info("=== PHASE: instantiate rooms ===")
        all_rooms: list[_RoomInstance] = []
        room_z_offsets: dict[str, int] = {}

        for level_def in template["levels"]:
            z_offset    = level_def["z_offset"]
            level       = levels[z_offset]
            level_rooms = instantiate_level_rooms(
                level_def, template, level.z_height, z_offset, world, rng,
                building_tier=building.system_economic_tier,
            )
            for room in level_rooms:
                room_z_offsets[room.room_id] = z_offset
                if room.staircase_type:
                    logger.info("post-instantiate: %r staircase_type=%r", room.room_id, room.staircase_type)
            all_rooms.extend(level_rooms)
            logger.info("instantiate | z_offset=%d rooms=%d", z_offset, len(level_rooms))

        shaft_rooms = instantiate_shaft_rooms(
            template, room_z_offsets, levels, world, rng,
            building_tier=building.system_economic_tier,
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

    # ------------------------------------------------------------------
    # Phase: layout

    def _layout_rooms(
        self,
        template: dict,
        building: NamedLocation,
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
    ) -> None:
        """Steps 4-5: place rooms on XY per level; mutates all_rooms in-place."""
        logger.info("=== PHASE: layout (order propagation) ===")
        bx = building.map_x or 0
        by = building.map_y or 0
        connections = template.get("connections", [])

        layout_order = _staircase_layout_order(template, room_z_offsets)
        level_start: dict[int, tuple[int, int]] = {layout_order[0]: (bx, by)}
        all_placed_by_id: dict[str, _RoomInstance] = {}
        level_footprint_bounds: dict[int, tuple[int, int, int, int]] = {}

        for z_offset in layout_order:
            start_x, start_y = level_start.get(z_offset, (bx, by))
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset]

            synth_conns = self._build_synth_conns(
                connections, template, z_offset, room_z_offsets, shaft_by_staircase,
            )

            parent_bounds = level_footprint_bounds.get(z_offset - 1) if z_offset > 0 else None
            layout_level(level_rooms, synth_conns, start_x, start_y, bounds=parent_bounds)

            for r in level_rooms:
                if r.placed:
                    all_placed_by_id[r.room_id] = r

            self._place_level_shafts(
                z_offset, template, all_rooms, room_z_offsets,
                shaft_by_staircase, all_placed_by_id, level_start,
            )
            self._propagate_trapdoor_starts(
                z_offset, template, room_z_offsets, all_placed_by_id, level_start,
            )

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
        connections: list[dict],
        template: dict,
        z_offset: int,
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
    ) -> list[dict]:
        """Synthetic archway connections: shaft ↔ to_room for the current level."""
        synth = list(connections)
        for sc in template.get("staircases", []):
            if sc.get("staircase_type", "u_shape") in _NO_SHAFT_TYPES:
                continue
            sc_id      = sc.get("staircase_id", "staircase")
            stops      = sc.get("stops", [])
            shaft_list = shaft_by_staircase.get(sc_id, [])
            for i, stop_id in enumerate(stops):
                if i == 0:
                    continue
                if room_z_offsets.get(stop_id) != z_offset:
                    continue
                if i < len(shaft_list):
                    synth.append({
                        "from_room":    shaft_list[i].room_id,
                        "to_room":      stop_id,
                        "passage_type": "archway",
                    })
        return synth

    def _place_level_shafts(
        self,
        z_offset: int,
        template: dict,
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        shaft_by_staircase: dict[str, list[_RoomInstance]],
        all_placed_by_id: dict[str, _RoomInstance],
        level_start: dict[int, tuple[int, int]],
    ) -> None:
        """AdjacentShaftPlacer for fr_z shaft instances; propagates level_start to to_z levels."""
        for sc in template.get("staircases", []):
            if sc.get("staircase_type", "u_shape") in _NO_SHAFT_TYPES:
                continue
            sc_id  = sc.get("staircase_id", "staircase")
            stops  = sc.get("stops", [])
            if not stops or room_z_offsets.get(stops[0]) != z_offset:
                continue

            fr_room    = all_placed_by_id.get(stops[0])
            shaft_list = shaft_by_staircase.get(sc_id, [])
            if fr_room is None or not shaft_list:
                continue

            shaft_fr        = shaft_list[0]
            placed_on_level = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            placer          = make_shaft_placer(sc)
            success         = placer.place(shaft_fr, fr_room, placed_on_level)

            if success:
                for shaft_other in shaft_list[1:]:
                    shaft_other.origin_x = shaft_fr.origin_x
                    shaft_other.origin_y = shaft_fr.origin_y
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
        template: dict,
        room_z_offsets: dict[str, int],
        all_placed_by_id: dict[str, _RoomInstance],
        level_start: dict[int, tuple[int, int]],
    ) -> None:
        """No-shaft staircases (trapdoor): align target level to the placed anchor room."""
        for sc in template.get("staircases", []):
            if sc.get("staircase_type") not in _NO_SHAFT_TYPES:
                continue
            sc_id = sc.get("staircase_id", "?")
            stops = sc.get("stops", [])
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
        template: dict,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        world: World,
    ) -> tuple[dict[tuple, MapCell], dict[str, str]]:
        """Steps 6-8: assign UIDs, generate cells per level."""
        logger.info("=== PHASE: cell generation ===")
        connections = template.get("connections", [])
        wall_mat    = building.parent_wall_material or "stone"

        room_uids: dict[str, str] = {
            room.uid_key: _det_uuid(building.location_uid, room.uid_key)
            for room in all_rooms
            if room.placed and not room.is_shaft
        }

        cells_dict: dict[tuple, MapCell] = {}
        for level_def in template["levels"]:
            z_offset    = level_def["z_offset"]
            level       = levels[z_offset]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            before      = len(cells_dict)
            for cell in build_level_cells(
                level_rooms, connections, level.z, level.z_height,
                world.world_uid, building.location_uid, wall_mat, room_uids,
            ):
                cells_dict[(cell.x, cell.y, cell.z)] = cell
            logger.info("cells | z_offset=%d generated=%d", z_offset, len(cells_dict) - before)

        return cells_dict, room_uids

    # ------------------------------------------------------------------
    # Phase: passages

    def _run_passages(
        self,
        template: dict,
        building: NamedLocation,
        levels: dict[int, LocationLevel],
        all_rooms: list[_RoomInstance],
        room_z_offsets: dict[str, int],
        cells_dict: dict[tuple, MapCell],
        world: World,
        rng: Random,
    ) -> list[LocationPassage]:
        """Steps 9-11: build passages (mutates cells_dict for door/staircase cells)."""
        for r in all_rooms:
            if r.staircase_type:
                logger.info("pre-passages room staircase_type: %r  %r", r.room_id, r.staircase_type)
        passages = build_passages(
            cells_dict, all_rooms, template.get("connections", []),
            levels, room_z_offsets,
            world.world_uid, building.location_uid, rng,
            world=world, template=template,
            building_tier=building.system_economic_tier,
        )
        logger.info("passages | count=%d  total_cells=%d", len(passages), len(cells_dict))
        return passages

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
        return StructureLayout(
            cells=list(cells_dict.values()),
            levels=list(levels.values()),
            passages=passages,
            rooms=named_locations,
        )

    def validate_template(self, data: dict) -> list[str]:
        raise NotImplementedError
