"""
Passage builder — creates LocationPassage objects and places door/staircase cells.

Mutates `cells: dict[(x,y,z) → MapCell]` in-place (replaces wall → door/staircase).
Returns list[LocationPassage].

Three sources of passages:
  1. Doorway / archway connections   → door cells on shared wall + passage
  2. entry_point / back_entry_point  → door cells on exterior wall + passage (from_level=None)
  3. Staircase connections           → staircase cell(s) in each room + cross-level passage
"""
import logging
import math
import uuid
from random import Random

from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))

class _EmptyWorld:
    item_value_tier_registry = []

_EMPTY_WORLD = _EmptyWorld()
_WALL_DIRS  = {"south": (0, -1), "north": (0, 1), "east": (1, 0), "west": (-1, 0)}


def _det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, "|".join(parts)))


def _door_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
               material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="door",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _stair_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
                material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="staircase",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


# ---------------------------------------------------------------------------
# Shared segment helpers

def _shared_segment(r1: _RoomInstance, r2: _RoomInstance) -> list[tuple[int, int]]:
    """Sorted list of cells in both footprints (the shared perimeter)."""
    shared = r1.get_footprint() & r2.get_footprint()
    return sorted(shared)


def _center_slice(cells: list[tuple[int, int]], width: int) -> list[tuple[int, int]]:
    """Return `width` cells centred in the sorted segment."""
    n = len(cells)
    if width >= n:
        return cells
    mid = n // 2
    half = width // 2
    start = mid - half
    return cells[start: start + width]


# ---------------------------------------------------------------------------
# Exterior wall direction helpers

