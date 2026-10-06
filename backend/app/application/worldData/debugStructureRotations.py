"""In-memory rotation diagnostics; no envelope, repositories or persistence."""

from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import logging

from app.application.worldData.context.locationScope import debug_building_context
from app.application.worldData.facingArrows import FACING_ARROW
from app.application.worldData.generators.structure.errors import GenerationError
from app.application.worldData.generators.structure.gridRenderer import render_all_levels
from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService, compute_occupied_footprint
from app.application.worldData.generators.structure.structureOrientation import entry_orientation
from app.dataModel.spatial.facing import Facing
from app.dataModel.locations.transitions.transitionType import TransitionType


class RotationProbe(StructureGeneratorService):
    """Retain runtime room bounds that NamedLocation deliberately does not store."""
    def _assemble_result(self, building, levels, all_rooms, room_uids, cells_dict, passages):
        self.runtime_rooms = deepcopy(all_rooms)
        self.room_uids = dict(room_uids)
        return super()._assemble_result(building, levels, all_rooms, room_uids, cells_dict, passages)


def compare_rotation(base, base_probe, actual, actual_probe, orientation, ground_z):
    cells = {(c.x, c.y, c.z): deepcopy(c) for c in base.cells}
    passages = deepcopy(base.transitions)
    rooms = deepcopy(base_probe.runtime_rooms)
    orientation.apply(cells, passages, rooms)
    origins = {base_probe.room_uids[r.uid_key]: (r.origin_x, r.origin_y) for r in rooms if r.placed and not r.is_shaft}
    expected_locations = [replace(r, map_x=origins[r.location_uid][0], map_y=origins[r.location_uid][1], created_at="") for r in base.rooms]
    checks = {
        "cells": cells == {(c.x, c.y, c.z): c for c in actual.cells},
        "passages": passages == actual.transitions,
        "rooms": rooms == actual_probe.runtime_rooms and expected_locations == [replace(r, created_at="") for r in actual.rooms],
        "levels": base.levels == actual.levels,
        "occupied_footprint": compute_occupied_footprint(list(cells.values()), ground_z) == actual.occupied_footprint,
    }
    return {"matches": all(checks.values()), "checks": checks}


def rotation_payload(layout, probe):
    levels = {level.level_uid: level.z for level in layout.levels}
    cells = {(c.x, c.y, c.z): c for c in layout.cells}
    markers = {}
    for passage in layout.passages:
        if passage.system_passage_type == TransitionType.STAIRCASE:
            z = levels.get(passage.to_level_uid)
            if z is not None:
                markers[(passage.to_x, passage.to_y, z)] = "$"
            z = levels.get(passage.from_level_uid)
            if z is not None:
                cell = cells.get((passage.from_x, passage.from_y, z))
                if cell and cell.system_facing:
                    markers[(passage.from_x, passage.from_y, z)] = FACING_ARROW.get(Facing(cell.system_facing), "@")
        elif passage.system_passage_type == TransitionType.MAIN_ENTRANCE:
            z = levels.get(passage.to_level_uid)
            if z is not None:
                markers[(passage.to_x, passage.to_y, z)] = "E"
    bounds = {probe.room_uids[r.uid_key]: {"width": r.width, "depth": r.depth} for r in probe.runtime_rooms if r.placed and not r.is_shaft}
    return {
        "summary": {"levels": len(layout.levels), "rooms": len(layout.rooms), "cells": len(layout.cells), "passages": len(layout.passages), "elements": dict(Counter(c.system_building_element for c in layout.cells))},
        "cells": [asdict(c) for c in layout.cells],
        "rooms": [{**asdict(r), **bounds[r.location_uid]} for r in layout.rooms],
        "levels": [asdict(level) for level in layout.levels],
        "passages": [asdict(p) for p in layout.passages],
        "occupied_footprint": asdict(layout.occupied_footprint) if layout.occupied_footprint else None,
        "grids": {str(z): grid for z, grid in render_all_levels(layout.cells, markers=markers).items()},
    }


def generate_rotations(world, building, structure, plot, capture_factory):
    logger = logging.getLogger("app.application.worldData.generators")
    ctx = debug_building_context(world, building, plot)

    def run(facing):
        probe = RotationProbe()
        capture = capture_factory()
        logger.addHandler(capture)
        try:
            layout = probe.generate_from_template(world, building, structure, facing=facing, ctx=ctx)
            return layout, probe, {"status": "ok", **rotation_payload(layout, probe), "warnings": capture.records}
        except GenerationError as exc:
            return None, probe, {"status": "error", "error": str(exc), "warnings": capture.records}
        finally:
            logger.removeHandler(capture)

    base, base_probe, baseline = run(None)
    variants, equivalence = {}, {}
    for facing in (Facing.NORTH, Facing.EAST, Facing.SOUTH, Facing.WEST):
        layout, probe, payload = run(facing)
        variants[facing.value] = payload
        if base is None or layout is None:
            equivalence[facing.value] = {"matches": None, "status": "unavailable"}
            continue
        orientation = entry_orientation(base_probe.runtime_rooms, base.transitions, structure.system_name, facing)
        equivalence[facing.value] = compare_rotation(base, base_probe, layout, probe, orientation, building.map_z or 0)
    return {"baseline": baseline, "rotations": variants, "equivalence": equivalence}
