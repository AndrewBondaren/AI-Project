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

from app.application.worldData.generators._economicTierBands import BAND_COMMON, BAND_POOR, band_of
from app.application.worldData.generators.structure._cellBuilder import _interior
from app.application.worldData.generators.structure._roomInstance import _RoomInstance
from app.db.models.locationLevel import LocationLevel
from app.db.models.locationPassage import LocationPassage
from app.db.models.mapCell import MapCell
from app.db.models.world import World

logger = logging.getLogger(__name__)

_NEIGHBOURS = ((1, 0), (-1, 0), (0, 1), (0, -1))

class _EmptyWorld:
    economic_tier_registry = []

_EMPTY_WORLD = _EmptyWorld()
_WALL_DIRS  = {"south": (0, -1), "north": (0, 1), "east": (1, 0), "west": (-1, 0)}

# Direction a straight staircase march runs, given its position (the wall it is anchored to).
# March runs away from the named wall into the room interior.
_STRAIGHT_MARCH: dict[str, tuple[int, int]] = {
    "north":     (0, -1),   # anchored at north wall → runs south
    "south":     (0,  1),   # anchored at south wall → runs north
    "east":      (-1, 0),   # anchored at east wall  → runs west
    "west":      (1,  0),   # anchored at west wall  → runs east
    "northeast": (-1, 0),
    "southeast": (-1, 0),
    "northwest": (1,  0),
    "southwest": (1,  0),
    "center":    (0,  1),   # default: runs north
    "edge":      (0,  1),
}


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


def _trapdoor_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
                   material: str) -> MapCell:
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="trapdoor",
        system_material=material,
        is_structural=False,
        location_uid=building_uid,
    )


def _stair_base_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
                     material: str) -> MapCell:
    """Структурная опора прямой лестницы — не проходима, не является путём."""
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="staircase_base",
        system_material=material,
        is_structural=True,
        location_uid=building_uid,
    )


def _void_cell(x: int, y: int, z: int, world_uid: str, building_uid: str) -> MapCell:
    """Пустота внутри шахты лестницы — открытый воздух, не пол, не проходимо."""
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="void",
        system_material=None,
        is_structural=False,
        location_uid=building_uid,
    )