def _exterior_cells_on_wall(
    room: _RoomInstance,
    direction: str,
    all_union: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """
    Cells just outside the room footprint in `direction` that are not in any room.
    These are the exterior wall cells on that side.
    """
    dx, dy = _WALL_DIRS[direction]
    fp = room.get_footprint()
    result: set[tuple[int, int]] = set()
    for (x, y) in fp:
        nb = (x + dx, y + dy)
        if nb not in all_union:
            result.add(nb)
    return sorted(result)


def _room_by_id(rooms: list[_RoomInstance], room_id: str) -> _RoomInstance | None:
    for r in rooms:
        if r.room_id == room_id:
            return r
    return None


# ---------------------------------------------------------------------------
# 1. Doorway passages

def _build_doorway(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
) -> LocationPassage | None:
    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("doorway %r→%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    width = conn.get("width", 1)
    if width > len(shared):
        logger.warning("doorway %r→%r: width %d > shared %d — clamped",
                       conn["from_room"], conn["to_room"], width, len(shared))
        width = len(shared)

    door_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.wall_material
    z = fr_level.z

    for (x, y) in door_cells:
        cells[(x, y, z)] = _door_cell(x, y, z, world_uid, building_uid, mat)

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, "door", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=cx,
        from_y=cy,
        to_level_uid=to_level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=conn.get("passage_type", "doorway"),
        is_bidirectional=True,
    )


# ---------------------------------------------------------------------------
# 2. Entry point passages

def _build_entry_point(
    room: _RoomInstance,
    ep: dict,
    level: LocationLevel,
    all_union: set[tuple[int, int]],
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    suffix: str = "",
) -> LocationPassage | None:
    direction = ep.get("wall", "south")
    ext_cells = _exterior_cells_on_wall(room, direction, all_union)
    if not ext_cells:
        logger.warning("entry_point on room %r: no exterior wall on %r side",
                       room.room_id, direction)
        return None

    width = ep.get("width", 1)
    door_cells = _center_slice(ext_cells, width)
    mat = ep.get("frame_material") or room.wall_material
    z = level.z

    for (x, y) in door_cells:
        cells[(x, y, z)] = _door_cell(x, y, z, world_uid, building_uid, mat)

    cx, cy = door_cells[len(door_cells) // 2]
    passage_uid = _det_uuid(building_uid, f"entry{suffix}", room.room_id)
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=None,
        from_x=None,
        from_y=None,
        to_level_uid=level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type=ep.get("passage_type", "main_entrance"),
        is_bidirectional=False,
    )


# ---------------------------------------------------------------------------
# 3. Staircase passages

def _resolve_staircase_type(
    conn: dict,
    fr_room: _RoomInstance,
    to_room: _RoomInstance,
    template: dict,
    world: World,
    z_height: int,
) -> str:
    """
    Auto-resolve staircase_type.

    Priority:
      1. Явный staircase_type в connection — использовать как есть.
      2. Переход поверхность ↔ подземный уровень → trapdoor (1×1 люк в полу).
         Семантика: скрытый вход в подвал/погреб, занимает 1 ячейку.
      3. Стандартный авто-резолв по z_height + economic_tier (ТЗ 3.9):
         - нижняя треть тиров AND z_height <= 3  → ladder
         - z_height <= 5                          → standard
         - иначе                                  → straight

    trapdoor:
      - footprint 1×1 (не занимает комнату)
      - system_building_element = "staircase" (пока), в будущем "trapdoor"
      - TODO: отдельный building_element "trapdoor" вместо "staircase"
      - TODO: cell_state "closed" → walkable=True (ходить по закрытому люку можно),
              cell_state "open"   → walkable=True + даёт доступ к уровню ниже.
              Отличие от door: door closed = непроходимо; trapdoor closed = проходимо.
      - TODO: NamedLocation subtype="cellar_hatch" с is_transit=True
      - TODO: материал — wood/iron по economic_tier (не floor_material)

    ladder:
      - TODO: movable определяется не типом лестницы, а материалом и контекстом:
              • деревянная лестница у стены         → movable item (StructureInteriorAssembler)
              • железная лестница в бетоне           → structural, fixed (строительный элемент)
              • верёвочная лестница                  → movable item
              • магическая/призванная лестница       → особая механика (spell item)
              Источник: material_registry[material].movable (bool) или ladder_fixed: bool на connection.
      - TODO: для fixed ladder — строительный генератор размещает ячейки staircase по всем z
              (аналогично standard), is_structural определяется material.structural_strength.
      - TODO: для movable ladder — генератор создаёт только shaft (дыра в перекрытии),
              сама лестница = item размещённый StructureInteriorAssembler.
              Если убрать: MovementNode проверяет альтернативы (Athletics, другой movable object).
    """
    explicit = conn.get("staircase_type")
    if explicit:
        return explicit

    # Переход поверхность ↔ подземный
    going_underground = (fr_room.z_offset >= 0 and to_room.z_offset < 0)
    coming_up         = (fr_room.z_offset < 0  and to_room.z_offset >= 0)
    if going_underground or coming_up:
        return "trapdoor"

    tiers = sorted(
        world.item_value_tier_registry or [],
        key=lambda t: t.get("base_value", 0),
    )
    effective_tier = to_room.economic_tier or template.get("economic_tier")

    tier_count = len(tiers)
    tier_rank: int | None = None
    if tiers and effective_tier:
        for i, t in enumerate(tiers):
            if t.get("system_tier") == effective_tier:
                tier_rank = i
                break

    if (tier_rank is not None
            and z_height <= 3
            and tier_rank < math.ceil(tier_count / 3)):
        return "ladder"

    if z_height <= 5:
        return "standard"
    return "straight"


_FALLBACK_CHAIN = ["straight", "standard", "spiral_standard", "spiral_small", "ladder"]


def _stair_fits(stair_type: str, room: _RoomInstance, z_height: int) -> bool:
    """True если footprint лестницы вписывается во внутренние размеры комнаты."""
    iw = max(0, room.width  - 2)   # interior width
    id_ = max(0, room.depth - 2)   # interior depth

    if stair_type in ("ladder", "trapdoor"):
        return True
    if stair_type in ("standard", "spiral_standard"):
        return iw >= 2 and id_ >= 2
    if stair_type == "spiral_small":
        return iw >= 1 and id_ >= 2
    if stair_type == "straight":
        length = max(2, math.ceil(z_height * 1.3))
        return iw >= length or id_ >= length
    return True


def _apply_fit_fallback(
    initial_type: str,
    room: _RoomInstance,
    z_height: int,
    conn_label: str,
) -> str:
    """
    Если initial_type не вписывается — применяет fallback chain.
    ladder/trapdoor всегда fit.
    """
    if _stair_fits(initial_type, room, z_height):
        return initial_type

    start = (_FALLBACK_CHAIN.index(initial_type) + 1
             if initial_type in _FALLBACK_CHAIN else 0)

    for candidate in _FALLBACK_CHAIN[start:]:
        if _stair_fits(candidate, room, z_height):
            logger.warning(
                "staircase %s: %r не вписывается в room=%r (%dx%d interior) — заменена на %r",
                conn_label, initial_type, room.room_id,
                max(0, room.width - 2), max(0, room.depth - 2), candidate,
            )
            return candidate

    return "ladder"  # ladder 1×1 — всегда fit


def _stair_footprint(
    staircase_type: str,
    anchor: tuple[int, int],
    z_height: int,
    rng: Random,
) -> list[tuple[int, int]]:
    """
    Return list of (x, y) cells for the staircase block at ONE z-level.
    anchor = top-left corner of the block.

    TODO: лестницы должны физически существовать на каждом z между fr_level.z и to_level.z.
          Сейчас: по 1 ячейке на каждом из двух этажей.
          Должно быть: ячейки staircase на всех промежуточных z (z=0, 1, 2, 3 для z_height=3).
          Это даёт: боёвку на ступенях, многоуровневые лестницы, физику падения.
          _build_staircase должен итерировать range(min_z, max_z+1) и для каждого z
          размещать footprint этого z-слоя (для straight — footprint сдвигается вдоль оси).
    """
    ax, ay = anchor
    if staircase_type in ("ladder", "trapdoor"):
        return [(ax, ay)]
    if staircase_type in ("standard", "spiral_standard", "spiral_small"):
        # 2×2 block
        return [(ax, ay), (ax + 1, ay), (ax, ay + 1), (ax + 1, ay + 1)]
    if staircase_type == "straight":
        length = max(2, math.ceil(z_height * 1.3))
        return [(ax, ay + i) for i in range(length)]
    # Unknown → ladder fallback
    logger.warning("staircase: unknown type %r, using ladder", staircase_type)
    return [(ax, ay)]


def _has_free_exit(
    anchor: tuple[int, int],
    stair_fp: list[tuple[int, int]],
    room_fp: set[tuple[int, int]],
) -> bool:
    """
    True если хотя бы одна из ячеек лестницы имеет соседа внутри footprint комнаты,
    который НЕ является частью самой лестницы.
    Гарантирует что вход/выход лестницы не упирается в стену.
    """
    stair_set = set(stair_fp)
    for (x, y) in stair_set:
        for dx, dy in _NEIGHBOURS:
            nb = (x + dx, y + dy)
            if nb in room_fp and nb not in stair_set:
                return True
    return False


def _stair_anchor(
    room: _RoomInstance,
    staircase_type: str,
    position: str | None,
    rng: Random,
    z_height: int = 3,
) -> tuple[int, int]:
    """
    Find anchor (top-left corner of staircase block) inside room footprint.
    Ensures staircase has at least one free adjacent cell (exit not blocked by wall).
    """
    from app.application.worldData.generators.structure._cellBuilder import _interior

    fp = room.get_footprint()
    interior = list(_interior(fp)) or list(fp)

    pos = position or ("center" if room.room_type in ("common_hall", "hall") else "edge")

    block_w, block_h = (1, 1)
    if staircase_type in ("standard", "spiral_standard"):
        block_w, block_h = 2, 2
    elif staircase_type == "spiral_small":
        block_w, block_h = 1, 2

    xs = sorted({x for (x, _) in interior})
    ys = sorted({y for (_, y) in interior})

    if pos == "center":
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        return cx, cy

    if pos in ("east", "northeast", "southeast"):
        ax = max(xs) - block_w + 1
        ay = (min(ys) + max(ys)) // 2
    elif pos in ("west", "northwest", "southwest"):
        ax = min(xs)
        ay = (min(ys) + max(ys)) // 2
    elif pos == "north":
        ax = (min(xs) + max(xs)) // 2
        ay = max(ys) - block_h + 1
    elif pos == "south":
        ax = (min(xs) + max(xs)) // 2
        ay = min(ys)
    else:  # "edge"
        if rng.choice([True, False]):
            ax = max(xs) - block_w + 1
        else:
            ax = min(xs)
        ay = (min(ys) + max(ys)) // 2

    # Проверяем что вход/выход лестницы не упирается в стену.
    # Если якорь в тупике — сдвигаем к центру пока не найдём свободный выход.
    stair_fp = _stair_footprint(staircase_type, (ax, ay), z_height, rng)
    if not _has_free_exit((ax, ay), stair_fp, fp):
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        for candidate in [(cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]:
            fp_c = _stair_footprint(staircase_type, candidate, z_height, rng)
            if _has_free_exit(candidate, fp_c, fp):
                logger.warning(
                    "staircase anchor shifted for room=%r: (%d,%d) had no exit → (%d,%d)",
                    room.room_id, ax, ay, candidate[0], candidate[1],
                )
                return candidate

    return ax, ay


def _build_staircase(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    world: World,
    template: dict,
    rng: Random,
) -> LocationPassage | None:
    z_height   = abs(to_level.z - fr_level.z)
    conn_label = f"{conn['from_room']}→{conn['to_room']}"
    stair_type = _resolve_staircase_type(conn, fr, to, template, world, z_height)
    stair_type = _apply_fit_fallback(stair_type, to, z_height, conn_label)
    mat        = conn.get("step_material") or fr.floor_material

    logger.info("staircase %s: type=%s z_height=%d", conn_label, stair_type, z_height)

    pos_hint  = conn.get("position")
    to_anchor = _stair_anchor(to, stair_type, pos_hint, rng, z_height)
    fr_anchor = _stair_anchor(fr, stair_type, None,     rng, z_height)
    # TODO: staircase anchor overlap — смещать fr_anchor если позиция уже занята
    #       другой лестницей этой же комнаты (см. описание выше в файле).

    z_lo = min(fr_level.z, to_level.z)
    z_hi = max(fr_level.z, to_level.z)

    if stair_type == "trapdoor":
        # Люк: каждый конец размещается в своей комнате независимо.
        # fr_anchor → fr_level.z, to_anchor → to_level.z.
        for (x, y) in _stair_footprint(stair_type, fr_anchor, z_height, rng):
            cells[(x, y, fr_level.z)] = _stair_cell(x, y, fr_level.z, world_uid, building_uid, mat)
        for (x, y) in _stair_footprint(stair_type, to_anchor, z_height, rng):
            cells[(x, y, to_level.z)] = _stair_cell(x, y, to_level.z, world_uid, building_uid, mat)
    else:
        # Физическая лестница: единый x,y footprint по всем z от z_lo до z_hi.
        # Используем to_anchor — позиция в комнате назначения, которая также входит
        # в footprint исходной комнаты (обе комнаты вертикально стекированы).
        fp = _stair_footprint(stair_type, to_anchor, z_height, rng)
        for z in range(z_lo, z_hi + 1):
            for (x, y) in fp:
                cells[(x, y, z)] = _stair_cell(x, y, z, world_uid, building_uid, mat)

    tx, ty = to_anchor
    fx, fy = fr_anchor
    passage_uid = _det_uuid(building_uid, "stair", conn["from_room"], conn["to_room"])
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=fx,
        from_y=fy,
        to_level_uid=to_level.level_uid,
        to_x=tx,
        to_y=ty,
        system_passage_type="staircase",
        is_bidirectional=True,
    )


# ---------------------------------------------------------------------------
# Public entry point

def build_passages(
    cells: dict[tuple, MapCell],
    rooms: list[_RoomInstance],
    connections: list[dict],
    levels: dict[int, LocationLevel],       # z_offset → LocationLevel
    room_z_offsets: dict[str, int],         # room_id → z_offset
    world_uid: str,
    building_uid: str,
    rng: Random,
    world: World | None = None,
    template: dict | None = None,
) -> list[LocationPassage]:
    passages: list[LocationPassage] = []

    # room_id → list of all placed instances (multiple when count > 1)
    placed_by_id: dict[str, list[_RoomInstance]] = {}
    for r in rooms:
        if r.placed:
            placed_by_id.setdefault(r.room_id, []).append(r)

    all_union: set[tuple[int, int]] = set()
    for r in rooms:
        if r.placed:
            all_union |= r.get_footprint()

    # --- doorway / staircase connections ---
    for conn in connections:
        fr_list = placed_by_id.get(conn["from_room"], [])
        to_list = placed_by_id.get(conn["to_room"], [])
        if not fr_list or not to_list:
            continue

        fr_offset = room_z_offsets[conn["from_room"]]
        to_offset = room_z_offsets[conn["to_room"]]
        fr_level  = levels[fr_offset]
        to_level  = levels[to_offset]
        ptype     = conn.get("passage_type", "doorway")

        if ptype == "staircase":
            # Staircase addresses instance_0 of each side per ТЗ
            p = _build_staircase(conn, fr_list[0], to_list[0], fr_level, to_level,
                                 cells, world_uid, building_uid,
                                 world or _EMPTY_WORLD, template or {}, rng)
            if p:
                passages.append(p)
        else:
            # Doorway: create a passage for every (fr, to) pair that shares a wall.
            # Typically fr has 1 instance (corridor), to has N instances (guest rooms).
            for fr in fr_list:
                fr_fp = fr.get_footprint()
                for to in to_list:
                    if fr_fp & to.get_footprint():   # physically adjacent
                        p = _build_doorway(conn, fr, to, fr_level, to_level,
                                           cells, world_uid, building_uid)
                        if p:
                            passages.append(p)

    # --- entry points ---
    for room in rooms:
        if not room.placed:
            continue
        z_offset = room_z_offsets[room.room_id]
        level = levels[z_offset]

        if room.entry_point:
            p = _build_entry_point(room, room.entry_point, level,
                                   all_union, cells, world_uid, building_uid)
            if p:
                passages.append(p)

        if room.back_entry_point:
            p = _build_entry_point(room, room.back_entry_point, level,
                                   all_union, cells, world_uid, building_uid, suffix="_back")
            if p:
                passages.append(p)

    return passages
