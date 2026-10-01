"""
Создаёт _RoomInstance объекты из room_def шаблона.
Решает: count, shape_type, размеры, shape_params, материалы, z_height.
Координаты (origin_x/y) не проставляются — это задача _layoutEngine.
"""
import logging
from random import Random

from app.application.worldData.generators.structure.errors import UnsupportedShapeError
from app.dataModel.structure.room.roomDef import RoomDef
from app.dataModel.structure.building.levelDef import LevelDef
from app.application.worldData.generators.utils.materialResolver import resolve_room_materials
from app.application.worldData.generators.structure.room.roomInstance import _RoomInstance
from app.application.worldData.generators.structure.shapeResolver import SizeShapeResolver
from app.dataModel.structure.building.structureTemplate import StructureTemplate
from app.dataModel.spatial.facing import CARDINAL_FACINGS
from app.application.worldData.generators.structure.shapeType import ShapeType, _V1_SHAPES
from app.application.worldData.generators.structure.shapes import resolve_stem_wall
from app.db.models.world import World

logger = logging.getLogger(__name__)

_SHAPES_WITHOUT_DEPTH = {ShapeType.SQUARE, ShapeType.CIRCLE, ShapeType.SEMICIRCLE}


def _resolve_shape(room_def: RoomDef, rng: Random) -> ShapeType:
    if room_def.shape_type is None:
        return SizeShapeResolver.from_size_def(room_def.size)
    raw = room_def.shape_type
    chosen = rng.choice(raw) if isinstance(raw, list) else raw
    try:
        st = ShapeType(chosen)
    except ValueError:
        raise UnsupportedShapeError(f"Unknown shape_type: {chosen!r}")
    if st not in _V1_SHAPES:
        raise UnsupportedShapeError(f"shape_type {chosen!r} not supported in v1")
    return st


def _resolve_size(
    room_def: RoomDef,
    shape: ShapeType,
    level_z_height: int,
    rng: Random,
    template_z_height: int | None = None,
) -> tuple[int, int, int]:
    """Возвращает (width, depth, room_z_height)."""
    size = room_def.size
    wr = size.resolved_width_range
    dr = size.resolved_depth_range
    zr = size.height_range(level_z_height, template_z_height)

    width = rng.randint(wr[0], wr[1])
    depth = rng.randint(dr[0], dr[1]) if shape not in _SHAPES_WITHOUT_DEPTH else width

    room_z = rng.randint(zr[0], zr[1])
    if room_z > level_z_height:
        logger.warning(
            "Room %r: z_range дало %d, уровень ограничен %d — потолок обрезан",
            room_def.room_id, room_z, level_z_height,
        )
        room_z = level_z_height

    return width, depth, room_z


def _resolve_shape_params(room_def: RoomDef, chosen_shape: ShapeType, rng: Random) -> dict:
    raw = room_def.shape_params
    params: dict = {}

    if chosen_shape is ShapeType.L_SHAPE:
        if raw is None or raw.arm_width_range is None or raw.arm_depth_range is None:
            logger.error(
                "Room '%s': incomplete shape_params for %s — using footprint defaults",
                room_def.room_id, chosen_shape.value,
            )
            return params
        awr = raw.arm_width_range
        adr = raw.arm_depth_range
        corner = raw.arm_corner
        if corner == "any":
            corner = rng.choice(["northeast", "northwest", "southeast", "southwest"])
        params = {
            "arm_width": rng.randint(awr[0], awr[1]),
            "arm_depth": rng.randint(adr[0], adr[1]),
            "arm_corner": corner,
        }

    elif chosen_shape is ShapeType.T_SHAPE:
        if raw is None or raw.stem_width_range is None:
            logger.error(
                "Room '%s': incomplete shape_params for %s — using footprint defaults",
                room_def.room_id, chosen_shape.value,
            )
            return params
        swr = raw.stem_width_range
        wall = raw.stem_wall
        if wall == "any":
            wall = rng.choice(list(CARDINAL_FACINGS)).value
        params = {
            "stem_width": rng.randint(swr[0], swr[1]),
            "stem_wall": wall,
        }

    return params


def instantiate_level_rooms(
    level_def: LevelDef,
    template: StructureTemplate,
    level_z_height: int,
    z_offset: int,
    world: World,
    rng: Random,
    building_tier: str | None = None,
    template_z_height: int | None = None,
    *,
    building_band: str | None = None,
) -> list[_RoomInstance]:
    instances: list[_RoomInstance] = []

    for room_def in level_def.rooms:
        room_id = room_def.room_id
        for index, spec in enumerate(room_def.wall_openings):
            for name, original in spec.substitutions:
                logger.error(
                    "Structure '%s' room '%s': wall_openings[%d].%s=%s — auto-resolve",
                    template.system_name, room_id, index, name, original,
                )
        if len(room_def.wall_openings) > 1:
            logger.error(
                "Structure '%s' room '%s': wall_openings entries after first ignored (%d)",
                template.system_name, room_id, len(room_def.wall_openings) - 1,
            )
        entry_point = room_def.entry_point
        back_entry_point = room_def.back_entry_point
        required = room_def.required

        # Resolve count
        if required:
            count = room_def.count
        else:
            cr = room_def.count_range
            count = rng.randint(cr[0], cr[1])

        shape = _resolve_shape(room_def, rng)
        shape_params = _resolve_shape_params(room_def, shape, rng)
        if shape is ShapeType.T_SHAPE and "stem_wall" in shape_params:
            # Normalize once per definition, before repeated footprint queries.
            shape_params["stem_wall"] = resolve_stem_wall(
                shape_params.get("stem_wall"),
                context=f"Structure '{template.system_name}' room '{room_id}'",
            )
        width, depth, room_z = _resolve_size(room_def, shape, level_z_height, rng, template_z_height)

        room_tier = room_def.economic_tier
        template_tier = None
        wall_mat, floor_mat = resolve_room_materials(
            world, room_tier, template_tier, rng, room_id=room_id,
            building_tier=building_tier, template=template,
            building_band=building_band,
        )

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
                display_name=room_def.display_name + suffix,
                room_type=room_def.room_type,
                is_public=room_def.is_public,
                is_forbidden=room_def.is_forbidden,
                required=required,
                wall_material=wall_mat,
                floor_material=floor_mat,
                economic_tier=room_def.economic_tier,
                attach_to=room_def.attach_to,
                attach_wall=room_def.attach_wall,
                perimeter_required=bool(room_def.perimeter_required
                                        or entry_point is not None or back_entry_point is not None),
                underground_fallback=room_def.underground_fallback,
                entry_point=entry_point,
                back_entry_point=back_entry_point,
                shape_params=shape_params,
                staircase_type=room_def.staircase_type,
                facing=room_def.facing,
                wall_openings=list(room_def.wall_openings),
            ))
            logger.info("factory | %r staircase_type=%r", room_id, room_def.staircase_type)

    return instances