def _open_cell(x: int, y: int, z: int, world_uid: str, building_uid: str,
               material: str) -> MapCell:
    """Open archway cell — floor element, replaces the interior wall."""
    return MapCell(
        world_uid=world_uid, x=x, y=y, z=z,
        system_building_element="floor",
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
    Perimeter cells of the room in `direction` whose neighbour in that direction
    is outside the union. These are the actual wall cells that face the exterior —
    pass3 places walls here; entry_point replaces one with a door.
    """
    dx, dy = _WALL_DIRS[direction]
    fp = room.get_footprint()
    result: set[tuple[int, int]] = set()
    for (x, y) in fp:
        nb = (x + dx, y + dy)
        if nb not in all_union:
            result.add((x, y))
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
        logger.warning("doorway %r->%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    width = conn.get("width", 1)
    if width > len(shared):
        logger.warning("doorway %r->%r: width %d > shared %d -- clamped",
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
# 1b. Archway passages (open, no door)

def _build_archway(
    conn: dict,
    fr: _RoomInstance,
    to: _RoomInstance,
    fr_level: LocationLevel,
    to_level: LocationLevel,
    cells: dict[tuple, MapCell],
    world_uid: str,
    building_uid: str,
    other_rooms: list | None = None,
) -> LocationPassage | None:
    """
    Open passage between two adjacent rooms — replaces shared wall with floor.
    No door cell, no visual obstruction.
    Width defaults to 2 (wider than doorway).
    Applied to all z layers in the level's z_height.
    Cells that are also in a third room's footprint are excluded to avoid
    accidentally opening that room's wall (e.g. guest room at corridor corner).
    """
    shared = _shared_segment(fr, to)
    if not shared:
        logger.warning("archway %r->%r: no shared wall found", conn["from_room"], conn["to_room"])
        return None

    if other_rooms:
        third_fp: set[tuple[int, int]] = set()
        for r in other_rooms:
            if r is not fr and r is not to and r.placed:
                third_fp |= r.get_footprint()
        shared = [(x, y) for (x, y) in shared if (x, y) not in third_fp]
        if not shared:
            logger.warning("archway %r->%r: all shared cells blocked by third rooms", conn["from_room"], conn["to_room"])
            return None

    width = conn.get("width", 2)
    if width > len(shared):
        width = len(shared)

    arch_cells = _center_slice(shared, width)
    mat = conn.get("frame_material") or fr.floor_material
    z_base = fr_level.z

    for (x, y) in arch_cells:
        for z_layer in range(z_base, z_base + fr_level.z_height):
            cells[(x, y, z_layer)] = _open_cell(x, y, z_layer, world_uid, building_uid, mat)

    cx, cy = arch_cells[len(arch_cells) // 2]
    passage_uid = _det_uuid(building_uid, "arch", conn["from_room"], conn["to_room"])
    logger.info(
        "archway %r->%r: shared=%d cells, width=%d, open at %s, z=%d..%d",
        conn["from_room"], conn["to_room"],
        len(shared), len(arch_cells),
        [(x, y) for (x, y) in arch_cells],
        z_base, z_base + fr_level.z_height - 1,
    )
    return LocationPassage(
        passage_uid=passage_uid,
        world_uid=world_uid,
        from_level_uid=fr_level.level_uid,
        from_x=cx,
        from_y=cy,
        to_level_uid=to_level.level_uid,
        to_x=cx,
        to_y=cy,
        system_passage_type="archway",
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
    building_tier: str | None = None,
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

    effective_tier = to_room.economic_tier or template.get("economic_tier") or building_tier

    if z_height <= 3 and effective_tier:
        b = band_of(world, effective_tier)
        if b in (BAND_POOR, BAND_COMMON):
            return "ladder"

    if z_height <= 5:
        return "standard"
    return "straight"


_FALLBACK_CHAIN = ["straight", "standard", "spiral_standard", "spiral_small", "ladder"]


def _stair_fits(stair_type: str, room: _RoomInstance, z_height: int, include_extra: bool = True) -> bool:
    """True если footprint лестницы вписывается во внутренние размеры комнаты.
    include_extra=True (default): учитывает extra_cells через реальный footprint.
    include_extra=False: проверяет базовый размер (до stairwell mutation)."""
    if stair_type in ("ladder", "trapdoor"):
        return True

    if include_extra and room.extra_cells:
        # Use actual footprint interior — extra_cells may have widened the room
        interior = _interior(room.get_footprint())
        if not interior:
            return False
        xs = {x for (x, _) in interior}
        ys = {y for (_, y) in interior}
        iw  = max(xs) - min(xs) + 1
        id_ = max(ys) - min(ys) + 1
    else:
        iw  = max(0, room.width  - 2)
        id_ = max(0, room.depth  - 2)

    if stair_type in ("standard", "spiral_standard"):
        return iw >= 2 and id_ >= 2
    if stair_type == "spiral_small":
        return iw >= 1 and id_ >= 2
    if stair_type == "straight":
        length = max(2, math.ceil(z_height * 1.3))
        return (iw >= 2 and id_ >= length) or (iw >= length and id_ >= 2)
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
    orientation: tuple[int, int] = (0, 1),
) -> list[tuple[int, int]]:
    """
    Return list of (x, y) cells for the staircase block at ONE z-level.
    anchor = corner of the block nearest the wall the staircase is anchored to.

    orientation: (dx, dy) march direction for straight staircases — see _STRAIGHT_MARCH.
    Ignored for column types (standard/spiral/ladder) and trapdoor.
    """
    ax, ay = anchor
    if staircase_type in ("ladder", "trapdoor"):
        return [(ax, ay)]
    if staircase_type in ("standard", "spiral_standard"):
        return [(ax, ay), (ax + 1, ay), (ax, ay + 1), (ax + 1, ay + 1)]
    if staircase_type == "spiral_small":
        return [(ax, ay), (ax, ay + 1)]
    if staircase_type == "straight":
        length = max(2, math.ceil(z_height * 1.3))
        dx, dy = orientation
        # Перпендикуляр к маршу: base-ячейка рядом с path на каждом шаге.
        px, py = abs(dy), abs(dx)
        cells = []
        for i in range(length):
            cells.append((ax + dx * i, ay + dy * i))             # path
            cells.append((ax + dx * i + px, ay + dy * i + py))   # base
        return cells
    logger.warning("staircase: unknown type %r, using ladder", staircase_type)
    return [(ax, ay)]


def _spiral_perimeter(ax: int, ay: int, W: int, H: int) -> list[tuple[int, int]]:
    """
    Обход периметра прямоугольника W×H от якоря (ax,ay)=SW-угол по ЧС (N→E→S→W).
    Длина = 2*(W+H)-4. Якорь — первый элемент.

    Пример 2×2: SW→NW→NE→SE (4 ячейки).
    Пример 2×3: SW→(0,1)→NW→NE→SE→(1,0) (6 ячеек).
    """
    pts: list[tuple[int, int]] = []
    for dy in range(H):                          # запад: вверх по y
        pts.append((ax, ay + dy))
    for dx in range(1, W):                       # север: вправо по x
        pts.append((ax + dx, ay + H - 1))
    for dy in range(H - 2, -1, -1):             # восток: вниз по y
        pts.append((ax + W - 1, ay + dy))
    for dx in range(W - 2, 0, -1):             # юг: влево по x (не повторяем SW)
        pts.append((ax + dx, ay))
    return pts


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
    orientation: tuple[int, int] | None = None,
) -> tuple[int, int]:
    """
    Find anchor (top-left corner of staircase block) inside room footprint.
    Ensures staircase has at least one free adjacent cell (exit not blocked by wall).
    """
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
    eff_orientation = orientation or (0, 1)
    stair_fp = _stair_footprint(staircase_type, (ax, ay), z_height, rng, eff_orientation)
    if not _has_free_exit((ax, ay), stair_fp, fp):
        cx = (min(xs) + max(xs)) // 2
        cy = (min(ys) + max(ys)) // 2
        for candidate in [(cx, cy), (cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)]:
            fp_c = _stair_footprint(staircase_type, candidate, z_height, rng, eff_orientation)
            if _has_free_exit(candidate, fp_c, fp):
                logger.warning(
                    "staircase anchor shifted for room=%r: (%d,%d) had no exit -> (%d,%d)",
                    room.room_id, ax, ay, candidate[0], candidate[1],
                )
                return candidate

    return ax, ay


def _existing_stair_anchor(
    room: _RoomInstance,
    z: int,
    cells: dict,
) -> tuple[int, int] | None:
    """
    Return the min-corner of an existing staircase block in room at z, or None.
    Used to detect shaft continuations — reuse existing XY instead of recomputing.
    """
    fp = room.get_footprint()
    stair_xy = {
        (x, y) for (x, y) in fp
        if cells.get((x, y, z)) and cells[(x, y, z)].system_building_element == "staircase"
    }
    return min(stair_xy) if stair_xy else None


def _free_stair_anchor(
    anchor: tuple[int, int],
    stair_type: str,
    z: int,
    z_height: int,
    room: _RoomInstance,
    cells: dict,
    rng: Random,
    conn_label: str,
    role: str,
) -> tuple[int, int]:
    """Shift anchor if its footprint overlaps non-staircase cells at z.
    Staircase cells from a connected shaft are treated as compatible — not a conflict."""
    interior = set(_interior(room.get_footprint())) or room.get_footprint()

    def fits_free(a: tuple[int, int]) -> bool:
        fp = set(_stair_footprint(stair_type, a, z_height, rng))
        if not fp <= interior:
            return False
        return not any(
            cells.get((x, y, z)) and cells[(x, y, z)].system_building_element not in ("floor", "staircase", "staircase_base", "trapdoor")
            for (x, y) in fp
        )

    if fits_free(anchor):
        return anchor

    for ax, ay in sorted(interior, key=lambda p: abs(p[0] - anchor[0]) + abs(p[1] - anchor[1])):
        if fits_free((ax, ay)):
            logger.warning(
                "staircase %s: %s anchor shifted (%d,%d)->(%d,%d) — overlap with non-staircase cell",
                conn_label, role, anchor[0], anchor[1], ax, ay,
            )
            return ax, ay

    logger.warning(
        "staircase %s: %s anchor (%d,%d) has no free slot — keeping original",
        conn_label, role, anchor[0], anchor[1],
    )
    return anchor


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
    building_tier: str | None = None,
) -> LocationPassage | None:
    z_height   = abs(to_level.z - fr_level.z)
    conn_label = f"{conn['from_room']}->{conn['to_room']}"
    desired    = _resolve_staircase_type(conn, fr, to, template, world, z_height, building_tier)
    stair_type = _apply_fit_fallback(desired, to, z_height, conn_label)
    mat        = conn.get("step_material") or fr.floor_material

    logger.info(
        "staircase %s: desired=%s final=%s z_height=%d fr_z=%d to_z=%d",
        conn_label, desired, stair_type, z_height, fr_level.z, to_level.z,
    )

    pos_hint = conn.get("position")

    # Shaft continuation: if fr_room already has staircase cells at fr_level.z,
    # this connection extends the same physical shaft — reuse existing XY anchor.
    # Skip anchor search, free-exit check, and _free_stair_anchor (shaft cells are compatible).
    shaft_anchor = _existing_stair_anchor(fr, fr_level.z, cells) if stair_type != "trapdoor" else None

    pos_key = (pos_hint or "center").split()[0]
    march = _STRAIGHT_MARCH.get(pos_key, (0, 1)) if stair_type == "straight" else (0, 1)

    if shaft_anchor is not None:
        to_anchor = shaft_anchor
        logger.info(
            "staircase %s: shaft continuation — reusing anchor (%d,%d) from fr_room=%r at z=%d",
            conn_label, shaft_anchor[0], shaft_anchor[1], fr.room_id, fr_level.z,
        )
    else:
        to_anchor = _stair_anchor(to, stair_type, pos_hint, rng, z_height, orientation=march)
        to_anchor = _free_stair_anchor(to_anchor, stair_type, to_level.z, z_height, to, cells, rng, conn_label, "to")

    if stair_type != "trapdoor":
        fr_anchor = to_anchor
    else:
        fr_anchor = _stair_anchor(fr, stair_type, None, rng, z_height)
        fr_anchor = _free_stair_anchor(fr_anchor, stair_type, fr_level.z, z_height, fr, cells, rng, conn_label, "fr")

    logger.info(
        "staircase %s: to_anchor=%s (room=%r) fr_anchor=%s (room=%r)",
        conn_label, to_anchor, to.room_id, fr_anchor, fr.room_id,
    )

    z_lo = min(fr_level.z, to_level.z)

    if stair_type == "trapdoor":
        # Люк: одна ячейка в полу fr_room; шахта через все z-слои to_room.
        for (x, y) in _stair_footprint(stair_type, fr_anchor, z_height, rng):
            cells[(x, y, fr_level.z)] = _trapdoor_cell(x, y, fr_level.z, world_uid, building_uid, mat)
        for (x, y) in _stair_footprint(stair_type, to_anchor, z_height, rng):
            for z_layer in range(to_level.z, to_level.z + to_level.z_height):
                cells[(x, y, z_layer)] = _trapdoor_cell(x, y, z_layer, world_uid, building_uid, mat)

    elif stair_type == "straight":
        # Диагональная раскладка: ступень i → path (ax+dx*i, ay+dy*i, z_lo+i) + base рядом.
        # Ориентация определяется position: north/south → ось Y, east/west → ось X.
        dx, dy = march
        px, py = abs(dy), abs(dx)   # перпендикуляр к маршу
        length = max(2, math.ceil(z_height * 1.3))
        for i in range(length):
            x, y = to_anchor[0] + dx * i, to_anchor[1] + dy * i
            z = z_lo + i
            cells[(x, y, z)] = _stair_cell(x, y, z, world_uid, building_uid, mat)
            bx, by = x + px, y + py
            cells[(bx, by, z)] = _stair_base_cell(bx, by, z, world_uid, building_uid, mat)

    elif stair_type in ("standard", "spiral_standard"):
        # Спираль: одна ступень на каждый z-уровень, циклически по периметру.
        # Ступень k: ячейка perimeter[(k+1)%n], z_s = z_lo + k.
        # Trail (z_s+1) кладётся только если z_s+1 < z_top.
        ax, ay = to_anchor
        z_top  = max(fr_level.z, to_level.z)
        W, H   = 2, 2   # размер footprint; при расширении типов менять здесь
        perimeter = _spiral_perimeter(ax, ay, W, H)
        n = len(perimeter)   # = 2*(W+H)-4

        # Ступени и trail — всегда перезаписывают (staircase вытесняет floor)
        for k in range(z_height):
            sx, sy = perimeter[(k + 1) % n]
            z_s = z_lo + k
            cells[(sx, sy, z_s)] = _stair_cell(sx, sy, z_s, world_uid, building_uid, mat)
            if z_s + 1 < z_top:
                cells[(sx, sy, z_s + 1)] = _stair_cell(sx, sy, z_s + 1, world_uid, building_uid, mat)

        # Вход — C0 = perimeter[0] = (ax, ay); выход — perimeter[z_height % n]
        ex, ey = perimeter[z_height % n]
        cells[(ax, ay, z_lo)] = _stair_cell(ax, ay, z_lo, world_uid, building_uid, mat)
        cells[(ex, ey, z_top)] = _stair_cell(ex, ey, z_top, world_uid, building_uid, mat)

        # Весь footprint: позиции без staircase → void на промежуточных z,
        # на z_lo → plain floor (нет шахты снизу, поручни не нужны),
        # на z_top → floor с поручнями на сторонах, смежных с другими footprint-ячейками
        # (эти ячейки закрывают шахту сверху и ограждают стояк).
        footprint_xy = [(ax + dx, ay + dy) for dx in range(W) for dy in range(H)]
        footprint_set = set(footprint_xy)

        def _railing_sides_for(cx: int, cy: int) -> str | None:
            """Стороны, смотрящие на staircase-ячейку в footprint (проём шахты)."""
            sides = [
                face for dx, dy, face in ((1,0,"E"),(-1,0,"W"),(0,1,"N"),(0,-1,"S"))
                if (cx + dx, cy + dy) in footprint_set
                and cells.get((cx + dx, cy + dy, z_top)) is not None
                and cells[(cx + dx, cy + dy, z_top)].system_building_element == "staircase"
            ]
            return ",".join(sorted(sides)) if sides else None

        _NO_OVERWRITE = {"staircase", "wall", "door", "trapdoor", "window", "column"}

        for z in range(z_lo, z_top + 1):
            for cx, cy in footprint_xy:
                key = (cx, cy, z)
                existing = cells.get(key)
                if existing is not None and existing.system_building_element in _NO_OVERWRITE:
                    continue
                if z == z_lo:
                    cells[key] = MapCell(
                        world_uid=world_uid, x=cx, y=cy, z=z,
                        system_building_element="floor",
                        system_material=mat,
                        is_structural=False,
                        location_uid=building_uid,
                    )
                elif z == z_top:
                    cells[key] = MapCell(
                        world_uid=world_uid, x=cx, y=cy, z=z,
                        system_building_element="floor",
                        system_material=mat,
                        is_structural=False,
                        location_uid=building_uid,
                        railing_sides=_railing_sides_for(cx, cy),
                    )
                else:
                    cells[key] = _void_cell(cx, cy, z, world_uid, building_uid)

    else:
        # Прочие типы (spiral_small и т.д.) — колонна: якорь на всех z, остальное — void.
        fp = _stair_footprint(stair_type, to_anchor, z_height, rng)
        z_top = max(fr_level.z, to_level.z)
        ax, ay = to_anchor
        for z in range(z_lo, z_top + 1):
            for (x, y) in fp:
                if (x, y) == (ax, ay):
                    cells[(x, y, z)] = _stair_cell(x, y, z, world_uid, building_uid, mat)
                else:
                    cells[(x, y, z)] = _void_cell(x, y, z, world_uid, building_uid)

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
    building_tier: str | None = None,
) -> list[LocationPassage]:
    logger.info("=== PHASE: build_passages ===")
    passages: list[LocationPassage] = []

    # room_id → list of all placed instances (multiple when count > 1)
    placed_by_id: dict[str, list[_RoomInstance]] = {}
    for r in rooms:
        if r.placed:
            placed_by_id.setdefault(r.room_id, []).append(r)

    # Global union (for doorway/archway shared-wall detection — same level only matters there too)
    all_union: set[tuple[int, int]] = set()
    for r in rooms:
        if r.placed:
            all_union |= r.get_footprint()

    # Per-level union — used for exterior wall detection (entry_point / back_entry_point).
    # Must exclude rooms from other z_offsets so that a basement under the kitchen doesn't
    # block the kitchen's north exterior wall detection.
    level_unions: dict[int, set[tuple[int, int]]] = {}
    for r in rooms:
        if r.placed:
            z = room_z_offsets[r.room_id]
            level_unions.setdefault(z, set())
            level_unions[z] |= r.get_footprint()

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

        logger.info(
            "passage | %s->%s type=%r z_offset=%d->%d",
            conn["from_room"], conn["to_room"], ptype, fr_offset, to_offset,
        )

        if ptype == "staircase":
            # Staircase addresses instance_0 of each side per ТЗ
            p = _build_staircase(conn, fr_list[0], to_list[0], fr_level, to_level,
                                 cells, world_uid, building_uid,
                                 world or _EMPTY_WORLD, template or {}, rng,
                                 building_tier=building_tier)
            if p:
                passages.append(p)
        elif ptype == "archway":
            # Archway: open passage, no door cell, spans full z_height
            same_level_rooms = [r for r in rooms if room_z_offsets.get(r.room_id) == fr_offset]
            for fr in fr_list:
                fr_fp = fr.get_footprint()
                for to in to_list:
                    if fr_fp & to.get_footprint():
                        p = _build_archway(conn, fr, to, fr_level, to_level,
                                           cells, world_uid, building_uid,
                                           other_rooms=same_level_rooms)
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
        same_level_union = level_unions.get(z_offset, all_union)

        if room.entry_point:
            p = _build_entry_point(room, room.entry_point, level,
                                   same_level_union, cells, world_uid, building_uid)
            if p:
                passages.append(p)

        if room.back_entry_point:
            p = _build_entry_point(room, room.back_entry_point, level,
                                   same_level_union, cells, world_uid, building_uid, suffix="_back")
            if p:
                passages.append(p)

    return passages
