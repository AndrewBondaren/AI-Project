"""
Запуск генератора здания с выводом логов.

Использование:
    python scripts/run_tavern_gen.py <template> [world] [z]
    python scripts/run_tavern_gen.py tavern_1
    python scripts/run_tavern_gen.py tavern_2 world_test
    python scripts/run_tavern_gen.py tavern_1 world_test 0
"""
import io
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

_OUT_FILE = Path(__file__).parent / "last_output.txt"


class _Tee(io.TextIOBase):
    def __init__(self, *streams):
        self._streams = streams

    def write(self, s):
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self):
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass


_file_handle = open(_OUT_FILE, "w", encoding="utf-8")
sys.stdout = _Tee(sys.__stdout__, _file_handle)
sys.stderr = _Tee(sys.__stderr__, _file_handle)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

from datetime import datetime, timezone

from app.application.worldData.generators.structure.structureGeneratorService import StructureGeneratorService
from app.db.models.namedLocation import NamedLocation
from app.db.models.world import World

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"

# --- Аргументы: template [world] [z] ---
_args         = [a for a in sys.argv[1:] if not a.lstrip("-").isdigit()]
_z_filter     = int(sys.argv[-1]) if sys.argv[-1:] and sys.argv[-1].lstrip("-").isdigit() else None

template_name = _args[0] if len(_args) > 0 else "tavern_1"
world_name    = _args[1] if len(_args) > 1 else "world_test"

# --- Мир из фикстуры ---
world_data = json.loads((FIXTURES / f"{world_name}.json").read_text(encoding="utf-8"))
w = world_data["world"]
world = World(
    world_uid=w["world_uid"],
    name=w["name"],
    created_at=w["created_at"],
)

# --- Здание ---
building = NamedLocation(
    location_uid=f"bld-{template_name}-test-001",
    world_uid=world.world_uid,
    display_name=f"Тест: {template_name}",
    system_location_type="building",
    created_at=datetime.now(timezone.utc).isoformat(),
    map_x=10,
    map_y=10,
    map_z=0,
    parent_wall_material="stone",
    parent_floor_material="wood",
)

# --- Шаблон ---
template = json.loads((FIXTURES / "templates" / f"{template_name}.json").read_text(encoding="utf-8"))

# --- Генерация ---
svc = StructureGeneratorService()
layout = svc.generate_from_template(world, building, template)

# --- Итог ---
print("\n=== РЕЗУЛЬТАТ ===")
print(f"Уровней:   {len(layout.levels)}")
print(f"Комнат:    {len(layout.rooms)}")
print(f"Ячеек:     {len(layout.cells)}")
print(f"Проходов:  {len(layout.passages)}")

print("\n--- Уровни ---")
for lvl in sorted(layout.levels, key=lambda l: l.z):
    print(f"  z={lvl.z:+d}  z_height={lvl.z_height}  '{lvl.display_name}'")

print("\n--- Комнаты ---")
for room in layout.rooms:
    print(f"  [{room.system_location_subtype}] '{room.display_name}'  origin=({room.map_x},{room.map_y})  z={room.map_z}")

print("\n--- Проходы ---")
for p in layout.passages:
    fr = p.from_level_uid or "exterior"
    print(f"  {p.system_passage_type}  {fr} -> {p.to_level_uid}  to=({p.to_x},{p.to_y})")

print("\n--- Элементы ячеек ---")
from collections import Counter
counts = Counter(c.system_building_element for c in layout.cells)
for elem, n in sorted(counts.items()):
    print(f"  {elem}: {n}")
railing_cells = [(c.x, c.y, c.z, c.railing_sides) for c in layout.cells if c.railing_sides]
print(f"  [railing cells: {len(railing_cells)}]")
for rc in sorted(railing_cells):
    print(f"    ({rc[0]},{rc[1]},z={rc[2]}) {rc[3]}")

print("\n--- Лестница: все ячейки ---")
_STAIR_TYPES = {"staircase", "stair_anchor", "stair_floor"}
_stair_cells = sorted(
    [(c.x, c.y, c.z, c.system_building_element) for c in layout.cells
     if c.system_building_element in _STAIR_TYPES],
    key=lambda c: (c[2], c[0], c[1]),
)
if _stair_cells:
    for _x, _y, _z, _t in _stair_cells:
        print(f"  ({_x},{_y},z={_z:+d}) {_t}")
else:
    print("  (нет ячеек)")

from app.application.worldData.generators.structure.gridRenderer import render_level, render_all_levels

level_uid_to_z = {lvl.level_uid: lvl.z for lvl in layout.levels}
anchor_dirs_by_z: dict[int, dict[tuple[int, int], str]] = {}

