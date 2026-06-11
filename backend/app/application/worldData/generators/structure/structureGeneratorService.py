import hashlib
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from random import Random

logger = logging.getLogger(__name__)

from app.application.worldData.generators.structure._cellBuilder import build_level_cells
from app.application.worldData.generators.structure._errors import GenerationError, UnsupportedShapeError
from app.application.worldData.generators.structure._layoutEngine import layout_level
from app.application.worldData.generators.structure._passageBuilder import build_passages
from app.application.worldData.generators.structure._roomFactory import instantiate_level_rooms
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.application.worldData.generators.structure.staircase._shaftFactory import (
    instantiate_shaft_rooms, _NO_SHAFT_TYPES,
)
from app.application.worldData.generators.structure.staircase._shaftPlacer import make_shaft_placer
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
        template_name = template.get("system_name", "?")
        logger.info(
            "generate_from_template | start building=%s template=%s",
            building.location_uid, template_name,
        )

        rng = Random(_make_seed(world.world_uid, building.location_uid))

        # Step 1: levels
        logger.info("=== PHASE: resolve levels ===")
        z_heights = _resolve_z_heights(template)
        levels    = _build_levels(template, building, z_heights)   # z_offset → LocationLevel
        logger.info("levels resolved: %s", {z: (l.z, l.z_height) for z, l in levels.items()})

        # Step 2–3: instantiate rooms per level
        logger.info("=== PHASE: instantiate rooms ===")
        all_rooms: list[_RoomInstance] = []
        room_z_offsets: dict[str, int] = {}   # room_id → z_offset

        for level_def in template["levels"]:
            z_offset   = level_def["z_offset"]
            level      = levels[z_offset]
            level_rooms = instantiate_level_rooms(
                level_def, template, level.z_height, z_offset, world, rng,
                building_tier=building.system_economic_tier,
            )
            for room in level_rooms:
                room_z_offsets[room.room_id] = z_offset
                if room.staircase_type:
                    logger.info("post-instantiate: %r staircase_type=%r", room.room_id, room.staircase_type)
            all_rooms.extend(level_rooms)
            logger.info(
                "generate_from_template | z_offset=%d instantiated %d rooms",
                z_offset, len(level_rooms),
            )

        # Instantiate shaft rooms from staircases[] and add to all_rooms
        shaft_rooms = instantiate_shaft_rooms(
            template, room_z_offsets, levels, world, rng,
            building_tier=building.system_economic_tier,
        )
        for sr in shaft_rooms:
            room_z_offsets[sr.room_id] = sr.z_offset
        all_rooms.extend(shaft_rooms)

        # Build lookup: staircase_id → shaft instances ordered by instance_idx (bottom→top)
        shaft_by_staircase: dict[str, list[_RoomInstance]] = {}
        for sr in shaft_rooms:
            if sr.staircase_id:
                shaft_by_staircase.setdefault(sr.staircase_id, []).append(sr)
        for lst in shaft_by_staircase.values():
            lst.sort(key=lambda r: r.instance_idx)

        logger.info(
            "generate_from_template | shaft rooms instantiated: %d across %d staircases",
            len(shaft_rooms), len(shaft_by_staircase),
        )

        # Step 4–5: layout per level
        logger.info("=== PHASE: layout (order propagation) ===")
        # Propagate staircase anchor positions: z_offset=0 first, then connected levels
        # so that each level starts where its staircase lands on the source level.
        bx = building.map_x or 0
        by = building.map_y or 0
        connections = template.get("connections", [])

        layout_order = _staircase_layout_order(template, room_z_offsets)
        level_start: dict[int, tuple[int, int]] = {layout_order[0]: (bx, by)}

        # Index placed rooms by id — built incrementally as levels are laid out
        all_placed_by_id: dict[str, _RoomInstance] = {}

        # Footprint bounds per z_offset — used to constrain attach_to rooms on adjacent levels.
        # Tuple is (x_min, y_min, x_max, y_max) of all placed room cells on that level.
        level_footprint_bounds: dict[int, tuple[int, int, int, int]] = {}

        for z_offset in layout_order:
            start_x, start_y = level_start.get(z_offset, (bx, by))
            level       = levels[z_offset]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset]

            # Build synthetic archway connections: shaft (pre-placed on to_z) ↔ to_room.
            # These give BFS a graph edge so corridor is placed adjacent to the shaft.
            synth_conns = list(connections)
            for sc in template.get("staircases", []):
                sc_type = sc.get("staircase_type", "u_shape")
                if sc_type in _NO_SHAFT_TYPES:
                    continue
                sc_id   = sc.get("staircase_id", "staircase")
                stops   = sc.get("stops", [])
                shaft_list = shaft_by_staircase.get(sc_id, [])
                for i, stop_id in enumerate(stops):
                    if i == 0:
                        continue  # fr_stop shaft is placed by AdjacentShaftPlacer, not BFS
                    if room_z_offsets.get(stop_id) != z_offset:
                        continue
                    if i < len(shaft_list):
                        synth_conns.append({
                            "from_room": shaft_list[i].room_id,
                            "to_room":   stop_id,
                            "passage_type": "archway",
                        })

            # Pass parent-level bounds so rooms on upper floors don't overhang the floor below.
            # Only z_offset > 0 (above-ground): upper floors constrained by floor directly below.
            # z_offset <= 0 (ground + underground): cellars extend freely — dug into the ground.
            if z_offset > 0:
                parent_bounds = level_footprint_bounds.get(z_offset - 1)
            else:
                parent_bounds = None

            layout_level(level_rooms, synth_conns, start_x, start_y, bounds=parent_bounds)

            # Record rooms placed by BFS now so AdjacentShaftPlacer can find fr_room.
            for r in level_rooms:
                if r.placed:
                    all_placed_by_id[r.room_id] = r

            # AdjacentShaftPlacer: place fr_z shaft instances after BFS on this level.
            # (to_z shafts are already pre-placed by XY alignment from a previous iteration.)
            for sc in template.get("staircases", []):
                sc_type = sc.get("staircase_type", "u_shape")
                if sc_type in _NO_SHAFT_TYPES:
                    continue
                sc_id  = sc.get("staircase_id", "staircase")
                stops  = sc.get("stops", [])
                if not stops:
                    continue
                fr_stop_z = room_z_offsets.get(stops[0])
                if fr_stop_z != z_offset:
                    continue  # this staircase doesn't start on current level

                fr_room = all_placed_by_id.get(stops[0])
                if fr_room is None:
                    continue

                shaft_list = shaft_by_staircase.get(sc_id, [])
                if not shaft_list:
                    continue
                shaft_fr = shaft_list[0]  # idx=0, fr_z shaft

                placed_on_level = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
                placer = make_shaft_placer(sc)
                success = placer.place(shaft_fr, fr_room, placed_on_level)

                if success:
                    # Multi-stop XY alignment: all other shaft instances → same XY as shaft_fr
                    for shaft_other in shaft_list[1:]:
                        shaft_other.origin_x = shaft_fr.origin_x
                        shaft_other.origin_y = shaft_fr.origin_y

                    # Set level_start for all to_z levels of this staircase
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

            # Record this level's footprint bounds for use by adjacent levels.
            # Run after shaft placer so shaft cells are included in bounds.
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
                logger.info(
                    "layout | z_offset=%d footprint_bounds=%s",
                    z_offset, level_footprint_bounds[z_offset],
                )

            placed_count  = sum(1 for r in placed_rooms_this)
            skipped = len(level_rooms) - placed_count
            logger.info(
                "layout | z_offset=%d start=(%d,%d) placed=%d skipped=%d",
                z_offset, start_x, start_y, placed_count, skipped,
            )
            for r in level_rooms:
                if r.placed:
                    logger.info(
                        "layout | z_offset=%d  room=%-20s  origin=(%d,%d)  size=%dx%d  extra_cells=%d",
                        z_offset, r.room_id, r.origin_x, r.origin_y,
                        r.width, r.depth, len(r.extra_cells),
                    )
                else:
                    logger.warning("layout | z_offset=%d  room=%s NOT PLACED", z_offset, r.room_id)
            if skipped:
                skipped_ids = [r.room_id for r in level_rooms if not r.placed]
                logger.warning(
                    "layout | z_offset=%d rooms not placed: %s",
                    z_offset, skipped_ids,
                )

            # Also record shaft rooms placed after BFS (AdjacentShaftPlacer output)
            for r in all_rooms:
                if r.z_offset == z_offset and r.placed and r.room_id not in all_placed_by_id:
                    all_placed_by_id[r.room_id] = r

        # Step 5.5: stairwell mutation skipped — room size pre-set by template (ТЗ § 8)

        # Step 6–8: assign UIDs + generate cells per level
        logger.info("=== PHASE: cell generation ===")
        room_uids: dict[str, str] = {}   # uid_key → location_uid (shaft rooms excluded)
        for room in all_rooms:
            if room.placed and not room.is_shaft:
                uid = _det_uuid(building.location_uid, room.uid_key)
                room_uids[room.uid_key] = uid

        cells_dict: dict[tuple, MapCell] = {}
        for level_def in template["levels"]:
            z_offset    = level_def["z_offset"]
            level       = levels[z_offset]
            level_rooms = [r for r in all_rooms if r.z_offset == z_offset and r.placed]
            wall_mat    = building.parent_wall_material or "stone"

            before = len(cells_dict)
            for cell in build_level_cells(
                level_rooms, connections, level.z, level.z_height,
                world.world_uid, building.location_uid,
                wall_mat, room_uids,
            ):
                cells_dict[(cell.x, cell.y, cell.z)] = cell
            logger.info(
                "generate_from_template | z_offset=%d cells generated: %d",
                z_offset, len(cells_dict) - before,
            )

        # Step 9–11: passages (mutates cells_dict for door/staircase cells)
        for _r in all_rooms:
            if _r.staircase_type:
                logger.info("pre-passages room staircase_type: %r  %r", _r.room_id, _r.staircase_type)
        passages = build_passages(
            cells_dict, all_rooms, connections,
            levels, room_z_offsets,
            world.world_uid, building.location_uid, rng,
            world=world, template=template,
            building_tier=building.system_economic_tier,
        )
        logger.info(
            "generate_from_template | passages=%d total_cells=%d",
            len(passages), len(cells_dict),
        )

        # Step 12: post-processing (railings, windows, …)
        logger.info("=== PHASE: post_process ===")
        from app.application.worldData.generators.structure._structurePostProcess import run as post_process
        post_process(cells_dict)

        # Step 13: assemble result
        logger.info("=== PHASE: assemble result ===")
        placed_rooms = [r for r in all_rooms if r.placed and not r.is_shaft]
        named_locations = [
            _room_to_named_location(
                room, building,
                levels[room.z_offset],
                room_uids[room.uid_key],
            )
            for room in placed_rooms
        ]

        logger.info(
            "generate_from_template | done building=%s rooms=%d cells=%d passages=%d",
            building.location_uid, len(named_locations),
            len(cells_dict), len(passages),
        )

        return StructureLayout(
            cells=list(cells_dict.values()),
            levels=list(levels.values()),
            passages=passages,
            rooms=named_locations,
        )

    def validate_template(self, data: dict) -> list[str]:
        raise NotImplementedError
