"""
Создаёт _RoomInstance объекты из room_def шаблона.
Решает: count, shape_type, размеры, shape_params, материалы, z_height.
Координаты (origin_x/y) не проставляются — это задача _layoutEngine.
"""
import logging
from random import Random

from app.application.worldData.generators.structure._errors import UnsupportedShapeError
from app.application.worldData.generators.structure._materialResolver import resolve_room_materials
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.application.worldData.generators.structure.roomSize import ROOM_SIZE_PRESETS, RoomSize
from app.application.worldData.generators.structure.shapeType import ShapeType, _V1_SHAPES
from app.db.models.world import World

logger = logging.getLogger(__name__)

_SHAPES_WITHOUT_DEPTH = {ShapeType.SQUARE, ShapeType.CIRCLE, ShapeType.SEMICIRCLE}


def _resolve_shape(room_def: dict, rng: Random) -> ShapeType:
    raw = room_def["shape_type"]
    chosen = rng.choice(raw) if isinstance(raw, list) else raw
    try:
        st = ShapeType(chosen)
    except ValueError:
        raise UnsupportedShapeError(f"Unknown shape_type: {chosen!r}")
    if st not in _V1_SHAPES:
        raise UnsupportedShapeError(f"shape_type {chosen!r} not supported in v1")
    return st


def _resolve_size(
    room_def: dict,
    shape: ShapeType,
    level_z_height: int,
    rng: Random,
) -> tuple[int, int, int]:
    """Возвращает (width, depth, room_z_height)."""
    size = room_def["size"]
    size_type = size.get("size_type")

    if size_type:
        preset = ROOM_SIZE_PRESETS[RoomSize(size_type)]
        wr = preset.width_range
        dr = preset.depth_range
        zr = size.get("z_range") or list(preset.z_range)
    else:
        wr = size["width_range"]
        dr = size.get("depth_range", [3, 3])
        zr = size.get("z_range", [3, 3])

    width = rng.randint(wr[0], wr[1])
    depth = rng.randint(dr[0], dr[1]) if shape not in _SHAPES_WITHOUT_DEPTH else width

    room_z = rng.randint(zr[0], zr[1])
    if room_z > level_z_height:
        logger.warning(
            "Room %r: z_range дало %d, уровень ограничен %d — потолок обрезан",
            room_def["room_id"], room_z, level_z_height,
        )
        room_z = level_z_height

    return width, depth, room_z


def _resolve_shape_params(room_def: dict, rng: Random) -> dict:
    raw = room_def.get("shape_params") or {}
    params: dict = {}

    if room_def.get("shape_type") in ("l_shape", ["l_shape"]):
        awr = raw.get("arm_width_range", [2, 3])
        adr = raw.get("arm_depth_range", [2, 3])
        corner = raw.get("arm_corner", "any")
        if corner == "any":
            corner = rng.choice(["northeast", "northwest", "southeast", "southwest"])
        params = {
            "arm_width": rng.randint(awr[0], awr[1]),
            "arm_depth": rng.randint(adr[0], adr[1]),
            "arm_corner": corner,
        }

    elif room_def.get("shape_type") in ("t_shape", ["t_shape"]):
        swr = raw.get("stem_width_range", [2, 3])
        wall = raw.get("stem_wall", "any")
        if wall == "any":
            wall = rng.choice(["north", "south", "east", "west"])
        params = {
            "stem_width": rng.randint(swr[0], swr[1]),
            "stem_wall": wall,
        }

    return params


def instantiate_level_rooms(
    level_def: dict,
    template: dict,
    level_z_height: int,
    z_offset: int,
    world: World,
    rng: Random,
) -> list[_RoomInstance]:
    instances: list[_RoomInstance] = []

    for room_def in level_def["rooms"]:
        room_id = room_def["room_id"]
        required = room_def["required"]

        # Resolve count
        if required:
            count = room_def.get("count", 1)
        else:
            cr = room_def["count_range"]
            count = rng.randint(cr[0], cr[1])

        shape = _resolve_shape(room_def, rng)
        shape_params = _resolve_shape_params(room_def, rng)
        width, depth, room_z = _resolve_size(room_def, shape, level_z_height, rng)

        room_tier = room_def.get("economic_tier")
        template_tier = template.get("economic_tier")
        wall_mat, floor_mat = resolve_room_materials(world, room_tier, template_tier, rng, room_id=room_id)

        for idx in range(count):
            suffix = f" {idx + 1}" if count > 1 else ""
            instances.append(_RoomInstance(
                room_id=room_id,
                instance_idx=idx,
                z_offset=z_offset,
                shape_type=shape.value,
                width=width,
                depth=depth,
                z_height=room_z,
                display_name=room_def["display_name"] + suffix,
                room_type=room_def["room_type"],
                is_public=room_def["is_public"],
                is_forbidden=room_def["is_forbidden"],
                required=required,
                wall_material=wall_mat,
                floor_material=floor_mat,
                attach_to=room_def.get("attach_to"),
                attach_wall=room_def.get("attach_wall"),
                perimeter_required=room_def.get("perimeter_required", False),
                underground_fallback=room_def.get("underground_fallback", False),
                entry_point=room_def.get("entry_point"),
                back_entry_point=room_def.get("back_entry_point"),
                shape_params=shape_params,
            ))

    return instances