_MOVE_SYM: dict[tuple[int, int], str] = {
    (0, 1): "↑", (1, 0): "→", (0, -1): "↓", (-1, 0): "←",
}

def _add_dir(z, x, y, direction):
    if z is None or x is None:
        return
    anchor_dirs_by_z.setdefault(z, {})[x, y] = direction

# Exit markers for staircase passage endpoints (to_anchor only)
for p in layout.passages:
    if p.system_passage_type != "staircase":
        continue
    to_z = level_uid_to_z.get(p.to_level_uid)
    if to_z is None:
        continue
    _add_dir(to_z, p.to_x, p.to_y, "$")

# Trail arrows: real movement vector from consecutive staircase cells.
# Applied to both the current cell and the next so the start anchor
# shows its true direction rather than a generic "↑".
_stair_by_z: dict[int, list[tuple[int, int]]] = {}
for _c in layout.cells:
    if _c.system_building_element in ("staircase", "stair_anchor"):
        _stair_by_z.setdefault(_c.z, []).append((_c.x, _c.y))

_sorted_stair_z = sorted(_stair_by_z)
for _z_k in _sorted_stair_z:
    _nxt_z = _z_k + 1
    if _nxt_z not in _stair_by_z:
        continue
    _cur_cells = _stair_by_z[_z_k]
    _nxt_cells = _stair_by_z[_nxt_z]
    if len(_cur_cells) == 1 and len(_nxt_cells) == 1:
        _cx, _cy = _cur_cells[0]
        _nx, _ny = _nxt_cells[0]
        _sym = _MOVE_SYM.get((_nx - _cx, _ny - _cy))
        if _sym:
            if (_cx, _cy) not in anchor_dirs_by_z.get(_z_k, {}):
                _add_dir(_z_k, _cx, _cy, _sym)
            if (_nx, _ny) not in anchor_dirs_by_z.get(_nxt_z, {}):
                _add_dir(_nxt_z, _nx, _ny, _sym)

# Back-fill: staircase cells with no arrow yet — infer from z±1 unit neighbour
_all_stair_z = sorted(_stair_by_z)
for _i, _z_k in enumerate(_all_stair_z):
    _cells = _stair_by_z[_z_k]
    if len(_cells) != 1:
        continue
    _px, _py = _cells[0]
    if (_px, _py) in anchor_dirs_by_z.get(_z_k, {}):
        continue
    # Try z+1
    _sym = None
    if _i + 1 < len(_all_stair_z):
        _nz = _all_stair_z[_i + 1]
        if _nz == _z_k + 1 and len(_stair_by_z[_nz]) == 1:
            _nx2, _ny2 = _stair_by_z[_nz][0]
            _sym = _MOVE_SYM.get((_nx2 - _px, _ny2 - _py))
    # Try z-1
    if _sym is None and _i > 0:
        _pz = _all_stair_z[_i - 1]
        if _pz == _z_k - 1 and len(_stair_by_z[_pz]) == 1:
            _px2, _py2 = _stair_by_z[_pz][0]
            _sym = _MOVE_SYM.get((_px - _px2, _py - _py2))
    if _sym:
        _add_dir(_z_k, _px, _py, _sym)

if _z_filter is not None:
    labels = {-3: "Подвал", 0: "Первый этаж", 3: "Второй этаж"}
    label  = labels.get(_z_filter, f"z={_z_filter}")
    grid = render_level(layout.cells, z_target=_z_filter, anchor_dirs=anchor_dirs_by_z.get(_z_filter))
    if grid:
        print(f"\n--- Сетка: {label} (z={_z_filter}) ---")
        print(grid)
    else:
        print(f"\n[{label}] нет ячеек на z={_z_filter}")
else:
    all_z = sorted({c.z for c in layout.cells})
    level_z_set = {lvl.z for lvl in layout.levels}
    floor_names = ["Первый этаж", "Второй этаж", "Третий этаж", "Четвёртый этаж",
                   "Пятый этаж", "Шестой этаж"]
    floor_idx = 0
    level_labels: dict[int, str] = {}
    for lvl in sorted(layout.levels, key=lambda l: l.z):
        if lvl.z < 0:
            level_labels[lvl.z] = "Подвал"
        else:
            level_labels[lvl.z] = floor_names[floor_idx] if floor_idx < len(floor_names) else f"Этаж {floor_idx+1}"
            floor_idx += 1
    for z in all_z:
        tag = f" [{level_labels[z]}]" if z in level_labels else " [промежуточный]"
        marker = "★" if z in level_z_set else "·"
        grid = render_level(layout.cells, z_target=z, anchor_dirs=anchor_dirs_by_z.get(z))
        print(f"\n{marker} z={z:+d}{tag}")
        print(grid if grid else "  (нет ячеек)")
